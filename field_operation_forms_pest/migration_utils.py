# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

import logging

from odoo.tools import sql

_logger = logging.getLogger(__name__)


def copy_legacy_form_data(env):
    """Move the legacy service-form pest data to the independent form model.

    The core module keeps the operation-side lines and copies the old form
    header values to the operation during its own migration.  This helper runs
    both when the bridge is installed for the first time (post-init hook) and
    when an already installed bridge is upgraded (post-migration).
    """
    cr = env.cr
    if not sql.column_exists(cr, "field_operation_pesticide", "forms_id"):
        return

    Line = env["field.operation.forms.pest"]
    if not Line.search_count([]):
        cr.execute(
            """
            SELECT forms_id,
                   name,
                   product_id,
                   product_uom,
                   product_qty,
                   used_equipment
              FROM field_operation_pesticide
             WHERE forms_id IS NOT NULL
             ORDER BY id
            """
        )
        rows = cr.fetchall()
        for (
            forms_id,
            name,
            product_id,
            product_uom,
            product_qty,
            used_equipment,
        ) in rows:
            Line.create(
                {
                    "forms_id": forms_id,
                    "name": name,
                    "product_id": product_id,
                    "product_uom": product_uom,
                    "product_qty": product_qty,
                    "used_equipment": used_equipment,
                }
            )
        _logger.info("Copied %s pest form lines to the form model.", len(rows))

    # The old form header fields were copied to the operation by the core
    # migration; bring them back to the form so the form-side flow owns them.
    cr.execute(
        """
        UPDATE field_operation_forms AS form
           SET hygiene = COALESCE(form.hygiene, FALSE)
                         OR COALESCE(operation.hygiene, FALSE),
               infestation = COALESCE(form.infestation, FALSE)
                             OR COALESCE(operation.infestation, FALSE),
               insulation = COALESCE(form.insulation, FALSE)
                            OR COALESCE(operation.insulation, FALSE),
               storage = COALESCE(form.storage, FALSE)
                         OR COALESCE(operation.storage, FALSE),
               efk_ift = COALESCE(form.efk_ift, FALSE)
                         OR COALESCE(operation.efk_ift, FALSE),
               monitors = COALESCE(form.monitors, FALSE)
                          OR COALESCE(operation.monitors, FALSE),
               others = COALESCE(form.others, FALSE)
                        OR COALESCE(operation.others, FALSE),
               residence = COALESCE(form.residence, operation.residence),
               place = COALESCE(form.place, operation.place),
               application_method = COALESCE(
                   form.application_method, operation.application_method
               ),
               security_precautions = COALESCE(
                   form.security_precautions, operation.security_precautions
               ),
               responsible_manager_id = COALESCE(
                   form.responsible_manager_id, operation.responsible_manager_id
               ),
               application_place = COALESCE(
                   form.application_place, operation.application_place
               )
          FROM field_operation AS operation
         WHERE form.operation_id = operation.id
           AND form.service_type = 'pest'
        """
    )

    if sql.table_exists(
        cr, "field_operation_forms_field_operation_pest_type_rel"
    ) and sql.table_exists(cr, "field_operation_field_operation_pest_type_rel"):
        cr.execute(
            """
            INSERT INTO field_operation_forms_field_operation_pest_type_rel
                        (field_operation_forms_id, field_operation_pest_type_id)
            SELECT form.id, rel.field_operation_pest_type_id
              FROM field_operation_forms AS form
              JOIN field_operation_field_operation_pest_type_rel AS rel
                ON rel.field_operation_id = form.operation_id
             WHERE form.service_type = 'pest'
               AND form.operation_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )

    # If the old form stock columns were dropped by the core update, rebuild
    # them from the delivery order that points back at the form.
    if sql.column_exists(cr, "stock_picking", "field_operation_form_id"):
        cr.execute(
            """
            UPDATE field_operation_forms AS form
               SET stock_picking_id = COALESCE(
                       form.stock_picking_id, picking.id
                   ),
                   picking_type_id = COALESCE(
                       form.picking_type_id, picking.picking_type_id
                   ),
                   source_location_id = COALESCE(
                       form.source_location_id, picking.location_id
                   ),
                   destination_location_id = COALESCE(
                       form.destination_location_id, picking.location_dest_id
                   )
              FROM (
                  SELECT DISTINCT ON (field_operation_form_id)
                         field_operation_form_id,
                         id,
                         picking_type_id,
                         location_id,
                         location_dest_id
                    FROM stock_picking
                   WHERE field_operation_form_id IS NOT NULL
                   ORDER BY field_operation_form_id, id DESC
              ) AS picking
             WHERE picking.field_operation_form_id = form.id
            """
        )
