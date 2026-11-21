# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from .migration_utils import copy_legacy_form_data

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
    """Copy the legacy form data the first time the bridge is installed."""
    copy_legacy_form_data(env)
