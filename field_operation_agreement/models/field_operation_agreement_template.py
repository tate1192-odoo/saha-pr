# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
import re
from datetime import date, datetime

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Single source of truth for the agreement type selection inside this module.
# The agreement model keeps its own copy of this list; if the two ever diverge
# the template picker and the agreement picker will stop agreeing on the types.
AGREEMENT_TYPE = [
    ("maintenance", "Maintenance"),
    ("service", "Service"),
    ("pest_control", "Pest Control"),
    ("other", "Other"),
]

# Field paths a template variable is allowed to resolve. Restricting the lookup
# to an explicit allow-list stops a template author from walking dot-notation
# into sensitive related records (e.g. user_id.password).
ALLOWED_FIELD_PATHS = frozenset(
    {
        "name",
        "reference",
        "agreement_type",
        "status",
        "start_date",
        "end_date",
        "total_amount",
        "signed_by",
        "signed_on",
        "partner_id.name",
        "partner_id.street",
        "partner_id.street2",
        "partner_id.city",
        "partner_id.zip",
        "partner_id.phone",
        "partner_id.email",
        "partner_id.vat",
        "partner_id.website",
        "partner_id.comment",
        "contact_id.name",
        "contact_id.phone",
        "contact_id.email",
        "company_id.name",
        "company_id.street",
        "company_id.city",
        "company_id.phone",
        "company_id.email",
        "company_id.vat",
        "user_id.name",
    }
)


class FieldOperationAgreementTemplate(models.Model):
    _name = "field.operation.agreement.template"
    _description = "Field Operation Agreement Template"
    _order = "agreement_type, name"

    name = fields.Char(string="Template Name", required=True, translate=True)
    agreement_type = fields.Selection(
        selection=AGREEMENT_TYPE,
        string="Agreement Type",
        required=True,
        default="service",
    )
    description = fields.Text(
        string="Description",
        help="Internal notes about this template",
    )
    # Keep the default HTML sanitization: the markup is authored in the back
    # office and is later injected into the rendered agreement document, so
    # unsafe tags (scripts, event handlers) must be stripped when written.
    content = fields.Html(
        string="Agreement Content",
        required=True,
        translate=False,
        help=(
            "Template content. Use {{1}}, {{2}}, {{3}}... as placeholders for "
            "dynamic content."
        ),
    )

    # --- Variables ---
    variable_ids = fields.One2many(
        "field.operation.agreement.template.variable",
        "template_id",
        string="Template Variables",
        copy=True,
    )

    active = fields.Boolean(string="Active", default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        default=lambda self: self.env.company,
    )

    # ============================================================
    # Placeholder Auto-Detect
    # ============================================================

    @api.onchange("content")
    def _onchange_content(self):
        """Auto-detect {{N}} placeholders and create/remove variable records."""
        if not self.content:
            self.variable_ids = [fields.Command.clear()]
            return

        body_vars = set(re.findall(r"\{\{[1-9][0-9]*\}\}", self.content or ""))

        if not body_vars:
            self.variable_ids = [fields.Command.clear()]
            return

        existing_names = set(self.variable_ids.mapped("name"))

        # Add new variables
        new_vars = sorted(
            body_vars - existing_names,
            key=lambda x: int(x.strip("{}")),
        )
        # Remove variables no longer in template
        to_remove = self.variable_ids.filtered(lambda v: v.name not in body_vars)

        commands = []
        for var in to_remove:
            commands.append(fields.Command.delete(var.id))
        for name in new_vars:
            commands.append(
                fields.Command.create(
                    {
                        "name": name,
                        "sequence": int(name.strip("{}")),
                        "sample_value": f"[Sample {name.strip('{}')}]",
                    }
                )
            )

        if commands:
            self.variable_ids = commands

    # ============================================================
    # Render
    # ============================================================

    def _render_content(self, agreement):
        """Render template content with actual values from an agreement record.

        :param agreement: field.operation.agreement record
        :return: rendered HTML string
        """
        self.ensure_one()

        if not agreement:
            return self.content or ""

        rendered = self.content or ""

        for var in self.variable_ids:
            if var.variable_type == "field":
                # Fall back to the sample value when the bound field is empty,
                # so a placeholder never renders blank.
                value = (
                    self._get_field_value(agreement, var.field_path)
                    or var.sample_value
                    or ""
                )
            else:
                value = var.free_text_value or ""

            rendered = rendered.replace(var.name, str(value) if value else "")

        return rendered

    def _get_field_value(self, record, field_path):
        """Resolve an allow-listed dot-notation field path from a record.

        :param record: field.operation.agreement record
        :param field_path: dot-notation path, e.g. 'partner_id.name'
        :return: string value, or '' when the path is not allowed or empty
        """
        if not field_path:
            return ""

        if field_path not in ALLOWED_FIELD_PATHS:
            _logger.warning(
                "Refusing to resolve non-allow-listed field path '%s'",
                field_path,
            )
            return ""

        try:
            value = record
            for field_name in field_path.split("."):
                if not hasattr(value, field_name):
                    return ""
                value = getattr(value, field_name)
        except (AttributeError, TypeError, ValueError) as exc:
            _logger.warning("Could not resolve field path '%s': %s", field_path, exc)
            return ""

        if isinstance(value, models.Model):
            return value.display_name if value else ""
        if isinstance(value, datetime):
            return fields.Datetime.to_string(value)
        if isinstance(value, date):
            return fields.Date.to_string(value)
        if isinstance(value, (list, tuple)):
            return ", ".join(
                item.display_name if isinstance(item, models.Model) else str(item)
                for item in value
            )
        if value is False or value is None:
            return ""

        return str(value)


class FieldOperationAgreementTemplateVariable(models.Model):
    _name = "field.operation.agreement.template.variable"
    _description = "Agreement Template Variable"
    _order = "sequence, name"

    template_id = fields.Many2one(
        "field.operation.agreement.template",
        string="Template",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Placeholder",
        required=True,
        help="The placeholder name like {{1}}, {{2}}, etc.",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Ordering of the placeholder; lower values come first.",
    )

    _template_name_uniq = models.Constraint(
        "unique(template_id, name)",
        "A variable with this placeholder already exists for this template!",
    )

    # --- Value Source ---
    variable_type = fields.Selection(
        selection=[
            ("free_text", "Free Text"),
            ("field", "Model Field"),
        ],
        string="Type",
        required=True,
        default="free_text",
    )

    # For free_text type
    free_text_value = fields.Text(
        string="Text Value",
        help="Static text that replaces the placeholder",
    )

    # For field type
    field_path = fields.Char(
        string="Field Path",
        help="Dot notation path, e.g. 'partner_id.name', 'partner_id.street', "
        "'start_date'",
    )

    # Fallback used by Model Field variables only
    sample_value = fields.Char(
        string="Sample Value",
        default="[Sample]",
        help="Fallback shown when a Model Field variable resolves to an empty "
        "value, so the placeholder never renders blank. Ignored for Free "
        "Text variables.",
    )

    @api.onchange("variable_type")
    def _onchange_variable_type(self):
        """Clear values when type changes."""
        if self.variable_type == "free_text":
            self.field_path = False
        else:
            self.free_text_value = False

    @api.onchange("field_path")
    def _onchange_field_path(self):
        """Update demo value placeholder based on field path."""
        if self.field_path and self.variable_type == "field":
            self.sample_value = f"[{self.field_path}]"
