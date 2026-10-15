# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    group_field_operation_sale_enabled = fields.Boolean(
        string="Enable Create Sale from Field Operation",
        implied_group="field_operation_sale.group_field_operation_sale_enabled",
        help="Enable the ability to create sales from field operations.",
    )

    field_operation_sale_default_product_id = fields.Many2one(
        "product.product",
        string="Default Product for Sale",
        config_parameter="field_operation_sale.default_product_id",
        domain=[("sale_ok", "=", True)],
        help="Default product used when creating sales from field operations.",
    )
