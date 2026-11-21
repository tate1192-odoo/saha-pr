{
    "name": "Field Operation Disinfect Form",
    "version": "19.0.1.2.1",
    "category": "Services/Field Service",
    "summary": "Field service operation disinfection forms",
    "description": """
Field Operation Disinfect Form
==============================

Disinfection forms for field service operations.

The module is operation-centric: the disinfection lines and the PH/CL
readings live on ``field.operation`` and the operation service report is
enough for customers that do not use service forms. The optional
``field_operation_forms_disinfect`` bridge restores the service-form tab,
the signed PDF and the e-mail template for customers that do.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence_data.xml",
        "views/res_company_view.xml",
        "views/field_disinfect_product_view.xml",
        "views/field_operation_view.xml",
        "pdf/field_disinfect_operation_pdf.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
