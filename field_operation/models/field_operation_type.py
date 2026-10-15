# field_operation/models/field_operation_type.py

from odoo import fields, models


class FieldOperationType(models.Model):
    _name = "field.operation.type"
    _description = "Field Operation Type"

    name = fields.Char(string="Name", required=True)
    sequence = fields.Integer("Sequence", default=1)
    color = fields.Integer(string="Color")
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "High"),
        ],
        default="0",
        index=True,
        string="Priority",
    )
    type = fields.Selection(
        [
            ("general", "General"),
            ("other", "Other"),
        ],
        string="Service Type",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    _name_uniq = models.Constraint(
        "unique (name)",
        "Type name already exists!",
    )
