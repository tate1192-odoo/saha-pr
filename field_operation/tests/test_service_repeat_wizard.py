"""Regression tests for the recurring service wizard (`service.repeat.wizard`).

* the monthly "Day of Month" defaulted to ``fields.Date.today().day``, so a rule
  starting on the 1st generated its operations on the 11th whenever today is
  the 11th — it now follows the start date and stays editable;
* the ``max_recurring_operations`` cap was checked AFTER
  ``list(rrule.rrule(...))``, so a large ``rrule_count`` (a free integer on the
  wizard) was materialised in full before the error was raised.
"""

import time
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("field_operation", "post_install", "-at_install")
class TestServiceRepeatWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Repeat Wizard Customer"})
        cls.wizard = cls.env["service.repeat.wizard"]

    def _wizard(self, **overrides):
        values = {
            "partner_id": self.partner.id,
            "dtstart": date(2026, 11, 1),
            "rrule_freq": "monthly",
            "rrule_interval": 1,
            "rrule_end_type": "count",
            "rrule_count": 3,
        }
        values.update(overrides)
        return self.wizard.with_context(tz="UTC").create(values)

    def test_the_monthly_day_follows_the_start_date(self):
        wizard = self._wizard()
        self.assertEqual(wizard.rrule_bymonthday, 1)
        self.assertEqual(wizard._prepare_rrule_params()["bymonthday"], 1)

    def test_the_monthly_day_stays_editable(self):
        wizard = self._wizard(rrule_bymonthday=15)
        self.assertEqual(wizard._prepare_rrule_params()["bymonthday"], 15)

    def test_the_cap_is_enforced_before_every_date_is_produced(self):
        started = time.time()
        with self.assertRaises(UserError) as error:
            self._wizard(
                rrule_freq="daily", rrule_count=10_000_000
            ).action_generate_operations()
        self.assertIn("more than 500", str(error.exception))
        self.assertLess(time.time() - started, 5)
