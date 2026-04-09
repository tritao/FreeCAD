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

"""Solver helpers for BIM wall junction relations.

The current wall-junction model groups 3+ walls around one carrier wall and
derives tee joints for the branch walls that terminate at the common
intersection point. This is the first junction-level relation layer above the
pairwise WallJoint model.
"""

from dataclasses import dataclass, field

import FreeCAD

import ArchWallJoinUtils

END_TOLERANCE = 1e-4
INTERSECTION_TOLERANCE = 1e-4


@dataclass
class WallJunctionSolution:
    """Typed solver output for a wall-junction relation."""

    status: str
    status_message: str
    intersection: FreeCAD.Vector = field(default_factory=FreeCAD.Vector)
    carrier_wall: object = None
    branch_walls: list = field(default_factory=list)
    walls: list = field(default_factory=list)

    def is_ok(self):
        return self.status == "OK"


def solve_wall_junction(junction):
    """Solves a wall junction relation and returns derived carrier/branch data."""
    if not junction:
        return WallJunctionSolution("MissingWall", "The wall junction object is missing.")
    if not getattr(junction, "Enabled", True):
        return WallJunctionSolution("Disabled", "The wall junction is disabled.")
    return solve_wall_junction_inputs(
        getattr(junction, "Walls", []),
        getattr(junction, "CarrierMode", "Auto"),
        getattr(junction, "CarrierWall", None),
    )


def solve_wall_junction_inputs(walls, carrier_mode="Auto", carrier_wall=None):
    """Solves a wall-junction configuration from the given walls and carrier settings."""
    walls = _unique_walls(walls)
    if len(walls) < 3:
        return WallJunctionSolution(
            "MissingWall",
            "A wall junction needs at least 3 unique walls.",
            walls=walls,
        )

    paths = {}
    for wall in walls:
        path = ArchWallJoinUtils.get_join_path(wall)
        if not path:
            return WallJunctionSolution(
                "UnsupportedBaseline",
                f"The wall junction only supports walls with a single straight baseline: {wall.Label}",
                walls=walls,
            )
        paths[wall] = path

    carrier_mode = carrier_mode if carrier_mode in ("Auto", "Explicit") else "Auto"
    if carrier_mode == "Explicit":
        if carrier_wall not in walls:
            return WallJunctionSolution(
                "MissingWall",
                "The explicit carrier wall must be part of the wall junction.",
                walls=walls,
            )
        return _solve_carrier_candidate(walls, paths, carrier_wall)

    best = None
    best_score = None
    saw_no_intersection = False
    saw_unsupported_topology = False
    for candidate in walls:
        solution = _solve_carrier_candidate(walls, paths, candidate)
        if solution.is_ok():
            score = ArchWallJoinUtils.get_join_path(candidate).nearest_end_distance(
                solution.intersection
            )
            if (best is None) or (score > best_score):
                best = solution
                best_score = score
        elif solution.status == "NoIntersection":
            saw_no_intersection = True
        elif solution.status == "UnsupportedTopology":
            saw_unsupported_topology = True

    if best:
        return best
    if saw_unsupported_topology:
        return WallJunctionSolution(
            "UnsupportedTopology",
            "The walls do not form a supported carrier-and-branches junction.",
            walls=walls,
        )
    if saw_no_intersection:
        return WallJunctionSolution(
            "NoIntersection",
            "The walls do not meet at a common junction point.",
            walls=walls,
        )
    return WallJunctionSolution("SolverError", "The wall junction solver failed.", walls=walls)


def _solve_carrier_candidate(walls, paths, carrier_wall):
    intersections = []
    for wall in walls:
        if wall == carrier_wall:
            continue
        intersection, _end_a, _end_b = ArchWallJoinUtils.find_best_intersection(
            paths[carrier_wall], paths[wall]
        )
        if not intersection:
            return WallJunctionSolution(
                "NoIntersection",
                f"{carrier_wall.Label} does not intersect {wall.Label}.",
                walls=walls,
            )
        intersections.append(intersection)

    common_point = intersections[0]
    for point in intersections[1:]:
        if point.distanceToPoint(common_point) > INTERSECTION_TOLERANCE:
            return WallJunctionSolution(
                "UnsupportedTopology",
                "The walls do not share one common junction point.",
                walls=walls,
            )

    carrier_distance = paths[carrier_wall].nearest_end_distance(common_point)
    if carrier_distance <= END_TOLERANCE:
        return WallJunctionSolution(
            "UnsupportedTopology",
            f"The carrier wall must pass through the junction point: {carrier_wall.Label}",
            walls=walls,
        )

    branch_walls = []
    for wall in walls:
        if wall == carrier_wall:
            continue
        branch_distance = paths[wall].nearest_end_distance(common_point)
        if branch_distance > END_TOLERANCE:
            return WallJunctionSolution(
                "UnsupportedTopology",
                f"Only branch walls ending at the junction point are supported: {wall.Label}",
                walls=walls,
            )
        branch_walls.append(wall)

    return WallJunctionSolution(
        "OK",
        "",
        intersection=common_point,
        carrier_wall=carrier_wall,
        branch_walls=branch_walls,
        walls=walls,
    )


def _unique_walls(walls):
    unique = []
    seen = set()
    for wall in walls or []:
        if not wall or wall.Name in seen:
            continue
        seen.add(wall.Name)
        unique.append(wall)
    return unique
