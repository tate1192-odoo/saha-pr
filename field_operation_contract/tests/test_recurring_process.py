from datetime import date

from freezegun import freeze_time

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRecurringProcess(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Monthly Maintenance",
                "type": "service",
                "lst_price": 1000.0,
            }
        )
        self.service_type = self.env["field.operation.type"].create(
            {
                "name": "Maintenance",
            }
        )

    def create_confirmed_contract(
        self, date_start, recurring_rule="monthly", interval=1, total_service=12
    ):
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date_start,
                "recurring_rule_type": recurring_rule,
                "recurring_interval": interval,
                "recurring_next_date": date_start,
            }
        )
        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "service_type_id": self.service_type.id,
                "total_service": total_service,
                "price_unit": 1000,
                "date_start": date_start,
                "recurring_rule_type": recurring_rule,
                "recurring_interval": interval,
                "recurring_generation_type": "beginning",
                "recurring_next_date": date_start,
            }
        )
        contract.action_confirm()
        return contract, line

    @freeze_time("2024-01-01")
    def test_recurring_process_creates_sale_order(self):
        contract, line = self.create_confirmed_contract(date(2024, 1, 1))
        self.env["field.operation.contract"]._recurring_create_sale_ops(
            contract, date(2024, 1, 1)
        )
        self.assertTrue(contract.generated_sale_ids)
        self.assertEqual(len(contract.generated_sale_ids), 1)
        self.assertEqual(contract.generated_sale_ids.service_contract_id, contract)

    @freeze_time("2024-01-01")
    def test_recurring_process_creates_field_operation(self):
        contract, line = self.create_confirmed_contract(date(2024, 1, 1))
        self.env["field.operation.contract"]._recurring_create_sale_ops(
            contract, date(2024, 1, 1)
        )
        self.assertTrue(contract.generated_operation_ids)
        self.assertEqual(len(contract.generated_operation_ids), 1)
        self.assertEqual(contract.generated_operation_ids.contract_id, contract)

    @freeze_time("2024-01-01")
    def test_recurring_process_updates_line_counters(self):
        contract, line = self.create_confirmed_contract(
            date(2024, 1, 1), total_service=5
        )
        self.assertEqual(line.generated_occurrences, 0)
        self.assertEqual(line.remaining_count, 5)
        self.env["field.operation.contract"]._recurring_create_sale_ops(
            contract, date(2024, 1, 1)
        )
        line.invalidate_recordset()
        self.assertEqual(line.generated_occurrences, 1)
        self.assertEqual(line.remaining_count, 4)

    def test_group_lines_by_location_with_header_recurrence(self):
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.partner.id,
                "date_start": date(2024, 1, 1),
                "state": "confirmed",
                "recurring_rule_type": "monthly",
                "recurring_interval": 1,
                "recurring_next_date": date(2024, 1, 1),
            }
        )
        loc1 = self.env["res.partner"].create(
            {
                "name": "Branch 1",
                "parent_id": self.partner.id,
                "type": "delivery",
            }
        )
        loc2 = self.env["res.partner"].create(
            {
                "name": "Branch 2",
                "parent_id": self.partner.id,
                "type": "delivery",
            }
        )
        self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "location_id": loc1.id,
                "date_start": date(2024, 1, 1),
                "total_service": 12,
                "price_unit": 100,
                "recurring_rule_type": "monthly",
                "recurring_interval": 1,
                "recurring_next_date": date(2024, 1, 1),
            }
        )
        self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "location_id": loc1.id,
                "date_start": date(2024, 1, 1),
                "total_service": 6,
                "price_unit": 200,
                "recurring_rule_type": "monthly",
                "recurring_interval": 1,
                "recurring_next_date": date(2024, 1, 1),
            }
        )
        self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": self.product.id,
                "location_id": loc2.id,
                "date_start": date(2024, 1, 1),
                "total_service": 12,
                "price_unit": 100,
                "recurring_rule_type": "monthly",
                "recurring_interval": 1,
                "recurring_next_date": date(2024, 1, 1),
            }
        )
        self.env["field.operation.contract"]._recurring_create_sale_ops(
            contract, date(2024, 1, 1)
        )
        self.assertEqual(len(contract.generated_sale_ids), 2)
        loc1_order = contract.generated_sale_ids.filtered(
            lambda o: o.partner_shipping_id == loc1
        )
        product_lines = loc1_order.order_line.filtered(
            lambda line: not line.display_type
        )
        self.assertEqual(len(product_lines), 2)

    @freeze_time("2024-01-01")
    def test_no_lines_to_process_when_next_date_in_future(self):
        contract, line = self.create_confirmed_contract(date(2024, 2, 1))
        result = contract._prepare_header_recurrence_values(date(2024, 1, 1))
        so_vals, op_vals, contract_updates, line_updates = result
        self.assertEqual(so_vals, [])
        self.assertEqual(op_vals, [])

    @freeze_time("2024-01-01")
    def test_cron_job_execution(self):
        contract1, _ = self.create_confirmed_contract(date(2024, 1, 1))
        contract2, _ = self.create_confirmed_contract(date(2024, 1, 15))
        contract3, _ = self.create_confirmed_contract(date(2024, 1, 1))
        contract3.action_cancel()
        self.env["field.operation.contract"].action_recurring_process()
        self.assertTrue(contract1.generated_sale_ids)
        self.assertFalse(contract2.generated_sale_ids)
        self.assertFalse(contract3.generated_sale_ids)
