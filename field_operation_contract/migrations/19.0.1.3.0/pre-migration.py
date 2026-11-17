"""Report duplicate periodic documents before the uniqueness constraints land.

Nothing is deleted: the query results are only written to the log so the
operator can review them. The generation itself is idempotent (a matching
operation/order is skipped), so a clean report is not a precondition for the
upgrade.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT service_contract_id, partner_shipping_id, date_order::date, count(*)
          FROM sale_order
         WHERE service_contract_id IS NOT NULL
           AND order_types IN ('invoice', 'service')
         GROUP BY 1, 2, 3
        HAVING count(*) > 1
         ORDER BY 4 DESC
         LIMIT 20
        """
    )
    duplicates = cr.fetchall()
    if duplicates:
        _logger.warning(
            "field_operation_contract: %s duplicated periodic order group(s) "
            "found (contract, location, date, count): %s",
            len(duplicates),
            duplicates,
        )
    else:
        _logger.info(
            "field_operation_contract: no duplicated periodic sale orders found."
        )

    cr.execute(
        """
        SELECT contract_id, start_date, subject, count(*)
          FROM field_operation
         WHERE contract_id IS NOT NULL
         GROUP BY 1, 2, 3
        HAVING count(*) > 1
         ORDER BY 4 DESC
         LIMIT 20
        """
    )
    duplicates = cr.fetchall()
    if duplicates:
        _logger.warning(
            "field_operation_contract: %s duplicated periodic operation group(s) "
            "found (contract, start_date, subject, count): %s",
            len(duplicates),
            duplicates,
        )
    else:
        _logger.info(
            "field_operation_contract: no duplicated periodic operations found."
        )
