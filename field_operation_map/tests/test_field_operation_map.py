from odoo.tests.common import TransactionCase, tagged

from odoo.addons.field_operation_map.hooks import uninstall_hook


@tagged("post_install", "-at_install")
class TestFieldOperationMap(TransactionCase):
    """Regression tests for the map view, address field and uninstall hook."""

    def test_display_address_reflects_partner_address(self):
        """display_address mirrors the formatted address and is falsy without one."""
        partner = self.env["res.partner"].create({"name": "Map Test Partner"})
        operation = self.env["field.operation"].create({"address_id": partner.id})
        self.assertEqual(
            operation.display_address,
            partner._display_address(without_company=True),
        )

        operation_without_address = self.env["field.operation"].create(
            {
                "address_id": False,
            }
        )
        self.assertFalse(operation_without_address.display_address)

    def test_map_view_and_action_view_record(self):
        """The leaflet_map view and its act_window.view record are wired up."""
        view = self.env.ref("field_operation_map.view_field_operation_map")
        self.assertEqual(view.type, "leaflet_map")

        act_view = self.env.ref("field_operation_map.action_field_operation_map_view")
        self.assertEqual(act_view.view_mode, "leaflet_map")
        self.assertEqual(act_view.sequence, 8)
        self.assertEqual(act_view.view_id, view)
        self.assertEqual(
            act_view.act_window_id,
            self.env.ref("field_operation.action_field_operation"),
        )

    def test_action_view_mode_includes_leaflet_map(self):
        """The base field.operation action exposes the leaflet_map view mode."""
        action = self.env.ref("field_operation.action_field_operation")
        modes = [mode.strip() for mode in action.view_mode.split(",")]
        self.assertIn("leaflet_map", modes)

    def test_the_mode_is_appended_without_dropping_the_others(self):
        """The mode is appended, never written as a whole string.

        A data record listing ``view_mode`` replaces it, and three modules write
        that action: the last one to update used to drop the others' modes
        (measured with field_operation_gantt).
        """
        action = self.env.ref("field_operation.action_field_operation")
        action.view_mode = "list,kanban,form,calendar,graph,pivot,activity"
        self.env["ir.actions.act_window"]._add_field_operation_map_view_mode()
        self.assertEqual(
            action.view_mode.split(","),
            [
                "list",
                "kanban",
                "form",
                "calendar",
                "graph",
                "pivot",
                "activity",
                "leaflet_map",
            ],
            "the core and sibling modes must survive, the map appended",
        )

    def test_the_mode_is_restored_after_a_sibling_rewrote_the_string(self):
        """Whatever a sibling module left behind, the map comes back."""
        action = self.env.ref("field_operation.action_field_operation")
        action.view_mode = "list,kanban,form,calendar,gantt_soft,graph,pivot,activity"
        self.env["ir.actions.act_window"]._add_field_operation_map_view_mode()
        modes = action.view_mode.split(",")
        self.assertIn("leaflet_map", modes)
        self.assertIn("gantt_soft", modes, "the sibling's mode must not be dropped")

    def test_the_mode_is_appended_once(self):
        """The function runs on every update of this module: it must be idempotent."""
        action = self.env.ref("field_operation.action_field_operation")
        self.env["ir.actions.act_window"]._add_field_operation_map_view_mode()
        once = action.view_mode
        self.env["ir.actions.act_window"]._add_field_operation_map_view_mode()
        self.assertEqual(action.view_mode, once)
        self.assertEqual(action.view_mode.count("leaflet_map"), 1)

    def test_uninstall_hook_removes_only_leaflet_map(self):
        """The hook strips leaflet_map from the base action only, and is idempotent."""
        action = self.env.ref("field_operation.action_field_operation")
        other_modes = [
            mode.strip()
            for mode in action.view_mode.split(",")
            if mode.strip() != "leaflet_map"
        ]
        self.assertTrue(other_modes)

        unrelated = self.env["ir.actions.act_window"].create(
            {
                "name": "Unrelated Leaflet Action",
                "res_model": "field.operation",
                "view_mode": "list,leaflet_map",
            }
        )

        uninstall_hook(self.env)

        modes_after = [mode.strip() for mode in action.view_mode.split(",")]
        self.assertNotIn("leaflet_map", modes_after)
        self.assertEqual(modes_after, other_modes)

        # The unrelated action must survive untouched: the hook no longer deletes
        # arbitrary actions that merely use the leaflet_map view mode.
        self.assertTrue(unrelated.exists())
        self.assertIn(
            "leaflet_map",
            [mode.strip() for mode in unrelated.view_mode.split(",")],
        )

        # A second call is a no-op and must not raise or change anything.
        uninstall_hook(self.env)
        self.assertEqual(
            [mode.strip() for mode in action.view_mode.split(",")],
            other_modes,
        )
        self.assertTrue(unrelated.exists())
