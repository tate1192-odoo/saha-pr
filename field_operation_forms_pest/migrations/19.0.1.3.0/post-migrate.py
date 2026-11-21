# Part of Softteknik Bilişim. See LICENSE file for copyright and licensing details.

from odoo import SUPERUSER_ID, api

from odoo.addons.field_operation_forms_pest.migration_utils import (
    copy_legacy_form_data,
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    copy_legacy_form_data(env)
