{
    "name": "Field Operation Resequence",
    "version": "19.0.1.0.0",
    "category": "Services/Field Service",
    "summary": "Resequence field operation numbers to fix incorrect sequence entries",
    "description": """
Field Operation Resequence
=========================

This module provides a restricted wizard to compact field operation numbers.
All active and archived operations are ordered by creation date and ID, then
renumbered from the start of the configured Field Operation sequence. The
sequence counter is reset to the next available number.

The operation is irreversible for printed documents and other external records
that contain the old reference. Run it only while no field operations are being
created or edited.
    """,
    "author": "Softteknik Bilişim",
    "website": "https://softteknik.com",
    "contributors": ["Softteknik Bilişim"],
    "license": "AGPL-3",
    "sequence": 130,
    "depends": [
        "field_operation",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/field_operation_resequence_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
