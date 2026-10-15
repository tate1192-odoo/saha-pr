from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    service_contractor_id = fields.Many2one(
        "field.operation.contractor",
        string="Contractor",
    )
    contractor_job_ids = fields.One2many(
        "field.operation.contractor",
        "partner_id",
        string="Contractor Jobs",
    )
    service_contractor_count = fields.Integer(
        compute="_compute_service_contractor_count",
        string="# Service Contractors",
    )

    is_contractor = fields.Boolean(string="Is a Contractor", default=False)

    @api.depends("contractor_job_ids")
    def _compute_service_contractor_count(self) -> None:
        # One grouped query for the whole recordset instead of one
        # search_count per partner, which would fire an N+1 query on list views.
        groups = self.env["field.operation.contractor"]._read_group(
            [("partner_id", "in", self.ids)],
            ["partner_id"],
            ["__count"],
        )
        counts = {partner.id: count for partner, count in groups}
        for partner in self:
            partner.service_contractor_count = counts.get(partner.id, 0)

    def show_service_contractor(self) -> dict:
        self.ensure_one()
        return {
            "name": "Service Contractors",
            "res_model": "field.operation.contractor",
            "view_mode": "list,form",
            "type": "ir.actions.act_window",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }
