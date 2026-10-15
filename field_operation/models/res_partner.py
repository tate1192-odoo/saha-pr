# field_operation/models/res_partner.py

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    field_operation_ids = fields.One2many(
        "field.operation", "partner_id", string="Services"
    )
    field_operation_count = fields.Integer(
        compute="_compute_field_operation_count", string="# Services", store=True
    )

    @api.depends("field_operation_ids.partner_id")
    def _compute_field_operation_count(self):
        for partner in self:
            # The partner itself plus every child contact (recursive)
            partner.field_operation_count = self.env["field.operation"].search_count(
                [("partner_id", "child_of", partner.id)]
            )

    def _compute_application_statistics_hook(self):
        """Expose the service counter as a badge in the "Stats" cell of a contact.

        Partners without any service are left out of the JSON value, so the
        badge only shows up where the counter is not zero (same idea as the
        core hooks of sale/crm/purchase/calendar).
        """
        data_list = super()._compute_application_statistics_hook()
        for partner in self.filtered("field_operation_count"):
            data_list[partner.id].append(
                {
                    "iconClass": "fa-tasks",
                    "value": partner.field_operation_count,
                    "label": self.env._("Services"),
                    "tagClass": "o_tag_color_0",
                }
            )
        return data_list

    def action_view_field_operation(self):
        self.ensure_one()
        return {
            "name": "Services",
            "res_model": "field.operation",
            "view_mode": "list,form",
            "type": "ir.actions.act_window",
            # Must stay identical to the domain the counter uses
            "domain": [("partner_id", "child_of", self.id)],
            "context": {"default_partner_id": self.id},
        }
