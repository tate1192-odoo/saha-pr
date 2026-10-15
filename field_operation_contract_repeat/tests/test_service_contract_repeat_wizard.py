# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import time
from datetime import datetime, timedelta

from dateutil import rrule

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.field_operation_contract_repeat.wizard import (
    service_contract_repeat_wizard,
)

UTC = {"tz": "UTC"}
ISTANBUL = {"tz": "Europe/Istanbul"}


@tagged("post_install", "-at_install")
class TestServiceContractRepeatWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Repeat Wizard Customer"})
        cls.service_type = cls.env["field.operation.type"].create(
            {"name": "Repeat Wizard Type"}
        )
        cls.contract = cls.env["field.operation.contract"].create(
            {
                "partner_id": cls.partner.id,
                "service_type_ids": [Command.set(cls.service_type.ids)],
                "date_start": "2026-11-01",
            }
        )
        cls.wizard = cls.env["service.contract.repeat.wizard"]

    def _wizard(self, tag="UTC", **overrides):
        """Create a monthly, three occurrence wizard for the contract."""
        context = UTC if tag == "UTC" else ISTANBUL
        values = {
            "contract_id": self.contract.id,
            "rrule_freq": "monthly",
            "rrule_interval": 1,
            "rrule_end_type": "count",
            "rrule_count": 3,
        }
        values.update(overrides)
        return self.wizard.with_context(**context).create(values)

    def _operations(self, subject=None):
        """The operations this contract already holds (optionally by subject)."""
        domain = [("contract_id", "=", self.contract.id)]
        if subject:
            domain.append(("subject", "=", subject))
        return self.env["field.operation"].search(domain, order="start_date")

    # ------------------------------------------------------------------
    # Defaults taken from the contract
    # ------------------------------------------------------------------
    def test_creating_with_the_contract_only_fills_the_required_fields(self):
        """The contract is enough: no onchange runs on create.

        The required fields used to be filled by `_onchange_contract_id` alone,
        so an RPC/test call creating the wizard with only `contract_id` died on
        `null value in column "partner_id" ... violates not-null constraint`.
        """
        wizard = self.wizard.create({"contract_id": self.contract.id})
        self.assertEqual(wizard.partner_id, self.partner)
        self.assertEqual(wizard.company_id, self.contract.company_id)
        self.assertEqual(wizard.subject, self.contract.subject)
        self.assertEqual(wizard.start_date, self.contract.date_start)
        self.assertEqual(wizard.service_type_id, self.service_type)
        self.assertTrue(wizard.user_id)

    def test_the_monthly_day_follows_the_start_date(self):
        """A monthly rule recurs on the day of the start date, not of today.

        The default used to be `fields.Date.today().day`: a contract starting on
        the 1st generated its operations on the 11th when today is the 11th.
        """
        wizard = self._wizard()
        self.assertEqual(wizard.rrule_bymonthday, 1)
        wizard.action_generate_operations()
        self.assertEqual(
            [op.start_date.day for op in self._operations()],
            [1, 1, 1],
            "every operation must land on the day of the contract start date",
        )

    # ------------------------------------------------------------------
    # Values written on the generated operations
    # ------------------------------------------------------------------
    def test_the_generated_operations_content(self):
        self._wizard(subject="Content Check").action_generate_operations()
        operations = self._operations("Content Check")
        self.assertEqual(len(operations), 3)
        for operation in operations:
            self.assertEqual(operation.contract_id, self.contract)
            self.assertEqual(operation.partner_id, self.partner)
            self.assertEqual(operation.service_type_id, self.service_type)
            self.assertEqual(operation.status, "draft")
            self.assertNotEqual(
                operation.name, "/", "the sequence assigns the reference"
            )
            self.assertEqual(
                operation.end_date - operation.start_date,
                timedelta(days=1),
                "the Gantt view draws the operation between start_date and end_date",
            )

    def test_the_start_date_is_converted_from_the_user_timezone(self):
        """A stored Datetime is naive UTC, so the user timezone has to be added.

        Writing the rrule result as it comes put every operation at 00:00 UTC:
        03:00 on screen in Turkey, and the previous day for negative offsets.
        """
        self._wizard("ISTANBUL", subject="Timezone Check").action_generate_operations()
        operation = self._operations("Timezone Check")[0]
        self.assertEqual(operation.start_date, datetime(2026, 10, 31, 21, 0, 0))
        self.assertEqual(operation.end_date, datetime(2026, 11, 1, 21, 0, 0))

    # ------------------------------------------------------------------
    # Recurrence parameters
    # ------------------------------------------------------------------
    def test_rrule_params_for_every_frequency_and_end_type(self):
        wizard = self._wizard(
            rrule_freq="daily", rrule_end_type="until", end_date="2026-11-05"
        )
        params = wizard._prepare_rrule_params()
        self.assertNotIn("count", params)
        self.assertEqual(params["until"], datetime(2026, 11, 5, 23, 59, 59, 999999))
        self.assertEqual(params["dtstart"], datetime(2026, 11, 1, 0, 0, 0))
        self.assertEqual(params["freq"], rrule.DAILY)

        wizard.rrule_freq = "weekly"
        wizard.rrule_byweekday = "WE"
        self.assertEqual(wizard._prepare_rrule_params()["byweekday"], [rrule.WE])

        wizard.rrule_freq = "monthly"
        wizard.rrule_month_by = "day"
        wizard.rrule_bysetpos = "-1"
        wizard.rrule_byweekday_pos = "FR"
        self.assertEqual(wizard._prepare_rrule_params()["byweekday"], rrule.FR(-1))

    def test_every_weekday_selection_value_maps_to_a_recurrence_day(self):
        """The selection and the rrule mapping must not drift apart."""
        selection = dict(self.wizard._fields["rrule_byweekday"].selection)
        self.assertEqual(set(selection), set(service_contract_repeat_wizard.WEEKDAYS))
        self.assertEqual(
            dict(self.wizard._fields["rrule_byweekday_pos"].selection), selection
        )

    def test_an_until_recurrence_includes_the_end_date(self):
        self._wizard(
            rrule_freq="daily",
            rrule_end_type="until",
            end_date="2026-11-05",
            subject="Until Check",
        ).action_generate_operations()
        self.assertEqual(len(self._operations("Until Check")), 5)

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def test_the_cap_is_enforced_before_every_date_is_produced(self):
        """The limit must hold WHILE the dates are produced.

        The guard used to run after `list(rrule.rrule(...))`, so a large
        `rrule_count` (a free integer on the wizard) was materialised in full —
        measured: 100000 dates in 0.14s, and only then the error. With islice
        the work stops at the cap, hence the generous time bound below.
        """
        started = time.time()
        with self.assertRaises(UserError) as error:
            self._wizard(
                rrule_freq="daily", rrule_count=10_000_000
            ).action_generate_operations()
        self.assertIn("more than 500", str(error.exception))
        self.assertLess(time.time() - started, 5)
        self.assertFalse(
            self._operations(), "nothing may be created when the cap is hit"
        )

    def test_constraints_refuse_invalid_settings(self):
        for label, overrides in (
            ("interval", {"rrule_interval": 0}),
            ("count", {"rrule_count": 0}),
            ("until", {"rrule_end_type": "until", "end_date": "2026-10-01"}),
            ("day of month", {"rrule_bymonthday": 45}),
        ):
            with self.subTest(label), self.assertRaises(ValidationError):
                self._wizard(**overrides)

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------
    def test_the_dates_already_planned_are_skipped(self):
        self._wizard(subject="Idempotency Check").action_generate_operations()
        self.assertEqual(len(self._operations("Idempotency Check")), 3)

        action = self._wizard(subject="Idempotency Check").action_generate_operations()
        self.assertEqual(len(self._operations("Idempotency Check")), 3, "no duplicate")
        self.assertEqual(action.get("tag"), "display_notification")
        self.assertIn("3", action["params"]["message"])

    def test_new_dates_are_still_created_next_to_the_skipped_ones(self):
        self._wizard(subject="Partial Check").action_generate_operations()
        action = self._wizard(
            subject="Partial Check", rrule_count=4
        ).action_generate_operations()
        self.assertEqual(len(self._operations("Partial Check")), 4)
        self.assertEqual(action.get("tag"), "display_notification")
        self.assertEqual(action["params"]["next"]["res_model"], "field.operation")

    def test_a_similar_date_of_another_contract_is_not_a_duplicate(self):
        """The duplicate scope is the contract, not the whole schedule."""
        other = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": "2026-11-01",
            }
        )
        self.env["field.operation"].create(
            {
                "name": "/",
                "subject": "Scoped Check",
                "partner_id": self.partner.id,
                "contract_id": other.id,
                "start_date": "2026-11-01 00:00:00",
                "end_date": "2026-11-02 00:00:00",
                "status": "draft",
            }
        )
        self._wizard(subject="Scoped Check").action_generate_operations()
        self.assertEqual(
            len(self._operations("Scoped Check")),
            3,
            "the other contract's operation must not block this one",
        )
        self.assertEqual(
            self.env["field.operation"].search_count([("contract_id", "=", other.id)]),
            1,
        )

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def test_the_wizard_is_reserved_to_the_recurring_planning_group(self):
        access = self.env["ir.model.access"].search(
            [("model_id.model", "=", "service.contract.repeat.wizard")]
        )
        self.assertEqual(len(access), 1)
        self.assertEqual(
            access.group_id,
            self.env.ref("field_operation.group_field_operation_recurring"),
        )

    def test_the_button_carries_the_group_and_the_current_contract(self):
        arch = self.env.ref(
            "field_operation_contract_repeat.field_operation_contract_view_form_inherit_repeat"
        ).arch
        self.assertIn("field_operation.group_field_operation_recurring", arch)
        self.assertIn("'default_contract_id': id", arch)
