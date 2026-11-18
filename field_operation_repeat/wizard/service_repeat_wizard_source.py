"""Source driven recurrence wizard.

``service_repeat_wizard.py`` schedules recurring operations from scratch: the
customer, the subject and the recurrence rules are typed in the dialog. This
overlay makes the same wizard usable from an existing service. The source is
optional; when it is set the dialog copies the customer, address, team, price,
tags and description of that service, keeps its time of day and duration, links
the generated periods to it and can skip the dates that already have one.
"""

from datetime import datetime
from itertools import islice

import pytz
from dateutil import rrule

from odoo import _, api, fields, models

#: Number of dates shown in the preview.
PREVIEW_LIMIT = 10


class ServiceRepeatWizard(models.TransientModel):
    _inherit = "service.repeat.wizard"

    field_operation_id = fields.Many2one(
        "field.operation",
        string="Source Service",
        ondelete="set null",
        help="When set, the new operations are built from this service instead of "
        "the standalone values of the dialog.",
    )
    copy_from_source = fields.Boolean(
        string="Copy Service Data",
        default=True,
        help="Copy the customer, address, team, price, tags and description of the "
        "source service to the generated operations.",
    )
    use_source_time = fields.Boolean(
        string="Keep Time of Day",
        default=True,
        help="Start every generated operation at the time of day and with the "
        "duration of the source service. Uncheck it to start them at midnight.",
    )
    link_to_source = fields.Boolean(
        string="Link to Series",
        default=True,
        help="Make the source service the parent of the generated operations, so "
        "that rescheduling one of them reschedules the rest of the series.",
    )
    skip_existing = fields.Boolean(
        string="Skip Planned Dates",
        help="Do not create an operation on a date where the source service already "
        "has one.",
    )
    generated_status = fields.Selection(
        [("draft", "Draft"), ("planned", "Planned")],
        string="Generated Status",
        default="planned",
        required=True,
        help="Status of the generated operations.",
    )
    preview_dates = fields.Text(
        string="Preview Dates",
        compute="_compute_preview_dates",
        help="Preview of the dates that will be generated with the current settings.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _user_timezone(self):
        """Timezone the wizard works in (the browser one, the user one, UTC)."""
        return pytz.timezone(self.env.context.get("tz") or self.env.user.tz or "UTC")

    def _source_local_start(self):
        """Start of the source service in the user's timezone (``None`` if none)."""
        self.ensure_one()
        source = self.field_operation_id
        if not source or not source.start_date:
            return None
        return pytz.utc.localize(source.start_date).astimezone(self._user_timezone())

    def _existing_local_dates(self):
        """Local dates the source series already has a period on."""
        self.ensure_one()
        timezone = self._user_timezone()
        return {
            pytz.utc.localize(period.start_date).astimezone(timezone).date()
            for period in self.field_operation_id.child_ids
            if period.start_date
        }

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends(
        "dtstart",
        "rrule_freq",
        "rrule_interval",
        "rrule_end_type",
        "rrule_count",
        "rrule_until",
        "rrule_byweekday",
        "rrule_month_by",
        "rrule_bymonthday",
        "rrule_bysetpos",
        "rrule_byweekday_pos",
        "field_operation_id",
    )
    def _compute_preview_dates(self):
        for wizard in self:
            wizard.preview_dates = wizard._preview_text()

    def _preview_dates(self):
        """Dates the current settings would generate, capped by the preview limit."""
        self.ensure_one()
        if not self.dtstart:
            return []
        try:
            params = self._prepare_rrule_params()
        except (KeyError, ValueError):
            return []
        dates = list(islice(rrule.rrule(**params), PREVIEW_LIMIT + 1))
        if self.field_operation_id:
            local_start = self._source_local_start()
            if local_start:
                dates = [date for date in dates if date.date() != local_start.date()]
            if self.skip_existing:
                existing = self._existing_local_dates()
                dates = [date for date in dates if date.date() not in existing]
        return dates

    def _preview_text(self):
        self.ensure_one()
        if not self.dtstart:
            return _("Please set a start date to see the preview.")
        dates = self._preview_dates()
        if not dates:
            return _("No date would be generated with the current settings.")
        lines = [date.strftime("%Y-%m-%d %A") for date in dates[:PREVIEW_LIMIT]]
        if len(dates) > PREVIEW_LIMIT:
            lines.append(_("... and more"))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Values
    # ------------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        source_id = self.env.context.get("default_field_operation_id")
        if not source_id:
            return res
        source = self.env["field.operation"].browse(source_id).exists()
        if not source:
            return res
        local_start = (
            pytz.utc.localize(source.start_date).astimezone(self._user_timezone())
            if source.start_date
            else None
        )
        values = {
            "field_operation_id": source.id,
            "dtstart": (
                local_start.date() if local_start else fields.Date.context_today(self)
            ),
        }
        for name in ("partner_id", "user_id", "company_id", "service_type_id"):
            value = source[name].id
            if value:
                values[name] = value
        if source.subject:
            values["subject"] = source.subject
        for name, value in values.items():
            if name in fields_list:
                res[name] = value
        return res

    def _prepare_operation_values(self, operation_date):
        """Build one generated operation, or return ``False`` to skip that date.

        ``operation_date`` is a naive datetime in the user's timezone: the core
        wizard works on local calendar dates.
        """
        values = super()._prepare_operation_values(operation_date)
        values["status"] = self.generated_status
        source = self.field_operation_id
        if not source:
            return values
        local_date = operation_date.date()
        local_start = self._source_local_start()
        if local_start and local_date == local_start.date():
            # The source is not one of its own periods.
            return False
        if self.skip_existing and local_date in self._existing_local_dates():
            return False
        if self.copy_from_source:
            values.update(
                {
                    "partner_id": source.partner_id.id,
                    "address_id": source.address_id.id,
                    "team_id": source.team_id.id,
                    "user_id": source.user_id.id,
                    "service_type_id": source.service_type_id.id,
                    "subject": source.subject or values["subject"],
                    "service_price": source.service_price,
                    "currency_id": source.currency_id.id,
                    "tag_ids": [(6, 0, source.tag_ids.ids)],
                    "description": source.description,
                }
            )
        if self.use_source_time and local_start:
            start = datetime.combine(local_date, local_start.time())
            values["start_date"] = self._local_to_utc(start)
            if source.end_date:
                duration = source.end_date - source.start_date
                values["end_date"] = self._local_to_utc(start + duration)
        if self.link_to_source:
            values["parent_id"] = source.id
        return values

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def action_generate_operations(self):
        """Generate the operations, then trace the run on the source service."""
        self.ensure_one()
        FieldOperation = self.env["field.operation"]
        source = self.field_operation_id
        trace = bool(source and self.link_to_source)
        domain = [("parent_id", "=", source.id)]
        before = FieldOperation.search_count(domain) if trace else 0
        result = super().action_generate_operations()
        if trace:
            created = FieldOperation.search_count(domain) - before
            if created:
                source.message_post(
                    body=_("%s recurring operations were generated from this service.")
                    % created
                )
        return result
