#!/usr/bin/env python3

# SPDX-License-Identifier: LGPL-2.1-or-later

"""Run the maintained BIM Plan Edit verification suite headlessly."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_SUITES = (
    "bimtests.TestBimPlanCore",
    "bimtests.TestBimPlanProviderSelectionGui",
    "bimtests.TestBimPlanEditGuiProvider",
    "bimtests.TestBimPlanEditGuiSymbols",
    "bimtests.TestBimPlanEditGuiOpenings",
    "bimtests.TestBimPlanEditGuiWalls",
    "bimtests.TestBimPlanEditGuiSpaces",
)

CORE_SUITE_MODULES = {
    "bimtests.TestBimPlanCore": "src.Mod.BIM.bimtests.TestBimPlanCore",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sync BIM Python sources into the build tree and run the maintained "
            "Plan Edit verification suites under xvfb-run."
        )
    )
    parser.add_argument(
        "--suite",
        action="append",
        dest="suites",
        help="Run only the given test suite. May be passed multiple times.",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip syncing Python sources into build/Mod/BIM before running.",
    )
    parser.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="Continue running remaining suites after the first failure.",
    )
    parser.add_argument(
        "--freecad",
        default="build/bin/FreeCAD",
        help="Path to the FreeCAD executable to use.",
    )
    return parser.parse_args()


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def resolve_freecad_executable(repo_root: Path, freecad_path: str) -> Path:
    candidate = Path(freecad_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def get_build_root(freecad_executable: Path) -> Path:
    for parent in (freecad_executable.parent, *freecad_executable.parents):
        if (parent / "Mod" / "BIM").exists() and (
            parent / "bin" / freecad_executable.name
        ).exists():
            return parent
    raise FileNotFoundError(
        f"Unable to determine build root from FreeCAD executable: {freecad_executable}"
    )


def sync_bim_python_tree(repo_root: Path, build_root: Path) -> None:
    source_dir = repo_root / "src/Mod/BIM/"
    build_dir = build_root / "Mod/BIM/"
    command = [
        "rsync",
        "-a",
        "--include=*/",
        "--include=*.py",
        "--exclude=*",
        f"{source_dir}/",
        f"{build_dir}/",
    ]
    subprocess.run(command, check=True, cwd=repo_root)


def get_core_test_environment(repo_root: Path, build_root: Path) -> dict[str, str]:
    pythonpath_parts = [
        str(build_root / "lib"),
        str(build_root / "Mod"),
        str(build_root / "Mod/BIM"),
        str(repo_root / "src/Mod/BIM"),
    ]
    current_pythonpath = os.environ.get("PYTHONPATH")
    if current_pythonpath:
        pythonpath_parts.append(current_pythonpath)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def run_suite(
    repo_root: Path, build_root: Path, freecad_executable: Path, suite: str
) -> tuple[int, float]:
    if suite in CORE_SUITE_MODULES:
        command = [sys.executable, "-m", "unittest", CORE_SUITE_MODULES[suite]]
        env = get_core_test_environment(repo_root, build_root)
    else:
        command = ["xvfb-run", "-a", str(freecad_executable), "-t", suite]
        env = None
    started_at = time.monotonic()
    result = subprocess.run(command, cwd=repo_root, env=env)
    elapsed = time.monotonic() - started_at
    return result.returncode, elapsed


def main() -> int:
    args = parse_args()
    repo_root = get_repo_root()
    freecad_executable = resolve_freecad_executable(repo_root, args.freecad)

    if not freecad_executable.exists():
        print(f"FreeCAD executable not found: {freecad_executable}", file=sys.stderr)
        return 2
    try:
        build_root = get_build_root(freecad_executable)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    suites = tuple(args.suites or DEFAULT_SUITES)

    if not args.no_sync:
        print(f"Syncing BIM Python sources into {build_root / 'Mod/BIM'}...", flush=True)
        sync_bim_python_tree(repo_root, build_root)

    failures: list[tuple[str, int]] = []
    durations: list[tuple[str, float]] = []

    for suite in suites:
        print(flush=True)
        print(f"=== {suite} ===", flush=True)
        returncode, elapsed = run_suite(repo_root, build_root, freecad_executable, suite)
        durations.append((suite, elapsed))
        if returncode != 0:
            failures.append((suite, returncode))
            if not args.continue_on_fail:
                break

    print()
    print("Summary")
    for suite, elapsed in durations:
        print(f"- {suite}: {elapsed:.1f}s")

    if failures:
        print()
        print("Failures")
        for suite, returncode in failures:
            print(f"- {suite}: exit code {returncode}")
        return 1

    print()
    print("All suites passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
