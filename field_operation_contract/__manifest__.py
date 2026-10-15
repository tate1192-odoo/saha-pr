{
    "name": "Field Operation Contract Management",
    "version": "19.0.1.1.0",
    "category": "Services/Field Service",
    "summary": "Manage recurring field service contracts with flexible scheduling",
    "description": """
Field Operation Contract Management
===================================

This module extends Field Operations to manage service contracts
with recurring schedules. It bridges the gap between Sales,
Invoicing, and Field Service Operations.

Features:
---------
* Dual Recurrence Logic - Contract-level and Line-level scheduling
* Automated Generation - Recurring Sale Orders and Field Operations
* Sale Order Integration - Convert Sales Orders into Contracts
* Management & Tracking - Digital signature, status workflow
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "images": ["static/description/icon.png"],
    "license": "AGPL-3",
    "sequence": 120,
    "depends": [
        "field_operation",
        "field_operation_sale",
        "portal",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "wizard/sale_order_to_contract_wizard_view.xml",
        "views/field_operation_contract_view.xml",
        "views/field_operation_contract_tag_view.xml",
        "views/field_operation_view.xml",
        "views/sale_order_view.xml",
        "views/res_partner_view.xml",
        "template/portal_my_contracts.xml",
        "template/portal_contract_page.xml",
        "pdf/contract_pdf.xml",
    ],
    "demo": [],
    "assets": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
