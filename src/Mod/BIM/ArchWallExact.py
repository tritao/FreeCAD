# SPDX-License-Identifier: LGPL-2.1-or-later

"""Experimental exact wall compiler for analytically supported geometry."""

from dataclasses import dataclass

import FreeCAD


@dataclass(frozen=True)
class WallExactFaceRole:
    """Semantic identity assigned to one face of a compiled wall solid."""

    face_index: int
    role: str
    source: object = None


@dataclass(frozen=True)
class WallExactCompilation:
    """An exact OCCT wall shape and its compiler-owned face semantics."""

    shape: object
    face_roles: tuple


def compile_straight_wall(wall, proxy):
    """Compile a supported wall without invoking a three-dimensional boolean."""

    import ArchPlanAnalytic

    recipe = ArchPlanAnalytic.straight_wall_geometry_recipe(wall, proxy)
    return compile_wall_recipe(recipe) if recipe is not None else None


def compile_wall_recipe(recipe, tolerance=1e-7):
    """Build one perforated wall solid directly, or return ``None``.

    Supported walls are horizontal, straight and single-layer. End trims must
    be vertical. Openings must be disjoint rectangles fully contained by the
    wall and span its complete lateral thickness.
    """

    if recipe is None:
        return None
    layers = recipe.section.visible_layers
    if len(layers) != 1 or recipe.z_max <= recipe.z_min + tolerance:
        return None
    axis = recipe.axis_end.sub(recipe.axis_start)
    length = axis.Length
    axis.normalize()
    lateral = FreeCAD.Vector(recipe.lateral)
    if abs(axis.z) > tolerance or abs(lateral.z) > tolerance:
        return None
    if abs(axis.dot(lateral)) > tolerance:
        return None
    if any(abs(trim.normal.z) > tolerance for trim in recipe.trim_planes):
        return None

    boundaries = recipe.plan_boundaries(recipe.z_min)
    if len(boundaries) != 1 or len(boundaries[0]) < 3:
        return None
    footprint = tuple(
        (
            point.sub(recipe.axis_start).dot(axis),
            point.sub(recipe.axis_start).dot(lateral),
        )
        for point in boundaries[0]
    )
    side_extents = {
        side: _polygon_u_extents_at_v(footprint, side, tolerance)
        for side in (recipe.section.y_min, recipe.section.y_max)
    }
    if any(extents is None for extents in side_extents.values()):
        return None

    openings = tuple(recipe.openings)
    for opening in openings:
        inside_both_sides = all(
            extents[0] + tolerance < opening.u_min
            and opening.u_max < extents[1] - tolerance
            for extents in side_extents.values()
        )
        if (
            not inside_both_sides
            or opening.z_min <= recipe.z_min + tolerance
            or opening.z_max >= recipe.z_max - tolerance
            or opening.v_min > recipe.section.y_min + tolerance
            or opening.v_max < recipe.section.y_max - tolerance
        ):
            return None
    for index, opening in enumerate(openings):
        for other in openings[index + 1 :]:
            separated = (
                opening.u_max < other.u_min - tolerance
                or other.u_max < opening.u_min - tolerance
                or opening.z_max < other.z_min - tolerance
                or other.z_max < opening.z_min - tolerance
            )
            if not separated:
                return None

    if recipe.trim_planes:
        return _compile_trimmed_prism(
            recipe, axis, lateral, footprint, side_extents, tolerance
        )

    import Part

    def profile_point(u, z):
        point = recipe.axis_start.add(axis * float(u)).add(
            lateral * recipe.section.y_min
        )
        point.z = float(z)
        return point

    def rectangle_wire(u_min, u_max, z_min, z_max, reverse=False):
        points = [
            profile_point(u_min, z_min),
            profile_point(u_max, z_min),
            profile_point(u_max, z_max),
            profile_point(u_min, z_max),
        ]
        if reverse:
            points.reverse()
        return Part.makePolygon((*points, points[0]))

    outer = rectangle_wire(0.0, length, recipe.z_min, recipe.z_max)
    holes = tuple(
        rectangle_wire(
            opening.u_min,
            opening.u_max,
            opening.z_min,
            opening.z_max,
            reverse=True,
        )
        for opening in openings
    )
    try:
        profile = Part.Face([outer, *holes])
        shape = profile.extrude(
            lateral * (recipe.section.y_max - recipe.section.y_min)
        )
    except Part.OCCError:
        return None
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        return None
    return WallExactCompilation(shape, _classify_faces(shape, recipe, axis, tolerance))


def _polygon_u_extents_at_v(polygon, target_v, tolerance):
    intersections = []
    for first, second in zip(polygon, polygon[1:] + polygon[:1]):
        u1, v1 = first
        u2, v2 = second
        if abs(v1 - target_v) <= tolerance:
            intersections.append(u1)
        if abs(v2 - target_v) <= tolerance:
            intersections.append(u2)
        if (v1 < target_v - tolerance and v2 > target_v + tolerance) or (
            v2 < target_v - tolerance and v1 > target_v + tolerance
        ):
            parameter = (target_v - v1) / (v2 - v1)
            intersections.append(u1 + parameter * (u2 - u1))
    if len(intersections) < 2:
        return None
    return min(intersections), max(intersections)


def _compile_trimmed_prism(recipe, axis, lateral, footprint, side_extents, tolerance):
    """Build a joined wall as an explicitly closed shell without a 3D BOP."""

    import Part

    origin = FreeCAD.Vector(recipe.axis_start)

    def point(u, v, z):
        result = origin.add(axis * float(u)).add(lateral * float(v))
        result.z = float(z)
        return result

    def wire(points, reverse=False):
        values = list(points)
        if reverse:
            values.reverse()
        return Part.makePolygon((*values, values[0]))

    faces = []

    def add_face(points, holes=()):
        outer = wire(points)
        inner = tuple(wire(hole, reverse=True) for hole in holes)
        face = Part.Face([outer, *inner]) if inner else Part.Face(outer)
        faces.append(face)

    bottom = tuple(point(u, v, recipe.z_min) for u, v in footprint)
    top = tuple(point(u, v, recipe.z_max) for u, v in footprint)
    add_face(bottom)
    add_face(top)

    for side in (recipe.section.y_min, recipe.section.y_max):
        u_min, u_max = side_extents[side]
        outer = (
            point(u_min, side, recipe.z_min),
            point(u_max, side, recipe.z_min),
            point(u_max, side, recipe.z_max),
            point(u_min, side, recipe.z_max),
        )
        holes = tuple(
            (
                point(opening.u_min, side, opening.z_min),
                point(opening.u_max, side, opening.z_min),
                point(opening.u_max, side, opening.z_max),
                point(opening.u_min, side, opening.z_max),
            )
            for opening in recipe.openings
        )
        add_face(outer, holes=holes)

    for first, second in zip(footprint, footprint[1:] + footprint[:1]):
        if abs(first[1] - second[1]) <= tolerance:
            continue
        add_face(
            (
                point(first[0], first[1], recipe.z_min),
                point(second[0], second[1], recipe.z_min),
                point(second[0], second[1], recipe.z_max),
                point(first[0], first[1], recipe.z_max),
            )
        )

    for opening in recipe.openings:
        v_min = recipe.section.y_min
        v_max = recipe.section.y_max
        add_face(
            (
                point(opening.u_min, v_min, opening.z_min),
                point(opening.u_min, v_max, opening.z_min),
                point(opening.u_min, v_max, opening.z_max),
                point(opening.u_min, v_min, opening.z_max),
            ),
        )
        add_face(
            (
                point(opening.u_max, v_min, opening.z_min),
                point(opening.u_max, v_max, opening.z_min),
                point(opening.u_max, v_max, opening.z_max),
                point(opening.u_max, v_min, opening.z_max),
            ),
        )
        for z in (opening.z_min, opening.z_max):
            add_face(
                (
                    point(opening.u_min, v_min, z),
                    point(opening.u_max, v_min, z),
                    point(opening.u_max, v_max, z),
                    point(opening.u_min, v_max, z),
                )
            )

    try:
        # Stitching the known boundary faces avoids the general 3D Boolean
        # intersection machinery (and its thread pool) used by wall joins.
        shell = Part.makeShell(faces)
        shape = Part.makeSolid(shell)
        if shape.Volume < 0:
            shape.reverse()
    except Part.OCCError:
        return None
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        return None
    return WallExactCompilation(
        shape, _classify_faces(shape, recipe, axis, tolerance)
    )


def _classify_faces(shape, recipe, axis, tolerance):
    roles = []
    origin = FreeCAD.Vector(recipe.axis_start)
    lateral = FreeCAD.Vector(recipe.lateral)
    for index, face in enumerate(shape.Faces, start=1):
        center = FreeCAD.Vector(face.CenterOfMass)
        u = center.sub(origin).dot(axis)
        v = center.sub(origin).dot(lateral)
        z = center.z
        role = "WallFace"
        source = None
        if abs(z - recipe.z_min) <= tolerance:
            role = "Bottom"
        elif abs(z - recipe.z_max) <= tolerance:
            role = "Top"
        elif abs(v - recipe.section.y_min) <= tolerance:
            role = "SideMin"
        elif abs(v - recipe.section.y_max) <= tolerance:
            role = "SideMax"
        else:
            for opening in recipe.openings:
                if (
                    opening.u_min - tolerance <= u <= opening.u_max + tolerance
                    and opening.z_min - tolerance <= z <= opening.z_max + tolerance
                ):
                    source = opening.source
                    if abs(z - opening.z_min) <= tolerance:
                        role = "OpeningSill"
                    elif abs(z - opening.z_max) <= tolerance:
                        role = "OpeningHead"
                    else:
                        role = "OpeningJamb"
                    break
            if role == "WallFace":
                middle_u = recipe.axis_end.sub(recipe.axis_start).Length * 0.5
                role = "EndStart" if u < middle_u else "EndEnd"
        roles.append(WallExactFaceRole(index, role, source))
    return tuple(roles)
