"""Tests for the independent pest form lines.

The form flow owns its data: the lines live in
``field.operation.forms.pest`` and the pest details live on the form.  No
operation is created or updated.
"""

import uuid

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_forms_pest", "post_install", "-at_install")
class TestFieldOperationFormsPest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.forms_model = cls.env["field.operation.forms"]
        cls.pesticide_model = cls.env["field.operation.forms.pest"]
        cls.operation_line_model = cls.env["field.operation.pesticide"]
        cls.operation_model = cls.env["field.operation"]
        cls.partner = cls.env["res.partner"].create({"name": "Pest Customer"})
        cls.service_type = cls.env["field.operation.type"].search(
            [("type", "=", "pest")], limit=1
        )
        if not cls.service_type:
            cls.service_type = cls.env["field.operation.type"].create(
                {"name": "Pest", "type": "pest"}
            )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Pest Product",
                "type": "consu",
                "is_storable": True,
                "barcode": "PEST" + uuid.uuid4().hex[:10],
                "default_code": "PEST" + uuid.uuid4().hex[:10],
            }
        )
        cls.picking_type = cls.env["stock.picking.type"].search(
            [("code", "=", "outgoing")], limit=1
        )
        warehouse = cls.env["stock.warehouse"].search([], limit=1)
        cls.source_location = (
            warehouse.lot_stock_id if warehouse else cls.env["stock.location"]
        )
        cls.dest_location = cls.env["stock.location"].search(
            [("usage", "=", "customer")], limit=1
        )

    def _form(self, **values):
        values.setdefault("customer_id", self.partner.id)
        values.setdefault("service_type_id", self.service_type.id)
        if self.picking_type:
            values.setdefault("picking_type_id", self.picking_type.id)
        if self.source_location:
            values.setdefault("source_location_id", self.source_location.id)
        if self.dest_location:
            values.setdefault("destination_location_id", self.dest_location.id)
        return self.forms_model.create(values)

    def _pesticide(self, form, qty=1.0):
        return self.pesticide_model.create(
            {
                "forms_id": form.id,
                "product_id": self.product.id,
                "product_qty": qty,
            }
        )

    def test_01_line_lives_on_the_form(self):
        """The form is the only parent: there is no operation link."""
        form = self._form()
        pesticide = self._pesticide(form)

        self.assertTrue(pesticide.name.startswith("BIO-F-"), pesticide.name)
        self.assertEqual(pesticide.forms_id, form)
        self.assertEqual(pesticide.product_id, self.product)
        self.assertEqual(pesticide.product_uom, self.product.uom_id)
        self.assertNotIn("operation_id", self.pesticide_model._fields)
        self.assertFalse(form.operation_id)

    def test_02_transfer_guards(self):
        """No lines, or no group: no delivery order."""
        form = self._form()
        with self.assertRaises(UserError):
            form.action_transfer()

        self._pesticide(form)
        outsider = self.env["res.users"].create(
            {
                "name": "pest_outsider",
                "login": "pest_outsider",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        with self.assertRaises(AccessError):
            form.with_user(outsider).action_transfer()

        form.destination_location_id = self.source_location
        with self.assertRaises(UserError):
            form.action_transfer()
        form.destination_location_id = self.dest_location

    def test_03_transfer_creates_a_linked_delivery_order(self):
        """The picking carries the pesticide lines and points back at the form."""
        if not self.picking_type or not self.dest_location:
            self.skipTest("No stock configuration in this database.")

        form = self._form()
        self._pesticide(form, qty=2.5)
        self.assertTrue(form.action_transfer())

        picking = form.stock_picking_id
        self.assertTrue(picking)
        self.assertEqual(picking.field_operation_form_id, form)
        self.assertEqual(picking.partner_id, self.partner)
        self.assertEqual(picking.origin, form.name)
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(picking.move_ids.product_qty, 2.5)
        self.assertEqual(form.picking_count, 1)
        self.assertEqual(form.action_view_picking()["res_id"], picking.id)

    def test_04_picking_count_is_zero_without_delivery(self):
        form = self._form()
        self.assertEqual(form.picking_count, 0)
        self.assertEqual(
            form.action_view_picking()["type"], "ir.actions.act_window_close"
        )

    def test_05_stock_and_pest_fields_are_gated_by_service_type(self):
        """The stock and pest-type fields only belong on a pest form."""
        view = self.env.ref(
            "field_operation_forms_pest.field_operation_forms_pest_view"
        )
        arch = etree.fromstring(view.arch_db)
        gated = {
            "pest_type_ids",
            "picking_type_id",
            "source_location_id",
            "destination_location_id",
        }
        found = {
            node.get("name"): node.get("invisible")
            for node in arch.iter("field")
            if node.get("name") in gated
        }
        self.assertEqual(set(found), gated)
        for name, expression in found.items():
            self.assertEqual(expression, "service_type != 'pest'", name)

    def test_06_pest_type_is_gated_on_the_operation_form(self):
        """The operation form carries the same gate as the service form."""
        arch = etree.fromstring(
            self.env["field.operation"].get_view(view_type="form")["arch"]
        )
        found = {
            node.get("name"): node.get("invisible")
            for node in arch.iter("field")
            if node.get("name") == "pest_type_ids"
        }
        self.assertEqual(
            found,
            {"pest_type_ids": "service_type_id.type != 'pest'"},
            "the operation form shows the pest type on every service type",
        )

    def test_07_operation_line_without_form(self):
        """A customer without forms creates the line straight on the operation."""
        operation = self.operation_model.create(
            {
                "partner_id": self.partner.id,
                "service_type_id": self.service_type.id,
            }
        )
        line = self.operation_line_model.create(
            {"operation_id": operation.id, "product_id": self.product.id}
        )

        self.assertNotIn("forms_id", self.operation_line_model._fields)
        self.assertEqual(line.customer_id, self.partner)
        self.assertEqual(line.status, operation.status)
        self.assertIn(line, operation.pesticide_ids)

    def test_08_pest_fields_live_on_the_form(self):
        pest_type = self.env["field.operation.pest.type"].create({"name": "Ant"})
        form = self._form()
        form.hygiene = True
        form.residence = "12"
        form.pest_type_ids = [Command.set([pest_type.id])]

        self.assertTrue(form.hygiene)
        self.assertEqual(form.residence, "12")
        self.assertEqual(form.pest_type_ids, pest_type)
        self.assertFalse(form.operation_id)

    def test_09_deleting_the_form_deletes_the_lines(self):
        form = self._form()
        line = self._pesticide(form)
        form.unlink()
        self.assertFalse(line.exists())

    def test_10_no_operation_is_created(self):
        operation_count = self.operation_model.search_count([])
        form = self._form()
        self._pesticide(form)
        self.assertFalse(form.operation_id)
        self.assertEqual(self.operation_model.search_count([]), operation_count)
