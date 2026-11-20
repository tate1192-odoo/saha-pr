# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    # pH / chlorine readings of the cleaning, taken once per operation.
    before_ph = fields.Char(string="Before PH")
    after_ph = fields.Char(string="After PH")
    before_cl = fields.Char(string="Before CL")
    after_cl = fields.Char(string="After CL")

    disinfect_ids = fields.One2many(
        "field.operation.disinfect",
        "operation_id",
        string="Disinfection Lines",
    )
