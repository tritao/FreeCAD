"""Extract anonymous rendering fingerprints from one or more FCStd files.

Run with FreeCAD's Python interpreter, for example::

    FreeCADCmd analyze_fcstd.py original.FCStd --output fingerprint.json

The output deliberately contains aggregate statistics only.  Original files
are calibration inputs and are not copied into the repository.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import FreeCAD as App

from common import (
    get_diffuse_colors,
    is_benchmark_info,
    is_link,
    is_part_feature,
    object_is_visible,
    shape_counts,
    shape_for_object,
    require_gui,
)


def analyze_document(doc: Any, *, tessellation_deviation: float) -> dict[str, Any]:
    objects = [obj for obj in doc.Objects if not is_benchmark_info(obj)]
    visible_objects = [obj for obj in objects if object_is_visible(obj)]

    type_ids = Counter(str(getattr(obj, "TypeId", "")) for obj in visible_objects)
    all_type_ids = Counter(str(getattr(obj, "TypeId", "")) for obj in objects)
    visible_shapes = []
    for obj in visible_objects:
        shape = shape_for_object(obj)
        counts = shape_counts(shape)
        colors = get_diffuse_colors(obj)
        faces = counts["faces"]
        visible_shapes.append((obj, shape, counts, colors, faces))

    face_counts = [faces for _, _, _, _, faces in visible_shapes]
    diffuse_counts = [len(colors) for _, _, _, colors, _ in visible_shapes]
    per_face_objects = [
        (colors, faces)
        for _, _, _, colors, faces in visible_shapes
        if faces > 0 and len(colors) == faces
    ]
    distinct_face_colors = {
        _rounded_color(item)
        for colors, _ in per_face_objects
        for item in colors
    }

    topology_totals = Counter()
    approximate_triangles = 0
    complexity = Counter()
    diffuse_histogram = Counter()
    bounding_box = None
    for _, shape, counts, colors, faces in visible_shapes:
        topology_totals.update(counts)
        complexity[_complexity_bucket(faces)] += 1
        diffuse_histogram[str(len(colors))] += 1
        bounding_box = _expand_bounding_box(bounding_box, shape)
        if shape is not None:
            try:
                _, triangles = shape.tessellate(tessellation_deviation)
                approximate_triangles += len(triangles)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass

    result = {
        "visible_objects": len(visible_objects),
        "type_id_histogram": dict(sorted(type_ids.items())),
        "all_type_id_histogram": dict(sorted(all_type_ids.items())),
        "links": sum(is_link(obj) for obj in objects),
        "visible_links": sum(is_link(obj) for obj in visible_objects),
        "part_features": sum(is_part_feature(obj) for obj in objects),
        "visible_part_features": sum(is_part_feature(obj) for obj in visible_objects),
        "solids": topology_totals["solids"],
        "shells": topology_totals["shells"],
        "faces": topology_totals["faces"],
        "edges": topology_totals["edges"],
        "vertices": topology_totals["vertices"],
        "triangles": approximate_triangles,
        "tessellation_deviation": tessellation_deviation,
        "faces_per_object": _distribution(face_counts),
        "diffuse_color_count_per_object": _distribution(diffuse_counts),
        "diffuse_color_count_histogram": dict(sorted(diffuse_histogram.items())),
        "distinct_face_colors": len(distinct_face_colors),
        "objects_with_per_face_colors": len(per_face_objects),
        "objects_with_overall_colors": sum(
            len(colors) <= 1 for _, _, _, colors, _ in visible_shapes
        ),
        "objects_with_mismatched_color_counts": sum(
            len(colors) > 1 and len(colors) != faces
            for _, _, _, colors, faces in visible_shapes
        ),
        "bounding_box": _bounding_box_json(bounding_box),
        "shape_complexity_distribution": dict(sorted(complexity.items())),
    }
    # Keep the most useful single-value aliases easy to compare in a report.
    result["largest_object_faces"] = max(face_counts, default=0)
    return result


def analyze_file(path: str, *, tessellation_deviation: float) -> dict[str, Any]:
    doc = None
    try:
        doc = App.openDocument(str(Path(path).expanduser().resolve()))
        doc.recompute()
        return analyze_document(doc, tessellation_deviation=tessellation_deviation)
    finally:
        if doc is not None:
            App.closeDocument(doc.Name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="FCStd files to analyze")
    parser.add_argument("--output", help="JSON output path; stdout when omitted")
    parser.add_argument(
        "--deviation",
        type=float,
        default=0.1,
        help="linear tessellation deviation used for approximate triangle counts",
    )
    args = parser.parse_args(argv)
    require_gui()

    if args.deviation <= 0:
        parser.error("--deviation must be positive")

    fingerprints = [
        analyze_file(path, tessellation_deviation=args.deviation) for path in args.inputs
    ]
    payload: Any = fingerprints[0] if len(fingerprints) == 1 else {"documents": fingerprints}
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


def _distribution(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "median": 0, "p95": 0, "maximum": 0}
    return {
        "count": len(values),
        "median": statistics.median(values),
        "p95": _percentile(values, 0.95),
        "maximum": max(values),
    }


def _percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _complexity_bucket(faces: int) -> str:
    if faces == 0:
        return "no_faces"
    if faces <= 6:
        return "1_to_6_faces"
    if faces <= 100:
        return "7_to_100_faces"
    if faces <= 1000:
        return "101_to_1000_faces"
    if faces <= 10000:
        return "1001_to_10000_faces"
    return "more_than_10000_faces"


def _expand_bounding_box(current: Any, shape: Any) -> Any:
    if shape is None:
        return current
    box = shape.BoundBox
    if not box.isValid():
        return current
    values = (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)
    if current is None:
        return values
    return (
        min(current[0], values[0]),
        min(current[1], values[1]),
        min(current[2], values[2]),
        max(current[3], values[3]),
        max(current[4], values[4]),
        max(current[5], values[5]),
    )


def _bounding_box_json(values: Any) -> dict[str, Any]:
    if values is None:
        return {"minimum": None, "maximum": None, "dimensions": [0.0, 0.0, 0.0]}
    return {
        "minimum": list(values[:3]),
        "maximum": list(values[3:]),
        "dimensions": [values[3] - values[0], values[4] - values[1], values[5] - values[2]],
    }


def _rounded_color(value: Any) -> tuple[float, ...]:
    return tuple(round(float(component), 6) for component in value)


if __name__ == "__main__":
    raise SystemExit(main())
