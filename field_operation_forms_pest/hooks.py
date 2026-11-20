# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

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

    # The legacy header/type copy lives in the core post-migration.  This hook
    # only creates the missing operations and links their pesticide lines.
