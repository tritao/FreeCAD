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
    trim_claims: tuple = ()
    opening_intervals: tuple = ()

    @property
    def boundary(self):
        return self.boundaries[0] if self.boundaries else ()

    @property
    def boundaries(self):
        start = FreeCAD.Vector(self.axis_start)
        end = FreeCAD.Vector(self.axis_end)
        axis = end.sub(start)
        axis.normalize()
        for claim in self.trim_claims:
            if claim.end_name == "Start":
                start = start.sub(axis * float(claim.extension))
            else:
                end = end.add(axis * float(claim.extension))
        lateral = FreeCAD.Vector(self.lateral)
        polygon = [
            start.add(lateral * self.y_min),
            end.add(lateral * self.y_min),
            end.add(lateral * self.y_max),
            start.add(lateral * self.y_max),
        ]
        for claim in self.trim_claims:
            reference = end if claim.end_name == "Start" else start
            normal = claim.plane.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
            keep_sign = 1.0 if reference.sub(claim.plane.Base).dot(normal) >= 0 else -1.0
            polygon = _clip_polygon(
                polygon,
                lambda point, origin=claim.plane.Base, direction=normal, sign=keep_sign: (
                    point.sub(origin).dot(direction) * sign
                ),
            )

        polygons = [polygon] if len(polygon) >= 3 else []
        origin = FreeCAD.Vector(self.axis_start)
        for lower, upper in self.opening_intervals:
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

        result = []
        for points in polygons:
            boundary = []
            for point in points:
                point = FreeCAD.Vector(point)
                point.z = self.target_z
                boundary.append(point)
            result.append(tuple(boundary))
        return tuple(result)

    def make_faces(self):
        """Materialize analytic regions as lightweight planar faces."""

        import Part

        return tuple(
            Part.Face(Part.makePolygon((*boundary, boundary[0])))
            for boundary in self.boundaries
        )

    def make_face(self):
        """Materialize the analytic boundary as a lightweight planar face."""

        import Part

        faces = self.make_faces()
        return faces[0] if faces else Part.Face()


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


def straight_wall_plan_model(wall, proxy, request):
    """Return an analytic model when a wall needs no BRep-derived Plan result."""

    if getattr(request, "cut_offset", None) is None:
        return None
    frame = getattr(request, "reference_frame", None)
    if frame is not None:
        frame_normal = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        if abs(abs(frame_normal.z) - 1.0) > 1e-7:
            return None
    if _has_manual_end_treatment(wall):
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
    if normal.z < 0:
        normal = normal.negative()
    lateral = axis.cross(normal)
    if lateral.Length <= 1e-9:
        return None
    lateral.normalize()

    shape = getattr(wall, "Shape", None)
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
    cut_z = float(request.cut_offset)
    if frame is not None:
        cut_z = frame.multVec(FreeCAD.Vector(0, 0, cut_z)).z
    if cut_z < bounds.ZMin - 1e-7 or cut_z > bounds.ZMax + 1e-7:
        return None
    target_z = request.target_offset
    if target_z is None:
        target_z = bounds.ZMin
    elif frame is not None:
        target_z = frame.multVec(FreeCAD.Vector(0, 0, float(target_z))).z
    trim_claims = _wall_trim_claims(wall)
    if trim_claims is None:
        return None
    opening_request = request
    if frame is not None:
        import ArchRepresentation

        opening_request = ArchRepresentation.RepresentationRequest(
            purpose=request.purpose,
            cut_offset=cut_z,
            target_offset=float(target_z),
            source=getattr(request, "source", None),
        )
    opening_intervals = _hosted_opening_intervals(wall, opening_request, baseline)
    if opening_intervals is None:
        return None
    return AnalyticWallPlan(
        source=wall,
        axis_start=FreeCAD.Vector(baseline.start_point),
        axis_end=FreeCAD.Vector(baseline.end_point),
        lateral=lateral,
        y_min=float(section.y_min),
        y_max=float(section.y_max),
        target_z=float(target_z),
        trim_claims=trim_claims,
        opening_intervals=opening_intervals,
    )


def _wall_trim_claims(wall):
    import ArchWallRelation
    from bimviews import representation_cache

    claims = []
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
            claims.append(claim)
    return tuple(claims)


def _hosted_opening_intervals(wall, request, baseline):
    document = getattr(wall, "Document", None)
    origin = FreeCAD.Vector(baseline.start_point)
    axis = FreeCAD.Vector(baseline.end_point).sub(origin)
    axis.normalize()
    intervals = []
    for obj in (getattr(document, "Objects", ()) or ()):
        if wall not in (getattr(obj, "Hosts", None) or ()):
            continue
        shape = getattr(obj, "Shape", None)
        cut_z = float(request.cut_offset)
        if shape and not shape.isNull() and (
            cut_z < shape.BoundBox.ZMin - 1e-7 or cut_z > shape.BoundBox.ZMax + 1e-7
        ):
            continue
        provider = getattr(getattr(obj, "Proxy", None), "get_plan_overlay_geometry", None)
        if not callable(provider):
            return None
        geometry = provider(request)
        jambs = tuple(geometry.get("jamb_polylines", ()) or ())
        points = [FreeCAD.Vector(point) for polyline in jambs for point in polyline]
        if not points:
            return None
        values = [point.sub(origin).dot(axis) for point in points]
        intervals.append((min(values), max(values)))
    return _merge_intervals(intervals)


def _merge_intervals(intervals, tolerance=1e-7):
    """Return ordered, non-overlapping intervals."""

    merged = []
    for lower, upper in sorted(intervals):
        if merged and lower <= merged[-1][1] + tolerance:
            merged[-1] = (merged[-1][0], max(merged[-1][1], upper))
        else:
            merged.append((lower, upper))
    return tuple(merged)


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
