# SPDX-License-Identifier: LGPL-2.1-or-later

"""Renderer-neutral geometry preparation for architectural planar views."""

from dataclasses import dataclass

import ArchCommands
import Draft


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
