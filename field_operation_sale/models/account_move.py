# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    field_operation_count = fields.Integer(
        compute="_compute_field_operation_count", string="Service Count"
    )
    field_operation_id = fields.Many2one("field.operation", string="Service")

    @api.depends("line_ids.sale_line_ids.order_id")
    def _compute_field_operation_count(self):
        """Service count per invoice.

        The lookup used to be done once for the whole recordset and written to every
        record, so a list of invoices all showed the same (aggregated) number.
        """
        for move in self:
            sale_ids = move.line_ids.sale_line_ids.order_id.ids
            move.field_operation_count = self.env["field.operation"].search_count(
                [("sale_id", "in", sale_ids)] if sale_ids else [("id", "=", False)]
            )

    def show_field_operation(self):
        """Open the services of the sale orders this invoice comes from."""
        self.ensure_one()
        sale_ids = self.line_ids.sale_line_ids.order_id.ids
        return {
            "name": _("Field Operations"),
            "res_model": "field.operation",
            "view_mode": "list,form",
            "type": "ir.actions.act_window",
            "domain": [("sale_id", "in", sale_ids)]
            if sale_ids
            else [("id", "=", False)],
        }
