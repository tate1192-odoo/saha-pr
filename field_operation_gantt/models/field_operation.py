# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models

#: Status -> completion, as a percentage.
#:
#: ``soft_gantt`` reads the ``progress`` field as a percentage, not as a
#: fraction: 100 fills the bar. The figures are the ones the view used before
#: it was ported, so the bars look the same.
STATUS_PROGRESS = {
    "draft": 0.0,
    "planned": 25.0,
    "progress": 50.0,
    "done": 100.0,
    "cancel": 0.0,
}

#: Status -> bar colour, as an index of the palette the view type paints with
#: (``o_gantt_soft_color_<index>``, 12 entries). Indices are chosen to keep the
#: colours the view used before the port: grey, teal, amber, green, red.
STATUS_COLOR_INDEX = {
    "draft": 2,
    "planned": 9,
    "progress": 10,
    "done": 8,
    "cancel": 11,
}


class FieldOperation(models.Model):
    _inherit = "field.operation"

    # Both figures are computed and not stored: the Gantt needs them, the
    # database does not, so adding them costs no column and no migration.
    gantt_progress = fields.Float(
        string="Progress (%)",
        compute="_compute_gantt_progress",
        help="Completion drawn as a progress bar in the Gantt view.",
    )
    gantt_color = fields.Integer(
        string="Gantt Colour",
        compute="_compute_gantt_color",
        help="Colour index of the bar in the Gantt view.",
    )

    @api.depends("status")
    def _compute_gantt_progress(self):
        for operation in self:
            operation.gantt_progress = STATUS_PROGRESS.get(operation.status, 0.0)

    @api.depends("status")
    def _compute_gantt_color(self):
        for operation in self:
            operation.gantt_color = STATUS_COLOR_INDEX.get(operation.status, 0)
