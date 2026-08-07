"""Benchmark deterministic camera rotations over one generated FCStd fixture.

Run from a GUI-capable FreeCAD build, for example::

    FreeCAD --console benchmark_rotation.py fixture.FCStd \
        --frames 120 --warmup 30 --output results.json

The fixture is opened once, validated from its embedded BenchmarkInfo object,
and then reused for every measured frame.  The FCStd hash is recorded so that
results can be compared across FreeCAD revisions using byte-identical inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from common import load_expected, require_gui, validate_expected


def benchmark(
    fixture: str,
    *,
    frames: int,
    warmup: int,
    step_degrees: float,
) -> dict[str, Any]:
    path = Path(fixture).expanduser().resolve()
    if frames <= 0:
        raise ValueError("frames must be positive")
    if warmup < 0:
        raise ValueError("warmup must not be negative")

    doc = None
    try:
        doc = App.openDocument(str(path))
        doc.recompute()
        expected = load_expected(doc)
        errors = validate_expected(doc, expected)
        if errors:
            raise RuntimeError("fixture validation failed:\n  " + "\n  ".join(errors))

        gui_doc = Gui.getDocument(doc.Name)
        view = gui_doc.activeView()
        view.viewAxonometric()
        view.fitAll()
        Gui.updateGui()
        initial_orientation = view.getCameraOrientation()

        def set_frame(frame: int) -> None:
            rotation = App.Rotation(App.Vector(0, 0, 1), frame * step_degrees)
            rotation.multiply(initial_orientation)
            view.setCameraOrientation(rotation)

        for frame in range(warmup):
            set_frame(frame)
            view.redraw()
            Gui.updateGui()

        opengl = _opengl_environment(view)
        samples = []
        for frame in range(frames):
            set_frame(warmup + frame)
            start = time.perf_counter()
            view.redraw()
            Gui.updateGui()
            samples.append(time.perf_counter() - start)

        version = list(App.Version())
        coin_version = _coin_version()
        result = {
            "fixture": str(path),
            "fixture_sha256": _sha256(path),
            "fixture_metadata": {
                "name": getattr(doc, "Label", doc.Name),
                "preset": getattr(doc.getObject("BenchmarkInfo"), "Preset", None),
                "seed": getattr(doc.getObject("BenchmarkInfo"), "Seed", None),
                "expected": expected,
            },
            "freecad_version": ".".join(version[:3]),
            "freecad_revision": version[3] if len(version) > 3 else None,
            "freecad_commit": version[7] if len(version) > 7 else None,
            "coin_version": coin_version,
            "opengl_renderer": opengl["renderer"],
            "gl_vendor": opengl["vendor"],
            "gl_renderer": opengl["renderer"],
            "gl_version": opengl["version"],
            "glsl_version": opengl["glsl_version"],
            "direct_rendering": opengl["direct_rendering"],
            "viewport_size": opengl["viewport_size"],
            "environment": opengl["environment"],
            "build_type": os.environ.get("FREECAD_BUILD_TYPE", "unknown"),
            "phase": os.environ.get("FREECAD_RENDERING_PHASE", "unknown"),
            "warmup_frames": warmup,
            "frame_count": frames,
            "rotation_step_degrees": step_degrees,
            "frame_times_ms": [_milliseconds(value) for value in samples],
            "median_frame_time_ms": _milliseconds(statistics.median(samples)),
            "p95_frame_time_ms": _milliseconds(_percentile(samples, 0.95)),
            "minimum_frame_time_ms": _milliseconds(min(samples)),
            "maximum_frame_time_ms": _milliseconds(max(samples)),
        }
        return result
    finally:
        if doc is not None:
            App.closeDocument(doc.Name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", help="generated FCStd fixture")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--warmup", type=int, default=30)
    parser.add_argument("--step-degrees", type=float, default=1.0)
    parser.add_argument("--output", help="write JSON results to this path")
    args = parser.parse_args(argv)
    require_gui()

    result = benchmark(
        args.fixture,
        frames=args.frames,
        warmup=args.warmup,
        step_degrees=args.step_degrees,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _milliseconds(value: float) -> float:
    return value * 1000.0


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _coin_version() -> str | None:
    try:
        return str(Gui.getSoDBVersion())
    except (AttributeError, RuntimeError):
        try:
            from pivy import coin

            return str(coin.SoDB.getVersion())
        except (ImportError, AttributeError, RuntimeError):
            return None


def _opengl_environment(view: Any) -> dict[str, Any]:
    """Capture the active GL context and X11 renderer details."""

    values = {
        "vendor": None,
        "renderer": None,
        "version": None,
        "glsl_version": None,
        "direct_rendering": None,
        "viewport_size": _viewport_size(view),
    }

    try:
        from PySide import QtGui, QtOpenGLWidgets

        widgets = Gui.getMainWindow().findChildren(QtOpenGLWidgets.QOpenGLWidget)
        contexts = [widget.context() for widget in widgets]
        current_context = QtGui.QOpenGLContext.currentContext()
        if current_context is not None:
            contexts.append(current_context)
        for context in contexts:
            if context is None:
                continue
            functions = context.functions()
            values["vendor"] = _decode_gl_string(functions.glGetString(0x1F00))
            values["renderer"] = _decode_gl_string(functions.glGetString(0x1F01))
            values["version"] = _decode_gl_string(functions.glGetString(0x1F02))
            values["glsl_version"] = _decode_gl_string(functions.glGetString(0x8B8C))
            if values["renderer"]:
                break
    except (AttributeError, ImportError, RuntimeError, TypeError):
        pass

    glx = _glxinfo()
    for key in ("vendor", "renderer", "version", "glsl_version"):
        if values[key] is None:
            values[key] = glx.get(key)
    values["direct_rendering"] = glx.get("direct_rendering")

    requested_environment = os.environ.get("FREECAD_RENDERING_ENVIRONMENT", "desktop")
    renderer = (values["renderer"] or "").lower()
    if requested_environment == "xvfb" and "llvmpipe" in renderer:
        environment = "xvfb-llvmpipe"
    elif requested_environment == "xvfb":
        environment = "xvfb"
    else:
        environment = requested_environment
    values["environment"] = environment
    return values


def _decode_gl_string(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _viewport_size(view: Any) -> dict[str, int] | None:
    try:
        value = view.getSize()
        if len(value) >= 2 and int(value[0]) > 0 and int(value[1]) > 0:
            return {"width": int(value[0]), "height": int(value[1])}
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    try:
        from PySide import QtOpenGLWidgets

        widgets = Gui.getMainWindow().findChildren(QtOpenGLWidgets.QOpenGLWidget)
        if widgets:
            widget = max(widgets, key=lambda item: item.width() * item.height())
            return {"width": int(widget.width()), "height": int(widget.height())}
    except (AttributeError, ImportError, RuntimeError, TypeError):
        pass
    return None


def _glxinfo() -> dict[str, Any]:
    executable = shutil.which("glxinfo")
    if executable is None:
        return {}
    try:
        completed = subprocess.run(
            [executable, "-B"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return {}

    values: dict[str, Any] = {}
    for line in completed.stdout.splitlines():
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        normalized = {
            "direct rendering": "direct_rendering",
            "opengl vendor string": "vendor",
            "opengl renderer string": "renderer",
            "opengl version string": "version",
            "opengl core profile version string": "version",
            "opengl es profile version string": "version",
            "opengl shading language version string": "glsl_version",
        }.get(key.lower())
        if normalized is None:
            continue
        if normalized == "direct_rendering":
            values[normalized] = value.lower() in ("yes", "true", "1")
        elif normalized not in values:
            values[normalized] = value
    return values


if __name__ == "__main__":
    raise SystemExit(main())
