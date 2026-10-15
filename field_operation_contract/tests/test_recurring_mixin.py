# test/test_recurring_mixin.py

# Copyright 2024 Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo.tests.common import TransactionCase


class TestRecurringMixin(TransactionCase):
    """Test recurring mixin through concrete model (contract.line)"""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
            }
        )
        self.contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )
        self.line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "date_start": date(2024, 1, 1),
                "total_service": 12,
                "price_unit": 100,
            }
        )
        # Mixin metodlarını line üzerinden test edeceğiz
        self.mixin = self.env["service.contract.recurring.mixin"]

    def test_get_relative_delta_daily(self):
        """Test relativedelta hesaplamaları - daily"""
        delta = self.mixin.get_relative_delta("daily", 2)
        self.assertEqual(delta, relativedelta(days=2))

    def test_get_relative_delta_weekly(self):
        """Test relativedelta hesaplamaları - weekly"""
        delta = self.mixin.get_relative_delta("weekly", 1)
        self.assertEqual(delta, relativedelta(weeks=1))

    def test_get_relative_delta_monthly(self):
        """Test relativedelta hesaplamaları - monthly"""
        delta = self.mixin.get_relative_delta("monthly", 3)
        self.assertEqual(delta, relativedelta(months=3))

    def test_get_relative_delta_quarterly(self):
        """Test relativedelta hesaplamaları - quarterly"""
        delta = self.mixin.get_relative_delta("quarterly", 1)
        self.assertEqual(delta, relativedelta(months=3))

    def test_get_relative_delta_semesterly(self):
        """Test relativedelta hesaplamaları - semesterly"""
        delta = self.mixin.get_relative_delta("semesterly", 1)
        self.assertEqual(delta, relativedelta(months=6))

    def test_get_relative_delta_yearly(self):
        """Test relativedelta hesaplamaları - yearly"""
        delta = self.mixin.get_relative_delta("yearly", 2)
        self.assertEqual(delta, relativedelta(years=2))

    def test_get_relative_delta_monthlylastday(self):
        """Test relativedelta hesaplamaları - monthlylastday"""
        delta = self.mixin.get_relative_delta("monthlylastday", 1)
        # day=31 otomatik ay sonuna ayarlar
        self.assertEqual(delta, relativedelta(months=1, day=31))

    def test_next_period_date_start_compute(self):
        """Test next period başlangıç tarihi hesaplama - computed field"""
        # Başlangıçta date_start kullanmalı
        self.assertEqual(self.line.next_period_date_start, date(2024, 1, 1))

        # last_date_processed ayarla
        self.line.last_date_processed = date(2024, 1, 31)
        self.line._compute_next_period_date_start()
        # +1 gün olmalı
        self.assertEqual(self.line.next_period_date_start, date(2024, 2, 1))

    def test_default_recurring_offset_beginning(self):
        """Test offset for beginning generation type"""
        offset = self.mixin._get_default_recurring_offset("beginning", "monthly")
        self.assertEqual(offset, 0)

    def test_default_recurring_offset_end(self):
        """Test offset for end generation type"""
        offset = self.mixin._get_default_recurring_offset("end", "monthly")
        self.assertEqual(offset, 1)

    def test_default_recurring_offset_monthlylastday(self):
        """Test offset for monthlylastday (always 0)"""
        offset_pre = self.mixin._get_default_recurring_offset(
            "beginning", "monthlylastday"
        )
        offset_post = self.mixin._get_default_recurring_offset("end", "monthlylastday")
        self.assertEqual(offset_pre, 0)
        self.assertEqual(offset_post, 0)

    @freeze_time("2024-01-01")
    def test_get_next_recurring_date_beginning(self):
        """Test dönem başı oluşturma"""
        next_date = self.mixin.get_next_recurring_date(
            next_period_date_start=date(2024, 1, 1),
            recurring_generation_type="beginning",
            recurring_offset=0,
            recurring_rule_type="monthly",
            recurring_interval=1,
            max_date_end=date(2024, 12, 31),
        )
        self.assertEqual(next_date, date(2024, 1, 1))

    def test_get_next_recurring_date_end(self):
        """Test dönem sonu oluşturma"""
        next_date = self.mixin.get_next_recurring_date(
            next_period_date_start=date(2024, 1, 1),
            recurring_generation_type="end",
            recurring_offset=1,
            recurring_rule_type="monthly",
            recurring_interval=1,
            max_date_end=date(2024, 12, 31),
        )
        # Jan 31 + 1 = Feb 1
        self.assertEqual(next_date, date(2024, 2, 1))

    def test_compute_recurring_next_date_depends_remaining(self):
        """Test recurring_next_date False when remaining_count <= 0"""
        self.line.remaining_count = 0
        self.line._compute_recurring_next_date()
        self.assertFalse(self.line.recurring_next_date)
