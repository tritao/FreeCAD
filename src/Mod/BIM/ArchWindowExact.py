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
    opening_envelope: HostedOpeningEnvelope


def compile_window_parts(obj):
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

    result = []
    movement = None
    for index in range(0, len(parts), 5):
        parsed = _parse_selector(parts[index + 2], base_shape)
        if parsed is None:
            return None
        wires, hinge_index, mode = parsed
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
        shape = _extrude_window_part_profile(outer, inner, extrusion)
        if not shape or shape.isNull() or len(shape.Solids) != 1:
            return None
        offset_vector = FreeCAD.Vector()
        if offset:
            offset_vector = DraftVecUtils.scaleTo(normal, offset)
            shape.translate(offset_vector)

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
    shape = Part.makeCompound(result)
    if shape.isNull():
        return None
    envelope = _opening_envelope(base_shape)
    if envelope is None:
        return None
    return WindowExactCompilation(
        shape=shape,
        part_shapes=tuple(result),
        opening_envelope=envelope,
    )


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
    hinge_index = None
    mode = None
    try:
        for token in str(selector).split(","):
            if token.startswith("Wire"):
                wire_index = int(token[4:])
                if wire_index < 0 or wire_index >= len(base_shape.Wires):
                    return None
                wires.append(base_shape.Wires[wire_index])
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
    return (tuple(wires), hinge_index, mode) if wires else None


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
