# SPDX-License-Identifier: LGPL-2.1-or-later

"""Canonical topology for joined BIM plan contours.

This module owns wall-boundary joining.  Renderers intentionally receive only
closed contours and semantic seam lines; they never repair a graph themselves.
"""

import FreeCAD

import ArchRepresentation


DEFAULT_TOLERANCE = 1.0e-7


def _point_key(point, tolerance):
    return tuple(round(float(getattr(point, axis)) / tolerance) for axis in "xyz")


def _segment_key(first, second, tolerance):
    return tuple(sorted((_point_key(first, tolerance), _point_key(second, tolerance))))


def _closed(points, tolerance):
    result = tuple(FreeCAD.Vector(point) for point in points)
    if len(result) < 3:
        return ()
    if result[0].distanceToPoint(result[-1]) > tolerance:
        result += (FreeCAD.Vector(result[0]),)
    return result if len(result) >= 4 else ()


def contours_from_representation(representation, tolerance=DEFAULT_TOLERANCE):
    """Build the canonical per-object contour value from semantic geometry."""

    outer = []
    openings = []
    seams = []
    mappings = []
    for geometry in representation.projected_geometry:
        mapping = representation.mapping_for(geometry)
        role = getattr(mapping, "role", None)
        if role not in {
            "PlanCutOuterBoundary",
            "PlanCutInnerBoundary",
            "WallJointCutLine",
        } or hasattr(geometry, "ShapeType"):
            continue
        points = tuple(FreeCAD.Vector(point) for point in geometry)
        if role == "WallJointCutLine":
            if len(points) < 2:
                continue
            target = seams
        else:
            points = _closed(points, tolerance)
            if not points:
                continue
            target = outer if role == "PlanCutOuterBoundary" else openings
        target.append(points)
        mappings.append(
            ArchRepresentation.BIMPlanContourMapping(
                points,
                role,
                getattr(mapping, "source", representation.source),
                getattr(mapping, "subelement", None),
                tuple(getattr(mapping, "related_sources", ()) or ()),
            )
        )
    return ArchRepresentation.BIMPlanContours(
        tuple(outer), tuple(openings), tuple(seams), tuple(mappings), tolerance
    )


def _component_indices(representations):
    parents = list(range(len(representations)))
    owners = {}

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first, second):
        first, second = find(first), find(second)
        if first != second:
            parents[second] = first

    for index, representation in enumerate(representations):
        contours = representation.plan_contours
        if contours is None:
            continue
        for mapping in contours.source_mappings:
            if mapping.role != "WallJointCutLine":
                continue
            for joint in mapping.related_sources:
                owner = owners.setdefault(id(joint), index)
                union(index, owner)
    groups = {}
    for index in range(len(representations)):
        groups.setdefault(find(index), []).append(index)
    return tuple(tuple(indices) for indices in groups.values())


def _cycles(outer_contours, seam_lines, tolerance):
    seam_keys = {
        _segment_key(first, second, tolerance)
        for seam in seam_lines
        for first, second in zip(seam, seam[1:])
        if _point_key(first, tolerance) != _point_key(second, tolerance)
    }
    edges = {}
    for contour in outer_contours:
        for first, second in zip(contour, contour[1:]):
            key = _segment_key(first, second, tolerance)
            if key not in seam_keys and key not in edges:
                edges[key] = (first, second)
    adjacency = {}
    edge_values = tuple(edges.values())
    for index, (first, second) in enumerate(edge_values):
        a, b = _point_key(first, tolerance), _point_key(second, tolerance)
        adjacency.setdefault(a, []).append((index, b))
        adjacency.setdefault(b, []).append((index, a))
    if not edge_values or any(len(entries) != 2 for entries in adjacency.values()):
        return ()
    visited = set()
    result = []
    for initial, edge in enumerate(edge_values):
        if initial in visited:
            continue
        start = _point_key(edge[0], tolerance)
        current = start
        points = []
        while True:
            candidates = [item for item in adjacency[current] if item[0] not in visited]
            if not candidates:
                return ()
            edge_index, next_key = candidates[0]
            visited.add(edge_index)
            first, second = edge_values[edge_index]
            points.append(first if _point_key(first, tolerance) == current else second)
            current = next_key
            if current == start:
                points.append(FreeCAD.Vector(points[0]))
                break
        if len(points) < 4:
            return ()
        result.append(tuple(points))
    return tuple(result) if len(visited) == len(edge_values) else ()


def joined_contours(representations, tolerance=DEFAULT_TOLERANCE):
    """Return one canonical contour value per disconnected wall component."""

    for representation in representations:
        if representation.plan_contours is None:
            representation.plan_contours = contours_from_representation(
                representation, tolerance
            )
    result = []
    for indices in _component_indices(representations):
        models = tuple(representations[index].plan_contours for index in indices)
        outer = tuple(item for model in models for item in model.outer_contours)
        openings = tuple(item for model in models for item in model.opening_contours)
        seams = tuple(item for model in models for item in model.seam_lines)
        mappings = tuple(item for model in models for item in model.source_mappings)
        joined = _cycles(outer, seams, tolerance) if len(indices) > 1 else outer
        result.append(
            ArchRepresentation.BIMPlanContours(
                joined or outer,
                openings,
                _deduplicate_lines(seams, tolerance),
                mappings,
                tolerance,
                bool(joined) or len(indices) == 1,
            )
        )
    return tuple(result)


def _deduplicate_lines(lines, tolerance):
    result = []
    seen = set()
    for line in lines:
        if len(line) < 2:
            continue
        key = tuple(_segment_key(a, b, tolerance) for a, b in zip(line, line[1:]))
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return tuple(result)
