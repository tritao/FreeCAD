# SPDX-License-Identifier: LGPL-2.1-or-later

"""Renderer-neutral geometry preparation for architectural planar views."""

from dataclasses import dataclass

import ArchCommands
import ArchRepresentation
import Draft
import FreeCAD


@dataclass(frozen=True)
class ProjectedViewGeometry:
    """Shapes split relative to one architectural view plane.

    ``visible_shapes`` are on the plane-normal side retained by the classic
    section renderer. ``hidden_shapes`` are on the opposite side when hidden
    geometry was requested. ``cut_shapes`` are faces on the plane itself.
    """

    visible_shapes: tuple
    hidden_shapes: tuple
    cut_shapes: tuple
    cut_face: object
    visible_volume: object
    hidden_volume: object
    object_cut_shapes: tuple = ()

    def legacy_tuple(self, group_cut_shapes_by_object=False):
        values = (
            list(self.visible_shapes),
            list(self.hidden_shapes),
            list(self.cut_shapes),
            self.cut_face,
            self.visible_volume,
            self.hidden_volume,
        )
        if group_cut_shapes_by_object:
            return (*values, list(self.object_cut_shapes))
        return values


@dataclass(frozen=True)
class _ElevationScopeProjection:
    """Cached OCC result from one scope-wide elevation projection."""

    sources: tuple


@dataclass(frozen=True)
class _ProjectedEdge:
    shape: object
    category: ArchRepresentation.ProjectedLineCategory


def project_shapes(
    objects,
    cut_plane,
    *,
    only_solids=True,
    clip=False,
    join_arch=False,
    include_hidden=False,
    group_cut_shapes_by_object=False,
):
    """Split object shapes using the established SectionPlane algorithm."""

    shapes = []
    hidden_shapes = []
    cut_shapes = []
    object_shapes = []
    object_cut_shapes = []

    if join_arch:
        shape_types = {}
        for obj in objects:
            if Draft.getType(obj) in ("Wall", "Structure"):
                if obj.Shape.isNull():
                    continue
                key = obj.Material.Name if getattr(obj, "Material", None) else "None"
                if only_solids:
                    shape_types.setdefault(key, []).extend(obj.Shape.Solids)
                else:
                    shape_types.setdefault(key, []).append(obj.Shape.copy())
            elif hasattr(obj, "Shape") and not obj.Shape.isNull():
                obj_shapes = obj.Shape.Solids if only_solids else [obj.Shape.copy()]
                shapes.extend(obj_shapes)
                object_shapes.append((obj, obj_shapes))
        for key, grouped_shapes in shape_types.items():
            fused = grouped_shapes.pop()
            if grouped_shapes:
                fused = fused.multiFuse(grouped_shapes).removeSplitter()
            if fused.Solids:
                shapes.extend(fused.Solids)
                object_shapes.append((key, fused.Solids))
            else:
                print("ArchSectionPlane: Fusing BIM objects produced non-solid results")
                shapes.append(fused)
                object_shapes.append((key, [fused]))
    else:
        for obj in objects:
            if not hasattr(obj, "Shape") or obj.Shape.isNull():
                continue
            if only_solids:
                if not obj.Shape.isValid():
                    continue
                obj_shapes = obj.Shape.Solids
            else:
                obj_shapes = [obj.Shape]
            shapes.extend(obj_shapes)
            object_shapes.append((obj, obj_shapes))

    cut_face, visible_volume, hidden_volume = ArchCommands.getCutVolume(
        cut_plane, shapes, clip
    )
    visible_shapes = []
    for source, source_shapes in object_shapes:
        source_cut_shapes = []
        layer_materials = None
        if (
            group_cut_shapes_by_object
            and not isinstance(source, str)
            and getattr(source, "Material", None)
            and getattr(source.Material, "Materials", None)
            and hasattr(source.Material, "Thicknesses")
        ):
            layer_materials = [
                source.Material.Materials[index]
                for index in range(len(source.Material.Materials))
                if source.Material.Thicknesses[index] >= 0
            ]
            if len(layer_materials) != len(source_shapes):
                layer_materials = None
        per_layer = [[] for _shape in source_shapes] if layer_materials else None

        for shape_index, shape in enumerate(source_shapes):
            subshapes = shape.SubShapes if shape.ShapeType == "Compound" else [shape]
            for subshape in subshapes:
                if not visible_volume:
                    visible_shapes.append(subshape)
                    continue
                if subshape.Volume < 0:
                    subshape = subshape.reversed()
                visible = subshape.cut(visible_volume)
                section = subshape.common(cut_face)
                source_cut_shapes.extend(section.Faces)
                if per_layer is not None:
                    per_layer[shape_index].extend(section.Faces)
                visible_shapes.extend(
                    visible.SubShapes if visible.ShapeType == "Compound" else [visible]
                )
                if include_hidden:
                    hidden = subshape.cut(hidden_volume)
                    hidden_shapes.extend(
                        hidden.SubShapes if hidden.ShapeType == "Compound" else [hidden]
                    )

        if source_cut_shapes:
            cut_shapes.extend(source_cut_shapes)
            if group_cut_shapes_by_object:
                if per_layer and layer_materials:
                    object_cut_shapes.extend(
                        (material, faces)
                        for material, faces in zip(layer_materials, per_layer)
                        if faces
                    )
                else:
                    object_cut_shapes.append((source, source_cut_shapes))

    return ProjectedViewGeometry(
        tuple(visible_shapes),
        tuple(hidden_shapes),
        tuple(cut_shapes),
        cut_face,
        visible_volume,
        hidden_volume,
        tuple(object_cut_shapes),
    )


def _validate_elevation_request(request):
    if getattr(request, "purpose", None) != ArchRepresentation.RepresentationPurpose.ELEVATION:
        raise ValueError("An Elevation representation request is required")
    frame = getattr(request, "reference_frame", None)
    if frame is None:
        raise ArchRepresentation.RepresentationUnavailable(
            "Elevation projection requires a reference frame"
        )
    return frame


def _local_elevation_shape(obj, request):
    frame = _validate_elevation_request(request)
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        raise ArchRepresentation.RepresentationUnavailable(
            "Elevation projection requires a shape"
        )

    local_shape = shape.copy()
    local_shape.Placement = frame.inverse().multiply(local_shape.Placement)
    projection_range = getattr(request, "projection_range", None)
    if projection_range and any(float(value) for value in projection_range):
        range_min, range_max = sorted(float(value) for value in projection_range)
        bounds = local_shape.BoundBox
        if bounds.ZMax < range_min or bounds.ZMin > range_max:
            return None
        if bounds.ZMin < range_min or bounds.ZMax > range_max:
            import Part

            margin = max(bounds.DiagonalLength * 0.01, 1.0)
            clip = Part.makeBox(
                max(bounds.XLength + 2.0 * margin, margin),
                max(bounds.YLength + 2.0 * margin, margin),
                max(range_max - range_min, 1e-7),
                FreeCAD.Vector(bounds.XMin - margin, bounds.YMin - margin, range_min),
            )
            unclipped_shape = local_shape
            local_shape = local_shape.common(clip)
            if local_shape.isNull():
                return None
            if not local_shape.BoundBox.isValid():
                local_shape = unclipped_shape
    return local_shape


def _project_visible_edges(local_shape):
    if local_shape is None or local_shape.isNull():
        return ()

    import TechDraw

    try:
        groups = TechDraw.projectEx(local_shape, FreeCAD.Vector(0, 0, 1))
    except Exception as error:
        raise ArchRepresentation.RepresentationUnavailable(
            "TechDraw could not project this object's shape"
        ) from error
    categories = (
        ArchRepresentation.ProjectedLineCategory.VISIBLE_HARD,
        ArchRepresentation.ProjectedLineCategory.VISIBLE_SMOOTH,
        ArchRepresentation.ProjectedLineCategory.VISIBLE_SEAM,
        ArchRepresentation.ProjectedLineCategory.SILHOUETTE,
        ArchRepresentation.ProjectedLineCategory.VISIBLE_ISO,
    )
    projected = []
    for group, category in zip(groups[:5], categories):
        edges = list(getattr(group, "Edges", ()))
        if edges:
            edges = TechDraw.scrubEdges(edges)
        projected.extend(_ProjectedEdge(edge, category) for edge in edges)
    return tuple(projected)


def _representation_from_edges(obj, request, local_shape, edges, deflection=None):
    frame = _validate_elevation_request(request)

    representation = ArchRepresentation.ViewportRepresentation(source=obj, request=request)
    if local_shape is None:
        return representation
    target_offset = float(getattr(request, "target_offset", 0.0) or 0.0)
    if deflection is None:
        diagonal = max(local_shape.BoundBox.DiagonalLength, 1.0)
        deflection = max(0.1, min(5.0, diagonal / 1000.0))
    for index, projected_edge in enumerate(edges, start=1):
        edge = projected_edge.shape
        try:
            points = edge.discretize(Deflection=float(deflection))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            points = [vertex.Point for vertex in edge.Vertexes]
        if len(points) < 2:
            continue
        projected = tuple(
            frame.multVec(FreeCAD.Vector(point.x, point.y, target_offset))
            for point in points
        )
        representation.add_geometry(
            "projected_geometry",
            projected,
            projected_edge.category.value,
            subelement="ElevationEdge{}".format(index),
        )
    return representation


def project_elevation_object(obj, request, *, deflection=None):
    """Return a viewport-ready 2D projection of one object on an elevation."""

    local_shape = _local_elevation_shape(obj, request)
    return _representation_from_edges(
        obj,
        request,
        local_shape,
        _project_visible_edges(local_shape),
        deflection=deflection,
    )


def project_elevation_scope(objects, request, *, deflection=None):
    """Project one elevation scope with global hidden-line removal.

    The scope is projected as one compound so nearer objects suppress geometry
    behind them. Surviving edges are then associated with the nearest source
    whose independent projection contains that edge, preserving semantic BIM
    identity for viewport picking and contextual editing.
    """

    _validate_elevation_request(request)
    objects = tuple(objects)
    representations = {
        obj: ArchRepresentation.ViewportRepresentation(source=obj, request=request)
        for obj in objects
    }

    document = next(
        (getattr(obj, "Document", None) for obj in objects if getattr(obj, "Document", None)),
        None,
    )
    from bimviews import representation_cache

    cache_key = (
        representation_cache.representation_request_key(request),
        tuple(getattr(obj, "Name", None) or id(obj) for obj in objects),
    )

    def compute_scope():
        return _compute_elevation_scope_projection(objects, request)

    projection = representation_cache.get_or_create_derived_value(
        document,
        "elevation-scope",
        cache_key,
        compute_scope,
    )
    for obj, shape, edges in projection.sources:
        representations[obj] = _representation_from_edges(
            obj,
            request,
            shape,
            edges,
            deflection=deflection,
        )
    return representations


def _compute_elevation_scope_projection(objects, request):
    local_shapes = []
    for obj in objects:
        try:
            shape = _local_elevation_shape(obj, request)
        except ArchRepresentation.RepresentationUnavailable:
            shape = None
        if shape is not None and not shape.isNull() and shape.BoundBox.isValid():
            local_shapes.append((obj, shape))
    if not local_shapes:
        return _ElevationScopeProjection(())

    import Part

    scope_edges = _project_visible_edges(
        Part.makeCompound([shape for _obj, shape in local_shapes])
    )
    source_edges = {
        obj: _project_visible_edges(shape) for obj, shape in local_shapes
    }
    diagonal = max(
        (shape.BoundBox.DiagonalLength for _obj, shape in local_shapes), default=1.0
    )
    tolerance = max(diagonal * 1e-7, 1e-5)
    assigned = {obj: [] for obj, _shape in local_shapes}
    for edge in scope_edges:
        candidates = []
        for obj, shape in local_shapes:
            if any(
                edge.shape.distToShape(candidate.shape)[0] <= tolerance
                for candidate in source_edges[obj]
            ):
                candidates.append((shape.BoundBox.ZMax, obj))
        if candidates:
            assigned[max(candidates, key=lambda item: item[0])[1]].append(edge)

    return _ElevationScopeProjection(
        tuple((obj, shape, tuple(assigned[obj])) for obj, shape in local_shapes)
    )
