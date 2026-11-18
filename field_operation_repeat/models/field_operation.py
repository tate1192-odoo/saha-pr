"""Recurring series of field operations.

A series has one source operation (its ``parent_id`` is empty) and the periods
generated from it. Rescheduling any period moves the later periods of the same
series by the same number of whole days, so the plan keeps its rhythm when the
calendar is re-arranged with a drag & drop.
"""

from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape

# Context key set while the siblings of a series are written. It stops
# ``write`` from shifting the series a second time.
SERIES_SHIFT_CONTEXT = "field_operation_series_shift"
# Context key turning the leave / overbooking guard of the core module into a
# non blocking check. The conflicts are reported as a warning right after the
# series has been moved (see ``_warn_shift``).
SKIP_TEAM_CHECK_CONTEXT = "field_operation_skip_team_check"
# Operations of the past. A series shift never moves them, and moving one of
# them never shifts the rest of the series either.
FROZEN_STATUSES = ("done", "cancel")


class FieldOperation(models.Model):
    _inherit = "field.operation"

    parent_id = fields.Many2one(
        "field.operation",
        string="Source Service",
        ondelete="set null",
        help="Service this operation was generated from.",
    )
    child_ids = fields.One2many(
        "field.operation",
        "parent_id",
        string="Recurring Services",
        help="Operations generated from this service.",
    )

    def action_repeat_service(self):
        """Open the recurrence wizard on this service.

        ``type="action"`` buttons of the core button box do not carry the record
        id, so the source is handed over through the context of the dialog.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generate Recurring Operations"),
            "res_model": "service.repeat.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_field_operation_id": self.id},
        }

    def write(self, vals):
        """Keep the recurrence series aligned when a service is rescheduled.

        The calendar view reschedules an event by writing ``start_date`` and
        ``end_date`` on the record, so this override covers the calendar drag &
        drop, the list and the form views alike: every later period of the same
        series follows the moved service by the same number of days.
        """
        if "start_date" not in vals or self.env.context.get(SERIES_SHIFT_CONTEXT):
            return super().write(vals)

        series = self.filtered(
            lambda operation: operation.parent_id or operation.child_ids
        )
        if not series:
            # Plain service, not part of a plan: nothing to keep in sync.
            return super().write(vals)

        old_starts = {operation.id: operation.start_date for operation in self}
        # Moving a plan is a planning decision, not a data integrity error: the
        # leave / overbooking guard is bypassed for the move and its conflicts
        # are reported as a warning instead (see ``_warn_shift``).
        skipping = self.with_context(**{SKIP_TEAM_CHECK_CONTEXT: True})
        result = super(FieldOperation, skipping).write(vals)
        moved, untouched = self._shift_later_periods(old_starts)
        warnings = self._collect_shift_warnings(moved, untouched)
        if warnings:
            self._warn_shift(warnings)
        return result

    def _later_periods(self, reference_start):
        """Return the moveable periods of the series coming after the reference.

        ``reference_start`` is the start date the moved operation had before the
        write: strictly later periods are returned, the operation itself and
        the periods already executed are not.
        """
        self.ensure_one()
        root = self.parent_id or self
        return (root.child_ids - self).filtered(
            lambda operation: operation.start_date
            and operation.start_date > reference_start
            and operation.status not in FROZEN_STATUSES
        )

    def _apply_shift(self, days):
        """Move the periods of the recordset ``days`` later (earlier if negative)."""
        delta = timedelta(days=days)
        for operation in self:
            values = {"start_date": operation.start_date + delta}
            if operation.end_date:
                values["end_date"] = operation.end_date + delta
            operation.with_context(
                **{
                    SERIES_SHIFT_CONTEXT: True,
                    SKIP_TEAM_CHECK_CONTEXT: True,
                }
            ).write(values)
        return self

    def _shift_later_periods(self, old_starts):
        """Move the later periods of every rescheduled service of the recordset.

        :param dict old_starts: start date of every operation before the write.
        :return: ``(moved, untouched)`` recordsets, ``untouched`` holding the
                 periods left in place because their series starts on an
                 operation already done or cancelled.
        """
        moved = self.env["field.operation"]
        untouched = self.env["field.operation"]
        for operation in self:
            if operation in moved:
                # Already moved by the write of another period of the same batch.
                continue
            old_start = old_starts.get(operation.id)
            if (
                not old_start
                or not operation.start_date
                or operation.start_date == old_start
            ):
                continue
            later = operation._later_periods(old_start)
            if not later:
                continue
            if operation.status in FROZEN_STATUSES:
                # Never reschedule the future from a closed service.
                untouched |= later
                continue
            # Whole days only: every period keeps its own time slot, a move of a
            # few hours must not shift the time of the whole series. Truncating
            # towards zero keeps the sign symmetric - ``timedelta.days`` floors,
            # so a two hour move backwards used to shift a whole day.
            shift_days = int((operation.start_date - old_start).total_seconds() / 86400)
            if shift_days:
                moved |= later._apply_shift(shift_days)
        return moved, untouched

    def _collect_shift_warnings(self, moved, untouched):
        """Return the warnings of a series move.

        The list is empty when the move is clean.
        """
        warnings = []
        if untouched:
            warnings.append(
                _(
                    "%(count)s later period(s) were left untouched because the "
                    "moved service is done or cancelled.",
                )
                % {"count": len(untouched)}
            )
        candidates = (self | moved).filtered(
            lambda operation: operation.person_ids
            and operation.start_date
            and operation.end_date
            and operation.status in ("planned", "progress")
        )
        for operation in candidates:
            try:
                # Same guard as the core module, called without the skip flag so
                # that the conflicts are collected instead of blocking the move.
                operation._check_team_integrity()
            except ValidationError as error:
                warnings.append(str(error))
        return warnings

    def _warn_shift(self, warnings):
        """Report a series move that needs attention without blocking it.

        The calendar drag & drop only gets the result of ``write`` back, so no
        dialog can be opened from here: the message is pushed on the user's bus
        (web client toast) and kept on the chatter of the moved service.
        """
        message = "\n".join(warnings)
        self.env.user._bus_send(
            "simple_notification",
            {
                "type": "warning",
                "title": _("Recurring Services"),
                "message": message,
                "sticky": False,
            },
        )
        # ``message_post`` escapes plain strings: the body is built as markup.
        body = html_escape(_("The series was moved, please check the following:"))
        body += Markup("<br/>") + Markup("<br/>").join(
            html_escape(warning) for warning in warnings
        )
        self[:1].message_post(body=body)
        return self

    @api.constrains("person_ids", "start_date", "end_date", "status")
    def _check_team_integrity(self):
        """Keep the leave / overbooking guard, except while a series moves.

        Redeclaring the constraint is required: the registry collects the
        constraint methods by attribute name (``getmembers``), so overriding
        this one without the decorator would drop the core check entirely.
        Every other write keeps the blocking behaviour of the core module.
        """
        if self.env.context.get(SKIP_TEAM_CHECK_CONTEXT):
            return
        return super()._check_team_integrity()
