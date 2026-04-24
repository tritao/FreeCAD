# SPDX-License-Identifier: LGPL-2.1-or-later

"""Manual UX benchmark runner for BIM Plan Edit.

This module is intended to be run inside the FreeCAD GUI Python environment.
It creates deterministic benchmark documents, drives Plan Edit interaction
handlers, and summarizes the existing Plan Edit JSONL performance trace.

Example from the FreeCAD Python console:

    import bimplan.benchmark as plan_bench
    plan_bench.run()

For command-style execution from a FreeCAD Python script:

    import bimplan.benchmark as plan_bench
    plan_bench.main(["--scenario", "small", "--iterations", "3"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
import argparse
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
import time

READINESS_LIMITS_MS = {
    "enter_plan_edit": 1000.0,
    "mouse_moved_fast_path": 10.0,
    "hover_pick_resolve": 33.0,
    "mouse_pressed": 100.0,
    "mouse_wheel": 50.0,
    "queued_integration_panel_refresh": 200.0,
    "benchmark_task_panel_refresh": 200.0,
    "benchmark_view_scale_overlay_refresh": 50.0,
    "benchmark_wall_handle_activation": 100.0,
    "benchmark_opening_handle_activation": 100.0,
    "benchmark_symbol_handle_activation": 100.0,
}


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    rows: int
    cols: int
    openings: int
    symbols: int
    spaces: int
    provider_overlays: int
    hover_samples: int
    click_samples: int
    cell_size: float = 4000.0
    wall_width: float = 200.0
    wall_height: float = 2800.0


@dataclass
class SceneData:
    level: object | None = None
    walls: list = field(default_factory=list)
    openings: list = field(default_factory=list)
    symbols: list = field(default_factory=list)
    spaces: list = field(default_factory=list)
    hover_points: list = field(default_factory=list)
    click_points: list = field(default_factory=list)
    provider_points: list = field(default_factory=list)


SCENARIOS = {
    "small": ScenarioSpec(
        name="small",
        rows=1,
        cols=1,
        openings=1,
        symbols=1,
        spaces=1,
        provider_overlays=6,
        hover_samples=32,
        click_samples=8,
    ),
    "medium": ScenarioSpec(
        name="medium",
        rows=4,
        cols=4,
        openings=8,
        symbols=8,
        spaces=4,
        provider_overlays=32,
        hover_samples=96,
        click_samples=16,
    ),
    "stress": ScenarioSpec(
        name="stress",
        rows=8,
        cols=8,
        openings=16,
        symbols=24,
        spaces=8,
        provider_overlays=96,
        hover_samples=192,
        click_samples=32,
    ),
}


class _FakeEventCallback:
    def __init__(self, event):
        self._event = event
        self._handled = False

    def getEvent(self):
        return self._event

    def setHandled(self):
        self._handled = True


class _FakeMousePosition:
    def __init__(self, x, y):
        self._value = (x, y)

    def getValue(self):
        return self._value


class _FakeMouseMoveEvent:
    def __init__(self, x, y):
        self._position = _FakeMousePosition(x, y)

    def getPosition(self):
        return self._position


class _FakeMouseButtonEvent:
    def __init__(self, x, y, button, state):
        self._position = _FakeMousePosition(x, y)
        self._button = button
        self._state = state

    def getButton(self):
        return self._button

    def getState(self):
        return self._state

    def getPosition(self):
        return self._position


class _FakeWheelTypeId:
    def getName(self):
        return "SoMouseWheelEvent"


class _FakeWheelEvent:
    def getTypeId(self):
        return _FakeWheelTypeId()


def _require_freecad_gui():
    try:
        import FreeCAD
        import FreeCADGui
    except Exception as exc:
        raise RuntimeError("Plan Edit benchmarks must run inside FreeCAD.") from exc
    if not getattr(FreeCAD, "GuiUp", False):
        raise RuntimeError("Plan Edit benchmarks require the FreeCAD GUI executable.")
    return FreeCAD, FreeCADGui


def _pump_gui_events(duration_ms=0):
    try:
        from PySide import QtCore, QtGui
    except Exception:
        return
    app = QtGui.QApplication.instance()
    if app is None:
        return
    if duration_ms and duration_ms > 0:
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(int(duration_ms), loop.quit)
        loop.exec_()
        return
    for _index in range(4):
        app.processEvents(QtCore.QEventLoop.AllEvents, 20)
        try:
            QtGui.QApplication.sendPostedEvents(None, 0)
        except Exception:
            pass


def _safe_name(value):
    text = str(value or "Object")
    chars = [char if char.isalnum() else "_" for char in text]
    result = "".join(chars).strip("_")
    return result or "Object"


def _make_wall(Draft, Arch, FreeCAD, level, start, end, width, height, label):
    base = Draft.makeLine(start, end)
    wall = Arch.makeWall(base, width=width, height=height, name=_safe_name(label))
    wall.Label = label
    try:
        level.addObject(wall)
    except Exception:
        pass
    midpoint = FreeCAD.Vector(
        (float(start.x) + float(end.x)) * 0.5,
        (float(start.y) + float(end.y)) * 0.5,
        (float(start.z) + float(end.z)) * 0.5,
    )
    return wall, midpoint


def _make_opening(Arch, FreeCAD, wall, point, index):
    try:
        opening = Arch.makeWindowPreset(
            "Simple door",
            width=900,
            height=2100,
            h1=50,
            h2=50,
            h3=50,
            w1=100,
            w2=40,
            o1=0,
            o2=0,
        )
        opening.Label = "Benchmark Opening {}".format(index + 1)
        opening.Placement = FreeCAD.Placement(
            FreeCAD.Vector(point.x, point.y, 0),
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90),
        )
        try:
            opening.Hosts = [wall]
        except Exception:
            Arch.addComponents(opening, wall)
        return opening
    except Exception:
        return None


def _make_symbol(doc, Arch, Part, FreeCAD, level, point, index):
    try:
        box = doc.addObject("Part::Box", "BenchmarkSymbolBox{}".format(index + 1))
        box.Length = 1000
        box.Width = 700
        box.Height = 500
        equipment = Arch.makeEquipment(box)
        equipment.Label = "Benchmark Symbol {}".format(index + 1)
        equipment.Placement.Base = FreeCAD.Vector(point.x, point.y, 0)

        plan = doc.addObject("Part::Feature", "BenchmarkSymbolPlan{}".format(index + 1))
        plan.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0)),
                Part.makeLine(FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 700, 0)),
                Part.makeLine(FreeCAD.Vector(1000, 700, 0), FreeCAD.Vector(0, 700, 0)),
                Part.makeLine(FreeCAD.Vector(0, 700, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        equipment.PlanSymbols = [plan]
        try:
            level.addObject(equipment)
        except Exception:
            pass
        return equipment
    except Exception:
        return None


def _make_space(doc, Arch, FreeCAD, level, point, cell_size, index):
    try:
        box = doc.addObject("Part::Box", "BenchmarkSpaceVolume{}".format(index + 1))
        box.Length = cell_size * 0.75
        box.Width = cell_size * 0.75
        box.Height = 2600
        box.Placement.Base = FreeCAD.Vector(
            point.x - (cell_size * 0.375),
            point.y - (cell_size * 0.375),
            0,
        )
        space = Arch.makeSpace(box, name="Benchmark Space {}".format(index + 1))
        try:
            level.addObject(space)
        except Exception:
            pass
        return space
    except Exception:
        return None


def _create_scene(spec):
    import Arch
    import Draft
    import Part
    import FreeCAD

    doc = FreeCAD.ActiveDocument
    scene = SceneData()
    scene.level = Arch.makeFloor(name="Benchmark Level")

    total_width = spec.cols * spec.cell_size
    total_depth = spec.rows * spec.cell_size

    for row in range(spec.rows + 1):
        y = row * spec.cell_size
        for col in range(spec.cols):
            x0 = col * spec.cell_size
            x1 = (col + 1) * spec.cell_size
            wall, midpoint = _make_wall(
                Draft,
                Arch,
                FreeCAD,
                scene.level,
                FreeCAD.Vector(x0, y, 0),
                FreeCAD.Vector(x1, y, 0),
                spec.wall_width,
                spec.wall_height,
                "Benchmark H Wall {} {}".format(row, col),
            )
            scene.walls.append(wall)
            scene.hover_points.append(midpoint)

    for col in range(spec.cols + 1):
        x = col * spec.cell_size
        for row in range(spec.rows):
            y0 = row * spec.cell_size
            y1 = (row + 1) * spec.cell_size
            wall, midpoint = _make_wall(
                Draft,
                Arch,
                FreeCAD,
                scene.level,
                FreeCAD.Vector(x, y0, 0),
                FreeCAD.Vector(x, y1, 0),
                spec.wall_width,
                spec.wall_height,
                "Benchmark V Wall {} {}".format(row, col),
            )
            scene.walls.append(wall)
            scene.hover_points.append(midpoint)

    horizontal_walls = scene.walls[: max(1, (spec.rows + 1) * spec.cols)]
    for index in range(min(spec.openings, len(horizontal_walls))):
        wall = horizontal_walls[index]
        col = index % spec.cols
        row = (index // spec.cols) % (spec.rows + 1)
        point = FreeCAD.Vector((col + 0.5) * spec.cell_size, row * spec.cell_size, 0)
        opening = _make_opening(Arch, FreeCAD, wall, point, index)
        if opening is not None:
            scene.openings.append(opening)
            scene.hover_points.append(point)

    for index in range(spec.symbols):
        col = index % max(1, spec.cols)
        row = (index // max(1, spec.cols)) % max(1, spec.rows)
        point = FreeCAD.Vector(
            (col + 0.35) * spec.cell_size,
            (row + 0.35) * spec.cell_size,
            0,
        )
        symbol = _make_symbol(doc, Arch, Part, FreeCAD, scene.level, point, index)
        if symbol is not None:
            scene.symbols.append(symbol)
            scene.hover_points.append(point)

    for index in range(spec.spaces):
        col = index % max(1, spec.cols)
        row = (index // max(1, spec.cols)) % max(1, spec.rows)
        point = FreeCAD.Vector(
            (col + 0.5) * spec.cell_size,
            (row + 0.5) * spec.cell_size,
            0,
        )
        space = _make_space(doc, Arch, FreeCAD, scene.level, point, spec.cell_size, index)
        if space is not None:
            scene.spaces.append(space)
            scene.hover_points.append(point)

    for index in range(spec.provider_overlays):
        col = index % max(1, spec.cols)
        row = (index // max(1, spec.cols)) % max(1, spec.rows)
        offset = 0.15 + (0.7 * ((index % 5) / 5.0))
        scene.provider_points.append(
            FreeCAD.Vector(
                (col + offset) * spec.cell_size,
                (row + 0.65) * spec.cell_size,
                0,
            )
        )

    scene.click_points = list(scene.hover_points)
    if not scene.click_points:
        scene.click_points = [
            FreeCAD.Vector(total_width * 0.5, total_depth * 0.5, 0),
        ]
    doc.recompute()
    return scene


def _register_benchmark_provider(scene, scenario_name):
    from bimplan.providers import (
        PlanContextPanelSpec,
        PlanContextPanelState,
        PlanContextRowSpec,
        PlanContextSubjectKind,
        PlanEditProvider,
        PlanInspectorSection,
        PlanIssueSeverity,
        PlanIssueSpec,
        PlanOverlaySpec,
        PlanToolSpec,
    )
    from bimplan.providers import get_plan_edit_registry

    class _BenchmarkPlanProvider(PlanEditProvider):
        provider_id = "benchmark-plan-provider-{}".format(scenario_name)
        display_name = "Benchmark Plan Provider"

        def get_tools(self, context):
            del context
            return (
                PlanToolSpec(
                    key="benchmark-point-tool",
                    label="Benchmark Point",
                    tooltip="Synthetic benchmark tool.",
                ),
            )

        def get_issues(self, context):
            del context
            return (
                PlanIssueSpec(
                    key="benchmark-warning",
                    title="Benchmark warning",
                    message="Synthetic Plan Edit benchmark issue.",
                    severity=PlanIssueSeverity.WARNING,
                ),
            )

        def get_context_panels(self, context):
            primary = context.get_primary_target()
            label = getattr(primary, "label", "") if primary else "No selection"
            return (
                PlanContextPanelSpec(
                    key="benchmark-context",
                    title=label,
                    subtitle="Benchmark",
                    state=PlanContextPanelState.SINGLE_OBJECT,
                    subject_kind=PlanContextSubjectKind.GEOMETRY,
                    summary_rows=(
                        PlanContextRowSpec("Walls", str(len(scene.walls))),
                        PlanContextRowSpec("Openings", str(len(scene.openings))),
                        PlanContextRowSpec("Symbols", str(len(scene.symbols))),
                    ),
                    message="Synthetic Plan Edit benchmark context.",
                ),
            )

        def get_inspector_sections(self, context):
            del context
            return (
                PlanInspectorSection(
                    key="benchmark-summary",
                    title="Benchmark Summary",
                    body="Synthetic provider content for Plan Edit benchmark runs.",
                ),
            )

        def get_overlays(self, context):
            del context
            overlays = []
            for index, point in enumerate(scene.provider_points):
                overlays.append(
                    PlanOverlaySpec(
                        key="benchmark-overlay-{}".format(index + 1),
                        label="Benchmark Overlay {}".format(index + 1),
                        points=((float(point.x), float(point.y), float(point.z)),),
                        color=(0.15, 0.55, 0.85),
                        category="benchmark",
                    )
                )
            return tuple(overlays)

    provider = _BenchmarkPlanProvider()
    registry = get_plan_edit_registry()
    registry.register_provider(provider)
    return provider


def _screen_point(session, point):
    try:
        screen = session.view.getPointOnScreen(point)
    except Exception:
        return None
    try:
        return int(screen[0]), int(screen[1])
    except Exception:
        return None


def _make_mouse_move_callback(x, y):
    return _FakeEventCallback(_FakeMouseMoveEvent(x, y))


def _make_mouse_press_callback(x, y, down=True):
    from pivy import coin

    state = coin.SoMouseButtonEvent.DOWN if down else coin.SoMouseButtonEvent.UP
    event = _FakeMouseButtonEvent(x, y, coin.SoMouseButtonEvent.BUTTON1, state)
    return _FakeEventCallback(event)


def _make_mouse_wheel_callback():
    return _FakeEventCallback(_FakeWheelEvent())


def _write_json_line(handle, payload):
    handle.write(json.dumps(payload, sort_keys=True))
    handle.write("\n")
    handle.flush()


def _measure_operation(
    operations_handle,
    scenario_name,
    operation_name,
    func,
    settle_ms=0,
    pre_settle_ms=0,
):
    _pump_gui_events(pre_settle_ms)
    started = time.perf_counter()
    ok = True
    error = ""
    try:
        func()
    except Exception as exc:
        ok = False
        error = repr(exc)
    total_ms = (time.perf_counter() - started) * 1000.0
    _pump_gui_events(settle_ms)
    _write_json_line(
        operations_handle,
        {
            "scenario": scenario_name,
            "operation": operation_name,
            "ok": ok,
            "error": error,
            "total_ms": round(total_ms, 3),
            "pre_settle_ms": int(pre_settle_ms or 0),
            "post_settle_ms": int(settle_ms or 0),
            "ts_unix": round(time.time(), 6),
        },
    )
    return ok


def _trace_direct_operation(session, event_name, scenario_name, operation):
    with session._plan_perf_trace_event(event_name, scenario=scenario_name):
        operation()


def _cancel_active_plan_tool(session):
    if getattr(session, "current_tool", "Select") == "Select":
        return
    try:
        session.finish(close_dialog=False)
    except Exception:
        pass


def _run_interactions(session, scene, spec, operations_handle, settle_ms, timer_settle_ms):
    hover_points = list(scene.hover_points or scene.click_points)
    click_points = list(scene.click_points or scene.hover_points)

    def hover_fast_path_once(point):
        screen = _screen_point(session, point)
        if screen is None:
            return
        session._hover_pick_last_time = time.monotonic()
        session._hover_pick_last_mouse_pos = (float(screen[0]), float(screen[1]))
        _trace_direct_operation(
            session,
            "mouse_moved_fast_path",
            spec.name,
            lambda: session.selection.update_hovered_plan_target(screen, force=False),
        )

    def hover_pick_resolve_once(point):
        screen = _screen_point(session, point)
        if screen is None:
            return

        def resolve():
            if not session.selection.update_hovered_plan_target(screen, force=True):
                return
            if session._grip_trackers or session._is_selected_plan_target("wall"):
                session.overlays.sync_wall_grips()
            session.viewport.request_view_redraw()

        _trace_direct_operation(session, "hover_pick_resolve", spec.name, resolve)

    for index in range(spec.hover_samples):
        point = hover_points[index % len(hover_points)]
        _measure_operation(
            operations_handle,
            spec.name,
            "mouse_moved_fast_path",
            lambda point=point: hover_fast_path_once(point),
            settle_ms=settle_ms,
        )
        _measure_operation(
            operations_handle,
            spec.name,
            "hover_pick_resolve",
            lambda point=point: hover_pick_resolve_once(point),
            settle_ms=settle_ms,
        )

    def click_once(point):
        screen = _screen_point(session, point)
        if screen is None:
            return
        session._on_mouse_pressed(_make_mouse_press_callback(screen[0], screen[1], down=True))
        session._on_mouse_pressed(_make_mouse_press_callback(screen[0], screen[1], down=False))

    for index in range(spec.click_samples):
        point = click_points[index % len(click_points)]
        _measure_operation(
            operations_handle,
            spec.name,
            "click_select",
            lambda point=point: click_once(point),
            settle_ms=settle_ms,
        )

    if scene.walls:
        wall = scene.walls[0]

        def activate_wall_handle():
            _trace_direct_operation(
                session,
                "benchmark_wall_handle_activation",
                spec.name,
                lambda: (
                    session._select_wall_for_plan_edit(wall),
                    session.overlays.sync_wall_grips(),
                    session._activate_wall_grip_now(0, wall=wall),
                ),
            )

        _measure_operation(
            operations_handle,
            spec.name,
            "wall_handle_activation",
            activate_wall_handle,
            settle_ms=settle_ms,
        )
        _cancel_active_plan_tool(session)

    if scene.openings:
        opening = scene.openings[0]

        def activate_opening_handle():
            _trace_direct_operation(
                session,
                "benchmark_opening_handle_activation",
                spec.name,
                lambda: (
                    session._select_opening_for_plan_edit(opening),
                    session.overlays.sync_selected_opening_handles(),
                    session.openings.activate_opening_handle_now(opening, 0),
                ),
            )

        _measure_operation(
            operations_handle,
            spec.name,
            "opening_handle_activation",
            activate_opening_handle,
            settle_ms=settle_ms,
        )
        _cancel_active_plan_tool(session)

    if scene.symbols:
        symbol = scene.symbols[0]

        def activate_symbol_handle():
            specs = tuple(session.overlays.get_selected_symbol_handle_specs(symbol))
            role = specs[0][0] if specs else "move"
            _trace_direct_operation(
                session,
                "benchmark_symbol_handle_activation",
                spec.name,
                lambda: (
                    session._select_symbol_for_plan_edit(symbol),
                    session.overlays.sync_selected_symbol_handles(),
                    session.symbols.activate_symbol_handle_now(symbol, role),
                ),
            )

        _measure_operation(
            operations_handle,
            spec.name,
            "symbol_handle_activation",
            activate_symbol_handle,
            settle_ms=settle_ms,
        )
        _cancel_active_plan_tool(session)

    def wheel_once():
        session._on_mouse_wheel(_make_mouse_wheel_callback())
        _trace_direct_operation(
            session,
            "benchmark_view_scale_overlay_refresh",
            spec.name,
            session._flush_view_scale_overlay_refresh,
        )

    _measure_operation(
        operations_handle,
        spec.name,
        "mouse_wheel",
        wheel_once,
        settle_ms=timer_settle_ms,
    )

    if session.task_panel is not None:

        def refresh_panel():
            _trace_direct_operation(
                session,
                "benchmark_task_panel_refresh",
                spec.name,
                lambda: session.task_panel.refresh_from_session(refresh_integrations=True),
            )

        _measure_operation(
            operations_handle,
            spec.name,
            "task_panel_refresh",
            refresh_panel,
            settle_ms=timer_settle_ms,
        )


def _run_scenario(spec, iteration, operations_handle, settle_ms, timer_settle_ms, keep_documents):
    FreeCAD, FreeCADGui = _require_freecad_gui()
    from bimcommands import BimPlanSession
    from bimplan.providers import get_plan_edit_registry

    active_session = BimPlanSession.get_active_session()
    if active_session:
        active_session.shutdown(close_dialog=False, teardown=True)

    doc_name = "BimPlanEditBenchmark_{}_{}".format(spec.name, iteration + 1)
    doc = FreeCAD.newDocument(doc_name)
    FreeCAD.setActiveDocument(doc.Name)
    try:
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(doc.Name)
    except Exception:
        pass

    provider = None
    session = None
    try:
        scene = _create_scene(spec)
        provider = _register_benchmark_provider(scene, spec.name)
        FreeCADGui.Selection.clearSelection()
        if scene.level is not None:
            FreeCADGui.Selection.addSelection(scene.level)
        _pump_gui_events(50)

        def start_session():
            nonlocal session
            session = BimPlanSession.start_session()
            if session is None:
                raise RuntimeError("Plan Edit session did not start.")

        _measure_operation(
            operations_handle,
            spec.name,
            "start_session",
            start_session,
            settle_ms=timer_settle_ms,
        )
        if session is None:
            raise RuntimeError("Plan Edit session did not start.")
        try:
            session.viewport.apply_plan_view(fit=True)
        except Exception:
            try:
                session.view.fitAll()
            except Exception:
                pass
        _pump_gui_events(timer_settle_ms)
        _run_interactions(session, scene, spec, operations_handle, settle_ms, timer_settle_ms)
    finally:
        if provider is not None:
            try:
                get_plan_edit_registry().unregister_provider(provider)
            except Exception:
                pass
        if session is not None:
            try:
                session.shutdown(close_dialog=False)
            except Exception:
                pass
        _pump_gui_events(50)
        if not keep_documents:
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:
                pass


def _read_jsonl(path):
    rows = []
    if not path or not Path(path).exists():
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"event": "invalid_json", "line": line})
    return rows


def _percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (float(percentile) / 100.0)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _stats(values):
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return {
            "count": 0,
            "min_ms": None,
            "mean_ms": None,
            "p50_ms": None,
            "p90_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
    return {
        "count": len(numbers),
        "min_ms": round(min(numbers), 3),
        "mean_ms": round(statistics.fmean(numbers), 3),
        "p50_ms": round(_percentile(numbers, 50), 3),
        "p90_ms": round(_percentile(numbers, 90), 3),
        "p95_ms": round(_percentile(numbers, 95), 3),
        "max_ms": round(max(numbers), 3),
    }


def _summarize_trace(events):
    grouped_events = {}
    grouped_spans = {}
    grouped_counts = {}
    for event in events:
        event_name = str(event.get("event") or "")
        if event_name:
            grouped_events.setdefault(event_name, []).append(event.get("total_ms"))
        counts = event.get("counts") or {}
        for count_name, value in counts.items():
            grouped_counts[str(count_name)] = grouped_counts.get(str(count_name), 0) + int(
                value or 0
            )
        spans = event.get("spans") or {}
        for span_name, span_data in spans.items():
            grouped_spans.setdefault(str(span_name), []).append(span_data.get("ms"))
    return {
        "events": {name: _stats(values) for name, values in sorted(grouped_events.items())},
        "spans": {name: _stats(values) for name, values in sorted(grouped_spans.items())},
        "counts": dict(sorted(grouped_counts.items())),
    }


def _summarize_operations(rows):
    grouped = {}
    for row in rows:
        operation = str(row.get("operation") or "")
        if operation:
            grouped.setdefault(operation, []).append(row.get("total_ms"))
    return {name: _stats(values) for name, values in sorted(grouped.items())}


def _build_readiness(summary):
    readiness = []
    events = summary.get("events", {})
    for event_name, limit_ms in sorted(READINESS_LIMITS_MS.items()):
        stats = events.get(event_name)
        if not stats or not stats.get("count"):
            readiness.append(
                {
                    "event": event_name,
                    "status": "missing",
                    "p95_ms": None,
                    "limit_ms": limit_ms,
                }
            )
            continue
        p95 = stats.get("p95_ms")
        status = "pass" if p95 is not None and float(p95) <= limit_ms else "warn"
        readiness.append(
            {
                "event": event_name,
                "status": status,
                "p95_ms": p95,
                "limit_ms": limit_ms,
                "count": stats.get("count", 0),
                "max_ms": stats.get("max_ms"),
            }
        )
    return readiness


def _format_ms(value):
    if value is None:
        return ""
    return "{:.3f}".format(float(value))


def _markdown_table(headers, rows):
    output = []
    output.append("| " + " | ".join(headers) + " |")
    output.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        output.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(output)


def _write_report(path, result):
    events = result["trace_summary"]["events"]
    spans = result["trace_summary"]["spans"]
    counts = result["trace_summary"].get("counts", {})
    operations = result["operation_summary"]
    readiness = result["readiness"]

    event_rows = []
    for name, stats in sorted(events.items()):
        event_rows.append(
            [
                name,
                stats["count"],
                _format_ms(stats["p50_ms"]),
                _format_ms(stats["p90_ms"]),
                _format_ms(stats["p95_ms"]),
                _format_ms(stats["max_ms"]),
            ]
        )

    readiness_rows = []
    for item in readiness:
        readiness_rows.append(
            [
                item["event"],
                item["status"],
                item.get("count", 0),
                _format_ms(item.get("p95_ms")),
                _format_ms(item.get("limit_ms")),
                _format_ms(item.get("max_ms")),
            ]
        )

    hover_skipped = int(counts.get("hover_pick_skipped") or 0)
    hover_resolved = int(counts.get("hover_pick_resolved") or 0)
    hover_total = hover_skipped + hover_resolved
    hover_count_rows = [
        ["hover_pick_skipped", hover_skipped],
        ["hover_pick_resolved", hover_resolved],
    ]
    if hover_total:
        hover_count_rows.append(
            ["hover_pick_skipped_ratio", "{:.3f}".format(hover_skipped / float(hover_total))]
        )

    operation_rows = []
    for name, stats in sorted(operations.items()):
        operation_rows.append(
            [
                name,
                stats["count"],
                _format_ms(stats["p50_ms"]),
                _format_ms(stats["p90_ms"]),
                _format_ms(stats["p95_ms"]),
                _format_ms(stats["max_ms"]),
            ]
        )

    slow_spans = sorted(
        ((name, stats) for name, stats in spans.items() if stats["count"]),
        key=lambda item: item[1]["p95_ms"] or 0.0,
        reverse=True,
    )[:20]
    span_rows = [
        [
            name,
            stats["count"],
            _format_ms(stats["p50_ms"]),
            _format_ms(stats["p90_ms"]),
            _format_ms(stats["p95_ms"]),
            _format_ms(stats["max_ms"]),
        ]
        for name, stats in slow_spans
    ]

    lines = [
        "# BIM Plan Edit Benchmark",
        "",
        "Generated: {}".format(result["generated_at"]),
        "",
        "Raw trace: `{}`".format(result["trace_path"]),
        "",
        "Operation timings: `{}`".format(result["operations_path"]),
        "",
        "Scenarios: {}".format(", ".join(result["scenarios"])),
        "",
        "## Readiness",
        "",
        _markdown_table(
            ["Event", "Status", "Count", "p95 ms", "Limit ms", "Max ms"],
            readiness_rows,
        ),
        "",
        "## Hover Pick Counts",
        "",
        _markdown_table(["Metric", "Value"], hover_count_rows),
        "",
        "## Event Latency",
        "",
        _markdown_table(["Event", "Count", "p50", "p90", "p95", "max"], event_rows),
        "",
        "## Runner Operation Latency",
        "",
        _markdown_table(["Operation", "Count", "p50", "p90", "p95", "max"], operation_rows),
        "",
        "## Slowest Spans",
        "",
        _markdown_table(["Span", "Count", "p50", "p90", "p95", "max"], span_rows),
        "",
    ]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def _make_output_paths(output_dir):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    root = Path(output_dir or tempfile.mkdtemp(prefix="freecad_plan_edit_benchmark_"))
    root.mkdir(parents=True, exist_ok=True)
    stem = "plan_edit_benchmark_{}".format(timestamp)
    return {
        "output_dir": root,
        "trace": root / "{}_trace.jsonl".format(stem),
        "operations": root / "{}_operations.jsonl".format(stem),
        "summary": root / "{}_summary.json".format(stem),
        "report": root / "{}_report.md".format(stem),
    }


def _select_scenarios(scenario_names):
    if not scenario_names or "all" in scenario_names:
        return [SCENARIOS[name] for name in ("small", "medium", "stress")]
    selected = []
    for name in scenario_names:
        if name not in SCENARIOS:
            raise ValueError(
                "Unknown scenario {!r}. Choose from: {}".format(
                    name,
                    ", ".join(sorted(SCENARIOS)),
                )
            )
        selected.append(SCENARIOS[name])
    return selected


def run(
    scenarios=None,
    iterations=1,
    output_dir=None,
    settle_ms=0,
    timer_settle_ms=120,
    keep_documents=False,
):
    """Run the Plan Edit benchmark and return a summary dictionary."""

    _require_freecad_gui()
    selected = _select_scenarios(list(scenarios or ["small", "medium"]))
    iterations = max(1, int(iterations or 1))
    paths = _make_output_paths(output_dir)

    old_perf = os.environ.get("FC_BIM_PLAN_EDIT_PERF")
    old_perf_log = os.environ.get("FC_BIM_PLAN_EDIT_PERF_LOG")
    os.environ["FC_BIM_PLAN_EDIT_PERF"] = "1"
    os.environ["FC_BIM_PLAN_EDIT_PERF_LOG"] = str(paths["trace"])

    try:
        with open(paths["operations"], "w", encoding="utf-8") as operations_handle:
            for iteration in range(iterations):
                for spec in selected:
                    _run_scenario(
                        spec,
                        iteration,
                        operations_handle,
                        int(settle_ms),
                        int(timer_settle_ms),
                        bool(keep_documents),
                    )
    finally:
        if old_perf is None:
            os.environ.pop("FC_BIM_PLAN_EDIT_PERF", None)
        else:
            os.environ["FC_BIM_PLAN_EDIT_PERF"] = old_perf
        if old_perf_log is None:
            os.environ.pop("FC_BIM_PLAN_EDIT_PERF_LOG", None)
        else:
            os.environ["FC_BIM_PLAN_EDIT_PERF_LOG"] = old_perf_log

    trace_rows = _read_jsonl(paths["trace"])
    operation_rows = _read_jsonl(paths["operations"])
    trace_summary = _summarize_trace(trace_rows)
    operation_summary = _summarize_operations(operation_rows)
    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scenarios": [spec.name for spec in selected],
        "iterations": iterations,
        "settle_ms": int(settle_ms),
        "timer_settle_ms": int(timer_settle_ms),
        "output_dir": str(paths["output_dir"]),
        "trace_path": str(paths["trace"]),
        "operations_path": str(paths["operations"]),
        "summary_path": str(paths["summary"]),
        "report_path": str(paths["report"]),
        "trace_summary": trace_summary,
        "operation_summary": operation_summary,
        "readiness": _build_readiness(trace_summary),
    }

    with open(paths["summary"], "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    _write_report(paths["report"], result)

    try:
        import FreeCAD

        FreeCAD.Console.PrintMessage("BIM Plan Edit benchmark report: {}\n".format(paths["report"]))
    except Exception:
        pass
    return result


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIOS) + ["all"],
        help="Scenario to run. May be passed multiple times. Defaults to small and medium.",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--output-dir", default="")
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=0,
        help="Qt event processing time after each immediate operation.",
    )
    parser.add_argument(
        "--timer-settle-ms",
        type=int,
        default=120,
        help="Qt event loop time for operations that intentionally queue QTimer work.",
    )
    parser.add_argument(
        "--keep-documents",
        action="store_true",
        help="Leave benchmark documents open after the run.",
    )
    return parser


def main(argv=None):
    parser = build_arg_parser()
    if argv is None:
        args, _unknown = parser.parse_known_args()
    else:
        args = parser.parse_args(argv)
    result = run(
        scenarios=args.scenario,
        iterations=args.iterations,
        output_dir=args.output_dir or None,
        settle_ms=args.settle_ms,
        timer_settle_ms=args.timer_settle_ms,
        keep_documents=args.keep_documents,
    )
    print("BIM Plan Edit benchmark report: {}".format(result["report_path"]))
    return result


if __name__ == "__main__":
    main()
