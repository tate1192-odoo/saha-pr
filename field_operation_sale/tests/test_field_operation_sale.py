"""Tests for the field_operation_sale bridge.

Both directions are covered — service → sale (wizard) and sale → service
(``create_sale_service``) — plus the guards around them and the counters, which used to
be computed without a dependency and would not move when the link changed.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_sale", "post_install", "-at_install")
class TestFieldOperationSale(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sale_group = cls.env.ref(
            "field_operation_sale.group_field_operation_sale_enabled"
        )
        cls.env.user.group_ids = [(4, cls.sale_group.id)]
        cls.partner = cls.env["res.partner"].create({"name": "Bridge Customer"})
        cls.service_product = cls.env["product.product"].create(
            {
                "name": "Bridge Service",
                "type": "service",
                "sale_ok": True,
                "list_price": 250.0,
            }
        )
        cls.wizard_model = cls.env["field.operation.create.sale.wizard"]

    def _operation(self, **values):
        defaults = {
            "subject": "Bridge Job",
            "partner_id": self.partner.id,
            "status": "done",
            "service_price": 250.0,
        }
        defaults.update(values)
        return self.env["field.operation"].create(defaults)

    def _sale(self, **values):
        defaults = {"partner_id": self.partner.id, "order_types": "service"}
        defaults.update(values)
        return self.env["sale.order"].create(defaults)

    def _wizard(self, operations, model=None):
        # `model or self.wizard_model` would be a trap: an empty recordset is falsy,
        # so the caller env (with_user) would silently be replaced by this one
        model = self.wizard_model if model is None else model
        return model.with_context(active_ids=operations.ids).create(
            {
                "operation_ids": [(6, 0, operations.ids)],
                "product_id": self.service_product.id,
            }
        )

    def _user_without_sale_group(self, extra_group=None):
        groups = [self.env.ref("field_operation.service_group_user").id]
        if extra_group:
            groups.append(self.env.ref(extra_group).id)
        return self.env["res.users"].create(
            {
                "name": "Office Without Sale Group",
                "login": "office_without_sale_group",
                "group_ids": [(6, 0, groups)],
            }
        )

    def test_01_wizard_creates_a_draft_sale_and_links_both_ways(self):
        """The wizard turns a service into a draft order with its price and customer."""
        operation = self._operation()
        wizard = self._wizard(operation)
        self.assertEqual(wizard.operation_ids, operation)

        action = wizard.action_create_sale()
        sale = self.env["sale.order"].browse(action["domain"][0][2])

        self.assertEqual(len(sale), 1)
        self.assertEqual(sale.state, "draft")
        self.assertEqual(sale.partner_id, self.partner)
        self.assertEqual(sale.order_types, "service")
        self.assertEqual(sale.field_operation_id, operation)
        self.assertEqual(operation.sale_id, sale)
        self.assertEqual(len(sale.order_line), 1)
        self.assertEqual(sale.order_line.price_unit, 250.0)
        self.assertEqual(sale.order_line.name, operation.subject)
        self.assertEqual(operation.sale_count, 1)
        self.assertEqual(sale.field_operation_count, 1)

    def test_02_wizard_refuses_a_service_without_customer(self):
        """A sale order needs a customer: the wizard says so instead of the ORM."""
        operation = self._operation(partner_id=False)
        wizard = self._wizard(operation)
        with self.assertRaises(UserError):
            wizard.action_create_sale()
        self.assertFalse(operation.sale_id)

    def test_03_wizard_needs_the_module_group(self):
        """The button is hidden by a group; the model must enforce the same group."""
        user = self._user_without_sale_group()
        self.assertFalse(
            user.has_group("field_operation_sale.group_field_operation_sale_enabled")
        )
        # the office record rule only shows the user their own services
        operation = self._operation(user_id=user.id)
        wizard = self._wizard(operation, model=self.wizard_model.with_user(user))
        self.assertEqual(wizard.env.user, user)
        with self.assertRaises(AccessError):
            wizard.action_create_sale()
        self.assertFalse(operation.sale_id)

    def test_04_invoice_preparation_carries_the_service(self):
        """Both link directions must reach the invoice reference."""
        operation = self._operation()
        sale = self._sale(field_operation_id=operation.id)
        self.assertEqual(sale._prepare_invoice()["field_operation_id"], operation.id)

        # reverse direction only: the service points at the order
        sale.field_operation_id = False
        operation.sale_id = sale
        self.assertEqual(sale._prepare_invoice()["field_operation_id"], operation.id)

    def test_05_create_sale_service_makes_one_service_per_line(self):
        """One operation per product line, priced from the line, and no duplicates."""
        sale = self._sale(
            order_line=[
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 2,
                        "price_unit": 100.0,
                    },
                ),
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 1,
                        "price_unit": 50.0,
                    },
                ),
            ]
        )
        self.assertEqual(sale.field_operation_count, 0)

        sale.create_sale_service()

        # the counter follows the new services (it used to stay at 0)
        self.assertEqual(sale.field_operation_count, 2)
        self.assertEqual(sale.field_operation_ids.partner_id, self.partner)
        self.assertEqual(
            sorted(sale.field_operation_ids.mapped("service_price")), [50.0, 200.0]
        )
        # start_date is a real timestamp, not midnight UTC coming from a date
        limit = fields.Datetime.now() - timedelta(minutes=5)
        for operation in sale.field_operation_ids:
            self.assertGreater(operation.start_date, limit)
            self.assertEqual(operation.sale_id, sale)

        with self.assertRaises(UserError):
            sale.create_sale_service()
        self.assertEqual(sale.field_operation_count, 2)

    def test_06_create_sale_service_needs_the_module_group(self):
        """A sale manager without the module group cannot create services this way."""
        user = self._user_without_sale_group("sales_team.group_sale_salesman")
        sale = self._sale(
            order_line=[
                (
                    0,
                    0,
                    {
                        "product_id": self.service_product.id,
                        "product_uom_qty": 1,
                        "price_unit": 10.0,
                    },
                ),
            ]
        ).with_user(user)
        with self.assertRaises(AccessError):
            sale.create_sale_service()
        # read back as the test user: the guard must have stopped it before any write
        created = self.env["field.operation"].search([("sale_id", "=", sale.id)])
        self.assertFalse(created)
