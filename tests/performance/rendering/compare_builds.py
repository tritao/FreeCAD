"""Collect deterministic rendering benchmark runs for a pre or post phase.

The collector starts a new FreeCAD process for every phase/fixture/run pair,
interleaves phase order when both phases are available, verifies fixture hashes
before every launch, and preserves the raw frame samples. Use
``compare_results.py`` to compare reports collected before and after a rebuild
of the same build directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--phase", choices=("pre", "post", "all"), default="all")
    parser.add_argument("--runs", type=int)
    parser.add_argument("--frames", type=int)
    parser.add_argument("--warmup", type=int)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--xvfb", action="store_true")
    args = parser.parse_args(argv)

    config_path = args.config.expanduser().resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    phases = _normalize_phases(config, config_path.parent, args.phase)
    fixtures = _normalize_fixtures(config, config_path.parent)
    settings = {
        "runs": args.runs if args.runs is not None else int(config.get("runs", 5)),
        "frames": args.frames if args.frames is not None else int(config.get("frames", 360)),
        "warmup": args.warmup if args.warmup is not None else int(config.get("warmup", 100)),
        "timeout_seconds": args.timeout,
        "xvfb": bool(args.xvfb or config.get("xvfb", False)),
        "step_degrees": float(config.get("step_degrees", 1.0)),
    }
    if settings["runs"] <= 0 or settings["frames"] <= 0 or settings["warmup"] < 0:
        raise ValueError("runs and frames must be positive; warmup must not be negative")

    output_dir = args.output_dir or Path(config.get("output_dir", "comparison-results"))
    if not output_dir.is_absolute():
        output_dir = config_path.parent / output_dir
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    _verify_fixture_hashes(fixtures)
    raw_results: list[dict[str, Any]] = []
    raw_paths: list[str] = []
    run_order = _run_orders(list(phases), settings["runs"])
    runner = Path(__file__).with_name("run_rendering.sh")

    for run_index, order in enumerate(run_order):
        for fixture in fixtures:
            for phase_name in order:
                phase = phases[phase_name]
                _verify_fixture_hash(fixture)
                raw_path = (
                    output_dir
                    / "raw"
                    / fixture["name"]
                    / phase_name
                    / f"run-{run_index + 1:02d}.json"
                )
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                result = _run_benchmark(
                    runner, phase_name, phase, fixture, raw_path, settings
                )
                raw_results.append(
                    {
                        "run_index": run_index,
                        "phase": phase_name,
                        "fixture": fixture["name"],
                        "path": str(raw_path),
                        "result": result,
                    }
                )
                raw_paths.append(str(raw_path))

    aggregates = _aggregate(raw_results)
    report = {
        "config": str(config_path),
        "settings": settings,
        "phases": phases,
        "fixtures": fixtures,
        "run_order": run_order,
        "raw_results": raw_paths,
        "aggregates": aggregates,
        "complete": True,
    }
    _write_json(output_dir / "comparison.json", report)
    (output_dir / "comparison.md").write_text(
        _markdown_report(report), encoding="utf-8"
    )
    print(json.dumps({"output_dir": str(output_dir), "complete": True}, indent=2))
    return 0


def _normalize_phases(
    config: dict[str, Any], base: Path, requested: str
) -> dict[str, dict[str, Any]]:
    values = config.get("phases", config.get("builds"))
    if not isinstance(values, dict):
        raise ValueError("config.phases must contain a pre and/or post entry")
    if requested == "all":
        selected = values
    else:
        if requested not in values:
            raise ValueError(f"config has no {requested!r} phase")
        selected = {requested: values[requested]}
    normalized: dict[str, dict[str, Any]] = {}
    for name, value in selected.items():
        if isinstance(value, str):
            entry = {"binary": value}
        elif isinstance(value, dict):
            entry = dict(value)
        else:
            raise ValueError(f"invalid phase entry for {name!r}")
        if "binary" not in entry:
            raise ValueError(f"phase {name!r} has no binary")
        entry["binary"] = str(_resolve_path(base, entry["binary"]))
        if not Path(entry["binary"]).is_file():
            raise ValueError(f"FreeCAD binary does not exist: {entry['binary']}")
        entry["name"] = str(name)
        normalized[str(name)] = entry
    if not normalized:
        raise ValueError("at least one phase is required")
    return normalized


def _normalize_fixtures(config: dict[str, Any], base: Path) -> list[dict[str, Any]]:
    values = config.get("fixtures")
    if not isinstance(values, list) or not values:
        raise ValueError("config.fixtures must be a non-empty list")
    hashes = config.get("fixture_hashes", {})
    normalized = []
    for value in values:
        if isinstance(value, str):
            entry = {"path": value}
        elif isinstance(value, dict):
            entry = dict(value)
        else:
            raise ValueError("invalid fixture entry")
        if "path" not in entry:
            raise ValueError("fixture has no path")
        path = _resolve_path(base, entry["path"])
        if not path.is_file():
            raise ValueError(f"fixture does not exist: {path}")
        entry["path"] = str(path)
        entry["name"] = str(entry.get("name", path.stem))
        expected_hash = entry.get(
            "sha256", hashes.get(str(entry["path"]), hashes.get(str(value)))
        )
        if not expected_hash:
            raise ValueError(f"fixture {entry['name']!r} has no required sha256")
        entry["sha256"] = str(expected_hash)
        normalized.append(entry)
    return normalized


def _resolve_path(base: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def _verify_fixture_hashes(fixtures: list[dict[str, Any]]) -> None:
    for fixture in fixtures:
        _verify_fixture_hash(fixture)


def _verify_fixture_hash(fixture: dict[str, Any]) -> None:
    actual = _sha256(Path(fixture["path"]))
    if actual != fixture["sha256"]:
        raise RuntimeError(
            f"fixture hash mismatch for {fixture['name']}: "
            f"expected {fixture['sha256']}, got {actual}"
        )


def _run_benchmark(
    runner: Path,
    phase_name: str,
    phase: dict[str, Any],
    fixture: dict[str, Any],
    output: Path,
    settings: dict[str, Any],
) -> dict[str, Any]:
    command = ["bash", str(runner)]
    if settings["xvfb"]:
        command.append("--xvfb")
    command += [
        "benchmark",
        fixture["path"],
        "--frames",
        str(settings["frames"]),
        "--warmup",
        str(settings["warmup"]),
        "--step-degrees",
        str(settings["step_degrees"]),
        "--output",
        str(output),
    ]
    environment = os.environ.copy()
    environment["FREECAD_BIN"] = phase["binary"]
    phase_lib = Path(phase["binary"]).resolve().parent.parent / "lib"
    existing_library_path = environment.get("LD_LIBRARY_PATH")
    environment["LD_LIBRARY_PATH"] = ":".join(
        value for value in (str(phase_lib), existing_library_path) if value
    )
    environment["FREECAD_BUILD_TYPE"] = str(phase.get("build_type", "unknown"))
    environment["FREECAD_RENDERING_PHASE"] = phase_name
    environment["FREECAD_RENDERING_ENVIRONMENT"] = (
        "xvfb" if settings["xvfb"] else "desktop"
    )
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=settings["timeout_seconds"],
    )
    if completed.returncode != 0 or not output.is_file():
        failure = output.with_suffix(".failure.json")
        _write_json(
            failure,
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
        raise RuntimeError(f"benchmark failed; diagnostics: {failure}")
    result = json.loads(output.read_text(encoding="utf-8"))
    if result.get("fixture_sha256") != fixture["sha256"]:
        raise RuntimeError(f"benchmark returned a mismatched fixture hash: {output}")
    if result.get("phase") != phase_name:
        raise RuntimeError(
            f"benchmark returned phase {result.get('phase')!r}, expected {phase_name!r}"
        )
    expected_commit = phase.get("commit")
    if expected_commit and result.get("freecad_commit") != expected_commit:
        raise RuntimeError(
            f"phase {phase_name!r} returned commit {result.get('freecad_commit')!r}, "
            f"expected {expected_commit!r}"
        )
    return result


def _run_orders(phase_names: list[str], runs: int) -> list[list[str]]:
    if set(phase_names) == {"pre", "post"} and len(phase_names) == 2:
        orders = [["pre", "post"], ["post", "pre"]]
    else:
        orders = [phase_names[i:] + phase_names[:i] for i in range(len(phase_names))]
    return [list(orders[index % len(orders)]) for index in range(runs)]


def _aggregate(raw_results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for item in raw_results:
        grouped.setdefault(item["fixture"], {}).setdefault(item["phase"], []).append(item)
    aggregates: dict[str, Any] = {}
    for fixture, phases in grouped.items():
        aggregates[fixture] = {}
        for phase, items in phases.items():
            frame_times = [
                float(sample)
                for item in items
                for sample in item["result"].get("frame_times_ms", [])
            ]
            process_medians = [
                float(item["result"]["median_frame_time_ms"]) for item in items
            ]
            aggregates[fixture][phase] = {
                "run_count": len(items),
                "frame_count": len(frame_times),
                "median_frame_time_ms": statistics.median(frame_times),
                "p95_frame_time_ms": _percentile(frame_times, 0.95),
                "median_of_process_medians_ms": statistics.median(process_medians),
                "process_median_cv_percent": _cv_percent(process_medians),
                "minimum_process_median_ms": min(process_medians),
                "maximum_process_median_ms": max(process_medians),
                "process_medians_ms": process_medians,
            }
    return aggregates


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Rendering benchmark collection",
        "",
        "| Fixture | Phase | Median (ms) | p95 (ms) | Process median CV |",
        "|---|---|---:|---:|---:|",
    ]
    for fixture, phases in report["aggregates"].items():
        for phase, values in phases.items():
            lines.append(
                f"| {fixture} | {phase} | {values['median_frame_time_ms']:.3f} | "
                f"{values['p95_frame_time_ms']:.3f} | "
                f"{values['process_median_cv_percent']:.2f}% |"
            )
    lines += ["", "Raw per-frame results are stored under `raw/`.", ""]
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _cv_percent(values: list[float]) -> float:
    if len(values) < 2 or statistics.mean(values) == 0:
        return 0.0
    return statistics.stdev(values) / statistics.mean(values) * 100.0


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
