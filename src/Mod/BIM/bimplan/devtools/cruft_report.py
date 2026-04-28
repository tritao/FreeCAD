#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Lightweight local report for recurring bimplan cruft patterns."""

from __future__ import annotations

import ast
import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[3]

PY_FILES = tuple(sorted(ROOT.rglob("*.py")))

SAME_API_BOUNCE_PATTERNS = {
    "spaces": re.compile(r"\bsession\.spaces\."),
    "selection": re.compile(r"\bsession\.selection\."),
    "providers": re.compile(r"\bsession\.providers\."),
    "overlays": re.compile(r"\bsession\.overlays\."),
    "visibility": re.compile(r"\bsession\.visibility\."),
    "document_visuals": re.compile(r"\bsession\.document_visuals\."),
    "wall_edit": re.compile(r"\bsession\.wall_edit\."),
    "wall_relations": re.compile(r"\bsession\.wall_relations\."),
    "windows": re.compile(r"\bsession\.windows\."),
}

OWNER_FILE_HINTS = {
    "spaces": ("tools/spaces.py", "tools/space_"),
    "selection": ("selection/",),
    "providers": ("providers/",),
    "overlays": ("overlays/",),
    "visibility": ("object_visibility.py",),
    "document_visuals": ("document_visuals.py",),
    "wall_edit": ("tools/wall_edit.py",),
    "wall_relations": ("tools/wall_relations.py",),
    "windows": ("tools/window_create.py",),
}

SESSION_PRIVATE_PATTERN = re.compile(r"\bsession\._[A-Za-z0-9_]+\b")
GENERATED_BINDER_PATTERN = re.compile(r"_PLAN_.*_BOUND_METHODS|def _bind_.*call|setattr\(Plan.*API")
FORWARDER_SURFACE_PATTERN = re.compile(r"_PLAN_[A-Z0-9_]*(?:FORWARDERS|BOUND_METHODS)\b")
FLAT_SELECTION_API_PATTERN = re.compile(
    r"\bsession\.selection\.(?!"
    r"state\b|refresh\b|sync\b|activation\b|hover\b|picking\b|targets\b|"
    r"selection_changes_suppressed\b|get_selected_objects\b"
    r")[A-Za-z_][A-Za-z0-9_]*\s*\("
)
FLAT_OVERLAYS_API_PATTERN = re.compile(
    r"\bsession\.overlays\.(?!"
    r"manager\b|geometry\b|walls\b|openings\b|symbols\b|spaces\b|providers\b|"
    r"queue_plan_overlay_visual_refresh\b|queue_plan_overlay_view_scale_refresh\b|"
    r"consume_dirty_plan_visuals\b"
    r")[A-Za-z_][A-Za-z0-9_]*\s*\("
)
OWNED_API_NAMES = (
    "selection",
    "providers",
    "spaces",
    "overlays",
    "visibility",
    "document_visuals",
    "wall_edit",
    "wall_relations",
    "windows",
    "openings",
    "symbols",
    "viewport",
    "performance",
    "task_panels",
    "lifecycle",
    "input",
    "snap",
    "storey",
)
OWNED_API_PROBE_PATTERNS = tuple(
    re.compile(rf"\b(?:getattr|hasattr)\(\s*session\.{name}\b") for name in OWNED_API_NAMES
) + tuple(
    re.compile(rf"\b(?:getattr|hasattr)\(\s*session\s*,\s*['\"]{name}['\"]")
    for name in OWNED_API_NAMES
)


@dataclass(frozen=True)
class Match:
    path: str
    lineno: int
    text: str


def relpath(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def line_matches(pattern: re.Pattern[str], text: str, path: Path) -> list[Match]:
    matches: list[Match] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            matches.append(Match(relpath(path), lineno, line.strip()))
    return matches


def top_level_reexports() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        mod = ast.parse(file_text(path))
        lines = file_text(path).splitlines()
        for node in mod.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            value = node.value
            if not isinstance(target, ast.Name):
                continue
            if not isinstance(value, ast.Attribute) or not isinstance(value.value, ast.Name):
                continue
            source_name = value.value.id
            if not (
                source_name.startswith("plan_")
                or source_name.startswith("overlay_")
                or source_name.startswith("provider_")
            ):
                continue
            text = lines[node.lineno - 1].strip()
            matches.append(Match(relpath(path), node.lineno, text))
    return matches


def generated_binders() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        if relpath(path).endswith("devtools/cruft_report.py"):
            continue
        matches.extend(line_matches(GENERATED_BINDER_PATTERN, file_text(path), path))
    return matches


def forwarding_surfaces() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        rel = relpath(path)
        if rel.endswith("devtools/cruft_report.py"):
            continue
        matches.extend(line_matches(FORWARDER_SURFACE_PATTERN, file_text(path), path))
    return matches


def flat_selection_api_calls() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        rel = relpath(path)
        if rel.endswith("devtools/cruft_report.py"):
            continue
        matches.extend(line_matches(FLAT_SELECTION_API_PATTERN, file_text(path), path))
    return matches


def flat_overlays_api_calls() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        rel = relpath(path)
        if rel.endswith("devtools/cruft_report.py"):
            continue
        matches.extend(line_matches(FLAT_OVERLAYS_API_PATTERN, file_text(path), path))
    return matches


def same_api_bounce_calls() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        rel = relpath(path)
        text = file_text(path)
        for api_name, pattern in SAME_API_BOUNCE_PATTERNS.items():
            owner_hints = OWNER_FILE_HINTS[api_name]
            if not any(hint in rel for hint in owner_hints):
                continue
            for match in line_matches(pattern, text, path):
                matches.append(match)
    return matches


def session_private_reads() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        rel = relpath(path)
        text = file_text(path)
        if (
            any(hint in rel for hints in OWNER_FILE_HINTS.values() for hint in hints)
            or "runtime/session_state.py" in rel
            or "runtime/session.py" in rel
        ):
            continue
        matches.extend(line_matches(SESSION_PRIVATE_PATTERN, text, path))
    return matches


def owned_api_probes() -> list[Match]:
    matches: list[Match] = []
    for path in PY_FILES:
        text = file_text(path)
        for pattern in OWNED_API_PROBE_PATTERNS:
            matches.extend(line_matches(pattern, text, path))
    matches.sort(key=lambda item: (item.path, item.lineno, item.text))
    return matches


def largest_files(limit: int = 12) -> list[tuple[str, int]]:
    rows = []
    for path in PY_FILES:
        rows.append((relpath(path), len(file_text(path).splitlines())))
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows[:limit]


def longest_functions(limit: int = 15) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for path in PY_FILES:
        mod = ast.parse(file_text(path))
        for node in ast.walk(mod):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                rows.append((relpath(path), node.name, end_lineno - node.lineno + 1))
    rows.sort(key=lambda item: item[2], reverse=True)
    return rows[:limit]


def print_section(title: str, rows: list[str]) -> None:
    print(f"\n## {title}")
    if not rows:
        print("(none)")
        return
    for row in rows:
        print(row)


def format_match_rows(matches: list[Match], limit: int = 20) -> list[str]:
    rows = [f"{m.path}:{m.lineno}: {m.text}" for m in matches[:limit]]
    if len(matches) > limit:
        rows.append(f"... {len(matches) - limit} more")
    return rows


def _print_report() -> None:
    print(f"# bimplan cruft report\nroot: {ROOT}")

    print_section(
        "Largest Files",
        [f"{path}: {count} lines" for path, count in largest_files()],
    )
    print_section(
        "Longest Functions",
        [f"{path}: {name} ({count} lines)" for path, name, count in longest_functions()],
    )
    print_section("Top-level Reexports", format_match_rows(top_level_reexports()))
    print_section("Generated Binder Patterns", format_match_rows(generated_binders()))
    print_section("Forwarder Surfaces", format_match_rows(forwarding_surfaces()))
    print_section(
        "Flat session.selection Calls",
        format_match_rows(flat_selection_api_calls()),
    )
    print_section(
        "Flat session.overlays Calls",
        format_match_rows(flat_overlays_api_calls()),
    )
    print_section(
        "Internal session.<same_api> Bounce Calls", format_match_rows(same_api_bounce_calls())
    )
    print_section("Owned API getattr/hasattr Probes", format_match_rows(owned_api_probes()))
    print_section("session._* Reads Outside Owners", format_match_rows(session_private_reads()))


def _check_grouped_api() -> int:
    selection_matches = flat_selection_api_calls()
    overlay_matches = flat_overlays_api_calls()
    if not selection_matches and not overlay_matches:
        print("Grouped API check passed: no flat session.selection/session.overlays calls.")
        return 0

    print("# Grouped API check failed")
    print_section("Flat session.selection Calls", format_match_rows(selection_matches))
    print_section("Flat session.overlays Calls", format_match_rows(overlay_matches))
    return 1


def _check_forwarder_surface_limit(max_count: int) -> int:
    matches = forwarding_surfaces()
    if len(matches) <= max_count:
        print("Forwarder surface check passed: " f"{len(matches)} match(es), limit {max_count}.")
        return 0

    print("# Forwarder surface check failed\n" f"found {len(matches)} match(es), limit {max_count}")
    print_section("Forwarder Surfaces", format_match_rows(matches, limit=len(matches)))
    return 1


def _check_no_private_session_reads() -> int:
    matches = session_private_reads()
    if not matches:
        print("Private session read check passed: no session._* reads outside owners.")
        return 0

    print("# Private session read check failed")
    print_section("session._* Reads Outside Owners", format_match_rows(matches, limit=len(matches)))
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report recurring BIM Plan Edit architecture cruft patterns.",
    )
    parser.add_argument(
        "--check-grouped-api",
        action="store_true",
        help=(
            "Fail if owned code calls flat session.selection/session.overlays methods "
            "instead of grouped services."
        ),
    )
    parser.add_argument(
        "--max-forwarder-surfaces",
        type=int,
        default=None,
        help=(
            "Fail if the number of forwarder surface matches is greater than this "
            "baseline. Use this while retiring existing forwarder surfaces."
        ),
    )
    parser.add_argument(
        "--check-no-private-session-reads",
        action="store_true",
        help="Fail if code outside state/session owners reads session._* private state.",
    )
    args = parser.parse_args()

    if args.check_grouped_api:
        grouped_api_status = _check_grouped_api()
        if grouped_api_status:
            return grouped_api_status

    if args.max_forwarder_surfaces is not None:
        forwarder_status = _check_forwarder_surface_limit(args.max_forwarder_surfaces)
        if forwarder_status:
            return forwarder_status

    if args.check_no_private_session_reads:
        private_read_status = _check_no_private_session_reads()
        if private_read_status:
            return private_read_status

    if (
        args.check_grouped_api
        or args.max_forwarder_surfaces is not None
        or args.check_no_private_session_reads
    ):
        return 0

    _print_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
