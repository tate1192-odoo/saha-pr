"""Drop the removed battery telemetry columns.

The battery level only ever fed a label on the multi-location map: the browser
API behind it (``navigator.getBattery()``) is unavailable on most phones in the
field, so what reached the database was a constant. The ORM stops reading and
writing the field in 19.0.1.8.0 and would leave the column behind for ever, so
it is dropped here. ``DROP COLUMN`` only touches the catalog; the history table
(which can hold hundreds of thousands of rows) is not rewritten.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

COLUMNS = (
    ("field_operation_team", "battery_level"),
    ("team_location_history", "battery_level"),
)


def migrate(cr, version):
    if not version:
        return
    for table, column in COLUMNS:
        cr.execute(
            sql.SQL("ALTER TABLE {} DROP COLUMN IF EXISTS {}").format(
                sql.Identifier(table), sql.Identifier(column)
            )
        )
        _logger.info("field_operation_geolocation: dropped %s.%s", table, column)
