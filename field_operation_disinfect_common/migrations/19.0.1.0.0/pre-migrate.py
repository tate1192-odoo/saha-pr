from odoo import SUPERUSER_ID, api

from odoo.addons.field_operation_disinfect_common.hooks import move_shared_xmlids


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    move_shared_xmlids(env)
