# SPDX-License-Identifier: LGPL-2.1-or-later

"""Additive selection helpers for BIM Plan Edit."""

from . import target_dispatch as plan_target_dispatch


def is_plan_additive_selection_active(session):
    if session.current_tool != "Select":
        return False
    try:
        from PySide import QtCore, QtGui

        modifiers = QtGui.QApplication.keyboardModifiers()
        return bool(modifiers & QtCore.Qt.ControlModifier)
    except Exception:
        return False


def activate_provider_overlay_target_node(session, node, event_callback=None):
    target_kind, target_obj = session._get_provider_overlay_target_from_edit_node(node)
    if target_obj is None:
        return False
    if session._is_valid_plan_target(target_kind, target_obj):
        session._provider_selected_objects = []
        session._set_pending_selected_plan_target(target_kind, target_obj)
    else:
        session._provider_selected_objects = [target_obj]
        session._set_pending_selected_plan_target()
    plan_target_dispatch.clear_hovered_targets(session)
    session._set_gui_selection_object(target_obj)
    session._refresh_primary_selected_plan_target()
    session._claim_left_button_click(event_callback)
    return True


def normalize_gui_object_selection(selection):
    normalized_selection = []
    seen = set()
    for selected in selection or ():
        if not selected:
            continue
        key = (
            getattr(getattr(selected, "Document", None), "Name", None),
            getattr(selected, "Name", None),
        )
        if key in seen:
            continue
        seen.add(key)
        normalized_selection.append(selected)
    return normalized_selection


def toggle_raw_plan_object_selection(session, obj, event_callback=None):
    if obj is None:
        return False

    primary_kind, primary_obj = session._get_selected_plan_target()
    selection = session._get_gui_selection()
    if primary_obj is not None and primary_obj not in selection:
        selection = [primary_obj] + selection
    selection = session._normalize_gui_object_selection(selection)

    provider_selection = session._normalize_gui_object_selection(session._provider_selected_objects)
    if obj in provider_selection:
        provider_selection = [selected for selected in provider_selection if selected != obj]
    else:
        provider_selection.append(obj)
    session._provider_selected_objects = session._normalize_gui_object_selection(provider_selection)
    new_selection = session._normalize_gui_object_selection(
        [selected for selected in selection if session._get_plan_target_for_object(selected)[0]]
    )

    if primary_obj is not None and primary_obj in new_selection:
        next_kind, next_obj = primary_kind, primary_obj
    else:
        next_kind, next_obj = session._get_first_plan_target_from_selection(new_selection)

    session._set_pending_selected_plan_target(next_kind, next_obj)
    plan_target_dispatch.clear_hovered_targets(session)
    session._set_gui_selection(new_selection)
    session._refresh_primary_selected_plan_target()
    session._claim_left_button_click(event_callback)
    return True


def toggle_plan_target_selection_at_position(session, mouse_pos, event_callback=None):
    node = session._get_edit_node(mouse_pos)
    if node and node[0] in ("provider_overlay_point", "provider_overlay_target"):
        target_kind, target_obj = session._get_provider_overlay_target_from_edit_node(node)
        if target_obj is not None and not session._is_valid_plan_target(
            target_kind,
            target_obj,
        ):
            return session._toggle_raw_plan_object_selection(target_obj, event_callback)
    else:
        target_kind, target_obj = session._get_plan_target_from_edit_node(node)
    if target_kind is None:
        target_kind, target_obj = session._get_plan_target_at_position(mouse_pos)
    if not target_kind or not target_obj:
        return False

    primary_kind, primary_obj = session._get_selected_plan_target()
    selection = session._get_gui_selection()
    if primary_obj is not None and primary_obj not in selection:
        selection = [primary_obj] + selection

    selection = session._normalize_gui_object_selection(selection)

    was_selected = target_obj in selection
    if was_selected:
        new_selection = [selected for selected in selection if selected != target_obj]
        if primary_obj == target_obj:
            next_kind, next_obj = session._get_first_plan_target_from_selection(new_selection)
        elif primary_obj is not None and primary_obj in new_selection:
            next_kind, next_obj = primary_kind, primary_obj
        else:
            next_kind, next_obj = session._get_first_plan_target_from_selection(new_selection)
    else:
        new_selection = list(selection)
        new_selection.append(target_obj)
        if primary_obj is not None and primary_obj in new_selection and primary_obj != target_obj:
            next_kind, next_obj = primary_kind, primary_obj
        else:
            next_kind, next_obj = target_kind, target_obj

    session._set_pending_selected_plan_target(next_kind, next_obj)
    plan_target_dispatch.clear_hovered_targets(session)
    session._set_gui_selection(new_selection)
    session._refresh_primary_selected_plan_target()
    session._claim_left_button_click(event_callback)
    return True
