# tests/test_line_recurrence.py
from datetime import date

from odoo import Command
from odoo.tests.common import TransactionCase


class TestLineRecurrence(TransactionCase):
    """Tests for the line-based recurrence mode.

    A periodic contract may contain lines with different periods (monthly,
    quarterly, one-time) and different service locations. Each line must be
    processed on its own date and keep its own counter.
    """

    def setUp(self):
        super().setUp()
        self.env = self.env(
            context=dict(self.env.context, skip_product_code_automation=True)
        )
        self.partner = self.env["res.partner"].create({"name": "Test Customer"})
        self.location_1 = self.env["res.partner"].create(
            {
                "name": "Branch 1",
                "parent_id": self.partner.id,
                "type": "delivery",
            }
        )
        self.location_2 = self.env["res.partner"].create(
            {
                "name": "Branch 2",
                "parent_id": self.partner.id,
                "type": "delivery",
            }
        )
        self.service_type = self.env["field.operation.type"].create(
            {"name": "Maintenance"}
        )
        self.product_monthly = self._product("Monthly pest control")
        self.product_quarterly = self._product("Quarterly warehouse cleaning")
        self.product_one_time = self._product("One-time chimney cleaning")

    def _product(self, name):
        return self.env["product.product"].create(
            {
                "name": name,
                "type": "service",
                "lst_price": 100.0,
                "service_type_id": self.service_type.id,
            }
        )

    def _contract(self, **overrides):
        vals = {
            "partner_id": self.partner.id,
            "date_start": date(2024, 1, 1),
            "date_end": date(2024, 12, 31),
            "service_type_ids": [Command.set(self.service_type.ids)],
            "line_recurrence": True,
        }
        vals.update(overrides)
        return self.env["field.operation.contract"].create(vals)

    def _line(self, contract, product, location, rule, total, first_date):
        return self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": product.id,
                "service_type_id": self.service_type.id,
                "location_id": location.id,
                "date_start": first_date,
                "recurring_rule_type": rule,
                "recurring_interval": 1,
                "recurring_next_date": first_date,
                "total_service": total,
                "price_unit": 100.0,
            }
        )

    def test_mixed_periods_and_locations(self):
        contract = self._contract()
        monthly = self._line(
            contract,
            self.product_monthly,
            self.location_1,
            "monthly",
            12,
            date(2024, 1, 1),
        )
        quarterly = self._line(
            contract,
            self.product_quarterly,
            self.location_2,
            "quarterly",
            4,
            date(2024, 1, 1),
        )
        one_time = self._line(
            contract,
            self.product_one_time,
            self.location_1,
            "monthly",
            1,
            date(2024, 2, 15),
        )
        contract.action_confirm()

        Contract = self.env["field.operation.contract"]
        Contract._recurring_create_sale_ops(contract, date(2024, 1, 1))
        contract.invalidate_recordset()

        self.assertEqual(monthly.generated_occurrences, 1)
        self.assertEqual(quarterly.generated_occurrences, 1)
        self.assertEqual(one_time.generated_occurrences, 0)
        self.assertEqual(monthly.remaining_count, 11)
        self.assertEqual(quarterly.remaining_count, 3)
        self.assertEqual(one_time.remaining_count, 1)

        # January: one order/operation for each location, one operation per
        # line because only the monthly and quarterly lines are due.
        self.assertEqual(len(contract.generated_sale_ids), 2)
        self.assertEqual(len(contract.generated_operation_ids), 2)

        # February: the monthly line and the one-time line are due on the same
        # location; the quarterly line is not due yet.
        Contract._recurring_create_sale_ops(contract, date(2024, 2, 15))
        contract.invalidate_recordset()

        self.assertEqual(monthly.generated_occurrences, 2)
        self.assertEqual(quarterly.generated_occurrences, 1)
        self.assertEqual(one_time.generated_occurrences, 1)
        self.assertEqual(one_time.remaining_count, 0)
        self.assertEqual(len(contract.generated_sale_ids), 3)
        self.assertEqual(len(contract.generated_operation_ids), 4)

        # A second run at the same date must not duplicate the exhausted
        # one-time line.
        Contract._recurring_create_sale_ops(contract, date(2024, 2, 15))
        contract.invalidate_recordset()
        self.assertEqual(one_time.generated_occurrences, 1)
        self.assertEqual(
            len(
                contract.generated_operation_ids.filtered(
                    lambda operation: operation.subject == self.product_one_time.name
                )
            ),
            1,
        )

    def test_header_recurrence_advances_one_period_when_cron_is_late(self):
        contract = self._contract(
            line_recurrence=False,
            recurring_rule_type="monthly",
            recurring_interval=1,
            recurring_generation_type="beginning",
        )
        line = self._line(
            contract,
            self.product_monthly,
            self.location_1,
            "monthly",
            2,
            date(2024, 1, 1),
        )
        contract.action_confirm()

        Contract = self.env["field.operation.contract"]
        Contract._recurring_create_sale_ops(contract, date(2024, 3, 15))
        contract.invalidate_recordset()
        line.invalidate_recordset()

        # The missed January period is processed first; the cron must not jump
        # directly to the period containing 15 March.
        self.assertEqual(contract.last_date_processed, date(2024, 1, 31))
        self.assertEqual(contract.recurring_next_date, date(2024, 2, 1))
        self.assertEqual(len(contract.generated_operation_ids), 1)
        self.assertEqual(
            contract.generated_operation_ids.start_date.date(), date(2024, 1, 1)
        )

        Contract._recurring_create_sale_ops(contract, date(2024, 3, 15))
        contract.invalidate_recordset()
        line.invalidate_recordset()
        self.assertEqual(contract.last_date_processed, date(2024, 2, 29))
        self.assertEqual(contract.recurring_next_date, date(2024, 3, 1))
        self.assertEqual(len(contract.generated_operation_ids), 2)
        self.assertEqual(line.generated_occurrences, 2)
        self.assertEqual(line.remaining_count, 0)

        # Nothing left to generate for the two-service line.
        Contract._recurring_create_sale_ops(contract, date(2024, 3, 15))
        contract.invalidate_recordset()
        self.assertEqual(len(contract.generated_operation_ids), 2)

    def test_end_generation_does_not_skip_a_period(self):
        contract = self._contract(
            line_recurrence=False,
            recurring_rule_type="monthly",
            recurring_interval=1,
            recurring_generation_type="end",
            recurring_offset=1,
        )
        self._line(
            contract,
            self.product_monthly,
            self.location_1,
            "monthly",
            2,
            date(2024, 1, 1),
        )
        contract.action_confirm()

        self.assertEqual(contract.recurring_next_date, date(2024, 2, 1))

        Contract = self.env["field.operation.contract"]
        Contract._recurring_create_sale_ops(contract, date(2024, 2, 1))
        contract.invalidate_recordset()
        self.assertEqual(contract.last_date_processed, date(2024, 1, 31))
        self.assertEqual(contract.recurring_next_date, date(2024, 3, 1))
        self.assertEqual(
            contract.generated_operation_ids.start_date.date(), date(2024, 2, 1)
        )

        Contract._recurring_create_sale_ops(contract, date(2024, 3, 1))
        contract.invalidate_recordset()
        self.assertEqual(contract.last_date_processed, date(2024, 2, 29))
        self.assertEqual(contract.recurring_next_date, date(2024, 4, 1))
        self.assertEqual(len(contract.generated_operation_ids), 2)

    def test_monthly_last_day_does_not_skip_a_month(self):
        contract = self._contract(
            line_recurrence=False,
            recurring_rule_type="monthlylastday",
            recurring_interval=1,
            recurring_generation_type="beginning",
        )
        self._line(
            contract,
            self.product_monthly,
            self.location_1,
            "monthlylastday",
            3,
            date(2024, 1, 1),
        )
        contract.action_confirm()
        self.assertEqual(contract.recurring_next_date, date(2024, 1, 31))

        Contract = self.env["field.operation.contract"]
        Contract._recurring_create_sale_ops(contract, date(2024, 1, 31))
        contract.invalidate_recordset()
        self.assertEqual(contract.last_date_processed, date(2024, 1, 31))
        self.assertEqual(contract.recurring_next_date, date(2024, 2, 29))
        self.assertEqual(
            contract.generated_operation_ids.start_date.date(), date(2024, 1, 31)
        )

        Contract._recurring_create_sale_ops(contract, date(2024, 2, 29))
        contract.invalidate_recordset()
        self.assertEqual(contract.last_date_processed, date(2024, 2, 29))
        self.assertEqual(contract.recurring_next_date, date(2024, 3, 31))
        self.assertEqual(len(contract.generated_operation_ids), 2)
