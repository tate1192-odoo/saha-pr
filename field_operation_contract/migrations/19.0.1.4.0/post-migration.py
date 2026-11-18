"""Normalise the recurring anchor of the contracts already in the database.

Issue #54, item 3: a contract whose ``last_date_processed`` holds a service
date instead of a period end moves its service day on the first generation run
(FOC/00005: the 7th becomes the 8th). ``recurring_next_date`` is the plan, so
the anchor is moved to ``next - 1 day`` -- no document is generated here.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    total = 0
    for model_name in ("field.operation.contract", "field.operation.contract.line"):
        records = env[model_name].search([("recurring_next_date", "!=", False)])
        moved = records._normalize_recurring_anchor()
        _logger.info(
            "%s: anchor normalised on %s of %s records", model_name, moved, len(records)
        )
        total += moved
    _logger.info("recurring anchor: %s records moved in total", total)
