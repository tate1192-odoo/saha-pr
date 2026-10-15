# --- field_operation_contract.py ---
import logging
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class FieldOperationContract(models.Model):
    _name = "field.operation.contract"
    _description = "Field Operation Contract"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "portal.mixin",
        "service.contract.recurring.mixin",
    ]

    name = fields.Char(string="Contract No", default="/", copy=False, readonly=True)
    subject = fields.Char(
        string="Subject",
        default=lambda self: _("Annual Service Contract"),
    )
    active = fields.Boolean(default=True, tracking=True)
    date_start = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    date_end = fields.Date(string="End Date", index=True, tracking=True)
    recurring_next_date = fields.Date(
        string="Date of Next Service (Contract)",
        compute="_compute_recurring_next_date",
        store=True,
        readonly=False,
        copy=False,
        help=(
            "Next date for the whole contract (used if 'Recurrence at line "
            "level' is unchecked)."
        ),
    )

    signature_status = fields.Boolean(
        string="Signature Status", default=False, tracking=True
    )
    signature_file = fields.Binary(string="Signature File", copy=False, attachment=True)
    signatory_name = fields.Char(string="Signatory Name", tracking=True, copy=False)
    signature_date = fields.Datetime(string="Signature Date", tracking=True, copy=False)

    line_recurrence = fields.Boolean(string="Recurrence at line level?", default=False)

    contract_terms = fields.Html(string="Contract Terms")
    description = fields.Html(string="Description")
    service_count = fields.Integer(
        compute="_compute_service_count", string="Operations Count"
    )
    sale_count = fields.Integer(compute="_compute_sale_count", string="Sales Count")
    rest_days = fields.Integer(compute="_compute_rest_days", string="Remaining Days")
    user_id = fields.Many2one(
        "res.users",
        string="Manager",
        default=lambda self: self.env.user,
        tracking=True,
    )
    amount_untaxed = fields.Monetary(
        string="Untaxed Amount", compute="_compute_total_amount", store=True
    )
    amount_tax = fields.Monetary(
        string="Tax Amount", compute="_compute_total_amount", store=True
    )
    total_amount = fields.Monetary(
        string="Total Amount", compute="_compute_total_amount", store=True
    )
    total_service_count = fields.Integer(
        string="Total Services",
        compute="_compute_service_counters",
        help="Total number of services (header-based mode, sum of lines).",
    )
    remaining_service_count = fields.Integer(
        string="Remaining Services",
        compute="_compute_service_counters",
        help="Remaining number of services (header-based mode, sum of lines).",
    )
    partner_id = fields.Many2one(
        "res.partner", string="Customer", required=True, tracking=True, index=True
    )
    contact_id = fields.Many2one(
        "res.partner", string="Contact", domain="[('id', 'child_of', partner_id)]"
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    service_type_ids = fields.Many2many(
        "field.operation.type", string="Service Type", required=True
    )
    tag_ids = fields.Many2many("field.operation.contract.tag", string="Tags")
    location_ids = fields.Many2many("res.partner", string="Branch/Location")
    generated_sale_ids = fields.One2many(
        "sale.order", "service_contract_id", string="Sales"
    )
    generated_operation_ids = fields.One2many(
        "field.operation", "contract_id", string="Services"
    )
    contract_line_ids = fields.One2many(
        "field.operation.contract.line",
        "contract_id",
        string="Contract Lines",
        copy=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("expired", "Expired"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        tracking=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains(
        "signature_status", "signature_file", "signatory_name", "signature_date"
    )
    def _check_signature_integrity(self):
        for rec in self:
            if not rec.signature_status:
                continue
            if not (rec.signature_file and rec.signatory_name and rec.signature_date):
                raise ValidationError(
                    _(
                        "A signed contract requires a signature file, a signatory "
                        "name and a signature date."
                    )
                )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends("contract_line_ids.price_subtotal", "contract_line_ids.price_tax")
    def _compute_total_amount(self):
        for rec in self:
            lines = rec.contract_line_ids.filtered(lambda line: not line.display_type)
            rec.amount_untaxed = sum(lines.mapped("price_subtotal"))
            rec.amount_tax = sum(lines.mapped("price_tax"))
            rec.total_amount = rec.amount_untaxed + rec.amount_tax

    @api.depends(
        "contract_line_ids.total_service",
        "contract_line_ids.remaining_count",
        "contract_line_ids.display_type",
    )
    def _compute_service_counters(self):
        """Sum total/remaining services over the non-display lines.

        Only meaningful in header-based mode; the figures are hidden in the
        UI when recurrence runs at line level.
        """
        for rec in self:
            lines = rec.contract_line_ids.filtered(lambda line: not line.display_type)
            rec.total_service_count = sum(lines.mapped("total_service"))
            rec.remaining_service_count = sum(lines.mapped("remaining_count"))

    @api.depends("generated_operation_ids")
    def _compute_service_count(self):
        for rec in self:
            rec.service_count = len(rec.generated_operation_ids)

    @api.depends("generated_sale_ids")
    def _compute_sale_count(self):
        for rec in self:
            rec.sale_count = len(rec.generated_sale_ids)

    @api.depends("date_end", "state")
    def _compute_rest_days(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if (
                rec.date_end
                and rec.date_end >= today
                and rec.state not in ("cancel", "expired")
            ):
                rec.rest_days = (rec.date_end - today).days
            else:
                rec.rest_days = 0

    def _compute_access_url(self):
        for rec in self:
            rec.access_url = f"/my/contract/{rec.id}"

    @api.depends(
        "line_recurrence",
        "contract_line_ids.display_type",
        "contract_line_ids.recurring_next_date",
        "contract_line_ids.remaining_count",
        "next_period_date_start",
        "recurring_generation_type",
        "recurring_offset",
        "recurring_rule_type",
        "recurring_interval",
        "date_end",
        "last_date_processed",
    )
    def _compute_recurring_next_date(self):
        for rec in self:
            if rec.line_recurrence:
                lines = rec.contract_line_ids.filtered(
                    lambda line: not line.display_type
                    and line.recurring_next_date
                    and line.remaining_count > 0
                )
                dates = lines.mapped("recurring_next_date")
                rec.recurring_next_date = min(dates) if dates else False
            else:
                # Header mode: compute from the contract recurrence settings.
                # Do not delegate to the mixin: it gates on remaining_count,
                # which is meaningless on the contract header (always 0).
                rec.recurring_next_date = rec.get_next_recurring_date(
                    rec.next_period_date_start,
                    rec.recurring_generation_type,
                    rec.recurring_offset,
                    rec.recurring_rule_type,
                    rec.recurring_interval,
                    max_date_end=rec.date_end,
                )

    # -------------------------------------------------------------------------
    # BATCH PROCESSING LOGIC (OCA STYLE ADAPTATION)
    # -------------------------------------------------------------------------

    @api.model
    def _get_contracts_to_process_domain(self, date_ref=None):
        """Domain selecting the contracts that must be processed."""
        if not date_ref:
            date_ref = fields.Date.context_today(self)
        return [
            ("state", "=", "confirmed"),
            ("active", "=", True),
            "|",
            ("date_end", "=", False),
            ("date_end", ">=", date_ref),
        ]

    @api.model
    def action_recurring_process(self):
        """Cron Job Entry Point"""
        self._check_service_group_manager()
        date_ref = fields.Date.context_today(self)
        domain = self._get_contracts_to_process_domain(date_ref)
        contracts = self.search(domain)

        if not contracts:
            return

        _logger.info("=== RECURRING PROCESS STARTED (OCA STYLE) ===")
        _logger.info("Date: %s, Contracts to check: %s", date_ref, len(contracts))

        # Group the contracts by company so every batch is created in the
        # matching company context (multi-company safety).
        companies = contracts.mapped("company_id")
        for company in companies:
            company_contracts = contracts.filtered(
                lambda c, company=company: c.company_id == company
            ).with_company(company)
            self._recurring_create_sale_ops(company_contracts, date_ref)

        _logger.info("=== RECURRING PROCESS COMPLETED ===")
        return True

    def _recurring_create_sale_ops(self, contracts, date_ref):
        """Create the prepared sale orders/operations in bulk, then update."""
        # 1. DATA PREPARATION PHASE (no DB write yet)
        (
            sale_orders_vals,
            sale_order_keys,
            field_ops_vals,
            lines_to_update,
            contracts_to_update,
        ) = self._prepare_recurrence_values(contracts, date_ref)

        if not sale_orders_vals and not field_ops_vals:
            return

        # 2. BULK CREATE PHASE (always in the contracts' own company context)
        # A. Create the sale orders.
        sale_orders = contracts.env["sale.order"].create(sale_orders_vals)

        # Map the unique_key of each prepared order to the created record id.
        key_to_so_id = dict(zip(sale_order_keys, sale_orders.ids, strict=False))

        # B. Create the field operations, linking each to its sale order.
        for op_vals in field_ops_vals:
            op_vals["sale_id"] = key_to_so_id.get(op_vals.pop("so_unique_key"))
        operations = contracts.env["field.operation"].create(field_ops_vals)

        # 3. TRACKING AND UPDATE PHASE
        # Keep the latest computed state for each updated line.
        for line, updates_list in lines_to_update.items():
            line.write(updates_list[-1])
            line.flush_recordset()

        # Apply the header-mode contract updates.
        for contract, updates in contracts_to_update.items():
            contract.write(updates)

        self._notify_generated_documents(sale_orders, operations)

        _logger.info(
            "Created %s Sale Orders and %s Field Operations",
            len(sale_orders),
            len(operations),
        )

    def _prepare_recurrence_values(self, contracts, date_ref):
        """Collect the bulk-create values for every given contract (no write)."""
        sale_orders_vals = []
        sale_order_keys = []  # keeps the unique_key of each prepared order
        field_ops_vals = []
        lines_to_update = defaultdict(list)  # {line: [values]}
        contracts_to_update = defaultdict(dict)  # {contract: {field: value}}

        for contract in contracts:
            if contract.line_recurrence:
                so_vals, ops_vals, line_updates = (
                    contract._prepare_line_recurrence_values(date_ref)
                )
                contract_updates = {}
            else:
                (
                    so_vals,
                    ops_vals,
                    contract_updates,
                    line_updates,
                ) = contract._prepare_header_recurrence_values(date_ref)
            for so_val in so_vals:
                # unique_key is only a mapping helper, never a sale.order field.
                sale_order_keys.append(so_val.pop("unique_key"))
                sale_orders_vals.append(so_val)
            field_ops_vals.extend(ops_vals)
            if contract_updates:
                contracts_to_update[contract].update(contract_updates)
            for line, vals in line_updates.items():
                lines_to_update[line].append(vals)

        return (
            sale_orders_vals,
            sale_order_keys,
            field_ops_vals,
            lines_to_update,
            contracts_to_update,
        )

    def _notify_generated_documents(self, sale_orders, operations):
        """Post one summary message per contract that generated documents."""
        totals_by_contract = defaultdict(lambda: {"sales": 0, "ops": 0})
        for so in sale_orders:
            if so.service_contract_id:
                totals_by_contract[so.service_contract_id]["sales"] += 1
        for operation in operations:
            if operation.contract_id:
                totals_by_contract[operation.contract_id]["ops"] += 1
        for contract, totals in totals_by_contract.items():
            body = (
                _("Generated %(sales)s sale order(s) and %(ops)s operation(s).")
                % totals
            )
            contract.message_post(body=body)

    # -------------------------------------------------------------------------
    # DATA PREPARATION HELPERS
    # -------------------------------------------------------------------------
    def _prepare_header_recurrence_values(self, process_date):
        """Prepare header-based generation values (does not write to the DB)."""
        self.ensure_one()
        if not self.recurring_next_date or self.recurring_next_date > process_date:
            return [], [], {}, {}

        valid_lines = self.contract_line_ids.filtered(
            lambda line: not line.display_type
            and line.product_id
            and line.product_id.type == "service"
            and (not line.date_end or line.date_end >= process_date)
            and line.remaining_count > 0
        )

        if not valid_lines:
            return [], [], {}, {}

        so_vals_list = []
        op_vals_list = []
        lines_updates = {}  # {line: values to write}

        # Group the lines by delivery location.
        lines_by_location = self._group_lines_by_location(valid_lines)

        for location, loc_lines in lines_by_location.items():
            unique_key = f"{self.id}_{location.id}"

            # 1. Sale order values.
            so_vals = {
                "unique_key": unique_key,
                "partner_id": self.partner_id.id,
                "partner_shipping_id": location.id,
                "company_id": self.company_id.id,
                "user_id": self.user_id.id,
                "origin": f"{self.name} - {location.name}",
                "order_types": "invoice",
                "service_contract_id": self.id,
                "date_order": fields.Datetime.now(),
                "order_line": [
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": f"Location: {location.name}",
                            "sequence": 10,
                        }
                    )
                ],
            }

            # Add one order line and one operation per contract line.
            for line in loc_lines:
                so_vals["order_line"].append(
                    Command.create(
                        {
                            "product_id": line.product_id.id,
                            "product_uom_qty": 1,
                            "price_unit": line.price_unit,
                            "name": line.name,
                            "discount": line.discount,
                            "product_uom_id": line.uom_id.id,
                            "sequence": 20,
                        }
                    )
                )

                # 2. Operation values.
                subject = line.product_id.name if line.product_id else line.name
                service_type_id = (
                    line.service_type_id.id if line.service_type_id else False
                )
                op_vals_list.append(
                    {
                        "so_unique_key": unique_key,
                        "contract_id": self.id,
                        "partner_id": self.partner_id.id,
                        "address_id": location.id,
                        "subject": subject,
                        "description": line.name,
                        "service_type_id": service_type_id,
                        "start_date": fields.Datetime.to_datetime(process_date),
                        "status": "draft",
                    }
                )

                # Line values written later in the update phase.
                lines_updates[line] = {
                    "generated_occurrences": line.generated_occurrences + 1,
                }

            so_vals_list.append(so_vals)

        # Header update: only ``last_date_processed`` moves forward, to the end
        # of the period that contains ``process_date``. ``recurring_next_date``
        # is computed from it and must not be written directly, otherwise the
        # computed date is discarded and the contract re-generates every day.
        contract_updates = {
            "last_date_processed": self._get_period_end_date(process_date),
        }

        return so_vals_list, op_vals_list, contract_updates, lines_updates

    def _prepare_line_recurrence_values(self, process_date):
        """Prepare line-based generation values (does not write to the DB)."""
        self.ensure_one()

        valid_lines = self.contract_line_ids.filtered(
            lambda line: not line.display_type
            and line.product_id
            and line.product_id.type == "service"
        )

        lines_to_process = valid_lines.filtered(
            lambda line: line.recurring_next_date
            and line.recurring_next_date <= process_date
            and (not line.date_end or line.recurring_next_date <= line.date_end)
            and line.remaining_count > 0
        )

        if not lines_to_process:
            return [], [], {}

        so_vals_list = []
        op_vals_list = []
        lines_updates = {}  # {line: values to write}

        lines_by_location = self._group_lines_by_location(lines_to_process)

        for location, loc_lines in lines_by_location.items():
            unique_key = f"{self.id}_{location.id}"

            so_vals = {
                "unique_key": unique_key,
                "partner_id": self.partner_id.id,
                "partner_shipping_id": location.id,
                "company_id": self.company_id.id,
                "user_id": self.user_id.id,
                "origin": f"{self.name} - {location.name}",
                "order_types": "service",
                "service_contract_id": self.id,
                "date_order": fields.Datetime.now(),
                "order_line": [
                    Command.create(
                        {
                            "display_type": "line_section",
                            "name": f"Location: {location.name}",
                            "sequence": 10,
                        }
                    )
                ],
            }

            for line in loc_lines:
                so_vals["order_line"].append(
                    Command.create(
                        {
                            "product_id": line.product_id.id,
                            "product_uom_qty": 1,
                            "price_unit": line.price_unit,
                            "name": line.name,
                            "discount": line.discount,
                            "product_uom_id": line.uom_id.id,
                            "sequence": 20,
                        }
                    )
                )

                op_vals_list.append(
                    {
                        "so_unique_key": unique_key,
                        "contract_id": self.id,
                        "partner_id": self.partner_id.id,
                        "address_id": location.id,
                        "subject": line.product_id.name,
                        "description": line.name,
                        "service_type_id": line.service_type_id.id,
                        "start_date": fields.Datetime.to_datetime(
                            line.recurring_next_date
                        ),
                        "status": "draft",
                    }
                )

                # Advance the line dates logically (no write here).
                old_next_date = line.recurring_next_date
                period_end_date = line._get_period_end_date(old_next_date)

                # Bump the counter and store the period end in one write.
                lines_updates[line] = {
                    "generated_occurrences": line.generated_occurrences + 1,
                    "last_date_processed": period_end_date,
                }

                # Recompute the line's own next date.
                next_period_start = period_end_date + relativedelta(days=1)
                new_next_date = line.get_next_recurring_date(
                    next_period_start,
                    line.recurring_generation_type,
                    line.recurring_offset,
                    line.recurring_rule_type,
                    line.recurring_interval,
                    max_date_end=line.date_end,
                )
                lines_updates[line]["recurring_next_date"] = new_next_date

            so_vals_list.append(so_vals)

        return so_vals_list, op_vals_list, lines_updates

    def _group_lines_by_location(self, lines):
        lines_by_location = defaultdict(list)
        for line in lines:
            location = line.location_id if line.location_id else self.partner_id
            lines_by_location[location].append(line)
        return lines_by_location

    # -------------------------------------------------------------------------
    # CREATE & ONCHANGE
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                sequence = self.env["ir.sequence"].next_by_code(
                    "field.operation.contract"
                )
                vals["name"] = sequence or _("New")
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # SECURITY GUARDS
    # -------------------------------------------------------------------------
    def _check_service_group_user(self):
        """Only field-service office users may drive the contract workflow."""
        if not (
            self.env.user.has_group("field_operation.service_group_user")
            or self.env.user.has_group("field_operation.service_group_manager")
        ):
            raise AccessError(
                _("You are not allowed to manage field operation contracts.")
            )

    def _check_service_group_manager(self):
        """Only field-service managers may run the recurring process."""
        if not self.env.user.has_group("field_operation.service_group_manager"):
            raise AccessError(_("Only service managers may run the recurring process."))

    def unlink(self):
        for contract in self:
            if contract.generated_sale_ids or contract.generated_operation_ids:
                raise UserError(
                    _(
                        "This contract has linked sale orders or operations and "
                        "cannot be deleted. Cancel it instead."
                    )
                )
        return super().unlink()

    # -------------------------------------------------------------------------
    # ACTIONS
    # -------------------------------------------------------------------------
    def action_confirm(self):
        self._check_service_group_user()
        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _("Only draft contracts can be confirmed: %s") % rec.name
                )
            if not rec.contract_line_ids:
                raise UserError(_("Please add contract lines for: %s") % rec.name)
            if not rec.line_recurrence and not rec.recurring_next_date:
                rec.recurring_next_date = rec.date_start
        self.write({"state": "confirmed"})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Contract(s) confirmed successfully."),
                "sticky": False,
                "type": "success",
            },
        }

    def action_cancel(self):
        self._check_service_group_user()
        for rec in self:
            if rec.state == "cancel":
                raise UserError(_("This contract is already cancelled."))
        # Cancel the linked draft sale orders and draft operations so no live
        # document is left pointing at a cancelled contract.
        draft_sales = self.generated_sale_ids.filtered(
            lambda so: so.state in ("draft", "sent")
        )
        draft_sales.action_cancel()
        draft_operations = self.generated_operation_ids.filtered(
            lambda operation: operation.status == "draft"
        )
        draft_operations.write({"status": "cancel"})
        return self.write({"state": "cancel"})

    def action_set_to_draft(self):
        self._check_service_group_user()
        return self.write({"state": "draft"})

    def action_expire(self):
        self._check_service_group_user()
        return self.write({"state": "expired"})

    def action_view_operations(self):
        self.ensure_one()
        return {
            "name": _("Operations"),
            "res_model": "field.operation",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id},
            "type": "ir.actions.act_window",
        }

    def action_view_sales(self):
        self.ensure_one()
        if self.sale_count == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "views": [(self.env.ref("sale.view_order_form").id, "form")],
                "view_mode": "form",
                "target": "current",
                "domain": [("service_contract_id", "=", self.id)],
                "context": {"default_service_contract_id": self.id},
            }
        return {
            "name": _("Sales Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("service_contract_id", "=", self.id)],
            "context": {"default_service_contract_id": self.id},
            "type": "ir.actions.act_window",
        }
