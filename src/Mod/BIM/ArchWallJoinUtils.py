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

"""Solver and utility helpers for BIM wall joints.

This module validates supported wall baselines, resolves joint roles and wall
ends, computes the global cutting planes for each wall, and reports conflicts
when multiple enabled joints claim the same wall end.
"""

from dataclasses import dataclass, field

import ArchWallPath
import ArchWallSection
import FreeCAD


@dataclass
class WallJointConflict:
    """Structured description of a joint-end conflict."""

    wall_key: str
    wall_object: object
    wall_end: str
    other_joint: object
    other_joint_type: str
    other_joint_label: str
    message: str

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


@dataclass
class WallJointSolution:
    """Typed solver output for a wall-joint relation."""

    status: str
    status_message: str
    intersection: FreeCAD.Vector = field(default_factory=FreeCAD.Vector)
    resolved_end_a: str = None
    resolved_end_b: str = None
    plane_a: FreeCAD.Placement = None
    plane_b: FreeCAD.Placement = None
    wall_a: object = None
    wall_b: object = None
    conflicts: list = field(default_factory=list)
    conflict_joint_a: object = None
    conflict_joint_b: object = None
    conflict_joint_label_a: str = ""
    conflict_joint_label_b: str = ""
    conflict_message_a: str = ""
    conflict_message_b: str = ""

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def update(self, values):
        for key, value in values.items():
            setattr(self, key, value)
        return self

    def is_ok(self):
        return self.status == "OK"

    def trim_for_wall(self, wall):
        if not self.is_ok():
            return None, None
        if wall == self.wall_a:
            return self.resolved_end_a, self.plane_a
        if wall == self.wall_b:
            return self.resolved_end_b, self.plane_b
        return None, None


def is_wall_joint(obj):
    """Returns True when the given object is a BIM wall joint."""
    return bool(obj and hasattr(obj, "Proxy") and getattr(obj.Proxy, "Type", None) == "WallJoint")


def is_wall_junction(obj):
    """Returns True when the given object is a BIM wall junction."""
    return bool(
        obj and hasattr(obj, "Proxy") and getattr(obj.Proxy, "Type", None) == "WallJunction"
    )


def iter_wall_relations(wall):
    """Yields wall relations that reference the given wall."""
    if not wall:
        return
    for obj in wall.InList:
        if is_wall_joint(obj) or is_wall_junction(obj):
            yield obj


def get_relation_walls(relation):
    """Returns the walls referenced by a wall relation object."""
    if is_wall_joint(relation):
        return [getattr(relation, "WallA", None), getattr(relation, "WallB", None)]
    if is_wall_junction(relation):
        return list(getattr(relation, "Walls", []))
    return []


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
    path = get_join_path(wall)
    return path.edge if path else None


def get_join_path(wall):
    """Returns the normalized supported path used by the wall-joint solver."""
    return ArchWallPath.get_wall_path(wall)


def get_join_section(wall):
    """Returns the normalized supported wall section used by the wall-joint solver."""
    return ArchWallSection.get_wall_section(wall)


def solve_wall_joint(joint, include_conflicts=True):
    """Solves a wall joint relation and returns derived trim data."""
    if not joint:
        return _status_result("MissingWall", "The joint object is missing.")
    if not getattr(joint, "Enabled", True):
        return _status_result(
            "Disabled", "The joint is disabled.", wall_a=joint.WallA, wall_b=joint.WallB
        )

    return solve_wall_joint_settings(
        joint,
        getattr(joint, "JointType", "Miter"),
        getattr(joint, "ButtTrimmed", "Auto"),
        getattr(joint, "TeeStem", "Auto"),
        getattr(joint, "EndA", "Auto"),
        getattr(joint, "EndB", "Auto"),
        include_conflicts=include_conflicts,
    )


def solve_wall_relation(relation, include_conflicts=True):
    """Solves a wall relation object and returns its trim solution."""
    if is_wall_joint(relation):
        return solve_wall_joint(relation, include_conflicts=include_conflicts)
    if is_wall_junction(relation):
        import ArchWallJunctionUtils

        return ArchWallJunctionUtils.solve_wall_junction(relation)
    return _status_result("SolverError", "Unsupported wall relation object.")


def solve_wall_joint_settings(
    joint,
    joint_type,
    butt_trimmed="Auto",
    tee_stem="Auto",
    end_a="Auto",
    end_b="Auto",
    include_conflicts=True,
):
    """Solves a wall joint from explicit settings, optionally including conflict checks."""
    if not joint:
        return _status_result("MissingWall", "The joint object is missing.")

    result = solve_wall_joint_inputs(
        joint.WallA,
        joint.WallB,
        joint_type,
        butt_trimmed,
        tee_stem,
        end_a,
        end_b,
    )
    if include_conflicts and result.is_ok():
        conflicts = get_joint_conflicts(joint, result)
        if conflicts:
            _apply_conflicts(result, conflicts)
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

    path_a = get_join_path(wall_a)
    path_b = get_join_path(wall_b)
    section_a = get_join_section(wall_a)
    section_b = get_join_section(wall_b)
    if not path_a:
        return _status_result(
            "UnsupportedBaseline",
            f"The joint only supports walls with a single straight baseline: {wall_a.Label}",
            wall_a=wall_a,
            wall_b=wall_b,
        )
    if not path_b:
        return _status_result(
            "UnsupportedBaseline",
            f"The joint only supports walls with a single straight baseline: {wall_b.Label}",
            wall_a=wall_a,
            wall_b=wall_b,
        )
    if not section_a:
        return _status_result(
            "SolverError",
            f"The joint could not determine the wall section: {wall_a.Label}",
            wall_a=wall_a,
            wall_b=wall_b,
        )
    if not section_b:
        return _status_result(
            "SolverError",
            f"The joint could not determine the wall section: {wall_b.Label}",
            wall_a=wall_a,
            wall_b=wall_b,
        )

    intersection, auto_end_a, auto_end_b = find_best_intersection(path_a, path_b)
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
            path_a, path_b, intersection, section_a, section_b
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
                path_a, path_b, intersection, section_a, section_b
            )
        else:
            plane_b, plane_a = calculate_butt_cutting_planes(
                path_b, path_a, intersection, section_b, section_a
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
    auto_stem = get_auto_tee_stem_role(path_a, path_b, intersection)
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
                        wall_a, wall_b, path_a, path_b, intersection, top_section=section_b
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
                calculate_tee_cutting_plane(
                    wall_b, wall_a, path_b, path_a, intersection, top_section=section_a
                )
                if resolved_end_b
                else None
            ),
        }
    )
    return result


def get_joint_conflicts(joint, solution=None):
    """Returns structured conflict entries for wall ends already trimmed by another joint."""
    if not joint:
        return []
    if solution is None:
        solution = solve_wall_joint(joint, include_conflicts=False)
    if not solution.is_ok():
        return []

    conflicts = []
    for wall_key, wall_obj, end_name in (
        ("A", solution.wall_a, solution.resolved_end_a),
        ("B", solution.wall_b, solution.resolved_end_b),
    ):
        if not wall_obj or not end_name:
            continue
        for other in iter_wall_joints(wall_obj):
            if other == joint or not getattr(other, "Enabled", True):
                continue
            other_solution = solve_wall_joint(other, include_conflicts=False)
            if not other_solution.is_ok():
                continue
            other_end_name, _other_plane = get_trim_for_wall(other_solution, wall_obj)
            if other_end_name == end_name:
                conflicts.append(
                    WallJointConflict(
                        wall_key=wall_key,
                        wall_object=wall_obj,
                        wall_end=end_name,
                        other_joint=other,
                        other_joint_type=getattr(other, "JointType", "WallJoint"),
                        other_joint_label=getattr(other, "Label", getattr(other, "Name", "")),
                        message=(
                            f"{wall_obj.Label} {end_name} is already trimmed by joint {other.Label}."
                        ),
                    )
                )
    return conflicts


def joint_has_conflict(joint, solution=None):
    """Returns True when another enabled joint trims one of the same wall ends."""
    return bool(get_joint_conflicts(joint, solution))


def collect_wall_relation_endings(wall):
    """Collects the unique relation-derived trim planes for the given wall."""
    claims = {"Start": [], "End": []}
    for relation in iter_wall_relations(wall):
        if not getattr(relation, "Enabled", True):
            continue
        solution = solve_wall_relation(relation, include_conflicts=False)
        if not solution.is_ok():
            continue
        end_name, plane = get_trim_for_wall(solution, wall)
        if end_name and plane:
            claims[end_name].append((relation, plane))

    result = {"Start": None, "End": None, "Conflicts": set()}
    for end_name, entries in claims.items():
        if len(entries) == 1:
            result[end_name] = entries[0][1]
        elif len(entries) > 1:
            result["Conflicts"].add(end_name)
    return result


def collect_wall_joint_endings(wall):
    """Alias for relation-derived trim collection."""
    return collect_wall_relation_endings(wall)


def get_trim_for_wall(solution, wall):
    """Returns the resolved end and plane for the requested wall."""
    if not solution:
        return None, None
    return solution.trim_for_wall(wall)


def find_best_intersection(line1, line2):
    """Finds the intersection point of two baselines and the closest end on each line."""
    return ArchWallPath.find_path_intersection(line1, line2)


def calculate_miter_cutting_planes(baseline1, baseline2, intersection, _section1, _section2):
    """Calculates the cutting planes for a miter wall joint."""
    path1 = ArchWallPath.coerce_wall_path(baseline1)
    path2 = ArchWallPath.coerce_wall_path(baseline2)
    if not path1 or not path2:
        return None, None

    dir1 = path1.tangent_towards(intersection)
    dir2 = path2.tangent_towards(intersection)
    bisector_normal = (dir1 + dir2).normalize()
    axis_x = dir1
    axis_y = FreeCAD.Vector(0, 0, 1)
    axis_z = bisector_normal.cross(axis_y).normalize()
    rotation = FreeCAD.Rotation(axis_x, axis_y, axis_z, "ZXY")
    plane1 = FreeCAD.Placement(intersection, rotation)
    plane2 = plane1.copy()
    plane2.rotate(intersection, FreeCAD.Vector(0, 0, 1), 180)
    return plane1, plane2


def calculate_butt_cutting_planes(baseline1, baseline2, intersection, section1, section2):
    """Calculates the cutting planes for a butt wall joint."""
    path1 = ArchWallPath.coerce_wall_path(baseline1)
    path2 = ArchWallPath.coerce_wall_path(baseline2)
    if not path1 or not path2:
        return None, None
    offset_1 = _get_section_face_offset_vector(path2, section2, path1.center() - intersection)
    offset_2 = _get_section_face_offset_vector(path1, section1, path2.center() - intersection)
    if offset_1 is None or offset_2 is None:
        return None, None

    axis_x_2 = path1.direction()
    axis_y_2 = FreeCAD.Vector(0, 0, 1)
    axis_z_2 = axis_x_2.cross(axis_y_2).normalize()
    rotation_2 = FreeCAD.Rotation(axis_x_2, axis_y_2, axis_z_2, "ZXY")
    plane2 = FreeCAD.Placement(intersection.add(offset_2), rotation_2)

    dir2 = path2.direction()
    axis_x_1 = dir2
    axis_y_1 = FreeCAD.Vector(0, 0, 1)
    axis_z_1 = axis_x_1.cross(axis_y_1).normalize()
    rotation_1 = FreeCAD.Rotation(axis_x_1, axis_y_1, axis_z_1, "ZXY")
    plane1 = FreeCAD.Placement(intersection.add(offset_1), rotation_1)
    return plane1, plane2


def calculate_tee_cutting_plane(
    stem_wall, top_wall, stem_line, top_line, intersection, top_section=None
):
    """Calculates the cutting plane for the stem wall in a tee joint."""
    stem_path = ArchWallPath.coerce_wall_path(stem_line, wall=stem_wall)
    top_path = ArchWallPath.coerce_wall_path(top_line, wall=top_wall)
    if not stem_path or not top_path:
        return None
    top_section = top_section if top_section else top_wall
    offset = _get_section_face_offset_vector(
        top_path,
        top_section,
        stem_path.center() - intersection,
    )
    if offset is None:
        return None

    plane_normal = stem_path.direction()
    rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), plane_normal)

    vec_to_stem = stem_path.center() - intersection
    plane_position = intersection.add(offset)
    if vec_to_stem.Length > 1e-9:
        plane_position = plane_position.add(vec_to_stem.normalize() * 1e-6)
    return FreeCAD.Placement(plane_position, rotation)


def get_auto_tee_stem_role(baseline_a, baseline_b, intersection):
    path_a = ArchWallPath.coerce_wall_path(baseline_a)
    path_b = ArchWallPath.coerce_wall_path(baseline_b)
    if not path_a or not path_b:
        return "WallB"

    dist_to_end_a = path_a.nearest_end_distance(intersection)
    dist_to_end_b = path_b.nearest_end_distance(intersection)
    return "WallA" if dist_to_end_a < dist_to_end_b else "WallB"


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
    return WallJointSolution(status=status, status_message=message, wall_a=wall_a, wall_b=wall_b)


def _apply_conflicts(result, conflicts):
    result.status = "Conflict"
    result.conflicts = conflicts
    unique_messages = []
    for conflict in conflicts:
        wall_key = conflict.wall_key
        if wall_key == "A" and result.conflict_joint_a is None:
            result.conflict_joint_a = conflict.other_joint
            result.conflict_joint_label_a = conflict.other_joint_label
            result.conflict_message_a = conflict.message
        elif wall_key == "B" and result.conflict_joint_b is None:
            result.conflict_joint_b = conflict.other_joint
            result.conflict_joint_label_b = conflict.other_joint_label
            result.conflict_message_b = conflict.message
        if conflict.message not in unique_messages:
            unique_messages.append(conflict.message)
    result.status_message = "Conflict: " + "; ".join(unique_messages)


def _get_section_face_offset_vector(path, section, towards_vector):
    """Returns a signed lateral offset from a wall centerline to the requested section face."""
    if not path:
        return None
    lateral = path.lateral_direction()
    extent = ArchWallSection.get_section_extent_towards(section, lateral, towards_vector)
    if extent is None:
        return None
    if lateral.dot(towards_vector) < 0:
        lateral = lateral * -1
    return lateral * extent
