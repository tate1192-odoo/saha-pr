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

                next_date = fields.Date.context_today(self)

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
                        "location_id": False,
                        "tax_id": [Command.set(line.tax_ids.ids)],
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
        # Never touch cancelled/completed orders.
        if order.state in ("cancel", "done"):
            raise UserError(
                _(
                    "A contract cannot be created from a cancelled "
                    "or completed sale order."
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
                            "service_type_id": line.service_type_id.id,
                            "location_id": line.location_id.id,
                            "tax_id": [Command.set(line.tax_id.ids)],
                            "recurring_interval": line.recurring_interval,
                            "recurring_rule_type": line.recurring_rule_type,
                            "recurring_next_date": line.recurring_next_date,
                            "date_start": line.recurring_next_date or self.date_start,
                            "date_end": line.date_end or self.date_end,
                        }
                    )
                )

        contract_vals = {
            "partner_id": order.partner_id.id,
            "company_id": self.company_id.id,
            "user_id": order.user_id.id,
            "description": order.note,
            "date_start": self.date_start,
            "date_end": self.date_end,
            "service_type_ids": [Command.set(self.service_type_ids.ids)],
            "location_ids": [Command.set(self.location_ids.ids)],
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

        order_vals = {"service_contract_id": contract.id}
        # Only advance draft/sent orders; confirmed orders must keep their state
        # (the wizard must never push a sale order back to "sent").
        if order.state in ("draft", "sent"):
            order_vals["state"] = "sent"
        order.write(order_vals)

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
    recurring_next_date = fields.Date("First Date")
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
