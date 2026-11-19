# field_operation/models/res_partner.py

from collections import defaultdict

from odoo import _, api, fields, models


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
        """Count the services of the partner and of its child contacts.

        The counter is recursive (child_of), so grouping the operations by
        partner_id is not enough: one _read_group collects the direct counts
        and the ancestors are then credited along the parent chain, instead of
        one search_count per partner.
        """
        for partner in self:
            partner.field_operation_count = 0
        partners = self.filtered("id")
        if not partners:
            return

        counts = defaultdict(int)
        groups = self.env["field.operation"]._read_group(
            domain=[("partner_id", "child_of", partners.ids)],
            groupby=["partner_id"],
            aggregates=["__count"],
        )
        for operation_partner, count in groups:
            node, seen = operation_partner, set()
            while node and node.id not in seen:
                seen.add(node.id)
                counts[node.id] += count
                node = node.parent_id

        for partner in partners:
            partner.field_operation_count = counts.get(partner.id, 0)

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
            "name": _("Services"),
            "res_model": "field.operation",
            "view_mode": "list,form",
            "type": "ir.actions.act_window",
            # Must stay identical to the domain the counter uses
            "domain": [("partner_id", "child_of", self.id)],
            "context": {"default_partner_id": self.id},
        }
