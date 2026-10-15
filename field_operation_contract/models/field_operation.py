# field_operation_contract/model/field_operation.py

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FieldOperation(models.Model):
    _inherit = "field.operation"

    contract_id = fields.Many2one(
        "field.operation.contract",
        string="Contract",
        tracking=True,
        ondelete="restrict",
    )
    service_contract_count = fields.Integer(
        compute="_compute_service_contract_count", string="Contract Count"
    )

    @api.depends("contract_id")
    def _compute_service_contract_count(self):
        """Compute the number of contracts linked to this field operation."""
        for operation in self:
            operation.service_contract_count = 1 if operation.contract_id else 0

    def action_view_contract(self):
        """View the contract linked to this field operation."""
        self.ensure_one()
        if not self.contract_id:
            raise UserError(_("This operation is not linked to any contract."))

        return {
            "name": _("Service Contract"),
            "res_model": "field.operation.contract",
            "view_mode": "form",
            "type": "ir.actions.act_window",
            "res_id": self.contract_id.id,
            "context": {"create": False, "edit": False},
        }
