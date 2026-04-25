# SPDX-License-Identifier: LGPL-2.1-or-later

"""Helpers for reading and restoring FreeCAD view-object properties."""

from bimplan.runtime import capabilities as runtime_capabilities


def has_view_property(view_object, property_name):
    return view_object is not None and hasattr(view_object, property_name)


def get_view_property(view_object, property_name, default=None):
    if not has_view_property(view_object, property_name):
        return default
    return runtime_capabilities.get_attr(view_object, property_name, default)


def set_view_property(view_object, property_name, value):
    if not has_view_property(view_object, property_name):
        return False
    return runtime_capabilities.set_attr_if_present(view_object, property_name, value)


def capture_view_properties(view_object, property_names):
    state = {}
    for property_name in property_names:
        value = get_view_property(view_object, property_name, None)
        if value is not None:
            state[property_name] = value
    return state


def restore_view_properties(view_object, state):
    applied = False
    for property_name, value in dict(state or {}).items():
        applied = set_view_property(view_object, property_name, value) or applied
    return applied
