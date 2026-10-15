import logging

_logger = logging.getLogger(__name__)


def uninstall_hook(env):
    """Restore the field.operation action to the view modes we modified.

    This module only appends ``leaflet_map`` to the base action's view_mode, so
    uninstall only removes that single mode. Other actions and other view modes
    are left untouched.
    """
    action = env.ref("field_operation.action_field_operation", raise_if_not_found=False)
    if action is None:
        return
    view_modes = [mode.strip() for mode in action.view_mode.split(",") if mode.strip()]
    if "leaflet_map" not in view_modes:
        return
    action.view_mode = ",".join(mode for mode in view_modes if mode != "leaflet_map")
    _logger.info(
        "Removed 'leaflet_map' from field_operation.action_field_operation view_mode"
    )
