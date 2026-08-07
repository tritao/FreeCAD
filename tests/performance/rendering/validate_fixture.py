"""Validate a generated FCStd fixture after save/reopen.

Basic topology, object-count, material-array, display-mode, and visibility
checks work in ``FreeCADCmd``.  Add ``--scene-graph`` in a GUI-capable build
to inspect the Coin nodes produced by the view providers as well.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import FreeCAD as App

from common import (
    get_diffuse_colors,
    is_benchmark_info,
    load_expected,
    object_is_visible,
    parse_display_mode,
    shape_counts,
    shape_for_object,
    validate_expected,
    require_gui,
)


def validate_file(path: str, *, inspect_scene_graph: bool, require_scene_graph: bool) -> dict[str, Any]:
    doc = None
    try:
        doc = App.openDocument(str(Path(path).expanduser().resolve()))
        doc.recompute()
        info = doc.getObject("BenchmarkInfo")
        expected = load_expected(doc)
        errors = validate_expected(doc, expected)
        errors.extend(_validate_view_properties(doc, info))

        scene_graph = None
        if inspect_scene_graph or require_scene_graph:
            scene_graph, scene_errors = _inspect_scene_graph(doc, expected)
            errors.extend(scene_errors)
            if require_scene_graph and not scene_graph.get("available", False):
                errors.append("Coin scene graph inspection was requested but unavailable")

        report = {
            "file": str(Path(path).expanduser().resolve()),
            "fixture": getattr(info, "FixtureName", None),
            "preset": getattr(info, "Preset", None),
            "seed": getattr(info, "Seed", None),
            "metadata": _metadata_report(info),
            "expected": expected,
            "errors": errors,
            "valid": not errors,
        }
        if scene_graph is not None:
            report["scene_graph"] = scene_graph
        return report
    finally:
        if doc is not None:
            App.closeDocument(doc.Name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="generated FCStd files")
    parser.add_argument("--json", dest="json_output", help="write a JSON report")
    parser.add_argument(
        "--scene-graph",
        action="store_true",
        help="inspect Coin material, binding, and indexed face-set nodes when available",
    )
    parser.add_argument(
        "--require-scene-graph",
        action="store_true",
        help="make unavailable Coin inspection a validation error",
    )
    args = parser.parse_args(argv)
    require_gui()

    reports = [
        validate_file(
            path,
            inspect_scene_graph=args.scene_graph,
            require_scene_graph=args.require_scene_graph,
        )
        for path in args.inputs
    ]
    payload: Any = reports[0] if len(reports) == 1 else {"fixtures": reports}
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        output = Path(args.json_output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if all(report["valid"] for report in reports) else 1


def _validate_view_properties(doc: Any, info: Any) -> list[str]:
    errors = []
    if info is None:
        return ["missing BenchmarkInfo object"]
    try:
        expected_display_mode = parse_display_mode(info.DisplayMode)
    except (AttributeError, ValueError):
        return ["BenchmarkInfo.DisplayMode is invalid"]

    for obj in doc.Objects:
        if is_benchmark_info(obj):
            continue
        try:
            actual_mode = obj.ViewObject.DisplayMode
        except (AttributeError, RuntimeError):
            errors.append(f"{obj.Name}: missing DisplayMode")
            continue
        if actual_mode != expected_display_mode:
            if getattr(obj, "TypeId", "") == "App::Link" and actual_mode in (
                "ChildView",
                "Link",
            ):
                continue
            errors.append(
                f"{obj.Name}.DisplayMode: expected {expected_display_mode!r}, got {actual_mode!r}"
            )
    return errors


def _metadata_report(info: Any) -> dict[str, Any]:
    if info is None:
        return {}
    names = (
        "FixtureType",
        "GeneratorVersion",
        "ObjectCount",
        "LinkCount",
        "FaceCount",
        "ExpectedColorCount",
    )
    return {name: getattr(info, name, None) for name in names}


def _inspect_scene_graph(doc: Any, expected: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    try:
        import FreeCADGui as Gui  # type: ignore
        from pivy import coin  # type: ignore
    except (ImportError, RuntimeError) as exc:
        return {"available": False, "reason": str(exc)}, []

    try:
        gui_doc = Gui.activeDocument()
        if gui_doc is None:
            return {"available": False, "reason": "no active GUI document"}, []
        gui_doc.activeView().redraw()
        Gui.updateGui()
    except (AttributeError, RuntimeError) as exc:
        return {"available": False, "reason": str(exc)}, []

    objects = []
    totals = {
        "material_nodes": 0,
        "material_binding_nodes": 0,
        "indexed_face_set_nodes": 0,
        "material_color_entries": 0,
    }
    binding_values = set()
    for obj in doc.Objects:
        if is_benchmark_info(obj) or not object_is_visible(obj):
            continue
        root = getattr(obj.ViewObject, "RootNode", None)
        if root is None:
            continue
        counts = {key: 0 for key in totals}
        material_color_counts = []
        values = set()
        _walk_coin(root, coin, counts, values, material_color_counts)
        for key, value in counts.items():
            totals[key] += value
        binding_values.update(values)
        objects.append(
            {
                "name": obj.Name,
                **counts,
                "material_bindings": sorted(values),
                "material_color_counts": material_color_counts,
            }
        )

    available = bool(objects)
    scene_graph = {
        "available": available,
        "visible_view_providers": len(objects),
        **totals,
        "material_bindings": sorted(binding_values),
        "objects": objects,
    }
    errors = []
    if not available:
        return scene_graph, errors
    if totals["indexed_face_set_nodes"] == 0:
        errors.append("scene graph has no indexed face-set nodes")
    if expected.get("color_mode") == "per-face":
        if totals["material_nodes"] == 0:
            errors.append("per-face fixture has no Coin material nodes")
        if not any("PER_PART" in value for value in binding_values):
            errors.append("per-face fixture has no PER_PART material binding")
    return scene_graph, errors


def _walk_coin(
    node: Any,
    coin: Any,
    counts: dict[str, int],
    bindings: set[str],
    material_color_counts: list[int],
) -> None:
    type_name = _coin_type_name(node)
    if type_name == "SoMaterial":
        counts["material_nodes"] += 1
        try:
            color_count = int(node.diffuseColor.getNum())
            material_color_counts.append(color_count)
            counts["material_color_entries"] += color_count
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
    elif type_name == "SoMaterialBinding":
        counts["material_binding_nodes"] += 1
        value = getattr(node, "value", None)
        text = _coin_enum_text(value, coin)
        for candidate in ("PER_PART_INDEXED", "PER_PART", "OVERALL"):
            if candidate in text:
                bindings.add(candidate)
    elif type_name in ("SoBrepFaceSet", "SoIndexedFaceSet", "SoFaceSet"):
        counts["indexed_face_set_nodes"] += 1

    try:
        child_count = node.getNumChildren()
    except (AttributeError, RuntimeError):
        return
    for index in range(child_count):
        _walk_coin(node.getChild(index), coin, counts, bindings, material_color_counts)


def _coin_type_name(node: Any) -> str:
    class_name = type(node).__name__
    if class_name.startswith("So") or class_name in ("Switch", "Separator", "Group"):
        return class_name
    try:
        return node.getTypeId().getName().getString()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return class_name


def _coin_enum_text(field: Any, coin: Any) -> str:
    if field is None:
        return ""
    for method_name in ("getValueAsString", "getValueAsText"):
        try:
            return str(getattr(field, method_name)())
        except (AttributeError, RuntimeError):
            pass
    try:
        value = int(field.getValue())
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return str(field)
    names = ("PER_PART_INDEXED", "PER_PART", "OVERALL")
    matches = []
    for name in names:
        candidate = getattr(coin.SoMaterialBinding, name, None)
        try:
            if int(candidate) == value:
                matches.append(name)
        except (TypeError, ValueError):
            pass
    return " ".join(matches) or str(value)


if __name__ == "__main__":
    raise SystemExit(main())
