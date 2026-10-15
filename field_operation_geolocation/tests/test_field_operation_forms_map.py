from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldOperationFormsMap(TransactionCase):
    """The map and geolocation features this module exposes on the form model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Forms = cls.env["field.operation.forms"]
        cls.provider = cls.env["maps.website"].search([], limit=1)
        cls.env.user.map_website_id = cls.provider
        cls.address = cls.env["res.partner"].create(
            {
                "name": "Forms Map Address",
                "partner_latitude": 41.0082,
                "partner_longitude": 28.9784,
            }
        )
        cls.form = cls.Forms.create(cls._form_vals(address_id=cls.address.id))

    @classmethod
    def _form_vals(cls, **overrides):
        """Vals for a form record, plus the picking type when the suite adds it.

        ``picking_type_id`` is required by ``field_operation_pest`` when that
        module is installed, and the very same test suite runs in databases
        where it (and ``stock``) is not.
        """
        vals = dict(overrides)
        if "picking_type_id" in cls.Forms._fields:
            vals["picking_type_id"] = (
                cls.env["stock.picking.type"].search([], limit=1).id
            )
        return vals

    def _arch(self, xmlid, view_type):
        """The resolved arch of a view, the way the client asks for it."""
        view = self.env.ref(xmlid)
        views = self.Forms.get_views([(view.id, view_type)])
        return views["views"][view_type]["arch"]

    def test_the_map_url_carries_the_record_coordinates(self):
        """The action opens the provider URL with this record's coordinates."""
        result = self.form.action_open_map()
        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertEqual(result["target"], "new")
        self.assertIn("mlat=41.0082", result["url"])
        self.assertIn("mlon=28.9784", result["url"])
        for placeholder in ("{LATITUDE}", "{LONGITUDE}", "{API_KEY}"):
            self.assertNotIn(placeholder, result["url"])

    def test_the_key_placeholder_is_stripped_for_providers_without_a_key(self):
        """A provider that needs no API key must not get a key query parameter."""
        self.provider.write({"requires_api_key": False, "api_key": False})
        self.assertNotIn("key=", self.form.action_open_map()["url"])

    def test_a_pair_of_zeros_counts_as_missing_coordinates(self):
        """Both zeros mean "no coordinates": the ORM cannot tell them from NULL."""
        self.address.write({"partner_latitude": 0.0, "partner_longitude": 0.0})
        self.assertFalse(self.form.service_latitude)
        with self.assertRaises(UserError):
            self.form.action_open_map()

    def test_a_lone_zero_latitude_is_still_a_coordinate(self):
        """A latitude of exactly 0.0 is the equator, not a missing value."""
        self.address.write({"partner_latitude": 0.0, "partner_longitude": 28.9784})
        self.assertIn("mlat=0.0", self.form.action_open_map()["url"])

    def test_a_missing_map_provider_is_refused(self):
        """Without a provider preference the action stops with a clear message."""
        self.env.user.map_website_id = False
        with self.assertRaises(UserError):
            self.form.action_open_map()

    def test_the_coordinates_follow_the_address(self):
        """The stored coordinates are refreshed when the address coordinates change."""
        self.address.write({"partner_latitude": 40.0, "partner_longitude": 29.0})
        self.assertEqual(self.form.service_latitude, 40.0)
        self.assertEqual(self.form.service_longitude, 29.0)

    def test_geolocating_without_an_address_is_refused(self):
        """The geolocation action needs a service address."""
        form = self.Forms.create(self._form_vals(address_id=False))
        with self.assertRaises(UserError):
            form.action_geolocate_address()

    def test_geolocating_reports_a_missing_match_instead_of_success(self):
        """geo_localize reports "no match" without raising, so the action warns."""
        address = self.env["res.partner"].create(
            {"name": "Nowhere", "street": "Unknown street", "city": "Nowhere"}
        )
        form = self.Forms.create(self._form_vals(address_id=address.id))
        result = form.action_geolocate_address()
        self.assertEqual(result["params"]["type"], "warning")

    def test_geolocating_reports_success_when_the_address_was_located(self):
        """A located address writes the coordinates and returns a success notice."""
        address = self.env["res.partner"].create(
            {"name": "Locatable", "street": "Some street", "city": "Somewhere"}
        )
        form = self.Forms.create(self._form_vals(address_id=address.id))
        partner_model = type(self.env["res.partner"])
        with patch.object(
            partner_model, "_geo_localize", return_value=(41.0082, 28.9784)
        ):
            result = form.with_context(
                force_geo_localize=True
            ).action_geolocate_address()

        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual(address.partner_latitude, 41.0082)
        self.assertEqual(form.service_latitude, 41.0082)

    def test_the_buttons_are_in_the_forms_views(self):
        """The list gets the Open Maps button, the form the Map and Geolocate pair."""
        list_arch = self._arch(
            "field_operation_forms.field_operation_forms_list_view", "list"
        )
        form_arch = self._arch(
            "field_operation_forms.field_operation_forms_form_view", "form"
        )
        self.assertEqual(list_arch.count("action_open_map"), 1)
        self.assertEqual(form_arch.count("action_open_map"), 1)
        self.assertEqual(form_arch.count("action_geolocate_address"), 1)
        self.assertEqual(form_arch.count('name="button_box"'), 1)
