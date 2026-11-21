from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    field_operation_form_id = fields.Many2one("field.operation.forms", "Field Biocidal")


class StockPicking(models.Model):
    _inherit = "stock.picking"

    field_operation_form_id = fields.Many2one("field.operation.forms", "Field Biocidal")
