import logging
from typing import Any

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import geo_helpers

_logger = logging.getLogger(__name__)


class FieldOperation(models.Model):
    """Map, route and geolocation actions for the operation model.

    The shared parts live in ``geo_helpers`` because the service form model
    (``field.operation.forms``) offers the same two buttons.
    """

    _inherit = "field.operation"

    @api.onchange("address_id")
    def _onchange_address_id(self):
        warning = {}
        for operation in self:
            if not operation.address_id:
                continue
            # Skip when the operation already carries coordinates.
            if operation.service_latitude and operation.service_longitude:
                continue
            try:
                result = operation.address_id.geo_localize()
                if result:
                    operation.date_localization = fields.Datetime.now()
                    _logger.info(
                        "Geolocation successful for operation %s", operation.name
                    )
                else:
                    warning = {
                        "warning": {
                            "title": _("Location Not Found"),
                            "message": _(
                                "No geographic coordinates could be found "
                                "automatically for the selected address."
                            ),
                        }
                    }
            except UserError as error:
                _logger.warning(
                    "Geolocation failed for address %s: %s",
                    operation.address_id.id,
                    error,
                )
                warning = {
                    "warning": {
                        "title": _("Error"),
                        "message": _(
                            "An error occurred while retrieving the location: %s"
                        )
                        % error,
                    }
                }
        if warning:
            return warning
        return {}

    def action_open_map(self) -> dict[str, Any]:
        """Open this operation's coordinates in the user's map provider."""
        self.ensure_one()
        return geo_helpers.open_map_action(self)

    def action_show_multi_locations_mark(self) -> dict[str, Any]:
        if not self:
            raise UserError(_("No records selected."))

        maps_website = (
            self.env.user.multi_locations_map_website_id or self.env.user.map_website_id
        )
        if not maps_website:
            raise UserError(_("Please configure a Multi-Location Map Provider."))

        coordinates = []
        for record in self:
            if geo_helpers.has_coordinates(record):
                coordinates.append(
                    (
                        float(record.service_latitude),
                        float(record.service_longitude),
                        record.display_name or "",
                    )
                )

        if not coordinates:
            raise UserError(_("No valid coordinates found."))

        url = maps_website._get_multi_location_marker_url(coordinates)
        if not url:
            raise UserError(
                _("The selected map provider does not support multi-markers.")
            )

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_show_selected_routes(self) -> dict[str, Any]:
        if not self or len(self) < 2:
            raise UserError(
                _("Please select at least 2 operations for route planning.")
            )

        maps_website = self.env.user.route_map_website_id
        if not maps_website:
            raise UserError(_("Please configure a Route Map Provider."))

        start_record = self[0]
        end_record = self[-1]
        waypoint_records = self[1:-1] if len(self) > 2 else self.env["field.operation"]

        all_records = start_record | end_record | waypoint_records
        for rec in all_records:
            if not geo_helpers.has_coordinates(rec):
                raise UserError(
                    _("Missing coordinates for operation '%s'.") % rec.display_name
                )

        start_coords = geo_helpers.coordinates_or_error(start_record)
        end_coords = geo_helpers.coordinates_or_error(end_record)

        waypoints_coords = [
            f"{wp.service_latitude},{wp.service_longitude}" for wp in waypoint_records
        ]
        waypoints_coords.append(f"{end_coords['latitude']},{end_coords['longitude']}")

        url = maps_website._get_route_url(start_coords, waypoints_coords)

        if not url:
            raise UserError(_("Map provider does not support multi-point routing."))

        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_geolocate_operation(self):
        """Geolocate the service address and report what actually happened."""
        self.ensure_one()
        geo_helpers.geolocate_service_address(self)
        self.date_localization = fields.Datetime.now()
        return geo_helpers.geolocation_notification(self)
