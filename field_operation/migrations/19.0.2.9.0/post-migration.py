"""Remove the database leftovers of the dropped recurring-service wizard.

19.0.2.9.0 deletes ``field_operation/wizard`` (``service.repeat.wizard``), so the
records that used to be created by ``wizard/service_repeat_wizard_view.xml`` are
referenced by no XML file any more. Odoo never deletes records that simply
disappear from a data file, they would stay in the database for ever: a stale
window action, a stale form view, an ACL row, and the transient model itself with
its table. They are removed here once, on the upgrade that drops the wizard.

The model row is deleted with plain SQL instead of ``ir.model.unlink()``: that
method reloads the registry in the middle of the module loading, and the model is
already gone from the registry at this point anyway.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

#: xmlid (without the module prefix) -> table holding the record it points to
RECORDS = {
    "service_repeat_wizard_view_form": "ir_ui_view",
    "action_service_repeat_wizard": "ir_act_window",
    "access_service_repeat_wizard_user": "ir_model_access",
}
MODEL_XMLID = "model_service_repeat_wizard"
WIZARD_MODEL = "service.repeat.wizard"
WIZARD_TABLE = "service_repeat_wizard"


def migrate(cr, version):
    if not version:
        return

    xmlids = tuple(list(RECORDS) + [MODEL_XMLID])
    cr.execute(
        "SELECT name, res_id FROM ir_model_data "
        "WHERE module = 'field_operation' AND name IN %s",
        (xmlids,),
    )
    found = cr.fetchall()

    for name, res_id in found:
        table = RECORDS.get(name)
        if table:
            cr.execute(
                sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(table)),
                (res_id,),
            )
            _logger.info("field_operation: removed %s (%s %s)", name, table, res_id)
        elif name == MODEL_XMLID:
            _drop_model(cr, res_id)

    cr.execute(
        "DELETE FROM ir_model_data WHERE module = 'field_operation' AND name IN %s",
        (xmlids,),
    )


def _drop_model(cr, model_id):
    """Delete the transient model row, its fields, selections and its table."""
    cr.execute("SELECT model FROM ir_model WHERE id = %s", (model_id,))
    row = cr.fetchone()
    model_name = row[0] if row else WIZARD_MODEL

    cr.execute("SELECT id FROM ir_model_fields WHERE model_id = %s", (model_id,))
    field_ids = tuple(r[0] for r in cr.fetchall())
    selection_ids = ()
    if field_ids:
        cr.execute(
            "SELECT id FROM ir_model_fields_selection WHERE field_id IN %s",
            (field_ids,),
        )
        selection_ids = tuple(r[0] for r in cr.fetchall())

    # xmlid rows of the model itself, of its fields and of the selections
    cr.execute("DELETE FROM ir_model_data WHERE model = %s", (model_name,))
    if field_ids:
        cr.execute(
            "DELETE FROM ir_model_data "
            "WHERE model = 'ir.model.fields' AND res_id IN %s",
            (field_ids,),
        )
    if selection_ids:
        cr.execute(
            "DELETE FROM ir_model_data "
            "WHERE model = 'ir.model.fields.selection' AND res_id IN %s",
            (selection_ids,),
        )

    # selections and fields cascade from the field rows
    cr.execute("DELETE FROM ir_model_fields WHERE model_id = %s", (model_id,))
    cr.execute(
        sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
            sql.Identifier(WIZARD_TABLE)
        )
    )
    cr.execute("DELETE FROM ir_model WHERE id = %s", (model_id,))
    _logger.info(
        "field_operation: removed model %s, its %d fields and table %s",
        model_name,
        len(field_ids),
        WIZARD_TABLE,
    )
