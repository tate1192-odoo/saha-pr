{
    "name": "Field Operation Pest Form",
    "version": "19.0.1.2.0",
    "category": "Services/Field Service",
    "summary": "Field service operation pest control forms",
    "description": """
Field Operation Pest Form
=========================

Pest control forms for field service operations.

The module is operation-centric: pesticide lines and the biocidal
application details live on ``field.operation`` and the operation service
report carries the pest section. The optional
``field_operation_forms_pest`` bridge restores the service-form tab, the
stock delivery flow and the forms record rules for customers that use
service forms.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence_data.xml",
        "views/res_company_view.xml",
        "views/product_template_view.xml",
        "views/field_operation_view.xml",
        "views/field_operation_pest_type_view.xml",
        "pdf/field_pest_operation_pdf.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
