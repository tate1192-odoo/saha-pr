# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldOperationFormsWhatsappButton(TransactionCase):
    """The WhatsApp shortcut this module adds to the service form model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Forms = cls.env["field.operation.forms"]
        cls.view = cls.env.ref("field_operation_forms.field_operation_forms_form_view")
        cls.button_view = cls.env.ref(
            "field_operation_whatsapp.view_field_operation_forms_whatsapp_form"
        )
        cls.form = cls.Forms.create(cls._form_vals())

    @classmethod
    def _form_vals(cls, **overrides):
        """Vals for a form record, plus the picking type when the suite adds it.

        ``picking_type_id`` is required by ``field_operation_pest`` when that
        module is installed, and the same test suite runs in databases where it
        (and ``stock``) is not.
        """
        vals = dict(overrides)
        if "picking_type_id" in cls.Forms._fields:
            vals["picking_type_id"] = (
                cls.env["stock.picking.type"].search([], limit=1).id
            )
        return vals

    def _arch(self, user=None):
        """The form arch as the given user receives it (groups are resolved)."""
        views = self.Forms.with_user(user or self.env.user).get_views(
            [(self.view.id, "form")]
        )
        return views["views"]["form"]["arch"]

    def _user(self, *group_xmlids):
        return self.env["res.users"].create(
            {
                "name": "WhatsApp Button Test",
                "login": f"whatsapp_button_{'_'.join(group_xmlids)}@example.com",
                "group_ids": [
                    (6, 0, [self.env.ref(xmlid).id for xmlid in group_xmlids])
                ],
            }
        )

    def test_the_stored_view_carries_the_group(self):
        """The raw arch is gated, so the button never reaches other users."""
        arch = self.button_view.arch_db
        self.assertIn('groups="field_operation.service_group_user"', arch)

    def test_the_button_is_hidden_from_a_user_without_the_group(self):
        """A forms user without the WhatsApp group must not receive the button.

        The button used to be ungated, so it was rendered for them and clicking
        it raised an access error on the wizard.
        """
        self.assertNotIn(
            "action_message_send",
            self._arch(self._user("field_operation_forms.forms_user")),
        )

    def test_the_button_is_visible_for_a_user_with_the_group(self):
        """A user in the WhatsApp group receives the button."""
        user = self._user(
            "field_operation.service_group_user", "field_operation_forms.forms_user"
        )
        self.assertIn("action_message_send", self._arch(user))

    def test_the_group_on_the_button_may_create_the_wizard(self):
        """The gating group must actually grant the wizard's create access."""
        button = etree.fromstring(self.button_view.arch_db).xpath(
            "//button[@name='action_message_send']"
        )[0]
        groups = self.env["res.groups"].browse(
            [self.env.ref(xmlid).id for xmlid in button.get("groups").split(",")]
        )
        wizard_model = self.env["ir.model"]._get("field.whatsapp.message")
        granting = self.env["ir.model.access"].search(
            [("model_id", "=", wizard_model.id), ("perm_create", "=", True)]
        )
        self.assertTrue(
            set(groups.ids) & set(granting.mapped("group_id").ids),
            "a user in the button's group would get an access error on click",
        )

    def test_the_wizard_opens_on_the_form_record(self):
        """The action opens the wizard with this record in its context."""
        result = self.form.action_message_send()
        self.assertEqual(result["res_model"], "field.whatsapp.message")
        self.assertEqual(result["target"], "new")
        self.assertEqual(
            result["context"]["default_res_model"], "field.operation.forms"
        )
        self.assertEqual(result["context"]["default_res_id"], self.form.id)

    def test_a_forms_user_without_the_group_is_refused(self):
        """Documents the failure the group gate prevents (measured, not assumed)."""
        user = self._user("field_operation_forms.forms_user")
        wizard = self.env["field.whatsapp.message"].with_user(user)
        with self.assertRaises(AccessError):
            wizard.create({"res_model": "field.operation.forms", "message": "hello"})
