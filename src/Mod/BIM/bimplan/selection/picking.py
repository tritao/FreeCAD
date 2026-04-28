# SPDX-License-Identifier: LGPL-2.1-or-later

"""Compatibility imports for BIM Plan Edit picking."""

from bimplan.picking import coordinator as plan_picking_coordinator
from bimplan.selection import area_picking as plan_area_picking
from bimplan.selection import edit_node_picking as plan_edit_node_picking
from bimplan.selection import hover_picking as plan_hover_picking
from bimplan.selection import overlay_picking as plan_overlay_picking
from bimplan.selection import picking_geometry as plan_picking_geometry
from bimplan.selection import provider_overlay_picking as plan_provider_overlay_picking
from bimplan.selection import target_kinds as plan_target_kinds

_PROVIDER_OVERLAY_PICK_RADIUS_PX = plan_provider_overlay_picking.PROVIDER_OVERLAY_PICK_RADIUS_PX


def get_plan_space_instances(session):
    return plan_area_picking.get_plan_space_instances(session)


def get_plan_region_instances(session):
    return plan_area_picking.get_plan_region_instances(session)


def get_screen_distance_sq_to_segment(session, mouse_pos, start, end):
    return plan_picking_geometry.get_screen_distance_sq_to_segment(
        session,
        mouse_pos,
        start,
        end,
    )


def get_screen_distance_sq_to_projected_segment(cursor_xy, start_xy, end_xy):
    return plan_picking_geometry.get_screen_distance_sq_to_projected_segment(
        cursor_xy,
        start_xy,
        end_xy,
    )


def should_skip_opening_by_plan_bounds(session, opening, plan_point, radius_px):
    return plan_overlay_picking.should_skip_opening_by_plan_bounds(
        session, opening, plan_point, radius_px
    )


def pick_plan_symbol_target_from_overlays(session, mouse_pos, radius_px=10):
    return plan_overlay_picking.pick_plan_symbol_target_from_overlays(
        session, mouse_pos, radius_px=radius_px
    )


def pick_plan_opening_target_from_overlays(session, mouse_pos, radius_px=10, candidates=None):
    return plan_overlay_picking.pick_plan_opening_target_from_overlays(
        session, mouse_pos, radius_px=radius_px, candidates=candidates
    )


def pick_provider_overlay_target_from_overlays(
    session,
    mouse_pos,
    radius_px=_PROVIDER_OVERLAY_PICK_RADIUS_PX,
):
    return plan_provider_overlay_picking.pick_provider_overlay_target_from_overlays(
        session,
        mouse_pos,
        radius_px=radius_px,
    )


def pick_provider_overlay_target_from_objects_info(session, mouse_pos):
    return plan_provider_overlay_picking.pick_provider_overlay_target_from_objects_info(
        session,
        mouse_pos,
    )


def pick_plan_space_target_from_overlays(session, mouse_pos, radius_px=10):
    return plan_area_picking.pick_plan_space_target_from_overlays(
        session, mouse_pos, radius_px=radius_px
    )


def pick_plan_region_target_from_overlays(session, mouse_pos, radius_px=10):
    return plan_area_picking.pick_plan_region_target_from_overlays(
        session, mouse_pos, radius_px=radius_px
    )


def get_region_pick_polylines(session, region):
    return plan_area_picking.get_region_pick_polylines(session, region)


def xy_polygon_area(polyline):
    return plan_area_picking.xy_polygon_area(polyline)


def xy_point_in_polygon(point, polyline, tolerance=1e-9):
    return plan_area_picking.xy_point_in_polygon(point, polyline, tolerance=tolerance)


def pick_plan_region_target_from_polylines(session, mouse_pos):
    return plan_area_picking.pick_plan_region_target_from_polylines(session, mouse_pos)


def pick_plan_target_from_footprint_faces(
    session, mouse_pos, is_target, get_faces, target_label="target"
):
    return plan_area_picking.pick_plan_target_from_footprint_faces(
        session,
        mouse_pos,
        is_target,
        get_faces,
        target_label=target_label,
    )


def pick_plan_space_target_from_footprints(session, mouse_pos):
    return plan_area_picking.pick_plan_space_target_from_footprints(session, mouse_pos)


def pick_plan_region_target_from_footprints(session, mouse_pos):
    return plan_area_picking.pick_plan_region_target_from_footprints(session, mouse_pos)


def get_plan_target_at_position(session, mouse_pos, *, include_space_fallback=True):
    return plan_picking_coordinator.get_plan_target_at_position(
        session,
        mouse_pos,
        include_space_fallback=include_space_fallback,
    )


def get_plan_target_from_edit_node(session, node):
    return plan_edit_node_picking.get_plan_target_from_edit_node(session, node)


def get_edit_node(session, mouse_pos):
    return plan_edit_node_picking.get_edit_node(session, mouse_pos)


def pick_selected_opening_handle(session, mouse_pos, radius_px=10):
    return plan_edit_node_picking.pick_selected_opening_handle(
        session, mouse_pos, radius_px=radius_px
    )


def get_provider_overlay_target_from_edit_node(session, node):
    return plan_provider_overlay_picking.get_provider_overlay_target_from_edit_node(
        session,
        node,
    )


def is_provider_overlay_point_subname(subname):
    return plan_provider_overlay_picking.is_provider_overlay_point_subname(subname)


def clear_hovered_plan_targets(*args, **kwargs):
    return plan_hover_picking.clear_hovered_plan_targets(*args, **kwargs)


def get_hovered_plan_target(*args, **kwargs):
    return plan_target_kinds.coerce_plan_target_ref(
        plan_hover_picking.get_hovered_plan_target(*args, **kwargs)
    )


def prime_hover_pick_caches(*args, **kwargs):
    return plan_hover_picking.prime_hover_pick_caches(*args, **kwargs)


def queue_prime_hover_pick_caches(*args, **kwargs):
    return plan_hover_picking.queue_prime_hover_pick_caches(*args, **kwargs)


def should_skip_hover_pick(*args, **kwargs):
    return plan_hover_picking.should_skip_hover_pick(*args, **kwargs)


def update_hovered_plan_target(*args, **kwargs):
    return plan_hover_picking.update_hovered_plan_target(*args, **kwargs)
