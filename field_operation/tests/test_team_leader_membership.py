"""A team leader is always a member of the team, also over RPC."""

from odoo.tests import TransactionCase, tagged


@tagged("field_operation", "post_install", "-at_install")
class TestTeamLeaderMembership(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Team = cls.env["field.operation.team"]
        office_group = cls.env.ref("field_operation.service_group_user")
        cls.leader = cls.env["res.users"].create(
            {
                "name": "Membership Leader",
                "login": "membership_leader@example.com",
                "group_ids": [(6, 0, [office_group.id])],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Membership Leader Employee", "user_id": cls.leader.id}
        )

    def test_create_adds_the_leader_to_the_members(self):
        team = self.Team.create(
            {"name": "Leader Only", "team_leader_id": self.leader.id}
        )
        self.assertIn(self.employee, team.team_members_ids)

    def test_write_leader_adds_the_employee_to_the_members(self):
        team = self.Team.create({"name": "Leader Write"})
        team.write({"team_leader_id": self.leader.id})
        self.assertIn(self.employee, team.team_members_ids)

    def test_members_write_keeps_the_leader(self):
        team = self.Team.create(
            {"name": "Members Keep", "team_leader_id": self.leader.id}
        )
        other = self.env["hr.employee"].create({"name": "Some Other Employee"})
        team.write({"team_members_ids": [(6, 0, [other.id])]})
        self.assertIn(self.employee, team.team_members_ids)
        self.assertIn(other, team.team_members_ids)

    def test_multi_team_write_keeps_the_shared_leader(self):
        """Two teams led by the same user: the leader stays a member in both.

        The leader employee is derived from the single leader of the batch, so
        a shared member list that drops it must get it back on every record.
        """
        other = self.env["hr.employee"].create({"name": "Shared Leader Other"})
        first = self.Team.create(
            {"name": "Shared Leader A", "team_leader_id": self.leader.id}
        )
        second = self.Team.create(
            {"name": "Shared Leader B", "team_leader_id": self.leader.id}
        )

        (first + second).write({"team_members_ids": [(6, 0, [other.id])]})

        for team in first + second:
            self.assertIn(self.employee, team.team_members_ids)
            self.assertIn(other, team.team_members_ids)
