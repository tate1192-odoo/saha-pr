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
    operation_id = fields.Many2one(
        "field.operation",
        string="Operation",
        ondelete="cascade",
        index=True,
        help="The operation this pesticide line belongs to. Legacy lines "
        "created before the operation-centric refactor may not have one.",
    )
    user_id = fields.Many2one(related="operation_id.user_id")
    customer_id = fields.Many2one(related="operation_id.partner_id")
    company_id = fields.Many2one(related="operation_id.company_id", store=True)
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain="[('type', '=', 'consu')]",
    )
    status = fields.Selection(
        related="operation_id.status",
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
            operation = (
                self.env["field.operation"].browse(vals.get("operation_id"))
                if vals.get("operation_id")
                else self.env["field.operation"]
            )
            if operation and operation.company_id:
                self = self.with_company(operation.company_id)
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "field.biocidal"
                ) or _("New")
        return super().create(vals_list)
