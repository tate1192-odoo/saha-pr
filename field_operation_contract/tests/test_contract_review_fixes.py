# tests/test_contract_review_fixes.py

# Copyright 2024 Softteknik Bilişim
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date

from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import HttpCase, TransactionCase, tagged


class ContractReviewFixCase(TransactionCase):
    """Shared fixtures for the review-fix regression tests."""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Contract Review Customer",
            }
        )
        self.service_type = self.env["field.operation.type"].create(
            {
                "name": "Maintenance",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Maintenance Service",
                "type": "service",
                "lst_price": 1000.0,
                "service_type_id": self.service_type.id,
            }
        )
        self.sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_types": "contract",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 2,
                            "price_unit": 1000,
                        }
                    ),
                ],
            }
        )

    def _create_contract(self, **overrides):
        vals = {
            "partner_id": self.partner.id,
            "date_start": date(2024, 1, 1),
            "service_type_ids": [Command.set(self.service_type.ids)],
        }
        vals.update(overrides)
        return self.env["field.operation.contract"].create(vals)

    def _add_line(self, contract, **overrides):
        vals = {
            "contract_id": contract.id,
            "product_id": self.product.id,
            "service_type_id": self.service_type.id,
            "total_service": 12,
            "price_unit": 1000,
            "date_start": date(2024, 1, 1),
        }
        vals.update(overrides)
        return self.env["field.operation.contract.line"].create(vals)

    def _create_confirmed_header_contract(self, **overrides):
        """A confirmed contract in header recurrence mode (line_recurrence=False)."""
        vals = {
            "recurring_rule_type": "monthly",
            "recurring_interval": 1,
            "recurring_generation_type": "beginning",
            "recurring_offset": 0,
        }
        vals.update(overrides)
        contract = self._create_contract(**vals)
        self._add_line(contract)
        contract.action_confirm()
        contract.invalidate_recordset()
        return contract

    def _create_non_manager_user(self):
        """Internal user holding field_operation.service_group_user only."""
        group_user = self.env.ref("field_operation.service_group_user")
        return self.env["res.users"].create(
            {
                "name": "Non Manager Office User",
                "login": "non_manager_contract_user",
                "email": "non_manager_contract_user@example.com",
                "group_ids": [Command.set(group_user.ids)],
            }
        )

    def _make_wizard(self, sale_order=None):
        sale_order = sale_order or self.sale_order
        return (
            self.env["sale.order.contract.wizard"]
            .with_context(
                active_id=sale_order.id,
                active_model="sale.order",
            )
            .create({})
        )


class TestHeaderRecurrenceFixes(ContractReviewFixCase):
    """P0 - header recurrence must advance by a whole period, and idempotently."""

    @freeze_time("2024-01-01")
    def test_header_recurrence_next_date_is_next_period_start(self):
        """Header mode must set recurring_next_date to the next period start."""
        contract = self._create_confirmed_header_contract()

        self.env["field.operation.contract"].action_recurring_process()
        contract.invalidate_recordset()

        self.assertEqual(len(contract.generated_sale_ids), 1)
        self.assertEqual(len(contract.generated_operation_ids), 1)
        self.assertEqual(contract.recurring_next_date, date(2024, 2, 1))

    @freeze_time("2024-01-01")
    def test_second_same_day_run_is_idempotent(self):
        """Running the recurring process twice the same day must not duplicate."""
        contract = self._create_confirmed_header_contract()
        Contract = self.env["field.operation.contract"]

        Contract.action_recurring_process()
        contract.invalidate_recordset()
        sales_after_first = len(contract.generated_sale_ids)
        ops_after_first = len(contract.generated_operation_ids)
        self.assertEqual(sales_after_first, 1)
        self.assertEqual(ops_after_first, 1)

        Contract.action_recurring_process()
        contract.invalidate_recordset()

        self.assertEqual(len(contract.generated_sale_ids), sales_after_first)
        self.assertEqual(len(contract.generated_operation_ids), ops_after_first)


class TestRecurrenceConstraints(ContractReviewFixCase):
    """P1 - interval guard and safe period calculation."""

    def test_recurring_interval_zero_raises_validation_error(self):
        """recurring_interval=0 must be rejected at create time."""
        with self.assertRaises(ValidationError):
            self._create_contract(recurring_interval=0)

    def test_get_period_end_date_returns_sane_period_end(self):
        """interval=1 must terminate and return the period end (no infinite loop)."""
        contract = self._create_contract()
        line = self._add_line(
            contract,
            date_start=date(2024, 1, 1),
            recurring_rule_type="monthly",
            recurring_interval=1,
        )
        period_end = line._get_period_end_date(date(2024, 1, 15))
        self.assertEqual(period_end, date(2024, 1, 31))


class TestRecurringNextDateCompute(ContractReviewFixCase):
    """P1 - recurring_next_date must follow remaining_count through compute."""

    def test_recurring_next_date_false_when_remaining_count_zero(self):
        """When remaining_count drops to 0, recurring_next_date becomes False."""
        contract = self._create_contract()
        line = self._add_line(
            contract,
            total_service=2,
            recurring_rule_type="monthly",
            recurring_interval=1,
            recurring_next_date=date(2024, 1, 1),
            date_start=date(2024, 1, 1),
        )
        line.flush_recordset()
        self.env.invalidate_all()
        self.assertEqual(line.remaining_count, 2)
        self.assertEqual(line.recurring_next_date, date(2024, 1, 1))

        line.generated_occurrences = 2
        line.flush_recordset()
        self.env.invalidate_all()

        self.assertEqual(line.remaining_count, 0)
        self.assertFalse(line.recurring_next_date)


class TestContractLifecycleGuards(ContractReviewFixCase):
    """P1 - unlink guard, cancel propagation, state machine and access rights."""

    @freeze_time("2024-01-01")
    def test_unlink_blocked_when_sale_orders_linked(self):
        """A contract with linked sale orders must not be deletable."""
        contract = self._create_confirmed_header_contract()
        self.env["field.operation.contract"]._recurring_create_sale_ops(
            contract, date(2024, 1, 1)
        )
        contract.invalidate_recordset()
        self.assertTrue(contract.generated_sale_ids)

        with self.assertRaises(UserError):
            contract.unlink()

    @freeze_time("2024-01-01")
    def test_cancel_cancels_linked_draft_records(self):
        """Cancelling a contract must cancel its draft sales and operations."""
        contract = self._create_confirmed_header_contract()
        self.env["field.operation.contract"]._recurring_create_sale_ops(
            contract, date(2024, 1, 1)
        )
        contract.invalidate_recordset()
        self.assertTrue(contract.generated_sale_ids)
        self.assertTrue(contract.generated_operation_ids)

        contract.action_cancel()
        contract.invalidate_recordset()

        self.assertEqual(set(contract.generated_sale_ids.mapped("state")), {"cancel"})
        self.assertEqual(
            set(contract.generated_operation_ids.mapped("status")), {"cancel"}
        )

    def test_non_manager_cannot_run_recurring_process(self):
        """A plain office user must not trigger the recurring generation."""
        user = self._create_non_manager_user()
        with self.assertRaises(AccessError):
            self.env["field.operation.contract"].with_user(
                user
            ).action_recurring_process()

    def test_user_without_service_group_cannot_confirm_contract(self):
        """A user outside the field-operation groups must not confirm a contract."""
        user = self.env["res.users"].create(
            {
                "name": "Plain Office User",
                "login": "plain_office_user",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        contract = self._create_contract()
        self._add_line(contract)

        with self.assertRaises(AccessError):
            contract.with_user(user).action_confirm()

    def test_non_manager_service_user_can_confirm_contract(self):
        """Office users run the workflow; only generation is manager-only."""
        user = self._create_non_manager_user()
        contract = self._create_contract()
        self._add_line(contract)

        contract.with_user(user).action_confirm()

        self.assertEqual(contract.state, "confirmed")

    def test_confirm_on_non_draft_contract_raises(self):
        """Confirming an already confirmed contract must raise."""
        contract = self._create_contract()
        self._add_line(contract)
        contract.action_confirm()
        self.assertEqual(contract.state, "confirmed")

        with self.assertRaises(UserError):
            contract.action_confirm()


class TestWizardGuards(ContractReviewFixCase):
    """P1 - wizard duplicate guard and single-period propagation."""

    def test_wizard_cannot_convert_sale_order_twice(self):
        """Converting the same sale order to a contract twice must fail."""
        wizard = self._make_wizard()
        wizard.action_create_contract()

        with self.assertRaises(UserError):
            wizard.action_create_contract()

    def test_wizard_propagates_single_rule_to_header(self):
        """A weekly-only sale order must yield a weekly header contract."""
        wizard = self._make_wizard()
        wizard.line_ids.filtered(lambda line: not line.display_type).write(
            {"recurring_rule_type": "weekly"}
        )

        action = wizard.action_create_contract()
        contract = self.env["field.operation.contract"].browse(action["res_id"])

        self.assertFalse(contract.line_recurrence)
        self.assertEqual(contract.recurring_rule_type, "weekly")


class TestSignatureAndSchemaCleanup(ContractReviewFixCase):
    """P1/P2 - signature integrity, removed state and removed field."""

    def test_signature_status_requires_proof(self):
        """signature_status=True without file/name/date must be rejected."""
        with self.assertRaises(ValidationError):
            self._create_contract(signature_status=True)

    def test_to_renew_state_removed(self):
        """The dead 'to_renew' state must no longer be part of the selection."""
        selection = dict(
            self.env["field.operation.contract"]._fields["state"].selection
        )
        self.assertNotIn("to_renew", selection)

    def test_unit_price_field_removed(self):
        """The unused 'unit_price' field must no longer exist on the model."""
        self.assertNotIn("unit_price", self.env["field.operation.contract"]._fields)


@tagged("post_install", "-at_install")
class TestContractPortalPdf(HttpCase):
    """P1 - the portal PDF endpoint must answer 200, not 500."""

    def test_portal_contract_pdf_returns_200(self):
        report = self.env.ref(
            "field_operation_contract.action_field_operation_contract_pdf"
        )
        self.assertTrue(report)

        portal_group = self.env.ref("base.group_portal")
        portal_user = self.env["res.users"].create(
            {
                "name": "Portal Contract Reader",
                "login": "portal_contract_reader",
                "email": "portal_contract_reader@example.com",
                "group_ids": [Command.set(portal_group.ids)],
            }
        )
        partner = portal_user.partner_id

        service_type = self.env["field.operation.type"].create(
            {
                "name": "Portal Maintenance",
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Portal Service",
                "type": "service",
                "lst_price": 100.0,
                "service_type_id": service_type.id,
            }
        )
        contract = self.env["field.operation.contract"].create(
            {
                "partner_id": partner.id,
                "date_start": date(2024, 1, 1),
                "date_end": date(2024, 12, 31),
                "service_type_ids": [Command.set(service_type.ids)],
            }
        )
        self.env["field.operation.contract.line"].create(
            {
                "contract_id": contract.id,
                "product_id": product.id,
                "total_service": 12,
                "price_unit": 100,
                "date_start": date(2024, 1, 1),
            }
        )
        token = contract._portal_ensure_token()

        self.authenticate("portal_contract_reader", "portal_contract_reader")
        response = self.url_open(f"/my/contract/{contract.id}/pdf?access_token={token}")
        self.assertEqual(response.status_code, 200)
