# SPDX-License-Identifier: LGPL-2.1-or-later

"""Safe access to widgets used by viewport controllers."""

import FreeCADGui


def resolve_widgets(viewport):
    """Return a live ``(graphics_view, viewport_widget)`` pair or ``(None, None)``."""
    graphics_view = viewport.get_plan_view_widget()
    if not FreeCADGui.isValidQObject(graphics_view):
        return None, None
    try:
        host_widget = graphics_view.viewport()
    except (AttributeError, RuntimeError, TypeError):
        return None, None
    if not FreeCADGui.isValidQObject(host_widget):
        return None, None
    return graphics_view, host_widget


def remove_event_filter(target, event_filter):
    """Remove an event filter when both wrappers still refer to live objects."""
    if not FreeCADGui.isValidQObject(target) or not FreeCADGui.isValidQObject(event_filter):
        return
    try:
        target.removeEventFilter(event_filter)
    except (AttributeError, RuntimeError, TypeError):
        pass
