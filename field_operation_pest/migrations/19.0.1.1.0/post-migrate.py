"""Give the pesticide lines a reference now that the sequence exists.

``field.operation.pesticide.create()`` always asked for the ``field.biocidal``
sequence while no module defined it: ``next_by_code`` returned False, so all 8044
live lines ended up named "Yeni" (_("New")). The sequence now ships with the module;
this script numbers the existing lines so the reference field means something.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    sequence = env["ir.sequence"].search([("code", "=", "field.biocidal")], limit=1)
    if not sequence:
        return
    pesticides = env["field.operation.pesticide"].search(
        [("name", "in", ("Yeni", "New", "/"))], order="id"
    )
    for pesticide in pesticides:
        pesticide.name = sequence.next_by_id()
