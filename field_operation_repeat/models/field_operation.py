"""Recurring series of field operations.

A series has one source operation (its ``parent_id`` is empty) and the periods
generated from it. This module only records that relationship; rescheduling a
service does not move the other periods of the series.
"""

from odoo import _, fields, models


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
