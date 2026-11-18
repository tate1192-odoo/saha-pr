"""Generation safety: lead time, idempotency, savepoint isolation, dry run."""

from datetime import date

from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.tests.common import TransactionCase


class TestGenerationSafety(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, skip_product_code_automation=True)
        )
        cls.company = cls.env.company
        cls.company.contract_generation_lead_days = 7
        cls.partner = cls.env["res.partner"].create({"name": "Safety Customer"})
        cls.location = cls.env["res.partner"].create(
            {
                "name": "Safety Branch",
                "parent_id": cls.partner.id,
                "type": "delivery",
            }
        )
        cls.service_type = cls.env["field.operation.type"].create(
            {"name": "Safety Type"}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Safety Service",
                "type": "service",
                "lst_price": 100.0,
                "service_type_id": cls.service_type.id,
            }
        )

    # ------------------------------------------------------------------ data
    def _contract(self, **overrides):
        vals = {
            "partner_id": self.partner.id,
            "date_start": date(2024, 1, 1),
            "date_end": date(2024, 12, 31),
            "service_type_ids": [Command.set(self.service_type.ids)],
            "recurring_rule_type": "monthly",
            "recurring_interval": 1,
            "recurring_generation_type": "beginning",
            "contract_line_ids": [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "location_id": self.location.id,
                        "date_start": date(2024, 1, 1),
                        "total_service": 12,
                        "price_unit": 100.0,
                    }
                )
            ],
        }
        vals.update(overrides)
        contract = self.env["field.operation.contract"].create(vals)
        contract.action_confirm()
        return contract

    def _run(self, contracts, process_date, dry_run=False):
        return self.env["field.operation.contract"]._recurring_create_sale_ops(
            contracts, process_date, dry_run=dry_run
        )

    # ------------------------------------------------------------------ lead
    def test_lead_time_defers_generation(self):
        """Nothing is created 8 days before the service date, only 7 days after."""
        contract = self._contract()
        self._run(contract, date(2023, 12, 24))
        contract.invalidate_recordset()
        self.assertEqual(contract.generated_sale_ids, self.env["sale.order"])
        self.assertEqual(contract.generated_operation_ids, self.env["field.operation"])

        self._run(contract, date(2023, 12, 25))
        contract.invalidate_recordset()
        self.assertEqual(len(contract.generated_sale_ids), 1)
        self.assertEqual(len(contract.generated_operation_ids), 1)
        # the service date itself must not move
        self.assertEqual(
            contract.generated_operation_ids.start_date.date(), date(2024, 1, 1)
        )
        self.assertEqual(
            contract.generated_sale_ids.date_order.date(), date(2024, 1, 1)
        )

    def test_contract_lead_overrides_company(self):
        contract = self._contract(generation_lead_days=3)
        self._run(contract, date(2023, 12, 28))
        contract.invalidate_recordset()
        self.assertEqual(contract.generated_sale_ids, self.env["sale.order"])

        self._run(contract, date(2023, 12, 29))
        contract.invalidate_recordset()
        self.assertEqual(len(contract.generated_sale_ids), 1)

    def test_company_lead_is_used_when_contract_is_zero(self):
        self.company.contract_generation_lead_days = 10
        contract = self._contract(generation_lead_days=0)
        self._run(contract, date(2023, 12, 21))
        contract.invalidate_recordset()
        self.assertEqual(contract.generated_sale_ids, self.env["sale.order"])

        self._run(contract, date(2023, 12, 22))
        contract.invalidate_recordset()
        self.assertEqual(len(contract.generated_sale_ids), 1)

    # ------------------------------------------------------------ idempotency
    def test_period_order_is_not_duplicated(self):
        """An order for the same period/location means the occurrence is done."""
        contract = self._contract()
        self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "partner_shipping_id": self.location.id,
                "service_contract_id": contract.id,
                "order_types": "invoice",
                "contract_period_start": date(2024, 1, 1),
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        self._run(contract, date(2024, 1, 1))
        contract.invalidate_recordset()
        self.assertEqual(len(contract.generated_sale_ids), 1)
        # the header still moves on, so the contract is not stuck
        self.assertEqual(contract.last_date_processed, date(2024, 1, 31))

    def test_legacy_order_counts_as_the_period(self):
        """Orders created before contract_period_start existed are recognised."""
        contract = self._contract()
        self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "partner_shipping_id": self.location.id,
                "service_contract_id": contract.id,
                "order_types": "invoice",
                "date_order": fields.Datetime.to_datetime(date(2024, 1, 5)),
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        self._run(contract, date(2024, 1, 1))
        contract.invalidate_recordset()
        self.assertEqual(
            self.env["sale.order"].search_count(
                [
                    ("service_contract_id", "=", contract.id),
                    ("contract_period_start", "=", date(2024, 1, 1)),
                ]
            ),
            0,
        )
        self.assertEqual(contract.last_date_processed, date(2024, 1, 31))

    def test_unique_period_constraint(self):
        contract = self._contract()
        values = {
            "partner_id": self.partner.id,
            "partner_shipping_id": self.location.id,
            "service_contract_id": contract.id,
            "order_types": "invoice",
            "contract_period_start": date(2024, 1, 1),
        }
        self.env["sale.order"].create(values)
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["sale.order"].create(dict(values))

    def test_line_operation_is_not_duplicated(self):
        contract = self._contract(line_recurrence=True)
        line = contract.contract_line_ids
        line.write({"recurring_next_date": date(2024, 1, 1)})
        self._run(contract, date(2024, 1, 1))
        line.invalidate_recordset()
        self.assertEqual(line.generated_occurrences, 1)

        operation = contract.generated_operation_ids
        self.assertEqual(len(operation), 1)
        self.assertEqual(operation.contract_line_id, line)

        # A second pass must not create another operation for the same date.
        line.write(
            {
                "generated_occurrences": 0,
                "last_date_processed": False,
                "recurring_next_date": date(2024, 1, 1),
            }
        )
        self._run(contract, date(2024, 1, 1))
        self.assertEqual(
            self.env["field.operation"].search_count(
                [("contract_id", "=", contract.id), ("contract_line_id", "=", line.id)]
            ),
            1,
        )

    # --------------------------------------------------------------- dry run
    def test_dry_run_writes_nothing(self):
        contract = self._contract()
        result = self._run(contract, date(2024, 1, 1), dry_run=True)
        self.assertEqual(
            self.env["sale.order"].search_count(
                [("service_contract_id", "=", contract.id)]
            ),
            0,
        )
        self.assertEqual(
            self.env["field.operation"].search_count(
                [("contract_id", "=", contract.id)]
            ),
            0,
        )
        self.assertEqual(result[0]["sales"], 1)
        self.assertEqual(result[0]["operations"], 1)
        self.assertEqual(result[0]["amount"], 100.0)

    # -------------------------------------------------------------- isolation
    def test_one_broken_contract_does_not_block_the_others(self):
        """A real database error on one contract must not abort the whole run."""
        good = self._contract()
        bad = self._contract()
        # An order already exists for the bad contract's period. The duplicate
        # check is bypassed for that contract, so the INSERT really violates the
        # unique constraint (a Python-level raise would not touch the cursor and
        # would not prove the savepoint).
        self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "partner_shipping_id": self.location.id,
                "service_contract_id": bad.id,
                "order_types": "invoice",
                "contract_period_start": date(2024, 1, 1),
            }
        )
        Contract = type(self.env["field.operation.contract"])
        original = Contract._already_generated

        def _already(self_, period_start, location, period_end=None):
            if self_ == bad:
                return False
            return original(self_, period_start, location, period_end)

        Contract._already_generated = _already
        try:
            results = self._run(good | bad, date(2024, 1, 1))
        finally:
            Contract._already_generated = original

        good.invalidate_recordset()
        bad.invalidate_recordset()
        self.assertEqual(len(good.generated_sale_ids), 1)
        self.assertEqual(len(bad.generated_sale_ids), 1)  # only the planted one
        errors = [row for row in results if row.get("error")]
        self.assertEqual(len(errors), 1)
        self.assertIn("contract_period_unique", errors[0]["error"])
        self.assertTrue(
            bad.message_ids.filtered(
                lambda message: "contract_period_unique" in (message.body or "")
            )
        )
        # The failed contract must not poison the transaction: SQL must still
        # work for the rest of the book. A bare try/except leaves the cursor
        # aborted; only the per-contract savepoint recovers it.
        self.env.flush_all()
        self.assertEqual(
            self.env["sale.order"].search_count(
                [("service_contract_id", "=", good.id)]
            ),
            1,
        )
