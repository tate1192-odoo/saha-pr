"""Rescheduling a recurring service drags its later periods with it."""

from datetime import datetime, timedelta
from unittest import mock

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

DAY = timedelta(days=1)
HOURS = timedelta(hours=2)


@tagged("standard")
class TestSeriesShift(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Repeat Customer"})
        # A Monday morning: the hours matter, moving a plan is a day matter.
        cls.start = datetime(2026, 3, 2, 9, 0, 0)
        cls.source = cls.env["field.operation"].create(
            {
                "partner_id": cls.partner.id,
                "subject": "Daily maintenance",
                "start_date": cls.start,
                "end_date": cls.start + HOURS,
            }
        )
        cls.periods = cls.env["field.operation"].create(
            [
                {
                    "partner_id": cls.partner.id,
                    "subject": "Daily maintenance",
                    "parent_id": cls.source.id,
                    "start_date": cls.start + DAY * index,
                    "end_date": cls.start + DAY * index + HOURS,
                }
                for index in (1, 2, 3)
            ]
        )

    def _assert_shifted(self, operation, expected_start):
        self.assertEqual(operation.start_date, expected_start)
        if operation.end_date:
            self.assertEqual(operation.end_date, expected_start + HOURS)

    def test_source_move_shifts_later_periods(self):
        """Dragging the source of the series moves every later period."""
        self.source.write(
            {
                "start_date": self.start + DAY * 2,
                "end_date": self.start + DAY * 2 + HOURS,
            }
        )
        for index, period in enumerate(self.periods, start=1):
            self._assert_shifted(period, self.start + DAY * (index + 2))

    def test_moving_a_period_shifts_only_the_following_ones(self):
        """Moving a middle period leaves the source and the past periods alone."""
        first, second, third = self.periods
        second.write(
            {
                "start_date": second.start_date + DAY * 3,
                "end_date": second.end_date + DAY * 3,
            }
        )
        self._assert_shifted(self.source, self.start)
        self._assert_shifted(first, self.start + DAY)
        self._assert_shifted(second, self.start + DAY * 5)
        self._assert_shifted(third, self.start + DAY * 6)

    def test_done_periods_are_left_alone(self):
        """Executed periods never move, the plan continues after them."""
        last = self.periods[-1]
        last.write({"status": "done"})
        self.source.write(
            {
                "start_date": self.start + DAY,
                "end_date": self.start + DAY + HOURS,
            }
        )
        self._assert_shifted(last, self.start + DAY * 3)

    def test_done_source_does_not_move_the_series(self):
        """A closed service never reschedules the future periods."""
        self.source.write({"status": "done"})
        with mock.patch.object(type(self.env.user), "_bus_send"):
            self.source.write(
                {
                    "start_date": self.start + DAY * 2,
                    "end_date": self.start + DAY * 2 + HOURS,
                }
            )
        self._assert_shifted(self.source, self.start + DAY * 2)
        for index, period in enumerate(self.periods, start=1):
            self._assert_shifted(period, self.start + DAY * index)

    def test_backward_move_shifts_periods_back(self):
        """Pulling the series forward pulls the later periods forward too."""
        self.source.write(
            {
                "start_date": self.start - DAY * 2,
                "end_date": self.start - DAY * 2 + HOURS,
            }
        )
        for index, period in enumerate(self.periods, start=1):
            self._assert_shifted(period, self.start + DAY * (index - 2))

    def test_time_only_change_does_not_move_the_series(self):
        """Only whole days move the plan, period time slots stay untouched."""
        self.source.write({"start_date": self.start + timedelta(hours=2)})
        for index, period in enumerate(self.periods, start=1):
            self._assert_shifted(period, self.start + DAY * index)

    def test_backward_time_only_change_does_not_move_the_series(self):
        """A move backwards of a few hours must not shift a whole day.

        ``timedelta.days`` floors, so the sign of the shift used to be
        asymmetric: two hours backwards moved the series back by one day.
        """
        self.source.write(
            {
                "start_date": self.start - timedelta(hours=2),
                "end_date": self.start - timedelta(hours=2) + HOURS,
            }
        )
        for index, period in enumerate(self.periods, start=1):
            self._assert_shifted(period, self.start + DAY * index)

    def test_conflict_is_warned_not_blocked(self):
        """A period falling on a busy employee warns the user, the move happens."""
        employee = self.env["hr.employee"].create({"name": "Repeat Technician"})
        busy_start = self.start + DAY * 5
        self.env["field.operation"].create(
            {
                "partner_id": self.partner.id,
                "subject": "Other job",
                "start_date": busy_start,
                "end_date": busy_start + HOURS,
                "person_ids": [(6, 0, employee.ids)],
                "status": "planned",
            }
        )
        self.source.write({"person_ids": [(6, 0, employee.ids)], "status": "planned"})
        with mock.patch.object(type(self.env.user), "_bus_send") as bus_send:
            self.source.write(
                {"start_date": busy_start, "end_date": busy_start + HOURS}
            )
        # The move went through: the guard did not block the calendar drag & drop.
        self._assert_shifted(self.source, busy_start)
        self._assert_shifted(self.periods[0], busy_start + DAY)
        # ... and the user was warned about the conflict.
        bus_send.assert_called_once()
        payload = bus_send.call_args.args[1]
        self.assertEqual(payload["type"], "warning")
        self.assertIn("Repeat Technician", payload["message"])
        # The move is also traced on the chatter of the moved service.
        self.assertTrue(self.source.message_ids)

    def test_plain_service_is_still_blocked(self):
        """Services outside a plan keep the blocking guard of the core module."""
        employee = self.env["hr.employee"].create({"name": "Repeat Technician"})
        busy_start = self.start + DAY * 5
        self.env["field.operation"].create(
            {
                "partner_id": self.partner.id,
                "subject": "Other job",
                "start_date": busy_start,
                "end_date": busy_start + HOURS,
                "person_ids": [(6, 0, employee.ids)],
                "status": "planned",
            }
        )
        plain = self.env["field.operation"].create(
            {
                "partner_id": self.partner.id,
                "subject": "Single service",
                "start_date": self.start,
                "end_date": self.start + HOURS,
                "person_ids": [(6, 0, employee.ids)],
                "status": "planned",
            }
        )
        with self.assertRaises(ValidationError):
            plain.write({"start_date": busy_start, "end_date": busy_start + HOURS})
