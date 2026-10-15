# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class FieldOperationCreateSaleWizard(models.TransientModel):
    _name = "field.operation.create.sale.wizard"
    _description = "Create Sale from Field Operation"

    operation_ids = fields.Many2many(
        "field.operation",
        "field_operation_create_sale_rel",
        "wizard_id",
        "operation_id",
        string="Field Operations",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain=[("sale_ok", "=", True)],
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["operation_ids"] = [fields.Command.set(active_ids)]
        if "product_id" in fields_list:
            product = self._default_product()
            if product:
                res["product_id"] = product.id
        return res

    @api.model
    def _default_product(self):
        """Return the product configured in the settings, if it still exists.

        The parameter is a raw ``ir.config_parameter`` value: it used to be fed to
        ``int()`` unguarded, so a deleted product (or any other junk value) made the
        wizard fail to open at all.
        """
        product_id = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("field_operation_sale.default_product_id")
        )
        if not product_id or not str(product_id).isdigit():
            return self.env["product.product"]
        return self.env["product.product"].browse(int(product_id)).exists()

    def action_create_sale(self):
        """Create one draft sale order per selected service."""
        self.ensure_one()

        if not self.env.user.has_group(
            "field_operation_sale.group_field_operation_sale_enabled"
        ):
            raise AccessError(
                _("You are not allowed to create sale orders from services.")
            )
        if not self.operation_ids:
            raise UserError(_("Please select at least one field operation."))

        without_customer = self.operation_ids.filtered(lambda op: not op.partner_id)
        if without_customer:
            raise UserError(
                _(
                    "These services have no customer, no sale order can be created: %s",
                    ", ".join(without_customer.mapped("name")),
                )
            )

        created_sales = self.env["sale.order"]
        for operation in self.operation_ids:
            sale = self.env["sale.order"].create(
                {
                    "partner_id": operation.partner_id.id,
                    "field_operation_id": operation.id,
                    "order_types": "service",
                    "note": operation.description or "",
                }
            )
            self.env["sale.order.line"].create(
                {
                    "order_id": sale.id,
                    "product_id": self.product_id.id,
                    "name": operation.subject or "",
                    "price_unit": operation.service_price or 0.0,
                    "product_uom_qty": 1.0,
                }
            )
            operation.sale_id = sale.id
            created_sales |= sale

        return {
            "name": _("Created Sales"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("id", "in", created_sales.ids)],
        }
