# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    field_operation_ids = fields.One2many(
        "field.operation", "account_move_id", string="Services"
    )
    field_operation_invoice_count = fields.Integer(
        compute="_compute_field_operation_invoice_count",
        string="Invoice Service Count",
        store=True,
    )

    # Cancelling an invoice leaves the service linked on purpose: the paper trail stays
    # readable from the service. An action_cancel() override used to sit here, but Odoo
    # has no account.move.action_cancel, so it never ran.

    @api.depends("field_operation_ids")
    def _compute_field_operation_invoice_count(self):
        for move in self:
            move.field_operation_invoice_count = len(move.field_operation_ids)

    def unlink(self):
        """Detach the services before deleting the invoice.

        The m2o cascade nulls the column straight in SQL, which never refreshes the
        stored ``invoicing`` of the service: it would keep showing "Billed" with no
        invoice behind it. Writing the link through the ORM first avoids that.
        """
        self.field_operation_ids.account_move_id = False
        return super().unlink()

    def action_show_field_operation(self):
        """Open the service behind this invoice, or the list of them."""
        self.ensure_one()
        operations = self.field_operation_ids
        if len(operations) == 1:
            return {
                "name": operations.display_name,
                "type": "ir.actions.act_window",
                "res_model": "field.operation",
                "view_mode": "form",
                "res_id": operations.id,
                "target": "current",
            }
        if len(operations) > 1:
            return {
                "name": _("Services"),
                "type": "ir.actions.act_window",
                "res_model": "field.operation",
                "view_mode": "list,form",
                "domain": [("id", "in", operations.ids)],
                "target": "current",
            }
        return {"type": "ir.actions.act_window_close"}
