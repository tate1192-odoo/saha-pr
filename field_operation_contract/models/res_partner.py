from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.depends("service_contract_ids")
    def _service_contract(self):
        for partner in self:
            partner.service_contract_count = len(partner.service_contract_ids)

    service_contract_ids = fields.One2many(
        "field.operation.contract", "partner_id", string="Service Contracts"
    )
    service_contract_count = fields.Integer(
        compute="_service_contract", string="# Service Contracts"
    )

    def show_service_contract(self):
        return {
            "name": "field_operation_contract",
            "res_model": "field.operation.contract",
            "view_mode": "list,form",
            "type": "ir.actions.act_window",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }
