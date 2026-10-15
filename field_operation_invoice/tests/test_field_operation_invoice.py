"""Tests for the field_operation_invoice bridge.

Covers both invoicing paths (single service, consolidated), their guards, and the two
behaviours that used to be wrong: the link surviving a cancellation (deliberate, the
override meant to break it never ran) and a stale bulk wizard invoicing a service twice.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("field_operation_invoice", "post_install", "-at_install")
class TestFieldOperationInvoice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Invoice Customer"})
        cls.other_partner = cls.env["res.partner"].create({"name": "Other Customer"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Invoiced Service",
                "type": "service",
                "sale_ok": True,
                "list_price": 200.0,
            }
        )
        cls.wizard_model = cls.env["field.operation.to.invoice.wizard"]
        cls.bulk_model = cls.env["field.operation.bulk.invoice.wizard"]

    def _operation(
        self, subject="Invoice Job", partner=None, status="done", price=100.0
    ):
        return self.env["field.operation"].create(
            {
                "subject": subject,
                "partner_id": (partner or self.partner).id,
                "status": status,
                "service_price": price,
            }
        )

    def _invoice(self, operation, price=100.0, product=None):
        wizard = self.wizard_model.create(
            {
                "field_operation_id": operation.id,
                "partner_id": operation.partner_id.id,
                "service_price": price,
                "product_id": (product or self.product).id,
            }
        )
        return self.env["account.move"].browse(wizard.action_create_invoice()["res_id"])

    def _invoice_count_for(self, operation):
        return self.env["account.move"].search_count(
            [("invoice_line_ids.field_operation_id", "=", operation.id)]
        )

    def test_01_single_wizard_creates_and_links_the_invoice(self):
        """The wizard turns a service into a draft invoice and links both ways."""
        operation = self._operation()
        wizard = self.wizard_model.with_context(
            default_field_operation_id=operation.id
        ).create({})

        self.assertEqual(wizard.field_operation_id, operation)
        self.assertEqual(wizard.partner_id, self.partner)
        self.assertEqual(wizard.service_price, 100.0)
        self.assertEqual(wizard.description, operation.subject)

        invoice = self.env["account.move"].browse(
            wizard.action_create_invoice()["res_id"]
        )
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.partner_id, self.partner)
        self.assertEqual(invoice.amount_total, 100.0)
        self.assertEqual(len(invoice.invoice_line_ids), 1)
        self.assertEqual(invoice.invoice_line_ids.field_operation_id, operation)
        self.assertEqual(invoice.invoice_line_ids.price_unit, 100.0)

        # the service side
        self.assertEqual(operation.account_move_id, invoice)
        self.assertEqual(operation.invoicing, "billed")
        self.assertEqual(operation.invoice_count, 1)
        self.assertEqual(invoice.field_operation_invoice_count, 1)

    def test_02_single_wizard_guards(self):
        """A service is invoiced once, and only with a customer and a positive price."""
        operation = self._operation()
        with self.assertRaises(UserError):
            self.wizard_model.create(
                {"field_operation_id": operation.id, "service_price": 0.0}
            ).action_create_invoice()

        invoice = self._invoice(operation)
        self.assertTrue(invoice)

        again = self.wizard_model.create(
            {
                "field_operation_id": operation.id,
                "partner_id": self.partner.id,
                "service_price": 100.0,
            }
        )
        with self.assertRaises(UserError):
            again.action_create_invoice()
        self.assertEqual(self._invoice_count_for(operation), 1)

    def test_03_cancelling_the_invoice_keeps_the_link(self):
        """Cancelling does not detach the service: the paper trail stays visible.

        The review found an ``action_cancel`` override that never ran (Odoo owns
        ``button_cancel``, not ``action_cancel``); the behaviour is now deliberate.
        """
        operation = self._operation()
        invoice = self._invoice(operation)
        invoice.button_cancel()

        self.assertEqual(invoice.state, "cancel")
        self.assertEqual(operation.account_move_id, invoice)
        self.assertEqual(operation.invoicing, "billed")

    def test_04_deleting_the_invoice_clears_the_link(self):
        """Deleting a draft invoice lets the ORM clear the service link (set null)."""
        operation = self._operation()
        invoice = self._invoice(operation)
        invoice.unlink()
        self.assertFalse(operation.account_move_id)
        self.assertEqual(operation.invoicing, "not_billed")
        self.assertEqual(operation.invoice_count, 0)

    def test_05_bulk_wizard_consolidates_and_guards(self):
        """One consolidated invoice for several services of one customer."""
        first = self._operation("Bulk 1", price=10.0)
        second = self._operation("Bulk 2", price=20.0)
        operations = first + second

        wizard = self.bulk_model.with_context(active_ids=operations.ids).create({})
        self.assertEqual(wizard.operation_count, 2)
        self.assertEqual(len(wizard.line_ids), 2)
        self.assertEqual(wizard.partner_id, self.partner)

        invoice = self.env["account.move"].browse(
            wizard.action_create_invoice()["res_id"]
        )
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        self.assertEqual(invoice.amount_total, 30.0)
        self.assertEqual(
            invoice.invoice_line_ids.mapped("field_operation_id"), operations
        )
        self.assertEqual(first.account_move_id, invoice)
        self.assertEqual(second.account_move_id, invoice)
        self.assertEqual(invoice.field_operation_invoice_count, 2)

    def test_06_bulk_wizard_refuses_what_it_cannot_group(self):
        """Another customer, an unfinished service, an invoiced one: all refused."""
        first = self._operation("Group 1")
        with self.assertRaises(UserError):
            self.bulk_model.with_context(
                active_ids=(
                    first + self._operation("X", partner=self.other_partner)
                ).ids
            ).create({})
        with self.assertRaises(UserError):
            self.bulk_model.with_context(
                active_ids=(self._operation("Draft", status="planned")).ids
            ).create({})

        self._invoice(first)
        with self.assertRaises(UserError):
            self.bulk_model.with_context(active_ids=first.ids).create({})

        # no customer on the wizard: nothing to invoice
        live = self._operation("Group 2")
        no_customer = self.bulk_model.with_context(active_ids=live.ids).create(
            {"partner_id": False}
        )
        with self.assertRaises(UserError):
            no_customer.action_create_invoice()

    def test_07_stale_bulk_wizard_cannot_invoice_twice(self):
        """A wizard opened before somebody else invoiced must refuse to submit."""
        operation = self._operation()
        wizard = self.bulk_model.with_context(active_ids=operation.ids).create({})

        # somebody else invoices the same service while the form is open
        invoice = self._invoice(operation)
        self.assertEqual(operation.account_move_id, invoice)

        with self.assertRaises(UserError):
            wizard.action_create_invoice()
        self.assertEqual(self._invoice_count_for(operation), 1)
        self.assertEqual(operation.account_move_id, invoice)

    def test_08_payment_is_manual_and_not_derived(self):
        """``payment`` stays a hand-held field, documented as such."""
        operation = self._operation()
        self._invoice(operation)
        self.assertFalse(
            operation.payment,
            "invoicing must not invent a payment status: the invoice owns that value",
        )
        operation.payment = "paid"
        self.assertEqual(operation.payment, "paid")
        self.assertIn("synchronised", operation._fields["payment"].help or "")
