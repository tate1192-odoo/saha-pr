from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    pdf_signature = fields.Binary(
        string="PDF Signature / Stamp",
        help="Signature or company stamp image rendered in the contract PDF.",
    )
    contract_generation_lead_days = fields.Integer(
        string="Contract Generation Lead (days)",
        default=7,
        help="Periodic sale orders and field operations are created this many "
        "days before the contractual service date, so the office has time to "
        "plan staff and routes. 7 days is the default; raise it for customers "
        "that need a longer planning window.",
    )

    @api.constrains("contract_generation_lead_days")
    def _check_contract_generation_lead_days(self):
        for company in self:
            if not 1 <= company.contract_generation_lead_days <= 30:
                raise ValidationError(
                    _(
                        "The contract generation lead must be between 1 and 30 "
                        "days (company: %(company)s).",
                        company=company.display_name,
                    )
                )
