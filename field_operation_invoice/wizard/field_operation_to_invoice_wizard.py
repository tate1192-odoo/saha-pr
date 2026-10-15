# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FieldOperationToInvoiceWizard(models.TransientModel):
    _name = "field.operation.to.invoice.wizard"
    _description = "Create Invoice from Field Operation"

    field_operation_id = fields.Many2one(
        "field.operation", required=True, readonly=True
    )
    partner_id = fields.Many2one("res.partner", string="Customer", readonly=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency", related="company_id.currency_id"
    )
    invoice_date = fields.Date(
        default=lambda self: fields.Date.context_today(self), required=True
    )
    invoice_date_due = fields.Date(string="Due Date")
    service_price = fields.Monetary(
        string="Service Price", currency_field="currency_id"
    )
    product_id = fields.Many2one(
        "product.product", string="Product", domain=[("type", "=", "service")]
    )
    description = fields.Text(string="Description")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        operation_id = self.env.context.get(
            "default_field_operation_id"
        ) or self.env.context.get("active_id")
        if not operation_id:
            return res

        operation = self.env["field.operation"].browse(operation_id)
        if not operation.exists():
            return res

        res.update(
            {
                "field_operation_id": operation.id,
                "partner_id": operation.partner_id.id,
                "company_id": operation.company_id.id,
                "service_price": operation.service_price
                if operation.service_price > 0
                else 0.0,
                "description": operation.subject or "",
            }
        )
        return res

    @api.onchange("product_id")
    def _onchange_product_id(self):
        """Backfill the description, and the price when the service has none."""
        if not self.product_id:
            return
        if not self.description:
            self.description = self.product_id.name
        if self.service_price == 0 and self.product_id.list_price:
            self.service_price = self.product_id.list_price

    def action_create_invoice(self):
        """Create the draft invoice and link it back to the service."""
        self.ensure_one()

        if self.field_operation_id.account_move_id:
            raise UserError(_("This operation already has an invoice."))
        if self.service_price <= 0:
            raise UserError(_("Service price must be greater than zero."))
        if not self.partner_id:
            raise UserError(_("Customer is required."))

        invoice_line_vals = {
            "name": self.description or self.field_operation_id.subject or "Service",
            "quantity": 1,
            "price_unit": self.service_price,
            "product_id": self.product_id.id,
            "field_operation_id": self.field_operation_id.id,
        }
        if self.product_id:
            invoice_line_vals["product_uom_id"] = self.product_id.uom_id.id

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_id.id,
                "invoice_date": self.invoice_date,
                "invoice_date_due": self.invoice_date_due,
                "company_id": self.company_id.id,
                "invoice_line_ids": [fields.Command.create(invoice_line_vals)],
            }
        )
        self.field_operation_id.account_move_id = invoice.id

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }
