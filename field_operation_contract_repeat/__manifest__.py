{
    "name": "Field Operation Contract Repeat Wizard",
    "version": "19.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "Manual recurring operations wizard for Field Operation Contracts",
    "description": """
Field Operation Contract Repeat Wizard
======================================

Optional add-on for Field Operation Contract that provides a manual
wizard to generate recurring field operations from a contract using
iCalendar recurrence rules (rrule).

Use case: sales teams who want to pre-generate field operations on
demand without relying on the automated cron-based recurrence.

Features:
---------
* Recurrence wizard (daily, weekly, monthly, yearly)
* Configurable end conditions (count or specific date)
* Bulk field.operation generation with safety limits

Separated from the base field_operation_contract module so that it
can be licensed and installed independently per customer needs.
""",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation_contract",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/service_contract_repeat_wizard_view.xml",
        "views/field_operation_contract_view.xml",
    ],
    "demo": [],
    "assets": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
