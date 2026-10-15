# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FieldOperationBulkInvoiceWizard(models.TransientModel):
    _name = "field.operation.bulk.invoice.wizard"
    _description = "Create Consolidated Invoice from Multiple Field Operations"

    operation_ids = fields.Many2many(
        "field.operation",
        "bulk_invoice_wizard_operation_rel",
        "wizard_id",
        "operation_id",
        string="Field Operations",
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
    operation_count = fields.Integer(
        compute="_compute_operation_count", string="Operations"
    )
    line_ids = fields.One2many(
        "field.operation.bulk.invoice.wizard.line", "wizard_id", string="Invoice Lines"
    )

    @api.depends("operation_ids")
    def _compute_operation_count(self):
        for wizard in self:
            wizard.operation_count = len(wizard.operation_ids)

    @api.model
    def _check_operations(self, operations):
        """Refuse a set of services that cannot end up on one invoice.

        Runs both when the wizard opens and when it is submitted: a form left open while
        somebody else invoices one of the services must not invoice it a second time.
        """
        partners = operations.mapped("partner_id")
        if len(partners) > 1:
            raise UserError(
                _("All selected operations must belong to the same customer.")
            )

        not_done = operations.filtered(lambda op: op.status != "done")
        if not_done:
            raise UserError(
                _(
                    "All operations must be completed (status: Done). "
                    "Operations %s are not done.",
                    ", ".join(not_done.mapped("name")),
                )
            )

        already_invoiced = operations.filtered("account_move_id")
        if already_invoiced:
            raise UserError(
                _(
                    "Operations %s already have an invoice.",
                    ", ".join(already_invoiced.mapped("name")),
                )
            )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if not active_ids:
            return res

        operations = self.env["field.operation"].browse(active_ids).exists()
        if not operations:
            return res

        self._check_operations(operations)

        line_commands = [
            fields.Command.create(
                {
                    "operation_id": operation.id,
                    "description": operation.subject or operation.name or "",
                    "price_unit": operation.service_price or 0.0,
                }
            )
            for operation in operations
        ]
        res.update(
            {
                "operation_ids": [fields.Command.set(operations.ids)],
                "partner_id": operations.mapped("partner_id")[:1].id,
                "company_id": operations[:1].company_id.id or self.env.company.id,
                "line_ids": line_commands,
            }
        )
        return res

    def action_create_invoice(self):
        """Create one consolidated draft invoice for the selected services."""
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("Please add at least one invoice line."))
        if not self.partner_id:
            raise UserError(_("Customer is required."))

        # The lines are the source of truth for both the invoice and the link back.
        operations = self.line_ids.operation_id
        self._check_operations(operations)

        invoice_lines = []
        for line in self.line_ids:
            line_vals = {
                "name": line.description or line.operation_id.subject or "Service",
                "quantity": 1,
                "price_unit": line.price_unit,
                "product_id": line.product_id.id,
                "field_operation_id": line.operation_id.id,
            }
            if line.product_id:
                line_vals["product_uom_id"] = line.product_id.uom_id.id
            invoice_lines.append(fields.Command.create(line_vals))

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_id.id,
                "invoice_date": self.invoice_date,
                "invoice_date_due": self.invoice_date_due,
                "company_id": self.company_id.id,
                "invoice_line_ids": invoice_lines,
            }
        )
        operations.write({"account_move_id": invoice.id})

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }


class FieldOperationBulkInvoiceWizardLine(models.TransientModel):
    _name = "field.operation.bulk.invoice.wizard.line"
    _description = "Bulk Invoice Wizard Line"

    wizard_id = fields.Many2one(
        "field.operation.bulk.invoice.wizard", ondelete="cascade", required=True
    )
    operation_id = fields.Many2one("field.operation", string="Operation", required=True)
    partner_id = fields.Many2one(related="operation_id.partner_id", string="Customer")
    product_id = fields.Many2one(
        "product.product", string="Product", domain=[("type", "=", "service")]
    )
    description = fields.Text(string="Description")
    price_unit = fields.Monetary(string="Price", currency_field="currency_id")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
