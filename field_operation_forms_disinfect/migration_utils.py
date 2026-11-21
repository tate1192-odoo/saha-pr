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
            INSERT INTO field_operation_forms_disinfect
                        (name, sequence, forms_id, product_id, tank_dimensions,
                         cleaning, disinfection, ozone, filter_change,
                         company_id, customer_id, user_id, subject, status,
                         start_date, end_date,
                         create_uid, create_date, write_uid, write_date)
            SELECT line.name, 10, line.forms_id, line.product_id,
                   line.tank_dimensions, line.cleaning, line.disinfection,
                   line.ozone, line.filter_change, form.company_id,
                   form.customer_id, form.user_id, form.subject, line.status,
                   operation.start_date, operation.end_date,
                   line.create_uid, line.create_date,
                   line.write_uid, line.write_date
              FROM field_operation_disinfect AS line
              JOIN field_operation_forms AS form ON form.id = line.forms_id
              LEFT JOIN field_operation AS operation
                ON operation.id = line.operation_id
             WHERE line.forms_id IS NOT NULL
            """
        )
        copied = cr.rowcount
        # Replace the legacy placeholder references with the form sequence.
        cr.execute(
            """
            SELECT id
              FROM field_operation_forms_disinfect
             WHERE name IS NULL OR name IN ('', '/', 'New', 'Yeni')
            """
        )
        for (line_id,) in cr.fetchall():
            name = (
                env["ir.sequence"].next_by_code("field.forms.disinfect") or "/"
            )
            cr.execute(
                "UPDATE field_operation_forms_disinfect SET name = %s WHERE id = %s",
                (name, line_id),
            )
        _logger.info(
            "Copied %s disinfection form lines to the form model.", copied
        )

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
