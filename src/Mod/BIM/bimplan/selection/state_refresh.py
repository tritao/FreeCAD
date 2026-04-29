# SPDX-License-Identifier: LGPL-2.1-or-later

"""Compatibility wrappers for BIM Plan Edit selection refresh."""


def sanitize_plan_target_references(session):
    return session.selection.refresh.sanitize_plan_target_references()


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
    return session.selection.refresh.resolve_selected_target_for_gui_object(
        selected,
        pending_target_ref=pending_target_ref,
        preserved_target_ref=preserved_target_ref,
        pending_kind=pending_kind,
        pending_target=pending_target,
        preserved_kind=preserved_kind,
        preserved_target=preserved_target,
    )


def refresh_selected_plan_target(session, *, force_wall_visual_resync=False):
    return session.selection.refresh.refresh_selected_plan_target(
        force_wall_visual_resync=force_wall_visual_resync,
    )


def schedule_selected_wall_reset(session, reason, obj):
    return session.selection.refresh.schedule_selected_wall_reset(reason, obj)


def reset_selected_wall_after_change(session):
    return session.selection.refresh.reset_selected_wall_after_change()


def suspend_selected_wall_state(session, wall=None, clear_gui_selection=True):
    return session.selection.refresh.suspend_selected_wall_state(
        wall=wall,
        clear_gui_selection=clear_gui_selection,
    )


def sync_primary_selected_plan_target_visuals(
    session,
    previous_kind=None,
    previous_obj=None,
    *,
    force_wall_visual_resync=False,
):
    return session.selection.refresh.sync_primary_selected_plan_target_visuals(
        previous_kind=previous_kind,
        previous_obj=previous_obj,
        force_wall_visual_resync=force_wall_visual_resync,
    )


def refresh_primary_selected_plan_target(session, *, force_wall_visual_resync=False):
    return session.selection.refresh.refresh_primary_selected_plan_target(
        force_wall_visual_resync=force_wall_visual_resync,
    )
