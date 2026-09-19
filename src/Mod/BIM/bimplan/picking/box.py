# SPDX-License-Identifier: LGPL-2.1-or-later

"""Screen-region selection for semantic Plan Edit representations."""

from .viewport import viewport_pixel


def _point_in_rect(point, rect):
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def _segment_intersects_rect(start, end, rect):
    if _point_in_rect(start, rect) or _point_in_rect(end, rect):
        return True
    min_x, min_y, max_x, max_y = rect
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    lower, upper = 0.0, 1.0
    for p, q in (
        (-dx, start[0] - min_x),
        (dx, max_x - start[0]),
        (-dy, start[1] - min_y),
        (dy, max_y - start[1]),
    ):
        if abs(p) <= 1e-12:
            if q < 0.0:
                return False
            continue
        ratio = q / p
        if p < 0.0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower > upper:
            return False
    return True


def _point_in_polygon(point, polygon):
    inside = False
    x, y = point
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        if (start[1] > y) == (end[1] > y):
            continue
        crossing_x = (end[0] - start[0]) * (y - start[1]) / (end[1] - start[1]) + start[0]
        if x < crossing_x:
            inside = not inside
    return inside


def _project_polylines(session, polylines):
    projected = []
    for polyline in polylines or ():
        points = []
        for point in polyline or ():
            try:
                screen = session.view.getPointOnScreen(point)
                points.append((float(screen[0]), float(screen[1])))
            except Exception:
                points = []
                break
        if points:
            projected.append(tuple(points))
    return tuple(projected)


def _target_screen_polylines(session, kind, obj):
    geometry = session.overlays.geometry
    if kind == "wall":
        return _project_polylines(session, geometry.get_wall_overlay_polylines(obj))
    if kind == "space":
        return _project_polylines(session, geometry.get_space_overlay_polylines(obj))
    if kind == "region":
        return _project_polylines(session, geometry.get_region_overlay_polylines(obj))
    if kind == "opening":
        return tuple(geometry.get_opening_overlay_screen_polylines(obj) or ())
    if kind == "symbol":
        return tuple(session.overlays.symbols.get_symbol_overlay_screen_polylines(obj) or ())
    return ()


def _screen_polylines_match(polylines, rect, crossing):
    points = [point for polyline in polylines for point in polyline]
    if not points:
        return False
    if not crossing:
        center = (
            (min(point[0] for point in points) + max(point[0] for point in points)) / 2.0,
            (min(point[1] for point in points) + max(point[1] for point in points)) / 2.0,
        )
        return _point_in_rect(center, rect)
    if any(
        _segment_intersects_rect(start, end, rect)
        for polyline in polylines
        for start, end in zip(polyline, polyline[1:])
    ):
        return True
    corners = (
        (rect[0], rect[1]),
        (rect[0], rect[3]),
        (rect[2], rect[1]),
        (rect[2], rect[3]),
    )
    return any(
        len(polyline) >= 3 and any(_point_in_polygon(corner, polyline) for corner in corners)
        for polyline in polylines
    )


def _native_box_selection_keys(session, start, end):
    query = getattr(session.view, "getBoxSelection", None)
    if not callable(query):
        return set()
    try:
        matches = query((viewport_pixel(start), viewport_pixel(end)), False, False)
    except Exception:
        return set()
    return {
        (str(match.get("Document", "")), str(match.get("Object", "")))
        for match in matches or ()
    }


def get_plan_targets_in_screen_rect(session, start, end):
    """Return semantic targets using native window/crossing direction semantics."""

    start = viewport_pixel(start)
    end = viewport_pixel(end)
    rect = (
        min(float(start[0]), float(end[0])),
        min(float(start[1]), float(end[1])),
        max(float(start[0]), float(end[0])),
        max(float(start[1]), float(end[1])),
    )
    crossing = float(start[0]) > float(end[0])
    native_keys = _native_box_selection_keys(session, start, end)
    matches = []
    for target in session.selection.targets.get_plan_targets():
        obj = session.selection.targets.resolve_plan_target_object(target)
        if obj is None:
            continue
        polylines = _target_screen_polylines(session, target.kind, obj)
        if polylines:
            matched = _screen_polylines_match(polylines, rect, crossing)
        else:
            doc = getattr(obj, "Document", None)
            matched = (
                str(getattr(doc, "Name", "")), str(getattr(obj, "Name", ""))
            ) in native_keys
        if matched:
            matches.append((target.kind, obj))
    return tuple(matches)
