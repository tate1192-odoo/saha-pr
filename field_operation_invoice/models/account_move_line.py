# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    field_operation_id = fields.Many2one(
        "field.operation", string="Service", index=True
    )
