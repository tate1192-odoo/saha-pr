# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.


def migrate(cr, version):
    """Remove the old form-side records before ``field_operation_forms`` is
    reloaded by a reverse-dependent module.

    The disinfection tab/PDF/e-mail moved to
    ``field_operation_forms_disinfect``.  Until the bridge is installed, the
    old inherited view still references ``before_ph`` / ``disinfect_ids`` and
    ``action_send_disinfect_mail``, which no longer exist on
    ``field.operation.forms``.  Odoo validates the forms view when a module that
    depends on disinfect reloads it, so the stale records have to go first.
    The bridge recreates them with the same XML ids.

    A view that is inherited by a customer module is left in place: deleting it
    would leave the child view with a dangling ``inherit_id``.
    """
    view_names = (
        "field_operation_forms_disinfect_view",
        "field_operation_forms_disinfect_mail_view",
        "pdf_field_disinfect",
        "field_disinfect_layout",
    )
    report_names = ("action_field_disinfect_pdf",)
    mail_names = ("email_field_operation_form_biocidal",)

    cr.execute(
        """
        DELETE FROM ir_ui_view AS view
         USING ir_model_data AS data
         WHERE data.model = 'ir.ui.view'
           AND data.res_id = view.id
           AND data.module = 'field_operation_disinfect'
           AND data.name = ANY(%s)
           AND NOT EXISTS (
               SELECT 1 FROM ir_ui_view AS child WHERE child.inherit_id = view.id
           )
        """,
        (list(view_names),),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data AS data
         WHERE data.module = 'field_operation_disinfect'
           AND data.model = 'ir.ui.view'
           AND data.name = ANY(%s)
           AND NOT EXISTS (
               SELECT 1 FROM ir_ui_view AS view WHERE view.id = data.res_id
           )
        """,
        (list(view_names),),
    )

    cr.execute(
        """
        DELETE FROM ir_act_report_xml AS report
         USING ir_model_data AS data
         WHERE data.model = 'ir.actions.report'
           AND data.res_id = report.id
           AND data.module = 'field_operation_disinfect'
           AND data.name = ANY(%s)
        """,
        (list(report_names),),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'field_operation_disinfect'
           AND model = 'ir.actions.report'
           AND name = ANY(%s)
        """,
        (list(report_names),),
    )

    cr.execute(
        """
        DELETE FROM mail_template AS template
         USING ir_model_data AS data
         WHERE data.model = 'mail.template'
           AND data.res_id = template.id
           AND data.module = 'field_operation_disinfect'
           AND data.name = ANY(%s)
        """,
        (list(mail_names),),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'field_operation_disinfect'
           AND model = 'mail.template'
           AND name = ANY(%s)
        """,
        (list(mail_names),),
    )
