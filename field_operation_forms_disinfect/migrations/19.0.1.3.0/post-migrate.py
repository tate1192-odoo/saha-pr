# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone() is not None


def migrate(cr, version):
    """Move the form-side lines to their own model.

    Before 19.0.1.3.0 the bridge stored the form lines in
    ``field.operation.disinfect`` and linked them through ``forms_id``.  The
    form flow is now independent, so those rows are copied to
    ``field.operation.forms.disinfect`` and the PH/CL readings are copied from
    the operation to the form.
    """
    if not version:
        return
    if not _column_exists(cr, "field_operation_disinfect", "forms_id"):
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Line = env["field.operation.forms.disinfect"]

    if not Line.search_count([]):
        cr.execute(
            """
            SELECT forms_id,
                   product_id,
                   tank_dimensions,
                   cleaning,
                   disinfection,
                   ozone,
                   filter_change
              FROM field_operation_disinfect
             WHERE forms_id IS NOT NULL
             ORDER BY id
            """
        )
        rows = cr.fetchall()
        for (
            forms_id,
            product_id,
            tank_dimensions,
            cleaning,
            disinfection,
            ozone,
            filter_change,
        ) in rows:
            Line.create(
                {
                    "forms_id": forms_id,
                    "product_id": product_id,
                    "tank_dimensions": tank_dimensions,
                    "cleaning": cleaning,
                    "disinfection": disinfection,
                    "ozone": ozone,
                    "filter_change": filter_change,
                }
            )
        _logger.info("Copied %s disinfection form lines to the form model.", len(rows))

    # The form fields used to be writable related fields on the operation.
    cr.execute(
        """
        UPDATE field_operation_forms AS form
           SET before_ph = COALESCE(form.before_ph, operation.before_ph),
               after_ph = COALESCE(form.after_ph, operation.after_ph),
               before_cl = COALESCE(form.before_cl, operation.before_cl),
               after_cl = COALESCE(form.after_cl, operation.after_cl)
          FROM field_operation AS operation
         WHERE form.operation_id = operation.id
           AND (operation.before_ph IS NOT NULL
                OR operation.after_ph IS NOT NULL
                OR operation.before_cl IS NOT NULL
                OR operation.after_cl IS NOT NULL)
        """
    )
