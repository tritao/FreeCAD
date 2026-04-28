# SPDX-License-Identifier: LGPL-2.1-or-later

"""Overlay-geometry picking helpers for BIM Plan Edit."""

from . import picking_debug as plan_picking_debug
from . import picking_geometry as plan_picking_geometry


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_set_fields(session, **fields):
    return session.performance.plan_perf_set_fields(**fields)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def pick_best_target_from_projected_polylines(
    session,
    objects,
    get_projected_polylines,
    mouse_pos,
    radius_px,
    *,
    candidate_count_name,
    segment_count_name,
):
    radius_sq = float(radius_px) * float(radius_px)
    cursor_xy = (float(mouse_pos[0]), float(mouse_pos[1]))
    best_target = None
    best_distance_sq = None
    for obj in objects:
        _perf_count(session, candidate_count_name)
        for projected in get_projected_polylines(obj):
            for start_xy, end_xy in zip(projected, projected[1:]):
                _perf_count(session, segment_count_name)
                distance_sq = plan_picking_geometry.get_screen_distance_sq_to_projected_segment(
                    cursor_xy,
                    start_xy,
                    end_xy,
                )
                if distance_sq is None or distance_sq > radius_sq:
                    continue
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_target = obj
                    best_distance_sq = distance_sq
    return best_target


def pick_best_target_from_overlay_segments(session, objects, get_segments, mouse_pos, radius_px):
    radius_sq = float(radius_px) * float(radius_px)
    best_target = None
    best_distance_sq = None
    for obj in objects:
        for start, end in get_segments(obj):
            distance_sq = plan_picking_geometry.get_screen_distance_sq_to_segment(
                session, mouse_pos, start, end
            )
            if distance_sq is None or distance_sq > radius_sq:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_target = obj
                best_distance_sq = distance_sq
    return best_target


def should_skip_opening_by_plan_bounds(session, opening, plan_point, radius_px):
    if plan_point is None:
        return False
    bound_box = session.overlays.geometry.get_opening_pick_bounds(opening)
    if bound_box is None:
        return False

    try:
        min_x, min_y, max_x, max_y = bound_box
        max_span = max(float(max_x) - float(min_x), float(max_y) - float(min_y))
        units_per_px = session.viewport.get_plan_view_units_per_pixel()
        pick_margin = float(radius_px) * float(units_per_px or 0.0) * 4.0
        margin = max(max_span * 2.0, pick_margin, 1500.0)
        point_x = float(plan_point.x)
        point_y = float(plan_point.y)
        return (
            point_x < float(min_x) - margin
            or point_x > float(max_x) + margin
            or point_y < float(min_y) - margin
            or point_y > float(max_y) + margin
        )
    except Exception:
        return False


def pick_plan_symbol_target_from_overlays(session, mouse_pos, radius_px=10):
    with _perf_trace_span(
        session,
        "pick_symbol_target_from_overlays",
        mouse_pos=mouse_pos,
        radius_px=radius_px,
    ):
        if not session.doc or not session.view or not mouse_pos:
            return None
        symbol_instances = tuple(session.overlays.symbols.get_plan_symbol_instances() or ())
        filtered_symbols = []
        for symbol in symbol_instances:
            _perf_count(session, "symbol_overlay_pick_objects_scanned")
            bounds = session.overlays.symbols.get_symbol_overlay_screen_bounds(symbol)
            if not plan_picking_geometry.screen_bounds_intersects_pick_radius(
                bounds, mouse_pos, radius_px
            ):
                _perf_count(session, "symbol_overlay_pick_bounds_skipped")
                continue
            filtered_symbols.append(symbol)
        best_symbol = pick_best_target_from_projected_polylines(
            session,
            filtered_symbols,
            session.overlays.symbols.get_symbol_overlay_screen_polylines,
            mouse_pos,
            radius_px,
            candidate_count_name="symbol_overlay_pick_candidates",
            segment_count_name="symbol_overlay_pick_segments_scanned",
        )
        if best_symbol is None:
            best_symbol = pick_best_target_from_overlay_segments(
                session,
                filtered_symbols,
                session.overlays.symbols.get_symbol_overlay_segments,
                mouse_pos,
                radius_px,
            )
        _perf_set_fields(
            session,
            symbol_overlay_pick_result=plan_picking_debug.describe_pick_object(
                session, best_symbol
            ),
        )
        return best_symbol


def pick_plan_opening_target_from_overlays(session, mouse_pos, radius_px=10, candidates=None):
    with _perf_trace_span(
        session,
        "pick_opening_target_from_overlays",
        mouse_pos=mouse_pos,
        radius_px=radius_px,
        candidate_mode="hosted" if candidates is not None else "document",
    ):
        if not session.doc or not session.view or not mouse_pos:
            return None
        plan_point = session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
        if candidates is None:
            objects = session.openings.get_plan_opening_instances()
        else:
            objects = candidates
        filtered_objects = []
        seen_names = set()
        for obj in objects or ():
            _perf_count(session, "opening_overlay_pick_objects_scanned")
            if not session.openings.is_hosted_opening_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            if should_skip_opening_by_plan_bounds(session, obj, plan_point, radius_px):
                _perf_count(session, "opening_overlay_pick_bounds_skipped")
                continue
            screen_bounds = session.overlays.geometry.get_opening_overlay_screen_bounds(obj)
            if not plan_picking_geometry.screen_bounds_intersects_pick_radius(
                screen_bounds, mouse_pos, radius_px
            ):
                _perf_count(session, "opening_overlay_pick_screen_bounds_skipped")
                continue
            filtered_objects.append(obj)
        best_opening = pick_best_target_from_projected_polylines(
            session,
            filtered_objects,
            session.overlays.geometry.get_opening_overlay_screen_polylines,
            mouse_pos,
            radius_px,
            candidate_count_name="opening_overlay_pick_candidates",
            segment_count_name="opening_overlay_pick_segments_scanned",
        )
        _perf_set_fields(
            session,
            opening_overlay_pick_mode="screen",
            opening_overlay_pick_result=plan_picking_debug.describe_pick_object(
                session, best_opening
            ),
        )
        return best_opening
