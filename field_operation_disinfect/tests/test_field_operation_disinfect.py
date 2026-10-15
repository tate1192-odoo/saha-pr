"""Tests for the disinfection module.

Covers what the review found broken: the record rule (assigned people and orphan lines),
the duplicated pH/CL fields, and the e-mail action that had no caller.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_disinfect", "post_install", "-at_install")
class TestFieldOperationDisinfect(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.forms_model = cls.env["field.operation.forms"]
        cls.line_model = cls.env["field.operation.disinfect"]
        cls.partner = cls.env["res.partner"].create({"name": "Disinfect Customer"})
        cls.service_type = cls.env["field.operation.type"].search([], limit=1)
        cls.product = cls.env["field.disinfect.product"].create({"name": "Dispenser"})

    def _user(self, login, *groups):
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "group_ids": [
                    Command.set(
                        [self.env.ref("base.group_user").id]
                        + [self.env.ref(xmlid).id for xmlid in groups]
                    )
                ],
            }
        )

    def _form(self, **values):
        values.setdefault("customer_id", self.partner.id)
        values.setdefault("service_type_id", self.service_type.id)
        return self.forms_model.create(values)

    def _line(self, form, **values):
        values.setdefault("product_id", self.product.id)
        if form:
            values.setdefault("forms_id", form.id)
        return self.line_model.create(values)

    def test_01_line_gets_a_reference(self):
        """The sequence the create() asks for exists and numbers the lines."""
        line = self._line(self._form())
        self.assertTrue(line.name.startswith("DIS-"), line.name)
        self.assertEqual(line.status, line.forms_id.status)
        self.assertEqual(line.customer_id, self.partner)

    def test_02_ph_fields_live_on_the_form_only(self):
        """The per-line pH/CL copies are gone; the form keeps the real pair."""
        self.assertNotIn("before_ph", self.line_model._fields)
        self.assertNotIn("before_cl", self.line_model._fields)
        self.assertIn("before_ph", self.forms_model._fields)

    def test_03_rule_follows_the_form_assignment(self):
        """Leader and assigned person see the lines; orphan lines stay private."""
        leader = self._user("dis_leader", "field_operation_forms.forms_user")
        technician = self._user("dis_tech", "field_operation_forms.forms_user")
        outsider = self._user("dis_outsider", "field_operation_forms.forms_user")
        employee = self.env["hr.employee"].create(
            {"name": "Disinfect Tech", "user_id": technician.id}
        )

        form = self._form(
            team_leader_id=leader.id, person_ids=[Command.set([employee.id])]
        )
        line = self._line(form)
        orphan = self._line(False, subject="Orphan line")

        self.assertIn(line, self.line_model.with_user(leader).search([]))
        self.assertIn(line, self.line_model.with_user(technician).search([]))
        self.assertNotIn(line, self.line_model.with_user(outsider).search([]))
        # an unassigned line is not shared with the field users any more
        self.assertNotIn(orphan, self.line_model.with_user(leader).search([]))

    def test_04_mail_action_opens_the_composer(self):
        """The template now has a caller, and it is the manager's action."""
        form = self._form(service_type_id=self.service_type.id)
        action = form.action_send_disinfect_mail()

        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertEqual(action["context"]["default_res_ids"], form.ids)
        template = self.env.ref(
            "field_operation_disinfect.email_field_operation_form_biocidal"
        )
        self.assertEqual(action["context"]["default_template_id"], template.id)

        forms_user = self._user("dis_mailer", "field_operation_forms.forms_user")
        with self.assertRaises(AccessError):
            form.with_user(forms_user).action_send_disinfect_mail()
