from odoo import _, api, fields, models


class FieldOperationPesticide(models.Model):
    _name = "field.operation.pesticide"
    _description = "Field Operation Pesticide"
    _order = "create_date desc"

    name = fields.Char(string="Name", default="/", index=True)
    subject = fields.Char(string="Subject")
    active = fields.Boolean(string="Active", default=True)
    product_qty = fields.Float(string="Quantity")
    product_uom = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        compute="compute_product_uom",
        store=True,
        precompute=True,
    )
    used_equipment = fields.Char(string="Used Equipment")
    forms_id = fields.Many2one("field.operation.forms", string="Forms")
    user_id = fields.Many2one(related="forms_id.user_id")
    customer_id = fields.Many2one(related="forms_id.customer_id")
    company_id = fields.Many2one(related="forms_id.company_id")
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain="[('type', '=', 'consu')]",
    )
    status = fields.Selection(
        related="forms_id.status",
        string="Status",
        copy=False,
        store=True,
        precompute=True,
    )

    @api.depends("product_id")
    def compute_product_uom(self):
        for repair in self:
            if repair.product_id:
                repair.product_uom = repair.product_id.uom_id
            else:
                repair.product_uom = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "company_id" in vals:
                self = self.with_company(vals["company_id"])
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "field.biocidal"
                ) or _("New")
        return super().create(vals_list)
