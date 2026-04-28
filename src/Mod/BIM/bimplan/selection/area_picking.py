# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space and region area picking helpers for BIM Plan Edit."""

import FreeCAD

from . import overlay_picking as plan_overlay_picking
from . import picking_debug as plan_picking_debug
from . import targets as plan_targets


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_set_fields(session, **fields):
    return session.performance.plan_perf_set_fields(**fields)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _is_pick_visible_view_object(view_object):
    return not (view_object and getattr(view_object, "Visibility", True) is False)


def _is_pick_visible_object(obj):
    view_object = getattr(obj, "ViewObject", None)
    return _is_pick_visible_view_object(view_object)


def _iter_pick_objects(objects, *, unique_names=False):
    seen = set()
    for obj in objects or []:
        if unique_names:
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
        if not _is_pick_visible_object(obj):
            continue
        yield obj


def _get_region_local_points(region):
    proxy = getattr(region, "Proxy", None)
    get_local_points = getattr(proxy, "_get_local_points", None)
    if callable(get_local_points):
        try:
            return list(get_local_points(region) or [])
        except Exception:
            return []
    points = getattr(region, "Points", None)
    if points is None:
        return []
    return [FreeCAD.Vector(point) for point in (points or [])]


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
        lambda obj: plan_targets.is_plan_space_object(session, obj),
        "plan_space_instance_objects_scanned",
        "build_plan_space_instances_cache",
    )


def get_plan_region_instances(session):
    return _get_cached_plan_instances(
        session,
        "plan_region_instances_cache",
        lambda obj: plan_targets.is_plan_region_object(session, obj),
        "plan_region_instance_objects_scanned",
        "build_plan_region_instances_cache",
    )


def pick_plan_space_target_from_overlays(session, mouse_pos, radius_px=10):
    if not session.doc or not session.view or not mouse_pos:
        return None
    return plan_overlay_picking.pick_best_target_from_overlay_segments(
        session,
        (
            obj
            for obj in _iter_pick_objects(
                get_plan_space_instances(session),
                unique_names=True,
            )
            if plan_targets.is_plan_space_object(session, obj)
        ),
        session.overlays.geometry.get_space_overlay_segments,
        mouse_pos,
        radius_px,
    )


def pick_plan_region_target_from_overlays(session, mouse_pos, radius_px=10):
    if not session.doc or not session.view or not mouse_pos:
        return None
    return plan_overlay_picking.pick_best_target_from_overlay_segments(
        session,
        (
            obj
            for obj in _iter_pick_objects(
                get_plan_region_instances(session),
                unique_names=True,
            )
            if plan_targets.is_plan_region_object(session, obj)
        ),
        session.overlays.geometry.get_region_overlay_segments,
        mouse_pos,
        radius_px,
    )


def get_region_pick_polylines(session, region):
    if not plan_targets.is_plan_region_object(session, region):
        return []

    polylines = session.overlays.geometry.get_region_overlay_polylines(region)
    if polylines:
        return polylines

    points = _get_region_local_points(region)

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
        for obj in get_plan_region_instances(session):
            _perf_count(session, "region_polyline_pick_objects_scanned")
            if not plan_targets.is_plan_region_object(session, obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if not _is_pick_visible_view_object(view_object):
                continue

            containing_area = None
            for polyline in get_region_pick_polylines(session, obj):
                if not xy_point_in_polygon(point, polyline):
                    continue
                area = xy_polygon_area(polyline)
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
        if target_label == "space":
            objects = get_plan_space_instances(session)
        elif target_label == "region":
            objects = get_plan_region_instances(session)

        for obj in objects or []:
            _perf_count(session, f"{target_label}_objects_scanned")
            if not is_target(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if not _is_pick_visible_view_object(view_object):
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
            **{
                f"{target_label}_pick_result": plan_picking_debug.describe_pick_object(
                    session, best_target
                )
            },
        )
        return best_target


def pick_plan_space_target_from_footprints(session, mouse_pos):
    return pick_plan_target_from_footprint_faces(
        session,
        mouse_pos,
        lambda obj: plan_targets.is_plan_space_object(session, obj),
        session.overlays.geometry.get_space_footprint_faces,
        target_label="space",
    )


def pick_plan_region_target_from_footprints(session, mouse_pos):
    return pick_plan_target_from_footprint_faces(
        session,
        mouse_pos,
        lambda obj: plan_targets.is_plan_region_object(session, obj),
        session.overlays.geometry.get_region_footprint_faces,
        target_label="region",
    )
