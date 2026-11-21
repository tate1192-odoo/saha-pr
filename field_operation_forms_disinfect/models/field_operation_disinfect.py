# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models


class FieldOperationFormsDisinfect(models.Model):
    _name = "field.operation.forms.disinfect"
    _description = "Field Operation Forms Disinfect Line"
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
    product_id = fields.Many2one("field.disinfect.product", string="Product")
    tank_dimensions = fields.Char(string="Tank Dimensions")
    cleaning = fields.Boolean(string="Cleaning", default=False)
    disinfection = fields.Boolean(string="Disinfection", default=False)
    ozone = fields.Boolean(string="Ozone", default=False)
    filter_change = fields.Boolean(string="Filter Change", default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name") in (None, "/", _("New")):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("field.forms.disinfect")
                    or "/"
                )
        return super().create(vals_list)
