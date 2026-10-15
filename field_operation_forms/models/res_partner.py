# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.depends("name")
    @api.depends_context("contact_display")
    def _compute_display_name(self):
        """Show the bare name in the contact pickers of the service form."""
        if self.env.context.get("contact_display") == "name_only":
            for partner in self:
                partner.display_name = partner.name or ""
        else:
            super()._compute_display_name()
