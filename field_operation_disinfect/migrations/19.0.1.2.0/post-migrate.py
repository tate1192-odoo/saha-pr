# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo.tools import sql


def migrate(cr, version):
    """Move the existing disinfection lines from the service form to the
    operation.  The old ``forms_id`` column is kept for the optional
    ``field_operation_forms_disinfect`` bridge."""
    if not sql.table_exists(cr, "field_operation_forms"):
        return

    cr.execute(
        """
        UPDATE field_operation_disinfect AS line
           SET operation_id = form.operation_id
          FROM field_operation_forms AS form
         WHERE line.forms_id = form.id
           AND line.operation_id IS NULL
           AND form.operation_id IS NOT NULL
        """
    )
    cr.execute(
        """
        UPDATE field_operation_disinfect AS line
           SET company_id = operation.company_id,
               status = operation.status
          FROM field_operation AS operation
         WHERE line.operation_id = operation.id
        """
    )

    # Copy the legacy form readings even when the optional bridge is not
    # installed.  An operation may have several forms, so aggregate instead of
    # joining the form table directly.
    if sql.column_exists(cr, "field_operation_forms", "before_ph"):
        cr.execute(
            """
            UPDATE field_operation AS operation
               SET before_ph = COALESCE(operation.before_ph, form.before_ph),
                   after_ph = COALESCE(operation.after_ph, form.after_ph),
                   before_cl = COALESCE(operation.before_cl, form.before_cl),
                   after_cl = COALESCE(operation.after_cl, form.after_cl)
              FROM (
                  SELECT operation_id,
                         MAX(before_ph) AS before_ph,
                         MAX(after_ph) AS after_ph,
                         MAX(before_cl) AS before_cl,
                         MAX(after_cl) AS after_cl
                    FROM field_operation_forms
                   WHERE operation_id IS NOT NULL
                   GROUP BY operation_id
              ) AS form
             WHERE form.operation_id = operation.id
            """
        )
