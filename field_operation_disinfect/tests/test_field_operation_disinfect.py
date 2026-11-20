"""Tests for the operation-side disinfection data.

These tests do not need ``field_operation_forms``: the same model is used by
customers that print the service report from ``field.operation``.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_disinfect", "post_install", "-at_install")
class TestFieldOperationDisinfect(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.operation_model = cls.env["field.operation"]
        cls.line_model = cls.env["field.operation.disinfect"]
        cls.partner = cls.env["res.partner"].create({"name": "Disinfect Customer"})
        cls.service_type = cls.env["field.operation.type"].search(
            [("type", "=", "disinfect")], limit=1
        )
        cls.product = cls.env["field.disinfect.product"].create({"name": "Dispenser"})

    def test_01_operation_line_gets_a_reference(self):
        """The operation is the parent and the sequence numbers the line."""
        operation = self.operation_model.create(
            {
                "partner_id": self.partner.id,
                "service_type_id": self.service_type.id,
            }
        )
        line = self.line_model.create(
            {"operation_id": operation.id, "product_id": self.product.id}
        )

        self.assertTrue(line.name.startswith("DIS-"), line.name)
        self.assertEqual(line.operation_id, operation)
        self.assertEqual(line.customer_id, self.partner)
        self.assertEqual(line.company_id, operation.company_id)
        self.assertEqual(line.status, operation.status)

    def test_02_ph_readings_live_on_the_operation(self):
        operation = self.operation_model.create(
            {
                "partner_id": self.partner.id,
                "service_type_id": self.service_type.id,
                "before_ph": "7.2",
                "after_cl": "0.5",
            }
        )
        self.assertEqual(operation.before_ph, "7.2")
        self.assertEqual(operation.after_cl, "0.5")
        self.assertIn("before_ph", self.operation_model._fields)
        self.assertNotIn("before_ph", self.line_model._fields)
