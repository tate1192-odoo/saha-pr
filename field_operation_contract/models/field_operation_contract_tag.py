from random import randint

from odoo import fields, models


class FieldOperationContractTag(models.Model):
    _name = "field.operation.contract.tag"
    _description = "Field Operation Contract Tags"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char("Tag Name", required=True)
    color = fields.Integer(string="Color Index", default=_get_default_color)

    _name_uniq = models.Constraint(
        "unique (name)",
        "Tag name already exists!",
    )
