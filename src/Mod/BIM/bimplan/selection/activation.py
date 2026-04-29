# SPDX-License-Identifier: LGPL-2.1-or-later

"""Compatibility wrappers for BIM Plan Edit selection activation."""

from . import target_kinds as plan_target_kinds


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
