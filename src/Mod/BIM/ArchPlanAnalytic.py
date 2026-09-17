# SPDX-License-Identifier: LGPL-2.1-or-later

"""Analytic architectural models used to derive inexpensive Plan geometry."""

from dataclasses import dataclass

import FreeCAD


@dataclass(frozen=True)
class AnalyticWallPlan:
    """A straight wall footprint expressed without inspecting its final solid."""

    source: object
    axis_start: object
    axis_end: object
    lateral: object
    y_min: float
    y_max: float
    target_z: float

    @property
    def boundary(self):
        start = FreeCAD.Vector(self.axis_start)
        end = FreeCAD.Vector(self.axis_end)
        lateral = FreeCAD.Vector(self.lateral)
        points = (
            start.add(lateral * self.y_min),
            end.add(lateral * self.y_min),
            end.add(lateral * self.y_max),
            start.add(lateral * self.y_max),
        )
        result = []
        for point in points:
            point.z = self.target_z
            result.append(point)
        return tuple(result)

    def make_face(self):
        """Materialize the analytic boundary as a lightweight planar face."""

        import Part

        boundary = self.boundary
        return Part.Face(Part.makePolygon((*boundary, boundary[0])))


def straight_wall_plan_model(wall, proxy, request):
    """Return an analytic model when a wall needs no BRep-derived Plan result."""

    if getattr(request, "reference_frame", None) is not None:
        return None
    if getattr(request, "cut_offset", None) is None:
        return None
    if proxy.requires_brep_export(wall):
        return None
    if _has_enabled_wall_relation(wall) or _has_hosted_opening(wall):
        return None
    if not _has_straight_path(wall):
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
    lateral = axis.cross(normal)
    if lateral.Length <= 1e-9:
        return None
    lateral.normalize()

    shape = getattr(wall, "Shape", None)
    if not shape or shape.isNull():
        return None
    bounds = shape.BoundBox
    cut_z = float(request.cut_offset)
    if cut_z < bounds.ZMin - 1e-7 or cut_z > bounds.ZMax + 1e-7:
        return None
    target_z = request.target_offset
    if target_z is None:
        target_z = bounds.ZMin
    return AnalyticWallPlan(
        source=wall,
        axis_start=FreeCAD.Vector(baseline.start_point),
        axis_end=FreeCAD.Vector(baseline.end_point),
        lateral=lateral,
        y_min=float(section.y_min),
        y_max=float(section.y_max),
        target_z=float(target_z),
    )


def _has_enabled_wall_relation(wall):
    import ArchWallRelation

    return any(
        getattr(relation, "Enabled", True)
        for relation in ArchWallRelation.iter_wall_joints(wall)
    )


def _has_hosted_opening(wall):
    document = getattr(wall, "Document", None)
    return any(
        wall in (getattr(obj, "Hosts", None) or ())
        for obj in (getattr(document, "Objects", ()) or ())
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
