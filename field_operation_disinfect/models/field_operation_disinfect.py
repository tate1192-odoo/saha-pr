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
    # The pH/CL readings live on the form (field.operation.forms), not here: the integer
    # copies this model used to carry were never filled (0 of 1326 live rows).
    tank_dimensions = fields.Char(string="Tank Dimensions")
    ozone = fields.Boolean(string="Ozone", default=False)
    filter_change = fields.Boolean(string="Filter Change", default=False)
    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")

    forms_id = fields.Many2one("field.operation.forms", string="Operation")
    user_id = fields.Many2one(related="forms_id.user_id")
    customer_id = fields.Many2one(related="forms_id.customer_id")
    company_id = fields.Many2one(related="forms_id.company_id")
    product_id = fields.Many2one("field.disinfect.product", string="Product")

    status = fields.Selection(
        related="forms_id.status", string="Status", copy=False, store=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "company_id" in vals:
                self = self.with_company(vals["company_id"])
            if vals.get("name") in (None, "/", _("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "field.disinfect"
                ) or _("New")
        return super().create(vals_list)
