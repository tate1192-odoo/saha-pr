# tests/test_contract.py

# Copyright 2024 Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestContract(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Monthly Service",
                "type": "service",
                "lst_price": 500.0,
            }
        )
        self.service_type = self.env["field.operation.type"].create(
            {
                "name": "Maintenance",
            }
        )

    def test_contract_sequence(self):
        """Test contract numarası sequence'dan gelmeli"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )
        self.assertNotEqual(contract.name, "/")
        self.assertTrue(len(contract.name) > 3)  # Sequence atandı mı?

    def test_confirm_without_lines_error(self):
        """Test satır olmadan confirm edilememe"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )
        with self.assertRaises(UserError):
            contract.action_confirm()

    def test_confirm_with_lines_success(self):
        """Test satır ile confirm başarılı"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )
        self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "total_service": 12,
                "price_unit": 500,
            }
        )

        self.assertEqual(contract.state, "draft")
        result = contract.action_confirm()

        self.assertEqual(contract.state, "confirmed")
        # signature_date is only set when the contract is actually signed
        self.assertFalse(contract.signature_date)
        self.assertEqual(result["type"], "ir.actions.client")

    def test_compute_total_amount(self):
        """Test toplam tutar hesaplama"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )
        # 2 satır ekle
        self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "total_service": 2,
                "price_unit": 100,
            }
        )
        self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "total_service": 3,
                "price_unit": 200,
            }
        )
        # 2*100 + 3*200 = 800
        self.assertEqual(contract.total_amount, 800.0)

    def test_compute_rest_days(self):
        """Test kalan gün hesaplama"""
        today = date.today()
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": today,
                "date_end": today + timedelta(days=30),
            }
        )
        contract._compute_rest_days()
        self.assertEqual(contract.rest_days, 30)

    def test_rest_days_expired_contract(self):
        """Test süresi dolmuş contract'ta kalan gün 0 olmalı"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2020, 1, 1),
                "date_end": date(2020, 12, 31),
                "state": "expired",
            }
        )
        self.assertEqual(contract.rest_days, 0)

    def test_action_view_operations(self):
        """Test operasyon görüntüleme action'ı"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )
        action = contract.action_view_operations()
        self.assertEqual(action["res_model"], "field.operation")
        self.assertEqual(action["domain"], [("contract_id", "=", contract.id)])

    def test_action_view_sales(self):
        """Test satış görüntüleme action'ı"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )
        action = contract.action_view_sales()
        self.assertEqual(action["res_model"], "sale.order")
        self.assertEqual(action["domain"], [("service_contract_id", "=", contract.id)])

    def test_state_transitions(self):
        """Test state geçişleri"""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
            }
        )

        # Draft -> Cancel
        contract.action_cancel()
        self.assertEqual(contract.state, "cancel")

        # Cancel -> Draft
        contract.action_set_to_draft()
        self.assertEqual(contract.state, "draft")

        # Draft -> Expired
        contract.action_expire()
        self.assertEqual(contract.state, "expired")

    def test_header_next_date_survives_line_change(self):
        """Header-mode recurring_next_date must not be wiped by line edits."""
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
                "recurring_rule_type": "monthly",
                "recurring_interval": 1,
            }
        )
        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "total_service": 12,
                "price_unit": 100,
                "date_start": date(2024, 1, 1),
                "recurring_next_date": date(2024, 1, 1),
            }
        )
        contract.action_confirm()
        self.assertEqual(contract.recurring_next_date, date(2024, 1, 1))

        line.total_service = 6
        contract.invalidate_recordset()
        self.assertEqual(contract.recurring_next_date, date(2024, 1, 1))
