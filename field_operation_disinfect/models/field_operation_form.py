# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class FieldOperationForms(models.Model):
    _inherit = "field.operation.forms"

    disinfect_ids = fields.One2many(
        "field.operation.disinfect", "forms_id", string="Disinfection Lines"
    )
    # pH / chlorine readings of the cleaning, taken once per form.
    before_ph = fields.Char(string="Before PH")
    after_ph = fields.Char(string="After PH")
    before_cl = fields.Char(string="Before CL")
    after_cl = fields.Char(string="After CL")

    def action_send_disinfect_mail(self):
        """Open the composer prefilled with the disinfection form template."""
        self.ensure_one()
        if not self.env.user.has_group("field_operation_forms.forms_manager"):
            raise AccessError(_("You are not allowed to e-mail this form."))
        template = self.env.ref(
            "field_operation_disinfect.email_field_operation_form_biocidal", False
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
