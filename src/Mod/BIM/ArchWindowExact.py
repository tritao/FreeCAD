# SPDX-License-Identifier: LGPL-2.1-or-later

"""Exact compiler for the common planar Arch WindowParts representation."""

from dataclasses import dataclass
import math

import FreeCAD


@dataclass(frozen=True)
class HostedOpeningEnvelope:
    """Document-space base geometry shared by native, wall and plan compilers."""

    point_lists: tuple
    z_min: float
    z_max: float

    def vectors(self):
        return tuple(
            tuple(FreeCAD.Vector(*coordinates) for coordinates in point_list)
            for point_list in self.point_lists
        )


@dataclass(frozen=True)
class WindowExactCompilation:
    """A final WindowParts shape with compiler-owned topology."""

    shape: object
    part_shapes: tuple
    closed_part_shapes: tuple
    part_profiles: tuple
    opening_envelope: HostedOpeningEnvelope
    base_placement: object
    source_signature: tuple


class WindowExactCompilationCache:
    """Derived exact geometry retained by one Window proxy."""

    def __init__(self):
        self.current = None
        self.previous = None

    def invalidate(self):
        if self.current is not None:
            self.previous = self.current
        self.current = None

    def clear(self):
        self.current = None
        self.previous = None

    def ensure(self, obj):
        if self.current is None:
            self.current = compile_window_parts(obj, previous=self.previous)
            self.previous = None
        return self.current

    def publish(self, compilation):
        self.current = compilation
        self.previous = None


def compile_window_parts(obj, previous=None):
    """Compile supported planar WindowParts, or return ``None``.

    This deliberately covers only construction geometry. Legacy plan/elevation
    symbols, louvres and component additions/subtractions retain the general
    builder.
    """

    parts = tuple(getattr(obj, "WindowParts", ()) or ())
    base = getattr(obj, "Base", None)
    if (
        base is None
        or not parts
        or len(parts) % 5
        or getattr(obj, "SymbolPlan", False)
        or getattr(obj, "SymbolElevation", False)
        or getattr(obj, "Additions", None)
        or getattr(obj, "Subtractions", None)
    ):
        return None
    if any(parts[index + 1] == "Louvre" for index in range(0, len(parts), 5)):
        return None

    base_shape = getattr(base, "Shape", None)
    if (
        not base_shape
        or base_shape.isNull()
        or not base_shape.Wires
        or not base_shape.isValid()
    ):
        return None

    import DraftVecUtils
    import Part
    from ArchWindow import _extrude_window_part_profile

    source_signature = _source_signature(obj, parts)
    base_placement = FreeCAD.Placement(base.getGlobalPlacement())
    result = []
    closed_shapes = []
    part_profiles = []
    movement = None
    for part_index, index in enumerate(range(0, len(parts), 5)):
        parsed = _parse_selector(parts[index + 2], base_shape)
        if parsed is None:
            return None
        wires, wire_indices, hinge_index, mode = parsed
        outer = max(wires, key=lambda wire: wire.BoundBox.DiagonalLength)
        inner = tuple(wire for wire in wires if not wire.isSame(outer))
        try:
            face = Part.Face(outer)
            normal = _part_normal(obj, face)
            thickness = _part_value(parts[index + 3], getattr(obj, "Frame", 0.0))
            offset = _part_value(parts[index + 4], getattr(obj, "Offset", 0.0))
        except (Part.OCCError, TypeError, ValueError):
            return None
        if normal is None or not thickness:
            return None

        extrusion = DraftVecUtils.scaleTo(normal, thickness)
        profile = _profile_points(wires, base_placement)
        shape = _reuse_closed_part(
            previous,
            part_index,
            profile,
            base_placement,
            source_signature,
        )
        reused = shape is not None
        if not reused:
            profile_face = None
            face_provider = getattr(
                getattr(base, "Proxy", None), "makeSelectedFace", None
            )
            if callable(face_provider):
                profile_face = face_provider(base, wire_indices)
            shape = _extrude_window_part_profile(
                outer,
                inner,
                extrusion,
                outer_face=face,
                profile_face=profile_face,
            )
        if not shape or shape.isNull() or len(shape.Solids) != 1:
            return None
        offset_vector = FreeCAD.Vector()
        if offset:
            offset_vector = DraftVecUtils.scaleTo(normal, offset)
            if not reused:
                shape.translate(offset_vector)

        closed_shapes.append(shape.copy())
        part_profiles.append(profile)

        if hinge_index is not None and mode:
            movement = _part_movement(
                obj,
                face,
                hinge_index,
                mode,
                normal,
                extrusion,
                offset_vector,
            )
            if movement is None:
                return None
        if movement is not None:
            kind, values = movement
            if kind == "rotate":
                pivot, axis, angle = values
                shape.rotate(pivot, axis, angle)
            else:
                shape.translate(values)
        result.append(shape)

    if not result:
        return None
    # This compiler owns the final topology and exposes part identity through
    # ``part_shapes`` rather than persistent element names. ``makeCompound``
    # nevertheless synthesizes a large element map from its inputs; dropping
    # it here avoids expanding irrelevant naming history when Shape is assigned.
    shape = Part.makeCompound(result).copy(noElementMap=True)
    if shape.isNull():
        return None
    envelope = _opening_envelope(base_shape)
    if envelope is None:
        return None
    return WindowExactCompilation(
        shape=shape,
        part_shapes=tuple(result),
        closed_part_shapes=tuple(closed_shapes),
        part_profiles=tuple(part_profiles),
        opening_envelope=envelope,
        base_placement=base_placement,
        source_signature=source_signature,
    )


def _source_signature(obj, parts):
    normal = FreeCAD.Vector(getattr(obj, "Normal", FreeCAD.Vector()))
    return (
        parts,
        float(getattr(getattr(obj, "Frame", 0.0), "Value", 0.0)),
        float(getattr(getattr(obj, "Offset", 0.0), "Value", 0.0)),
        (normal.x, normal.y, normal.z),
        bool(getattr(obj, "AutoNormalReversed", False)),
    )


def _profile_points(wires, placement):
    inverse = placement.inverse()
    return tuple(
        tuple(
            tuple(inverse.multVec(vertex.Point))
            for vertex in wire.Vertexes
        )
        for wire in wires
    )


def _reuse_closed_part(previous, index, profile, placement, source_signature):
    """Reuse one part only when its selected wires share one exact affine map."""

    if (
        previous is None
        or previous.source_signature != source_signature
        or index >= len(previous.closed_part_shapes)
        or index >= len(previous.part_profiles)
    ):
        return None
    old_profile = previous.part_profiles[index]
    if tuple(map(len, old_profile)) != tuple(map(len, profile)):
        return None
    old_points = tuple(point for wire in old_profile for point in wire)
    new_points = tuple(point for wire in profile for point in wire)
    if not old_points:
        return None

    def axis_transform(axis):
        old_values = [point[axis] for point in old_points]
        new_values = [point[axis] for point in new_points]
        old_span = max(old_values) - min(old_values)
        new_span = max(new_values) - min(new_values)
        if old_span <= 1e-9:
            return (1.0, new_values[0] - old_values[0])
        scale = new_span / old_span
        return (scale, min(new_values) - min(old_values) * scale)

    scale_x, offset_x = axis_transform(0)
    scale_y, offset_y = axis_transform(1)
    scale_z, offset_z = axis_transform(2)
    for old, new in zip(old_points, new_points):
        mapped = (
            old[0] * scale_x + offset_x,
            old[1] * scale_y + offset_y,
            old[2] * scale_z + offset_z,
        )
        if any(abs(actual - expected) > 1e-6 for actual, expected in zip(mapped, new)):
            return None

    local_scale = FreeCAD.Matrix()
    local_scale.A11 = scale_x
    local_scale.A22 = scale_y
    local_scale.A33 = scale_z
    local_scale.A14 = offset_x
    local_scale.A24 = offset_y
    local_scale.A34 = offset_z
    transform = (
        placement.toMatrix()
        * local_scale
        * previous.base_placement.inverse().toMatrix()
    )
    try:
        shape = previous.closed_part_shapes[index].transformGeometry(transform)
    except Exception:
        return None
    if not shape or shape.isNull() or len(shape.Solids) != 1:
        return None
    return shape


def _opening_envelope(base_shape):
    point_lists = []
    z_values = []
    for edge in base_shape.Edges:
        points = edge.tessellate(1)
        if isinstance(points, tuple):
            points = points[0]
        if len(points) < 2:
            try:
                points = edge.discretize(Deflection=1.0)
            except Exception:
                points = []
        if len(points) < 2:
            points = [vertex.Point for vertex in edge.Vertexes]
        if len(points) < 2:
            continue
        coordinates = tuple((point.x, point.y, point.z) for point in points)
        point_lists.append(coordinates)
        z_values.extend(point[2] for point in coordinates)
    if not point_lists or not z_values:
        return None
    return HostedOpeningEnvelope(
        point_lists=tuple(point_lists),
        z_min=min(z_values),
        z_max=max(z_values),
    )


def _parse_selector(selector, base_shape):
    wires = []
    wire_indices = []
    hinge_index = None
    mode = None
    try:
        for token in str(selector).split(","):
            if token.startswith("Wire"):
                wire_index = int(token[4:])
                if wire_index < 0 or wire_index >= len(base_shape.Wires):
                    return None
                wires.append(base_shape.Wires[wire_index])
                wire_indices.append(wire_index)
            elif token.startswith("Edge"):
                hinge_index = int(token[4:]) - 1
                if hinge_index < 0 or hinge_index >= len(base_shape.Edges):
                    return None
            elif token.startswith("Mode"):
                mode = int(token[4:])
                if mode < 0 or mode > 10:
                    return None
            elif token.strip():
                return None
    except ValueError:
        return None
    return (tuple(wires), tuple(wire_indices), hinge_index, mode) if wires else None


def _part_normal(obj, face):
    import DraftVecUtils

    normal = FreeCAD.Vector(getattr(obj, "Normal", FreeCAD.Vector()))
    if DraftVecUtils.isNull(normal):
        if not getattr(obj, "AutoNormalReversed", False):
            normal = face.normalAt(0, 0)
        else:
            normal = obj.Base.getGlobalPlacement().Rotation.multVec(FreeCAD.Vector(0, 0, -1))
    return normal if not DraftVecUtils.isNull(normal) else None


def _part_value(expression, variable):
    text = str(expression or "")
    extra = 0.0
    if text.endswith("+V"):
        text = text[:-2]
        extra = float(getattr(variable, "Value", variable) or 0.0)
    return float(text or 0.0) + extra


def _part_movement(obj, face, hinge_index, mode, normal, extrusion, offset):
    import DraftVecUtils

    edge = obj.Base.Shape.Edges[hinge_index]
    first = FreeCAD.Vector(edge.Vertexes[0].Point)
    second = FreeCAD.Vector(edge.Vertexes[-1].Point)
    tolerance = 1e-5
    if math.isclose(first.z, second.z, abs_tol=tolerance):
        local = obj.Base.Placement.Rotation.inverted().multVec(second - first)
        for coordinate in list(local)[::-1]:
            if math.isclose(coordinate, 0.0, abs_tol=tolerance):
                continue
            if coordinate < 0.0:
                first, second = second, first
            break
    elif second.z < first.z:
        first, second = second, first

    axis = second - first
    farthest = None
    distance = 0.0
    for vertex in face.Vertexes:
        candidate_distance = vertex.Point.distanceToLine(first, axis)
        if candidate_distance > distance:
            distance = candidate_distance
            farthest = FreeCAD.Vector(vertex.Point)
    if farthest is None:
        return None
    projection = DraftVecUtils.project(farthest - first, axis)
    if projection.Length > 0.0:
        farthest = farthest - projection
    chord = farthest - first
    opening = float(getattr(obj, "Opening", 0.0) or 0.0) / 100.0

    if 1 <= mode <= 8:
        angles = {1: 90.0, 2: -90.0, 3: 45.0, 4: -45.0,
                  5: 180.0, 6: -180.0, 7: 90.0, 8: -90.0}
        pivot = FreeCAD.Vector(first)
        adjusted_offset = FreeCAD.Vector(offset)
        if DraftVecUtils.angle(chord, normal, axis) < 0:
            if mode % 2 == 0:
                adjusted_offset = adjusted_offset + extrusion
        elif mode % 2 == 1:
            adjusted_offset = adjusted_offset + extrusion
        pivot = pivot + adjusted_offset
        return "rotate", (pivot, axis, angles[mode] * opening)
    if mode in (9, 10):
        inverse = obj.Base.Placement.inverse()
        points = sorted(
            ((inverse.multVec(first), first), (inverse.multVec(second), second)),
            key=lambda item: tuple(round(value, 3) for value in item[0]),
        )
        start, end = (points[0][1], points[1][1]) if mode == 9 else (points[1][1], points[0][1])
        travel = end - start
        length = travel.Length
        if length <= 1e-9:
            return None
        travel.normalize()
        return "translate", travel * min(length * opening, max(0.0, length - 80.0))
    return None
