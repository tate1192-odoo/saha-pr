# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    account_move_id = fields.Many2one("account.move", "Invoice", tracking=True)
    invoice_count = fields.Integer(
        compute="_compute_invoice_count", string="Invoice Count"
    )
    invoicing = fields.Selection(
        [("billed", "Billed"), ("not_billed", "Not Billed")],
        compute="_compute_invoicing",
        store=True,
        readonly=False,
        tracking=True,
        string="Invoicing",
        help="Comes from the linked invoice. A value typed by hand survives until the "
        "invoice link changes, when the compute overwrites it.",
    )
    payment = fields.Selection(
        [("not_paid", "Not Paid"), ("partial", "Partially"), ("paid", "Paid")],
        string="Payment",
        tracking=True,
        help="Kept by hand: it is NOT synchronised with the invoice. The authoritative "
        "payment status is the one on the invoice itself.",
    )

    @api.depends("account_move_id")
    def _compute_invoicing(self):
        for operation in self:
            operation.invoicing = (
                "billed" if operation.account_move_id else "not_billed"
            )

    @api.depends("account_move_id")
    def _compute_invoice_count(self):
        for operation in self:
            operation.invoice_count = 1 if operation.account_move_id else 0

    def action_create_invoice(self):
        """Open the invoicing wizard for this service."""
        self.ensure_one()
        return {
            "name": _("Create Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "field.operation.to.invoice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_field_operation_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }

    def action_view_invoice(self):
        """Open the invoice linked to this service."""
        self.ensure_one()
        if not self.account_move_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.account_move_id.id,
            "target": "current",
        }
