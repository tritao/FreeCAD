# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection state helpers for BIM Plan Edit."""

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass

import FreeCADGui
from bimplan.providers import runtime as plan_provider_runtime
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds

_PRIMARY_SELECTED_TARGET_PRIORITY = {
    kind: index
    for index, kind in enumerate(plan_target_kinds.PRIMARY_SELECTED_TARGET_PRIORITY_KINDS)
}
_GUI_SELECTION_TOOL_NAMES = ("Select", "Pick Space Region")
_PENDING_TARGET_UNCHANGED = object()
_WALL_GRIP_NONE = "none"
_WALL_GRIP_CLEAR = "clear"
_WALL_GRIP_SYNC = "sync"
_MISSING = object()


@dataclass(frozen=True)
class SelectionRefreshResult:
    primary_kind: object = None
    primary_obj: object = None
    secondary_targets: tuple = ()
    pending_target: object = _PENDING_TARGET_UNCHANGED
    wall_grip_action: str = _WALL_GRIP_NONE


@dataclass(frozen=True)
class TargetActivationBehavior:
    select_method_name: str
    clear_hovered_kinds: tuple[str, ...]
    sync_gui_selection: bool = True
    defer_gui_selection: bool = False
    defer_wall_grips: bool = False


def _make_select_plan_target_function(kind):
    def _select_plan_target(
        session,
        obj,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return session._select_plan_target_for_plan_edit(
            kind,
            obj,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    return _select_plan_target


def _make_set_hovered_target_function(kind):
    def _set_hovered_target(session, obj):
        return plan_target_dispatch.set_hovered_target(session, kind, obj)

    return _set_hovered_target


def _supports_native_selection_state(session):
    return callable(getattr(session, "_sanitize_plan_target_references", None))


def _get_selection_api(session):
    return getattr(session, "selection", None)


def _call_legacy_selection_method(session, method_name, *args):
    legacy_method = getattr(session, method_name, None)
    if callable(legacy_method):
        return legacy_method(*args)
    return _MISSING


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


def _choose_primary_selected_target(selected_targets, pending_kind=None, pending_target=None):
    if pending_kind is not None and pending_target is not None:
        for target_kind, target_obj in selected_targets:
            if target_kind == pending_kind and target_obj == pending_target:
                return (target_kind, target_obj)
    if not selected_targets:
        return (None, None)
    target_kind, target_obj = min(
        selected_targets,
        key=lambda item: _PRIMARY_SELECTED_TARGET_PRIORITY.get(
            item[0], len(_PRIMARY_SELECTED_TARGET_PRIORITY)
        ),
    )
    return (target_kind, target_obj)


def _apply_selection_refresh_result(session, refresh_result):
    session._set_selected_plan_target_state(
        refresh_result.primary_kind,
        refresh_result.primary_obj,
    )
    session._set_secondary_selected_plan_targets(
        refresh_result.secondary_targets,
        primary_kind=refresh_result.primary_kind,
        primary_obj=refresh_result.primary_obj,
    )
    if refresh_result.pending_target is not _PENDING_TARGET_UNCHANGED:
        if refresh_result.pending_target is None:
            session._set_pending_selected_plan_target()
        else:
            session._set_pending_selected_plan_target(*refresh_result.pending_target)
    if refresh_result.wall_grip_action == _WALL_GRIP_CLEAR:
        session.overlays.clear_wall_grips()
    elif refresh_result.wall_grip_action == _WALL_GRIP_SYNC:
        session.overlays.sync_wall_grips()


def _resolve_direct_selection_refresh_result(session, previous_wall):
    if session.wall_edit.is_wall_edit_modal_active():
        return SelectionRefreshResult(
            primary_kind=plan_target_kinds.PLAN_TARGET_WALL,
            primary_obj=session._edit_wall,
            wall_grip_action=_WALL_GRIP_SYNC,
        )
    if session.current_tool == "Set Space Text":
        return SelectionRefreshResult(
            primary_kind=plan_target_kinds.PLAN_TARGET_SPACE,
            primary_obj=(
                session._edit_space if session._is_plan_space_object(session._edit_space) else None
            ),
            wall_grip_action=_WALL_GRIP_CLEAR,
        )
    if session.current_tool == "Join":
        wall = previous_wall
        if not session._is_plan_selectable_wall(wall):
            session.current_tool = "Select"
            wall = None
        return SelectionRefreshResult(
            primary_kind=plan_target_kinds.PLAN_TARGET_WALL,
            primary_obj=wall,
            wall_grip_action=_WALL_GRIP_CLEAR,
        )
    if session.current_tool not in _GUI_SELECTION_TOOL_NAMES:
        return SelectionRefreshResult(pending_target=None)
    return None


def _collect_selected_targets_from_gui_selection(session, selection, previous_kind, previous_obj):
    selected_targets = []
    pending_kind, pending_target = session._pending_selected_plan_target or (None, None)
    preserved_kind = (
        previous_kind if previous_kind == plan_target_kinds.PLAN_TARGET_PROVIDER else None
    )
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
    return selected_targets, pending_kind, pending_target


def _resolve_gui_selection_refresh_result(session, selection, previous_kind, previous_obj):
    if not selection:
        pending_kind, pending_target = session._consume_pending_selected_plan_target()
        return SelectionRefreshResult(
            primary_kind=pending_kind,
            primary_obj=pending_target,
        )

    selected_targets, pending_kind, pending_target = _collect_selected_targets_from_gui_selection(
        session,
        selection,
        previous_kind,
        previous_obj,
    )
    target_kind, target_obj = _choose_primary_selected_target(
        selected_targets,
        pending_kind=pending_kind,
        pending_target=pending_target,
    )
    if target_kind is None:
        return SelectionRefreshResult(pending_target=None)
    pending_selection = (target_kind, target_obj)
    if len(selection) == 1 and target_kind not in (
        plan_target_kinds.PLAN_TARGET_SPACE,
        plan_target_kinds.PLAN_TARGET_REGION,
    ):
        pending_selection = None
    return SelectionRefreshResult(
        primary_kind=target_kind,
        primary_obj=target_obj,
        secondary_targets=tuple(selected_targets),
        pending_target=pending_selection,
    )


def refresh_selected_plan_target(session):
    with session._plan_perf_trace_span("refresh_selected_plan_target"):
        session._plan_perf_count("selection_refreshes")
        if session._tearing_down:
            return
        if session._ignore_selection_changes:
            return

        previous_kind, previous_obj = get_selected_plan_target(session)
        session._plan_perf_set_fields(
            selected_before=session._plan_perf_describe_target(previous_kind, previous_obj),
            selected_before_kind=previous_kind or "none",
        )
        previous_wall = session._get_plan_target_object_from_state(
            previous_kind,
            previous_obj,
            plan_target_kinds.PLAN_TARGET_WALL,
        )

        refresh_result = _resolve_direct_selection_refresh_result(session, previous_wall)
        if refresh_result is None:
            try:
                selection = FreeCADGui.Selection.getSelection()
            except (ReferenceError, RuntimeError):
                session._set_selected_plan_target_state()
                return
            session._plan_perf_count("gui_selection_size", len(selection or []))
            refresh_result = _resolve_gui_selection_refresh_result(
                session,
                selection,
                previous_kind,
                previous_obj,
            )

        _apply_selection_refresh_result(session, refresh_result)
        if (
            refresh_result.wall_grip_action == _WALL_GRIP_NONE
            and session._selected_plan_target_changed(
                previous_kind,
                previous_obj,
                plan_target_kinds.PLAN_TARGET_WALL,
            )
        ):
            if get_selected_plan_target_object(session, plan_target_kinds.PLAN_TARGET_WALL):
                session._schedule_wall_grip_sync()
            else:
                session.overlays.clear_wall_grips()
        session._sync_primary_selected_plan_target_visuals(previous_kind, previous_obj)
        selected_kind, selected_obj = get_selected_plan_target(session)
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
    if not _supports_native_selection_state(session):
        selection_api = _get_selection_api(session)
        if selection_api is not None:
            return selection_api.get_selected_plan_target_object(kind)
        legacy_target_object = _call_legacy_selection_method(
            session,
            "_get_selected_plan_target_object",
            kind,
        )
        if legacy_target_object is not _MISSING:
            return legacy_target_object
        return None
    selected_kind, selected_obj = get_selected_plan_target(session)
    if kind is not None and selected_kind != kind:
        return None
    return selected_obj


def is_selected_plan_target(session, kind, obj=None):
    selected_kind, selected_obj = get_selected_plan_target(session)
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
    return plan_target_dispatch.validate_plan_target(session, kind, obj)


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
    if not _supports_native_selection_state(session):
        selection_api = _get_selection_api(session)
        if selection_api is not None:
            return selection_api.get_selected_plan_target()
        legacy_target = _call_legacy_selection_method(session, "_get_selected_plan_target")
        if legacy_target is not _MISSING:
            return legacy_target
        return (None, None)
    session._sanitize_plan_target_references()
    kind, obj = get_selected_plan_target_state(session, plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS)
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
        primary_kind, primary_obj = get_selected_plan_target(session)
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
    if not _supports_native_selection_state(session):
        selection_api = _get_selection_api(session)
        if selection_api is not None:
            return selection_api.get_secondary_selected_plan_targets()
        legacy_targets = _call_legacy_selection_method(
            session,
            "_get_secondary_selected_plan_targets",
        )
        if legacy_targets is not _MISSING:
            return legacy_targets
        return []
    session._sanitize_plan_target_references()
    primary_kind, primary_obj = get_selected_plan_target(session)
    session._set_secondary_selected_plan_targets(
        getattr(session, "_secondary_selected_plan_targets_state", []),
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )
    return list(getattr(session, "_secondary_selected_plan_targets_state", []))


def get_selected_plan_targets(session):
    if not _supports_native_selection_state(session):
        selection_api = _get_selection_api(session)
        if selection_api is not None:
            return selection_api.get_selected_plan_targets()
        legacy_targets = _call_legacy_selection_method(session, "_get_selected_plan_targets")
        if legacy_targets is not _MISSING:
            return legacy_targets
        return []
    primary_kind, primary_obj = get_selected_plan_target(session)
    targets = []
    seen = set()
    if primary_kind and primary_obj:
        key = session._get_plan_target_state_key(primary_kind, primary_obj)
        seen.add(key)
        targets.append((primary_kind, primary_obj))
    for target_kind, target_obj in get_secondary_selected_plan_targets(session):
        key = session._get_plan_target_state_key(target_kind, target_obj)
        if key in seen:
            continue
        seen.add(key)
        targets.append((target_kind, target_obj))
    return targets


def normalize_gui_object_selection(session, selection):
    if not _supports_native_selection_state(session):
        selection_api = _get_selection_api(session)
        if selection_api is not None:
            return selection_api.normalize_gui_object_selection(selection)
    del session
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


def get_plan_target_object_from_state(state_kind, state_obj, kind):
    if state_kind == kind:
        return state_obj
    return None


def selected_plan_target_changed(session, previous_kind, previous_obj, kind=None):
    current_kind, current_obj = get_selected_plan_target(session)
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
        session.overlays.sync_junction_node_overlays()
        session.overlays.sync_selected_wall_opening_context_overlay()
        session.overlays.sync_hovered_wall_opening_context_overlay()
        plan_target_dispatch.sync_hovered_target_visuals(
            session,
            kinds=(plan_target_kinds.PLAN_TARGET_OPENING,),
        )
        if not preserve_hovered_symbol_overlay:
            plan_target_dispatch.sync_hovered_target_visuals(
                session,
                kinds=(plan_target_kinds.PLAN_TARGET_SYMBOL,),
            )
        plan_target_dispatch.sync_hovered_target_visuals(
            session,
            kinds=(
                plan_target_kinds.PLAN_TARGET_SPACE,
                plan_target_kinds.PLAN_TARGET_REGION,
            ),
        )


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
    wall = get_selected_plan_target_object(session, "wall")
    if not wall:
        return
    session.overlays.clear_wall_grips()
    session.overlays.clear_selected_wall_overlay()
    session._clear_selected_plan_target_if_matches("wall", wall)
    session._set_gui_selection([])
    session._refresh_task_panel_status()


def suspend_selected_wall_state(session, wall=None, clear_gui_selection=True):
    if session._tearing_down:
        return
    if wall is None:
        wall = get_selected_plan_target_object(session, "wall")
    if wall is None:
        return
    if not session._is_selected_plan_target("wall", wall):
        return
    session._pending_selected_wall_reset = False
    session.overlays.clear_wall_grips()
    session.overlays.clear_selected_wall_overlay()
    session._clear_selected_plan_target_if_matches("wall", wall)
    if clear_gui_selection:
        session._set_gui_selection([])
    session._refresh_task_panel_status(selection_only=True)


def sync_primary_selected_plan_target_visuals(session, previous_kind=None, previous_obj=None):
    with session._plan_perf_trace_span("sync_primary_selected_plan_target_visuals"):
        if session.current_tool != "Select" or session._selected_plan_target_changed(
            previous_kind,
            previous_obj,
            plan_target_kinds.PLAN_TARGET_WALL,
        ):
            with session._plan_perf_trace_span("sync_selected_wall_overlay"):
                session.overlays.sync_selected_wall_overlay()
        with session._plan_perf_trace_span("sync_selected_wall_opening_context_overlay"):
            session.overlays.sync_selected_wall_opening_context_overlay()
        with session._plan_perf_trace_span("sync_hovered_wall_overlay"):
            session.overlays.sync_hovered_wall_overlay()
        with session._plan_perf_trace_span("sync_hovered_wall_opening_context_overlay"):
            session.overlays.sync_hovered_wall_opening_context_overlay()
        plan_target_dispatch.sync_selected_target_visuals(
            session,
            kinds=plan_target_kinds.PRIMARY_SELECTED_VISUAL_SYNC_KINDS,
            previous_kind=previous_kind,
            previous_obj=previous_obj,
            trace_style="by_method",
        )
        plan_target_dispatch.sync_hovered_target_visuals(
            session,
            kinds=(
                plan_target_kinds.PLAN_TARGET_SYMBOL,
                plan_target_kinds.PLAN_TARGET_PROVIDER,
            ),
            trace_style="by_method",
        )
        plan_target_dispatch.sync_selected_target_visuals(
            session,
            kinds=(plan_target_kinds.PLAN_TARGET_PROVIDER,),
            force=True,
            trace_style="by_method",
        )
        plan_target_dispatch.sync_hovered_target_visuals(
            session,
            kinds=(
                plan_target_kinds.PLAN_TARGET_OPENING,
                plan_target_kinds.PLAN_TARGET_SPACE,
                plan_target_kinds.PLAN_TARGET_REGION,
            ),
            trace_style="by_method",
        )
        with session._plan_perf_trace_span("sync_secondary_selected_overlays"):
            session.overlays.sync_secondary_selected_overlays()
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
    session.overlays.sync_junction_node_overlays()
    session.overlays.sync_hovered_wall_overlay()
    session.overlays.sync_hovered_wall_opening_context_overlay()
    if session.current_tool == "Join":
        session._refresh_task_panel_status(
            selection_only=session.current_tool == "Select"
            and session._is_selected_plan_target("wall")
        )


set_hovered_opening = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_OPENING)


set_hovered_symbol = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_SYMBOL)


set_hovered_provider = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_PROVIDER)


set_hovered_space = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_SPACE)


set_hovered_region = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_REGION)


def queue_restore_selected_plan_target(session, kind, obj):
    plan_target_dispatch.queue_restore_selected_target(session, kind, obj)


def select_plan_target_for_plan_edit(
    session,
    kind,
    obj,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    if not plan_target_dispatch.validate_plan_target(session, kind, obj):
        return False
    previous_kind, previous_obj = get_selected_plan_target(session)
    session.current_tool = "Select"
    session._provider_selected_objects = []
    preserve_hovered_symbol_overlay = (
        kind == plan_target_kinds.PLAN_TARGET_SYMBOL
        and session.hovered_symbol == obj
        and bool(session._symbol_hover_trackers)
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
    if kind == plan_target_kinds.PLAN_TARGET_WALL:
        if defer_wall_grips:
            session._schedule_wall_grip_sync()
        else:
            session.overlays.sync_selected_wall_overlay()
            session.overlays.sync_wall_grips()
    else:
        session.overlays.clear_wall_grips()
        session.overlays.clear_selected_wall_overlay()
    plan_target_dispatch.sync_selected_target_visuals(
        session,
        kinds=plan_target_kinds.CLEAR_PLAN_SELECTION_VISUAL_KINDS,
        previous_kind=previous_kind,
        previous_obj=previous_obj,
    )
    session.overlays.sync_secondary_selected_overlays()
    session._refresh_task_panel_status(selection_only=session.current_tool == "Select")
    if queue_restore:
        session._queue_restore_selected_plan_target(kind, obj)
    return True


select_opening_for_plan_edit = _make_select_plan_target_function(
    plan_target_kinds.PLAN_TARGET_OPENING
)


select_symbol_for_plan_edit = _make_select_plan_target_function(
    plan_target_kinds.PLAN_TARGET_SYMBOL
)


select_region_for_plan_edit = _make_select_plan_target_function(
    plan_target_kinds.PLAN_TARGET_REGION
)


select_space_for_plan_edit = _make_select_plan_target_function(plan_target_kinds.PLAN_TARGET_SPACE)


select_wall_for_plan_edit = _make_select_plan_target_function(plan_target_kinds.PLAN_TARGET_WALL)


_TARGET_ACTIVATION_BEHAVIORS = {
    plan_target_kinds.PLAN_TARGET_OPENING: TargetActivationBehavior(
        select_method_name="_select_opening_for_plan_edit",
        clear_hovered_kinds=plan_target_kinds.SEMANTIC_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_SYMBOL: TargetActivationBehavior(
        select_method_name="_select_symbol_for_plan_edit",
        clear_hovered_kinds=plan_target_kinds.SEMANTIC_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_REGION: TargetActivationBehavior(
        select_method_name="_select_region_for_plan_edit",
        clear_hovered_kinds=plan_target_kinds.SEMANTIC_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_SPACE: TargetActivationBehavior(
        select_method_name="_select_space_for_plan_edit",
        clear_hovered_kinds=plan_target_kinds.SPACE_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_WALL: TargetActivationBehavior(
        select_method_name="_select_wall_for_plan_edit",
        clear_hovered_kinds=plan_target_kinds.WALL_TARGET_CLEAR_HOVERED_KINDS,
    ),
}


def _get_target_activation_behavior(kind):
    return _TARGET_ACTIVATION_BEHAVIORS.get(kind)


def _activate_configured_plan_target(
    session,
    kind,
    mouse_pos,
    event_callback=None,
    resolved_target=None,
    *,
    defer_gui_selection=None,
    defer_wall_grips=None,
):
    behavior = _get_target_activation_behavior(kind)
    if behavior is None:
        return False
    if defer_gui_selection is None:
        defer_gui_selection = behavior.defer_gui_selection
    if defer_wall_grips is None:
        defer_wall_grips = behavior.defer_wall_grips
    return session._activate_plan_target(
        kind,
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=behavior.sync_gui_selection,
        clear_hovered_kinds=behavior.clear_hovered_kinds,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def activate_plan_target_for_kind(
    session,
    kind,
    mouse_pos,
    event_callback=None,
    resolved_target=None,
    *,
    defer_gui_selection=None,
    defer_wall_grips=None,
):
    return _activate_configured_plan_target(
        session,
        kind,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
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
        behavior = _get_target_activation_behavior(kind)
        select_target = getattr(session, behavior.select_method_name, None) if behavior else None
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
    if _get_target_activation_behavior(target_kind) is None:
        return False
    if target_kind == plan_target_kinds.PLAN_TARGET_WALL:
        return _activate_configured_plan_target(
            session,
            target_kind,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=(target_kind, target_obj),
            defer_gui_selection=True,
            defer_wall_grips=True,
        )
    return _activate_configured_plan_target(
        session,
        target_kind,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=(target_kind, target_obj),
    )


def activate_opening_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return activate_plan_target_for_kind(
        session,
        plan_target_kinds.PLAN_TARGET_OPENING,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_symbol_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return activate_plan_target_for_kind(
        session,
        plan_target_kinds.PLAN_TARGET_SYMBOL,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_region_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return activate_plan_target_for_kind(
        session,
        plan_target_kinds.PLAN_TARGET_REGION,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_space_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return activate_plan_target_for_kind(
        session,
        plan_target_kinds.PLAN_TARGET_SPACE,
        mouse_pos,
        event_callback=event_callback,
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
    return activate_plan_target_for_kind(
        session,
        plan_target_kinds.PLAN_TARGET_WALL,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def clear_plan_selection_state(session):
    previous_kind, previous_obj = get_selected_plan_target(session)
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
            plan_target_dispatch.clear_hovered_targets(session)
        with session._plan_perf_trace_span("clear_plan_selection_wall_grips"):
            session.overlays.clear_wall_grips()
            session.overlays.clear_selected_wall_overlay()
        with session._plan_perf_trace_span("clear_plan_selection_secondary_overlays"):
            session.overlays.sync_secondary_selected_overlays()
        plan_target_dispatch.sync_selected_target_visuals(
            session,
            kinds=plan_target_kinds.CLEAR_PLAN_SELECTION_VISUAL_KINDS,
            force=True,
            trace_style="by_kind",
            trace_prefix="clear_plan_selection",
        )
        with session._plan_perf_trace_span("clear_plan_selection_task_status"):
            session._refresh_task_panel_status(selection_only=session.current_tool == "Select")
        selected_kind, selected_obj = get_selected_plan_target(session)
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
    plan_target_dispatch.clear_hovered_targets(session)
    session._set_gui_selection_object(target_obj)
    session._refresh_primary_selected_plan_target()
    session._claim_left_button_click(event_callback)
    return True


def toggle_raw_plan_object_selection(session, obj, event_callback=None):
    if obj is None:
        return False

    primary_kind, primary_obj = session.selection.get_selected_plan_target()
    selection = session._get_gui_selection()
    if primary_obj is not None and primary_obj not in selection:
        selection = [primary_obj] + selection
    selection = normalize_gui_object_selection(session, selection)

    provider_selection = normalize_gui_object_selection(session, session._provider_selected_objects)
    if obj in provider_selection:
        provider_selection = [selected for selected in provider_selection if selected != obj]
    else:
        provider_selection.append(obj)
    session._provider_selected_objects = normalize_gui_object_selection(session, provider_selection)
    new_selection = normalize_gui_object_selection(
        session,
        [selected for selected in selection if session._get_plan_target_for_object(selected)[0]],
    )

    if primary_obj is not None and primary_obj in new_selection:
        next_kind, next_obj = primary_kind, primary_obj
    else:
        next_kind, next_obj = session.selection.get_first_plan_target_from_selection(new_selection)

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

    primary_kind, primary_obj = session.selection.get_selected_plan_target()
    selection = session._get_gui_selection()
    if primary_obj is not None and primary_obj not in selection:
        selection = [primary_obj] + selection

    selection = normalize_gui_object_selection(session, selection)

    was_selected = target_obj in selection
    if was_selected:
        new_selection = [selected for selected in selection if selected != target_obj]
        if primary_obj == target_obj:
            next_kind, next_obj = session.selection.get_first_plan_target_from_selection(
                new_selection
            )
        elif primary_obj is not None and primary_obj in new_selection:
            next_kind, next_obj = primary_kind, primary_obj
        else:
            next_kind, next_obj = session.selection.get_first_plan_target_from_selection(
                new_selection
            )
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


@contextmanager
def selection_changes_suppressed(session):
    previous_ignore = session._ignore_selection_changes
    session._ignore_selection_changes = True
    try:
        yield
    finally:
        session._ignore_selection_changes = previous_ignore


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
    selected_kind, selected_obj = session.selection.get_selected_plan_target()
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


def _should_filter_hidden_provider_preselection(session, doc_name, obj_name):
    preselected_obj = _resolve_document_object(session, doc_name, obj_name)
    if preselected_obj is None:
        return False
    return _should_filter_hidden_provider_preselection_for_object(session, preselected_obj)


def _should_filter_hidden_provider_preselection_for_object(session, obj):
    if not plan_provider_runtime.is_plan_provider_target_object(session, obj):
        return False
    return not plan_provider_runtime.is_plan_provider_target_visible_for_mode(session, obj)


def _should_preserve_provider_selected_target(session, kind, obj, selected):
    if kind != "provider" or obj is None or selected != obj:
        return False
    if not session._is_valid_plan_target(kind, obj):
        return False
    return bool(plan_provider_runtime.is_plan_provider_target_visible_for_mode(session, obj))


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


from functools import wraps


def _bind_session_call(func):
    @wraps(func)
    def method(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    return method


_PLAN_SELECTION_API_BOUND_METHODS = (
    "get_selected_target_for_kind",
    "set_selected_target_for_kind",
    "get_selected_plan_target_object",
    "is_selected_plan_target",
    "clear_selected_plan_target_if_matches",
    "clear_hidden_provider_preselection",
    "selected_plan_target_changed",
    "set_pending_selected_plan_target",
    "consume_pending_selected_plan_target",
    "get_selected_plan_target",
    "get_first_plan_target_from_selection",
    "is_valid_plan_target",
    "normalize_plan_target_list",
    "normalize_plan_targets_from_selection",
    "set_secondary_selected_plan_targets",
    "sync_secondary_selected_plan_targets_from_selection",
    "sync_secondary_selected_plan_targets_from_gui_selection",
    "get_secondary_selected_plan_targets",
    "get_selected_plan_targets",
    "set_selected_plan_target",
    "schedule_selected_wall_reset",
    "reset_selected_wall_after_change",
    "suspend_selected_wall_state",
    "sync_primary_selected_plan_target_visuals",
    "refresh_selected_plan_target",
    "refresh_primary_selected_plan_target",
    "set_hovered_wall",
    "set_hovered_opening",
    "set_hovered_symbol",
    "set_hovered_provider",
    "set_hovered_space",
    "set_hovered_region",
    "queue_restore_selected_plan_target",
    "select_plan_target_for_plan_edit",
    "select_opening_for_plan_edit",
    "select_symbol_for_plan_edit",
    "select_region_for_plan_edit",
    "select_space_for_plan_edit",
    "select_wall_for_plan_edit",
    "activate_plan_target",
    "activate_semantic_plan_target",
    "activate_opening_target",
    "activate_symbol_target",
    "activate_region_target",
    "activate_space_target",
    "activate_wall_target",
    "clear_plan_selection_state",
    "normalize_gui_object_selection",
)


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class PlanSelectionAPI(_SessionAPI):
    """Owned session surface for Plan Edit selection behavior."""

    __slots__ = ()

    get_plan_target_object_from_state = staticmethod(get_plan_target_object_from_state)
    get_plan_target_state_key = staticmethod(get_plan_target_state_key)

    def get_selected_plan_target_state(self):
        from bimplan.runtime import session_components as plan_session_components

        return plan_session_components.plan_selection.get_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
        )

    def set_selected_plan_target_state(self, kind=None, obj=None):
        from bimplan.runtime import session_components as plan_session_components

        return plan_session_components.plan_selection.set_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
            kind=kind,
            obj=obj,
        )


for _method_name in _PLAN_SELECTION_API_BOUND_METHODS:
    setattr(PlanSelectionAPI, _method_name, _bind_session_call(globals()[_method_name]))
