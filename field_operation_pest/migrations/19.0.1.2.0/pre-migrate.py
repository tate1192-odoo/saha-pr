# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.


def migrate(cr, version):
    """Remove the old pest inherited views before reverse-dependent modules
    reload ``field_operation_forms``.

    The pest tab moved to ``field_operation_forms_pest``.  Until the bridge is
    installed, the old inherited views still reference fields and actions that
    no longer exist on ``field.operation.forms``; Odoo validates them when a
    module that depends on pest reloads the forms view.  The bridge recreates
    the views with the same XML ids.

    A view that is inherited by a customer module is left in place: deleting it
    would leave the child view with a dangling ``inherit_id``.  Such a view is
    handled by ``_process_end`` instead.
    """
    view_names = (
        "field_operation_forms_pest_view",
        "field_operation_forms_pest_picking_view",
    )
    cr.execute(
        """
        DELETE FROM ir_ui_view AS view
         USING ir_model_data AS data
         WHERE data.model = 'ir.ui.view'
           AND data.res_id = view.id
           AND data.module = 'field_operation_pest'
           AND data.name = ANY(%s)
           AND NOT EXISTS (
               SELECT 1 FROM ir_ui_view AS child WHERE child.inherit_id = view.id
           )
        """,
        (list(view_names),),
    )
    # Only drop the XML ids of the views that were actually removed; a skipped
    # view keeps its XML id.
    cr.execute(
        """
        DELETE FROM ir_model_data AS data
         WHERE data.module = 'field_operation_pest'
           AND data.model = 'ir.ui.view'
           AND data.name = ANY(%s)
           AND NOT EXISTS (
               SELECT 1 FROM ir_ui_view AS view WHERE view.id = data.res_id
           )
        """,
        (list(view_names),),
    )
