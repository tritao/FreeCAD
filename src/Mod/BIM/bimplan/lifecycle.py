# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared lifecycle cleanup helpers for BIM Plan Edit."""

from bimplan import target_dispatch as plan_target_dispatch


def clear_hover_visuals(
    session,
    kinds=None,
    *,
    include_junction_nodes=False,
    include_hovered_wall_opening_context=False,
):
    if include_junction_nodes:
        session._clear_junction_node_overlays()
    if include_hovered_wall_opening_context:
        session._clear_hovered_wall_opening_context_overlay()
    plan_target_dispatch.clear_hovered_target_visuals(session, kinds=kinds)


def clear_selection_visuals(
    session,
    kinds=None,
    *,
    clear_handle_kinds=None,
    include_wall_grips=False,
    include_selected_wall_opening_context=False,
    include_secondary_selection=False,
):
    if include_wall_grips:
        session._clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        kinds=kinds,
        clear_handle_kinds=clear_handle_kinds,
    )
    if include_selected_wall_opening_context:
        session._clear_selected_wall_opening_context_overlay()
    if include_secondary_selection:
        session._clear_secondary_selected_overlays()


def clear_transient_visuals(
    session,
    *,
    include_provider_overlays=False,
    include_provider_point_preview=False,
    include_space_region_pick=False,
    include_opening_handle_pool=False,
    include_opening_move_preview=False,
    include_symbol_edit_preview=False,
    include_plan_region_preview=False,
):
    if include_provider_overlays:
        session._clear_provider_overlays()
    if include_provider_point_preview:
        session._clear_provider_point_preview()
    if include_space_region_pick:
        session._clear_space_region_pick_overlays()
    if include_opening_handle_pool:
        session._discard_opening_handle_tracker_pool()
    if include_opening_move_preview:
        session._clear_opening_move_preview()
    if include_symbol_edit_preview:
        session._clear_symbol_edit_preview()
    if include_plan_region_preview:
        session._clear_plan_region_preview()


def detach_runtime_observers(session):
    session._detach_selection_observer()
    session._detach_document_observer()
    session._unregister_edit_callbacks()
