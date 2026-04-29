#!/usr/bin/env python3

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Run the BIM Plan Edit benchmark under the GUI test harness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync BIM Python sources into the build tree and run the Plan Edit "
            "benchmark under xvfb-run/FreeCAD -t."
        )
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help=(
            "Benchmark scenario to run. May be passed multiple times. "
            "Defaults to the benchmark module default."
        ),
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for benchmark trace, operations, summary, and report files.",
    )
    parser.add_argument("--settle-ms", type=int, default=0)
    parser.add_argument("--timer-settle-ms", type=int, default=120)
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip syncing Python sources into build/Mod/BIM before running.",
    )
    parser.add_argument(
        "--freecad",
        default="build/bin/FreeCAD",
        help="Path to the FreeCAD executable to use.",
    )
    return parser.parse_args()


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def sync_bim_python_tree(repo_root: Path) -> None:
    source_dir = repo_root / "src/Mod/BIM/"
    build_dir = repo_root / "build/Mod/BIM/"
    command = [
        "rsync",
        "-a",
        "--checksum",
        "--include=*/",
        "--include=*.py",
        "--exclude=*",
        str(source_dir),
        str(build_dir),
    ]
    subprocess.run(command, check=True, cwd=repo_root)


def make_default_output_dir(repo_root: Path) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return repo_root / "build" / "plan_edit_benchmarks" / timestamp


def write_benchmark_test_module(
    temp_dir: Path,
    scenarios: list[str] | None,
    iterations: int,
    output_dir: Path,
    settle_ms: int,
    timer_settle_ms: int,
) -> str:
    module_name = "plan_edit_benchmark_headless"
    module_path = temp_dir / f"{module_name}.py"
    module_path.write_text(
        textwrap.dedent(f"""
            import json
            import unittest


            class PlanEditBenchmarkHeadless(unittest.TestCase):
                def test_plan_edit_benchmark(self):
                    import bimplan.benchmark as benchmark

                    result = benchmark.run(
                        scenarios={scenarios!r},
                        iterations={int(iterations)!r},
                        output_dir={str(output_dir)!r},
                        settle_ms={int(settle_ms)!r},
                        timer_settle_ms={int(timer_settle_ms)!r},
                    )
                    print("PLAN_EDIT_BENCHMARK_REPORT", result["report_path"])
                    print("PLAN_EDIT_BENCHMARK_SUMMARY", result["summary_path"])
                    print("PLAN_EDIT_BENCHMARK_TRACE", result["trace_path"])
                    failing = [
                        row
                        for row in result.get("readiness", ())
                        if row.get("status") == "fail"
                    ]
                    if failing:
                        print(
                            "PLAN_EDIT_BENCHMARK_FAILING",
                            json.dumps(failing, sort_keys=True),
                        )
                    self.assertFalse(failing)
            """).lstrip(),
        encoding="utf-8",
    )
    return module_name


def print_readiness_summary(output_dir: Path) -> None:
    summaries = sorted(output_dir.glob("*_summary.json"))
    if not summaries:
        return
    summary_path = summaries[-1]
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    print()
    print("Readiness")
    for row in data.get("readiness", ()):
        status = row.get("status")
        event = row.get("event")
        count = row.get("count", 0)
        p95 = row.get("p95_ms")
        limit = row.get("limit_ms")
        if p95 is None:
            print(f"- {event}: {status} ({count} samples)")
        else:
            print(f"- {event}: {status} p95={p95:.3f}ms limit={limit:.3f}ms")


def main() -> int:
    args = parse_args()
    repo_root = get_repo_root()
    freecad_executable = (repo_root / args.freecad).resolve()
    output_dir = Path(args.output_dir) if args.output_dir else make_default_output_dir(repo_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not freecad_executable.exists():
        print(f"FreeCAD executable not found: {freecad_executable}", file=sys.stderr)
        return 2

    if not args.no_sync:
        print("Syncing BIM Python sources into build/Mod/BIM...", flush=True)
        sync_bim_python_tree(repo_root)

    with tempfile.TemporaryDirectory(prefix="freecad_plan_edit_benchmark_test_") as temp:
        module_name = write_benchmark_test_module(
            Path(temp),
            args.scenario,
            max(1, int(args.iterations or 1)),
            output_dir,
            int(args.settle_ms or 0),
            int(args.timer_settle_ms or 0),
        )
        command = [
            "xvfb-run",
            "-a",
            str(freecad_executable),
            "-P",
            temp,
            "-t",
            module_name,
        ]
        result = subprocess.run(command, cwd=repo_root)

    print_readiness_summary(output_dir)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
