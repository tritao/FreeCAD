# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD Project Association
# SPDX-FileNotice: Part of the FreeCAD project.
################################################################################
#                                                                              #
#   FreeCAD is free software: you can redistribute it and/or modify            #
#   it under the terms of the GNU Lesser General Public                       #
#   License as published by the Free Software Foundation, either version 2    #
#   of the License, or (at your option) any later version.                     #
#                                                                              #
#   FreeCAD is distributed in the hope that it will be useful,                 #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of              #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the             #
#   GNU Lesser General Public License for more details.                        #
#                                                                              #
#   You should have received a copy of the GNU Lesser General Public           #
#   License along with FreeCAD. If not, see https://www.gnu.org/licenses       #
#                                                                              #
################################################################################

"""Pure value objects and operations for resolved wall geometry.

``WallBaseline`` and ``WallPath`` are deliberately independent of wall
proxies and FreeCAD wall properties.  Callers provide global straight
geometry; this module validates it and exposes path-to-path operations.

``WallSection`` and ``WallSectionLayer`` represent an already-resolved wall
profile.  They expose geometric queries only and never resolve FreeCAD
properties or wall proxies.
"""

from dataclasses import dataclass

import DraftGeomUtils
import FreeCAD
import Part


@dataclass(frozen=True)
class WallBaseline:
    """An oriented, resolved wall baseline in global coordinates.

    ``start_point`` and ``end_point`` are semantic wall endpoints.  They are
    stored explicitly so callers never need to infer Start/End from the
    topological ordering of a rebuilt shape.
    """

    edge: Part.Edge
    normal: FreeCAD.Vector
    start_point: FreeCAD.Vector
    end_point: FreeCAD.Vector

    def __post_init__(self):
        normal = FreeCAD.Vector(self.normal)
        normal.normalize()
        object.__setattr__(self, "normal", normal)
        object.__setattr__(self, "start_point", FreeCAD.Vector(self.start_point))
        object.__setattr__(self, "end_point", FreeCAD.Vector(self.end_point))


class WallPath:
    """A strict finite straight baseline in global coordinates.

    The edge's vertex order defines Start and End.  The supplied section
    normal is copied and normalized, so relation code can use the value object
    without reinterpreting placements or mutating caller-owned vectors.
    """

    def __init__(self, edge, normal):
        """Validate and store one global baseline and section normal.

        ``edge`` must be a non-degenerate straight ``Part.Edge`` with exactly
        two vertices.  ``normal`` must be non-zero and non-parallel to the
        baseline.  Wall proxies are intentionally not accepted or inspected.
        """
        if not isinstance(edge, Part.Edge):
            raise TypeError("WallPath requires a Part.Edge")
        if edge.Curve.TypeId != "Part::GeomLine":
            raise ValueError("WallPath requires a straight edge")
        if len(edge.Vertexes) != 2:
            raise ValueError("WallPath requires an edge with two vertices")
        if edge.Length <= 1e-9:
            raise ValueError("WallPath requires a non-degenerate edge")
        if normal is None or normal.Length <= 1e-9:
            raise ValueError("WallPath requires a non-zero section normal")
        normal = FreeCAD.Vector(normal)
        normal.normalize()
        direction = edge.Vertexes[-1].Point.sub(edge.Vertexes[0].Point)
        if direction.cross(normal).Length <= 1e-9:
            raise ValueError("WallPath baseline cannot be parallel to its section normal")
        self.edge = edge
        self.normal = normal

    @classmethod
    def from_baseline(cls, baseline):
        """Create a strict path from a resolved :class:`WallBaseline`."""
        if not isinstance(baseline, WallBaseline):
            raise TypeError("WallPath.from_baseline requires a WallBaseline")
        return cls(baseline.edge, baseline.normal)

    @property
    def start_point(self):
        """Return the first ordered endpoint of the global baseline."""
        return self.edge.Vertexes[0].Point

    @property
    def end_point(self):
        """Return the second ordered endpoint of the global baseline."""
        return self.edge.Vertexes[-1].Point

    def vector(self):
        """Return the oriented vector from Start to End."""
        return self.end_point.sub(self.start_point)

    def direction(self):
        """Return the normalized direction from Start to End."""
        return self.vector().normalize()

    def center(self):
        """Return the midpoint of the finite baseline."""
        return (self.start_point + self.end_point) * 0.5

    def nearest_end_name(self, point):
        """Return the nearest endpoint name, using End to break ties."""
        start_distance = point.distanceToPoint(self.start_point)
        end_distance = point.distanceToPoint(self.end_point)
        return "Start" if start_distance < end_distance else "End"

    def nearest_end_distance(self, point):
        """Return the distance from a point to the nearer endpoint."""
        return min(
            point.distanceToPoint(self.start_point),
            point.distanceToPoint(self.end_point),
        )

    def contains_point(self, point, tolerance=1e-4):
        """Return whether a point lies on this finite segment.

        The tolerance applies both to the segment bounds and to the distance
        from the point to its orthogonal projection on the baseline.
        """
        segment = self.vector()
        length = segment.Length
        if length <= 1e-9:
            return False
        parameter = point.sub(self.start_point).dot(segment) / (length * length)
        if parameter < -tolerance / length or parameter > 1.0 + tolerance / length:
            return False
        projected = self.start_point + segment * parameter
        return projected.distanceToPoint(point) <= tolerance

    def direction_away_from(self, point):
        """Return the unit direction away from the nearer endpoint to point."""
        direction = self.vector()
        if point.distanceToPoint(self.start_point) > point.distanceToPoint(self.end_point):
            direction.multiply(-1)
        return direction.normalize()

    def lateral_direction(self):
        """Return the unit lateral direction implied by baseline and normal."""
        lateral = self.direction().cross(self.normal)
        if lateral.Length <= 1e-9:
            raise ValueError("WallPath has no lateral direction")
        return lateral.normalize()


def find_path_intersection(path_a, path_b):
    """Intersect two paths' infinite baseline lines.

    Return ``(point, end_a, end_b)`` where the endpoint names classify the
    intersection relative to each finite path.  The intersection itself may
    lie outside either finite segment because relation resolution considers
    the supporting lines.  Parallel or otherwise non-intersecting paths
    return ``(None, None, None)``.
    """
    if not isinstance(path_a, WallPath) or not isinstance(path_b, WallPath):
        raise TypeError("find_path_intersection requires WallPath values")
    intersections = DraftGeomUtils.findIntersection(
        path_a.edge, path_b.edge, infinite1=True, infinite2=True
    )
    if not intersections:
        return None, None, None
    point = intersections[0]
    return point, path_a.nearest_end_name(point), path_b.nearest_end_name(point)


@dataclass(frozen=True)
class WallSectionLayer:
    """One resolved material layer in local lateral coordinates.

    ``raw_thickness`` retains the source sign.  Positive layers are visible;
    negative layers are construction-only cursor steps.  ``y_min`` and
    ``y_max`` describe the layer's resolved lateral interval.
    """

    raw_thickness: float
    y_min: float
    y_max: float

    @property
    def visible(self):
        return self.raw_thickness > 0


@dataclass(frozen=True)
class WallSection:
    """Immutable resolved wall section consumed by relation geometry.

    The layer tuple is already ordered and positioned by ``ArchWall``.  This
    value object exposes only geometric queries and never resolves FreeCAD
    properties or wall proxies.
    """

    layers: tuple

    @property
    def visible_layers(self):
        return tuple(layer for layer in self.layers if layer.visible)

    @property
    def y_min(self):
        return min((layer.y_min for layer in self.visible_layers), default=0.0)

    @property
    def y_max(self):
        return max((layer.y_max for layer in self.visible_layers), default=0.0)

    def offset_towards(self, lateral_direction, world_direction):
        """Return the signed lateral offset to the requested visible face.

        A zero world direction has no preferred face, so it selects the
        ``y_min`` face deterministically.  Callers that require a directional
        result should resolve or reject that ambiguity before calling here.
        """
        if lateral_direction is None or world_direction is None:
            return None
        if lateral_direction.Length <= 1e-9:
            return None
        if not self.visible_layers:
            return None
        if world_direction.Length <= 1e-9:
            return -self.y_min
        if lateral_direction.dot(world_direction) >= 0:
            return -self.y_min
        return -self.y_max


@dataclass(frozen=True)
class WallTrimPlane:
    """Renderer-independent half-space trimming one end of a wall."""

    end_name: str
    origin: object
    normal: object
    extension: float = 0.0

    def __post_init__(self):
        if self.end_name not in ("Start", "End"):
            raise ValueError("WallTrimPlane end_name must be Start or End")
        normal = FreeCAD.Vector(self.normal)
        if normal.Length <= 1e-9:
            raise ValueError("WallTrimPlane requires a non-zero normal")
        normal.normalize()
        object.__setattr__(self, "origin", FreeCAD.Vector(self.origin))
        object.__setattr__(self, "normal", normal)
        object.__setattr__(self, "extension", float(self.extension))


@dataclass(frozen=True)
class WallViewportMesh:
    """Closed triangle mesh derived from a wall recipe without OCCT."""

    vertices: tuple
    triangles: tuple
    triangle_roles: tuple

    @property
    def bounds(self):
        """Return axis-aligned bounds as ``(xmin, ymin, zmin, xmax, ymax, zmax)``."""

        coordinates = tuple(zip(*((point.x, point.y, point.z) for point in self.vertices)))
        return tuple(min(values) for values in coordinates) + tuple(
            max(values) for values in coordinates
        )

    @property
    def volume(self):
        """Return the volume enclosed by the consistently oriented triangles."""

        signed_volume = 0.0
        for first, second, third in self.triangles:
            a = self.vertices[first]
            b = self.vertices[second]
            c = self.vertices[third]
            signed_volume += a.dot(b.cross(c)) / 6.0
        return abs(signed_volume)

    @property
    def is_closed(self):
        """Whether every undirected triangle edge has exactly two users."""

        edge_users = {}
        for triangle in self.triangles:
            for first, second in zip(triangle, triangle[1:] + triangle[:1]):
                edge = tuple(sorted((first, second)))
                edge_users[edge] = edge_users.get(edge, 0) + 1
        return bool(edge_users) and all(count == 2 for count in edge_users.values())


@dataclass(frozen=True)
class WallGeometryRecipe:
    """Resolved straight-wall geometry shared by display and exact outputs."""

    axis_start: object
    axis_end: object
    lateral: object
    section: WallSection
    z_min: float
    z_max: float
    trim_planes: tuple = ()
    openings: tuple = ()

    def __post_init__(self):
        start = FreeCAD.Vector(self.axis_start)
        end = FreeCAD.Vector(self.axis_end)
        if end.sub(start).Length <= 1e-9:
            raise ValueError("WallGeometryRecipe requires a non-degenerate axis")
        lateral = FreeCAD.Vector(self.lateral)
        if lateral.Length <= 1e-9:
            raise ValueError("WallGeometryRecipe requires a lateral direction")
        lateral.normalize()
        if not isinstance(self.section, WallSection):
            raise TypeError("WallGeometryRecipe requires a WallSection")
        object.__setattr__(self, "axis_start", start)
        object.__setattr__(self, "axis_end", end)
        object.__setattr__(self, "lateral", lateral)
        object.__setattr__(self, "z_min", float(self.z_min))
        object.__setattr__(self, "z_max", float(self.z_max))
        object.__setattr__(self, "trim_planes", tuple(self.trim_planes or ()))
        object.__setattr__(self, "openings", tuple(self.openings or ()))

    def opening_intervals_at(self, cut_z):
        """Return merged axis intervals for openings crossing one elevation."""

        intervals = [
            (opening.u_min, opening.u_max)
            for opening in self.openings
            if opening.intersects_elevation(cut_z)
        ]
        merged = []
        for lower, upper in sorted(intervals):
            if merged and lower <= merged[-1][1] + 1e-7:
                merged[-1] = (merged[-1][0], max(merged[-1][1], upper))
            else:
                merged.append((lower, upper))
        return tuple(merged)

    def plan_boundaries(self, target_z, opening_intervals=(), *, y_min=None, y_max=None):
        """Derive clipped Plan polygons without constructing an OCCT shape."""

        start = FreeCAD.Vector(self.axis_start)
        end = FreeCAD.Vector(self.axis_end)
        axis = end.sub(start)
        axis.normalize()
        for trim in self.trim_planes:
            if trim.end_name == "Start":
                start = start.sub(axis * trim.extension)
            else:
                end = end.add(axis * trim.extension)
        lower = self.section.y_min if y_min is None else float(y_min)
        upper = self.section.y_max if y_max is None else float(y_max)
        polygon = [
            start.add(self.lateral * lower),
            end.add(self.lateral * lower),
            end.add(self.lateral * upper),
            start.add(self.lateral * upper),
        ]
        for trim in self.trim_planes:
            reference = end if trim.end_name == "Start" else start
            keep_sign = 1.0 if reference.sub(trim.origin).dot(trim.normal) >= 0 else -1.0
            polygon = _clip_polygon(
                polygon,
                lambda point, trim=trim, sign=keep_sign: (
                    point.sub(trim.origin).dot(trim.normal) * sign
                ),
            )

        polygons = [polygon] if len(polygon) >= 3 else []
        origin = FreeCAD.Vector(self.axis_start)
        for lower, upper in opening_intervals:
            pieces = []
            for current in polygons:
                left = _clip_polygon(
                    current,
                    lambda point, limit=lower: limit - point.sub(origin).dot(axis),
                )
                right = _clip_polygon(
                    current,
                    lambda point, limit=upper: point.sub(origin).dot(axis) - limit,
                )
                if len(left) >= 3:
                    pieces.append(left)
                if len(right) >= 3:
                    pieces.append(right)
            polygons = pieces

        return tuple(
            tuple(FreeCAD.Vector(point.x, point.y, float(target_z)) for point in polygon)
            for polygon in polygons
        )

    def viewport_mesh(self):
        """Build an experimental closed mesh for a straight wall without openings.

        Openings deliberately remain unsupported until their full 3D topology can
        be represented without falling back to boolean operations.
        """

        if self.openings or self.z_max <= self.z_min:
            return None
        boundaries = self.plan_boundaries(self.z_min)
        if len(boundaries) != 1 or len(boundaries[0]) < 3:
            return None
        bottom = list(boundaries[0])
        signed_area = sum(
            first.x * second.y - second.x * first.y
            for first, second in zip(bottom, bottom[1:] + bottom[:1])
        )
        if signed_area < 0:
            bottom.reverse()
        count = len(bottom)
        top = [FreeCAD.Vector(point.x, point.y, self.z_max) for point in bottom]
        triangles = []
        roles = []
        for index in range(1, count - 1):
            triangles.append((0, index + 1, index))
            roles.append("Bottom")
            triangles.append((count, count + index, count + index + 1))
            roles.append("Top")
        axis = self.axis_end.sub(self.axis_start)
        axis.normalize()
        for index in range(count):
            following = (index + 1) % count
            triangles.extend(
                (
                    (index, following, count + following),
                    (index, count + following, count + index),
                )
            )
            edge = bottom[following].sub(bottom[index])
            if abs(edge.dot(axis)) >= abs(edge.dot(self.lateral)):
                midpoint = bottom[index].add(bottom[following]) * 0.5
                offset = midpoint.sub(self.axis_start).dot(self.lateral)
                role = "SideMin" if abs(offset - self.section.y_min) <= abs(
                    offset - self.section.y_max
                ) else "SideMax"
            else:
                role = "End"
            roles.extend((role, role))
        return WallViewportMesh(tuple(bottom + top), tuple(triangles), tuple(roles))


def _clip_polygon(polygon, signed_distance, tolerance=1e-7):
    """Clip a convex polygon to the non-negative side of one line."""

    if not polygon:
        return []
    result = []
    previous = polygon[-1]
    previous_distance = float(signed_distance(previous))
    for current in polygon:
        current_distance = float(signed_distance(current))
        previous_inside = previous_distance >= -tolerance
        current_inside = current_distance >= -tolerance
        if previous_inside != current_inside:
            denominator = previous_distance - current_distance
            if abs(denominator) > 1e-12:
                ratio = previous_distance / denominator
                result.append(previous.add(current.sub(previous) * ratio))
        if current_inside:
            result.append(FreeCAD.Vector(current))
        previous = current
        previous_distance = current_distance
    return result


@dataclass(frozen=True)
class WallOpeningRecipe:
    """A host-aligned opening volume consumed by Plan and future 3D outputs."""

    source: object
    u_min: float
    u_max: float
    v_min: float
    v_max: float
    z_min: float
    z_max: float

    def __post_init__(self):
        for lower_name, upper_name in (
            ("u_min", "u_max"),
            ("v_min", "v_max"),
            ("z_min", "z_max"),
        ):
            lower = float(getattr(self, lower_name))
            upper = float(getattr(self, upper_name))
            if upper <= lower:
                raise ValueError(f"WallOpeningRecipe requires {upper_name} > {lower_name}")
            object.__setattr__(self, lower_name, lower)
            object.__setattr__(self, upper_name, upper)

    def intersects_elevation(self, elevation, tolerance=1e-7):
        elevation = float(elevation)
        return self.z_min - tolerance <= elevation <= self.z_max + tolerance
