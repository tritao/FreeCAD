# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection state helpers for BIM Plan Edit."""

from contextlib import contextmanager, nullcontext

import FreeCAD
import FreeCADGui
from . import provider_targets as plan_provider_targets


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
    session._gui_selection_sync_queued = False
    session._gui_selection_sync_generation += 1
    session._queued_gui_selection_object = None
    with session._plan_perf_trace_span("set_gui_selection"):
        with session._selection_changes_suppressed():
            try:
                with session._plan_perf_trace_span("set_gui_selection_clear"):
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
                    with session._plan_perf_trace_span("set_gui_selection_add"):
                        session._add_gui_selection_object(obj)
            except Exception:
                pass
        with session._plan_perf_trace_span("set_gui_selection_secondary_targets"):
            session._sync_secondary_selected_plan_targets_from_selection(selection)


def set_gui_selection_object(session, obj):
    if not obj:
        return
    session._set_gui_selection([obj])


def schedule_gui_selection_object(session, obj, delay_ms=80):
    if session._tearing_down or not obj:
        return
    session._gui_selection_sync_queued = True
    session._gui_selection_sync_generation += 1
    session._queued_gui_selection_object = obj
    generation = session._gui_selection_sync_generation
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(
            delay_ms,
            lambda generation=generation: session._run_scheduled_gui_selection_sync(generation),
        )
    except Exception:
        session._run_scheduled_gui_selection_sync(generation)


def run_scheduled_gui_selection_sync(session, generation=None):
    if not session._gui_selection_sync_queued:
        return
    if generation is not None and generation != session._gui_selection_sync_generation:
        return
    obj = session._queued_gui_selection_object
    if obj is None:
        session._gui_selection_sync_queued = False
        return
    with session._plan_perf_trace_event("scheduled_gui_selection_sync"):
        if session._tearing_down:
            session._gui_selection_sync_queued = False
            session._queued_gui_selection_object = None
            return
        set_gui_selection_object(session, obj)


def attach_selection_observer(session):
    if not session._selection_observer_added:
        FreeCADGui.Selection.addObserver(session)
        session._selection_observer_added = True


def detach_selection_observer(session):
    if session._selection_observer_added:
        FreeCADGui.Selection.removeObserver(session)
        session._selection_observer_added = False


def schedule_selection_refresh(session):
    if session._tearing_down or session._ignore_selection_changes:
        return
    if session._selection_refresh_queued:
        return
    session._selection_refresh_queued = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, session._run_scheduled_selection_refresh)
    except Exception:
        session._run_scheduled_selection_refresh()


def run_scheduled_selection_refresh(session):
    if not session._selection_refresh_queued:
        return
    session._selection_refresh_queued = False
    with session._plan_perf_trace_event("selection_observer_refresh"):
        if session._tearing_down or session._ignore_selection_changes:
            return
        session._refresh_primary_selected_plan_target()


def selection_observer_add(session, doc, obj, sub, point):
    with session._plan_perf_trace_event(
        "selection_observer_add",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        if sub in ("EditNode0", "EditNode1", "EditNode2"):
            return
        del doc, obj, sub, point
        session._schedule_selection_refresh()


def selection_observer_remove(session, doc, obj, sub):
    with session._plan_perf_trace_event(
        "selection_observer_remove",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        del doc, obj, sub
        session._schedule_selection_refresh()


def selection_observer_set(session, doc):
    with session._plan_perf_trace_event("selection_observer_set", selection_document=doc):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        del doc
        session._schedule_selection_refresh()


def selection_observer_clear(session, doc):
    selected_kind, selected_obj = session._get_selected_plan_target()
    with session._plan_perf_trace_event(
        "selection_observer_clear",
        selection_document=doc,
        selected_before_clear=session._plan_perf_describe_target(selected_kind, selected_obj),
        selected_before_clear_kind=selected_kind or "none",
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return
        del doc
        session._schedule_selection_refresh()


def selection_observer_set_preselection(session, doc, obj, sub):
    with session._plan_perf_trace_event(
        "selection_observer_set_preselection",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")
        if session._tearing_down:
            return
        if not _should_filter_hidden_provider_preselection(session, doc, obj):
            return
        session._plan_perf_count("provider_preselection_filtered")
        _clear_gui_preselection()


def selection_observer_remove_preselection(session, doc, obj, sub):
    with session._plan_perf_trace_event(
        "selection_observer_remove_preselection",
        selection_document=doc,
        selection_object=obj,
        selection_subelement=sub,
    ):
        session._plan_perf_count("selection_observer_callbacks")


def clear_hidden_provider_preselection(session):
    if session._tearing_down:
        return False
    preselected_obj = _get_gui_preselection_object(session)
    if preselected_obj is None:
        return False
    if not _should_filter_hidden_provider_preselection_for_object(session, preselected_obj):
        return False
    session._plan_perf_count("provider_preselection_cleared_for_mode")
    return _clear_gui_preselection()


def _should_filter_hidden_provider_preselection(session, doc_name, obj_name):
    preselected_obj = _resolve_document_object(session, doc_name, obj_name)
    if preselected_obj is None:
        return False
    return _should_filter_hidden_provider_preselection_for_object(session, preselected_obj)


def _should_filter_hidden_provider_preselection_for_object(session, obj):
    if not plan_provider_targets.is_plan_provider_target_object(session, obj):
        return False
    return not plan_provider_targets.is_plan_provider_target_visible_for_mode(session, obj)


def _should_preserve_provider_selected_target(session, kind, obj, selected):
    if kind != "provider" or obj is None or selected != obj:
        return False
    if not session._is_valid_plan_target(kind, obj):
        return False
    return bool(plan_provider_targets.is_plan_provider_target_visible_for_mode(session, obj))


def resolve_selected_target_for_gui_object(
    session,
    selected,
    *,
    pending_kind=None,
    pending_target=None,
    preserved_kind=None,
    preserved_target=None,
):
    if selected is None:
        return (None, None)
    if selected == pending_target and session._is_valid_plan_target(pending_kind, pending_target):
        return (pending_kind, pending_target)
    if _should_preserve_provider_selected_target(
        session,
        preserved_kind,
        preserved_target,
        selected,
    ):
        return (preserved_kind, preserved_target)
    return session._get_plan_target_for_object(selected)


def _resolve_document_object(session, document_name, object_name):
    object_name = str(object_name or "").strip()
    if not object_name:
        return None
    document_name = str(document_name or "").strip()
    doc = None
    if document_name:
        try:
            doc = FreeCAD.getDocument(document_name)
        except Exception:
            doc = None
    if doc is None:
        doc = getattr(session, "doc", None)
    if doc is None:
        return None
    try:
        return doc.getObject(object_name)
    except Exception:
        return None


def _get_gui_preselection_object(session):
    try:
        preselection = FreeCADGui.Selection.getPreselection()
    except Exception:
        return None
    try:
        obj = getattr(preselection, "Object", None)
    except Exception:
        obj = None
    if obj is not None:
        return obj
    return _resolve_document_object(
        session,
        getattr(preselection, "DocumentName", ""),
        getattr(preselection, "ObjectName", ""),
    )


def _clear_gui_preselection():
    try:
        FreeCADGui.Selection.clearPreselection()
        return True
    except Exception:
        return False


def refresh_selected_plan_target(session):
    with session._plan_perf_trace_span("refresh_selected_plan_target"):
        session._plan_perf_count("selection_refreshes")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return

        previous_kind, previous_obj = session._get_selected_plan_target()
        session._plan_perf_set_fields(
            selected_before=session._plan_perf_describe_target(previous_kind, previous_obj),
            selected_before_kind=previous_kind or "none",
        )
        previous_wall = session._get_plan_target_object_from_state(
            previous_kind, previous_obj, "wall"
        )
        if session._is_wall_edit_modal_active():
            session._set_selected_plan_target_state("wall", session._edit_wall)
            session._set_secondary_selected_plan_targets([])
            if session._selected_plan_target_changed(previous_kind, previous_obj, "wall"):
                session._sync_wall_grips()
            session._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
            return
        if session.current_tool == "Set Space Text":
            session._set_selected_plan_target_state(
                "space",
                session._edit_space if session._is_plan_space_object(session._edit_space) else None,
            )
            session._set_secondary_selected_plan_targets([])
            session._clear_wall_grips()
            session._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
            return
        if session.current_tool == "Join":
            wall = previous_wall
            if not session._is_plan_selectable_wall(wall):
                session.current_tool = "Select"
                wall = None
            session._set_selected_plan_target_state("wall", wall)
            session._set_secondary_selected_plan_targets([])
            session._clear_wall_grips()
            session._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
            return
        session._set_selected_plan_target_state()
        try:
            selection = FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            return
        session._plan_perf_count("gui_selection_size", len(selection or []))
        if session.current_tool in ("Select", "Pick Space Region") and selection:
            selected_targets = []
            pending_kind, pending_target = session._pending_selected_plan_target or (None, None)
            preserved_kind = previous_kind if previous_kind == "provider" else None
            preserved_target = previous_obj if preserved_kind else None
            provider_refresh_scope = (
                session._plan_provider_refresh_cache_scope()
                if hasattr(session, "_plan_provider_refresh_cache_scope")
                else nullcontext()
            )
            with provider_refresh_scope:
                for selected in selection:
                    target_kind, target_obj = resolve_selected_target_for_gui_object(
                        session,
                        selected,
                        pending_kind=pending_kind,
                        pending_target=pending_target,
                        preserved_kind=preserved_kind,
                        preserved_target=preserved_target,
                    )
                    if target_kind:
                        selected_targets.append((target_kind, target_obj))
            session._plan_perf_count("selected_targets_considered", len(selected_targets))

            matched_target = None
            if pending_target is not None:
                for target_kind, selected in selected_targets:
                    if selected == pending_target and target_kind == pending_kind:
                        matched_target = (target_kind, selected)
                        break
            if matched_target is None:
                for preferred_kind in ("opening", "symbol", "wall", "provider", "region", "space"):
                    matched_target = next(
                        (
                            (target_kind, selected)
                            for target_kind, selected in selected_targets
                            if target_kind == preferred_kind
                        ),
                        None,
                    )
                    if matched_target is not None:
                        break

            if matched_target is not None:
                target_kind, selected = matched_target
                session._set_selected_plan_target_state(target_kind, selected)
                session._set_secondary_selected_plan_targets(
                    selected_targets,
                    primary_kind=target_kind,
                    primary_obj=selected,
                )
                if len(selection) == 1 and target_kind not in ("space", "region"):
                    session._set_pending_selected_plan_target()
                else:
                    session._set_pending_selected_plan_target(target_kind, selected)
            else:
                session._set_secondary_selected_plan_targets([])
                session._set_pending_selected_plan_target()
        elif session.current_tool in ("Select", "Pick Space Region") and not selection:
            pending_kind, pending_target = session._consume_pending_selected_plan_target()
            session._set_selected_plan_target_state(pending_kind, pending_target)
            session._set_secondary_selected_plan_targets([])
        else:
            session._set_secondary_selected_plan_targets([])
            session._set_pending_selected_plan_target()
        if session._selected_plan_target_changed(previous_kind, previous_obj, "wall"):
            if session._get_selected_plan_target_object("wall"):
                session._schedule_wall_grip_sync()
            else:
                session._clear_wall_grips()
        session._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
        selected_kind, selected_obj = session._get_selected_plan_target()
        session._plan_perf_set_fields(
            selected_after=session._plan_perf_describe_target(selected_kind, selected_obj),
            selected_after_kind=selected_kind or "none",
            selection_refresh_cleared_target=bool(previous_kind and not selected_kind),
        )


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
        "provider": session._is_plan_provider_target_object,
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
