from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Per-customer planning window: the periodic documents are created this
    # many days before the contractual service date.
    contract_generation_lead_days = fields.Integer(
        related="company_id.contract_generation_lead_days",
        readonly=False,
        string="Contract Generation Lead (days)",
        help="How many days before the service date the periodic sale orders "
        "and field operations are created. Set it per customer: 7 days by "
        "default, longer for customers with a slower planning cycle.",
    )
