from odoo import _, api, fields, models


class FieldOperationFormsPest(models.Model):
    _name = "field.operation.forms.pest"
    _description = "Field Operation Forms Pest Line"
    _order = "sequence, id"

    name = fields.Char(string="Reference", default="/", index=True)
    sequence = fields.Integer(default=10)
    forms_id = fields.Many2one(
        "field.operation.forms",
        string="Operation Form",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain="[('type', '=', 'consu')]",
    )
    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        compute="compute_product_uom",
        store=True,
        precompute=True,
    )
    product_qty = fields.Float(string="Quantity")
    used_equipment = fields.Char(string="Used Equipment")

    @api.depends("product_id")
    def compute_product_uom(self):
        for line in self:
            line.product_uom = line.product_id.uom_id if line.product_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name") in (None, "", "/", "New", "Yeni", _("New")):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("field.forms.pest") or "/"
                )
        return super().create(vals_list)
