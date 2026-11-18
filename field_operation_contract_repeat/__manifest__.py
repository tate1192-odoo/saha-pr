{
    "name": "Field Operation Contract Repeat Wizard",
    "version": "19.0.2.0.0",
    "category": "Services/Field Service",
    "summary": "Pre-generate the recurring operations of a contract",
    "description": """
Field Operation Contract Repeat Wizard
======================================

Optional add-on for Field Operation Contract. It lets a user pre-generate the
recurring operations of a contract from the contract form, on demand, instead of
waiting for the cron based recurrence of the contract module.

Use case: sales teams who want to pre-generate field operations on demand.

The recurrence engine is not duplicated: the module extends
``service.repeat.wizard`` (``field_operation_repeat``) with the contract source,
so the dialog, the ``rrule`` handling, the safety limits and the date filtering
are shared with the rest of the suite.
""",
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "license": "AGPL-3",
    "sequence": 121,
    "depends": [
        "field_operation_contract",
        "field_operation_repeat",
    ],
    "data": [
        "wizard/service_repeat_wizard_view.xml",
        "views/field_operation_contract_view.xml",
    ],
    "demo": [],
    "assets": {},
    "installable": True,
    "auto_install": False,
    "application": False,
}
