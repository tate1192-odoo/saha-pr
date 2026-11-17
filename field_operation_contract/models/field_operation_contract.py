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
    generation_lead_days = fields.Integer(
        string="Generation Lead (days)",
        default=0,
        help="Create the periodic orders and operations this many days before "
        "the service date, so the office can plan staff and routes. 0 uses the "
        "company setting.",
    )

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
        "sale.order",
        "service_contract_id",
        string="Sales",
        domain=[("order_types", "!=", "contract")],
        help="Periodic sale orders generated from this contract. The source "
        "quotation (order type 'contract') is intentionally excluded.",
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
    def action_recurring_process(self, dry_run=False):
        """Periodic generation entry point (cron and the preview button).

        ``dry_run=True`` returns what *would* be created and writes nothing.
        """
        self._check_service_group_manager()
        date_ref = fields.Date.context_today(self)
        contracts = self.search(self._get_contracts_to_process_domain(date_ref))

        if not contracts:
            return [] if dry_run else True

        _logger.info("=== RECURRING PROCESS STARTED (%s) ===", date_ref)
        _logger.info("Contracts to check: %s (dry_run=%s)", len(contracts), dry_run)

        results = []
        # Group the contracts by company so every batch is created in the
        # matching company context (multi-company safety).
        companies = contracts.mapped("company_id")
        for company in companies:
            company_contracts = contracts.filtered(
                lambda c, company=company: c.company_id == company
            ).with_company(company)
            results.extend(
                self._recurring_create_sale_ops(
                    company_contracts, date_ref, dry_run=dry_run
                )
            )

        _logger.info("=== RECURRING PROCESS COMPLETED ===")
        return results if dry_run else True

    def action_preview_recurring_process(self):
        """Form button: show what the next run would create, writing nothing."""
        self._check_service_group_manager()
        results = (
            self.env["field.operation.contract"]
            .sudo()
            .action_recurring_process(dry_run=True)
        )
        lines = [
            _(
                "%(contract)s: %(sales)s order(s), %(operations)s operation(s), "
                "%(amount).2f"
            )
            % row
            for row in results
            if row.get("sales") or row.get("operations")
        ]
        errors = [
            _("%(contract)s: ERROR %(error)s") % row
            for row in results
            if row.get("error")
        ]
        body = "\n".join(errors + lines) or _("Nothing to generate right now.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Recurring preview (nothing was written)"),
                "message": body,
                "sticky": True,
                "type": "warning" if errors else "info",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _recurring_create_sale_ops(self, contracts, date_ref, dry_run=False):
        """Generate the periodic documents contract by contract.

        Every contract runs in its own savepoint, so a single broken contract is
        reported on its chatter instead of stopping the whole book.
        """
        results = []
        for contract in contracts:
            if dry_run:
                results.append(contract._preview_recurrence_values(date_ref))
                continue
            try:
                with self.env.cr.savepoint():
                    results.append(contract._create_recurrence_documents(date_ref))
            except Exception as exc:  # noqa: BLE001 - isolate a single contract
                _logger.exception(
                    "Periodic generation failed for contract %s", contract.name
                )
                self.env.invalidate_all()
                try:
                    contract.message_post(
                        body=_(
                            "Periodic generation failed for %(contract)s: %(error)s",
                            contract=contract.name,
                            error=str(exc),
                        )
                    )
                except Exception:  # noqa: BLE001 - never mask the real error
                    _logger.exception("Could not post the generation error")
                results.append(
                    {
                        "contract": contract.name,
                        "sales": 0,
                        "operations": 0,
                        "amount": 0.0,
                        "error": str(exc),
                    }
                )
        return results

    def _preview_recurrence_values(self, date_ref):
        """Report what the generation would create for this contract."""
        self.ensure_one()
        (
            sale_orders_vals,
            _sale_order_keys,
            field_ops_vals,
            lines_to_update,
            _contracts_to_update,
        ) = self._prepare_recurrence_values(self, date_ref)

        amount = 0.0
        for so_vals in sale_orders_vals:
            for command in so_vals.get("order_line", []):
                if isinstance(command, (list, tuple)) and len(command) == 3:
                    vals = command[2] or {}
                    if not vals.get("product_id"):
                        continue
                    amount += (vals.get("price_unit") or 0.0) * (
                        vals.get("product_uom_qty") or 0.0
                    )
        return {
            "contract": self.name,
            "sales": len(sale_orders_vals),
            "operations": len(field_ops_vals),
            "lines": len(lines_to_update),
            "amount": amount,
        }

    def _create_recurrence_documents(self, date_ref):
        """Create the prepared documents of this contract (one savepoint)."""
        self.ensure_one()
        (
            sale_orders_vals,
            sale_order_keys,
            field_ops_vals,
            lines_to_update,
            contracts_to_update,
        ) = self._prepare_recurrence_values(self, date_ref)

        if (
            not sale_orders_vals
            and not field_ops_vals
            and not lines_to_update
            and not contracts_to_update
        ):
            return {"contract": self.name, "sales": 0, "operations": 0, "amount": 0.0}

        # A. Create the sale orders.
        sale_orders = self.env["sale.order"]
        if sale_orders_vals:
            sale_orders = self.env["sale.order"].create(sale_orders_vals)

        # Map the unique_key of each prepared order to the created record id.
        key_to_so_id = dict(zip(sale_order_keys, sale_orders.ids, strict=False))

        # B. Create the field operations, linking each to its sale order.
        operations = self.env["field.operation"]
        if field_ops_vals:
            for op_vals in field_ops_vals:
                op_vals["sale_id"] = key_to_so_id.get(op_vals.pop("so_unique_key"))
            operations = self.env["field.operation"].create(field_ops_vals)

        # C. Tracking updates (line counters, header period).
        for line, updates_list in lines_to_update.items():
            line.write(updates_list[-1])
            line.flush_recordset()

        header_updates = {}
        for updates in contracts_to_update.values():
            header_updates.update(updates)
        if header_updates:
            self.write(header_updates)

        if sale_orders or operations:
            self._notify_generated_documents(sale_orders, operations)

        return {
            "contract": self.name,
            "sales": len(sale_orders),
            "operations": len(operations),
            "amount": sum(sale_orders.mapped("amount_untaxed")),
        }

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
    def _get_effective_lead_days(self):
        """Days before the service date on which the documents are created.

        A contract-level value (anything but 0) wins over the company setting,
        so a single fussy customer/contract can be given a longer planning
        window without touching the rest of the book.
        """
        self.ensure_one()
        lead_days = self.generation_lead_days
        if not lead_days:
            lead_days = self.company_id.contract_generation_lead_days or 7
        return max(0, min(lead_days, 30))

    def _already_generated(self, period_start, location, period_end=None):
        """True when the periodic order for this period and location exists.

        Rows generated before ``contract_period_start`` existed carry the
        generation date in ``date_order`` and no period, so an order inside the
        period window counts as the same occurrence. Without this fallback the
        first run after the upgrade would create a duplicate of the period that
        was already generated.
        """
        self.ensure_one()
        domain = [
            ("service_contract_id", "=", self.id),
            ("partner_shipping_id", "=", location.id),
        ]
        if self.env["sale.order"].search_count(
            domain + [("contract_period_start", "=", period_start)]
        ):
            return True
        if not period_end:
            return False
        return bool(
            self.env["sale.order"].search_count(
                domain
                + [
                    ("contract_period_start", "=", False),
                    ("date_order", ">=", fields.Datetime.to_datetime(period_start)),
                    (
                        "date_order",
                        "<",
                        fields.Datetime.to_datetime(period_end + relativedelta(days=1)),
                    ),
                ]
            )
        )

    def _prepare_header_recurrence_values(self, process_date):
        """Prepare header-based generation values (does not write to the DB)."""
        self.ensure_one()
        due_date = self.recurring_next_date
        if not due_date:
            return [], [], {}, {}

        # Documents are created ``lead_days`` before the service date so the
        # office can plan staff and routes. The service date itself does not
        # move: only the moment the order/operation is created does.
        lead_days = self._get_effective_lead_days()
        if due_date - relativedelta(days=lead_days) > process_date:
            return [], [], {}, {}

        # Header mode is driven by the contract schedule; the line start date
        # is intentionally not used here. Otherwise a line starting after the
        # contract anchor would keep the contract on the same due date forever
        # and nothing would ever be generated for it.
        valid_lines = self.contract_line_ids.filtered(
            lambda line: not line.display_type
            and line.product_id
            and line.product_id.type == "service"
            and (not line.date_end or line.date_end >= due_date)
            and line.remaining_count > 0
        )

        if not valid_lines:
            return [], [], {}, {}

        # Advance by the period that starts at ``next_period_date_start``.
        # Using the period that contains ``process_date`` would skip every
        # missed period when the cron was late (and also the period after an
        # end-of-period occurrence).
        period_end = self.get_next_period_date_end(
            self.next_period_date_start,
            self.recurring_rule_type,
            self.recurring_interval,
            max_date_end=self.date_end,
        )
        if not period_end:
            return [], [], {}, {}

        so_vals_list = []
        op_vals_list = []
        lines_updates = {}  # {line: values to write}

        # Group the lines by delivery location.
        lines_by_location = self._group_lines_by_location(valid_lines)

        for location, loc_lines in lines_by_location.items():
            unique_key = f"{self.id}_{location.id}"

            if self._already_generated(due_date, location, period_end):
                _logger.info(
                    "Contract %s: the order for %s / %s already exists, skipped.",
                    self.name,
                    due_date,
                    location.name,
                )
                continue

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
                "contract_period_start": due_date,
                "date_order": fields.Datetime.to_datetime(due_date),
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
                    line.service_type_id.id
                    if line.service_type_id
                    else self.service_type_ids[:1].id
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
                        "start_date": fields.Datetime.to_datetime(due_date),
                        "status": "draft",
                    }
                )

                # Line values written later in the update phase.
                lines_updates[line] = {
                    "generated_occurrences": line.generated_occurrences + 1,
                }

            so_vals_list.append(so_vals)

        # Header update: only ``last_date_processed`` moves forward. It must be
        # the end of the period that starts at ``next_period_date_start``; the
        # next date is computed from it. Writing the period that contains
        # ``process_date`` would skip missed periods when the cron runs late.
        contract_updates = {
            "last_date_processed": period_end,
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
            and line.recurring_next_date
            - relativedelta(days=self._get_effective_lead_days())
            <= process_date
            and (not line.date_end or line.recurring_next_date <= line.date_end)
            and line.remaining_count > 0
            and not line._already_generated(line.recurring_next_date)
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

            due_dates = []
            for line in loc_lines:
                # Advance from the period that starts at the line's current
                # next-period start, not from the date that contains the
                # occurrence date. This keeps end-of-period and
                # monthly-last-day schedules from skipping a period.
                period_end_date = line.get_next_period_date_end(
                    line.next_period_date_start,
                    line.recurring_rule_type,
                    line.recurring_interval,
                    max_date_end=line.date_end,
                )
                if not period_end_date:
                    continue

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

                due_dates.append(line.recurring_next_date)
                op_vals_list.append(
                    {
                        "so_unique_key": unique_key,
                        "contract_id": self.id,
                        "contract_line_id": line.id,
                        "partner_id": self.partner_id.id,
                        "address_id": location.id,
                        "subject": line.product_id.name,
                        "description": line.name,
                        "service_type_id": (
                            line.service_type_id.id
                            if line.service_type_id
                            else self.service_type_ids[:1].id
                        ),
                        "start_date": fields.Datetime.to_datetime(
                            line.recurring_next_date
                        ),
                        "status": "draft",
                    }
                )

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

            # Do not create an empty order (section only) for a location where
            # every line hit its end date.
            if len(so_vals["order_line"]) > 1:
                if due_dates:
                    period_start = min(due_dates)
                    so_vals["date_order"] = fields.Datetime.to_datetime(period_start)
                    so_vals["contract_period_start"] = period_start
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
            # ``generated_sale_ids`` intentionally excludes the source
            # quotation, but a linked source order still uses the contract via
            # ``ondelete='restrict'``; check the real relation too so the user
            # gets the friendly error instead of a database error.
            linked_sales = self.env["sale.order"].search_count(
                [("service_contract_id", "=", contract.id)]
            )
            if linked_sales or contract.generated_operation_ids:
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
        # document is left pointing at a cancelled contract. Search the real
        # relation because ``generated_sale_ids`` excludes the source quotation.
        draft_sales = self.env["sale.order"].search(
            [
                ("service_contract_id", "in", self.ids),
                ("state", "in", ("draft", "sent")),
            ]
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
        domain = [
            ("service_contract_id", "=", self.id),
            ("order_types", "!=", "contract"),
        ]
        if self.sale_count == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "views": [(self.env.ref("sale.view_order_form").id, "form")],
                "view_mode": "form",
                "target": "current",
                "domain": domain,
                "context": {"default_service_contract_id": self.id},
            }
        return {
            "name": _("Sales Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": domain,
            "context": {"default_service_contract_id": self.id},
            "type": "ir.actions.act_window",
        }
