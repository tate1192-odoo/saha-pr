"""Live-data regressions from issue #54 (measured on the uzman backup)."""

from datetime import date

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractSalesVisibility(TransactionCase):
    """Item 1: a confirmed source quotation is a real order and must stay visible."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Visibility Customer"})
        cls.contract = cls.env["field.operation.contract"].create(
            {
                "partner_id": cls.partner.id,
                "date_start": date(2026, 1, 1),
            }
        )

    def _sale(self, order_types, state):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "service_contract_id": self.contract.id,
                "order_types": order_types,
            }
        )
        order.write({"state": state})
        return order

    def test_a_confirmed_contract_quotation_stays_on_the_button(self):
        approved = self._sale("contract", "sale")
        open_quote = self._sale("contract", "sent")
        periodic = self._sale("service", "sale")

        self.assertIn(approved, self.contract.generated_sale_ids)
        self.assertNotIn(open_quote, self.contract.generated_sale_ids)
        self.assertIn(periodic, self.contract.generated_sale_ids)
        self.assertEqual(self.contract.sale_count, 2)

    def test_the_sales_action_uses_the_same_domain(self):
        approved = self._sale("contract", "sale")
        open_quote = self._sale("contract", "draft")

        action = self.contract.action_view_sales()
        sales = self.env["sale.order"].search(action["domain"])

        self.assertIn(approved, sales)
        self.assertNotIn(open_quote, sales)


@tagged("post_install", "-at_install")
class TestRecurringPlanIsEditable(TransactionCase):
    """Item 2: header mode lets the office drive the plan by hand."""

    def test_the_header_fields_are_editable_and_the_line_mode_is_not(self):
        view = self.env.ref(
            "field_operation_contract.view_field_operation_contract_form"
        )
        arch = etree.fromstring(view.arch_db)
        for name in ("recurring_next_date", "last_date_processed"):
            nodes = arch.xpath(f"//field[@name='{name}']")
            editable = [n for n in nodes if n.get("readonly") == "line_recurrence"]
            self.assertTrue(
                editable,
                f"{name} must be editable in header mode and read-only in line mode",
            )


@tagged("post_install", "-at_install")
class TestRecurringAnchor(TransactionCase):
    """Item 3: normalising the pair must not move the service day."""

    def setUp(self):
        super().setUp()
        self.contract = self.env["field.operation.contract"].create(
            {
                "partner_id": self.env["res.partner"].create({"name": "Anchor"}).id,
                "date_start": date(2026, 1, 7),
                "recurring_rule_type": "monthly",
                "recurring_interval": 1,
                "recurring_generation_type": "beginning",
            }
        )

    def test_the_anchor_moves_to_the_day_the_book_plans(self):
        # The live pair: a service date in ``last`` and the wanted day in ``next``.
        self.contract.write({"last_date_processed": date(2026, 3, 7)})
        self.contract.write({"recurring_next_date": date(2026, 4, 7)})

        moved = self.contract._normalize_recurring_anchor()

        self.assertEqual(moved, 1)
        self.assertEqual(self.contract.last_date_processed, date(2026, 4, 6))
        self.assertEqual(self.contract.recurring_next_date, date(2026, 4, 7))
        self.assertEqual(self.contract.next_period_date_start, date(2026, 4, 7))

    def test_a_consistent_pair_is_left_alone(self):
        self.contract.write({"last_date_processed": date(2026, 3, 31)})
        self.contract.write({"recurring_next_date": date(2026, 4, 1)})

        self.assertEqual(self.contract._normalize_recurring_anchor(), 0)
        self.assertEqual(self.contract.last_date_processed, date(2026, 3, 31))
        self.assertEqual(self.contract._normalize_recurring_anchor(), 0)

    def test_a_dry_run_reports_without_writing(self):
        self.contract.write({"last_date_processed": date(2026, 3, 7)})
        self.contract.write({"recurring_next_date": date(2026, 4, 7)})

        self.assertEqual(self.contract._normalize_recurring_anchor(dry_run=True), 1)
        self.assertEqual(self.contract.last_date_processed, date(2026, 3, 7))

    def test_an_exhausted_line_is_not_normalized(self):
        """Backfilling an exhausted line would erase its historical plan date."""
        line = self.env["field.operation.contract.line"].create(
            {
                "contract_id": self.contract.id,
                "date_start": date(2026, 1, 1),
                "total_service": 0,
            }
        )
        self.assertEqual(line.remaining_count, 0)
        # Simulate a manually edited historical pair after remaining_count was
        # computed; normalization must not turn that date into a fresh schedule.
        line.write(
            {
                "last_date_processed": date(2026, 2, 17),
                "recurring_next_date": date(2026, 2, 19),
            }
        )
        self.assertEqual(line.recurring_next_date, date(2026, 2, 19))

        self.assertEqual(line._normalize_recurring_anchor(), 0)
        self.assertEqual(line.last_date_processed, date(2026, 2, 17))
        self.assertEqual(line.recurring_next_date, date(2026, 2, 19))

    def _anchor_contract(self, rule_type, generation_type):
        return self.env["field.operation.contract"].create(
            {
                "partner_id": self.env["res.partner"].create({"name": "Anchor"}).id,
                "date_start": date(2026, 1, 31),
                "recurring_rule_type": rule_type,
                "recurring_interval": 1,
                "recurring_generation_type": generation_type,
            }
        )

    def test_an_end_of_period_schedule_is_not_normalized(self):
        """``next = last + 1`` does not hold for ``end``: the plan would move."""
        contract = self._anchor_contract("monthly", "end")
        contract.write({"last_date_processed": date(2026, 3, 31)})
        self.assertEqual(contract.recurring_next_date, date(2026, 5, 1))

        self.assertEqual(contract._normalize_recurring_anchor(), 0)
        self.assertEqual(contract.last_date_processed, date(2026, 3, 31))
        self.assertEqual(contract.recurring_next_date, date(2026, 5, 1))

    def test_a_month_last_day_schedule_is_not_normalized(self):
        """The occurrence survives, but the period window would jump to month end."""
        contract = self._anchor_contract("monthlylastday", "beginning")
        contract.write({"last_date_processed": date(2026, 3, 31)})
        self.assertEqual(contract.recurring_next_date, date(2026, 4, 30))
        period_start = contract.next_period_date_start

        self.assertEqual(contract._normalize_recurring_anchor(), 0)
        self.assertEqual(contract.last_date_processed, date(2026, 3, 31))
        self.assertEqual(contract.next_period_date_start, period_start)
