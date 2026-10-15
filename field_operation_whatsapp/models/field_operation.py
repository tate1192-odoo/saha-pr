# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models


class FieldOperation(models.Model):
    """The WhatsApp shortcut on the operation form.

    The action itself lives on the wizard (``field.whatsapp.message``) because
    the service form model exposes the same button.
    """

    _inherit = "field.operation"

    def action_message_send(self):
        """Open the WhatsApp wizard pre-filled with this operation."""
        self.ensure_one()
        return self.env["field.whatsapp.message"]._open_action_for(self._name, self.id)
