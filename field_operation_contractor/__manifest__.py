{
    "name": "Field Operation Contractor",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "Manage contractor jobs for field operations",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/field_operation_contractor_view.xml",
        "views/field_operation_view.xml",
        "views/res_partner_view.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
