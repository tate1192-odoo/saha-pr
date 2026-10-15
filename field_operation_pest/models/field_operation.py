from odoo import fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    pest_type_ids = fields.Many2many("field.operation.pest.type", string="Pest Type")
