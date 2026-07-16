#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Benchmark production mesh ViewProvider updates and rendering.

Run this script with two FreeCAD builds and compare the emitted JSON files::

    xvfb-run -a path/to/benchmark_mesh_rendering.py --freecad ./bin/FreeCAD \
        --triangles 100000,500000 --iterations 30 --output results.json

The benchmark deliberately remains outside the test suite: framebuffer timings
depend on the graphics driver and machine. Mesh construction is performed before
each scenario and is not included in the reported ViewProvider timings.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Callable


DEFAULT_SCENARIOS = (
    "initial-display",
    "warm-render",
    "material-change",
    "open-edges",
    "mesh-replacement",
)


def _parse_csv(value: str, cast: Callable[[str], object]) -> list:
    try:
        result = [cast(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not result:
        raise argparse.ArgumentTypeError("the list must not be empty")
    return result


def _parse_arguments(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freecad",
        default="FreeCAD",
        help="FreeCAD GUI executable to benchmark (default: FreeCAD from PATH)",
    )
    parser.add_argument(
        "--triangles",
        type=lambda value: _parse_csv(value, int),
        default=[100_000],
        help="comma-separated target triangle counts (default: 100000)",
    )
    parser.add_argument(
        "--scenarios",
        type=lambda value: _parse_csv(value, str),
        default=list(DEFAULT_SCENARIOS),
        help=f"comma-separated scenarios (default: {','.join(DEFAULT_SCENARIOS)})",
    )
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(arguments)

    unknown = set(arguments.scenarios) - set(DEFAULT_SCENARIOS)
    if unknown:
        parser.error(f"unknown scenarios: {', '.join(sorted(unknown))}")
    if any(count <= 0 for count in arguments.triangles):
        parser.error("triangle counts must be positive")
    if arguments.iterations <= 0 or arguments.warmups < 0:
        parser.error("iterations must be positive and warmups must not be negative")
    if arguments.width <= 0 or arguments.height <= 0:
        parser.error("image dimensions must be positive")
    return arguments


def _make_grid_mesh(target_triangles: int, z_offset: float = 0.0):
    """Return a connected rectangular grid with approximately the requested size."""
    target_cells = math.ceil(target_triangles / 2)
    columns = math.ceil(math.sqrt(target_cells))
    rows = math.ceil(target_cells / columns)
    triangles = []
    for row in range(rows):
        y0 = row / rows
        y1 = (row + 1) / rows
        for column in range(columns):
            x0 = column / columns
            x1 = (column + 1) / columns
            triangles.extend(
                (
                    (x0, y0, z_offset),
                    (x1, y0, z_offset),
                    (x1, y1, z_offset),
                    (x0, y0, z_offset),
                    (x1, y1, z_offset),
                    (x0, y1, z_offset),
                )
            )
    return Mesh.Mesh(triangles), 2 * (rows + columns)


def _milliseconds(operation: Callable[[], object]) -> float:
    start = time.perf_counter_ns()
    operation()
    return (time.perf_counter_ns() - start) / 1_000_000.0


def _summarize(samples: list[float]) -> dict:
    ordered = sorted(samples)
    p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return {
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[p95_index],
        "min_ms": ordered[0],
        "max_ms": ordered[-1],
        "samples_ms": samples,
    }


class MeshBenchmark:
    def __init__(self, arguments: argparse.Namespace):
        self.arguments = arguments
        self.document = FreeCAD.newDocument("MeshRenderingBenchmark")
        FreeCADGui.setActiveDocument(self.document.Name)
        self.object = self.document.addObject("Mesh::Feature", "BenchmarkMesh")
        self.document.recompute()
        FreeCADGui.updateGui()
        self.view = FreeCADGui.activeDocument().activeView()
        self.viewer = self.view.getViewer()
        self.view.setAnimationEnabled(False)
        self.view.setAxisCross(False)
        self.viewer.setGradientBackground("NONE")

    def close(self) -> None:
        if FreeCAD.getDocument(self.document.Name):
            FreeCAD.closeDocument(self.document.Name)
            FreeCADGui.updateGui()

    def synchronize(self) -> None:
        self.document.recompute()
        FreeCADGui.updateGui()

    def render(self) -> None:
        image = self.viewer.renderToImage(
            width=self.arguments.width,
            height=self.arguments.height,
            samples=0,
        )
        if image.isNull():
            raise RuntimeError("renderToImage returned an empty image")

    def _measure(self, operation: Callable[[], object]) -> dict:
        for _ in range(self.arguments.warmups):
            operation()
        return _summarize([_milliseconds(operation) for _ in range(self.arguments.iterations)])

    def _measure_update_and_first_render(self, update: Callable[[], object]) -> dict:
        for _ in range(self.arguments.warmups):
            update()
            self.render()
        update_samples = []
        render_samples = []
        for _ in range(self.arguments.iterations):
            update_samples.append(_milliseconds(update))
            render_samples.append(_milliseconds(self.render))
        return {
            "update": _summarize(update_samples),
            "first_render": _summarize(render_samples),
        }

    def run_size(self, target_triangles: int) -> dict:
        mesh_a, boundary_edges = _make_grid_mesh(target_triangles)
        mesh_b, _ = _make_grid_mesh(target_triangles, z_offset=0.0001)
        actual_triangles = mesh_a.CountFacets
        result = {
            "target_triangles": target_triangles,
            "actual_triangles": actual_triangles,
            "points": mesh_a.CountPoints,
            "expected_boundary_edges": boundary_edges,
            "scenarios": {},
        }

        def assign(mesh) -> None:
            self.object.Mesh = mesh
            self.synchronize()

        initial_update_ms = _milliseconds(lambda: assign(mesh_a))
        self.view.fitAll()
        initial_render_ms = _milliseconds(self.render)
        if "initial-display" in self.arguments.scenarios:
            result["scenarios"]["initial-display"] = {
                "update_ms": initial_update_ms,
                "first_render_ms": initial_render_ms,
            }

        if "warm-render" in self.arguments.scenarios:
            result["scenarios"]["warm-render"] = self._measure(self.render)

        if "material-change" in self.arguments.scenarios:
            colors = ((0.82, 0.24, 0.18), (0.18, 0.42, 0.86))
            color_index = 0

            def change_material() -> None:
                nonlocal color_index
                self.object.ViewObject.ShapeColor = colors[color_index]
                color_index = 1 - color_index
                self.synchronize()

            result["scenarios"]["material-change"] = self._measure_update_and_first_render(
                change_material
            )

        if "open-edges" in self.arguments.scenarios:
            def rebuild_open_edges() -> None:
                self.object.ViewObject.OpenEdges = False
                self.synchronize()
                self.object.ViewObject.OpenEdges = True
                self.synchronize()

            result["scenarios"]["open-edges"] = self._measure_update_and_first_render(
                rebuild_open_edges
            )
            result["scenarios"]["open-edges"]["warm_render"] = self._measure(self.render)
            self.object.ViewObject.OpenEdges = False
            self.synchronize()

        if "mesh-replacement" in self.arguments.scenarios:
            replacement_index = 0

            def replace_mesh() -> None:
                nonlocal replacement_index
                assign((mesh_a, mesh_b)[replacement_index])
                replacement_index = 1 - replacement_index

            result["scenarios"]["mesh-replacement"] = self._measure_update_and_first_render(
                replace_mesh
            )

        self.object.Mesh = Mesh.Mesh()
        self.synchronize()
        return result


def _run_inside_freecad(configuration: dict) -> None:
    global FreeCAD, FreeCADGui, Mesh
    import FreeCAD  # type: ignore[no-redef]
    import FreeCADGui  # type: ignore[no-redef]
    import Mesh  # type: ignore[no-redef]

    arguments = argparse.Namespace(**configuration["arguments"])
    arguments.output = Path(configuration["result_path"])
    benchmark = MeshBenchmark(arguments)
    try:
        results = [benchmark.run_size(count) for count in arguments.triangles]
    finally:
        benchmark.close()

    payload = {
        "schema_version": 1,
        "environment": {
            "freecad_version": FreeCAD.Version(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "resolution": [arguments.width, arguments.height],
            "iterations": arguments.iterations,
            "warmups": arguments.warmups,
            "capture_api": "renderToImage(samples=0)",
        },
        "results": results,
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(encoded + "\n", encoding="utf-8")


def _launch(arguments: argparse.Namespace) -> int:
    requested_output = arguments.output
    with tempfile.TemporaryDirectory(prefix="freecad-mesh-benchmark-") as temp_directory:
        result_path = Path(temp_directory) / "result.json"
        configuration = {
            "arguments": {
                "triangles": arguments.triangles,
                "scenarios": arguments.scenarios,
                "iterations": arguments.iterations,
                "warmups": arguments.warmups,
                "width": arguments.width,
                "height": arguments.height,
            },
            "result_path": str(result_path),
        }
        environment = os.environ.copy()
        environment["FREECAD_MESH_BENCHMARK_CONFIG"] = json.dumps(configuration)
        script_directory = Path(__file__).resolve().parent
        test_module_directory = script_directory.parents[1] / "src" / "Mod" / "Test"
        command = [
            arguments.freecad,
            "--python-path",
            str(script_directory),
            "--python-path",
            str(test_module_directory),
            "--run-test",
            "benchmark_mesh_rendering.MeshRenderingBenchmarkTest.test_benchmark",
        ]
        completed = subprocess.run(command, env=environment, check=False)
        if completed.returncode:
            return completed.returncode
        if not result_path.is_file():
            print("FreeCAD exited without producing benchmark results", file=sys.stderr)
            return 1

        encoded = result_path.read_text(encoding="utf-8")
        if requested_output:
            requested_output.parent.mkdir(parents=True, exist_ok=True)
            requested_output.write_text(encoded, encoding="utf-8")
        else:
            print(encoded, end="")
    return 0


class MeshRenderingBenchmarkTest(unittest.TestCase):
    """FreeCAD test-runner entry point used by the external launcher."""

    def test_benchmark(self):
        encoded_configuration = os.environ.get("FREECAD_MESH_BENCHMARK_CONFIG")
        if not encoded_configuration:
            self.fail("FREECAD_MESH_BENCHMARK_CONFIG is not set")
        _run_inside_freecad(json.loads(encoded_configuration))


if __name__ == "__main__":
    raise SystemExit(_launch(_parse_arguments(sys.argv[1:])))
