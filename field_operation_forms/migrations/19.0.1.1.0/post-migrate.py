"""Realign field.operation.forms_id after it became a field derived from the form side.

The operation and its form were linked by two independent fields
(``field.operation.forms_id`` and ``field.operation.forms.operation_id``) which drifted:
200 operations pointed at a form whose ``operation_id`` was another operation or empty.
``forms_id`` is now computed from ``operation_id``, so the form side is the reference;
this script marks the reverse relation as modified to force the stored values to be
recomputed.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    operations = env["field.operation"].with_context(active_test=False).search([])
    operations.modified(["form_ids"])
    operations.flush_recordset(["forms_id"])
