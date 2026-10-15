import logging

_logger = logging.getLogger(__name__)


def set_default_map_settings(env):
    """Assign the default map settings to existing users after module install."""
    _logger.info("Assigning default map settings to existing users...")

    default_map = env["maps.website"].search(
        [
            ("provider_type", "=", "openstreetmap"),
            ("active", "=", True),
        ],
        limit=1,
    ) or env["maps.website"].search([("active", "=", True)], limit=1)

    if not default_map:
        _logger.warning("No default map found; users will not be updated.")
        return

    default_route = (
        env["maps.website"].search(
            [
                ("provider_type", "=", "openstreetmap"),
                ("route_lat_lon_url", "!=", False),
                ("active", "=", True),
            ],
            limit=1,
        )
        or default_map
    )

    users_to_update = env["res.users"].search(
        [
            "|",
            "|",
            ("map_website_id", "=", False),
            ("multi_locations_map_website_id", "=", False),
            ("route_map_website_id", "=", False),
        ]
    )

    for user in users_to_update:
        vals = {}
        if not user.map_website_id:
            vals["map_website_id"] = default_map.id
        if not user.multi_locations_map_website_id:
            vals["multi_locations_map_website_id"] = default_map.id
        if not user.route_map_website_id:
            vals["route_map_website_id"] = default_route.id

        if vals:
            # sudo(): the hook runs during install and must seed the map
            # preferences of every existing user regardless of their groups.
            user.sudo().write(vals)
            _logger.info("Updated user %s: %s", user.login, vals)

    _logger.info("Updated %d users in total.", len(users_to_update))
