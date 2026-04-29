# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection activation and additive selection helpers for BIM Plan Edit."""

from dataclasses import dataclass

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
    return session.selection.activation.select_plan_target_for_plan_edit(
        kind,
        obj,
        queue_restore=queue_restore,
        sync_gui_selection=sync_gui_selection,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


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
    return session.selection.activation.activate_plan_target_for_kind(
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
    return session.selection.activation.activate_plan_target(
        kind,
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=sync_gui_selection,
        clear_hovered_kinds=clear_hovered_kinds,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def activate_semantic_plan_target(session, mouse_pos, event_callback=None):
    return session.selection.activation.activate_semantic_plan_target(
        mouse_pos,
        event_callback=event_callback,
    )


def activate_opening_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session.selection.activation.activate_opening_target(
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_symbol_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session.selection.activation.activate_symbol_target(
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_region_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session.selection.activation.activate_region_target(
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_space_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return session.selection.activation.activate_space_target(
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
    return session.selection.activation.activate_wall_target(
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def clear_plan_selection_state(session):
    return session.selection.activation.clear_plan_selection_state()


def is_plan_additive_selection_active(session):
    return session.selection.activation.is_plan_additive_selection_active()


def activate_provider_overlay_target_node(session, node, event_callback=None):
    return session.selection.activation.activate_provider_overlay_target_node(
        node,
        event_callback=event_callback,
    )


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
    return session.selection.activation.toggle_raw_plan_object_selection(
        obj,
        event_callback=event_callback,
    )


def toggle_plan_target_selection_at_position(session, mouse_pos, event_callback=None):
    return session.selection.activation.toggle_plan_target_selection_at_position(
        mouse_pos,
        event_callback=event_callback,
    )
