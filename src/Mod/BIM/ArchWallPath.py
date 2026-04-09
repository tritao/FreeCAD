# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026                                                    *
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

"""Path adapters for BIM wall joint solving.

This module normalizes supported wall baselines into global straight wall paths.
The current adapter only accepts a single straight baseline and exposes the
small set of geometric helpers used by the wall-joint solver.
"""

import DraftGeomUtils
import FreeCAD
import Part


class WallPath:
    """Normalized straight wall path used by the wall-joint solver."""

    def __init__(self, edge, wall=None):
        self.edge = get_single_straight_edge(edge)
        self.wall = wall

    @property
    def start_point(self):
        return self.edge.Vertexes[0].Point

    @property
    def end_point(self):
        return self.edge.Vertexes[-1].Point

    def vector(self):
        return self.end_point.sub(self.start_point)

    def direction(self):
        return self.vector().normalize()

    def center(self):
        return (self.start_point + self.end_point) * 0.5

    def nearest_end_name(self, point):
        dist_start = point.distanceToPoint(self.start_point)
        dist_end = point.distanceToPoint(self.end_point)
        return "Start" if dist_start < dist_end else "End"

    def nearest_end_distance(self, point):
        return min(
            point.distanceToPoint(self.start_point),
            point.distanceToPoint(self.end_point),
        )

    def tangent_towards(self, point):
        direction = self.vector()
        if point.distanceToPoint(self.start_point) > point.distanceToPoint(self.end_point):
            direction.multiply(-1)
        return direction.normalize()

    def lateral_direction(self):
        return self.direction().cross(FreeCAD.Vector(0, 0, 1)).normalize()


def get_wall_path(wall):
    """Returns the supported global straight path for a wall join."""
    if not wall:
        return None

    baseline_edge = _get_supported_baseline_edge(wall)
    if not baseline_edge:
        return None

    global_edge = _get_global_path_edge(wall, baseline_edge)
    if not global_edge:
        return None

    return WallPath(global_edge, wall=wall)


def coerce_wall_path(path_or_edge, wall=None):
    """Returns a WallPath from an existing path or a single straight edge."""
    if isinstance(path_or_edge, WallPath):
        return path_or_edge

    edge = get_single_straight_edge(path_or_edge)
    if not edge:
        return None
    return WallPath(edge, wall=wall)


def find_path_intersection(path_a, path_b):
    """Returns the infinite-line intersection and nearest end names for two paths."""
    path_a = coerce_wall_path(path_a)
    path_b = coerce_wall_path(path_b)
    if not path_a or not path_b:
        return None, None, None

    intersections = DraftGeomUtils.findIntersection(
        path_a.edge, path_b.edge, infinite1=True, infinite2=True
    )
    if not intersections:
        return None, None, None

    intersection_point = intersections[0]
    return (
        intersection_point,
        path_a.nearest_end_name(intersection_point),
        path_b.nearest_end_name(intersection_point),
    )


def get_single_straight_edge(shape_or_edge):
    """Returns a single straight edge from the given shape-like object."""
    if not shape_or_edge:
        return None

    edges = getattr(shape_or_edge, "Edges", None)
    if edges is None and hasattr(shape_or_edge, "Curve") and hasattr(shape_or_edge, "Vertexes"):
        edges = [shape_or_edge]
    if not edges or len(edges) != 1:
        return None

    edge = edges[0]
    curve = getattr(edge, "Curve", None)
    if getattr(curve, "TypeId", "") != "Part::GeomLine":
        return None
    return edge


def _get_supported_baseline_edge(wall):
    base = getattr(wall, "Base", None)
    if base and hasattr(base, "Shape"):
        return get_single_straight_edge(base.Shape)
    if hasattr(wall, "Proxy") and hasattr(wall.Proxy, "calc_endpoints"):
        endpoints = wall.Proxy.calc_endpoints(wall)
        if len(endpoints) >= 2:
            return get_single_straight_edge(Part.makeLine(endpoints[0], endpoints[1]))
    return None


def _get_global_path_edge(wall, fallback_edge):
    if hasattr(wall, "Proxy") and hasattr(wall.Proxy, "calc_endpoints"):
        endpoints = wall.Proxy.calc_endpoints(wall)
        if len(endpoints) >= 2:
            return get_single_straight_edge(Part.makeLine(endpoints[0], endpoints[1]))
    return fallback_edge
