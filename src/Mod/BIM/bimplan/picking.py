# SPDX-License-Identifier: LGPL-2.1-or-later

"""Pointer picking helpers for BIM Plan Edit."""

import FreeCAD


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
    return session._get_screen_distance_sq_to_projected_segment(
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


def pick_plan_symbol_target_from_overlays(session, mouse_pos, radius_px=10):
    with session._plan_perf_trace_span(
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
        for obj in session._get_plan_symbol_instances():
            session._plan_perf_count("symbol_overlay_pick_candidates")
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            for projected in session._get_symbol_overlay_screen_polylines(obj):
                for start_xy, end_xy in zip(projected, projected[1:]):
                    session._plan_perf_count("symbol_overlay_pick_segments_scanned")
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
        session._plan_perf_set_fields(
            symbol_overlay_pick_result=session._plan_perf_describe_object(best_symbol)
        )
        return best_symbol


def pick_plan_opening_target_from_overlays(session, mouse_pos, radius_px=10, candidates=None):
    with session._plan_perf_trace_span(
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
        if candidates is None:
            objects = getattr(session.doc, "Objects", []) or []
        else:
            objects = candidates
        for obj in objects or []:
            session._plan_perf_count("opening_overlay_pick_objects_scanned")
            if not session._is_hosted_opening_object(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            session._plan_perf_count("opening_overlay_pick_candidates")
            for projected in session._get_opening_overlay_screen_polylines(obj):
                for start_xy, end_xy in zip(projected, projected[1:]):
                    session._plan_perf_count("opening_overlay_pick_segments_scanned")
                    distance_sq = session._get_screen_distance_sq_to_projected_segment(
                        cursor_xy, start_xy, end_xy
                    )
                    if distance_sq is None or distance_sq > screen_radius_sq:
                        continue
                    if best_distance_sq is None or distance_sq < best_distance_sq:
                        best_opening = obj
                        best_distance_sq = distance_sq
        session._plan_perf_set_fields(
            opening_overlay_pick_mode="screen",
            opening_overlay_pick_result=session._plan_perf_describe_object(best_opening),
        )
        return best_opening


def pick_plan_space_target_from_overlays(session, mouse_pos, radius_px=10):
    if not session.doc or not session.view or not mouse_pos:
        return None
    radius_sq = float(radius_px) * float(radius_px)
    best_space = None
    best_distance_sq = None
    seen = set()
    for obj in getattr(session.doc, "Objects", []) or []:
        if not session._is_plan_space_object(obj):
            continue
        name = getattr(obj, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        view_object = getattr(obj, "ViewObject", None)
        if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
            continue
        for start, end in session._get_space_overlay_segments(obj):
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
    for obj in getattr(session.doc, "Objects", []) or []:
        if not session._is_plan_region_object(obj):
            continue
        name = getattr(obj, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        view_object = getattr(obj, "ViewObject", None)
        if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
            continue
        for start, end in session._get_region_overlay_segments(obj):
            distance_sq = session._get_screen_distance_sq_to_segment(mouse_pos, start, end)
            if distance_sq is None or distance_sq > radius_sq:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_region = obj
                best_distance_sq = distance_sq
    return best_region


def get_region_pick_polylines(session, region):
    if not session._is_plan_region_object(region):
        return []

    polylines = session._get_region_overlay_polylines(region)
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
    if not session.doc or not mouse_pos:
        return None

    point = session._get_plan_point_from_mouse_pos(mouse_pos)
    if point is None:
        return None

    best_region = None
    best_area = None
    seen = set()
    for obj in getattr(session.doc, "Objects", []) or []:
        if not session._is_plan_region_object(obj):
            continue
        name = getattr(obj, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        view_object = getattr(obj, "ViewObject", None)
        if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
            continue

        containing_area = None
        for polyline in session._get_region_pick_polylines(obj):
            if not session._xy_point_in_polygon(point, polyline):
                continue
            area = session._xy_polygon_area(polyline)
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
    with session._plan_perf_trace_span(span_name, mouse_pos=mouse_pos):
        if not session.doc or not mouse_pos:
            return None

        point = session._get_plan_point_from_mouse_pos(mouse_pos)
        if point is None:
            return None

        best_target = None
        best_area = None
        seen = set()
        for obj in getattr(session.doc, "Objects", []) or []:
            session._plan_perf_count(f"{target_label}_objects_scanned")
            if not is_target(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if view_object and hasattr(view_object, "Visibility") and not view_object.Visibility:
                continue
            session._plan_perf_count(f"{target_label}_visible_candidates")

            containing_area = None
            faces = list(get_faces(obj) or [])
            session._plan_perf_count(f"{target_label}_footprint_faces_returned", len(faces))
            for face in faces:
                session._plan_perf_count(f"{target_label}_footprint_faces_tested")
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
            session._plan_perf_count(f"{target_label}_containing_candidates")
            if best_area is None or containing_area < best_area:
                best_target = obj
                best_area = containing_area

        session._plan_perf_set_fields(
            **{f"{target_label}_pick_result": session._plan_perf_describe_object(best_target)}
        )
        return best_target


def pick_plan_space_target_from_footprints(session, mouse_pos):
    return session._pick_plan_target_from_footprint_faces(
        mouse_pos,
        session._is_plan_space_object,
        session._get_space_footprint_faces,
        target_label="space",
    )


def pick_plan_region_target_from_footprints(session, mouse_pos):
    return session._pick_plan_target_from_footprint_faces(
        mouse_pos,
        session._is_plan_region_object,
        session._get_region_footprint_faces,
        target_label="region",
    )


def get_plan_target_at_position(session, mouse_pos):
    with session._plan_perf_trace_span("get_plan_target_at_position", mouse_pos=mouse_pos):
        if not session.view or not mouse_pos:
            return (None, None)
        try:
            with session._plan_perf_trace_span("view_get_objects_info"):
                infos = session.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
        except (AttributeError, ReferenceError, RuntimeError):
            infos = None
        if not infos:
            infos = []
        session._plan_perf_count("objects_info_entries", len(infos))

        wall_candidate = None
        symbol_candidate = None
        region_candidate = None
        space_candidate = None
        result = (None, None)
        for info in infos:
            session._plan_perf_count("objects_info_scanned")
            if not info:
                continue
            doc_name = info.get("Document")
            obj_name = info.get("Object")
            if not doc_name or not obj_name:
                continue
            try:
                doc = FreeCAD.getDocument(str(doc_name))
            except Exception:
                doc = None
            if not doc:
                continue
            obj = doc.getObject(str(obj_name))
            parent_obj = info.get("ParentObject")
            target_kind, target_obj = session._get_plan_target_for_object(
                obj, parent_obj=parent_obj
            )
            if target_kind == "opening":
                result = ("opening", target_obj)
                break
            if target_kind == "symbol" and symbol_candidate is None:
                symbol_candidate = target_obj
            elif target_kind == "region" and region_candidate is None:
                region_candidate = target_obj
            elif target_kind == "wall" and wall_candidate is None:
                wall_candidate = target_obj
            elif target_kind == "space" and space_candidate is None:
                space_candidate = target_obj
        if result == (None, None):
            if symbol_candidate is not None and wall_candidate is None:
                result = ("symbol", symbol_candidate)
            else:
                opening_candidates = None
                if wall_candidate is not None:
                    opening_candidates = session._get_wall_hosted_openings(wall_candidate)
                opening_candidate = session._pick_plan_opening_target_from_overlays(
                    mouse_pos,
                    candidates=opening_candidates,
                )
                if opening_candidate is not None:
                    result = ("opening", opening_candidate)
                elif symbol_candidate is None:
                    symbol_candidate = session._pick_plan_symbol_target_from_overlays(mouse_pos)
            if result == (None, None) and symbol_candidate is not None:
                result = ("symbol", symbol_candidate)
            elif result == (None, None) and wall_candidate is not None:
                result = ("wall", wall_candidate)
            elif result == (None, None):
                if region_candidate is None:
                    region_candidate = session._pick_plan_region_target_from_polylines(mouse_pos)
                if region_candidate is None:
                    region_candidate = session._pick_plan_region_target_from_footprints(mouse_pos)
                if region_candidate is None:
                    region_candidate = session._pick_plan_region_target_from_overlays(mouse_pos)
                if region_candidate is not None:
                    result = ("region", region_candidate)
                else:
                    if space_candidate is None:
                        space_candidate = session._pick_plan_space_target_from_footprints(mouse_pos)
                    if space_candidate is None:
                        space_candidate = session._pick_plan_space_target_from_overlays(mouse_pos)
                    if space_candidate is not None:
                        result = ("space", space_candidate)
        session._plan_perf_set_fields(
            picked_target=session._plan_perf_describe_target(result[0], result[1])
        )
        return result


def get_plan_target_from_edit_node(session, node):
    if not node:
        return (None, None)
    node_kind = node[0]
    if node_kind == "opening_handle":
        opening = node[1]
        if session._is_hosted_opening_object(opening):
            return ("opening", opening)
        return (None, None)
    if node_kind == "symbol_handle":
        symbol = node[1]
        if session._is_plan_symbol_instance(symbol):
            return ("symbol", symbol)
        return (None, None)
    try:
        point = node[1]
        doc = FreeCAD.getDocument(str(point.documentName.getValue()))
        obj = doc.getObject(str(point.objectName.getValue()))
    except Exception:
        return (None, None)
    if session._is_hosted_opening_object(obj):
        return ("opening", obj)
    return session._get_plan_target_for_object(obj)


def get_hovered_plan_target(session):
    for kind, obj in (
        ("opening", session.hovered_opening),
        ("symbol", session.hovered_symbol),
        ("wall", session.hovered_wall),
        ("region", session.hovered_region),
        ("space", session.hovered_space),
    ):
        if obj is not None:
            return (kind, obj)
    return (None, None)
