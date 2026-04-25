#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Lightweight local report for recurring bimplan cruft patterns."""

from __future__ import annotations

import ast
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


def main() -> int:
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
    print_section(
        "Internal session.<same_api> Bounce Calls", format_match_rows(same_api_bounce_calls())
    )
    print_section("session._* Reads Outside Owners", format_match_rows(session_private_reads()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
