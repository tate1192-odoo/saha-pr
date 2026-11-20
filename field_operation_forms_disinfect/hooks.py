# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

# XML ids that move from field_operation_disinfect to this bridge.  Moving them
# before the bridge data is loaded makes Odoo update the existing records instead
# of creating duplicates (views, report, mail template, sequence is not moved).
MOVED_XMLIDS = (
    "pdf_field_disinfect",
    "field_disinfect_layout",
    "action_field_disinfect_pdf",
    "email_field_operation_form_biocidal",
    "field_operation_forms_disinfect_view",
    "field_operation_forms_disinfect_mail_view",
    "field_field_operation_forms__disinfect_ids",
    "field_field_operation_forms__before_ph",
    "field_field_operation_forms__after_ph",
    "field_field_operation_forms__before_cl",
    "field_field_operation_forms__after_cl",
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
            "field_operation_forms_disinfect",
            "field_operation_disinfect",
            list(MOVED_XMLIDS),
        ),
    )


def post_init_hook(env):
    """Link the legacy service-form disinfection data to an operation.

    The core module keeps the line tables and adds ``operation_id``; the
    bridge restores ``forms_id`` and is responsible for the form-side data.
    """
    # Forms created directly in the service-form screen have no operation.
    # The operation is the parent of the domain data, so create it now.
    forms = env["field.operation.forms"].search(
        [
            ("operation_id", "=", False),
            "|",
            ("disinfect_ids", "!=", False),
            ("service_type", "=", "disinfect"),
        ]
    )
    for form in forms:
        form._ensure_disinfect_operation()

    env.flush_all()

    env.cr.execute(
        """
        UPDATE field_operation_disinfect AS line
           SET operation_id = form.operation_id
          FROM field_operation_forms AS form
         WHERE line.forms_id = form.id
           AND line.operation_id IS NULL
           AND form.operation_id IS NOT NULL
        """
    )
    env.cr.execute(
        """
        UPDATE field_operation_disinfect AS line
           SET company_id = operation.company_id,
               status = operation.status
          FROM field_operation AS operation
         WHERE line.operation_id = operation.id
        """
    )

    # The old module labelled this field "Dispenser Type".  Keep the new
    # Turkish label even on databases that still carry the old translation.
    field = env["ir.model.fields"].search(
        [("model", "=", "field.operation.forms"), ("name", "=", "disinfect_ids")],
        limit=1,
    )
    if field and env["res.lang"].search_count(
        [("code", "=", "tr_TR"), ("active", "=", True)]
    ):
        field.update_field_translations(
            "field_description", {"tr_TR": "Dezenfeksiyon Satırları"}
        )
