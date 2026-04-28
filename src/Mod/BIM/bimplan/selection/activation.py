# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection activation and additive selection helpers for BIM Plan Edit."""

from dataclasses import dataclass

from bimplan.runtime import tools as plan_runtime_tools

from . import edit_nodes as plan_edit_nodes
from . import gui_sync as plan_selection_gui_sync
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds


@dataclass(frozen=True)
class TargetActivationBehavior:
    select_target: object
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
        return select_plan_target_for_plan_edit(
            session,
            kind,
            obj,
            queue_restore=queue_restore,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    return _select_plan_target


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
    previous_kind, previous_obj = session.selection.state.get_selected_plan_target()
    session.current_tool = plan_runtime_tools.PlanTool.SELECT
    session.provider_transient_state.provider_selected_objects = []
    preserve_hovered_symbol_overlay = (
        kind == plan_target_kinds.PLAN_TARGET_SYMBOL
        and session.hovered_symbol == obj
        and bool(session.overlay_tracker_state.symbol_hover_trackers)
    )
    session.selection.state.set_selected_plan_target(
        kind,
        obj,
        pending_restore=queue_restore,
        preserve_hovered_symbol_overlay=preserve_hovered_symbol_overlay,
    )
    if sync_gui_selection:
        if defer_gui_selection:
            plan_selection_gui_sync.schedule_gui_selection_object(session, obj)
        else:
            plan_selection_gui_sync.set_gui_selection_object(session, obj)
    session.overlays.walls.apply_selected_wall_selection_feedback(
        defer_grips=kind == plan_target_kinds.PLAN_TARGET_WALL and defer_wall_grips
    )
    plan_target_dispatch.sync_selected_target_visuals(
        session,
        kinds=plan_target_kinds.CLEAR_PLAN_SELECTION_VISUAL_KINDS,
        previous_kind=previous_kind,
        previous_obj=previous_obj,
    )
    session.overlays.spaces.sync_secondary_selected_overlays()
    session.task_panels.refresh_task_panel_status(
        reason=(
            "selection" if session.current_tool == plan_runtime_tools.PlanTool.SELECT else "full"
        )
    )
    if queue_restore:
        session.selection.activation.queue_restore_selected_plan_target(kind, obj)
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
        select_target=select_opening_for_plan_edit,
        clear_hovered_kinds=plan_target_kinds.SEMANTIC_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_SYMBOL: TargetActivationBehavior(
        select_target=select_symbol_for_plan_edit,
        clear_hovered_kinds=plan_target_kinds.SEMANTIC_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_REGION: TargetActivationBehavior(
        select_target=select_region_for_plan_edit,
        clear_hovered_kinds=plan_target_kinds.SEMANTIC_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_SPACE: TargetActivationBehavior(
        select_target=select_space_for_plan_edit,
        clear_hovered_kinds=plan_target_kinds.SPACE_TARGET_CLEAR_HOVERED_KINDS,
    ),
    plan_target_kinds.PLAN_TARGET_WALL: TargetActivationBehavior(
        select_target=select_wall_for_plan_edit,
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
    return activate_plan_target(
        session,
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
        target_ref = plan_target_kinds.coerce_plan_target_ref(session.picking.pick(mouse_pos))
    else:
        target_ref = plan_target_kinds.coerce_plan_target_ref(resolved_target)
    with session.performance.plan_perf_trace_span(
        f"activate_plan_target_{kind}", requested_kind=kind, mouse_pos=mouse_pos
    ):
        session.performance.plan_perf_count(f"activate_plan_target_attempts_{kind}")
        session.performance.plan_perf_set_fields(
            resolved_target=session.performance.plan_perf_describe_target(
                target_ref.kind, target_ref.obj
            )
        )
        target_obj = target_ref.obj if target_ref.kind == kind else None
        behavior = _get_target_activation_behavior(kind)
        if behavior is None or not behavior.select_target(
            session,
            target_obj,
            queue_restore=True,
            sync_gui_selection=sync_gui_selection,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        ):
            session.performance.plan_perf_set_fields(activate_plan_target_result=False)
            return False
        session.selection.hover.clear_hovered_plan_targets(clear_hovered_kinds)
        session.input.claim_left_button_click(event_callback)
        session.performance.plan_perf_set_fields(
            activate_plan_target_result=True,
            activated_target=session.performance.plan_perf_describe_target(kind, target_obj),
        )
        return True


def activate_semantic_plan_target(session, mouse_pos, event_callback=None):
    def _hover_pick_matches_mouse():
        last_mouse_pos = session.hover_pick_state.last_mouse_pos
        if mouse_pos is None or last_mouse_pos is None:
            return False
        try:
            return (
                abs(float(last_mouse_pos[0]) - float(mouse_pos[0])) <= 1.0
                and abs(float(last_mouse_pos[1]) - float(mouse_pos[1])) <= 1.0
            )
        except Exception:
            return False

    target_ref = session.selection.hover.get_hovered_plan_target()
    hover_pick_dirty = bool(session.hover_pick_state.dirty)
    reuse_hovered_target = (
        target_ref.kind == plan_target_kinds.PLAN_TARGET_WALL
        and target_ref.obj is not None
        and not hover_pick_dirty
        and _hover_pick_matches_mouse()
    )
    perf = getattr(session, "performance", None)
    if not reuse_hovered_target:
        target_ref = plan_target_kinds.coerce_plan_target_ref(session.picking.pick(mouse_pos))
        source = "picked_after_throttled_hover" if hover_pick_dirty else "picked"
        session.hover_pick_state.dirty = False
        if perf is not None:
            perf.plan_perf_count(f"semantic_target_source_{source}")
            perf.plan_perf_set_fields(semantic_target_source=source)
    else:
        if perf is not None:
            perf.plan_perf_count("semantic_target_source_hovered")
            perf.plan_perf_set_fields(
                semantic_target_source="hovered",
                hovered_target=perf.plan_perf_describe_target(target_ref.kind, target_ref.obj),
            )
    if _get_target_activation_behavior(target_ref.kind) is None:
        return False
    if target_ref.kind == plan_target_kinds.PLAN_TARGET_WALL:
        return _activate_configured_plan_target(
            session,
            target_ref.kind,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=target_ref,
            defer_gui_selection=True,
            defer_wall_grips=True,
        )
    return _activate_configured_plan_target(
        session,
        target_ref.kind,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=target_ref,
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
    previous_kind, previous_obj = session.selection.state.get_selected_plan_target()
    with session.performance.plan_perf_trace_event(
        "clear_plan_selection_state",
        clear_selection_started_kind=previous_kind or "none",
        clear_selection_started_target=session.performance.plan_perf_describe_target(
            previous_kind, previous_obj
        ),
    ):
        with session.performance.plan_perf_trace_span("clear_plan_selection_gui_selection"):
            plan_selection_gui_sync.set_gui_selection(session, [])
        with session.performance.plan_perf_trace_span("clear_plan_selection_target_state"):
            session.selection.state.set_selected_plan_target()
            session.provider_transient_state.provider_selected_objects = []
        with session.performance.plan_perf_trace_span("clear_plan_selection_hover_state"):
            plan_target_dispatch.clear_hovered_targets(session)
        with session.performance.plan_perf_trace_span("clear_plan_selection_wall_grips"):
            session.overlays.walls.clear_wall_grips()
            session.overlays.walls.clear_selected_wall_overlay()
        with session.performance.plan_perf_trace_span("clear_plan_selection_secondary_overlays"):
            session.overlays.spaces.sync_secondary_selected_overlays()
        plan_target_dispatch.sync_selected_target_visuals(
            session,
            kinds=plan_target_kinds.CLEAR_PLAN_SELECTION_VISUAL_KINDS,
            force=True,
            trace_style="by_kind",
            trace_prefix="clear_plan_selection",
        )
        with session.performance.plan_perf_trace_span("clear_plan_selection_task_status"):
            session.task_panels.refresh_task_panel_status(
                reason=(
                    "selection"
                    if session.current_tool == plan_runtime_tools.PlanTool.SELECT
                    else "full"
                )
            )
        selected_kind, selected_obj = session.selection.state.get_selected_plan_target()
        session.performance.plan_perf_set_fields(
            clear_selection_ended_kind=selected_kind or "none",
            clear_selection_ended_target=session.performance.plan_perf_describe_target(
                selected_kind, selected_obj
            ),
            clear_selection_cleared_wall=bool(previous_kind == "wall" and not selected_kind),
        )


def is_plan_additive_selection_active(session):
    if session.current_tool != plan_runtime_tools.PlanTool.SELECT:
        return False
    try:
        from PySide import QtCore, QtGui

        modifiers = QtGui.QApplication.keyboardModifiers()
        return bool(modifiers & QtCore.Qt.ControlModifier)
    except Exception:
        return False


def activate_provider_overlay_target_node(session, node, event_callback=None):
    target_ref = plan_target_kinds.coerce_plan_target_ref(
        session.picking.get_provider_overlay_target_from_edit_node(node)
    )
    if target_ref.obj is None:
        return False
    if session.selection.state.is_valid_plan_target(target_ref.kind, target_ref.obj):
        session.provider_transient_state.provider_selected_objects = []
        session.selection.state.set_pending_selected_plan_target(target_ref)
    else:
        session.provider_transient_state.provider_selected_objects = [target_ref.obj]
        session.selection.state.set_pending_selected_plan_target()
    plan_target_dispatch.clear_hovered_targets(session)
    plan_selection_gui_sync.set_gui_selection_object(session, target_ref.obj)
    session.selection.refresh.refresh_primary_selected_plan_target()
    session.input.claim_left_button_click(event_callback)
    return True


def _get_current_additive_gui_selection(session):
    primary_kind, primary_obj = session.selection.state.get_selected_plan_target()
    selection = plan_selection_gui_sync.get_gui_selection()
    if primary_obj is not None and primary_obj not in selection:
        selection = [primary_obj] + selection
    return (
        primary_kind,
        primary_obj,
        session.selection.sync.normalize_gui_object_selection(selection),
    )


def _resolve_next_selected_target(
    session, selection, primary_kind, primary_obj, fallback_target=None
):
    if primary_obj is not None and primary_obj in selection:
        return (primary_kind, primary_obj)
    if fallback_target is not None:
        fallback_target_ref = plan_target_kinds.coerce_plan_target_ref(fallback_target)
        if (
            fallback_target_ref.kind
            and fallback_target_ref.obj
            and fallback_target_ref.obj in selection
        ):
            return (fallback_target_ref.kind, fallback_target_ref.obj)
    return session.selection.state.get_first_plan_target_from_selection(selection)


def _apply_additive_selection_update(session, selection, next_kind, next_obj, event_callback=None):
    session.selection.state.set_pending_selected_plan_target(next_kind, next_obj)
    plan_target_dispatch.clear_hovered_targets(session)
    plan_selection_gui_sync.set_gui_selection(session, selection)
    session.selection.refresh.refresh_primary_selected_plan_target()
    session.input.claim_left_button_click(event_callback)
    return True


def toggle_raw_plan_object_selection(session, obj, event_callback=None):
    if obj is None:
        return False

    primary_kind, primary_obj, selection = _get_current_additive_gui_selection(session)
    provider_selection = session.selection.sync.normalize_gui_object_selection(
        session.provider_transient_state.provider_selected_objects
    )
    if obj in provider_selection:
        provider_selection = [selected for selected in provider_selection if selected != obj]
    else:
        provider_selection.append(obj)
    session.provider_transient_state.provider_selected_objects = (
        session.selection.sync.normalize_gui_object_selection(provider_selection)
    )
    new_selection = session.selection.sync.normalize_gui_object_selection(
        [
            selected
            for selected in selection
            if session.selection.targets.get_plan_target_for_object(selected).kind
        ],
    )
    next_kind, next_obj = _resolve_next_selected_target(
        session,
        new_selection,
        primary_kind,
        primary_obj,
    )
    return _apply_additive_selection_update(
        session,
        new_selection,
        next_kind,
        next_obj,
        event_callback,
    )


def toggle_plan_target_selection_at_position(session, mouse_pos, event_callback=None):
    node = session.picking.pick_edit_node(mouse_pos)
    if plan_edit_nodes.get_edit_node_kind(node) in (
        "provider_overlay_point",
        "provider_overlay_target",
    ):
        target_ref = plan_target_kinds.coerce_plan_target_ref(
            session.picking.get_provider_overlay_target_from_edit_node(node)
        )
        if target_ref.obj is not None and not session.selection.state.is_valid_plan_target(
            target_ref.kind,
            target_ref.obj,
        ):
            return toggle_raw_plan_object_selection(session, target_ref.obj, event_callback)
    else:
        target_ref = plan_target_kinds.coerce_plan_target_ref(
            session.picking.get_plan_target_from_edit_node(node)
        )
    if target_ref.kind is None:
        target_ref = plan_target_kinds.coerce_plan_target_ref(session.picking.pick(mouse_pos))
    if not target_ref.kind or not target_ref.obj:
        return False

    primary_kind, primary_obj, selection = _get_current_additive_gui_selection(session)

    was_selected = target_ref.obj in selection
    if was_selected:
        new_selection = [selected for selected in selection if selected != target_ref.obj]
        fallback_target = None if primary_obj == target_ref.obj else target_ref
        next_kind, next_obj = _resolve_next_selected_target(
            session,
            new_selection,
            primary_kind,
            primary_obj,
            fallback_target=fallback_target,
        )
    else:
        new_selection = list(selection)
        new_selection.append(target_ref.obj)
        next_kind, next_obj = _resolve_next_selected_target(
            session,
            new_selection,
            primary_kind,
            primary_obj,
            fallback_target=target_ref,
        )

    return _apply_additive_selection_update(
        session,
        new_selection,
        next_kind,
        next_obj,
        event_callback,
    )
