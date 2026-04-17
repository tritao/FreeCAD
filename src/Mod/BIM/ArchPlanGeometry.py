# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Shared plan-geometry helpers for BIM footprint and overlay polylines."""

import FreeCAD


def _normalize_point_list(points):
    normalized = []
    for point in points or []:
        if isinstance(point, FreeCAD.Vector):
            normalized.append(FreeCAD.Vector(point))
            continue
        try:
            normalized.append(FreeCAD.Vector(point))
        except Exception:
            continue
    return normalized


def collect_edge_points(edge):
    """Return a stable list of points for a plan edge."""

    points = []
    try:
        points = edge.tessellate(1)
    except Exception:
        points = []

    if isinstance(points, tuple) and points:
        points = points[0]

    if points and all(isinstance(point, FreeCAD.Vector) for point in points):
        return _normalize_point_list(points)

    try:
        points = edge.discretize(Deflection=1.0)
    except Exception:
        points = []
    points = _normalize_point_list(points)
    if len(points) >= 2:
        return points

    points = _normalize_point_list([vertex.Point for vertex in getattr(edge, "Vertexes", []) or []])
    return points if len(points) >= 2 else []


def get_wire_polyline(wire, close=True, tolerance=0.001):
    """Build an ordered polyline from a wire by following its edges."""

    points = []
    for edge in getattr(wire, "Edges", []) or []:
        polyline = collect_edge_points(edge)
        if len(polyline) < 2:
            continue
        if points:
            last_point = points[-1]
            start_distance = polyline[0].distanceToPoint(last_point)
            end_distance = polyline[-1].distanceToPoint(last_point)
            if end_distance < start_distance:
                polyline = list(reversed(polyline))
            if polyline[0].distanceToPoint(last_point) < tolerance:
                polyline = polyline[1:]
        points.extend(polyline)

    if len(points) < 2:
        return []
    if close and points[0].distanceToPoint(points[-1]) > tolerance:
        points.append(FreeCAD.Vector(points[0]))
    return points


def get_face_wire_polylines(faces, close=True, tolerance=0.001):
    """Return ordered wire polylines for a sequence of footprint faces."""

    polylines = []
    for face in faces or []:
        for wire in getattr(face, "Wires", []) or []:
            points = get_wire_polyline(wire, close=close, tolerance=tolerance)
            if len(points) >= 2:
                polylines.append(points)
    return polylines
