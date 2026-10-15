from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldOperationContractor(TransactionCase):
    """Cover the contractor job model, sync flag, ACL and partner helpers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Contractor = cls.env["field.operation.contractor"]
        cls.Partner = cls.env["res.partner"]
        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "Contractor Manager",
                "login": "contractor_manager_test",
                "group_ids": [
                    (6, 0, [cls.env.ref("field_operation.service_group_manager").id]),
                ],
            }
        )
        cls.office_user = cls.env["res.users"].create(
            {
                "name": "Contractor Office User",
                "login": "contractor_office_test",
                "group_ids": [
                    (6, 0, [cls.env.ref("field_operation.service_group_user").id]),
                ],
            }
        )
        cls.partner = cls.Partner.create({"name": "Contractor Partner"})
        cls.other_partner = cls.Partner.create({"name": "Other Partner"})

    def _create_job(self, partner, name="Job"):
        """Create a contractor job owned by the current admin user."""
        return self.Contractor.create(
            {
                "name": name,
                "partner_id": partner.id,
                "user_id": self.env.user.id,
            }
        )

    def test_01_display_name_combines_partner_and_job(self):
        """A job with a partner and a name shows both, partner first."""
        job = self._create_job(self.partner, name="Fumigation")
        self.assertEqual(job.display_name, "Contractor Partner - Fumigation")

    def test_02_display_name_falls_back_to_partner(self):
        """With an empty job name the display name is the partner name."""
        job = self._create_job(self.partner, name="")
        self.assertEqual(job.display_name, self.partner.name)

    def test_03_display_name_empty_without_values(self):
        """With neither partner nor name the display name is empty."""
        job = self.Contractor.new({"name": ""})
        job._compute_display_name()
        self.assertEqual(job.display_name, "")

    def test_04_service_contractor_count_aggregates(self):
        """The count reflects every job of a partner, in one query."""
        self._create_job(self.partner, name="A")
        self._create_job(self.partner, name="B")
        self._create_job(self.other_partner, name="C")
        self.partner.invalidate_recordset()
        self.other_partner.invalidate_recordset()
        self.assertEqual(self.partner.service_contractor_count, 2)
        self.assertEqual(self.other_partner.service_contractor_count, 1)

    def test_05_service_contractor_count_zero(self):
        """A partner without any job counts zero."""
        self.partner.invalidate_recordset()
        self.assertEqual(self.partner.service_contractor_count, 0)

    def test_06_create_sets_contractor_flag(self):
        """Creating a job flags its partner as a contractor."""
        self._create_job(self.partner)
        self.partner.invalidate_recordset()
        self.assertTrue(self.partner.is_contractor)

    def test_07_reassign_clears_old_partner_flag(self):
        """Moving the only job away clears the previous partner flag."""
        job = self._create_job(self.partner)
        job.write({"partner_id": self.other_partner.id})
        self.partner.invalidate_recordset()
        self.other_partner.invalidate_recordset()
        self.assertFalse(self.partner.is_contractor)
        self.assertTrue(self.other_partner.is_contractor)

    def test_08_reassign_keeps_flag_when_other_job_exists(self):
        """A partner that still owns another job keeps the flag."""
        self._create_job(self.partner, name="Keep")
        job = self._create_job(self.partner, name="Move")
        job.write({"partner_id": self.other_partner.id})
        self.partner.invalidate_recordset()
        self.assertTrue(self.partner.is_contractor)

    def test_09_unlink_clears_flag(self):
        """Deleting the last job clears the partner flag."""
        job = self._create_job(self.partner)
        job.unlink()
        self.partner.invalidate_recordset()
        self.assertFalse(self.partner.is_contractor)

    def test_10_manager_can_unlink(self):
        """A manager is allowed to delete a contractor job."""
        job = self._create_job(self.partner)
        job.with_user(self.manager_user).unlink()
        self.assertFalse(self.Contractor.search([("id", "=", job.id)]))

    def test_11_office_user_cannot_unlink(self):
        """An office user is denied the unlink operation."""
        job = self._create_job(self.partner)
        with self.assertRaises(AccessError):
            job.with_user(self.office_user).unlink()

    def test_12_both_groups_can_read_and_write(self):
        """Both the office user and the manager may read and write jobs."""
        job = self._create_job(self.partner)
        job.with_user(self.office_user).write({"name": "Office Edit"})
        job.with_user(self.manager_user).write({"name": "Manager Edit"})
        self.assertEqual(job.with_user(self.office_user).name, "Manager Edit")

    def test_13_show_service_contractor_action(self):
        """The smart button action targets the jobs of one partner."""
        action = self.partner.show_service_contractor()
        self.assertEqual(action["res_model"], "field.operation.contractor")
        self.assertEqual(action["domain"], [("partner_id", "=", self.partner.id)])
        self.assertEqual(action["context"], {"default_partner_id": self.partner.id})

    def test_14_show_service_contractor_requires_singleton(self):
        """Calling the action on several partners raises an error."""
        partners = self.partner | self.other_partner
        self.assertEqual(len(partners), 2)
        with self.assertRaises(ValueError):
            partners.show_service_contractor()

    def test_15_operation_onchange_fills_contractor(self):
        """Selecting a contractor partner fills the operation contractor."""
        job = self._create_job(self.partner)
        self.partner.write({"service_contractor_id": job.id})
        operation = self.env["field.operation"].new({})
        operation.partner_id = self.partner
        operation._onchange_partner_id()
        self.assertEqual(operation.contractor_id, job)

    def test_16_action_view_customers(self):
        """The customers action filters by the job and pre-fills the link."""
        job = self._create_job(self.partner)
        action = job.action_view_customers()
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["domain"], [("service_contractor_id", "=", job.id)])
        self.assertEqual(
            action["context"],
            {"default_service_contractor_id": job.id},
        )
