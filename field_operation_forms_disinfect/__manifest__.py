{
    "name": "Field Operation Forms Disinfect",
    "version": "19.0.1.2.0",
    "category": "Services/Field Service",
    "summary": "Disinfection tab, PDF and e-mail on field operation forms",
    "description": """
Field Operation Forms Disinfect
===============================

Optional bridge between ``field_operation_disinfect`` and
``field_operation_forms``.  It restores the disinfection tab, the signed
service-form PDF and the e-mail template for customers that use service
forms.  Customers that do not install ``field_operation_forms`` keep the
same disinfection data on the operation and print it from the operation
service report.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation_disinfect",
        "field_operation_forms",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/field_operation_forms_view.xml",
        "pdf/field_disinfect_pdf.xml",
        "data/email_template.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
}
