from odoo import fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    agreement_id = fields.Many2one(
        "field.operation.agreement",
        string="Agreement",
        index=True,
        ondelete="set null",
        tracking=True,
    )
