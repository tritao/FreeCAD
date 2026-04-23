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


def get_plan_target_object_from_state(state_kind, state_obj, kind):
    if state_kind == kind:
        return state_obj
    return None


def selected_plan_target_changed(session, previous_kind, previous_obj, kind=None):
    current_kind, current_obj = session._get_selected_plan_target()
    if kind is None:
        return previous_kind != current_kind or previous_obj != current_obj
    previous_target = session._get_plan_target_object_from_state(previous_kind, previous_obj, kind)
    current_target = session._get_plan_target_object_from_state(current_kind, current_obj, kind)
    return previous_target != current_target


def set_selected_plan_target(
    session,
    kind=None,
    obj=None,
    pending_restore=False,
    preserve_hovered_symbol_overlay=False,
):
    if session._is_valid_plan_target(kind, obj):
        session._set_selected_plan_target_state(kind, obj)
    else:
        session._set_selected_plan_target_state()
        kind = None
        obj = None
    session._sync_secondary_selected_plan_targets_from_gui_selection(
        primary_kind=kind,
        primary_obj=obj,
    )
    session._clear_plan_relation_status()
    session._sync_active_plan_target_object()
    if pending_restore:
        session._set_pending_selected_plan_target(kind, obj)
    else:
        session._set_pending_selected_plan_target()
    if not session._tearing_down:
        session._sync_junction_node_overlays()
        session._sync_selected_wall_opening_context_overlay()
        session._sync_hovered_wall_opening_context_overlay()
        session._sync_hovered_opening_overlay()
        if not preserve_hovered_symbol_overlay:
            session._sync_hovered_symbol_overlay()
        session._sync_hovered_space_overlay()
        session._sync_hovered_region_overlay()


def schedule_selected_wall_reset(session, reason, obj):
    del reason, obj
    if session._pending_selected_wall_reset or session._tearing_down:
        return
    session._pending_selected_wall_reset = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, session._reset_selected_wall_after_change)
    except Exception:
        session._reset_selected_wall_after_change()


def reset_selected_wall_after_change(session):
    session._pending_selected_wall_reset = False
    if session._tearing_down or session.current_tool != "Select":
        return
    wall = session._get_selected_plan_target_object("wall")
    if not wall:
        return
    session._clear_wall_grips()
    session._clear_selected_wall_overlay()
    session._clear_selected_plan_target_if_matches("wall", wall)
    session._set_gui_selection([])
    session._refresh_task_panel_status()


def suspend_selected_wall_state(session, wall=None, clear_gui_selection=True):
    if session._tearing_down:
        return
    if wall is None:
        wall = session._get_selected_plan_target_object("wall")
    if wall is None:
        return
    if not session._is_selected_plan_target("wall", wall):
        return
    session._pending_selected_wall_reset = False
    session._clear_wall_grips()
    session._clear_selected_wall_overlay()
    session._clear_selected_plan_target_if_matches("wall", wall)
    if clear_gui_selection:
        session._set_gui_selection([])
    session._refresh_task_panel_status(selection_only=True)


def sync_primary_selected_plan_target_visuals(session, previous_kind=None, previous_obj=None):
    with session._plan_perf_trace_span("sync_primary_selected_plan_target_visuals"):
        if session.current_tool != "Select" or session._selected_plan_target_changed(
            previous_kind, previous_obj, "wall"
        ):
            with session._plan_perf_trace_span("sync_selected_wall_overlay"):
                session._sync_selected_wall_overlay()
        with session._plan_perf_trace_span("sync_selected_wall_opening_context_overlay"):
            session._sync_selected_wall_opening_context_overlay()
        with session._plan_perf_trace_span("sync_hovered_wall_overlay"):
            session._sync_hovered_wall_overlay()
        with session._plan_perf_trace_span("sync_hovered_wall_opening_context_overlay"):
            session._sync_hovered_wall_opening_context_overlay()
        if session.current_tool != "Select" or session._selected_plan_target_changed(
            previous_kind, previous_obj, "opening"
        ):
            with session._plan_perf_trace_span("sync_selected_opening_overlay"):
                session._sync_selected_opening_overlay()
            with session._plan_perf_trace_span("sync_selected_opening_handles"):
                session._sync_selected_opening_handles()
        if session.current_tool != "Select" or session._selected_plan_target_changed(
            previous_kind, previous_obj, "symbol"
        ):
            with session._plan_perf_trace_span("sync_selected_symbol_overlay"):
                session._sync_selected_symbol_overlay()
            with session._plan_perf_trace_span("sync_selected_symbol_handles"):
                session._sync_selected_symbol_handles()
        if session.current_tool != "Select" or session._selected_plan_target_changed(
            previous_kind, previous_obj, "region"
        ):
            with session._plan_perf_trace_span("sync_selected_region_overlay"):
                session._sync_selected_region_overlay()
        if session.current_tool != "Select" or session._selected_plan_target_changed(
            previous_kind, previous_obj, "space"
        ):
            with session._plan_perf_trace_span("sync_selected_space_overlay"):
                session._sync_selected_space_overlay()
        with session._plan_perf_trace_span("sync_hovered_symbol_overlay"):
            session._sync_hovered_symbol_overlay()
        with session._plan_perf_trace_span("sync_hovered_provider_overlay"):
            session._sync_hovered_provider_overlay()
        with session._plan_perf_trace_span("sync_selected_provider_overlay"):
            session._sync_selected_provider_overlay()
        with session._plan_perf_trace_span("sync_selected_provider_handles"):
            session._sync_selected_provider_handles()
        with session._plan_perf_trace_span("sync_hovered_opening_overlay"):
            session._sync_hovered_opening_overlay()
        with session._plan_perf_trace_span("sync_hovered_space_overlay"):
            session._sync_hovered_space_overlay()
        with session._plan_perf_trace_span("sync_hovered_region_overlay"):
            session._sync_hovered_region_overlay()
        with session._plan_perf_trace_span("sync_secondary_selected_overlays"):
            session._sync_secondary_selected_overlays()
        with session._plan_perf_trace_span("sync_active_plan_target_object"):
            session._sync_active_plan_target_object()
        session._refresh_task_panel_status(selection_only=session.current_tool == "Select")


def refresh_primary_selected_plan_target(session):
    session._refresh_selected_plan_target()


def set_hovered_wall(session, wall):
    if session._is_selected_plan_target("wall", wall):
        wall = None
    if session.hovered_wall == wall:
        return
    session.hovered_wall = wall
    session._sync_junction_node_overlays()
    session._sync_hovered_wall_overlay()
    session._sync_hovered_wall_opening_context_overlay()
    if session.current_tool == "Join":
        session._refresh_task_panel_status(
            selection_only=session.current_tool == "Select"
            and session._is_selected_plan_target("wall")
        )


def set_hovered_opening(session, opening):
    if session._is_selected_plan_target("opening", opening):
        opening = None
    if session.hovered_opening == opening:
        return
    session.hovered_opening = opening
    session._sync_selected_wall_opening_context_overlay()
    session._sync_hovered_opening_overlay()


def set_hovered_symbol(session, symbol):
    if session._is_selected_plan_target("symbol", symbol):
        symbol = None
    if session.hovered_symbol == symbol:
        return
    session.hovered_symbol = symbol
    session._sync_hovered_symbol_overlay()


def set_hovered_provider(session, provider):
    if session._is_selected_plan_target("provider", provider):
        provider = None
    if session.hovered_provider == provider:
        return
    session.hovered_provider = provider
    session._sync_hovered_provider_overlay()


def set_hovered_space(session, space):
    if session._is_selected_plan_target("space", space):
        space = None
    if session.hovered_space == space:
        return
    session.hovered_space = space
    session._sync_hovered_space_overlay()


def set_hovered_region(session, region):
    if session._is_selected_plan_target("region", region):
        region = None
    if session.hovered_region == region:
        return
    session.hovered_region = region
    session._sync_hovered_region_overlay()


def queue_restore_selected_plan_target(session, kind, obj):
    if not obj:
        return
    queue_restore = {
        "opening": session._queue_restore_selected_opening,
        "symbol": session._queue_restore_selected_symbol,
        "region": session._queue_restore_selected_region,
        "space": session._queue_restore_selected_space,
    }.get(kind)
    if queue_restore is not None:
        queue_restore(obj)


def select_plan_target_for_plan_edit(
    session,
    kind,
    obj,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    validators = {
        "opening": session._is_hosted_opening_object,
        "provider": session._is_plan_provider_target_object,
        "symbol": session._is_plan_symbol_instance,
        "region": session._is_plan_region_object,
        "space": session._is_plan_space_object,
        "wall": session._is_plan_selectable_wall,
    }
    validator = validators.get(kind)
    if validator is None or not validator(obj):
        return False
    previous_kind, previous_obj = session._get_selected_plan_target()
    session.current_tool = "Select"
    session._provider_selected_objects = []
    preserve_hovered_symbol_overlay = (
        kind == "symbol" and session.hovered_symbol == obj and bool(session._symbol_hover_trackers)
    )
    session._set_selected_plan_target(
        kind,
        obj,
        pending_restore=queue_restore,
        preserve_hovered_symbol_overlay=preserve_hovered_symbol_overlay,
    )
    if sync_gui_selection:
        if defer_gui_selection:
            session._schedule_gui_selection_object(obj)
        else:
            session._set_gui_selection_object(obj)
    if kind == "wall":
        if defer_wall_grips:
            session._schedule_wall_grip_sync()
        else:
            session._sync_selected_wall_overlay()
            session._sync_wall_grips()
    else:
        session._clear_wall_grips()
        session._clear_selected_wall_overlay()
    if session._selected_plan_target_changed(previous_kind, previous_obj, "opening"):
        session._sync_selected_opening_overlay()
        session._sync_selected_opening_handles()
    if session._selected_plan_target_changed(previous_kind, previous_obj, "symbol"):
        session._sync_selected_symbol_overlay()
        session._sync_selected_symbol_handles()
    if session._selected_plan_target_changed(previous_kind, previous_obj, "region"):
        session._sync_selected_region_overlay()
    if session._selected_plan_target_changed(previous_kind, previous_obj, "space"):
        session._sync_selected_space_overlay()
    if session._selected_plan_target_changed(previous_kind, previous_obj, "provider"):
        session._sync_selected_provider_overlay()
        session._sync_selected_provider_handles()
    session._sync_secondary_selected_overlays()
    session._refresh_task_panel_status(selection_only=session.current_tool == "Select")
    if queue_restore:
        session._queue_restore_selected_plan_target(kind, obj)
    return True


def select_opening_for_plan_edit(
    session,
    opening,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return session._select_plan_target_for_plan_edit(
        "opening",
        opening,
        queue_restore=queue_restore,
        sync_gui_selection=sync_gui_selection,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def select_symbol_for_plan_edit(
    session,
    symbol,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return session._select_plan_target_for_plan_edit(
        "symbol",
        symbol,
        queue_restore=queue_restore,
        sync_gui_selection=sync_gui_selection,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def select_region_for_plan_edit(
    session,
    region,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return session._select_plan_target_for_plan_edit(
        "region",
        region,
        queue_restore=queue_restore,
        sync_gui_selection=sync_gui_selection,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def select_space_for_plan_edit(
    session,
    space,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return session._select_plan_target_for_plan_edit(
        "space",
        space,
        queue_restore=queue_restore,
        sync_gui_selection=sync_gui_selection,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def select_wall_for_plan_edit(
    session,
    wall,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return session._select_plan_target_for_plan_edit(
        "wall",
        wall,
        queue_restore=queue_restore,
        sync_gui_selection=sync_gui_selection,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def activate_plan_target(
    session,
    kind,
    mouse_pos,
    event_callback=None,
    sync_gui_selection=False,
    clear_hovered_kinds=None,
    resolved_target=None,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    if resolved_target is None:
        target_kind, target_obj = session._get_plan_target_at_position(mouse_pos)
    else:
        target_kind, target_obj = resolved_target
    with session._plan_perf_trace_span(
        f"activate_plan_target_{kind}", requested_kind=kind, mouse_pos=mouse_pos
    ):
        session._plan_perf_count(f"activate_plan_target_attempts_{kind}")
        session._plan_perf_set_fields(
            resolved_target=session._plan_perf_describe_target(target_kind, target_obj)
        )
        if target_kind != kind:
            target_obj = None
        select_target = {
            "opening": session._select_opening_for_plan_edit,
            "symbol": session._select_symbol_for_plan_edit,
            "region": session._select_region_for_plan_edit,
            "space": session._select_space_for_plan_edit,
            "wall": session._select_wall_for_plan_edit,
        }.get(kind)
        if select_target is None or not select_target(
            target_obj,
            queue_restore=True,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        ):
            session._plan_perf_set_fields(activate_plan_target_result=False)
            return False
        session._clear_hovered_plan_targets(clear_hovered_kinds)
        session._claim_left_button_click(event_callback)
        session._plan_perf_set_fields(
            activate_plan_target_result=True,
            activated_target=session._plan_perf_describe_target(kind, target_obj),
        )
        return True


def activate_semantic_plan_target(session, mouse_pos, event_callback=None):
    target_kind, target_obj = session._get_hovered_plan_target()
    if target_obj is None or session._hover_pick_dirty:
        target_kind, target_obj = session._get_plan_target_at_position(mouse_pos)
        source = "picked_after_throttled_hover" if session._hover_pick_dirty else "picked"
        session._hover_pick_dirty = False
        session._plan_perf_count(f"semantic_target_source_{source}")
        session._plan_perf_set_fields(semantic_target_source=source)
    else:
        session._plan_perf_count("semantic_target_source_hovered")
        session._plan_perf_set_fields(
            semantic_target_source="hovered",
            hovered_target=session._plan_perf_describe_target(target_kind, target_obj),
        )
    activate_target = {
        "opening": session._activate_opening_target,
        "symbol": session._activate_symbol_target,
        "region": session._activate_region_target,
        "space": session._activate_space_target,
        "wall": session._activate_wall_target,
    }.get(target_kind)
    if activate_target is None:
        return False
    if target_kind == "wall":
        return activate_target(
            mouse_pos,
            event_callback=event_callback,
            resolved_target=(target_kind, target_obj),
            defer_gui_selection=True,
            defer_wall_grips=True,
        )
    return activate_target(
        mouse_pos,
        event_callback=event_callback,
        resolved_target=(target_kind, target_obj),
    )


def activate_opening_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session._activate_plan_target(
        "opening",
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=True,
        clear_hovered_kinds=("wall", "opening", "symbol", "space", "region"),
        resolved_target=resolved_target,
    )


def activate_symbol_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session._activate_plan_target(
        "symbol",
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=True,
        clear_hovered_kinds=("wall", "opening", "symbol", "space", "region"),
        resolved_target=resolved_target,
    )


def activate_region_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session._activate_plan_target(
        "region",
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=True,
        clear_hovered_kinds=("wall", "opening", "symbol", "space", "region"),
        resolved_target=resolved_target,
    )


def activate_space_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session._activate_plan_target(
        "space",
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=True,
        clear_hovered_kinds=("wall", "opening", "symbol", "region"),
        resolved_target=resolved_target,
    )


def activate_wall_target(
    session,
    mouse_pos,
    event_callback=None,
    resolved_target=None,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return session._activate_plan_target(
        "wall",
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=True,
        clear_hovered_kinds=("wall", "symbol", "space", "region"),
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def clear_plan_selection_state(session):
    previous_kind, previous_obj = session._get_selected_plan_target()
    with session._plan_perf_trace_event(
        "clear_plan_selection_state",
        clear_selection_started_kind=previous_kind or "none",
        clear_selection_started_target=session._plan_perf_describe_target(
            previous_kind, previous_obj
        ),
    ):
        with session._plan_perf_trace_span("clear_plan_selection_gui_selection"):
            session._set_gui_selection([])
        with session._plan_perf_trace_span("clear_plan_selection_target_state"):
            session._set_selected_plan_target()
            session._provider_selected_objects = []
        with session._plan_perf_trace_span("clear_plan_selection_hover_state"):
            session._set_hovered_wall(None)
            session._set_hovered_opening(None)
            session._set_hovered_symbol(None)
            session._set_hovered_provider(None)
            session._set_hovered_space(None)
            session._set_hovered_region(None)
        with session._plan_perf_trace_span("clear_plan_selection_wall_grips"):
            session._clear_wall_grips()
            session._clear_selected_wall_overlay()
        with session._plan_perf_trace_span("clear_plan_selection_secondary_overlays"):
            session._sync_secondary_selected_overlays()
        with session._plan_perf_trace_span("clear_plan_selection_opening_overlay"):
            session._sync_selected_opening_overlay()
            session._sync_selected_opening_handles()
        with session._plan_perf_trace_span("clear_plan_selection_symbol_overlay"):
            session._sync_selected_symbol_overlay()
            session._sync_selected_symbol_handles()
        with session._plan_perf_trace_span("clear_plan_selection_region_overlay"):
            session._sync_selected_region_overlay()
        with session._plan_perf_trace_span("clear_plan_selection_space_overlay"):
            session._sync_selected_space_overlay()
        with session._plan_perf_trace_span("clear_plan_selection_provider_overlay"):
            session._sync_selected_provider_overlay()
            session._sync_selected_provider_handles()
        with session._plan_perf_trace_span("clear_plan_selection_task_status"):
            session._refresh_task_panel_status(selection_only=session.current_tool == "Select")
        selected_kind, selected_obj = session._get_selected_plan_target()
        session._plan_perf_set_fields(
            clear_selection_ended_kind=selected_kind or "none",
            clear_selection_ended_target=session._plan_perf_describe_target(
                selected_kind, selected_obj
            ),
            clear_selection_cleared_wall=bool(previous_kind == "wall" and not selected_kind),
        )


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
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    session._set_hovered_space(None)
    session._set_hovered_region(None)
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
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    session._set_hovered_space(None)
    session._set_hovered_region(None)
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
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    session._set_hovered_space(None)
    session._set_hovered_region(None)
    session._set_gui_selection(new_selection)
    session._refresh_primary_selected_plan_target()
    session._claim_left_button_click(event_callback)
    return True
