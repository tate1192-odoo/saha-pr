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
