from odoo import fields, models


class FieldOperation(models.Model):
    _inherit = "field.operation"

    pest_type_ids = fields.Many2many("field.operation.pest.type", string="Pest Type")

    # Biocidal application details.
    hygiene = fields.Boolean(string="Hygiene")
    infestation = fields.Boolean(string="Infestation")
    insulation = fields.Boolean(string="Insulation")
    storage = fields.Boolean(string="Storage")
    efk_ift = fields.Boolean(string="EFK-IFT")
    monitors = fields.Boolean(string="Monitors")
    others = fields.Boolean(string="Others")
    residence = fields.Char(string="Number of Residential Flats")
    place = fields.Char(string="Area of the Place Built")
    application_method = fields.Char(string="Application Method")
    security_precautions = fields.Html(string="Security Precautions")
    responsible_manager_id = fields.Many2one(
        "hr.employee", string="Responsible Manager"
    )
    application_place = fields.Selection(
        [
            ("house", "House"),
            ("workplace", "Workplace"),
            ("other", "Other"),
        ],
        string="Application Place",
        tracking=True,
    )

    pesticide_ids = fields.One2many(
        "field.operation.pesticide", "operation_id", string="Pesticide Product"
    )
