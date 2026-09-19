# SPDX-License-Identifier: LGPL-2.1-or-later

"""Analytic architectural models used to derive inexpensive Plan geometry."""

from dataclasses import dataclass, replace

import ArchWallGeometry
import FreeCAD


@dataclass(frozen=True)
class AnalyticWallPlan:
    """A straight wall footprint expressed without inspecting its final solid."""

    source: object
    recipe: object
    target_z: float
    opening_intervals: tuple = ()

    @property
    def boundary(self):
        return self.boundaries[0] if self.boundaries else ()

    @property
    def boundaries(self):
        return self.recipe.plan_boundaries(self.target_z, self.opening_intervals)

    def make_faces(self):
        """Materialize analytic regions as lightweight planar faces."""

        import Part

        faces = []
        for boundary in self.boundaries:
            if len(boundary) < 3:
                continue
            try:
                faces.append(Part.Face(Part.makePolygon((*boundary, boundary[0]))))
            except Part.OCCError:
                # Invalid edit previews may collapse a clipped region to a
                # point or line.  Such a region contributes no Plan face.
                continue
        return tuple(faces)

    @property
    def face_meshes(self):
        """Return direct convex polygon meshes for Plan rendering and picking."""

        return tuple(
            (
                boundary,
                tuple((0, index, index + 1) for index in range(1, len(boundary) - 1)),
            )
            for boundary in self.boundaries
            if len(boundary) >= 3
        )

    def make_face(self):
        """Materialize the analytic boundary as a lightweight planar face."""

        import Part

        faces = self.make_faces()
        return faces[0] if faces else Part.Face()


def straight_wall_plan_model(wall, proxy, request, opening_overrides=None):
    """Return an analytic model when a wall needs no BRep-derived Plan result."""

    if getattr(request, "cut_offset", None) is None:
        return None
    frame = getattr(request, "reference_frame", None)
    if frame is not None:
        frame_normal = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        if abs(abs(frame_normal.z) - 1.0) > 1e-7:
            return None
    recipe = straight_wall_geometry_recipe(
        wall, proxy, opening_overrides=opening_overrides
    )
    if recipe is None:
        return None
    cut_z = float(request.cut_offset)
    if frame is not None:
        cut_z = frame.multVec(FreeCAD.Vector(0, 0, cut_z)).z
    if cut_z < recipe.z_min - 1e-7 or cut_z > recipe.z_max + 1e-7:
        return None
    target_z = request.target_offset
    if target_z is None:
        target_z = recipe.z_min
    elif frame is not None:
        target_z = frame.multVec(FreeCAD.Vector(0, 0, float(target_z))).z
    return AnalyticWallPlan(
        source=wall,
        recipe=recipe,
        target_z=float(target_z),
        opening_intervals=recipe.opening_intervals_at(cut_z),
    )


def straight_wall_geometry_recipe(
    wall, proxy, geometry_shape=None, opening_overrides=None
):
    """Resolve the shared geometry recipe for one supported straight wall."""

    if _has_manual_end_treatment(wall) or not _has_straight_path(wall):
        return None
    baseline = proxy.get_global_baseline(wall)
    section = proxy.get_resolved_section(wall)
    if baseline is None or section is None:
        return None
    axis = FreeCAD.Vector(baseline.end_point).sub(FreeCAD.Vector(baseline.start_point))
    if axis.Length <= 1e-9:
        return None
    axis.normalize()
    normal = FreeCAD.Vector(baseline.normal)
    if normal.z < 0:
        normal = normal.negative()
    lateral = axis.cross(normal)
    if lateral.Length <= 1e-9:
        return None
    lateral.normalize()

    shape = geometry_shape or getattr(wall, "Shape", None)
    if not shape or shape.isNull():
        return None
    bounds = shape.BoundBox
    section_center = (float(section.y_min) + float(section.y_max)) * 0.5
    if abs(section_center) > 1e-7:
        baseline_midpoint = FreeCAD.Vector(baseline.start_point).add(
            FreeCAD.Vector(baseline.end_point)
        ) * 0.5
        shape_center = FreeCAD.Vector(bounds.Center)
        if shape_center.sub(baseline_midpoint).dot(lateral) * section_center < 0:
            lateral = lateral.negative()
    trim_planes = _wall_trim_planes(wall)
    if trim_planes is None:
        return None
    recipe = ArchWallGeometry.WallGeometryRecipe(
        axis_start=baseline.start_point,
        axis_end=baseline.end_point,
        lateral=lateral,
        section=section,
        z_min=bounds.ZMin,
        z_max=bounds.ZMax,
        trim_planes=trim_planes,
    )
    openings = _hosted_opening_recipes(wall, recipe, opening_overrides)
    return None if openings is None else replace(recipe, openings=openings)


def _wall_trim_planes(wall):
    import ArchWallRelation
    from bimviews import representation_cache

    trim_planes = []
    for relation in ArchWallRelation.iter_wall_relations(wall):
        if not getattr(relation, "Enabled", True):
            continue
        if not ArchWallRelation.is_wall_joint(relation):
            return None
        solution = representation_cache.get_or_create_derived_value(
            getattr(relation, "Document", None),
            "wall-joint-solution",
            getattr(relation, "Name", id(relation)),
            lambda relation=relation: ArchWallRelation.solve_wall_joint(relation),
        )
        if not solution.is_ok():
            return None
        claim = solution.trim_for_wall(wall)
        if claim is not None:
            trim_planes.append(
                ArchWallGeometry.WallTrimPlane(
                    end_name=claim.end_name,
                    origin=claim.plane.Base,
                    normal=claim.plane.Rotation.multVec(FreeCAD.Vector(0, 0, 1)),
                    extension=claim.extension,
                )
            )
    return tuple(trim_planes)


def _hosted_opening_recipes(wall, recipe, opening_overrides=None):
    from bimviews import representation_cache

    document = getattr(wall, "Document", None)
    openings = []
    opening_overrides = opening_overrides or {}
    for obj in (getattr(document, "Objects", ()) or ()):
        if wall not in (getattr(obj, "Hosts", None) or ()):
            continue
        if obj in opening_overrides:
            opening = opening_overrides[obj]
            if opening is None:
                return None
            openings.append(opening)
            continue
        provider = getattr(
            getattr(obj, "Proxy", None), "get_hosted_opening_geometry_recipe", None
        )
        if not callable(provider):
            return None
        opening = representation_cache.get_or_create_derived_value(
            document,
            "hosted-opening-recipe",
            (getattr(obj, "Name", id(obj)), getattr(wall, "Name", id(wall))),
            lambda provider=provider, recipe=recipe: provider(recipe),
        )
        if opening is None:
            return None
        openings.append(opening)
    return tuple(openings)


def _has_manual_end_treatment(wall):
    import ArchWallEndCondition

    return any(
        not ArchWallEndCondition.is_null_placement(placement)
        for placement in (
            getattr(wall, "EndingStart", FreeCAD.Placement()),
            getattr(wall, "EndingEnd", FreeCAD.Placement()),
        )
    )


def _has_straight_path(wall):
    base = getattr(wall, "Base", None)
    shape = getattr(base, "Shape", None) if base is not None else None
    if not shape:
        return True
    edges = tuple(getattr(shape, "Edges", ()) or ())
    if len(edges) != 1:
        return False
    curve_name = type(getattr(edges[0], "Curve", None)).__name__
    return curve_name in {"Line", "LineSegment"}
