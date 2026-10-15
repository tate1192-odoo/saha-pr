# tests/test_sale_order_contract_wizard.py

# Copyright 2024 Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.tests.common import TransactionCase


class TestSaleOrderContractWizard(TransactionCase):
    """Tests for Sale Order to Contract Wizard."""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
            }
        )
        self.product_service = self.env["product.product"].create(
            {
                "name": "Maintenance Service",
                "type": "service",
                "lst_price": 1000.0,
                "service_type_id": self.env["field.operation.type"]
                .create({"name": "Maintenance"})
                .id,
            }
        )
        self.product_product = self.env["product.product"].create(
            {
                "name": "Physical Product",
                "type": "consu",
                "lst_price": 500.0,
            }
        )

        # Create Sale Order
        self.sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_types": "contract",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_service.id,
                            "product_uom_qty": 2,
                            "price_unit": 1000,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_product.id,
                            "product_uom_qty": 1,
                            "price_unit": 500,
                        }
                    ),
                ],
            }
        )

    def test_wizard_default_get_populates_from_sale_order(self):
        """Test wizard populates correctly from sale order context."""
        # Launch wizard with active_id context
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id, active_model="sale.order")
            .create({})
        )

        self.assertEqual(wizard.sale_order_id, self.sale_order)
        self.assertEqual(wizard.partner_id, self.partner)
        self.assertEqual(wizard.company_id, self.sale_order.company_id)

        # Check date defaults
        self.assertEqual(wizard.date_start, date.today())
        self.assertEqual(wizard.date_end, date.today() + relativedelta(years=1))

    def test_wizard_default_get_creates_lines_for_service_products(self):
        """Test wizard creates lines only for service products."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        # Should have 1 line (service product only, not physical product)
        self.assertEqual(len(wizard.line_ids), 1)

        line = wizard.line_ids[0]
        self.assertEqual(line.product_id, self.product_service)
        self.assertEqual(line.product_uom_qty, 2)
        self.assertEqual(line.price_unit, 1000)
        self.assertEqual(line.service_type_id, self.product_service.service_type_id)

    def test_wizard_default_get_no_service_lines(self):
        """Test wizard has no lines when SO has no service products."""
        sale_only_physical = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_product.id,
                            "product_uom_qty": 1,
                            "price_unit": 500,
                        }
                    ),
                ],
            }
        )

        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=sale_only_physical.id)
            .create({})
        )
        self.assertEqual(len(wizard.line_ids), 0)

    def test_wizard_default_get_sets_service_types(self):
        """Test wizard collects service types from products."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        # Should include the service type from product
        self.assertIn(self.product_service.service_type_id, wizard.service_type_ids)

    def test_wizard_line_default_values(self):
        """Test wizard line gets correct default values."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        line = wizard.line_ids[0]
        self.assertEqual(line.recurring_interval, 1)
        self.assertEqual(line.recurring_rule_type, "monthly")
        self.assertEqual(line.recurring_next_date, date.today())
        self.assertEqual(line.sequence, 10)

    def test_action_create_contract_creates_contract(self):
        """Test creating contract from wizard."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        # Set some values
        wizard.date_start = date(2024, 1, 1)
        wizard.date_end = date(2024, 12, 31)

        # Execute
        action = wizard.action_create_contract()

        # Check contract created
        contract = self.env["field.operation.contract"].browse(action["res_id"])
        self.assertTrue(contract.exists())
        self.assertEqual(contract.partner_id, self.partner)
        self.assertEqual(contract.date_start, date(2024, 1, 1))
        self.assertEqual(contract.date_end, date(2024, 12, 31))

    def test_action_create_contract_creates_contract_lines(self):
        """Test contract lines are created from wizard lines."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        # Modify wizard line
        wizard_line = wizard.line_ids[0]
        wizard_line.recurring_interval = 2
        wizard_line.recurring_rule_type = "weekly"
        wizard_line.recurring_next_date = date(2024, 1, 15)

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])

        # Check contract line
        self.assertEqual(len(contract.contract_line_ids), 1)
        contract_line = contract.contract_line_ids[0]

        self.assertEqual(contract_line.product_id, self.product_service)
        self.assertEqual(contract_line.total_service, 2)  # qty from SO
        self.assertEqual(contract_line.price_unit, 1000)
        self.assertEqual(contract_line.recurring_interval, 2)
        self.assertEqual(contract_line.recurring_rule_type, "weekly")
        self.assertEqual(contract_line.recurring_next_date, date(2024, 1, 15))
        self.assertEqual(contract_line.date_start, date(2024, 1, 15))

    def test_action_create_contract_links_sale_order(self):
        """Test sale order is linked to created contract."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])

        # Check sale order updated
        self.assertEqual(self.sale_order.service_contract_id, contract)
        self.assertEqual(self.sale_order.state, "sent")  # State changed to sent

    def test_action_create_contract_with_location(self):
        """Test contract created with locations."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        # Add location
        location = self.env["res.partner"].create(
            {
                "name": "Service Location",
                "parent_id": self.partner.id,
                "type": "delivery",
            }
        )
        wizard.location_ids = location
        wizard.line_ids.location_id = location

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])

        self.assertIn(location, contract.location_ids)
        self.assertEqual(contract.contract_line_ids[0].location_id, location)

    def test_action_create_contract_description_from_note(self):
        """Test contract description comes from sale order note."""
        self.sale_order.note = "<p>Special requirements</p>"

        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])

        self.assertEqual(contract.description, "<p>Special requirements</p>")

    def test_wizard_line_name_fallback(self):
        """Test wizard line name falls back to product name if empty."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        line = wizard.line_ids[0]
        line.name = False

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])

        # Name should fallback to product display_name
        self.assertEqual(
            contract.contract_line_ids[0].name, self.product_service.display_name
        )

    def test_action_create_contract_with_section_line(self):
        """Section/note lines must not break on required date_start."""
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_types": "contract",
                "order_line": [
                    Command.create(
                        {"display_type": "line_section", "name": "Section A"}
                    ),
                    Command.create(
                        {
                            "product_id": self.product_service.id,
                            "product_uom_qty": 1,
                            "price_unit": 1000,
                        }
                    ),
                ],
            }
        )
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=sale_order.id)
            .create({})
        )

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])

        sections = contract.contract_line_ids.filtered(
            lambda line: line.display_type == "line_section"
        )
        self.assertEqual(len(sections), 1)
        self.assertTrue(sections.date_start)

    def test_action_create_contract_maps_taxes(self):
        """Taxes on sale order lines must be carried over to contract lines."""
        tax = self.env["account.tax"].create(
            {
                "name": "Test Sale Tax",
                "amount": 20,
                "type_tax_use": "sale",
            }
        )
        self.product_service.taxes_id = tax

        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_types": "contract",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_service.id,
                            "product_uom_qty": 1,
                            "price_unit": 1000,
                        }
                    ),
                ],
            }
        )
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=sale_order.id)
            .create({})
        )
        wizard_line = wizard.line_ids.filtered(lambda line: not line.display_type)
        self.assertIn(tax, wizard_line.tax_id)

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])
        contract_line = contract.contract_line_ids.filtered(
            lambda line: not line.display_type
        )
        self.assertIn(tax, contract_line.tax_id)

    def test_contract_returns_open_action(self):
        """Test wizard returns action to open created contract."""
        wizard = (
            self.env["sale.order.contract.wizard"]
            .with_context(active_id=self.sale_order.id)
            .create({})
        )

        action = wizard.action_create_contract()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "field.operation.contract")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "current")
        self.assertTrue(action["res_id"])
