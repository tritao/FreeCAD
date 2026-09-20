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
    recipe: object
    face_roles: tuple
    vertical_area: float
    horizontal_area: float
    perimeter_length: float


def compile_straight_wall(wall, proxy, geometry_shape=None):
    """Compile a supported wall without invoking a three-dimensional boolean."""

    if (
        getattr(wall, "Additions", None)
        or getattr(wall, "Subtractions", None)
        or getattr(wall, "Axis", None)
        or getattr(wall, "MakeBlocks", False)
    ):
        return None

    import ArchPlanAnalytic

    recipe = ArchPlanAnalytic.straight_wall_geometry_recipe(
        wall, proxy, geometry_shape=geometry_shape
    )
    return compile_wall_recipe(recipe) if recipe is not None else None


def compile_wall_recipe(recipe, tolerance=1e-7):
    """Build one perforated wall solid directly, or return ``None``.

    Supported walls are horizontal, straight and single-layer. End trims must
    be vertical. Openings must be disjoint rectangles, may meet the wall's
    bottom boundary, and must span its complete lateral thickness.
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
        section_width = recipe.section.y_max - recipe.section.y_min
        opening_depth = opening.v_max - opening.v_min
        spans_section = (
            opening_depth >= section_width - tolerance
            or (
                opening.v_min <= recipe.section.y_min + tolerance
                and opening.v_max >= recipe.section.y_max - tolerance
            )
        )
        inside_both_sides = all(
            extents[0] + tolerance < opening.u_min
            and opening.u_max < extents[1] - tolerance
            for extents in side_extents.values()
        )
        if (
            not inside_both_sides
            or opening.z_min < recipe.z_min - tolerance
            or opening.z_max >= recipe.z_max - tolerance
            or not spans_section
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

    boundary_openings = tuple(
        opening
        for opening in openings
        if opening.z_min <= recipe.z_min + tolerance
    )
    if boundary_openings and not recipe.trim_planes:
        compilation = _compile_prismatic_profile(
            recipe,
            axis,
            lateral,
            side_extents,
            boundary_openings,
            tolerance,
        )
        if compilation is not None:
            return compilation
    if recipe.trim_planes or boundary_openings:
        return _compile_boundary_shell(
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
    return _compilation(shape, recipe, axis, tolerance)


def _compile_prismatic_profile(
    recipe,
    axis,
    lateral,
    side_extents,
    bottom_openings,
    tolerance,
):
    """Extrude one elevation profile for an untrimmed straight wall."""

    import Part

    first_extents, second_extents = tuple(side_extents.values())
    if any(
        abs(first - second) > tolerance
        for first, second in zip(first_extents, second_extents)
    ):
        return None
    u_min, u_max = first_extents

    def point(u, z):
        result = recipe.axis_start.add(axis * float(u)).add(
            lateral * recipe.section.y_min
        )
        result.z = float(z)
        return result

    def wire(points, reverse=False):
        values = [point(u, z) for u, z in points]
        if reverse:
            values.reverse()
        return Part.makePolygon((*values, values[0]))

    outer = wire(
        _elevation_outline(
            u_min,
            u_max,
            recipe.z_min,
            recipe.z_max,
            bottom_openings,
        )
    )
    holes = tuple(
        wire(
            (
                (opening.u_min, opening.z_min),
                (opening.u_max, opening.z_min),
                (opening.u_max, opening.z_max),
                (opening.u_min, opening.z_max),
            ),
            reverse=True,
        )
        for opening in recipe.openings
        if opening not in bottom_openings
    )
    try:
        profile = Part.Face([outer, *holes]) if holes else Part.Face(outer)
        shape = profile.extrude(
            lateral * (recipe.section.y_max - recipe.section.y_min)
        )
        if shape.Volume < 0:
            shape.reverse()
    except Part.OCCError:
        return None
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        return None
    return _compilation(shape, recipe, axis, tolerance)


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


def _compile_boundary_shell(recipe, axis, lateral, footprint, side_extents, tolerance):
    """Build joined or bottom-open wall geometry without a three-dimensional BOP."""

    import Part

    origin = FreeCAD.Vector(recipe.axis_start)

    def point(u, v, z):
        result = origin.add(axis * float(u)).add(lateral * float(v))
        result.z = float(z)
        return result

    def wire(points, reverse=False):
        values = _clean_polygon_points(points, tolerance)
        if reverse:
            values.reverse()
        return Part.makePolygon((*values, values[0]))

    faces = []

    def add_face(points, holes=()):
        outer = wire(points)
        inner = tuple(wire(hole, reverse=True) for hole in holes)
        face = Part.Face([outer, *inner]) if inner else Part.Face(outer)
        faces.append(face)

    top = tuple(point(u, v, recipe.z_max) for u, v in footprint)
    add_face(top)

    bottom_openings = tuple(
        opening
        for opening in recipe.openings
        if opening.z_min <= recipe.z_min + tolerance
    )
    bottom_intervals = tuple(
        (opening.u_min, opening.u_max) for opening in bottom_openings
    )
    for boundary in recipe.plan_boundaries(recipe.z_min, bottom_intervals):
        add_face(
            tuple(
                point(
                    vertex.sub(recipe.axis_start).dot(axis),
                    vertex.sub(recipe.axis_start).dot(lateral),
                    recipe.z_min,
                )
                for vertex in boundary
            )
        )

    for side in (recipe.section.y_min, recipe.section.y_max):
        u_min, u_max = side_extents[side]
        outer = tuple(
            point(u, side, z)
            for u, z in _elevation_outline(
                u_min,
                u_max,
                recipe.z_min,
                recipe.z_max,
                bottom_openings,
            )
        )
        holes = tuple(
            (
                point(opening.u_min, side, opening.z_min),
                point(opening.u_max, side, opening.z_min),
                point(opening.u_max, side, opening.z_max),
                point(opening.u_min, side, opening.z_max),
            )
            for opening in recipe.openings
            if opening not in bottom_openings
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
        reveal_levels = [opening.z_max]
        if opening not in bottom_openings:
            reveal_levels.insert(0, opening.z_min)
        for z in reveal_levels:
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
    return _compilation(shape, recipe, axis, tolerance)


def _elevation_outline(u_min, u_max, z_min, z_max, bottom_openings):
    """Return a wall-side outline with floor-touching openings as notches."""

    points = [(u_min, z_min)]
    for opening in sorted(bottom_openings, key=lambda item: item.u_min):
        points.extend(
            (
                (opening.u_min, z_min),
                (opening.u_min, opening.z_max),
                (opening.u_max, opening.z_max),
                (opening.u_max, z_min),
            )
        )
    points.extend(((u_max, z_min), (u_max, z_max), (u_min, z_max)))
    return tuple(points)


def _clean_polygon_points(points, tolerance):
    """Remove clipping duplicates and straight-through vertices from a wire."""

    values = []
    for point in points:
        value = FreeCAD.Vector(point)
        if not values or value.sub(values[-1]).Length > tolerance:
            values.append(value)
    if len(values) > 1 and values[0].sub(values[-1]).Length <= tolerance:
        values.pop()

    changed = True
    while changed and len(values) > 3:
        changed = False
        for index, value in enumerate(values):
            incoming = value.sub(values[index - 1])
            outgoing = values[(index + 1) % len(values)].sub(value)
            scale = max(1.0, incoming.Length * outgoing.Length)
            if incoming.cross(outgoing).Length <= tolerance * scale and incoming.dot(
                outgoing
            ) >= 0:
                values.pop(index)
                changed = True
                break
    return values


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


def _compilation(shape, recipe, axis, tolerance):
    roles = _classify_faces(shape, recipe, axis, tolerance)
    faces_by_index = {
        index: face for index, face in enumerate(shape.Faces, start=1)
    }
    horizontal_roles = {"Top", "Bottom", "OpeningSill", "OpeningHead"}
    vertical_area = sum(
        faces_by_index[item.face_index].Area
        for item in roles
        if item.role not in horizontal_roles
    )
    top_faces = tuple(
        faces_by_index[item.face_index] for item in roles if item.role == "Top"
    )
    if len(top_faces) != 1:
        return None
    top_face = top_faces[0]
    return WallExactCompilation(
        shape=shape,
        recipe=recipe,
        face_roles=roles,
        vertical_area=vertical_area,
        horizontal_area=top_face.Area,
        perimeter_length=top_face.OuterWire.Length,
    )
