# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

KNOWN_PLACEHOLDERS = "A={name} B={partner_name} C={description} D={unknown_but_refused}"


@tagged("post_install", "-at_install")
class TestFieldWhatsappTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "WhatsApp Customer", "phone": "0212 111 22 33"}
        )
        cls.operation = cls.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Template Probe",
                "partner_id": cls.partner.id,
                "start_date": "2026-11-03 08:00:00",
                "description": "<p>Kalin <b>aciklama</b>  satiri</p>",
            }
        )

    def test_the_placeholders_are_filled_from_the_record(self):
        template = self.env["field.whatsapp.template"].create(
            {
                "name": "Placeholder Check",
                "template_content": "A={name} B={partner_name} C={description}",
            }
        )
        message = template.replace_template_fields(self.operation)
        self.assertIn(f"A={self.operation.name}", message)
        self.assertIn("B=WhatsApp Customer", message)
        # HTML fields are sent as WhatsApp friendly plain text
        self.assertIn("C=Kalin *aciklama* satiri", message)
        self.assertNotIn("<b>", message)

    def test_an_unknown_placeholder_is_refused_on_save(self):
        """A placeholder Odoo cannot fill would reach the customer as '{x}'."""
        with self.assertRaises(ValidationError) as error:
            self.env["field.whatsapp.template"].create(
                {"name": "Unknown", "template_content": KNOWN_PLACEHOLDERS}
            )
        self.assertIn("unknown_but_refused", str(error.exception))

    def test_the_shipped_templates_pass_the_validation(self):
        """The data templates must not trip the new constraint."""
        templates = self.env["field.whatsapp.template"].search([])
        self.assertTrue(templates, "the sample templates are installed")
        templates._check_template_placeholders()

    def test_the_empty_record_gives_empty_values(self):
        template = self.env["field.whatsapp.template"].create(
            {"name": "Empty Check", "template_content": "A={name} B={partner_name}"}
        )
        self.assertEqual(
            template.replace_template_fields(self.env["field.operation"]), "A= B="
        )

    def test_the_form_uses_a_boolean_widget_this_version_has(self):
        """`boolean_button` does not exist in 19.0; the archive toggle was dead."""
        arch = self.env.ref(
            "field_operation_whatsapp.view_field_whatsapp_template_form"
        ).arch
        self.assertIn("boolean_toggle", arch)
        self.assertNotIn("boolean_button", arch)
