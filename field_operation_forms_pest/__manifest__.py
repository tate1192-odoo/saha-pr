{
    "name": "Field Operation Forms Pest",
    "version": "19.0.1.2.0",
    "category": "Services/Field Service",
    "summary": "Pest tab, stock delivery and form rules on field operation forms",
    "description": """
Field Operation Forms Pest
==========================

Optional bridge between ``field_operation_pest`` and
``field_operation_forms``.  It restores the biocidal/pesticide tab, the
stock delivery flow and the forms record rules for customers that use
service forms.  Customers that do not install ``field_operation_forms``
keep the same pest data on the operation and print it from the operation
service report.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation_pest",
        "field_operation_forms",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/field_operation_forms_view.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": True,
    "application": False,
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
}
