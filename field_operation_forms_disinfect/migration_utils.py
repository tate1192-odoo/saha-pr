# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def copy_legacy_form_data(env):
    """Copy the legacy service-form disinfection data to the form model.

    The core module keeps the operation-side lines and copies the old form
    readings to the operation during its own migration.  This helper runs both
    when the bridge is installed for the first time (post-init hook) and when
    an already installed bridge is upgraded (post-migration).
    """
    cr = env.cr
    if not sql.column_exists(cr, "field_operation_disinfect", "forms_id"):
        return

    Line = env["field.operation.forms.disinfect"]
    if not Line.search_count([]):
        cr.execute(
            """
            SELECT forms_id,
                   name,
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
            name,
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
                    "name": name,
                    "product_id": product_id,
                    "tank_dimensions": tank_dimensions,
                    "cleaning": cleaning,
                    "disinfection": disinfection,
                    "ozone": ozone,
                    "filter_change": filter_change,
                }
            )
        _logger.info("Copied %s disinfection form lines to the form model.", len(rows))

    # The old form readings were moved to the operation by the core migration;
    # bring them back to the form fields.
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
