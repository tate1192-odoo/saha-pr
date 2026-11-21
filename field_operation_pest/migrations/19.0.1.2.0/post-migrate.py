# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo.tools import sql


def migrate(cr, version):
    """Link the existing pesticide lines and pest details to their operation.

    The old ``forms_id`` column is kept for the optional
    ``field_operation_forms_pest`` bridge.  The copies are guarded so the
    module can be upgraded on a database without forms.
    """
    if not sql.table_exists(cr, "field_operation_forms"):
        return

    cr.execute(
        """
        UPDATE field_operation_pesticide AS line
           SET operation_id = form.operation_id
          FROM field_operation_forms AS form
         WHERE line.forms_id = form.id
           AND line.operation_id IS NULL
           AND form.operation_id IS NOT NULL
        """
    )
    cr.execute(
        """
        UPDATE field_operation_pesticide AS line
           SET company_id = operation.company_id,
               status = COALESCE(line.status, operation.status)
          FROM field_operation AS operation
         WHERE line.operation_id = operation.id
        """
    )

    if sql.column_exists(cr, "field_operation_forms", "hygiene"):
        cr.execute(
            """
            UPDATE field_operation AS operation
               SET hygiene = COALESCE(operation.hygiene, FALSE) OR COALESCE(form.hygiene, FALSE),
                   infestation = COALESCE(operation.infestation, FALSE) OR COALESCE(form.infestation, FALSE),
                   insulation = COALESCE(operation.insulation, FALSE) OR COALESCE(form.insulation, FALSE),
                   storage = COALESCE(operation.storage, FALSE) OR COALESCE(form.storage, FALSE),
                   efk_ift = COALESCE(operation.efk_ift, FALSE) OR COALESCE(form.efk_ift, FALSE),
                   monitors = COALESCE(operation.monitors, FALSE) OR COALESCE(form.monitors, FALSE),
                   others = COALESCE(operation.others, FALSE) OR COALESCE(form.others, FALSE),
                   residence = COALESCE(operation.residence, form.residence),
                   place = COALESCE(operation.place, form.place),
                   application_method = COALESCE(operation.application_method, form.application_method),
                   security_precautions = COALESCE(operation.security_precautions, form.security_precautions),
                   responsible_manager_id = COALESCE(operation.responsible_manager_id, form.responsible_manager_id),
                   application_place = COALESCE(operation.application_place, form.application_place)
              FROM (
                  SELECT operation_id,
                         BOOL_OR(hygiene) AS hygiene,
                         BOOL_OR(infestation) AS infestation,
                         BOOL_OR(insulation) AS insulation,
                         BOOL_OR(storage) AS storage,
                         BOOL_OR(efk_ift) AS efk_ift,
                         BOOL_OR(monitors) AS monitors,
                         BOOL_OR(others) AS others,
                         MAX(residence) AS residence,
                         MAX(place) AS place,
                         MAX(application_method) AS application_method,
                         MAX(security_precautions) AS security_precautions,
                         MAX(responsible_manager_id) AS responsible_manager_id,
                         MAX(application_place) AS application_place
                    FROM field_operation_forms
                   WHERE operation_id IS NOT NULL
                   GROUP BY operation_id
              ) AS form
             WHERE form.operation_id = operation.id
            """
        )

    if sql.table_exists(cr, "field_operation_forms_field_operation_pest_type_rel"):
        cr.execute(
            """
            INSERT INTO field_operation_field_operation_pest_type_rel
                        (field_operation_id, field_operation_pest_type_id)
            SELECT DISTINCT form.operation_id, rel.field_operation_pest_type_id
              FROM field_operation_forms AS form
              JOIN field_operation_forms_field_operation_pest_type_rel AS rel
                ON rel.field_operation_forms_id = form.id
             WHERE form.operation_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )
