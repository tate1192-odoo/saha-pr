from odoo import api, fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    display_address = fields.Char(compute="_compute_display_address")

    @api.depends("address_id")
    def _compute_display_address(self):
        for operation in self:
            if operation.address_id:
                operation.display_address = operation.address_id._display_address(
                    without_company=True,
                )
            else:
                operation.display_address = False
