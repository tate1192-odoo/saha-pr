# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class FieldOperationForms(models.Model):
    """The WhatsApp shortcut on the service form model.

    ``field_operation_forms_ext`` carried a copy of the operation's action for
    this model and no group on its button, so a forms user without the WhatsApp
    group saw a button that raised an access error. The action now comes from
    the wizard and the button is gated by the group the wizard needs.
    """

    _inherit = "field.operation.forms"

    def action_message_send(self):
        """Open the WhatsApp wizard pre-filled with this service form."""
        self.ensure_one()
        return self.env["field.whatsapp.message"]._open_action_for(self._name, self.id)
