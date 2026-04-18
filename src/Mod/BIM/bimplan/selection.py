# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection state helpers for BIM Plan Edit."""

from contextlib import contextmanager

import FreeCADGui


def get_gui_selection_ex():
    try:
        return list(FreeCADGui.Selection.getSelectionEx() or [])
    except (ReferenceError, RuntimeError):
        return []


def get_gui_selection():
    try:
        return list(FreeCADGui.Selection.getSelection() or [])
    except (ReferenceError, RuntimeError):
        return []


@contextmanager
def selection_changes_suppressed(session):
    previous_ignore = session._ignore_selection_changes
    session._ignore_selection_changes = True
    try:
        yield
    finally:
        session._ignore_selection_changes = previous_ignore


def add_gui_selection_object(obj):
    if not obj:
        return
    doc_name = getattr(getattr(obj, "Document", None), "Name", None)
    obj_name = getattr(obj, "Name", None)
    try:
        if doc_name and obj_name:
            FreeCADGui.Selection.addSelection(doc_name, obj_name)
        else:
            FreeCADGui.Selection.addSelection(obj)
    except Exception:
        if doc_name and obj_name:
            try:
                FreeCADGui.Selection.addSelection(obj)
            except Exception:
                pass


def set_gui_selection(session, selection):
    with session._selection_changes_suppressed():
        try:
            FreeCADGui.Selection.clearSelection()
            seen = set()
            for obj in selection or []:
                if not obj:
                    continue
                key = (
                    getattr(getattr(obj, "Document", None), "Name", None),
                    getattr(obj, "Name", None),
                )
                if key in seen:
                    continue
                seen.add(key)
                session._add_gui_selection_object(obj)
        except Exception:
            pass
    session._sync_secondary_selected_plan_targets_from_selection(selection)


def set_gui_selection_object(session, obj):
    if not obj:
        return
    session._set_gui_selection([obj])


def get_selected_target_for_kind(session, kind):
    if getattr(session, "_selected_plan_target_kind", None) == kind:
        return getattr(session, "_selected_plan_target_obj", None)
    return None


def set_selected_target_for_kind(session, kind, obj):
    if obj is None:
        if getattr(session, "_selected_plan_target_kind", None) == kind:
            session._selected_plan_target_kind = None
            session._selected_plan_target_obj = None
        return
    session._selected_plan_target_kind = kind
    session._selected_plan_target_obj = obj


def get_selected_plan_target_state(session, primary_kinds):
    kind = getattr(session, "_selected_plan_target_kind", None)
    obj = getattr(session, "_selected_plan_target_obj", None)
    if kind not in primary_kinds or obj is None:
        return (None, None)
    return (kind, obj)


def set_selected_plan_target_state(session, primary_kinds, kind=None, obj=None):
    if kind not in primary_kinds or obj is None:
        kind = None
        obj = None
    session._selected_plan_target_kind = kind
    session._selected_plan_target_obj = obj


def get_selected_plan_target_object(session, kind=None):
    selected_kind, selected_obj = session._get_selected_plan_target()
    if kind is not None and selected_kind != kind:
        return None
    return selected_obj


def is_selected_plan_target(session, kind, obj=None):
    selected_kind, selected_obj = session._get_selected_plan_target()
    if selected_kind != kind:
        return False
    if obj is None:
        return selected_obj is not None
    return selected_obj == obj


def clear_selected_plan_target_if_matches(session, kind, obj):
    if not session._is_selected_plan_target(kind, obj):
        return False
    session._set_selected_plan_target_state()
    return True


def is_valid_plan_target(session, kind, obj):
    validators = {
        "opening": session._is_hosted_opening_object,
        "symbol": session._is_plan_symbol_instance,
        "region": session._is_plan_region_object,
        "space": session._is_plan_space_object,
        "wall": session._is_plan_selectable_wall,
    }
    validator = validators.get(kind)
    return bool(validator is not None and validator(obj))


def set_pending_selected_plan_target(session, kind=None, obj=None):
    if is_valid_plan_target(session, kind, obj):
        session._pending_selected_plan_target = (kind, obj)
        return
    session._pending_selected_plan_target = None


def consume_pending_selected_plan_target(session):
    pending_target = session._pending_selected_plan_target
    session._pending_selected_plan_target = None
    if not pending_target:
        return (None, None)
    kind, obj = pending_target
    if is_valid_plan_target(session, kind, obj):
        return (kind, obj)
    return (None, None)


def get_selected_plan_target(session):
    session._sanitize_plan_target_references()
    kind, obj = session._get_selected_plan_target_state()
    if session._is_valid_plan_target(kind, obj):
        return (kind, obj)
    if kind is not None or obj is not None:
        session._set_selected_plan_target_state()
    return (None, None)


def get_first_plan_target_from_selection(session, selection):
    for selected in selection or []:
        target_kind, target_obj = session._get_plan_target_for_object(selected)
        if target_kind and target_obj:
            return (target_kind, target_obj)
    return (None, None)


def get_plan_target_state_key(kind, obj):
    if not kind or not obj:
        return None
    return (
        kind,
        getattr(getattr(obj, "Document", None), "Name", None),
        getattr(obj, "Name", None),
    )


def normalize_plan_target_list(session, targets):
    normalized = []
    seen = set()
    for target in targets or []:
        try:
            target_kind, target_obj = target
        except Exception:
            continue
        if not session._is_valid_plan_target(target_kind, target_obj):
            continue
        key = session._get_plan_target_state_key(target_kind, target_obj)
        if key is None or key in seen:
            continue
        seen.add(key)
        normalized.append((target_kind, target_obj))
    return normalized


def normalize_plan_targets_from_selection(session, selection):
    return session._normalize_plan_target_list(
        [
            (target_kind, target_obj)
            for target_kind, target_obj in (
                session._get_plan_target_for_object(selected) for selected in (selection or [])
            )
            if target_kind and target_obj
        ]
    )


def set_secondary_selected_plan_targets(session, targets, primary_kind=None, primary_obj=None):
    if primary_kind is None and primary_obj is None:
        primary_kind, primary_obj = session._get_selected_plan_target()
    normalized = []
    for target_kind, target_obj in session._normalize_plan_target_list(targets):
        if target_kind == primary_kind and target_obj == primary_obj:
            continue
        normalized.append((target_kind, target_obj))
    session._secondary_selected_plan_targets_state = normalized


def sync_secondary_selected_plan_targets_from_selection(
    session, selection, primary_kind=None, primary_obj=None
):
    session._set_secondary_selected_plan_targets(
        session._normalize_plan_targets_from_selection(selection),
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )


def sync_secondary_selected_plan_targets_from_gui_selection(
    session, primary_kind=None, primary_obj=None
):
    session._sync_secondary_selected_plan_targets_from_selection(
        session._get_gui_selection(),
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )


def get_secondary_selected_plan_targets(session):
    session._sanitize_plan_target_references()
    primary_kind, primary_obj = session._get_selected_plan_target()
    session._set_secondary_selected_plan_targets(
        getattr(session, "_secondary_selected_plan_targets_state", []),
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )
    return list(getattr(session, "_secondary_selected_plan_targets_state", []))


def get_selected_plan_targets(session):
    primary_kind, primary_obj = session._get_selected_plan_target()
    targets = []
    seen = set()
    if primary_kind and primary_obj:
        key = session._get_plan_target_state_key(primary_kind, primary_obj)
        seen.add(key)
        targets.append((primary_kind, primary_obj))
    for target_kind, target_obj in session._get_secondary_selected_plan_targets():
        key = session._get_plan_target_state_key(target_kind, target_obj)
        if key in seen:
            continue
        seen.add(key)
        targets.append((target_kind, target_obj))
    return targets
