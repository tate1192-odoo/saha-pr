# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import datetime, time, timedelta
from itertools import islice

import pytz
from dateutil import rrule

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

#: Upper bound on the operations one run may generate, overridable with the
#: ``max_recurring_operations`` context key.
DEFAULT_MAX_OPERATIONS = 500

FREQUENCIES = {
    "daily": rrule.DAILY,
    "weekly": rrule.WEEKLY,
    "monthly": rrule.MONTHLY,
    "yearly": rrule.YEARLY,
}

#: Weekday selection of the wizard, and its ``dateutil`` counterpart.
WEEKDAY_SELECTION = [
    ("MO", "Monday"),
    ("TU", "Tuesday"),
    ("WE", "Wednesday"),
    ("TH", "Thursday"),
    ("FR", "Friday"),
    ("SA", "Saturday"),
    ("SU", "Sunday"),
]
WEEKDAYS = {
    "MO": rrule.MO,
    "TU": rrule.TU,
    "WE": rrule.WE,
    "TH": rrule.TH,
    "FR": rrule.FR,
    "SA": rrule.SA,
    "SU": rrule.SU,
}


class ServiceContractRepeatWizard(models.TransientModel):
    """Generate the recurring operations of a contract, on demand.

    The contract carries the recurrence of its own (``field_operation_contract``
    runs it on a cron); this wizard lets somebody pre-generate a series by hand
    from the contract form, with an iCalendar ``rrule`` built from the fields
    below.
    """

    _name = "service.contract.repeat.wizard"
    _description = "Service Contract Repeat Wizard"

    contract_id = fields.Many2one(
        "field.operation.contract", string="Contract", required=True
    )
    # All of these mirror the contract, which is why they are computed instead
    # of filled by an onchange: an onchange does not run on ``create``, so an
    # RPC/test call creating the wizard with only ``contract_id`` used to die on
    # the NOT NULL columns. Stored + readonly=False keeps them editable.
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        compute="_compute_contract_defaults",
        store=True,
        readonly=False,
        precompute=True,
        help="Customer for whom the recurring services will be scheduled",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        required=True,
        compute="_compute_contract_defaults",
        store=True,
        readonly=False,
        precompute=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        compute="_compute_contract_defaults",
        store=True,
        readonly=False,
        precompute=True,
    )
    subject = fields.Char(
        string="Subject",
        required=True,
        compute="_compute_contract_defaults",
        store=True,
        readonly=False,
        precompute=True,
    )
    service_type_id = fields.Many2one(
        "field.operation.type",
        string="Service Type",
        compute="_compute_contract_defaults",
        store=True,
        readonly=False,
        precompute=True,
    )
    start_date = fields.Date(
        string="Start Date",
        required=True,
        compute="_compute_contract_defaults",
        store=True,
        readonly=False,
        precompute=True,
    )
    end_date = fields.Date(
        string="End Date",
        compute="_compute_contract_defaults",
        store=True,
        readonly=False,
        precompute=True,
    )
    rrule_freq = fields.Selection(
        [
            ("yearly", "Yearly"),
            ("monthly", "Monthly"),
            ("weekly", "Weekly"),
            ("daily", "Daily"),
        ],
        string="Frequency",
        default="monthly",
        required=True,
    )
    rrule_interval = fields.Integer(string="Interval", default=1, required=True)
    rrule_byweekday = fields.Selection(
        WEEKDAY_SELECTION,
        string="On Weekday",
    )
    rrule_month_by = fields.Selection(
        [("date", "Day of the month"), ("day", "Day of the week")],
        string="Monthly Repeat By",
        default="date",
    )
    rrule_bymonthday = fields.Integer(
        string="Day of Month",
        compute="_compute_rrule_bymonthday",
        store=True,
        readonly=False,
        precompute=True,
        help="Enter a day from 1 to 31. It follows the start date, and the "
        "recurrence uses it as soon as you edit it.",
    )
    rrule_bysetpos = fields.Selection(
        [
            ("1", "First"),
            ("2", "Second"),
            ("3", "Third"),
            ("4", "Fourth"),
            ("-1", "Last"),
        ],
        string="Which Occurrence",
    )
    rrule_byweekday_pos = fields.Selection(
        WEEKDAY_SELECTION,
        string="Weekday for Positional Repeat",
    )
    rrule_end_type = fields.Selection(
        [("count", "After a number of occurrences"), ("until", "On a specific date")],
        string="End Repetition",
        default="count",
        required=True,
    )
    rrule_count = fields.Integer(string="Number of Occurrences", default=10)

    show_rrule_count = fields.Boolean(compute="_compute_visibility_flags")
    require_rrule_count = fields.Boolean(compute="_compute_visibility_flags")
    show_end_date = fields.Boolean(compute="_compute_visibility_flags")
    require_end_date = fields.Boolean(compute="_compute_visibility_flags")
    show_weekly_options = fields.Boolean(compute="_compute_visibility_flags")
    show_monthly_options = fields.Boolean(compute="_compute_visibility_flags")
    show_monthly_day_options = fields.Boolean(compute="_compute_visibility_flags")
    show_monthly_date_options = fields.Boolean(compute="_compute_visibility_flags")
    require_monthly_date_options = fields.Boolean(compute="_compute_visibility_flags")
    require_monthly_day_options = fields.Boolean(compute="_compute_visibility_flags")

    @api.depends("contract_id")
    def _compute_contract_defaults(self):
        """Take the scheduling data from the contract, leaving it editable."""
        for wizard in self:
            contract = wizard.contract_id
            wizard.partner_id = contract.partner_id
            wizard.user_id = contract.user_id or self.env.user
            wizard.company_id = contract.company_id or self.env.company
            wizard.subject = contract.subject or _("Scheduled Service")
            wizard.service_type_id = contract.service_type_ids[:1]
            wizard.start_date = contract.date_start or fields.Date.context_today(wizard)
            wizard.end_date = contract.date_end

    @api.depends("contract_id", "start_date")
    def _compute_rrule_bymonthday(self):
        """Recur on the day of the start date, not on the day of today.

        The default used to be ``today.day``, so a monthly rule on a contract
        starting on the 1st generated its operations on the 11th (measured).
        """
        for wizard in self:
            day_of = wizard.start_date or fields.Date.context_today(wizard)
            wizard.rrule_bymonthday = day_of.day

    @api.depends("rrule_end_type", "rrule_freq", "rrule_month_by")
    def _compute_visibility_flags(self):
        for wizard in self:
            wizard.show_rrule_count = wizard.rrule_end_type == "count"
            wizard.require_rrule_count = wizard.rrule_end_type == "count"
            wizard.show_end_date = wizard.rrule_end_type == "until"
            wizard.require_end_date = wizard.rrule_end_type == "until"
            wizard.show_weekly_options = wizard.rrule_freq == "weekly"
            wizard.show_monthly_options = wizard.rrule_freq == "monthly"
            wizard.show_monthly_date_options = (
                wizard.rrule_freq == "monthly" and wizard.rrule_month_by == "date"
            )
            wizard.require_monthly_date_options = wizard.show_monthly_date_options
            wizard.show_monthly_day_options = (
                wizard.rrule_freq == "monthly" and wizard.rrule_month_by == "day"
            )
            wizard.require_monthly_day_options = wizard.show_monthly_day_options

    @api.constrains("rrule_interval")
    def _check_interval(self):
        for record in self:
            if record.rrule_interval <= 0:
                raise ValidationError(_("Interval must be a positive number."))

    @api.constrains("rrule_bymonthday", "rrule_freq", "rrule_month_by")
    def _check_bymonthday(self):
        for record in self:
            if (
                record.rrule_freq == "monthly"
                and record.rrule_month_by == "date"
                and not 1 <= record.rrule_bymonthday <= 31
            ):
                raise ValidationError(
                    _(
                        "For monthly repetition by date, 'Day of Month' must "
                        "be between 1 and 31."
                    )
                )

    @api.constrains("rrule_count", "rrule_end_type")
    def _check_rrule_count(self):
        for record in self:
            if record.rrule_end_type == "count" and record.rrule_count <= 0:
                raise ValidationError(
                    _(
                        "Number of occurrences must be positive if 'End "
                        "Repetition' is by count."
                    )
                )

    @api.constrains("start_date", "end_date", "rrule_end_type")
    def _check_end_date(self):
        for record in self:
            if record.rrule_end_type != "until":
                continue
            if not record.end_date:
                raise ValidationError(
                    _("End Date is required if 'End Repetition' is by date.")
                )
            if record.start_date and record.end_date < record.start_date:
                raise ValidationError(
                    _("End Date cannot be earlier than the Start Date.")
                )

    def _local_to_utc(self, local_dt):
        """Convert a naive datetime in the user timezone to naive UTC.

        Stored ``Datetime`` values are naive UTC: writing the ``rrule`` result
        as it comes put every generated operation at 00:00 UTC whatever the
        user timezone is (03:00 on screen in Turkey, and the previous day for
        negative offsets).
        """
        tz_name = self.env.context.get("tz") or self.env.user.tz or "UTC"
        local = pytz.timezone(tz_name).localize(local_dt, is_dst=False)
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _prepare_rrule_params(self):
        """Build the ``dateutil.rrule`` keyword arguments of this wizard."""
        self.ensure_one()
        params = {"freq": FREQUENCIES[self.rrule_freq]}
        start_datetime = datetime.combine(self.start_date, time.min)
        params["dtstart"] = start_datetime

        if self.rrule_interval > 0:
            params["interval"] = self.rrule_interval

        if self.rrule_end_type == "count" and self.rrule_count > 0:
            params["count"] = self.rrule_count
        elif self.rrule_end_type == "until" and self.end_date:
            # inclusive: a recurrence that ends "on" a date includes that date
            params["until"] = datetime.combine(self.end_date, time.max)

        if self.rrule_freq == "weekly" and self.rrule_byweekday:
            params["byweekday"] = [WEEKDAYS[self.rrule_byweekday]]

        if self.rrule_freq == "monthly":
            if self.rrule_month_by == "date":
                params["bymonthday"] = self.rrule_bymonthday or start_datetime.day
            elif self.rrule_bysetpos and self.rrule_byweekday_pos:
                weekday = WEEKDAYS[self.rrule_byweekday_pos]
                params["byweekday"] = weekday(int(self.rrule_bysetpos))
        return params

    def _prepare_operation_values(self, operation_date):
        """Build the values of one ``field.operation`` for ``operation_date``."""
        self.ensure_one()
        service_type = self.service_type_id or self.contract_id.service_type_ids[:1]
        return {
            # the sequence of field.operation assigns the real reference
            "name": "/",
            "subject": self.subject,
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "user_id": self.user_id.id,
            "service_type_id": service_type.id,
            "contract_id": self.contract_id.id,
            "start_date": self._local_to_utc(operation_date),
            "end_date": self._local_to_utc(operation_date + timedelta(days=1)),
            "status": "draft",
        }

    def _existing_start_dates(self, values):
        """Return the start dates of this contract that are already planned."""
        self.ensure_one()
        operations = self.env["field.operation"].search(
            [
                ("contract_id", "=", self.contract_id.id),
                ("start_date", "in", [vals["start_date"] for vals in values]),
            ]
        )
        return set(operations.mapped("start_date"))

    def _notification(
        self, title, message, notification_type="warning", next_action=None
    ):
        """Build the client action that shows ``message`` in a notification."""
        params = {
            "title": title,
            "message": message,
            "sticky": False,
            "type": notification_type,
        }
        if next_action:
            # display_notification opens `next` once the notification is shown
            params["next"] = next_action
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }

    def action_generate_operations(self):
        """Create one field operation per date of the recurrence rule."""
        self.ensure_one()
        FieldOperation = self.env["field.operation"]
        max_operations = int(
            self.env.context.get("max_recurring_operations", DEFAULT_MAX_OPERATIONS)
        )

        try:
            rule = rrule.rrule(**self._prepare_rrule_params())
            # islice, so the cap holds while the dates are produced: `count` is a
            # free integer on the wizard, and materialising all of a large one
            # exhausted the worker before any check could run (measured: 100000
            # dates built in 0.14s and only then rejected).
            generated_dates = list(islice(rule, max_operations + 1))

            if not generated_dates:
                raise UserError(
                    _(
                        "No dates could be generated with the given recurrence "
                        "rules. Please check your settings."
                    )
                )

            if len(generated_dates) > max_operations:
                raise UserError(
                    _(
                        "The current settings would generate more than %(max)s "
                        "operations. Please adjust the recurrence rules or end "
                        "condition."
                    )
                    % {"max": max_operations}
                )

            values = [
                self._prepare_operation_values(operation_date)
                for operation_date in generated_dates
            ]
            already_planned = self._existing_start_dates(values)
            duplicates = [
                vals for vals in values if vals["start_date"] in already_planned
            ]
            to_create = [
                vals for vals in values if vals["start_date"] not in already_planned
            ]
            created_ops = (
                FieldOperation.create(to_create) if to_create else FieldOperation
            )
        except (UserError, ValidationError):
            raise
        except Exception as error:
            # surfaced to the user as a message, with the original error attached
            raise UserError(
                _(
                    "An unexpected error occurred while generating recurring "
                    "operations: %s"
                )
                % error
            ) from error

        skipped = len(duplicates)
        self._log_generation(len(created_ops), skipped)

        if not created_ops:
            if skipped:
                message = _(
                    "%(skipped)s operations already exist for this contract: "
                    "nothing was generated."
                ) % {"skipped": skipped}
            else:
                message = _(
                    "No operations were generated based on the given recurrence rules."
                )
            return self._notification(_("No Operations Generated"), message)

        action = self.env["ir.actions.actions"]._for_xml_id(
            "field_operation.action_field_operation"
        )
        action["domain"] = [("id", "in", created_ops.ids)]
        action["display_name"] = _("Generated Operations (%s)") % len(created_ops)
        if skipped:
            return self._notification(
                _("Operations Generated"),
                _(
                    "%(created)s operations were generated, %(skipped)s were skipped "
                    "because they already exist for this contract."
                )
                % {"created": len(created_ops), "skipped": skipped},
                next_action=action,
            )
        return action

    def _log_generation(self, created, skipped):
        """Leave an audit trail on the contract."""
        self.ensure_one()
        if created:
            body = _("%(created)s recurring operations were generated.") % {
                "created": created
            }
        else:
            body = _("No new recurring operation was generated.")
        parts = [body]
        if skipped:
            parts.append(
                _("%(skipped)s dates were skipped: an operation already exists.")
                % {"skipped": skipped}
            )
        self.contract_id.message_post(body=" ".join(parts))
