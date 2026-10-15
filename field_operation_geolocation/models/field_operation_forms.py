from odoo import fields, models

from . import geo_helpers


class FieldOperationForms(models.Model):
    """Coordinates, map and geolocation actions for the service form model.

    The fields and the actions they feed used to live in
    ``field_operation_forms_ext`` as a copy of what this module already does for
    ``field.operation``; the logic now lives in ``geo_helpers`` (with the URL
    building in ``maps.website``) and is shared by both models.
    """

    _inherit = "field.operation.forms"

    service_latitude = fields.Float(
        string="Latitude",
        related="address_id.partner_latitude",
        store=True,
    )
    service_longitude = fields.Float(
        string="Longitude",
        related="address_id.partner_longitude",
        store=True,
    )

    def action_open_map(self):
        """Open this form's service coordinates in the user's map provider."""
        self.ensure_one()
        return geo_helpers.open_map_action(self)

    def action_geolocate_address(self):
        """Geolocate the service address and report what actually happened."""
        self.ensure_one()
        geo_helpers.geolocate_service_address(self)
        return geo_helpers.geolocation_notification(self)
