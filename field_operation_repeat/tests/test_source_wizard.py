"""The recurrence wizard can be opened on an existing service."""

from datetime import date, datetime, timedelta

from odoo.tests import TransactionCase, tagged

HOURS = timedelta(hours=2)
TZ = "Europe/Istanbul"


@tagged("standard")
class TestSourceWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Wizard Customer"})
        # 09:00 in Istanbul (UTC+3) is 06:00 UTC.
        cls.start = datetime(2026, 3, 3, 6, 0, 0)
        cls.source = cls.env["field.operation"].create(
            {
                "partner_id": cls.partner.id,
                "subject": "Monthly maintenance",
                "start_date": cls.start,
                "end_date": cls.start + HOURS,
                "service_price": 150.0,
            }
        )

    def _wizard(self, **values):
        settings = {
            "field_operation_id": self.source.id,
            "partner_id": self.partner.id,
            "dtstart": date(2026, 3, 3),
            "rrule_freq": "monthly",
            "rrule_interval": 1,
            "rrule_end_type": "count",
            "rrule_count": 3,
        }
        settings.update(values)
        return self.env["service.repeat.wizard"].with_context(tz=TZ).create(settings)

    def _periods(self):
        return self.source.child_ids.sorted("start_date")

    def test_default_get_fills_the_source(self):
        """The dialog opens with the customer, subject and local start of the source."""
        values = (
            self.env["service.repeat.wizard"]
            .with_context(tz=TZ, default_field_operation_id=self.source.id)
            .default_get(["field_operation_id", "partner_id", "subject", "dtstart"])
        )
        self.assertEqual(values["field_operation_id"], self.source.id)
        self.assertEqual(values["partner_id"], self.partner.id)
        self.assertEqual(values["subject"], "Monthly maintenance")
        self.assertEqual(values["dtstart"], date(2026, 3, 3))

    def test_generated_periods_follow_the_source(self):
        """Periods are linked to the source and keep its time of day."""
        self._wizard().action_generate_operations()
        periods = self._periods()
        # count=3 includes the source date, which is not one of its own periods.
        self.assertEqual(len(periods), 2)
        self.assertEqual(
            periods.mapped("start_date"),
            [datetime(2026, 4, 3, 6, 0), datetime(2026, 5, 3, 6, 0)],
        )
        for period in periods:
            self.assertEqual(period.parent_id, self.source)
            self.assertEqual(period.end_date, period.start_date + HOURS)
            self.assertEqual(period.partner_id, self.partner)
            self.assertEqual(period.subject, "Monthly maintenance")
            self.assertEqual(period.service_price, 150.0)
            self.assertEqual(period.status, "planned")
        # The run is traced on the source service.
        self.assertTrue(self.source.message_ids)

    def test_night_service_keeps_its_local_date(self):
        """A service at 00:30 local keeps its own date in the series."""
        source = self.env["field.operation"].create(
            {
                "partner_id": self.partner.id,
                "subject": "Night call",
                # 00:30 in Istanbul on 04-03 is 21:30 UTC on 03-03.
                "start_date": datetime(2026, 3, 3, 21, 30),
                "end_date": datetime(2026, 3, 3, 22, 30),
            }
        )
        wizard = self._wizard(field_operation_id=source.id, dtstart=date(2026, 3, 4))
        wizard.action_generate_operations()
        starts = source.child_ids.sorted("start_date").mapped("start_date")
        # 00:30 local on the 4th of each month is 21:30 UTC the day before.
        self.assertEqual(
            starts,
            [datetime(2026, 4, 3, 21, 30), datetime(2026, 5, 3, 21, 30)],
        )

    def test_generated_status(self):
        """The overlay decides the status of the generated operations."""
        self._wizard(generated_status="draft").action_generate_operations()
        self.assertEqual(set(self._periods().mapped("status")), {"draft"})

    def test_skip_existing_dates(self):
        """A date that already has a period is not planned twice."""
        self.env["field.operation"].create(
            {
                "partner_id": self.partner.id,
                "subject": "Monthly maintenance",
                "parent_id": self.source.id,
                "start_date": datetime(2026, 4, 3, 6, 0),
                "end_date": datetime(2026, 4, 3, 8, 0),
            }
        )
        self._wizard(skip_existing=True).action_generate_operations()
        self.assertEqual(
            self._periods().mapped("start_date"),
            [datetime(2026, 4, 3, 6, 0), datetime(2026, 5, 3, 6, 0)],
        )

    def test_unlinked_periods(self):
        """The series link can be switched off."""
        before = self.env["field.operation"].search([])
        self._wizard(link_to_source=False).action_generate_operations()
        created = self.env["field.operation"].search([]) - before
        self.assertEqual(len(created), 2)
        self.assertFalse(created.parent_id)
        self.assertFalse(self.source.child_ids)

    def test_dialog_without_source_keeps_the_core_behaviour(self):
        """Without a source the dialog is the core one: midnight, no parent."""
        wizard = (
            self.env["service.repeat.wizard"]
            .with_context(tz=TZ)
            .create(
                {
                    "partner_id": self.partner.id,
                    "subject": "Standalone",
                    "dtstart": date(2026, 3, 5),
                    "rrule_freq": "daily",
                    "rrule_interval": 1,
                    "rrule_end_type": "count",
                    "rrule_count": 2,
                }
            )
        )
        wizard.action_generate_operations()
        created = self.env["field.operation"].search(
            [("subject", "=", "Standalone")], order="start_date"
        )
        self.assertEqual(len(created), 2)
        # Midnight in Istanbul is 21:00 UTC of the previous day.
        self.assertEqual(created[0].start_date, datetime(2026, 3, 4, 21, 0))
        self.assertFalse(created.parent_id)

    def test_preview_skips_the_source_date(self):
        """The preview shows the dates that will really be created."""
        preview = self._wizard().preview_dates
        self.assertIn("2026-04-03", preview)
        self.assertNotIn("2026-03-03", preview)

    def test_rescheduling_does_not_move_other_periods(self):
        """The series is only a link, not a rescheduling instruction."""
        self._wizard().action_generate_operations()
        periods = self._periods()
        old_dates = [(period.start_date, period.end_date) for period in periods]
        new_start = self.start + timedelta(days=10)

        self.source.write(
            {"start_date": new_start, "end_date": new_start + HOURS}
        )

        self.assertEqual(
            [(period.start_date, period.end_date) for period in periods], old_dates
        )
