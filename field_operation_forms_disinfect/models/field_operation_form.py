# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError


class FieldOperationForms(models.Model):
    _inherit = "field.operation.forms"

    disinfect_ids = fields.One2many(
        "field.operation.disinfect", "forms_id", string="Disinfection Lines"
    )
    # The readings belong to the operation; the form shows (and edits) the
    # operation values so both documents stay in sync.
    before_ph = fields.Char(
        related="operation_id.before_ph", readonly=False, string="Before PH"
    )
    after_ph = fields.Char(
        related="operation_id.after_ph", readonly=False, string="After PH"
    )
    before_cl = fields.Char(
        related="operation_id.before_cl", readonly=False, string="Before CL"
    )
    after_cl = fields.Char(
        related="operation_id.after_cl", readonly=False, string="After CL"
    )

    def _ensure_disinfect_operation(self):
        """Return the operation of this form, creating it when the form was
        entered directly in the service-form screen."""
        self.ensure_one()
        if self.operation_id:
            return self.operation_id

        service_type = self.service_type_id or self.env["field.operation.type"].search(
            [("type", "=", "disinfect")], limit=1
        )
        operation = self.env["field.operation"].create(
            {
                "subject": self.subject,
                "description": self.description,
                "solution": self.solution,
                "service_type_id": service_type.id,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "partner_id": self.customer_id.id,
                "contact_id": self.contact_id.id,
                "address_id": self.address_id.id,
                "user_id": self.user_id.id,
                "team_id": self.team_id.id,
                "team_leader_id": self.team_leader_id.id,
                "company_id": self.company_id.id,
                "person_ids": [Command.set(self.person_ids.ids)],
            }
        )
        self.operation_id = operation
        if self.customer_signature:
            operation.write(
                {
                    "form_signature": self.customer_signature,
                    "signed_by": self.customer_signed_by,
                    "signed_on": self.signed_on,
                }
            )
        if self.staff_signature:
            operation.write(
                {
                    "staff_signature": self.staff_signature,
                    "staff_signed_by": self.staff_signed_by,
                }
            )
        return operation

    @api.model_create_multi
    def create(self, vals_list):
        forms = super().create(vals_list)
        for form in forms:
            if form.service_type == "disinfect" and not form.operation_id:
                form._ensure_disinfect_operation()
        return forms

    def write(self, vals):
        old_operations = (
            {form.id: form.operation_id.id for form in self}
            if "operation_id" in vals
            else {}
        )
        result = super().write(vals)
        if "operation_id" in vals:
            for form in self:
                if old_operations.get(form.id) != form.operation_id.id:
                    form.disinfect_ids.write({"operation_id": form.operation_id.id})
        if vals.get("service_type_id"):
            for form in self:
                if form.service_type == "disinfect" and not form.operation_id:
                    form._ensure_disinfect_operation()
        return result

    def action_send_disinfect_mail(self):
        """Open the composer prefilled with the disinfection form template."""
        self.ensure_one()
        if not self.env.user.has_group("field_operation_forms.forms_manager"):
            raise AccessError(_("You are not allowed to e-mail this form."))
        template = self.env.ref(
            "field_operation_forms_disinfect.email_field_operation_form_biocidal", False
        )
        if not template:
            raise UserError(_("The disinfection form e-mail template is missing."))
        compose_form = self.env.ref("mail.email_compose_message_wizard_form")
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(compose_form.id, "form")],
            "target": "new",
            "context": {
                "default_model": self._name,
                "default_res_ids": self.ids,
                "default_use_template": True,
                "default_template_id": template.id,
                "default_composition_mode": "comment",
            },
        }
