from odoo import api, fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    contractor_id = fields.Many2one(
        "field.operation.contractor",
        string="Contractor",
        tracking=True,
        ondelete="restrict",
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self) -> None:
        if self.partner_id and self.partner_id.service_contractor_id:
            self.contractor_id = self.partner_id.service_contractor_id
