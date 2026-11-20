# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo.tools import sql

# XML ids that move from field_operation_pest to this bridge.  Moving them
# before the bridge data is loaded makes Odoo update the existing records
# instead of creating duplicates.
MOVED_XMLIDS = (
    "field_operation_forms_pest_view",
    "field_operation_forms_pest_picking_view",
    "field_field_operation_pesticide__forms_id",
    "field_field_operation_forms__application_method",
    "field_field_operation_forms__application_place",
    "field_field_operation_forms__destination_location_id",
    "field_field_operation_forms__efk_ift",
    "field_field_operation_forms__hygiene",
    "field_field_operation_forms__infestation",
    "field_field_operation_forms__insulation",
    "field_field_operation_forms__monitors",
    "field_field_operation_forms__others",
    "field_field_operation_forms__pest_type_ids",
    "field_field_operation_forms__pesticide_ids",
    "field_field_operation_forms__picking_count",
    "field_field_operation_forms__picking_type_id",
    "field_field_operation_forms__place",
    "field_field_operation_forms__residence",
    "field_field_operation_forms__responsible_manager_id",
    "field_field_operation_forms__security_precautions",
    "field_field_operation_forms__source_location_id",
    "field_field_operation_forms__stock_picking_id",
    "field_field_operation_forms__storage",
    "field_stock_move__field_operation_form_id",
    "field_stock_picking__field_operation_form_id",
    "selection__field_operation_forms__application_place__house",
    "selection__field_operation_forms__application_place__other",
    "selection__field_operation_forms__application_place__workplace",
)


def pre_init_hook(env):
    """Re-own the form-side records before the bridge data files run."""
    env.cr.execute(
        """
        UPDATE ir_model_data
           SET module = %s
         WHERE module = %s
           AND name = ANY(%s)
        """,
        (
            "field_operation_forms_pest",
            "field_operation_pest",
            list(MOVED_XMLIDS),
        ),
    )


def post_init_hook(env):
    """Link the legacy service-form pest data to an operation.

    The core module keeps the line tables and adds ``operation_id``; the bridge
    restores ``forms_id`` and is responsible for the form-side data.
    """
    forms = env["field.operation.forms"].search(
        [
            ("operation_id", "=", False),
            "|",
            ("pesticide_ids", "!=", False),
            ("service_type", "=", "pest"),
        ]
    )
    for form in forms:
        form._ensure_pest_operation()

    env.flush_all()

    env.cr.execute(
        """
        UPDATE field_operation_pesticide AS line
           SET operation_id = form.operation_id
          FROM field_operation_forms AS form
         WHERE line.forms_id = form.id
           AND line.operation_id IS NULL
           AND form.operation_id IS NOT NULL
        """
    )
    env.cr.execute(
        """
        UPDATE field_operation_pesticide AS line
           SET company_id = operation.company_id,
               status = operation.status
          FROM field_operation AS operation
         WHERE line.operation_id = operation.id
        """
    )

    if sql.column_exists(env.cr, "field_operation_forms", "hygiene"):
        env.cr.execute(
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

    if sql.table_exists(env.cr, "field_operation_forms_field_operation_pest_type_rel"):
        env.cr.execute(
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
