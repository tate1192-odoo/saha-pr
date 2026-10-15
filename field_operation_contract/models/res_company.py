from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    pdf_signature = fields.Binary(
        string="PDF Signature / Stamp",
        help="Signature or company stamp image rendered in the contract PDF.",
    )
