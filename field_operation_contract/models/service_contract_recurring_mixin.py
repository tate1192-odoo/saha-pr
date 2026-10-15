# --- service_contract_recurring_mixin.py ---
import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

#: Hard stop for _get_period_end_date: a broken (zero) recurring delta would
#: otherwise turn the period walk into an infinite loop.
MAX_PERIOD_ITERATIONS = 100000


class ServiceContractRecurringMixin(models.AbstractModel):
    """Abstract model for recurring service/operation generation logic"""

    _name = "service.contract.recurring.mixin"
    _description = "Service Contract Recurring Mixin"

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
        string="Recurrence",
        help="Specify interval for automatic service/order generation.",
    )
    recurring_interval = fields.Integer(
        default=1,
        string="Repeat Every",
        help="Repeat every (Days/Week/Month/Year)",
    )
    recurring_generation_type = fields.Selection(
        [("beginning", "At Beginning of Period"), ("end", "At End of Period")],
        default="beginning",
        string="Generation Type",
    )
    recurring_offset = fields.Integer(
        compute="_compute_recurring_offset",
        store=True,
        readonly=False,
        string="Date Offset",
    )
    last_date_processed = fields.Date(
        string="Last Processed Date",
        copy=False,
    )
    recurring_next_date = fields.Date(
        string="Date of Next Service",
        compute="_compute_recurring_next_date",
        store=True,
        readonly=False,
        copy=False,
    )
    next_period_date_start = fields.Date(
        string="Next Period Start",
        compute="_compute_next_period_date_start",
        readonly=False,
        store=True,
    )
    remaining_count = fields.Integer(default=0)
    next_period_date_end = fields.Date(
        string="Next Period End",
        compute="_compute_next_period_date_end",
        readonly=False,
        store=True,
    )

    @api.constrains("recurring_interval")
    def _check_recurring_interval(self):
        for rec in self:
            if rec.recurring_interval < 1:
                raise ValidationError(
                    _("The recurring interval must be greater than or equal to 1.")
                )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS (OCA Contract Logic)
    # -------------------------------------------------------------------------
    @api.depends("last_date_processed", "date_start", "date_end")
    def _compute_next_period_date_start(self):
        """OCA Logic: next period starts the day after last processed date"""
        for rec in self:
            if rec.last_date_processed:
                next_period_date_start = rec.last_date_processed + relativedelta(days=1)
            else:
                next_period_date_start = rec.date_start

            if (
                rec.date_end
                and next_period_date_start
                and next_period_date_start > rec.date_end
            ):
                next_period_date_start = False
            rec.next_period_date_start = next_period_date_start

    @api.depends(
        "next_period_date_start",
        "recurring_generation_type",
        "recurring_offset",
        "recurring_rule_type",
        "recurring_interval",
        "date_end",
        "recurring_next_date",
    )
    def _compute_next_period_date_end(self):
        for rec in self:
            rec.next_period_date_end = self.get_next_period_date_end(
                rec.next_period_date_start,
                rec.recurring_rule_type,
                rec.recurring_interval,
                max_date_end=rec.date_end,
                next_process_date=rec.recurring_next_date,
                recurring_generation_type=rec.recurring_generation_type,
                recurring_offset=rec.recurring_offset,
            )

    @api.depends("recurring_generation_type", "recurring_rule_type")
    def _compute_recurring_offset(self):
        for rec in self:
            rec.recurring_offset = self._get_default_recurring_offset(
                rec.recurring_generation_type, rec.recurring_rule_type
            )

    @api.depends(
        "next_period_date_start",
        "recurring_generation_type",
        "recurring_offset",
        "recurring_rule_type",
        "recurring_interval",
        "date_end",
        "remaining_count",
    )
    def _compute_recurring_next_date(self):
        """Calculate next recurring date based on OCA contract logic"""
        for rec in self:
            # Skip if no remaining services.
            if rec.remaining_count <= 0:
                rec.recurring_next_date = False
                continue

            rec.recurring_next_date = self.get_next_recurring_date(
                rec.next_period_date_start,
                rec.recurring_generation_type,
                rec.recurring_offset,
                rec.recurring_rule_type,
                rec.recurring_interval,
                max_date_end=rec.date_end,
            )

    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    @api.model
    def get_relative_delta(self, recurring_rule_type, interval):
        """Return relativedelta for one period"""
        if recurring_rule_type == "daily":
            return relativedelta(days=interval)
        elif recurring_rule_type == "weekly":
            return relativedelta(weeks=interval)
        elif recurring_rule_type == "monthly":
            return relativedelta(months=interval)
        elif recurring_rule_type == "monthlylastday":
            # Use day=31, will be adjusted automatically
            return relativedelta(months=interval, day=31)
        elif recurring_rule_type == "quarterly":
            return relativedelta(months=3 * interval)
        elif recurring_rule_type == "semesterly":
            return relativedelta(months=6 * interval)
        else:  # yearly
            return relativedelta(years=interval)

    @api.model
    def get_next_period_date_end(
        self,
        next_period_date_start,
        recurring_rule_type,
        recurring_interval,
        max_date_end,
        next_process_date=False,
        recurring_generation_type=False,
        recurring_offset=False,
    ):
        """Calculate end date of next period (OCA logic)"""
        if not next_period_date_start or (
            max_date_end and next_period_date_start > max_date_end
        ):
            return False

        if not next_process_date:
            # Regular case: start date + interval - 1 day
            next_period_date_end = (
                next_period_date_start
                + self.get_relative_delta(recurring_rule_type, recurring_interval)
                - relativedelta(days=1)
            )
        else:
            # Forced processing date
            if recurring_generation_type == "beginning":
                next_period_date_end = (
                    next_process_date
                    - relativedelta(days=recurring_offset)
                    + self.get_relative_delta(recurring_rule_type, recurring_interval)
                    - relativedelta(days=1)
                )
            else:
                next_period_date_end = next_process_date - relativedelta(
                    days=recurring_offset
                )

        if max_date_end and next_period_date_end > max_date_end:
            next_period_date_end = max_date_end
        return next_period_date_end

    @api.model
    def get_next_recurring_date(
        self,
        next_period_date_start,
        recurring_generation_type,
        recurring_offset,
        recurring_rule_type,
        recurring_interval,
        max_date_end,
    ):
        """Calculate next recurring date (OCA logic)"""
        next_period_date_end = self.get_next_period_date_end(
            next_period_date_start,
            recurring_rule_type,
            recurring_interval,
            max_date_end=max_date_end,
        )
        if not next_period_date_end:
            return False

        if recurring_generation_type == "beginning":
            recurring_date = next_period_date_start + relativedelta(
                days=recurring_offset
            )
        else:
            recurring_date = next_period_date_end + relativedelta(days=recurring_offset)

        # Handle monthlylastday special case
        if recurring_rule_type == "monthlylastday" and recurring_date:
            next_month = recurring_date + relativedelta(months=1)
            first_day_next_month = next_month.replace(day=1)
            recurring_date = first_day_next_month - relativedelta(days=1)

        return recurring_date

    @api.model
    def _get_default_recurring_offset(
        self, recurring_generation_type, recurring_rule_type
    ):
        """Default offset in days"""
        if (
            recurring_generation_type == "beginning"
            or recurring_rule_type == "monthlylastday"
        ):
            return 0
        return 1

    # -------------------------------------------------------------------------
    # PERIOD CALCULATION METHODS
    # -------------------------------------------------------------------------
    def _get_period_end_date(self, process_date):
        """Return the end date of the period containing ``process_date``.

        Walks the periods from ``date_start`` following the OCA logic. A
        zero/invalid delta or an excessive number of iterations returns
        ``process_date`` unchanged, so a broken configuration cannot hang the
        recurring cron.
        """
        self.ensure_one()

        if not self.date_start or not process_date:
            return process_date

        delta = self.get_relative_delta(
            self.recurring_rule_type, self.recurring_interval
        )
        if self.recurring_interval < 1 or not delta:
            _logger.warning(
                "Invalid recurring delta for %s (rule=%s, interval=%s); "
                "returning the process date.",
                self,
                self.recurring_rule_type,
                self.recurring_interval,
            )
            return process_date

        # Start from date_start and find the period that contains process_date.
        current_start = self.date_start
        iteration = 0
        while current_start <= process_date:
            period_end = current_start + delta - relativedelta(days=1)
            if current_start <= process_date <= period_end:
                return period_end
            current_start += delta
            iteration += 1
            if iteration >= MAX_PERIOD_ITERATIONS:
                _logger.warning(
                    "Could not resolve the period end for %s around %s; "
                    "returning the process date.",
                    self,
                    process_date,
                )
                return process_date

        # Not found (should not happen): fall back to the process date.
        return process_date
