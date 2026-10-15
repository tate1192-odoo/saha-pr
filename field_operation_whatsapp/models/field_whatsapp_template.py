# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import re
from typing import ClassVar

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext


class FieldWhatsAppTemplate(models.Model):
    _name = "field.whatsapp.template"
    _description = "WhatsApp Message Templates"
    _order = "name"

    name = fields.Char(
        "Template Name", required=True, help="Descriptive name for the template"
    )
    template_content = fields.Text(
        "Message Template",
        required=True,
        help="Message content. Use {field_name} for dynamic fields",
    )
    active = fields.Boolean("Active", default=True)
    available_fields = fields.Text(
        "Available Fields",
        help="Comma separated list of available field names",
        default="name,partner_name,contact_name,operation_date,subject,description,solution,address,phone,sender_company,sender_phone,sender_user",
    )
    template_category = fields.Selection(
        [
            ("greeting", "Greeting"),
            ("confirmation", "Confirmation"),
            ("reminder", "Reminder"),
            ("update", "Status Update"),
            ("completion", "Completion"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
    )
    usage_count = fields.Integer("Usage Count", default=0)

    FIELD_MAPPING: ClassVar[dict[str, str]] = {
        "partner_name": "partner_id.name",
        "contact_name": "contact_id.name",
        "operation_date": "start_date",
        "subject": "subject",
        "description": "description",
        "solution": "solution",
        "name": "name",
        "address": "address_id.display_name",
        "phone": "partner_id.phone",
        "sender_company": "company_id.name",
        "sender_phone": "company_id.phone",
        "sender_user": "user_id.name",
    }

    @api.constrains("template_content")
    def _check_template_placeholders(self):
        """Refuse placeholders the wizard cannot fill in.

        ``replace_template_fields`` leaves an unknown ``{key}`` untouched, so the
        customer receives the raw placeholder (measured: 'A={yok} B=FO/00579').
        Saving is the last moment the author can be told about it.
        """
        known = set(self.FIELD_MAPPING)
        for record in self:
            used = set(
                re.findall(
                    r"\{([A-Za-z_][A-Za-z0-9_]*)\}", record.template_content or ""
                )
            )
            unknown = sorted(used - known)
            if unknown:
                raise ValidationError(
                    _(
                        "Unknown placeholder(s) in the template: %(unknown)s. "
                        "Available placeholders: %(known)s.",
                        unknown=", ".join(unknown),
                        known=", ".join(sorted(known)),
                    )
                )

    def replace_template_fields(self, record):
        """Replace template fields with actual values from record"""
        if not self.template_content:
            return ""

        content = self.template_content

        for field_key, field_path in self.FIELD_MAPPING.items():
            field_value = self._get_field_value(record, field_path)
            content = content.replace("{" + field_key + "}", str(field_value))

        return content

    def _get_field_value(self, record, field_path):
        """Get field value by traversing the field path"""
        if not record or not field_path:
            return ""

        value = record
        for field in field_path.split("."):
            if hasattr(value, field):
                value = getattr(value, field)
                if not value:
                    break
            else:
                value = ""
                break

        if hasattr(value, "name"):
            return value.name
        elif hasattr(value, "display_name"):
            return value.display_name
        elif isinstance(value, bool):
            return _("Yes") if value else _("No")
        elif not value:
            return ""
        else:
            html_fields = ["description", "solution"]
            if field_path in html_fields and value:
                plain_text = html2plaintext(str(value))
                plain_text = " ".join(plain_text.split())
                return plain_text
            else:
                return str(value)

    def action_view_usage(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Usage Logs"),
            "res_model": "field.whatsapp.log",
            "view_mode": "list,form",
            "domain": [("template_id", "=", self.id)],
            "context": {"default_template_id": self.id},
        }


class FieldWhatsAppLog(models.Model):
    _name = "field.whatsapp.log"
    _description = "WhatsApp Message Log"
    _order = "create_date desc"

    template_id = fields.Many2one("field.whatsapp.template", "Template Used")
    res_model = fields.Char("Related Document Model")
    res_id = fields.Integer("Related Document ID")
    res_name = fields.Char("Record Name", compute="_compute_res_name", store=True)
    contact_mobile = fields.Char("Contact Phone")
    message_sent = fields.Text("Message")
    company_id = fields.Many2one(
        "res.company",
        "Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Company of the record the message belongs to; the log is filtered "
        "on it so one company cannot read another one's messages.",
    )
    create_date = fields.Datetime("Opened On", readonly=True)

    @api.depends("res_model", "res_id")
    def _compute_res_name(self):
        for record in self:
            if record.res_model and record.res_id:
                related_record = (
                    self.env[record.res_model].browse(record.res_id).exists()
                )
                record.res_name = (
                    related_record.display_name if related_record else _("Unknown")
                )
            else:
                record.res_name = _("Unknown")
