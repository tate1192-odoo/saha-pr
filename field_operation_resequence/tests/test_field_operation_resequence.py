"""Regression tests for the global Field Operation resequence wizard."""

from datetime import datetime, timezone

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("field_operation_resequence", "post_install", "-at_install")
class TestFieldOperationResequence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operation_model = (
            cls.env["field.operation"].sudo().with_context(active_test=False)
        )
        cls.operation_model.search([]).unlink()
        cls.sequence = cls.env.ref("field_operation.seq_field_operation")
        cls.sequence.write(
            {
                "active": True,
                "company_id": False,
                "prefix": "FO/",
                "suffix": False,
                "padding": 5,
                "number_increment": 1,
                "number_next": 50,
                "use_date_range": False,
                "implementation": "standard",
            }
        )
        cls.company = cls.env.company

    def _create_operation(self, name, create_date, **values):
        vals = {"name": name, "subject": name}
        vals.update(values)
        operation = self.env["field.operation"].create(vals)
        operation.write({"create_date": create_date})
        return operation

    def _wizard(self):
        return self.env["field.operation.resequence.wizard"].create({})

    def _create_user(self, name, group, companies):
        return self.env["res.users"].create(
            {
                "name": name,
                "login": f"{name.lower().replace(' ', '_')}@example.com",
                "company_id": companies[0].id,
                "company_ids": [Command.set(companies.ids)],
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            group.id,
                        ]
                    )
                ],
            }
        )

    def test_resequence_compacts_active_and_archived_operations(self):
        first = self._create_operation(
            "OLD/00003", datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        )
        archived = self._create_operation(
            "OLD/00001",
            datetime(2026, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
            active=False,
        )
        last = self._create_operation(
            "OLD/00002", datetime(2026, 1, 3, 10, 0, 0, tzinfo=timezone.utc)
        )

        wizard = self._wizard()
        self.assertEqual(wizard.total_count, 3)
        wizard.action_resequence()

        records = self.operation_model.search([], order="create_date asc, id asc")
        self.assertEqual(
            records.mapped("name"),
            ["FO/00001", "FO/00002", "FO/00003"],
        )
        self.assertEqual(records, first + archived + last)
        self.assertEqual(self.sequence.number_next, 4)

    def test_equal_create_dates_are_ordered_by_id(self):
        same_date = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        first = self._create_operation("OLD/00002", same_date)
        second = self._create_operation("OLD/00001", same_date)

        self._wizard().action_resequence()

        self.assertEqual(first.name, "FO/00001")
        self.assertEqual(second.name, "FO/00002")
        self.assertEqual(self.sequence.number_next, 3)

    def test_second_run_is_idempotent(self):
        self._create_operation(
            "OLD/00009", datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        )
        self._create_operation(
            "OLD/00008", datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)
        )

        self._wizard().action_resequence()
        self._wizard().action_resequence()

        self.assertEqual(
            self.operation_model.search([], order="create_date asc, id asc").mapped(
                "name"
            ),
            ["FO/00001", "FO/00002"],
        )
        self.assertEqual(self.sequence.number_next, 3)

    def test_empty_list_resets_the_sequence_to_one(self):
        wizard = self._wizard()
        self.assertEqual(wizard.total_count, 0)

        wizard.action_resequence()

        self.assertEqual(self.sequence.number_next, 1)

    def test_only_head_office_can_run_the_wizard(self):
        operation = self._create_operation(
            "OLD/00001", datetime(2026, 4, 1, 9, 0, 0, tzinfo=timezone.utc)
        )
        office_group = self.env.ref("field_operation.service_group_user")
        head_office_group = self.env.ref("field_operation.service_group_all")
        office = self._create_user("Resequence Office", office_group, self.company)
        head_office = self._create_user(
            "Resequence Head Office", head_office_group, self.company
        )
        wizard = self._wizard()

        with self.assertRaises(AccessError):
            wizard.with_user(office).action_resequence()
        with self.assertRaises(AccessError):
            self.env["field.operation.resequence.wizard"].with_user(office).create({})

        head_office_wizard = (
            self.env["field.operation.resequence.wizard"]
            .with_user(head_office)
            .create({})
        )
        head_office_wizard.action_resequence()

        self.assertEqual(operation.name, "FO/00001")
        self.assertEqual(self.sequence.number_next, 2)

    def test_operations_from_an_inaccessible_company_block_the_run(self):
        self._create_operation(
            "OLD/00001", datetime(2026, 5, 1, 9, 0, 0, tzinfo=timezone.utc)
        )
        other_company = self.env["res.company"].create({"name": "Other Company"})
        other_operation = self._create_operation(
            "OLD/00002",
            datetime(2026, 5, 2, 9, 0, 0, tzinfo=timezone.utc),
            company_id=other_company.id,
        )
        head_office_group = self.env.ref("field_operation.service_group_all")
        head_office = self._create_user(
            "Single Company Head Office", head_office_group, self.company
        )
        wizard = self._wizard()

        with self.assertRaises(UserError):
            wizard.with_user(head_office).action_resequence()

        self.assertEqual(other_operation.name, "OLD/00002")
        self.assertEqual(self.sequence.number_next, 50)

    def test_unsupported_sequence_configuration_is_rejected(self):
        self._create_operation(
            "OLD/00001", datetime(2026, 6, 1, 9, 0, 0, tzinfo=timezone.utc)
        )
        self.sequence.write({"use_date_range": True})
        wizard = self._wizard()

        with self.assertRaises(UserError):
            wizard.action_resequence()
