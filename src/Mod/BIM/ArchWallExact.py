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
    """Extrude one perforated wall-local profile, or return ``None``.

    This first exact compiler intentionally accepts only horizontal, straight,
    single-layer walls without end trims. Openings must be disjoint rectangles
    fully contained by the wall and span its complete lateral thickness.
    """

    if recipe is None or recipe.trim_planes:
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

    openings = tuple(recipe.openings)
    for opening in openings:
        if (
            opening.u_min <= tolerance
            or opening.u_max >= length - tolerance
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
        elif abs(u) <= tolerance:
            role = "EndStart"
        elif abs(u - recipe.axis_end.sub(recipe.axis_start).Length) <= tolerance:
            role = "EndEnd"
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
        roles.append(WallExactFaceRole(index, role, source))
    return tuple(roles)
