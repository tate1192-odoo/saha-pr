from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # 1. Group switch for the recurring service wizard
    group_field_operation_recurring = fields.Boolean(
        string="Recurring Service Planning",
        help="Enable recurring service scheduling wizard",
        implied_group="field_operation.group_field_operation_recurring",
    )

    # 2. Group switch for the digital signature
    group_field_operation_signature = fields.Boolean(
        string="Digital Signature",
        help="Enable digital signature collection in field operations",
        implied_group="field_operation.group_field_operation_signature",
    )
