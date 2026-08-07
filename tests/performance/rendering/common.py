"""Shared helpers for deterministic rendering benchmark fixtures.

These scripts are intentionally usable from FreeCAD's Python console.  They
keep generation, round-trip validation, and the small amount of metadata used
by the validators in one place so that each fixture exercises the same save
and reopen path.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
from typing import Any, Iterable

import FreeCAD as App
import FreeCADGui as Gui


GENERATOR_VERSION = "1"
RGBA = tuple[float, float, float, float]


def require_gui() -> None:
    """Fail once, early, when invoked from a non-GUI FreeCAD executable."""

    if not hasattr(Gui, "activeDocument"):
        raise RuntimeError(
            "rendering fixtures require a GUI FreeCAD build with view providers"
        )


def color(r: float, g: float, b: float, a: float = 1.0) -> RGBA:
    """Return a FreeCAD-compatible RGBA tuple with stable float values."""

    return (float(r), float(g), float(b), float(a))


def rgb(rgba: RGBA) -> tuple[float, float, float]:
    return (rgba[0], rgba[1], rgba[2])


def parse_display_mode(value: str) -> str:
    modes = {
        "shaded": "Shaded",
        "flat-lines": "Flat Lines",
    }
    try:
        return modes[value.lower()]
    except KeyError as exc:
        raise ValueError("display mode must be 'shaded' or 'flat-lines'") from exc


def add_benchmark_info(
    doc: Any,
    *,
    fixture_name: str,
    generator: str,
    preset: str,
    seed: int,
    display_mode: str,
    parameters: dict[str, Any],
    expected: dict[str, Any],
) -> Any:
    """Add a hidden, self-describing ``BenchmarkInfo`` object to *doc*."""

    info = doc.addObject("App::FeaturePython", "BenchmarkInfo")
    info.Label = "BenchmarkInfo"

    string_properties = {
        "FixtureName": fixture_name,
        "FixtureType": fixture_name.split("_", 1)[0],
        "Generator": generator,
        "GeneratorVersion": GENERATOR_VERSION,
        "Preset": preset,
        "DisplayMode": display_mode,
        "Parameters": json.dumps(parameters, sort_keys=True, separators=(",", ":")),
        "Expected": json.dumps(expected, sort_keys=True, separators=(",", ":")),
    }
    for name, value in string_properties.items():
        info.addProperty("App::PropertyString", name, "Benchmark")
        setattr(info, name, value)

    info.addProperty("App::PropertyInteger", "Seed", "Benchmark")
    info.Seed = int(seed)
    integer_properties = {
        "ObjectCount": expected.get("visible_objects", 0),
        "LinkCount": expected.get("links", 0),
        "FaceCount": expected.get("visible_faces", 0),
        "ExpectedColorCount": expected.get("target_diffuse_color_count", 0),
    }
    for name, value in integer_properties.items():
        info.addProperty("App::PropertyInteger", name, "Benchmark")
        setattr(info, name, int(value))
    info.addProperty("App::PropertyString", "README", "Benchmark")
    info.README = (
        "Generated deterministically; use the recorded generator, preset, "
        "seed, and parameters to reproduce this fixture."
    )
    info.ViewObject.Visibility = False
    return info


def configure_view(
    obj: Any,
    *,
    display_mode: str,
    visible: bool = True,
    shape_color: RGBA | None = None,
    deviation: float | None = None,
    angular_deflection: float | None = None,
) -> None:
    """Apply view settings shared by generated objects."""

    view = obj.ViewObject
    try:
        view.DisplayMode = parse_display_mode(display_mode)
    except (AttributeError, RuntimeError, ValueError):
        # App::Link view providers expose Link/ChildView modes and inherit
        # the actual Shaded/Flat Lines choice from their linked source.
        if getattr(obj, "TypeId", "") != "App::Link":
            raise
        view.DisplayMode = "ChildView"
    view.Visibility = bool(visible)
    if shape_color is not None:
        _set_if_present(view, "ShapeColor", rgb(shape_color))
    if deviation is not None:
        _set_if_present(view, "Deviation", float(deviation))
    if angular_deflection is not None:
        _set_if_present(view, "AngularDeflection", float(angular_deflection))


def set_diffuse_colors(obj: Any, colors: Iterable[RGBA]) -> list[RGBA]:
    """Assign a per-face material array and return it as a concrete list."""

    material_colors = list(colors)
    obj.ViewObject.DiffuseColor = material_colors
    return material_colors


def create_document(name: str) -> Any:
    """Create a document for a generator."""

    return App.newDocument(name)


def assign_face_colors(obj: Any, colors: Iterable[RGBA]) -> list[RGBA]:
    """Public spelling for assigning a per-face material array."""

    return set_diffuse_colors(obj, colors)


def deterministic_color(index: int, seed: int = 31603) -> RGBA:
    """Return one reproducible palette entry without using global RNG state."""

    rng = __import__("random").Random(int(seed) + int(index))
    return color(
        0.25 + 0.65 * rng.random(),
        0.25 + 0.65 * rng.random(),
        0.25 + 0.65 * rng.random(),
    )


def stable_json_hash(value: Any) -> str:
    """Hash JSON-compatible values with a canonical representation."""

    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def deterministic_placement(
    index: int, *, side: int, spacing: float, angle: float = 0.0
) -> Any:
    """Return a stable grid placement for an indexed assembly component."""

    side = max(1, int(side))
    return App.Placement(
        App.Vector(
            (index % side) * spacing,
            ((index // side) % side) * spacing,
            (index // (side * side)) * spacing,
        ),
        App.Rotation(App.Vector(0, 0, 1), float(angle)),
    )


def get_diffuse_colors(obj: Any) -> list[RGBA]:
    """Normalize FreeCAD's several Python representations of DiffuseColor."""

    try:
        value = obj.ViewObject.DiffuseColor
    except (AttributeError, RuntimeError):
        return []
    if value is None:
        return []

    if _looks_like_color(value):
        return [_as_rgba(value)]

    try:
        return [_as_rgba(item) for item in value]
    except (TypeError, ValueError):
        return []


def shape_for_object(obj: Any) -> Any | None:
    """Return an object's shape, resolving a simple App::Link if necessary."""

    try:
        shape = obj.Shape
        if shape is not None and not shape.isNull():
            return shape
    except (AttributeError, RuntimeError):
        pass

    try:
        linked = obj.LinkedObject
    except (AttributeError, RuntimeError):
        linked = None
    if linked is not None:
        try:
            shape = linked.Shape
            if shape is not None and not shape.isNull():
                return shape
        except (AttributeError, RuntimeError):
            pass
    return None


def shape_counts(shape: Any | None) -> dict[str, int]:
    if shape is None:
        return {key: 0 for key in ("solids", "shells", "faces", "edges", "vertices")}
    return {
        "solids": len(shape.Solids),
        "shells": len(shape.Shells),
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "vertices": len(shape.Vertexes),
    }


def object_is_visible(obj: Any) -> bool:
    return bool(obj.ViewObject.Visibility)


def is_benchmark_info(obj: Any) -> bool:
    return getattr(obj, "Name", "") == "BenchmarkInfo"


def is_link(obj: Any) -> bool:
    try:
        return bool(obj.isDerivedFrom("App::Link"))
    except (AttributeError, RuntimeError):
        return getattr(obj, "TypeId", "") == "App::Link"


def is_part_feature(obj: Any) -> bool:
    try:
        return bool(obj.isDerivedFrom("Part::Feature"))
    except (AttributeError, RuntimeError):
        return getattr(obj, "TypeId", "") == "Part::Feature"


def document_metrics(doc: Any) -> dict[str, Any]:
    """Collect the same stable, topology-focused metrics used for validation."""

    objects = [obj for obj in doc.Objects if not is_benchmark_info(obj)]
    visible = [obj for obj in objects if object_is_visible(obj)]
    visible_shapes = [(obj, shape_for_object(obj)) for obj in visible]
    visible_shapes = [(obj, shape) for obj, shape in visible_shapes if shape is not None]

    totals = {key: 0 for key in ("solids", "shells", "faces", "edges", "vertices")}
    for _, shape in visible_shapes:
        for key, value in shape_counts(shape).items():
            totals[key] += value

    return {
        "visible_objects": len(visible),
        "links": sum(is_link(obj) for obj in objects),
        "visible_links": sum(is_link(obj) for obj in visible),
        "part_features": sum(is_part_feature(obj) for obj in objects),
        "visible_part_features": sum(is_part_feature(obj) for obj in visible),
        "visible_shape_objects": len(visible_shapes),
        "visible_faces": totals["faces"],
        "visible_solids": totals["solids"],
        "visible_shells": totals["shells"],
        "visible_edges": totals["edges"],
        "visible_vertices": totals["vertices"],
    }


def load_expected(doc: Any) -> dict[str, Any]:
    info = doc.getObject("BenchmarkInfo")
    if info is None:
        raise RuntimeError("document has no BenchmarkInfo object")
    try:
        expected = json.loads(info.Expected)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("BenchmarkInfo.Expected is not valid JSON") from exc
    if not isinstance(expected, dict):
        raise RuntimeError("BenchmarkInfo.Expected must be a JSON object")
    return expected


def validate_expected(doc: Any, expected: dict[str, Any]) -> list[str]:
    """Return validation errors without raising, for useful CLI diagnostics."""

    metrics = document_metrics(doc)
    checks = {
        "visible_objects": metrics["visible_objects"],
        "links": metrics["links"],
        "part_features": metrics["part_features"],
        "visible_faces": metrics["visible_faces"],
    }
    errors = []
    for key, actual in checks.items():
        if key in expected and int(expected[key]) != actual:
            errors.append(f"{key}: expected {expected[key]}, got {actual}")

    info = doc.getObject("BenchmarkInfo")
    metadata_checks = {
        "ObjectCount": expected.get("visible_objects", 0),
        "LinkCount": expected.get("links", 0),
        "FaceCount": expected.get("visible_faces", 0),
        "ExpectedColorCount": expected.get("target_diffuse_color_count", 0),
    }
    if info is None:
        errors.append("missing BenchmarkInfo object")
    else:
        for name, expected_value in metadata_checks.items():
            try:
                actual_value = int(getattr(info, name))
            except (AttributeError, TypeError, ValueError):
                errors.append(f"BenchmarkInfo.{name}: missing or invalid")
                continue
            if actual_value != int(expected_value):
                errors.append(
                    f"BenchmarkInfo.{name}: expected {expected_value}, got {actual_value}"
                )

    target_name = expected.get("target_object")
    expected_faces = expected.get("target_faces")
    if target_name and expected_faces is not None:
        target = doc.getObject(target_name)
        shape = shape_for_object(target) if target is not None else None
        actual_faces = shape_counts(shape)["faces"]
        if actual_faces != int(expected_faces):
            errors.append(f"{target_name}.faces: expected {expected_faces}, got {actual_faces}")

    expected_color_count = expected.get("target_diffuse_color_count")
    if target_name and expected_color_count is not None:
        target = doc.getObject(target_name)
        if target is None:
            errors.append(f"missing target object {target_name}")
        else:
            actual_colors = len(get_diffuse_colors(target))
            if actual_colors != int(expected_color_count):
                errors.append(
                    f"{target_name}.DiffuseColor: expected {expected_color_count}, "
                    f"got {actual_colors}"
                )
    return errors


def save_reopen_validate(doc: Any, output: str | os.PathLike[str], expected: dict[str, Any]) -> None:
    """Save, close, reopen, validate, and close a generated document."""

    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.recompute()
    Gui.updateGui()
    doc.saveAs(str(output_path))
    original_name = doc.Name
    App.closeDocument(original_name)

    reopened = None
    try:
        reopened = App.openDocument(str(output_path))
        reopened.recompute()
        Gui.updateGui()
        errors = validate_expected(reopened, expected)
        if errors:
            raise RuntimeError("round-trip validation failed:\n  " + "\n  ".join(errors))
    finally:
        if reopened is not None:
            App.closeDocument(reopened.Name)


def save_and_reopen(
    doc: Any, output: str | os.PathLike[str], expected: dict[str, Any] | None = None
) -> None:
    """Save and reopen a document, optionally validating its expected counts."""

    save_reopen_validate(doc, output, expected if expected is not None else load_expected(doc))


def add_benchmark_metadata(doc: Any, **kwargs: Any) -> Any:
    """Public spelling for adding the self-describing BenchmarkInfo object."""

    return add_benchmark_info(doc, **kwargs)


def print_generation_result(output: str | os.PathLike[str], expected: dict[str, Any]) -> None:
    print(json.dumps({"output": str(Path(output).resolve()), "expected": expected}, indent=2))


def grid_count(size: str, *, kind: str) -> int:
    values = {
        "face": {"small": 16, "medium": 32, "large": 64, "xlarge": 128},
        "assembly": {"small": 64, "medium": 256, "large": 1024, "xlarge": 4096},
    }
    try:
        return values[kind][size]
    except KeyError as exc:
        raise ValueError(f"unknown {kind} size {size!r}") from exc


def ceil_cube_root(value: int) -> int:
    return max(1, int(math.ceil(value ** (1.0 / 3.0))))


def _set_if_present(obj: Any, name: str, value: Any) -> None:
    try:
        setattr(obj, name, value)
    except (AttributeError, RuntimeError):
        pass


def _looks_like_color(value: Any) -> bool:
    try:
        if len(value) not in (3, 4):
            return False
        return all(isinstance(component, (int, float)) for component in value)
    except (TypeError, ValueError):
        return False


def _as_rgba(value: Any) -> RGBA:
    components = tuple(float(component) for component in value)
    if len(components) == 3:
        return color(*components)
    if len(components) == 4:
        return color(*components)
    raise ValueError("not an RGB or RGBA value")
