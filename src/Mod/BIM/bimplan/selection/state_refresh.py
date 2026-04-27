# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection refresh and state-resolution helpers for BIM Plan Edit."""

from dataclasses import dataclass, field

import FreeCADGui
from bimplan.runtime import tools as plan_runtime_tools

from . import gui_sync as plan_selection_gui_sync
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds
from . import targets as plan_targets

_PRIMARY_SELECTED_TARGET_PRIORITY = {
    kind: index
    for index, kind in enumerate(plan_target_kinds.PRIMARY_SELECTED_TARGET_PRIORITY_KINDS)
}
_GUI_SELECTION_TOOL_NAMES = (
    plan_runtime_tools.PlanTool.SELECT,
    plan_runtime_tools.PlanTool.PICK_SPACE_REGION,
)
_PENDING_TARGET_UNCHANGED = object()
_WALL_GRIP_NONE = "none"
_WALL_GRIP_CLEAR = "clear"
_WALL_GRIP_SYNC = "sync"
_MISSING = object()


@dataclass(frozen=True)
class SelectionRefreshResult:
    primary_target_ref: object = field(default_factory=plan_target_kinds.make_plan_target_ref)
    secondary_targets: tuple = ()
    pending_target: object = _PENDING_TARGET_UNCHANGED
    wall_grip_action: str = _WALL_GRIP_NONE

    @property
    def primary_kind(self):
        return self.primary_target_ref.kind

    @property
    def primary_obj(self):
        return self.primary_target_ref.obj


@dataclass(frozen=True)
class GuiSelectionResolutionState:
    pending_target_ref: object = None
    preserved_target_ref: object = None


def sanitize_plan_target_references(session):
    visibility = getattr(session, "visibility", None)
    is_live_document_object = getattr(visibility, "is_live_document_object", None)
    if not callable(is_live_document_object):
        return False
    changed = False
    for kind in ("wall", "opening", "symbol", "region", "space"):
        obj = session.selection.get_selected_target_for_kind(kind)
        if obj is None or is_live_document_object(obj):
            continue
        session.selection.set_selected_target_for_kind(kind, None)
        changed = True
    for attr in (
        "hovered_wall",
        "hovered_opening",
        "hovered_symbol",
        "hovered_provider",
        "hovered_region",
        "hovered_space",
    ):
        obj = getattr(session, attr, None)
        if obj is None or is_live_document_object(obj):
            continue
        setattr(session, attr, None)
        changed = True
    selection_state = session.selection_state
    normalized_secondary = session.selection.normalize_plan_target_list(
        selection_state.secondary_selected_plan_targets_state
    )
    if normalized_secondary != selection_state.secondary_selected_plan_targets_state:
        selection_state.secondary_selected_plan_targets_state = normalized_secondary
        changed = True
    return changed


def _is_valid_plan_target(session, kind, obj):
    selection_api = getattr(session, "selection", None)
    validate = getattr(selection_api, "is_valid_plan_target", None)
    if callable(validate):
        return bool(validate(kind, obj))
    validate = getattr(session, "_is_valid_plan_target", None)
    if callable(validate):
        return bool(validate(kind, obj))
    return plan_target_dispatch.validate_plan_target(session, kind, obj)


def _should_preserve_provider_selected_target(session, kind, obj, selected):
    if kind != "provider" or obj is None or selected != obj:
        return False
    if not _is_valid_plan_target(session, kind, obj):
        return False
    return plan_selection_gui_sync.is_visible_provider_target_object(session, obj)


def resolve_selected_target_for_gui_object(
    session,
    selected,
    *,
    pending_target_ref=None,
    preserved_target_ref=None,
    pending_kind=None,
    pending_target=None,
    preserved_kind=None,
    preserved_target=None,
):
    if selected is None:
        return plan_target_kinds.make_plan_target_ref()
    if pending_target_ref is None and (pending_kind is not None or pending_target is not None):
        pending_target_ref = plan_target_kinds.make_plan_target_ref(pending_kind, pending_target)
    pending_target_ref = plan_target_kinds.coerce_plan_target_ref(pending_target_ref)
    if selected == pending_target_ref.obj and _is_valid_plan_target(
        session, pending_target_ref.kind, pending_target_ref.obj
    ):
        return plan_target_kinds.make_plan_target_ref(
            pending_target_ref.kind, pending_target_ref.obj
        )
    if preserved_target_ref is None and (
        preserved_kind is not None or preserved_target is not None
    ):
        preserved_target_ref = plan_target_kinds.make_plan_target_ref(
            preserved_kind,
            preserved_target,
        )
    preserved_target_ref = plan_target_kinds.coerce_plan_target_ref(preserved_target_ref)
    if _should_preserve_provider_selected_target(
        session,
        preserved_target_ref.kind,
        preserved_target_ref.obj,
        selected,
    ):
        return plan_target_kinds.make_plan_target_ref(
            preserved_target_ref.kind, preserved_target_ref.obj
        )
    selection_api = getattr(session, "selection", None)
    get_plan_target_for_object = getattr(selection_api, "get_plan_target_for_object", None)
    if callable(get_plan_target_for_object):
        return plan_target_kinds.coerce_plan_target_ref(get_plan_target_for_object(selected))
    return plan_targets.get_plan_target_for_object(session, selected)


def _get_gui_selection_resolution_state(session, previous_kind, previous_obj):
    pending_target_ref = plan_target_kinds.coerce_plan_target_ref(
        session.selection_state.pending_selected_plan_target
    )
    preserved_target_ref = plan_target_kinds.make_plan_target_ref()
    if previous_kind == plan_target_kinds.PLAN_TARGET_PROVIDER:
        preserved_target_ref = plan_target_kinds.make_plan_target_ref(previous_kind, previous_obj)
    return GuiSelectionResolutionState(
        pending_target_ref=pending_target_ref,
        preserved_target_ref=preserved_target_ref,
    )


def _resolve_gui_selection_target(session, selected, resolution_state):
    return resolve_selected_target_for_gui_object(
        session,
        selected,
        pending_target_ref=resolution_state.pending_target_ref,
        preserved_target_ref=resolution_state.preserved_target_ref,
    )


def _choose_primary_selected_target(selected_targets, pending_target_ref=None):
    pending_target_ref = plan_target_kinds.coerce_plan_target_ref(pending_target_ref)
    if pending_target_ref.kind is not None and pending_target_ref.obj is not None:
        for target_ref in selected_targets:
            if (
                target_ref.kind == pending_target_ref.kind
                and target_ref.obj == pending_target_ref.obj
            ):
                return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)
    if not selected_targets:
        return plan_target_kinds.make_plan_target_ref()
    primary_target_ref = min(
        selected_targets,
        key=lambda target_ref: _PRIMARY_SELECTED_TARGET_PRIORITY.get(
            target_ref.kind, len(_PRIMARY_SELECTED_TARGET_PRIORITY)
        ),
    )
    return plan_target_kinds.make_plan_target_ref(primary_target_ref.kind, primary_target_ref.obj)


def _apply_selection_refresh_result(session, refresh_result):
    primary_target_ref = plan_target_kinds.coerce_plan_target_ref(refresh_result.primary_target_ref)
    session.selection.set_selected_plan_target_state(
        primary_target_ref.kind,
        primary_target_ref.obj,
    )
    session.selection.set_secondary_selected_plan_targets(
        refresh_result.secondary_targets,
        primary_kind=primary_target_ref.kind,
        primary_obj=primary_target_ref.obj,
    )
    if refresh_result.pending_target is not _PENDING_TARGET_UNCHANGED:
        if refresh_result.pending_target is None:
            session.selection.set_pending_selected_plan_target()
        else:
            session.selection.set_pending_selected_plan_target(refresh_result.pending_target)
    if refresh_result.wall_grip_action == _WALL_GRIP_CLEAR:
        session.overlays.clear_wall_grips()
    elif refresh_result.wall_grip_action == _WALL_GRIP_SYNC:
        session.overlays.sync_wall_grips()


def _get_selection_refresh_baseline(session):
    previous_target_ref = session.selection.get_selected_plan_target()
    session.performance.plan_perf_set_fields(
        selected_before=session.performance.plan_perf_describe_target(
            previous_target_ref.kind, previous_target_ref.obj
        ),
        selected_before_kind=previous_target_ref.kind or "none",
    )
    previous_wall = session.selection.get_plan_target_object_from_state(
        previous_target_ref.kind,
        previous_target_ref.obj,
        plan_target_kinds.PLAN_TARGET_WALL,
    )
    return previous_target_ref.kind, previous_target_ref.obj, previous_wall


def _resolve_direct_selection_refresh_result(session, previous_wall):
    if session.wall_edit.is_wall_edit_modal_active():
        interaction_state = session.interaction_state
        return SelectionRefreshResult(
            primary_target_ref=plan_target_kinds.make_plan_target_ref(
                plan_target_kinds.PLAN_TARGET_WALL,
                interaction_state.edit_wall,
            ),
            wall_grip_action=_WALL_GRIP_SYNC,
        )
    if session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
        interaction_state = session.interaction_state
        return SelectionRefreshResult(
            primary_target_ref=plan_target_kinds.make_plan_target_ref(
                plan_target_kinds.PLAN_TARGET_SPACE,
                (
                    interaction_state.edit_space
                    if plan_targets.is_plan_space_object(session, interaction_state.edit_space)
                    else None
                ),
            ),
            wall_grip_action=_WALL_GRIP_CLEAR,
        )
    if session.current_tool == plan_runtime_tools.PlanTool.JOIN:
        wall = previous_wall
        if not plan_targets.is_plan_selectable_wall(session, wall):
            session.current_tool = plan_runtime_tools.PlanTool.SELECT
            wall = None
        return SelectionRefreshResult(
            primary_target_ref=plan_target_kinds.make_plan_target_ref(
                plan_target_kinds.PLAN_TARGET_WALL,
                wall,
            ),
            wall_grip_action=_WALL_GRIP_CLEAR,
        )
    if session.current_tool not in _GUI_SELECTION_TOOL_NAMES:
        return SelectionRefreshResult(pending_target=None)
    return None


def _get_gui_selection():
    try:
        return FreeCADGui.Selection.getSelection()
    except (ReferenceError, RuntimeError):
        return _MISSING


def _collect_selected_targets_from_gui_selection(session, selection, previous_kind, previous_obj):
    selected_targets = []
    resolution_state = _get_gui_selection_resolution_state(session, previous_kind, previous_obj)
    provider_refresh_scope = session.providers.plan_provider_refresh_cache_scope()
    with provider_refresh_scope:
        for selected in selection:
            target_ref = _resolve_gui_selection_target(session, selected, resolution_state)
            if target_ref.kind:
                selected_targets.append(target_ref)
    session.performance.plan_perf_count("selected_targets_considered", len(selected_targets))
    return selected_targets, resolution_state.pending_target_ref


def _resolve_gui_selection_refresh_result(session, selection, previous_kind, previous_obj):
    if not selection:
        pending_target_ref = session.selection.consume_pending_selected_plan_target()
        return SelectionRefreshResult(
            primary_target_ref=plan_target_kinds.coerce_plan_target_ref(pending_target_ref),
        )

    selected_targets, pending_target_ref = _collect_selected_targets_from_gui_selection(
        session,
        selection,
        previous_kind,
        previous_obj,
    )
    primary_target_ref = _choose_primary_selected_target(
        selected_targets,
        pending_target_ref=pending_target_ref,
    )
    if primary_target_ref.kind is None:
        return SelectionRefreshResult(pending_target=None)
    pending_selection = primary_target_ref
    if len(selection) == 1 and primary_target_ref.kind not in (
        plan_target_kinds.PLAN_TARGET_SPACE,
        plan_target_kinds.PLAN_TARGET_REGION,
    ):
        pending_selection = None
    return SelectionRefreshResult(
        primary_target_ref=primary_target_ref,
        secondary_targets=tuple(selected_targets),
        pending_target=pending_selection,
    )


def _resolve_selection_refresh_result(session, previous_kind, previous_obj, previous_wall):
    refresh_result = _resolve_direct_selection_refresh_result(session, previous_wall)
    if refresh_result is not None:
        return refresh_result
    selection = _get_gui_selection()
    if selection is _MISSING:
        session.selection.set_selected_plan_target_state()
        return None
    session.performance.plan_perf_count("gui_selection_size", len(selection or []))
    return _resolve_gui_selection_refresh_result(
        session,
        selection,
        previous_kind,
        previous_obj,
    )


def _sync_wall_grips_after_selection_refresh(
    session,
    refresh_result,
    previous_kind,
    previous_obj,
    *,
    force_wall_visual_resync=False,
):
    if refresh_result.wall_grip_action != _WALL_GRIP_NONE:
        return
    wall_target_changed = session.selection.selected_plan_target_changed(
        previous_kind,
        previous_obj,
        plan_target_kinds.PLAN_TARGET_WALL,
    )
    if not wall_target_changed and not force_wall_visual_resync:
        return
    if session.selection.get_selected_plan_target_object(plan_target_kinds.PLAN_TARGET_WALL):
        session.overlays.schedule_wall_grip_sync()
    else:
        session.overlays.clear_wall_grips()


def _record_selection_refresh_result(session, previous_kind):
    selected_kind, selected_obj = session.selection.get_selected_plan_target()
    session.performance.plan_perf_set_fields(
        selected_after=session.performance.plan_perf_describe_target(selected_kind, selected_obj),
        selected_after_kind=selected_kind or "none",
        selection_refresh_cleared_target=bool(previous_kind and not selected_kind),
    )


def refresh_selected_plan_target(session, *, force_wall_visual_resync=False):
    with session.performance.plan_perf_trace_span("refresh_selected_plan_target"):
        session.performance.plan_perf_count("selection_refreshes")
        if session.lifecycle_state.tearing_down:
            return
        if session.lifecycle_state.ignore_selection_changes:
            return

        previous_kind, previous_obj, previous_wall = _get_selection_refresh_baseline(session)
        refresh_result = _resolve_selection_refresh_result(
            session,
            previous_kind,
            previous_obj,
            previous_wall,
        )
        _apply_selection_refresh_result(session, refresh_result)
        _sync_wall_grips_after_selection_refresh(
            session,
            refresh_result,
            previous_kind,
            previous_obj,
            force_wall_visual_resync=force_wall_visual_resync,
        )
        sync_primary_selected_plan_target_visuals(
            session,
            previous_kind,
            previous_obj,
            force_wall_visual_resync=force_wall_visual_resync,
        )
        _record_selection_refresh_result(session, previous_kind)


def schedule_selected_wall_reset(session, reason, obj):
    del reason, obj
    if session._pending_selected_wall_reset or session.lifecycle_state.tearing_down:
        return
    session._pending_selected_wall_reset = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, lambda: reset_selected_wall_after_change(session))
    except ImportError:
        reset_selected_wall_after_change(session)


def reset_selected_wall_after_change(session):
    session._pending_selected_wall_reset = False
    if (
        session.lifecycle_state.tearing_down
        or session.current_tool != plan_runtime_tools.PlanTool.SELECT
    ):
        return
    wall = session.selection.get_selected_plan_target_object("wall")
    if not wall:
        return
    session.overlays.clear_wall_grips()
    session.overlays.clear_selected_wall_overlay()
    session.selection.clear_selected_plan_target_if_matches("wall", wall)
    plan_selection_gui_sync.set_gui_selection(session, [])
    session.task_panels.refresh_task_panel_status()


def suspend_selected_wall_state(session, wall=None, clear_gui_selection=True):
    if session.lifecycle_state.tearing_down:
        return
    if wall is None:
        wall = session.selection.get_selected_plan_target_object("wall")
    if wall is None:
        return
    if not session.selection.is_selected_plan_target("wall", wall):
        return
    session._pending_selected_wall_reset = False
    session.overlays.clear_wall_grips()
    session.overlays.clear_selected_wall_overlay()
    session.selection.clear_selected_plan_target_if_matches("wall", wall)
    if clear_gui_selection:
        plan_selection_gui_sync.set_gui_selection(session, [])
    session.task_panels.refresh_task_panel_status(reason="selection")


def sync_primary_selected_plan_target_visuals(
    session,
    previous_kind=None,
    previous_obj=None,
    *,
    force_wall_visual_resync=False,
):
    with session.performance.plan_perf_trace_span("sync_primary_selected_plan_target_visuals"):
        if (
            session.current_tool != plan_runtime_tools.PlanTool.SELECT
            or force_wall_visual_resync
            or session.selection.selected_plan_target_changed(
                previous_kind,
                previous_obj,
                plan_target_kinds.PLAN_TARGET_WALL,
            )
        ):
            with session.performance.plan_perf_trace_span("sync_selected_wall_overlay"):
                session.overlays.sync_selected_wall_overlay()
        with session.performance.plan_perf_trace_span("sync_selected_wall_opening_context_overlay"):
            session.overlays.sync_selected_wall_opening_context_overlay()
        with session.performance.plan_perf_trace_span("sync_hovered_wall_overlay"):
            session.overlays.sync_hovered_wall_overlay()
        with session.performance.plan_perf_trace_span("sync_hovered_wall_opening_context_overlay"):
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
        with session.performance.plan_perf_trace_span("sync_secondary_selected_overlays"):
            session.overlays.sync_secondary_selected_overlays()
        with session.performance.plan_perf_trace_span("sync_active_plan_target_object"):
            session.viewport.sync_active_plan_target_object()
        session.task_panels.refresh_task_panel_status(
            reason=(
                "selection"
                if session.current_tool == plan_runtime_tools.PlanTool.SELECT
                else "full"
            )
        )


def refresh_primary_selected_plan_target(session, *, force_wall_visual_resync=False):
    refresh_selected_plan_target(
        session,
        force_wall_visual_resync=force_wall_visual_resync,
    )
