# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

import base64
import binascii

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

# The portal signature widget posts the base64 payload only, without the
# "data:image/png;base64," prefix: portal's signature_form.js sends
# ``getSignatureImage().split(",")[1]``, so validating a data: URL here would
# reject every real signature.
MAX_SIGNATURE_SIZE = 2 * 1024 * 1024


class FieldOperationForms(models.Model):
    _name = "field.operation.forms"
    _description = "Field Operation Forms"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "create_date desc"

    name = fields.Char(string="Reference", default="/", index=True, copy=False)
    subject = fields.Char(string="Subject")
    description = fields.Html(string="Description")
    solution = fields.Html(string="Solution")
    active = fields.Boolean(string="Active", default=True)
    start_date = fields.Datetime(string="Start Date")
    end_date = fields.Datetime(string="End Date")
    operation_count = fields.Integer(
        compute="_compute_operation_count", string="Operations"
    )

    signed = fields.Boolean(
        string="Signed",
        compute="_compute_signed",
        help="A form counts as signed once both the customer signature and the "
        "staff signature are stored. Derived from the two signature fields, so "
        "the flag cannot drift away from the signature images.",
    )
    customer_signature = fields.Binary(
        string="Customer Signature", copy=False, attachment=True
    )
    customer_signed_by = fields.Char(string="Customer Name", copy=False)
    signed_on = fields.Datetime(string="Signed Date", copy=False)
    staff_signature = fields.Binary(
        string="Staff Signature", copy=False, attachment=True
    )
    staff_signed_by = fields.Char(string="Staff Name", copy=False)

    operation_id = fields.Many2one(
        "field.operation", string="Operation", tracking=True, copy=False
    )
    team_id = fields.Many2one(
        "field.operation.team", string="Service Team", tracking=True
    )
    team_leader_id = fields.Many2one("res.users", string="Team Leader", tracking=True)
    person_ids = fields.Many2many("hr.employee", string="Assigned Person")
    user_id = fields.Many2one(
        "res.users", string="Created By User", default=lambda self: self.env.user
    )
    customer_id = fields.Many2one("res.partner", string="Customer", check_company=True)
    contact_id = fields.Many2one("res.partner", string="Contact")
    # v19 dropped res.partner.mobile: the contact phone is the equivalent field.
    # readonly keeps it a read-through: writing it here would silently overwrite the
    # phone stored on the contact (res.partner.phone) with the field user's edit.
    contact_mobile = fields.Char(related="contact_id.phone", store=True, readonly=True)
    address_id = fields.Many2one("res.partner", string="Service Address")
    area_id = fields.Char(
        string="Area", store=True, index=True, related="address_id.city"
    )
    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    service_type_id = fields.Many2one("field.operation.type", string="Service Type")
    service_type = fields.Selection(
        related="service_type_id.type",
        store=True,
        readonly=True,
        string="Service Type Code",
    )
    status = fields.Selection(
        [
            ("new", "New"),
            ("completed", "Completed"),
            ("done", "Done"),
            ("cancel", "Cancel"),
        ],
        string="Status",
        default="new",
        tracking=True,
    )

    @api.depends("operation_id")
    def _compute_operation_count(self):
        for form in self:
            form.operation_count = 1 if form.operation_id else 0

    @api.depends("customer_signature", "staff_signature")
    def _compute_signed(self):
        """A form is signed once both signature images are stored.

        Derived instead of stamped: the flag used to be written by the portal staff
        route and by a client-side onchange only, so 6.274 of the 6.275 live forms
        carried signatures with ``signed = False``.
        """
        for form in self:
            form.signed = bool(form.customer_signature) and bool(form.staff_signature)

    def _compute_access_url(self):
        for form in self:
            form.access_url = f"/my/operation_forms_detail/{form.id}"

    def customer_signature_missing(self):
        """True while the customer signature has not been captured yet.

        The portal template reads it twice: the "Customer Sign" shortcut is offered
        only while the signature is missing, and the modal is built on the same
        condition, so a signed form cannot open an empty dialog any more.
        """
        self.ensure_one()
        return not self.customer_signature

    def staff_signature_missing(self):
        """True while the staff signature has not been captured yet."""
        self.ensure_one()
        return not self.staff_signature

    def show_operation(self):
        """Open the operation this form belongs to."""
        self.ensure_one()
        if not self.operation_id:
            return {"type": "ir.actions.act_window_close"}
        return {
            "name": self.operation_id.display_name,
            "res_model": "field.operation",
            "view_mode": "form",
            "res_id": self.operation_id.id,
            "type": "ir.actions.act_window",
        }

    @api.onchange("customer_signed_by")
    def _signed_on(self):
        """Stamp the signature with the moment it was captured.

        ``signed`` is computed, so this only maintains the timestamp.
        """
        self.signed_on = fields.Datetime.now()

    def action_signe_form(self):
        """Open the portal page where the customer signs the form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "target": "self",
            "url": self.get_portal_url(),
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # The field default is "/" and the web client sends it back inside the
            # create payload, so the sequence has to run for "/" and for a missing
            # value alike: the previous `== _("New")` test never fired from the UI and
            # left every form created there without a FOF- number.
            if vals.get("name") in (None, "", "/", _("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "field.operation.forms"
                ) or _("New")
        return super().create(vals_list)

    # ------------------------------------------------------------
    # Server-side rights
    # ------------------------------------------------------------
    def _ensure_group(self, xmlid, action):
        """Refuse an action when the user lacks the group its button is gated on.

        The buttons carry ``groups=``, which only hides them: the check has to run
        again on the server for RPC calls.
        """
        if not self.env.user.has_group(xmlid):
            raise AccessError(
                _("You are not allowed to %(action)s this form.", action=action)
            )

    def action_draft(self):
        """Send the form back to the field user."""
        self._ensure_group("field_operation_forms.forms_user", _("reopen"))
        return self.write({"status": "new"})

    def action_completed(self):
        """Mark the work as completed, waiting for the closing signature."""
        self._ensure_group("field_operation_forms.forms_user", _("complete"))
        return self.write({"status": "completed"})

    def action_done(self):
        """Close the form and push the outcome onto its operation.

        The write on the operation goes through ``sudo()``: the form groups (Field
        User, Field Manager) are unrelated to the rights on ``field.operation``, and
        this button is the manager's one. Only the listed fields are copied.
        """
        self.ensure_one()
        self._ensure_group("field_operation_forms.forms_manager", _("close"))
        if not self.operation_id:
            raise UserError(
                _("This form is not linked to an operation: link it before closing it.")
            )
        self.operation_id.sudo().write(
            {
                "end_date": self.end_date,
                "signed_on": self.signed_on,
                "signed_by": self.customer_signed_by,
                "form_signature": self.customer_signature,
                "staff_signed_by": self.staff_signed_by,
                "staff_signature": self.staff_signature,
                "solution": self.solution,
            }
        )
        self.write({"status": "done"})
        return True

    def action_cancel(self):
        """Cancel the form."""
        self._ensure_group("field_operation_forms.forms_manager", _("cancel"))
        return self.write({"status": "cancel"})

    def action_mail_send(self):
        """Open the composer prefilled with the service form template."""
        self.ensure_one()
        self._ensure_group("field_operation_forms.forms_manager", _("e-mail"))
        mail_template = self.env.ref(
            "field_operation_forms.field_operation_forms_email_template", False
        )
        if not mail_template:
            raise UserError(_("The service form e-mail template is missing."))
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
                "default_template_id": mail_template.id,
                "default_composition_mode": "comment",
            },
        }

    # ------------------------------------------------------------
    # Portal signature: called by the controllers on a sudoed record
    # ------------------------------------------------------------
    @api.model
    def _check_signature_payload(self, signature):
        """Validate the drawn signature: a base64 payload, bounded in size."""
        if not signature:
            raise UserError(_("Signature is missing."))
        if not isinstance(signature, str) or len(signature) > MAX_SIGNATURE_SIZE:
            raise UserError(_("Invalid signature data."))
        try:
            base64.b64decode(signature, validate=True)
        except (binascii.Error, ValueError) as error:
            raise UserError(_("Invalid signature data.")) from error

    def _portal_sign_customer(self, name, signature):
        """Store the customer signature: signature, signer name, timestamp."""
        self.ensure_one()
        self._check_signature_payload(signature)
        self.sudo().write(
            {
                "customer_signature": signature,
                "customer_signed_by": name or self.customer_id.name,
                "signed_on": fields.Datetime.now(),
            }
        )

    def _portal_sign_staff(self, name, signature):
        """Store the staff signature and stamp the signing moment.

        ``signed`` is a computed field, so it is not written here any more.
        """
        self.ensure_one()
        self._check_signature_payload(signature)
        self.sudo().write(
            {
                "staff_signature": signature,
                "staff_signed_by": name or self.team_id.name,
                "signed_on": fields.Datetime.now(),
            }
        )
