from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MapsWebsite(models.Model):
    _name = "maps.website"
    _description = "Map Website"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(string="Sequence", default=10)
    website_url = fields.Char(string="Provider Website")
    requires_api_key = fields.Boolean(string="Requires API Key")
    api_key = fields.Char(string="API Key", password=True, help="Provider API Key")
    lat_lon_url = fields.Char(string="Latitude/Longitude URL", required=True)
    route_lat_lon_url = fields.Char(string="Route Latitude/Longitude URL")
    provider_type = fields.Selection(
        [
            ("google", "Google Maps"),
            ("openstreetmap", "OpenStreetMap"),
            ("bing", "Bing Maps"),
            ("here", "Here Maps"),
            ("mapbox", "Mapbox"),
            ("other", "Other"),
        ],
        string="Provider Type",
        default="other",
    )

    @api.constrains("lat_lon_url", "route_lat_lon_url")
    def _check_url_placeholders(self):
        """Check that the configured URLs carry the expected placeholders."""
        for record in self:
            if record.lat_lon_url and (
                "{LATITUDE}" not in record.lat_lon_url
                or "{LONGITUDE}" not in record.lat_lon_url
            ):
                raise ValidationError(
                    _("Lat/Lon URL must contain {LATITUDE} and {LONGITUDE}")
                )

            if record.route_lat_lon_url:
                required = [
                    "{START_LATITUDE}",
                    "{START_LONGITUDE}",
                    "{DEST_LATITUDE}",
                    "{DEST_LONGITUDE}",
                ]
                if not all(
                    placeholder in record.route_lat_lon_url for placeholder in required
                ):
                    raise ValidationError(
                        _("Route Lat/Lon URL must contain required placeholders")
                    )

    @api.depends("name", "active")
    def _compute_display_name(self):
        for record in self:
            name = record.name
            if not record.active:
                name = f"{name} (Inactive)"
            record.display_name = name

    def _get_osm_multi_url(self, coordinates: list[tuple[float, float, str]]) -> str:
        """Generate OpenStreetMap multi-marker URL using GraphHopper."""
        self.ensure_one()
        if not coordinates:
            return False

        params = [f"point={lat},{lon}" for lat, lon, name in coordinates]
        params.append("layer=Omniscale")
        return "https://graphhopper.com/maps/?" + "&".join(params)

    def _get_google_multi_url(self, coordinates: list[tuple[float, float, str]]) -> str:
        """Generate Google Maps multi-marker URL."""
        self.ensure_one()
        if not coordinates:
            return False

        # The directions format is used as a fallback for multiple points.
        parts = [f"{lat},{lon}" for lat, lon, name in coordinates]
        return "https://www.google.com/maps/dir/" + "/".join(parts)

    def _get_lat_lon_url(self, latitude: float, longitude: float) -> str:
        """Generate the single-point URL, with the API key slot resolved.

        Follows the convention of the other builders here: return ``False`` when
        this provider has no single-point URL, and let the caller report it.
        """
        self.ensure_one()
        if not self.lat_lon_url:
            return False
        url = self.lat_lon_url.replace("{LATITUDE}", str(latitude))
        url = url.replace("{LONGITUDE}", str(longitude))
        # The template carries a {API_KEY} slot only for the providers that need
        # one; strip it otherwise so it never reaches the browser.
        if self.requires_api_key and self.api_key:
            url = url.replace("{API_KEY}", self.api_key)
        else:
            url = url.replace("&key={API_KEY}", "").replace("?key={API_KEY}", "")
        return url

    def _get_multi_location_marker_url(
        self, coordinates: list[tuple[float, float, str]]
    ) -> str:
        """Generate multi-marker URL based on provider type."""
        self.ensure_one()
        if self.provider_type == "openstreetmap":
            return self._get_osm_multi_url(coordinates)
        if self.provider_type == "google":
            return self._get_google_multi_url(coordinates)
        if self.provider_type == "bing":
            # Bing format: pos.lat_lon~pos.lat_lon
            points = [f"pos.{lat}_{lon}" for lat, lon, name in coordinates]
            return (
                f"https://www.bing.com/maps?rtp={'~'.join(points)}" if points else False
            )
        if self.provider_type == "here":
            points = [f"{lat},{lon}" for lat, lon, name in coordinates]
            return (
                "https://www.here.com/search/" + "/".join(points) if points else False
            )
        return self._get_osm_multi_url(coordinates)

    def _get_route_url(
        self, start_coords: dict[str, float], waypoints: list[str]
    ) -> str:
        """Generate route URL based on provider type."""
        self.ensure_one()
        if not start_coords or not waypoints:
            return False

        start_lat = start_coords.get("latitude")
        start_lon = start_coords.get("longitude")

        if self.provider_type == "openstreetmap":
            base_url = "https://graphhopper.com/maps/?"
            params = []
            if start_lat and start_lon:
                params.append(f"point={start_lat},{start_lon}")
            params.extend(f"point={wp}" for wp in waypoints)
            params.append("vehicle=car")
            return base_url + "&".join(params) if len(params) > 1 else False

        if self.provider_type == "google":
            base_url = "https://www.google.com/maps/dir/"
            parts = []
            if start_lat and start_lon:
                parts.append(f"{start_lat},{start_lon}")
            parts.extend(waypoints)
            return base_url + "/".join(parts) if len(parts) > 1 else False

        if self.provider_type == "bing":
            base_url = "https://www.bing.com/maps/directions?"
            rtp_parts = []
            if start_lat and start_lon:
                rtp_parts.append(f"pos.{start_lat}_{start_lon}")
            rtp_parts.extend(f"pos.{wp.replace(',', '_')}" for wp in waypoints)
            return (
                f"{base_url}rtp={'~'.join(rtp_parts)}" if len(rtp_parts) > 1 else False
            )

        # Route URLs are only defined for the providers handled above.
        return False
