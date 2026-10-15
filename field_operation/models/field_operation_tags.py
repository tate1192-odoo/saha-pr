# field_operation/models/field_operation_tags.py

from random import randint

from odoo import fields, models


class FieldOperationTags(models.Model):
    _name = "field.operation.tags"
    _description = "Service Tags"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char("Tag Name", required=True)
    color = fields.Integer(string="Color Index", default=_get_default_color)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    _name_uniq = models.Constraint(
        "unique (name)",
        "Tag name already exists!",
    )
