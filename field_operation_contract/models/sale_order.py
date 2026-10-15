# field_operation_contract/sale_order.py
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ondelete='restrict' blocks deleting a contract while a sale order still
    # references it, so the relation can never be silently orphaned.
    service_contract_id = fields.Many2one(
        "field.operation.contract",
        string="Related Contract",
        copy=False,
        ondelete="restrict",
    )
    service_contract_count = fields.Integer(
        compute="_compute_service_contract_count", string="Contract Count"
    )
    order_types = fields.Selection(
        selection_add=[("contract", "Contract"), ("invoice", "Invoice")]
    )

    @api.depends("service_contract_id")
    def _compute_service_contract_count(self):
        for order in self:
            order.service_contract_count = 1 if order.service_contract_id else 0

    def show_service_contract(self):
        """Smart button: open the service contract linked to this sale order."""
        self.ensure_one()
        if not self.service_contract_id:
            raise UserError(_("No contract is linked to this sale order."))
        return {
            "name": _("Service Contract"),
            "res_model": "field.operation.contract",
            "view_mode": "form",
            "type": "ir.actions.act_window",
            "res_id": self.service_contract_id.id,
            "context": {"create": False, "edit": False},
        }
