"""Tests for the operation-side pest data.

These tests do not need ``field_operation_forms``: the same model is used by
customers that print the service report from ``field.operation``.
"""

import uuid

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_pest", "post_install", "-at_install")
class TestFieldOperationPest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operation_model = cls.env["field.operation"]
        cls.line_model = cls.env["field.operation.pesticide"]
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
                "barcode": "PEST" + uuid.uuid4().hex[:10],
                "default_code": "PEST" + uuid.uuid4().hex[:10],
            }
        )

    def test_01_operation_line_gets_a_reference(self):
        operation = self.operation_model.create(
            {
                "partner_id": self.partner.id,
                "service_type_id": self.service_type.id,
            }
        )
        line = self.line_model.create(
            {"operation_id": operation.id, "product_id": self.product.id}
        )

        self.assertTrue(line.name.startswith("BIO-"), line.name)
        self.assertEqual(line.operation_id, operation)
        self.assertEqual(line.customer_id, self.partner)
        self.assertEqual(line.company_id, operation.company_id)
        self.assertEqual(line.status, operation.status)
        self.assertEqual(line.product_uom, self.product.uom_id)

    def test_02_pest_details_live_on_the_operation(self):
        operation = self.operation_model.create(
            {
                "partner_id": self.partner.id,
                "service_type_id": self.service_type.id,
                "hygiene": True,
                "residence": "12",
                "application_place": "house",
            }
        )
        self.assertTrue(operation.hygiene)
        self.assertEqual(operation.residence, "12")
        self.assertEqual(operation.application_place, "house")
        self.assertIn("hygiene", self.operation_model._fields)
        self.assertNotIn("hygiene", self.line_model._fields)
