# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared plan-geometry helpers for BIM footprint polylines."""

import FreeCAD


def _normalize_point_list(points):
    normalized = []
    for point in points or []:
        try:
            normalized.append(FreeCAD.Vector(point))
        except Exception:
            continue
    return normalized


def collect_edge_points(edge):
    """Return a stable list of sample points for a plan edge."""

    try:
        points = edge.tessellate(1)
    except Exception:
        points = []
    if isinstance(points, tuple) and points:
        points = points[0]
    points = _normalize_point_list(points)
    if len(points) >= 2:
        return points

    try:
        points = edge.discretize(Deflection=1.0)
    except Exception:
        points = []
    points = _normalize_point_list(points)
    if len(points) >= 2:
        return points

    points = _normalize_point_list(
        [vertex.Point for vertex in getattr(edge, "Vertexes", []) or []]
    )
    return points if len(points) >= 2 else []


def get_wire_polyline(wire, close=True, tolerance=0.001):
    """Build an ordered polyline by following the edges of a wire."""

    points = []
    for edge in getattr(wire, "Edges", []) or []:
        edge_points = collect_edge_points(edge)
        if len(edge_points) < 2:
            continue
        if points:
            last_point = points[-1]
            start_distance = edge_points[0].distanceToPoint(last_point)
            end_distance = edge_points[-1].distanceToPoint(last_point)
            if end_distance < start_distance:
                edge_points.reverse()
            if edge_points[0].distanceToPoint(last_point) < tolerance:
                edge_points = edge_points[1:]
        points.extend(edge_points)

    if len(points) < 2:
        return []
    if close and points[0].distanceToPoint(points[-1]) > tolerance:
        points.append(FreeCAD.Vector(points[0]))
    return points


def get_face_wire_polylines(faces, close=True, tolerance=0.001):
    """Return ordered wire polylines from a sequence of footprint faces."""

    polylines = []
    for face in faces or []:
        for wire in getattr(face, "Wires", []) or []:
            points = get_wire_polyline(wire, close=close, tolerance=tolerance)
            if len(points) >= 2:
                polylines.append(points)
    return polylines
