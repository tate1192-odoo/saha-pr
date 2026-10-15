# Copyright(C) 2026 - Today Softteknik Bilişim (<https://softteknik.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models

#: The mode this module offers, and the core mode it is shown after.
VIEW_MODE = "gantt_soft"
AFTER_MODE = "calendar"


class IrActionsActWindow(models.Model):
    """Add the Gantt mode to the field operation action.

    ``view_mode`` is a comma separated Char, so a data record listing it can
    only write the WHOLE string: whichever module writes last wins, and the
    modes of the other modules (and of the core action itself) are silently
    dropped. Measured on this suite: installing ``field_operation_map`` after
    this module used to leave the action with
    ``kanban,list,form,activity,leaflet_map`` — the Gantt gone, and with it
    ``calendar``, ``graph``, ``pivot`` and ``activity``.

    So the mode is added instead of the string being replaced: the existing
    modes are read, ``gantt_soft`` is inserted right after ``calendar`` when
    that mode is present (the position the screen has always shown) and
    appended otherwise, and the value is written back. The operation is
    idempotent, which is what makes it safe to run on every update of this
    module: it is called from a ``<function>`` tag in the data file, and those
    run on install and on update alike.
    """

    _inherit = "ir.actions.act_window"

    @api.model
    def _add_field_operation_gantt_view_mode(self):
        action = self.env.ref(
            "field_operation.action_field_operation", raise_if_not_found=False
        )
        if not action:
            return
        modes = [mode for mode in (action.view_mode or "").split(",") if mode]
        if VIEW_MODE in modes:
            return
        if AFTER_MODE in modes:
            modes.insert(modes.index(AFTER_MODE) + 1, VIEW_MODE)
        else:
            modes.append(VIEW_MODE)
        action.view_mode = ",".join(modes)
