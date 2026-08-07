"""Exercise live source mutations used by the render-ready cache keys.

This is intentionally a short GUI smoke test rather than a frame-time
benchmark. It mutates the source material, geometry, normals, and indexed
topology while rendering between each mutation. Coin node generations are
checked so a cache implementation cannot rely only on stable allocations.
The generated report records the mutation sequence and the observed cache
state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from common import get_diffuse_colors, is_benchmark_info, object_is_visible, require_gui


ASYMMETRIC_RGBA = (0x12 / 255.0, 0x48 / 255.0, 0xA7 / 255.0, 1.0)


def _type_name(node: Any) -> str:
    try:
        return node.getTypeId().getName().getString()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return type(node).__name__


def _walk(node: Any):
    yield node
    try:
        children = node.getNumChildren()
    except (AttributeError, RuntimeError, TypeError):
        return
    for index in range(children):
        yield from _walk(node.getChild(index))


def _find(root: Any, type_name: str) -> list[Any]:
    return [node for node in _walk(root) if _type_name(node) == type_name]


def _node_id(node: Any) -> int | None:
    try:
        return int(node.getNodeId())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _redraw(view: Any) -> None:
    view.redraw()
    Gui.updateGui()


def _visible_shape_object(doc: Any) -> Any:
    for obj in doc.Objects:
        if is_benchmark_info(obj) or not object_is_visible(obj):
            continue
        try:
            if obj.Shape is not None and not obj.Shape.isNull():
                return obj
        except (AttributeError, RuntimeError):
            continue
    raise RuntimeError("fixture has no visible shape object")


def _set_field_value(field: Any, index: int, value: Any) -> None:
    try:
        field.set1Value(index, value)
    except (AttributeError, RuntimeError, TypeError):
        field[index] = value


def _field_value(field: Any, index: int) -> Any:
    try:
        return field[index]
    except (AttributeError, RuntimeError, TypeError, IndexError):
        return field.getValues(index, 1)[0]


def run(path: str) -> dict[str, Any]:
    doc = None
    operations: list[dict[str, Any]] = []
    try:
        from pivy import coin

        doc = App.openDocument(str(Path(path).expanduser().resolve()))
        doc.recompute()
        gui_doc = Gui.activeDocument()
        if gui_doc is None:
            raise RuntimeError("fixture did not create an active GUI document")
        view = gui_doc.activeView()
        obj = _visible_shape_object(doc)
        root = obj.ViewObject.RootNode

        _redraw(view)

        materials = _find(root, "SoMaterial") + _find(root, "SoPackedColor")
        material_id_before = _node_id(materials[0]) if materials else None
        colors = get_diffuse_colors(obj)
        if not colors:
            raise RuntimeError("fixture target has no face colors")
        changed_colors = list(colors)
        changed_colors[0] = ASYMMETRIC_RGBA
        obj.ViewObject.DiffuseColor = changed_colors
        doc.recompute()
        _redraw(view)
        applied_colors = get_diffuse_colors(obj)
        material_nodes_after = _find(obj.ViewObject.RootNode, "SoMaterial")
        material_nodes_after += _find(obj.ViewObject.RootNode, "SoPackedColor")
        material_id_after = _node_id(material_nodes_after[0]) if material_nodes_after else None
        operations.append(
            {
                "name": "asymmetric_face_color",
                "expected_rgba": [0x12, 0x48, 0xA7, 0xFF],
                "source_generation_changed": (
                    material_id_before != material_id_after
                    if material_id_before is not None and material_id_after is not None
                    else None
                ),
                "color_applied": bool(
                    applied_colors
                    and all(
                        abs(actual - expected) < 1.0e-6
                        for actual, expected in zip(applied_colors[0], ASYMMETRIC_RGBA)
                    )
                ),
                "rendered_after_mutation": True,
            }
        )
        obj.ViewObject.DiffuseColor = colors
        doc.recompute()
        _redraw(view)

        face_sets = _find(obj.ViewObject.RootNode, "SoBrepFaceSet")
        if not face_sets:
            raise RuntimeError("fixture scene graph has no SoBrepFaceSet node")
        shape = obj.Shape.copy()
        coordinate_id_before = _node_id(face_sets[0])
        shape.translate(App.Vector(0.01, 0.0, 0.0))
        obj.Shape = shape
        doc.recompute()
        _redraw(view)
        coordinate_nodes_after = _find(obj.ViewObject.RootNode, "SoBrepFaceSet")
        coordinate_id_after = _node_id(coordinate_nodes_after[0]) if coordinate_nodes_after else None
        operations.append(
            {
                "name": "coordinate_geometry",
                "source_generation_changed": coordinate_id_before != coordinate_id_after,
                "rendered_after_mutation": True,
            }
        )

        # Changing angular deflection forces a fresh tessellation and normal
        # source even though the BRep object remains the same.
        normal_id_before = _node_id(_find(obj.ViewObject.RootNode, "SoBrepFaceSet")[0])
        original_deflection = float(obj.ViewObject.AngularDeflection)
        obj.ViewObject.AngularDeflection = max(0.1, original_deflection * 0.5)
        doc.recompute()
        _redraw(view)
        normal_nodes_after = _find(obj.ViewObject.RootNode, "SoBrepFaceSet")
        normal_id_after = _node_id(normal_nodes_after[0]) if normal_nodes_after else None
        operations.append(
            {
                "name": "normal_data",
                "source_generation_changed": normal_id_before != normal_id_after,
                "rendered_after_mutation": True,
            }
        )
        obj.ViewObject.AngularDeflection = original_deflection
        doc.recompute()
        _redraw(view)

        face_sets = _find(obj.ViewObject.RootNode, "SoBrepFaceSet")
        if not face_sets:
            raise RuntimeError("fixture scene graph has no SoBrepFaceSet node")
        face_set = face_sets[0]
        coord_index_id_before = _node_id(face_set)
        coord_index = face_set.coordIndex
        index_count = int(coord_index.getNum())
        if index_count < 3:
            raise RuntimeError("fixture has too few coordinate indices")
        first = _field_value(coord_index, 0)
        second = _field_value(coord_index, 1)
        _set_field_value(coord_index, 0, second)
        _set_field_value(coord_index, 1, first)
        _redraw(view)
        coord_index_id_after = _node_id(_find(obj.ViewObject.RootNode, "SoBrepFaceSet")[0])
        operations.append(
            {
                "name": "indexed_topology",
                "source_generation_changed": coord_index_id_before != coord_index_id_after,
            }
        )
        _set_field_value(coord_index, 0, first)
        _set_field_value(coord_index, 1, second)
        _redraw(view)

        # A custom attribute changes the vertex domain. The render-ready path
        # must decline it rather than associating the original attribute array
        # with expanded face corners.
        custom_attribute_added = False
        custom_attribute_error = None
        try:
            attribute = coin.SoVertexAttribute()
            attribute.name = "renderingMutationAttribute"
            attribute.typeName = "SoMFFloat"
            shader_program = coin.SoShaderProgram()
            vertex_shader = coin.SoVertexShader()
            vertex_shader.sourceType = coin.SoShaderObject.GLSL_PROGRAM
            vertex_shader.sourceProgram = "void main() { gl_Position = ftransform(); }"
            shader_program.shaderObject.set1Value(0, vertex_shader)
            root = obj.ViewObject.RootNode
            root.insertChild(shader_program, 0)
            root.insertChild(attribute, 1)
            custom_attribute_added = True
            _redraw(view)
            root.removeChild(attribute)
            root.removeChild(shader_program)
            _redraw(view)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            # Older Pivy builds may not expose SoVertexAttribute construction;
            # report the limitation rather than hiding the other mutations.
            custom_attribute_error = str(exc)

        operations.append(
            {
                "name": "custom_vertex_attribute_guard",
                "exercised": custom_attribute_added,
                "error": custom_attribute_error,
            }
        )

        failed = [
            op["name"]
            for op in operations
            if op.get("source_generation_changed") is False or op.get("color_applied") is False
        ]
        return {
            "file": str(Path(path).expanduser().resolve()),
            "target": obj.Name,
            "operations": operations,
            "failed_generation_checks": failed,
            "custom_attribute_guard_exercised": custom_attribute_added,
            "valid": not failed,
        }
    finally:
        if doc is not None:
            App.closeDocument(doc.Name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="canonical FCStd fixture")
    parser.add_argument("--stats", help="write the mutation report JSON")
    args = parser.parse_args(argv)
    require_gui()
    report = run(args.input)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.stats:
        output = Path(args.stats).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
