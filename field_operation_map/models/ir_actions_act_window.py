from odoo import api, models

#: The mode this module offers.
VIEW_MODE = "leaflet_map"


class IrActionsActWindow(models.Model):
    """Add the map mode to the field operation action.

    ``view_mode`` is a comma separated Char, so a data record listing it can
    only write the WHOLE string: whichever module writes last wins and the
    modes of the other modules (and of the core action itself) disappear
    silently. Measured on this suite: with the whole string written here, an
    update of this module after ``field_operation_gantt`` left the action with
    ``kanban,list,form,activity,leaflet_map`` — no Gantt, and no
    ``calendar``/``graph``/``pivot``/``activity`` either.

    So the mode is appended instead of the string being replaced, and the
    operation is idempotent, which is what makes it safe on every update: the
    function is called from a ``<function>`` tag in the data file, and those run
    on install and on update alike. ``hooks.py`` removes the mode again on
    uninstall, which keeps the two halves symmetric.
    """

    _inherit = "ir.actions.act_window"

    @api.model
    def _add_field_operation_map_view_mode(self):
        action = self.env.ref(
            "field_operation.action_field_operation", raise_if_not_found=False
        )
        if not action:
            return
        modes = [mode for mode in (action.view_mode or "").split(",") if mode]
        if VIEW_MODE in modes:
            return
        modes.append(VIEW_MODE)
        action.view_mode = ",".join(modes)
