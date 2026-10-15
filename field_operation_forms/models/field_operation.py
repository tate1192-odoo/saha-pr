# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# Groups allowed to turn an operation into a service form.
FORM_CREATE_GROUPS = (
    "field_operation_forms.forms_user",
    "field_operation.service_group_user",
    "field_operation.service_group_all",
)


class FieldOperation(models.Model):
    _inherit = "field.operation"

    form_ids = fields.One2many("field.operation.forms", "operation_id", string="Forms")
    forms_id = fields.Many2one(
        "field.operation.forms",
        string="Form",
        compute="_compute_forms_id",
        store=True,
        readonly=True,
        copy=False,
        help="Form linked to this operation. Derived from the form side "
        "(field.operation.forms.operation_id), so the two links cannot drift apart.",
    )
    forms_count = fields.Integer(compute="_compute_forms_count")

    @api.depends("form_ids")
    def _compute_forms_id(self):
        # Legacy operations can carry several forms (the old button created one per
        # click): the highest id, i.e. the latest one, is the reference.
        for operation in self:
            operation.forms_id = operation.form_ids.sorted("id", reverse=True)[:1]

    @api.depends("form_ids")
    def _compute_forms_count(self):
        for operation in self:
            operation.forms_count = len(operation.form_ids)

    def show_forms(self):
        """Open the form of this operation, or the list of them."""
        self.ensure_one()
        if not self.form_ids:
            return {"type": "ir.actions.act_window_close"}
        if len(self.form_ids) == 1:
            return {
                "name": self.form_ids.display_name,
                "res_model": "field.operation.forms",
                "view_mode": "form",
                "res_id": self.form_ids.id,
                "type": "ir.actions.act_window",
            }
        return {
            "name": _("Forms"),
            "res_model": "field.operation.forms",
            "view_mode": "list,form",
            "domain": [("id", "in", self.form_ids.ids)],
            "type": "ir.actions.act_window",
        }

    def action_create_forms(self):
        """Create the service form of this operation.

        Refuses a second form: clicking the button repeatedly used to create one form
        per click, leaving the link on the newest while the older ones stayed behind
        (24 operations and 61 orphan forms in the live data). The creation runs as
        sudo because the create right on the forms model belongs to the Field Manager
        group, while the operation flow is driven by the groups checked below.
        """
        self.ensure_one()
        if not self.team_id:
            raise UserError(_("Please select a service team."))
        if self.forms_id:
            raise UserError(_("This operation already has a form."))
        if not any(self.env.user.has_group(xmlid) for xmlid in FORM_CREATE_GROUPS):
            raise AccessError(_("You are not allowed to create service forms."))
        return (
            self.env["field.operation.forms"]
            .sudo()
            .create(
                {
                    "subject": self.subject,
                    "description": self.description,
                    "service_type_id": self.service_type_id.id,
                    "start_date": self.start_date,
                    "customer_id": self.partner_id.id,
                    "contact_id": self.contact_id.id,
                    "address_id": self.address_id.id,
                    "user_id": self.user_id.id,
                    "team_id": self.team_id.id,
                    "team_leader_id": self.team_leader_id.id,
                    "company_id": self.company_id.id,
                    "operation_id": self.id,
                    "person_ids": [fields.Command.set(self.person_ids.ids)],
                }
            )
        )
