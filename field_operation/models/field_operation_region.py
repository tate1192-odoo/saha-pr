# field_operation/models/field_operation_region.py

from odoo import fields, models


class FieldOperationRegion(models.Model):
    _name = "field.operation.region"
    _description = "Field Operation Region"

    name = fields.Char(string="Region Name", required=True)
    code = fields.Char(string="Region Code")
    manager_id = fields.Many2one(
        "res.users",
        string="Regional Manager",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
