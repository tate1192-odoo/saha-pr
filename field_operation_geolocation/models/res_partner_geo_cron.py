import logging
import time
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Delay between two OpenStreetMap/Nominatim calls to stay under its rate limit.
# Kept as a constant to document the intent; time.sleep() blocks the worker
# thread for the whole loop.
GEO_LOCALIZE_RATE_LIMIT_SLEEP = 1.1

# A partner whose geolocation failed is only retried once this many days have
# passed, so the cron does not keep hammering the same unreachable partners.
GEO_LOCALIZE_RETRY_DAYS = 30


class ResPartner(models.Model):
    _inherit = "res.partner"

    geo_localize_attempted = fields.Datetime(
        string="Geolocation Last Attempt",
        help="Date and time of the last automatic geolocation attempt made by the "
        "company geolocation cron. A partner is retried only once this timestamp "
        "is older than the retry window.",
    )

    @api.model
    def action_cron_update_company_geolocations(self, limit=50):
        """Geolocate companies missing coordinates, oldest attempt first."""
        # Only partners never attempted, or last attempted outside the retry
        # window, are eligible. Without this guard the same first results would
        # be retried on every run and later partners would never be reached.
        retry_threshold = fields.Datetime.now() - timedelta(
            days=GEO_LOCALIZE_RETRY_DAYS
        )
        partners = self.search(
            [
                ("is_company", "=", True),
                "|",
                "|",
                ("partner_latitude", "=", False),
                ("partner_latitude", "=", 0.0),
                "|",
                ("partner_longitude", "=", False),
                ("partner_longitude", "=", 0.0),
                "|",
                ("geo_localize_attempted", "=", False),
                ("geo_localize_attempted", "<", retry_threshold),
            ],
            limit=limit,
            order="geo_localize_attempted asc, id",
        )

        if not partners:
            _logger.info("Company geolocation cron: nothing to process.")
            return True

        updated = 0
        skipped = 0

        for partner in partners:
            # Mark every selected partner as attempted, skipped ones included, so
            # they move to the back of the queue instead of starving it.
            partner.geo_localize_attempted = fields.Datetime.now()

            # street2 counts as well: some companies only have a second line.
            if not (partner.street or partner.street2 or partner.city):
                skipped += 1
                _logger.debug("Skipped (empty address): %s", partner.name)
                continue

            address_searched = " ".join(
                filter(None, [partner.street, partner.city, partner.country_id.name])
            )

            try:
                partner.geo_localize()

                if partner.partner_latitude:
                    updated += 1
                    _logger.info("Geolocated: %s -> %s", partner.name, address_searched)
                else:
                    _logger.warning(
                        "No match: %s (address searched: [%s])",
                        partner.name,
                        address_searched,
                    )

                time.sleep(GEO_LOCALIZE_RATE_LIMIT_SLEEP)

            except Exception as error:  # noqa: BLE001
                # Broad catch on purpose: one failing partner (network, geocoder,
                # bad encoding, ...) must not abort the whole cron run.
                _logger.error("Geolocation error for %s: %s", partner.name, error)
                continue

        _logger.info(
            "Company geolocation cron report: %s updated, %s empty address, "
            "%s not found or failed.",
            updated,
            skipped,
            len(partners) - updated - skipped,
        )
        return True
