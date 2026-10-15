# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import urllib.parse

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

MOBILE_UA = {"user_agent": "Mozilla/5.0 (Linux; Android 14)"}
DESKTOP_UA = {"user_agent": "Mozilla/5.0 (Windows NT 10.0)"}


@tagged("post_install", "-at_install")
class TestFieldWhatsappMessage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Message Customer", "phone": "0212 000 00 00"}
        )
        cls.operation = cls.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Message Probe",
                "partner_id": cls.partner.id,
                "start_date": "2026-11-04 09:00:00",
                "contact_mobile": "+90 (533) 444-55-66",
            }
        )
        cls.wizard = cls.env["field.whatsapp.message"]

    def _wizard(self, **overrides):
        values = {"res_model": "field.operation", "res_id": self.operation.id}
        values.update(overrides)
        return self.wizard.with_context(
            active_model="field.operation", active_id=self.operation.id, **MOBILE_UA
        ).create(values)

    def _logs(self):
        return self.env["field.whatsapp.log"].search(
            [("res_id", "=", self.operation.id), ("res_model", "=", "field.operation")]
        )

    # ------------------------------------------------------------------
    # Recipient phone
    # ------------------------------------------------------------------
    def test_the_default_get_prefers_the_operation_contact(self):
        wizard = self._wizard()
        self.assertEqual(wizard.contact_mobile, "+90 (533) 444-55-66")
        self.assertEqual(wizard.res_name, self.operation.display_name)
        self.assertEqual(wizard.partner_name, "Message Customer")

    def test_the_phone_falls_back_to_the_service_address_then_the_partner(self):
        operation = self.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Fallback Probe",
                "partner_id": self.partner.id,
                "start_date": "2026-11-04 09:00:00",
            }
        )
        wizard = self.wizard.with_context(
            active_model="field.operation", active_id=operation.id
        ).create({"res_model": "field.operation", "res_id": operation.id})
        self.assertEqual(
            wizard.contact_mobile, operation.address_id.phone or self.partner.phone
        )

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def test_the_message_is_opened_in_the_mobile_and_desktop_urls(self):
        mobile_url = self._wizard(message="Merhaba").action_send_whatsapp()["url"]
        self.assertTrue(
            mobile_url.startswith("https://api.whatsapp.com/send?phone=905334445566")
        )
        desktop = self.wizard.with_context(
            active_model="field.operation",
            active_id=self.operation.id,
            **DESKTOP_UA,
        ).create(
            {
                "res_model": "field.operation",
                "res_id": self.operation.id,
                "message": "Merhaba",
            }
        )
        desktop_url = desktop.action_send_whatsapp()["url"]
        self.assertTrue(
            desktop_url.startswith("https://web.whatsapp.com/send?phone=905334445566")
        )

    def test_the_log_keeps_the_cleaned_number_and_the_message(self):
        wizard = self._wizard(message="Temiz numara")
        self.assertEqual(wizard.action_send_whatsapp()["type"], "ir.actions.act_url")
        log = self._logs()
        self.assertEqual(len(log), 1)
        self.assertEqual(log.contact_mobile, "905334445566")
        self.assertEqual(log.message_sent, "Temiz numara")
        self.assertEqual(log.company_id, self.operation.company_id)
        self.assertEqual(log.template_id, self.env["field.whatsapp.template"])

    def test_the_chatter_note_says_the_window_was_opened(self):
        """Odoo cannot know the message was delivered: it only opens WhatsApp."""
        self._wizard(message="Chatter kontrolu").action_send_whatsapp()
        messages = self.env["mail.message"].search(
            [("model", "=", "field.operation"), ("res_id", "=", self.operation.id)]
        )
        self.assertTrue(
            any("WhatsApp opened" in message.body for message in messages),
            "no note says the WhatsApp window was opened: %s"
            % [message.body for message in messages],
        )

    def test_the_template_counter_is_incremented(self):
        template = self.env["field.whatsapp.template"].search(
            [("name", "=", "Welcome Message")], limit=1
        )
        before = template.usage_count
        wizard = self._wizard(message="Sablon sayaci")
        wizard.template_id = template
        wizard.action_send_whatsapp()
        self.assertEqual(template.usage_count, before + 1)

    def test_an_empty_phone_or_message_is_refused(self):
        with self.assertRaises(UserError):
            self._wizard(message="   ").action_send_whatsapp()
        wizard = self._wizard(message="telefon yok")
        wizard.contact_mobile = "   "
        with self.assertRaises(UserError):
            wizard.action_send_whatsapp()

    # ------------------------------------------------------------------
    # Service report link
    # ------------------------------------------------------------------
    def test_the_report_link_points_to_the_service_report_with_a_token(self):
        """The customer is not logged in: /web/content needs an access token.

        The report name used to be wrong ('field_operation.field_operation_pdf'
        does not exist in this suite), so the checkbox raised a UserError.
        """
        wizard = self._wizard(message="Rapor linki", include_report=True)
        url = urllib.parse.unquote(wizard.action_send_whatsapp()["url"])
        self.assertIn("/web/content/", url)
        self.assertIn("access_token=", url)

        log = self._logs()
        self.assertIn("Service Report:", log.message_sent)
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", "field.operation"), ("res_id", "=", self.operation.id)],
            limit=1,
        )
        self.assertTrue(attachment, "the report was rendered and attached")
        self.assertFalse(attachment.public, "a public attachment is readable by id")
        self.assertTrue(attachment.access_token)
        self.assertIn(attachment.access_token, url)
        self.assertGreater(len(attachment.datas), 1000)

    def test_the_report_link_is_refused_for_another_model(self):
        partner_wizard = self.wizard.with_context(
            active_model="res.partner", active_id=self.partner.id
        ).create(
            {
                "res_model": "res.partner",
                "res_id": self.partner.id,
                "contact_mobile": "905000000000",
                "message": "Rapor yok",
                "include_report": True,
            }
        )
        with self.assertRaises(UserError) as error:
            partner_wizard.action_send_whatsapp()
        self.assertIn("field.operation", str(error.exception))

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def test_the_log_is_scoped_to_the_company_of_the_record(self):
        """A record rule, so it must be asserted with a non-superuser.

        TransactionCase runs as SUPERUSER, whose env bypasses ir.rule.
        """
        other_company = self.env["res.company"].create({"name": "Other Company"})
        self._wizard(message="A sirketi").action_send_whatsapp()
        self.env["field.whatsapp.log"].create(
            {
                "res_model": "field.operation",
                "res_id": self.operation.id,
                "contact_mobile": "905000000000",
                "message_sent": "B sirketi",
                "company_id": other_company.id,
            }
        )
        reader = self.env["res.users"].create(
            {
                "name": "WA Log Reader",
                "login": "wa_log_reader",
                "company_id": self.operation.company_id.id,
                "company_ids": [
                    Command.set([self.operation.company_id.id, other_company.id])
                ],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("field_operation.service_group_user").id,
                        ]
                    )
                ],
            }
        )
        scoped = (
            self.env["field.whatsapp.log"]
            .with_user(reader)
            .with_context(allowed_company_ids=[self.operation.company_id.id])
        )
        self.assertEqual(len(scoped.search([("res_id", "=", self.operation.id)])), 1)
        self.assertNotIn(other_company, scoped.search([]).company_id)

    def test_the_log_unlink_is_manager_only(self):
        access = self.env["ir.model.access"].search(
            [("model_id.model", "=", "field.whatsapp.log")]
        )
        self.assertEqual(len(access), 2)
        by_group = {acl.group_id: acl for acl in access}
        user = by_group[self.env.ref("field_operation.service_group_user")]
        manager = by_group[self.env.ref("field_operation.service_group_manager")]
        self.assertFalse(user.perm_unlink)
        self.assertTrue(user.perm_read and user.perm_write and user.perm_create)
        self.assertTrue(manager.perm_unlink)

    def test_the_operation_button_is_not_wrapped_in_a_second_button_box(self):
        """`position='inside'` must add the button, not another button box."""
        form = self.env.ref("field_operation.view_field_operation_form")
        arch = str(
            self.env["field.operation"].get_views([(form.id, "form")])["views"]["form"][
                "arch"
            ]
        )
        self.assertEqual(arch.count('name="button_box"'), 1)
        self.assertEqual(arch.count("action_message_send"), 1)
        # the resolved arch drops `groups`, so the gate is read from the view itself
        view_arch = self.env.ref(
            "field_operation_whatsapp.whatsapp_field_operation_form_view"
        ).arch
        self.assertIn("field_operation.service_group_user", view_arch)
