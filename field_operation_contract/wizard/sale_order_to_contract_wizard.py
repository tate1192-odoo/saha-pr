# field_operation_contract/wizard/sale_order_to_contract_wizard.py

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class SaleOrderContractWizard(models.TransientModel):
    _name = "sale.order.contract.wizard"
    _description = "Create Contract from Sale Order"

    sale_order_id = fields.Many2one("sale.order", required=True, readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    date_start = fields.Date(
        default=lambda self: fields.Date.context_today(self), required=True
    )
    date_end = fields.Date()
    service_type_ids = fields.Many2many("field.operation.type", string="Service Types")
    location_ids = fields.Many2many("res.partner", string="Branches / Locations")
    line_ids = fields.One2many(
        "sale.order.contract.wizard.line", "wizard_id", string="Lines"
    )

    # ---------------------------------------------------------
    # DEFAULT GET
    # ---------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order = self.env["sale.order"].browse(self.env.context.get("active_id"))

        if not order.exists():
            return res

        # Block converting a sale order that is already linked to a contract.
        if order.service_contract_id:
            raise UserError(_("This sale order is already linked to a contract."))

        lines = []
        unique_service_types = self.env["field.operation.type"]

        default_location = order.partner_shipping_id
        if not default_location:
            delivery_id = order.partner_id.address_get(["delivery"]).get("delivery")
            default_location = self.env["res.partner"].browse(delivery_id)
        if not default_location:
            default_location = order.partner_id

        for line in order.order_line:
            if not line.display_type and line.product_id.type != "service":
                continue
            wizard_line_vals = {
                "sale_line_id": line.id,
                "name": line.name,
                "display_type": line.display_type,
                "sequence": line.sequence,
            }

            # Only complete the remaining details for real product lines
            # (sections and notes keep just the descriptive fields).
            if not line.display_type:
                if line.product_id and line.product_id.service_type_id:
                    unique_service_types |= line.product_id.service_type_id

                next_date = res.get("date_start") or fields.Date.context_today(self)

                wizard_line_vals.update(
                    {
                        "product_id": line.product_id.id,
                        "product_uom_qty": line.product_uom_qty,
                        "price_unit": line.price_unit,
                        "discount": line.discount,
                        "uom_id": line.product_uom_id.id,
                        "service_type_id": line.product_id.service_type_id.id
                        if line.product_id.service_type_id
                        else False,
                        "location_id": default_location.id,
                        "tax_id": [Command.set(line.tax_ids.ids)],
                        "date_start": next_date,
                        "recurring_interval": 1,
                        "recurring_rule_type": "monthly",
                        "recurring_next_date": next_date,
                    }
                )

            lines.append(Command.create(wizard_line_vals))

        res.update(
            {
                "sale_order_id": order.id,
                "partner_id": order.partner_id.id,
                "company_id": order.company_id.id,
                "line_ids": lines,
                "service_type_ids": [Command.set(unique_service_types.ids)],
                "date_end": fields.Date.context_today(self) + relativedelta(years=1),
            }
        )
        return res

    def _validate_lines(self, valid_lines):
        """Validate the periodic contract lines before creating the contract."""
        if self.date_end and self.date_start and self.date_end < self.date_start:
            raise UserError(
                _("The contract end date cannot be earlier than its start date.")
            )

        for line in valid_lines:
            if not line.product_id or line.product_id.type != "service":
                raise UserError(
                    _(
                        "Line '%(line)s' must use a service product.",
                        line=line.name or line.product_id.display_name,
                    )
                )
            if not line.product_uom_qty or line.product_uom_qty <= 0:
                raise UserError(
                    _(
                        "Line '%(line)s' must have a quantity greater than zero. "
                        "For a periodic contract the quantity is the number of "
                        "periods (e.g. 12 for a 12-month monthly contract).",
                        line=line.name or line.product_id.display_name,
                    )
                )
            if not line.location_id:
                raise UserError(
                    _(
                        "Line '%(line)s' has no service location. Select the "
                        "branch/location for every product line.",
                        line=line.name or line.product_id.display_name,
                    )
                )
            if not line.recurring_next_date:
                raise UserError(
                    _(
                        "Line '%(line)s' has no first service date.",
                        line=line.name or line.product_id.display_name,
                    )
                )
            line_end = line.date_end or self.date_end
            if line_end and line_end < line.recurring_next_date:
                raise UserError(
                    _(
                        "Line '%(line)s' has an end date earlier than its first "
                        "service date.",
                        line=line.name or line.product_id.display_name,
                    )
                )
            if self.date_start and line.recurring_next_date < self.date_start:
                raise UserError(
                    _(
                        "Line '%(line)s' starts before the contract start date. "
                        "Set the contract start date first, then the line dates.",
                        line=line.name or line.product_id.display_name,
                    )
                )

    # ---------------------------------------------------------
    # CREATE CONTRACT
    # ---------------------------------------------------------
    def action_create_contract(self):
        self.ensure_one()

        order = self.sale_order_id

        # --- SERVER-SIDE GUARDS ---
        # A sale order can be converted only once.
        if order.service_contract_id:
            raise UserError(_("This sale order is already linked to a contract."))
        # Only quotations can be converted. A confirmed order already has
        # delivery/invoicing obligations and must not become a contract source.
        if order.state not in ("draft", "sent"):
            raise UserError(
                _(
                    "Only draft or sent quotations can be converted to a "
                    "contract. This sale order is in state '%s'.",
                    order.state,
                )
            )
        # The button is only visible for contract orders, but the RPC entry
        # point must enforce the same rule.
        if order.order_types != "contract":
            raise UserError(
                _('Contracts can only be created from sale orders of type "Contract".')
            )
        # The customer is always the sale order customer.
        if self.partner_id and self.partner_id != order.partner_id:
            raise UserError(
                _(
                    "The selected customer does not match the customer "
                    "of the sale order."
                )
            )

        # --- AUTOMATIC MODE SELECTION ---
        # Analyse real product lines only (sections/notes are ignored).
        valid_lines = self.line_ids.filtered(lambda ln: not ln.display_type)

        if not valid_lines:
            raise UserError(
                _(
                    "There is no product line in this sale order "
                    "to create a contract from."
                )
            )
        if not self.service_type_ids:
            raise UserError(
                _("At least one service type is required to create a contract.")
            )
        self._validate_lines(valid_lines)

        all_rules = valid_lines.mapped("recurring_rule_type")
        all_intervals = valid_lines.mapped("recurring_interval")
        all_dates = valid_lines.mapped("recurring_next_date")

        is_line_recurrence = False

        # Different rules or intervals -> line-based recurrence.
        if len(set(all_rules)) > 1 or len(set(all_intervals)) > 1:
            is_line_recurrence = True

        # Different dates (manual date entry) -> line-based recurrence.
        if len(set(all_dates)) > 1:
            is_line_recurrence = True

        contract_lines = []

        for line in self.line_ids:
            # --- LINE BUILDING ---
            if line.display_type:
                # Section or note: only carry the descriptive fields.
                contract_lines.append(
                    Command.create(
                        {
                            "name": line.name,
                            "display_type": line.display_type,
                            "sequence": line.sequence,
                        }
                    )
                )
            else:
                # Product line: carry every service detail.
                contract_lines.append(
                    Command.create(
                        {
                            "name": line.name,
                            "display_type": line.display_type,
                            "product_id": line.product_id.id,
                            "total_service": line.product_uom_qty,
                            "price_unit": line.price_unit,
                            "discount": line.discount,
                            "uom_id": line.uom_id.id,
                            "service_type_id": (
                                line.service_type_id.id
                                if line.service_type_id
                                else (
                                    line.product_id.service_type_id.id
                                    or self.service_type_ids[:1].id
                                )
                            ),
                            "location_id": line.location_id.id,
                            "tax_id": [Command.set(line.tax_id.ids)],
                            "recurring_interval": line.recurring_interval,
                            "recurring_rule_type": line.recurring_rule_type,
                            "recurring_next_date": line.recurring_next_date,
                            "date_start": (
                                line.recurring_next_date
                                or line.date_start
                                or self.date_start
                            ),
                            "date_end": line.date_end or self.date_end,
                        }
                    )
                )

        contract_locations = self.location_ids or valid_lines.mapped("location_id")

        contract_vals = {
            "partner_id": order.partner_id.id,
            "company_id": order.company_id.id,
            "user_id": order.user_id.id,
            "description": order.note,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "service_type_ids": [Command.set(self.service_type_ids.ids)],
            "location_ids": [Command.set(contract_locations.ids)],
            "contract_line_ids": contract_lines,
            "line_recurrence": is_line_recurrence,
        }

        # In header mode the per-line period would otherwise be lost: copy the
        # first line's recurrence to the contract header so that, for example, a
        # weekly schedule is not silently turned into the default monthly one.
        if not is_line_recurrence:
            first_line = valid_lines[:1]
            contract_vals.update(
                {
                    "recurring_rule_type": first_line.recurring_rule_type,
                    "recurring_interval": first_line.recurring_interval,
                }
            )

        contract = self.env["field.operation.contract"].create(contract_vals)

        # The quotation is only the commercial source. Link it to the contract
        # and close it: leaving it in "sent" would keep it in the sales pipeline
        # and would allow a user to confirm/invoice it in parallel with the
        # periodic orders generated by the contract.
        order.write({"service_contract_id": contract.id})
        order.action_cancel()
        order.message_post(
            body=_(
                "This quotation was converted to contract %(contract)s and "
                "closed. The contract now carries the recurring schedule.",
                contract=contract.name,
            )
        )

        # --- VIEW ACTION AND USER NOTICE ---
        result = {
            "type": "ir.actions.act_window",
            "res_model": "field.operation.contract",
            "res_id": contract.id,
            "view_mode": "form",
            "target": "current",
        }

        # Warn the user when the recurrence fell back to line-based mode.
        if is_line_recurrence:
            result["warning"] = {
                "title": _("Warning: Different Periods Detected!"),
                "message": _(
                    "The recurrence periods of the selected services vary "
                    "(e.g., Monthly, Quarterly, etc.).\n"
                    "Therefore, the system has activated the "
                    '"Line-based Recurrence" mode.\n'
                    "Please verify that the line dates in the contract "
                    "details are correct."
                ),
            }

        return result


# ---------------------------------------------------------
# WIZARD LINE (CHILD MODEL)
# ---------------------------------------------------------
class SaleOrderContractWizardLine(models.TransientModel):
    _name = "sale.order.contract.wizard.line"
    _description = "Wizard Line"

    name = fields.Text(string="Description")
    sequence = fields.Integer(default=10)
    date_start = fields.Date(default=lambda self: fields.Date.context_today(self))
    date_end = fields.Date()
    recurring_interval = fields.Integer(default=1, string="Repeat Every")
    recurring_rule_type = fields.Selection(
        [
            ("daily", "Day(s)"),
            ("weekly", "Week(s)"),
            ("monthly", "Month(s)"),
            ("monthlylastday", "Month(s) last day"),
            ("quarterly", "Quarter(s)"),
            ("semesterly", "Semester(s)"),
            ("yearly", "Year(s)"),
        ],
        default="monthly",
    )
    recurring_next_date = fields.Date(
        "First Service Date",
        default=lambda self: fields.Date.context_today(self),
    )
    product_uom_qty = fields.Float()
    price_unit = fields.Float()
    discount = fields.Float()
    uom_id = fields.Many2one("uom.uom")
    service_type_id = fields.Many2one("field.operation.type")
    wizard_id = fields.Many2one("sale.order.contract.wizard")
    sale_line_id = fields.Many2one("sale.order.line")
    product_id = fields.Many2one("product.product")
    display_type = fields.Selection(
        [
            ("line_section", "Section"),
            ("line_note", "Note"),
        ]
    )
    location_id = fields.Many2one(
        "res.partner",
        string="Branch/Location",
        help="Select the branch this service line applies to.",
    )
    tax_id = fields.Many2many(
        "account.tax",
        string="Taxes",
        domain=[("type_tax_use", "=", "sale")],
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Fill the service line from the selected product.

        The wizard starts from a sale order, but users may add a line manually.
        Without this onchange the recurrence, service type and tax fields stay
        empty and the contract line is created incomplete.
        """
        for line in self:
            if not line.product_id:
                continue
            line.name = line.product_id.get_product_multiline_description_sale()
            line.price_unit = line.product_id.lst_price
            line.uom_id = line.product_id.uom_id
            line.tax_id = line.product_id.taxes_id
            line.service_type_id = line.product_id.service_type_id
            if not line.product_uom_qty:
                line.product_uom_qty = 1.0
