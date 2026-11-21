# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

# XML ids that move from field_operation_disinfect to this bridge.  Moving them
# before the bridge data is loaded makes Odoo update the existing records instead
# of creating duplicates (views, report, mail template; the line model is new).
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
    """Keep the Turkish label of the form-side line field."""
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
