# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

MODULE = "field_operation_grease_duct"
OLD_MODEL = "field.operation.grease.duct.line"
NEW_MODEL = "field.operation.grease.duct"
OLD_TABLE = "field_operation_grease_duct_line"
NEW_TABLE = "field_operation_grease_duct"
OLD_XMLID = "model_field_operation_grease_duct_line"
NEW_XMLID = "model_field_operation_grease_duct"


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return cr.fetchone()[0] is not None


def _model_id(cr, model):
    cr.execute("SELECT id FROM ir_model WHERE model = %s", (model,))
    row = cr.fetchone()
    return row[0] if row else None


def _xmlid_exists(cr, name):
    cr.execute(
        """
        SELECT 1
          FROM ir_model_data
         WHERE module = %s
           AND model = 'ir.model'
           AND name = %s
        """,
        (MODULE, name),
    )
    return cr.fetchone() is not None


def migrate(cr, version):
    """Rename the grease duct line model without losing its existing rows.

    The model moves from ``field.operation.grease.duct.line`` to
    ``field.operation.grease.duct``.  The table, the ``ir.model`` row and the
    model XML id are renamed together so the ORM reuses the existing fields,
    access rules and record rules instead of creating a second, empty model.
    """
    if not version:
        return

    old_table = _table_exists(cr, OLD_TABLE)
    new_table = _table_exists(cr, NEW_TABLE)
    if old_table and not new_table:
        cr.execute(f'ALTER TABLE "{OLD_TABLE}" RENAME TO "{NEW_TABLE}"')
        _logger.info("Renamed table %s to %s", OLD_TABLE, NEW_TABLE)
    elif old_table and new_table:
        _logger.warning(
            "Both %s and %s exist; leaving the tables untouched.",
            OLD_TABLE,
            NEW_TABLE,
        )

    old_model_id = _model_id(cr, OLD_MODEL)
    new_model_id = _model_id(cr, NEW_MODEL)
    if old_model_id and not new_model_id:
        cr.execute(
            "UPDATE ir_model SET model = %s WHERE id = %s",
            (NEW_MODEL, old_model_id),
        )
        if _xmlid_exists(cr, OLD_XMLID) and not _xmlid_exists(cr, NEW_XMLID):
            cr.execute(
                """
                UPDATE ir_model_data
                   SET name = %s
                 WHERE module = %s
                   AND model = 'ir.model'
                   AND name = %s
                """,
                (NEW_XMLID, MODULE, OLD_XMLID),
            )
    elif old_model_id and new_model_id:
        _logger.warning(
            "Both models %s and %s exist; leaving the model rows untouched.",
            OLD_MODEL,
            NEW_MODEL,
        )
