# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models


class FieldOperationDisinfect(models.Model):
    _name = "field.operation.disinfect"
    _description = "Field Operation Disinfect"
    _order = "create_date desc"

    name = fields.Char(string="Reference", default="/", index=True)
    subject = fields.Char(string="Subject")

    cleaning = fields.Boolean(string="Cleaning", default=False)
    disinfection = fields.Boolean(string="Disinfection", default=False)
    tank_dimensions = fields.Char(string="Tank Dimensions")
    ozone = fields.Boolean(string="Ozone", default=False)
    filter_change = fields.Boolean(string="Filter Change", default=False)
    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")

    operation_id = fields.Many2one(
        "field.operation",
        string="Operation",
        ondelete="cascade",
        index=True,
        help="The operation this line belongs to. Legacy lines created before "
        "the operation-centric refactor may not have one; new lines always do.",
    )
    user_id = fields.Many2one(related="operation_id.user_id")
    customer_id = fields.Many2one(related="operation_id.partner_id")
    company_id = fields.Many2one(related="operation_id.company_id", store=True)
    product_id = fields.Many2one("field.disinfect.product", string="Product")

    status = fields.Selection(
        related="operation_id.status", string="Status", copy=False, store=True
    )

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
            if vals.get("name") in (None, "/", _("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "field.disinfect"
                ) or _("New")
        return super().create(vals_list)
