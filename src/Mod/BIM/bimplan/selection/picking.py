# SPDX-License-Identifier: LGPL-2.1-or-later

"""Pointer picking helpers for BIM Plan Edit."""

import FreeCAD
import math
from bimplan.selection import hover_picking as plan_hover_picking
from bimplan.providers import runtime as plan_provider_runtime
from bimplan import selection as plan_selection
from bimplan.selection import targets as plan_targets
from bimplan.providers import PlanOverlayMarkerKind

_PROVIDER_OVERLAY_POINT_PREFIX = "ProviderOverlayPoint"
_PROVIDER_OVERLAY_PICK_RADIUS_PX = 12.0
_PROVIDER_OVERLAY_PICK_PADDING_PX = 3.0
_PROVIDER_OVERLAY_PICK_PADDING_RATIO = 0.15
_PROVIDER_OVERLAY_MARKER_TOLERANCE_BASE_PX = 4.5
_PROVIDER_OVERLAY_MARKER_TOLERANCE_WIDTH_SCALE = 1.25
_MAX_PICK_DEBUG_ITEMS = 40


def _get_plan_provider_overlay_pick_mode(session):
    get_mode = getattr(session, "get_plan_provider_overlay_mode", None)
    if not callable(get_mode):
        return "all"
    try:
        mode = str(get_mode() or "").strip().lower()
    except Exception:
        return "all"
    return mode or "all"


def _should_prioritize_provider_targets_for_mode(session):
    return plan_provider_runtime.is_focused_provider_overlay_pick_mode(
        _get_plan_provider_overlay_pick_mode(session)
    )


def _emit_pick_debug(session, name, **fields):
    try:
        if not session.performance.is_plan_pick_debug_active():
            return
    except Exception:
        return
    try:
        session.performance.plan_pick_debug_event(name, **fields)
    except Exception:
        return


def _append_pick_debug_item(items, value, limit=_MAX_PICK_DEBUG_ITEMS):
    if items is None or value is None or len(items) >= int(limit):
        return
    items.append(value)


def _describe_pick_object(session, obj):
    try:
        return session.performance.plan_perf_describe_object(obj)
    except Exception:
        pass
    if obj is None:
        return None
    document_name = str(getattr(getattr(obj, "Document", None), "Name", "") or "").strip()
    object_name = str(getattr(obj, "Name", "") or "").strip()
    label = str(getattr(obj, "Label", "") or "").strip()
    result = {}
    if document_name:
        result["document"] = document_name
    if object_name:
        result["name"] = object_name
    if label and label != object_name:
        result["label"] = label
    return result or repr(obj)


def _describe_pick_target(session, kind, obj):
    try:
        return session.performance.plan_perf_describe_target(kind, obj)
    except Exception:
        pass
    if not kind or obj is None:
        return None
    result = {"kind": str(kind)}
    described = _describe_pick_object(session, obj)
    if isinstance(described, dict):
        result.update(described)
    elif described is not None:
        result["value"] = described
    return result


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_set_fields(session, **fields):
    return session.performance.plan_perf_set_fields(**fields)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _describe_pick_info_entry(info):
    if not info:
        return None
    result = {}
    for key in ("Document", "Object"):
        value = str(info.get(key) or "").strip()
        if value:
            result[key.lower()] = value
    parent_obj = info.get("ParentObject")
    if parent_obj is not None:
        result["parent_object"] = {
            "document": str(
                getattr(getattr(parent_obj, "Document", None), "Name", "") or ""
            ).strip(),
            "name": str(getattr(parent_obj, "Name", "") or "").strip(),
        }
    return result or None


def _describe_pick_overlay_target(target):
    if target is None:
        return None
    target_kind = getattr(target, "target_kind", None)
    if target_kind is not None:
        target_kind = getattr(target_kind, "value", target_kind)
    result = {
        "document_name": str(getattr(target, "document_name", "") or "").strip(),
        "object_name": str(getattr(target, "object_name", "") or "").strip(),
        "target_kind": str(target_kind or "").strip(),
    }
    subname = str(getattr(target, "subname", "") or "").strip()
    if subname:
        result["subname"] = subname
    return result


def _describe_pick_overlay(overlay):
    if overlay is None:
        return None
    marker_kind = getattr(overlay, "marker_kind", None)
    if marker_kind is not None:
        marker_kind = getattr(marker_kind, "value", marker_kind)
    return {
        "provider_id": str(getattr(overlay, "provider_id", "") or "").strip(),
        "key": str(getattr(overlay, "key", "") or "").strip(),
        "category": str(getattr(overlay, "category", "") or "").strip(),
        "marker_kind": str(marker_kind or "").strip(),
        "marker_size": float(getattr(overlay, "marker_size", 0.0) or 0.0),
        "point_count": len(tuple(getattr(overlay, "points", ()) or ())),
    }


def _get_cached_plan_instances(session, cache_field, is_target, count_name, span_name):
    if not session.doc:
        return ()
    doc_name = getattr(session.doc, "Name", None)
    cache_record = getattr(session.overlay_cache_state, cache_field, None)
    if cache_record is not None and cache_record[0] == doc_name:
        _perf_count(session, f"{cache_field}_hits")
        return cache_record[1]

    instances = []
    with _perf_trace_span(session, span_name):
        for obj in getattr(session.doc, "Objects", []) or []:
            _perf_count(session, count_name)
            if is_target(obj):
                instances.append(obj)
    result = tuple(instances)
    setattr(session.overlay_cache_state, cache_field, (doc_name, result))
    return result


def get_plan_space_instances(session):
    return _get_cached_plan_instances(
        session,
        "plan_space_instances_cache",
        session._is_plan_space_object,
        "plan_space_instance_objects_scanned",
        "build_plan_space_instances_cache",
    )


def get_plan_region_instances(session):
    return _get_cached_plan_instances(
        session,
        "plan_region_instances_cache",
        session._is_plan_region_object,
        "plan_region_instance_objects_scanned",
        "build_plan_region_instances_cache",
    )


def get_screen_distance_sq_to_segment(session, mouse_pos, start, end):
    if not session.view or not mouse_pos:
        return None
    try:
        cursor_x = float(mouse_pos[0])
        cursor_y = float(mouse_pos[1])
        start_x, start_y = session.view.getPointOnScreen(start)
        end_x, end_y = session.view.getPointOnScreen(end)
    except Exception:
        return None
    projector = getattr(session, "_get_screen_distance_sq_to_projected_segment", None)
    if callable(projector):
        return projector(
            (cursor_x, cursor_y),
            (start_x, start_y),
            (end_x, end_y),
        )
    return get_screen_distance_sq_to_projected_segment(
        (cursor_x, cursor_y),
        (start_x, start_y),
        (end_x, end_y),
    )


def get_screen_distance_sq_to_projected_segment(cursor_xy, start_xy, end_xy):
    if cursor_xy is None or start_xy is None or end_xy is None:
        return None

    cursor_x = float(cursor_xy[0])
    cursor_y = float(cursor_xy[1])
    start_x = float(start_xy[0])
    start_y = float(start_xy[1])
    end_x = float(end_xy[0])
    end_y = float(end_xy[1])
    dx = end_x - start_x
    dy = end_y - start_y
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        proj_x = start_x
        proj_y = start_y
    else:
        t = ((cursor_x - start_x) * dx + (cursor_y - start_y) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        proj_x = start_x + t * dx
        proj_y = start_y + t * dy
    offset_x = proj_x - cursor_x
    offset_y = proj_y - cursor_y
    return offset_x * offset_x + offset_y * offset_y


def should_skip_opening_by_plan_bounds(session, opening, plan_point, radius_px):
    if plan_point is None:
        return False
    try:
        shape = getattr(opening, "Shape", None)
        bound_box = getattr(shape, "BoundBox", None)
    except Exception:
        return False
    if bound_box is None:
        return False

    try:
        max_span = max(float(bound_box.XLength), float(bound_box.YLength))
        units_per_px = session.viewport.get_plan_view_units_per_pixel()
        pick_margin = float(radius_px) * float(units_per_px or 0.0) * 4.0
        margin = max(max_span * 2.0, pick_margin, 1500.0)
        point_x = float(plan_point.x)
        point_y = float(plan_point.y)
        return (
            point_x < float(bound_box.XMin) - margin
            or point_x > float(bound_box.XMax) + margin
            or point_y < float(bound_box.YMin) - margin
            or point_y > float(bound_box.YMax) + margin
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
        radius_sq = float(radius_px) * float(radius_px)
        best_symbol = None
        best_distance_sq = None
        cursor_xy = (float(mouse_pos[0]), float(mouse_pos[1]))
        for obj in session.overlays.get_plan_symbol_instances():
            _perf_count(session, "symbol_overlay_pick_candidates")
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            for projected in session.overlays.get_symbol_overlay_screen_polylines(obj):
                for start_xy, end_xy in zip(projected, projected[1:]):
                    _perf_count(session, "symbol_overlay_pick_segments_scanned")
                    distance_sq = session._get_screen_distance_sq_to_projected_segment(
                        cursor_xy,
                        start_xy,
                        end_xy,
                    )
                    if distance_sq is None or distance_sq > radius_sq:
                        continue
                    if best_distance_sq is None or distance_sq < best_distance_sq:
                        best_symbol = obj
                        best_distance_sq = distance_sq
        _perf_set_fields(
            session, symbol_overlay_pick_result=_describe_pick_object(session, best_symbol)
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
        screen_radius_sq = float(radius_px) * float(radius_px)
        best_opening = None
        best_distance_sq = None
        seen = set()
        cursor_xy = (float(mouse_pos[0]), float(mouse_pos[1]))
        plan_point = session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
        if candidates is None:
            objects = session.openings.get_plan_opening_instances()
        else:
            objects = candidates
        for obj in objects or []:
            _perf_count(session, "opening_overlay_pick_objects_scanned")
            if not session.openings.is_hosted_opening_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            if should_skip_opening_by_plan_bounds(session, obj, plan_point, radius_px):
                _perf_count(session, "opening_overlay_pick_bounds_skipped")
                continue
            _perf_count(session, "opening_overlay_pick_candidates")
            for projected in session.overlays.get_opening_overlay_screen_polylines(obj):
                for start_xy, end_xy in zip(projected, projected[1:]):
                    _perf_count(session, "opening_overlay_pick_segments_scanned")
                    distance_sq = session._get_screen_distance_sq_to_projected_segment(
                        cursor_xy, start_xy, end_xy
                    )
                    if distance_sq is None or distance_sq > screen_radius_sq:
                        continue
                    if best_distance_sq is None or distance_sq < best_distance_sq:
                        best_opening = obj
                        best_distance_sq = distance_sq
        _perf_set_fields(
            session,
            opening_overlay_pick_mode="screen",
            opening_overlay_pick_result=_describe_pick_object(session, best_opening),
        )
        return best_opening


def pick_provider_overlay_target_from_overlays(
    session,
    mouse_pos,
    radius_px=_PROVIDER_OVERLAY_PICK_RADIUS_PX,
):
    with _perf_trace_span(
        session,
        "pick_provider_overlay_target_from_overlays",
        mouse_pos=mouse_pos,
        radius_px=radius_px,
    ):
        if not session.view or not mouse_pos:
            return (None, None)
        try:
            cursor_x = float(mouse_pos[0])
            cursor_y = float(mouse_pos[1])
        except Exception:
            return (None, None)

        get_overlays = getattr(session, "get_plan_provider_overlays", None)
        if not callable(get_overlays):
            return (None, None)
        is_visible = getattr(session, "is_plan_provider_overlay_visible", None)

        best_distance_sq = None
        best_target_kind = None
        best_target_obj = None
        debug_candidates = []
        for overlay in tuple(get_overlays() or ()):
            if not bool(getattr(overlay, "visible", True)):
                continue
            if callable(is_visible) and not is_visible(overlay):
                continue
            points = tuple(getattr(overlay, "points", ()) or ())
            targets = tuple(getattr(overlay, "point_targets", ()) or ())
            for index, point in enumerate(points):
                target = targets[index] if index < len(targets) else None
                if not _has_provider_overlay_target_identity(target):
                    continue
                point_vec = _coerce_overlay_point_vector(point)
                if point_vec is None:
                    continue
                try:
                    point_x, point_y = session.view.getPointOnScreen(point_vec)
                except Exception:
                    continue
                dx = float(point_x) - cursor_x
                dy = float(point_y) - cursor_y
                center_distance_sq = dx * dx + dy * dy
                pick_radius_px = _get_provider_overlay_pick_radius_px(
                    session,
                    overlay,
                    point_vec,
                    fallback_radius_px=radius_px,
                )
                marker_distance_sq = _get_provider_overlay_marker_screen_distance_sq(
                    session,
                    mouse_pos,
                    overlay,
                    point_vec,
                )
                marker_tolerance_px = _get_provider_overlay_marker_tolerance_px(
                    overlay,
                    fallback_radius_px=radius_px,
                )
                debug_candidate = {
                    "overlay": _describe_pick_overlay(overlay),
                    "point_index": index,
                    "target": _describe_pick_overlay_target(target),
                    "center_distance_px": round(center_distance_sq**0.5, 3),
                    "pick_radius_px": round(float(pick_radius_px), 3),
                    "marker_tolerance_px": round(float(marker_tolerance_px), 3),
                }
                if marker_distance_sq is not None:
                    debug_candidate["marker_distance_px"] = round(marker_distance_sq**0.5, 3)
                distance_sq = center_distance_sq
                if marker_distance_sq is not None:
                    distance_sq = min(distance_sq, marker_distance_sq)
                if center_distance_sq > pick_radius_px * pick_radius_px and (
                    marker_distance_sq is None
                    or marker_distance_sq > marker_tolerance_px * marker_tolerance_px
                ):
                    debug_candidate["decision"] = "outside_radius"
                    _append_pick_debug_item(debug_candidates, debug_candidate)
                    continue
                target_obj = _resolve_document_object(
                    session,
                    getattr(target, "document_name", ""),
                    getattr(target, "object_name", ""),
                )
                if target_obj is None:
                    debug_candidate["decision"] = "unresolved_object"
                    _append_pick_debug_item(debug_candidates, debug_candidate)
                    continue
                debug_candidate["decision"] = "candidate"
                debug_candidate["resolved_object"] = _describe_pick_object(session, target_obj)
                debug_candidate["distance_px"] = round(distance_sq**0.5, 3)
                _append_pick_debug_item(debug_candidates, debug_candidate)
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_distance_sq = distance_sq
                    best_target_kind = (
                        target.target_kind.value if target.target_kind is not None else ""
                    )
                    best_target_obj = target_obj
        _perf_set_fields(
            session,
            provider_overlay_pick_result=_describe_pick_object(session, best_target_obj),
        )
        _emit_pick_debug(
            session,
            "pick_provider_overlay_target_from_overlays",
            mouse_pos=mouse_pos,
            fallback_radius_px=radius_px,
            candidates=debug_candidates,
            result=_describe_pick_target(session, best_target_kind, best_target_obj),
        )
        return (best_target_kind, best_target_obj)


def pick_provider_overlay_target_from_objects_info(session, mouse_pos):
    with _perf_trace_span(
        session,
        "pick_provider_overlay_target_from_objects_info",
        mouse_pos=mouse_pos,
    ):
        if not session.view or not mouse_pos:
            return (None, None)
        try:
            infos = session.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
        except (AttributeError, ReferenceError, RuntimeError):
            return (None, None)
        if not infos:
            return (None, None)

        visible_targets = _collect_visible_provider_overlay_targets(session)
        if not visible_targets:
            _emit_pick_debug(
                session,
                "pick_provider_overlay_target_from_objects_info",
                mouse_pos=mouse_pos,
                objects_info=[_describe_pick_info_entry(info) for info in infos],
                visible_targets=[],
                result=None,
            )
            return (None, None)

        debug_infos = []
        debug_visible_targets = []
        for identity, target in tuple(visible_targets.items())[:_MAX_PICK_DEBUG_ITEMS]:
            debug_visible_targets.append(
                {
                    "identity": list(identity),
                    "target": _describe_pick_overlay_target(target),
                }
            )
        for info in infos:
            info_entry = {
                "info": _describe_pick_info_entry(info),
                "candidates": [],
            }
            for target_kind, target_obj in _iter_provider_overlay_targets_from_info(
                session,
                info,
                visible_targets,
            ):
                _append_pick_debug_item(
                    info_entry["candidates"],
                    _describe_pick_target(session, target_kind, target_obj),
                )
                if target_obj is not None:
                    _perf_set_fields(
                        session,
                        provider_overlay_info_pick_result=_describe_pick_object(
                            session, target_obj
                        ),
                    )
                    _append_pick_debug_item(debug_infos, info_entry)
                    _emit_pick_debug(
                        session,
                        "pick_provider_overlay_target_from_objects_info",
                        mouse_pos=mouse_pos,
                        objects_info=debug_infos,
                        visible_targets=debug_visible_targets,
                        result=_describe_pick_target(session, target_kind, target_obj),
                    )
                    return (target_kind, target_obj)
            _append_pick_debug_item(debug_infos, info_entry)
        _emit_pick_debug(
            session,
            "pick_provider_overlay_target_from_objects_info",
            mouse_pos=mouse_pos,
            objects_info=debug_infos,
            visible_targets=debug_visible_targets,
            result=None,
        )
        return (None, None)


def pick_plan_space_target_from_overlays(session, mouse_pos, radius_px=10):
    if not session.doc or not session.view or not mouse_pos:
        return None
    radius_sq = float(radius_px) * float(radius_px)
    best_space = None
    best_distance_sq = None
    seen = set()
    for obj in session.selection.get_plan_space_instances():
        if not session.selection.is_plan_space_object(obj):
            continue
        name = getattr(obj, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        view_object = getattr(obj, "ViewObject", None)
        if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
            continue
        for start, end in session.overlays.get_space_overlay_segments(obj):
            distance_sq = session._get_screen_distance_sq_to_segment(mouse_pos, start, end)
            if distance_sq is None or distance_sq > radius_sq:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_space = obj
                best_distance_sq = distance_sq
    return best_space


def pick_plan_region_target_from_overlays(session, mouse_pos, radius_px=10):
    if not session.doc or not session.view or not mouse_pos:
        return None
    radius_sq = float(radius_px) * float(radius_px)
    best_region = None
    best_distance_sq = None
    seen = set()
    for obj in session.selection.get_plan_region_instances():
        if not session.selection.is_plan_region_object(obj):
            continue
        name = getattr(obj, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        view_object = getattr(obj, "ViewObject", None)
        if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
            continue
        for start, end in session.overlays.get_region_overlay_segments(obj):
            distance_sq = session._get_screen_distance_sq_to_segment(mouse_pos, start, end)
            if distance_sq is None or distance_sq > radius_sq:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_region = obj
                best_distance_sq = distance_sq
    return best_region


def get_region_pick_polylines(session, region):
    if not session.selection.is_plan_region_object(region):
        return []

    polylines = session.overlays.get_region_overlay_polylines(region)
    if polylines:
        return polylines

    proxy = getattr(region, "Proxy", None)
    points = []
    if proxy and hasattr(proxy, "_get_local_points"):
        try:
            points = list(proxy._get_local_points(region) or [])
        except Exception:
            points = []
    elif hasattr(region, "Points"):
        points = [FreeCAD.Vector(point) for point in (getattr(region, "Points", []) or [])]

    if len(points) < 3:
        return []

    placement = getattr(region, "Placement", None)
    if placement is not None:
        try:
            points = [placement.multVec(FreeCAD.Vector(point)) for point in points]
        except Exception:
            points = [FreeCAD.Vector(point) for point in points]
    return [points + [points[0]]]


def xy_polygon_area(polyline):
    if not polyline or len(polyline) < 4:
        return 0.0
    area = 0.0
    for start, end in zip(polyline, polyline[1:]):
        area += float(start.x) * float(end.y) - float(end.x) * float(start.y)
    return abs(area) * 0.5


def xy_point_in_polygon(point, polyline, tolerance=1e-9):
    if not point or not polyline or len(polyline) < 4:
        return False

    px = float(point.x)
    py = float(point.y)
    inside = False
    points = polyline
    if points[0].distanceToPoint(points[-1]) > tolerance:
        points = list(points) + [points[0]]

    for start, end in zip(points, points[1:]):
        x1 = float(start.x)
        y1 = float(start.y)
        x2 = float(end.x)
        y2 = float(end.y)
        if abs(y2 - y1) <= tolerance:
            continue
        intersects = (y1 > py) != (y2 > py)
        if not intersects:
            continue
        x_cross = x1 + ((py - y1) * (x2 - x1) / (y2 - y1))
        if x_cross >= px - tolerance:
            inside = not inside
    return inside


def pick_plan_region_target_from_polylines(session, mouse_pos):
    with _perf_trace_span(session, "pick_region_target_from_polylines", mouse_pos=mouse_pos):
        if not session.doc or not mouse_pos:
            return None

        point = session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
        if point is None:
            return None

        best_region = None
        best_area = None
        seen = set()
        for obj in session.selection.get_plan_region_instances():
            _perf_count(session, "region_polyline_pick_objects_scanned")
            if not session.selection.is_plan_region_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue

            containing_area = None
            for polyline in session.selection.get_region_pick_polylines(obj):
                if not session.selection.xy_point_in_polygon(point, polyline):
                    continue
                area = session.selection.xy_polygon_area(polyline)
                if area <= 0.0:
                    continue
                if containing_area is None or area < containing_area:
                    containing_area = area

            if containing_area is None:
                continue
            if best_area is None or containing_area < best_area:
                best_region = obj
                best_area = containing_area

        return best_region


def pick_plan_target_from_footprint_faces(
    session, mouse_pos, is_target, get_faces, target_label="target"
):
    span_name = f"pick_{target_label}_target_from_footprints"
    with _perf_trace_span(session, span_name, mouse_pos=mouse_pos):
        if not session.doc or not mouse_pos:
            return None

        point = session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
        if point is None:
            return None

        best_target = None
        best_area = None
        seen = set()
        objects = getattr(session.doc, "Objects", []) or []
        if target_label == "space" and hasattr(session.selection, "get_plan_space_instances"):
            objects = session.selection.get_plan_space_instances()
        elif target_label == "region" and hasattr(session.selection, "get_plan_region_instances"):
            objects = session.selection.get_plan_region_instances()

        for obj in objects or []:
            _perf_count(session, f"{target_label}_objects_scanned")
            if not is_target(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            _perf_count(session, f"{target_label}_visible_candidates")

            containing_area = None
            faces = list(get_faces(obj) or [])
            _perf_count(session, f"{target_label}_footprint_faces_returned", len(faces))
            for face in faces:
                _perf_count(session, f"{target_label}_footprint_faces_tested")
                bound_box = getattr(face, "BoundBox", None)
                if bound_box is None:
                    continue
                test_point = FreeCAD.Vector(point.x, point.y, float(bound_box.ZMin))
                try:
                    if not face.isInside(test_point, 0.001, True):
                        continue
                except Exception:
                    continue
                area = float(getattr(face, "Area", 0.0) or 0.0)
                if containing_area is None or area < containing_area:
                    containing_area = area

            if containing_area is None:
                continue
            _perf_count(session, f"{target_label}_containing_candidates")
            if best_area is None or containing_area < best_area:
                best_target = obj
                best_area = containing_area

        _perf_set_fields(
            session,
            **{f"{target_label}_pick_result": _describe_pick_object(session, best_target)},
        )
        return best_target


def pick_plan_space_target_from_footprints(session, mouse_pos):
    return session.selection.pick_plan_target_from_footprint_faces(
        mouse_pos,
        session._is_plan_space_object,
        session.overlays.get_space_footprint_faces,
        target_label="space",
    )


def pick_plan_region_target_from_footprints(session, mouse_pos):
    return session.selection.pick_plan_target_from_footprint_faces(
        mouse_pos,
        session._is_plan_region_object,
        session.overlays.get_region_footprint_faces,
        target_label="region",
    )


def get_plan_target_at_position(session, mouse_pos, *, include_space_fallback=True):
    with _perf_trace_span(session, "get_plan_target_at_position", mouse_pos=mouse_pos):
        if not session.view or not mouse_pos:
            return (None, None)
        prioritize_provider_targets = _should_prioritize_provider_targets_for_mode(session)
        try:
            with _perf_trace_span(session, "view_get_objects_info"):
                infos = session.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
        except (AttributeError, ReferenceError, RuntimeError):
            infos = None
        if not infos:
            infos = []
        _perf_count(session, "objects_info_entries", len(infos))

        wall_candidate = None
        symbol_candidate = None
        provider_candidate = None
        region_candidate = None
        space_candidate = None
        debug_infos = []
        result = (None, None)
        for info in infos:
            _perf_count(session, "objects_info_scanned")
            if not info:
                continue
            doc_name = info.get("Document")
            obj_name = info.get("Object")
            if not doc_name or not obj_name:
                continue
            obj = _resolve_document_object(session, doc_name, obj_name)
            if obj is None:
                continue
            parent_obj = info.get("ParentObject")
            target_kind, target_obj = plan_targets.get_plan_pick_target_for_object(
                session,
                obj,
                parent_obj=parent_obj,
            )
            _append_pick_debug_item(
                debug_infos,
                {
                    "info": _describe_pick_info_entry(info),
                    "resolved_object": _describe_pick_object(session, obj),
                    "target": _describe_pick_target(session, target_kind, target_obj),
                },
            )
            if target_kind == "opening":
                result = ("opening", target_obj)
                break
            if target_kind == "symbol" and symbol_candidate is None:
                symbol_candidate = target_obj
            elif target_kind == "provider" and provider_candidate is None:
                provider_candidate = target_obj
            elif target_kind == "region" and region_candidate is None:
                region_candidate = target_obj
            elif target_kind == "wall" and wall_candidate is None:
                wall_candidate = target_obj
            elif target_kind == "space" and space_candidate is None:
                space_candidate = target_obj
        if result == (None, None):
            if provider_candidate is None:
                provider_overlay_kind, provider_overlay_obj = (
                    session.selection.pick_provider_overlay_target_from_overlays(
                        mouse_pos,
                        radius_px=_PROVIDER_OVERLAY_PICK_RADIUS_PX,
                    )
                )
                if provider_overlay_kind == "provider" and provider_overlay_obj is not None:
                    provider_candidate = provider_overlay_obj
            if prioritize_provider_targets and provider_candidate is not None:
                result = ("provider", provider_candidate)
            elif symbol_candidate is not None and wall_candidate is None:
                result = ("symbol", symbol_candidate)
            else:
                opening_candidates = None
                if wall_candidate is not None:
                    opening_candidates = session.openings.get_wall_hosted_openings(wall_candidate)
                opening_candidate = session.selection.pick_plan_opening_target_from_overlays(
                    mouse_pos,
                    candidates=opening_candidates,
                )
                if opening_candidate is not None:
                    result = ("opening", opening_candidate)
                elif symbol_candidate is None:
                    symbol_candidate = session.selection.pick_plan_symbol_target_from_overlays(
                        mouse_pos
                    )
            if result == (None, None) and symbol_candidate is not None:
                result = ("symbol", symbol_candidate)
            elif result == (None, None) and wall_candidate is not None:
                result = ("wall", wall_candidate)
            elif result == (None, None) and provider_candidate is not None:
                result = ("provider", provider_candidate)
            elif result == (None, None):
                if region_candidate is None:
                    region_candidate = session.selection.pick_plan_region_target_from_polylines(
                        mouse_pos
                    )
                if region_candidate is None:
                    region_candidate = session.selection.pick_plan_region_target_from_footprints(
                        mouse_pos
                    )
                if region_candidate is None:
                    region_candidate = session.selection.pick_plan_region_target_from_overlays(
                        mouse_pos
                    )
                if region_candidate is not None:
                    result = ("region", region_candidate)
                elif include_space_fallback:
                    if space_candidate is None:
                        space_candidate = session.selection.pick_plan_space_target_from_footprints(
                            mouse_pos
                        )
                    if space_candidate is None:
                        space_candidate = session.selection.pick_plan_space_target_from_overlays(
                            mouse_pos
                        )
                    if space_candidate is not None:
                        result = ("space", space_candidate)
        _perf_set_fields(
            session,
            picked_target=_describe_pick_target(session, result[0], result[1]),
        )
        _emit_pick_debug(
            session,
            "get_plan_target_at_position",
            mouse_pos=mouse_pos,
            overlay_mode=_get_plan_provider_overlay_pick_mode(session),
            prioritize_provider_targets=prioritize_provider_targets,
            include_space_fallback=bool(include_space_fallback),
            objects_info=debug_infos,
            candidates={
                "symbol": _describe_pick_target(session, "symbol", symbol_candidate),
                "provider": _describe_pick_target(session, "provider", provider_candidate),
                "wall": _describe_pick_target(session, "wall", wall_candidate),
                "region": _describe_pick_target(session, "region", region_candidate),
                "space": _describe_pick_target(session, "space", space_candidate),
            },
            result=_describe_pick_target(session, result[0], result[1]),
        )
        return result


def get_plan_target_from_edit_node(session, node):
    if not node:
        return (None, None)
    node_kind = node[0]
    if node_kind in ("provider_overlay_point", "provider_overlay_target"):
        target_kind, obj = get_provider_overlay_target_from_edit_node(session, node)
        if session.selection.is_valid_plan_target(target_kind, obj):
            return (target_kind, obj)
        return session.selection.get_plan_target_for_object(obj)
    if node_kind == "opening_handle":
        opening = node[1]
        if session.openings.is_hosted_opening_object(opening):
            return ("opening", opening)
        return (None, None)
    if node_kind == "symbol_handle":
        symbol = node[1]
        if session.visibility.is_plan_symbol_instance(symbol):
            return ("symbol", symbol)
        return (None, None)
    try:
        point = node[1]
        doc = FreeCAD.getDocument(str(point.documentName.getValue()))
        obj = doc.getObject(str(point.objectName.getValue()))
    except Exception:
        return (None, None)
    if session.openings.is_hosted_opening_object(obj):
        return ("opening", obj)
    return session.selection.get_plan_target_for_object(obj)


def get_edit_node(session, mouse_pos):
    symbol_handle_role = session.overlays.pick_selected_symbol_handle(mouse_pos)
    if symbol_handle_role is not None:
        node = (
            "symbol_handle",
            plan_selection.get_selected_plan_target_object(session, "symbol"),
            symbol_handle_role,
        )
        _emit_pick_debug(
            session,
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="selected_symbol_handle",
            result=node,
        )
        return node
    opening_handle_index = session.selection.pick_selected_opening_handle(mouse_pos)
    if opening_handle_index is not None:
        node = (
            "opening_handle",
            plan_selection.get_selected_plan_target_object(session, "opening"),
            opening_handle_index,
        )
        _emit_pick_debug(
            session,
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="selected_opening_handle",
            result=node,
        )
        return node
    provider_handle_index = session.overlays.pick_selected_provider_handle(mouse_pos)
    if provider_handle_index is not None:
        node = (
            "provider_handle",
            plan_selection.get_selected_plan_target_object(session, "provider"),
            provider_handle_index,
        )
        _emit_pick_debug(
            session,
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="selected_provider_handle",
            result=node,
        )
        return node
    target_kind, target_obj = session.selection.pick_provider_overlay_target_from_objects_info(
        mouse_pos
    )
    if target_obj is not None:
        node = ("provider_overlay_target", target_kind, target_obj)
        _emit_pick_debug(
            session,
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="provider_overlay_objects_info",
            result=node,
        )
        return node
    target_kind, target_obj = session.selection.pick_provider_overlay_target_from_overlays(
        mouse_pos
    )
    if target_obj is not None:
        node = ("provider_overlay_target", target_kind, target_obj)
        _emit_pick_debug(
            session,
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="provider_overlay_overlays",
            result=node,
        )
        return node
    if not session._render_manager:
        _emit_pick_debug(
            session,
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="no_render_manager",
            result=None,
        )
        return None
    try:
        from pivy import coin
    except Exception:
        _emit_pick_debug(
            session,
            "get_edit_node",
            mouse_pos=mouse_pos,
            source="coin_import_failed",
            result=None,
        )
        return None

    ray_pick = coin.SoRayPickAction(session._render_manager.getViewportRegion())
    ray_pick.setPoint(coin.SbVec2s(*mouse_pos))
    ray_pick.setRadius(8)
    ray_pick.setPickAll(True)
    ray_pick.apply(session._render_manager.getSceneGraph())
    picked_points = ray_pick.getPickedPointList()
    if picked_points:
        for picked_point in picked_points:
            path = picked_point.getPath()
            point = path.getNode(path.getLength() - 2)
            try:
                sub_element = str(point.subElementName.getValue())
            except Exception:
                continue
            if is_provider_overlay_point_subname(sub_element):
                node = ("provider_overlay_point", point)
                _emit_pick_debug(
                    session,
                    "get_edit_node",
                    mouse_pos=mouse_pos,
                    source="ray_pick_provider_overlay_point",
                    result=node,
                )
                return node
            if "EditNode" in sub_element:
                node = ("edit_node", point)
                _emit_pick_debug(
                    session,
                    "get_edit_node",
                    mouse_pos=mouse_pos,
                    source="ray_pick_edit_node",
                    result=node,
                )
                return node
    _emit_pick_debug(
        session,
        "get_edit_node",
        mouse_pos=mouse_pos,
        source="no_edit_node",
        result=None,
    )
    return None


def pick_selected_opening_handle(session, mouse_pos, radius_px=10):
    opening = plan_selection.get_selected_plan_target_object(session, "opening")
    if not session.openings.is_hosted_opening_object(opening) or not session.view:
        return None
    try:
        cursor_x = int(mouse_pos[0])
        cursor_y = int(mouse_pos[1])
    except Exception:
        return None
    best_index = None
    best_distance_sq = None
    for idx, _role, point, _marker in session.overlays.get_selected_opening_handle_specs(opening):
        try:
            screen_x, screen_y = session.view.getPointOnScreen(point)
        except Exception:
            continue
        dx = float(screen_x) - float(cursor_x)
        dy = float(screen_y) - float(cursor_y)
        distance_sq = dx * dx + dy * dy
        if distance_sq > radius_px * radius_px:
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_index = idx
            best_distance_sq = distance_sq
    return best_index


def get_provider_overlay_target_from_edit_node(session, node):
    if not node:
        return (None, None)
    node_kind = node[0]
    if node_kind == "provider_overlay_target":
        try:
            return (node[1], node[2])
        except Exception:
            return (None, None)
    if node_kind != "provider_overlay_point":
        return (None, None)
    try:
        point = node[1]
        document_name = str(point.documentName.getValue())
        object_name = str(point.objectName.getValue())
        subname = str(point.subElementName.getValue())
    except Exception:
        return (None, None)
    obj = _resolve_document_object(session, document_name, object_name)
    if obj is None:
        return (None, None)
    target_kind = _parse_provider_overlay_target_kind(subname)
    if target_kind and session.selection.is_valid_plan_target(target_kind, obj):
        return (target_kind, obj)
    inferred_kind, inferred_obj = session.selection.get_plan_target_for_object(obj)
    if inferred_kind and inferred_obj:
        return (inferred_kind, inferred_obj)
    return (None, obj)


def is_provider_overlay_point_subname(subname):
    return str(subname or "").startswith(_PROVIDER_OVERLAY_POINT_PREFIX + ":")


def _parse_provider_overlay_target_kind(subname):
    parts = str(subname or "").split(":")
    if len(parts) < 2 or parts[0] != _PROVIDER_OVERLAY_POINT_PREFIX:
        return ""
    return parts[1].strip()


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


def _coerce_overlay_point_vector(point):
    if point is None:
        return None
    if isinstance(point, FreeCAD.Vector):
        return FreeCAD.Vector(point)
    try:
        return FreeCAD.Vector(float(point[0]), float(point[1]), float(point[2]))
    except (TypeError, ValueError, IndexError):
        try:
            return FreeCAD.Vector(
                float(point.x),
                float(point.y),
                float(getattr(point, "z", 0.0) or 0.0),
            )
        except Exception:
            return None


def _collect_visible_provider_overlay_targets(session):
    get_overlays = getattr(session, "get_plan_provider_overlays", None)
    if not callable(get_overlays):
        return {}
    is_visible = getattr(session, "is_plan_provider_overlay_visible", None)
    targets = {}
    for overlay in tuple(get_overlays() or ()):
        if not bool(getattr(overlay, "visible", True)):
            continue
        if callable(is_visible) and not is_visible(overlay):
            continue
        for target in tuple(getattr(overlay, "point_targets", ()) or ()):
            if not _has_provider_overlay_target_identity(target):
                continue
            identity = _get_provider_overlay_target_identity(session, target)
            if identity is None or identity in targets:
                continue
            targets[identity] = target
    return targets


def _iter_provider_overlay_targets_from_info(session, info, visible_targets):
    if not info or not visible_targets:
        return ()
    yielded = []
    for obj in _iter_objects_info_candidate_objects(session, info):
        if obj is None:
            continue
        identity = (
            str(getattr(getattr(obj, "Document", None), "Name", "") or "").strip(),
            str(getattr(obj, "Name", "") or "").strip(),
        )
        if not identity[1]:
            continue
        target = visible_targets.get(identity)
        if target is None:
            continue
        yielded.append((target.target_kind.value if target.target_kind is not None else "", obj))
    return tuple(yielded)


def _iter_objects_info_candidate_objects(session, info):
    if not info:
        return ()
    candidates = []
    doc_name = str(info.get("Document") or "").strip()
    obj_name = str(info.get("Object") or "").strip()
    if obj_name:
        resolved = _resolve_document_object(session, doc_name, obj_name)
        if resolved is not None:
            candidates.append(resolved)
    parent_obj = info.get("ParentObject")
    if parent_obj is not None and parent_obj not in candidates:
        candidates.append(parent_obj)
    return tuple(candidates)


def _get_provider_overlay_pick_radius_px(session, overlay, point, fallback_radius_px):
    radius_px = max(1.0, float(fallback_radius_px))
    marker_size = max(1.0, float(getattr(overlay, "marker_size", 160.0) or 160.0))
    marker_half_size = marker_size / 2.0
    marker_extent_factor = _get_provider_overlay_pick_extent_factor(overlay.marker_kind)
    try:
        center_x, center_y = session.view.getPointOnScreen(point)
        edge_x, edge_y = session.view.getPointOnScreen(
            FreeCAD.Vector(
                point.x + (marker_half_size * marker_extent_factor),
                point.y,
                point.z,
            )
        )
        projected_radius_px = (
            (float(edge_x) - float(center_x)) ** 2 + (float(edge_y) - float(center_y)) ** 2
        ) ** 0.5
        radius_px = max(
            radius_px,
            projected_radius_px
            + max(
                _PROVIDER_OVERLAY_PICK_PADDING_PX,
                projected_radius_px * _PROVIDER_OVERLAY_PICK_PADDING_RATIO,
            ),
        )
    except Exception:
        pass
    return radius_px


def _get_provider_overlay_marker_screen_distance_sq(session, mouse_pos, overlay, point):
    marker_segments = _get_provider_overlay_marker_segments(overlay, point)
    if not marker_segments:
        return None
    best_distance_sq = None
    for start, end in marker_segments:
        distance_sq = get_screen_distance_sq_to_segment(session, mouse_pos, start, end)
        if distance_sq is None:
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
    return best_distance_sq


def _get_provider_overlay_marker_segments(overlay, point):
    try:
        from bimplan.overlays.providers import _get_point_marker_segment_specs
    except Exception:
        return ()
    try:
        specs = _get_point_marker_segment_specs(
            point,
            label="provider-overlay-pick",
            color=(0.0, 0.0, 0.0),
            width=float(getattr(overlay, "line_width", 2.0) or 2.0),
            dotted=bool(getattr(overlay, "dotted", False)),
            marker_size=float(getattr(overlay, "marker_size", 160.0) or 160.0),
            marker_kind=overlay.marker_kind,
        )
    except Exception:
        return ()
    return tuple(
        (spec.get("start"), spec.get("end"))
        for spec in tuple(specs or ())
        if spec.get("start") is not None and spec.get("end") is not None
    )


def _get_provider_overlay_marker_tolerance_px(overlay, fallback_radius_px):
    line_width = max(1.0, float(getattr(overlay, "line_width", 2.0) or 2.0))
    return max(
        _PROVIDER_OVERLAY_MARKER_TOLERANCE_BASE_PX,
        2.0 + (line_width * _PROVIDER_OVERLAY_MARKER_TOLERANCE_WIDTH_SCALE),
    )


def _get_provider_overlay_pick_extent_factor(marker_kind):
    if marker_kind in (
        PlanOverlayMarkerKind.SQUARE,
        PlanOverlayMarkerKind.HOURGLASS,
    ):
        return math.sqrt(2.0)
    return 1.0


def _get_provider_overlay_target_identity(session, target):
    object_name = str(getattr(target, "object_name", "") or "").strip()
    if not object_name:
        return None
    document_name = str(getattr(target, "document_name", "") or "").strip()
    if not document_name:
        document_name = str(getattr(getattr(session, "doc", None), "Name", "") or "")
    return (document_name, object_name)


def _has_provider_overlay_target_identity(target):
    return bool(str(getattr(target, "object_name", "") or "").strip())


clear_hovered_plan_targets = plan_hover_picking.clear_hovered_plan_targets
get_hovered_plan_target = plan_hover_picking.get_hovered_plan_target
prime_hover_pick_caches = plan_hover_picking.prime_hover_pick_caches
queue_prime_hover_pick_caches = plan_hover_picking.queue_prime_hover_pick_caches
should_skip_hover_pick = plan_hover_picking.should_skip_hover_pick
update_hovered_plan_target = plan_hover_picking.update_hovered_plan_target
