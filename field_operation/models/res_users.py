# field_operation/models/res_users.py
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    field_team_ids = fields.Many2many(
        comodel_name="field.operation.team",
        relation="field_operation_team_res_users_rel",
        column1="res_users_id",
        column2="field_operation_team_id",
    )
