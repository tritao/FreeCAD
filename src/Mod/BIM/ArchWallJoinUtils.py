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

"""Shared helpers for BIM wall joint relations."""

import DraftGeomUtils
import FreeCAD


def is_wall_joint(obj):
    """Returns True when the given object is a BIM wall joint."""
    return bool(obj and hasattr(obj, "Proxy") and getattr(obj.Proxy, "Type", None) == "WallJoint")


def iter_wall_joints(wall):
    """Yields joint relations that reference the given wall."""
    if not wall:
        return
    for obj in wall.InList:
        if is_wall_joint(obj):
            yield obj


def find_existing_joint(doc, wall_a, wall_b):
    """Finds an existing joint between two walls, regardless of link order."""
    for obj in doc.Objects:
        if not is_wall_joint(obj):
            continue
        if {obj.WallA, obj.WallB} == {wall_a, wall_b}:
            return obj
    return None


def get_join_baseline(wall):
    """Returns the supported straight baseline edge for a wall join."""
    if not (wall and hasattr(wall, "Proxy") and hasattr(wall.Proxy, "get_baseline")):
        return None

    baseline = wall.Proxy.get_baseline(wall)
    return _get_single_straight_edge(baseline)


def solve_wall_joint(joint, include_conflicts=True):
    """Solves a wall joint relation and returns derived trim data."""
    if not joint:
        return _status_result("MissingWall", "The joint object is missing.")
    if not getattr(joint, "Enabled", True):
        return _status_result(
            "Disabled", "The joint is disabled.", wall_a=joint.WallA, wall_b=joint.WallB
        )

    result = solve_wall_joint_inputs(
        joint.WallA,
        joint.WallB,
        getattr(joint, "JointType", "Miter"),
        getattr(joint, "ButtTrimmed", "Auto"),
        getattr(joint, "TeeStem", "Auto"),
        getattr(joint, "EndA", "Auto"),
        getattr(joint, "EndB", "Auto"),
    )
    if include_conflicts and result["status"] == "OK" and joint_has_conflict(joint, result):
        result["status"] = "Conflict"
        result["status_message"] = (
            "Another enabled wall joint already trims one of the same wall ends."
        )
    return result


def solve_wall_joint_inputs(
    wall_a,
    wall_b,
    joint_type,
    butt_trimmed="Auto",
    tee_stem="Auto",
    end_a="Auto",
    end_b="Auto",
):
    """Solves a wall joint configuration from wall objects and relation settings."""
    result = _status_result("SolverError", "The joint solver failed.", wall_a=wall_a, wall_b=wall_b)
    if not wall_a or not wall_b:
        return _status_result(
            "MissingWall", "The joint must reference two walls.", wall_a=wall_a, wall_b=wall_b
        )
    if wall_a == wall_b:
        return _status_result(
            "MissingWall",
            "A wall joint cannot reference the same wall twice.",
            wall_a=wall_a,
            wall_b=wall_b,
        )

    baseline_a = get_join_baseline(wall_a)
    baseline_b = get_join_baseline(wall_b)
    if not baseline_a:
        return _status_result(
            "UnsupportedBaseline",
            f"The joint only supports walls with a single straight baseline: {wall_a.Label}",
            wall_a=wall_a,
            wall_b=wall_b,
        )
    if not baseline_b:
        return _status_result(
            "UnsupportedBaseline",
            f"The joint only supports walls with a single straight baseline: {wall_b.Label}",
            wall_a=wall_a,
            wall_b=wall_b,
        )

    intersection, auto_end_a, auto_end_b = find_best_intersection(baseline_a, baseline_b)
    if not intersection:
        return _status_result(
            "NoIntersection",
            "The baselines of the selected walls do not intersect.",
            wall_a=wall_a,
            wall_b=wall_b,
        )

    result.update(
        {
            "status": "OK",
            "status_message": "",
            "intersection": intersection,
            "wall_a": wall_a,
            "wall_b": wall_b,
        }
    )

    joint_type = _normalize_enum(joint_type, ("Miter", "Butt", "Tee"), "Miter")
    if joint_type == "Miter":
        plane_a, plane_b = calculate_miter_cutting_planes(
            baseline_a, baseline_b, intersection, wall_a.Width.Value, wall_b.Width.Value
        )
        resolved_end_a = _resolve_end(auto_end_a, end_a)
        resolved_end_b = _resolve_end(auto_end_b, end_b)
        result.update(
            {
                "resolved_end_a": resolved_end_a,
                "resolved_end_b": resolved_end_b,
                "plane_a": plane_a if resolved_end_a else None,
                "plane_b": plane_b if resolved_end_b else None,
            }
        )
        return result

    if joint_type == "Butt":
        butt_trimmed = _normalize_enum(butt_trimmed, ("Auto", "WallA", "WallB"), "Auto")
        if butt_trimmed in ("Auto", "WallB"):
            plane_a, plane_b = calculate_butt_cutting_planes(
                baseline_a, baseline_b, intersection, wall_a.Width.Value, wall_b.Width.Value
            )
        else:
            plane_b, plane_a = calculate_butt_cutting_planes(
                baseline_b, baseline_a, intersection, wall_b.Width.Value, wall_a.Width.Value
            )
        resolved_end_a = _resolve_end(auto_end_a, end_a)
        resolved_end_b = _resolve_end(auto_end_b, end_b)
        result.update(
            {
                "resolved_end_a": resolved_end_a,
                "resolved_end_b": resolved_end_b,
                "plane_a": plane_a if resolved_end_a else None,
                "plane_b": plane_b if resolved_end_b else None,
            }
        )
        return result

    tee_stem = _normalize_enum(tee_stem, ("Auto", "WallA", "WallB"), "Auto")
    auto_stem = get_auto_tee_stem_role(baseline_a, baseline_b, intersection)
    if tee_stem == "Auto":
        tee_stem = auto_stem

    if tee_stem == "WallA":
        resolved_end_a = _resolve_end(auto_end_a, end_a)
        result.update(
            {
                "resolved_end_a": resolved_end_a,
                "resolved_end_b": None,
                "plane_a": (
                    calculate_tee_cutting_plane(
                        wall_a, wall_b, baseline_a, baseline_b, intersection
                    )
                    if resolved_end_a
                    else None
                ),
                "plane_b": None,
            }
        )
        return result

    resolved_end_b = _resolve_end(auto_end_b, end_b)
    result.update(
        {
            "resolved_end_a": None,
            "resolved_end_b": resolved_end_b,
            "plane_a": None,
            "plane_b": (
                calculate_tee_cutting_plane(wall_b, wall_a, baseline_b, baseline_a, intersection)
                if resolved_end_b
                else None
            ),
        }
    )
    return result


def joint_has_conflict(joint, solution=None):
    """Returns True when another enabled joint trims one of the same wall ends."""
    if not joint:
        return False
    if solution is None:
        solution = solve_wall_joint(joint, include_conflicts=False)
    if solution["status"] != "OK":
        return False

    for wall, end_name in (
        (solution["wall_a"], solution["resolved_end_a"]),
        (solution["wall_b"], solution["resolved_end_b"]),
    ):
        if not wall or not end_name:
            continue
        for other in iter_wall_joints(wall):
            if other == joint or not getattr(other, "Enabled", True):
                continue
            other_solution = solve_wall_joint(other, include_conflicts=False)
            if other_solution["status"] != "OK":
                continue
            other_end_name, _other_plane = get_trim_for_wall(other_solution, wall)
            if other_end_name == end_name:
                return True
    return False


def collect_wall_joint_endings(wall):
    """Collects the unique joint-derived trim planes for the given wall."""
    claims = {"Start": [], "End": []}
    for joint in iter_wall_joints(wall):
        if not getattr(joint, "Enabled", True):
            continue
        solution = solve_wall_joint(joint, include_conflicts=False)
        if solution["status"] != "OK":
            continue
        end_name, plane = get_trim_for_wall(solution, wall)
        if end_name and plane:
            claims[end_name].append((joint, plane))

    result = {"Start": None, "End": None, "Conflicts": set()}
    for end_name, entries in claims.items():
        if len(entries) == 1:
            result[end_name] = entries[0][1]
        elif len(entries) > 1:
            result["Conflicts"].add(end_name)
    return result


def get_trim_for_wall(solution, wall):
    """Returns the resolved end and plane for the requested wall."""
    if not solution or solution["status"] != "OK":
        return None, None
    if wall == solution["wall_a"]:
        return solution["resolved_end_a"], solution["plane_a"]
    if wall == solution["wall_b"]:
        return solution["resolved_end_b"], solution["plane_b"]
    return None, None


def find_best_intersection(line1, line2):
    """Finds the intersection point of two baselines and the closest end on each line."""
    edge1 = _get_single_straight_edge(line1)
    edge2 = _get_single_straight_edge(line2)
    if not edge1 or not edge2:
        return None, None, None

    intersections = DraftGeomUtils.findIntersection(edge1, edge2, infinite1=True, infinite2=True)
    if not intersections:
        return None, None, None

    intersection_point = intersections[0]
    dist_start1 = intersection_point.distanceToPoint(edge1.Vertexes[0].Point)
    dist_end1 = intersection_point.distanceToPoint(edge1.Vertexes[-1].Point)
    end_name1 = "Start" if dist_start1 < dist_end1 else "End"

    dist_start2 = intersection_point.distanceToPoint(edge2.Vertexes[0].Point)
    dist_end2 = intersection_point.distanceToPoint(edge2.Vertexes[-1].Point)
    end_name2 = "Start" if dist_start2 < dist_end2 else "End"

    return intersection_point, end_name1, end_name2


def calculate_miter_cutting_planes(baseline1, baseline2, intersection, _width1, _width2):
    """Calculates the cutting planes for a miter wall joint."""
    dir1 = baseline1.Vertexes[-1].Point.sub(baseline1.Vertexes[0].Point)
    if intersection.distanceToPoint(baseline1.Vertexes[0].Point) > intersection.distanceToPoint(
        baseline1.Vertexes[-1].Point
    ):
        dir1.multiply(-1)

    dir2 = baseline2.Vertexes[-1].Point.sub(baseline2.Vertexes[0].Point)
    if intersection.distanceToPoint(baseline2.Vertexes[0].Point) > intersection.distanceToPoint(
        baseline2.Vertexes[-1].Point
    ):
        dir2.multiply(-1)

    bisector_normal = (dir1.normalize() + dir2.normalize()).normalize()
    axis_x = dir1.normalize()
    axis_y = FreeCAD.Vector(0, 0, 1)
    axis_z = bisector_normal.cross(axis_y).normalize()
    rotation = FreeCAD.Rotation(axis_x, axis_y, axis_z, "ZXY")
    plane1 = FreeCAD.Placement(intersection, rotation)
    plane2 = plane1.copy()
    plane2.rotate(intersection, FreeCAD.Vector(0, 0, 1), 180)
    return plane1, plane2


def calculate_butt_cutting_planes(baseline1, baseline2, intersection, width1, width2):
    """Calculates the cutting planes for a butt wall joint."""
    axis_x_2 = DraftGeomUtils.vec(baseline1)
    axis_y_2 = FreeCAD.Vector(0, 0, 1)
    axis_z_2 = axis_x_2.cross(axis_y_2).normalize()
    rotation_2 = FreeCAD.Rotation(axis_x_2, axis_y_2, axis_z_2, "ZXY")
    plane2 = FreeCAD.Placement(intersection, rotation_2)

    dir1 = DraftGeomUtils.vec(baseline1).normalize()
    dir2 = DraftGeomUtils.vec(baseline2).normalize()
    offset_dir = dir1.cross(FreeCAD.Vector(0, 0, 1))
    if offset_dir.dot(dir2) < 0:
        offset_dir.multiply(-1)

    offset_intersection = intersection.add(offset_dir * (width2 / 2.0))
    axis_x_1 = dir2
    axis_y_1 = FreeCAD.Vector(0, 0, 1)
    axis_z_1 = axis_x_1.cross(axis_y_1).normalize()
    rotation_1 = FreeCAD.Rotation(axis_x_1, axis_y_1, axis_z_1, "ZXY")
    plane1 = FreeCAD.Placement(offset_intersection, rotation_1)
    return plane1, plane2


def calculate_tee_cutting_plane(stem_wall, top_wall, stem_line, top_line, intersection):
    """Calculates the cutting plane for the stem wall in a tee joint."""
    plane_normal = DraftGeomUtils.vec(stem_line).normalize()
    rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), plane_normal)

    top_dir = DraftGeomUtils.vec(top_line).normalize()
    offset_dir = top_dir.cross(FreeCAD.Vector(0, 0, 1))

    center_stem = (stem_line.Vertexes[0].Point + stem_line.Vertexes[-1].Point) / 2
    vec_to_stem = center_stem - intersection

    if offset_dir.dot(vec_to_stem) < 0:
        offset_dir.multiply(-1)

    plane_position = intersection.add(offset_dir * (top_wall.Width.Value / 2.0))
    plane_position = plane_position.add(vec_to_stem.normalize() * 1e-6)
    return FreeCAD.Placement(plane_position, rotation)


def get_auto_tee_stem_role(baseline_a, baseline_b, intersection):
    dist_to_end_a = min(
        intersection.distanceToPoint(baseline_a.Vertexes[0].Point),
        intersection.distanceToPoint(baseline_a.Vertexes[-1].Point),
    )
    dist_to_end_b = min(
        intersection.distanceToPoint(baseline_b.Vertexes[0].Point),
        intersection.distanceToPoint(baseline_b.Vertexes[-1].Point),
    )
    return "WallA" if dist_to_end_a < dist_to_end_b else "WallB"


def _get_single_straight_edge(shape_or_edge):
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


def _normalize_enum(value, allowed, default):
    return value if value in allowed else default


def _resolve_end(auto_end, override):
    override = _normalize_enum(override, ("Auto", "Start", "End", "None"), "Auto")
    if override == "Auto":
        return auto_end
    if override == "None":
        return None
    return override


def _status_result(status, message, wall_a=None, wall_b=None):
    return {
        "status": status,
        "status_message": message,
        "intersection": FreeCAD.Vector(),
        "resolved_end_a": None,
        "resolved_end_b": None,
        "plane_a": None,
        "plane_b": None,
        "wall_a": wall_a,
        "wall_b": wall_b,
    }
