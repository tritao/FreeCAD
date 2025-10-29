#!/usr/bin/env python3

"""
Generate an inventory of legacy OpenGL API usage across the FreeCAD sources.

Legacy in this context refers to immediate-mode drawing (`glBegin`, `glEnd`,
`glVertex*`, etc.), matrix stack manipulation, and fixed-function lighting /
material state that prevents us from moving towards a core-profile compatible
renderer.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator


# Directories that we skip when crawling. Adjust as needed.
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "build",
    "build_debug",
    "build_main",
    "build_async",
    "build_async_fastsignals",
    "build_async_fastsignals_dialogs",
    "build_fastsignals",
    "build_occt",
    "build_ortho",
    "dist",
    "doc",
    "docs",
    "examples",
    "tests",
    "3rdParty",
}

# File suffixes we consider part of the C/C++/ObjC++ source set.
SOURCE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".c++",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".h++",
    ".ipp",
    ".mm",
}

# Patterns grouped by category so we can emit a more informative report.
LEGACY_PATTERNS = {
    "ImmediateMode": [
        r"\bglBegin\s*\(",
        r"\bglEnd\s*\(",
        r"\bglVertex[234][ifds]\s*\(",
        r"\bglColor[34][ifds]\s*\(",
        r"\bglNormal[3][ifds]\s*\(",
        r"\bglTexCoord[1234][ifds]\s*\(",
        r"\bglEdgeFlag\s*\(",
        r"\bglIndex[ifds]\s*\(",
    ],
    "MatrixStack": [
        r"\bglMatrixMode\s*\(",
        r"\bglPushMatrix\s*\(",
        r"\bglPopMatrix\s*\(",
        r"\bglLoadIdentity\s*\(",
        r"\bglLoadMatrix[fd]\s*\(",
        r"\bglMultMatrix[fd]\s*\(",
        r"\bglTranslate[fd]\s*\(",
        r"\bglRotate[fd]\s*\(",
        r"\bglScale[fd]\s*\(",
        r"\bgluPerspective\s*\(",
        r"\bglOrtho\s*\(",
        r"\bglFrustum\s*\(",
    ],
    "FixedFunctionState": [
        r"\bglEnable\s*\(\s*GL_(COLOR_MATERIAL|LIGHTING|LIGHT\d+|FOG|TEXTURE_\dD|CLIP_PLANE\d)\s*\)",
        r"\bglDisable\s*\(\s*GL_(COLOR_MATERIAL|LIGHTING|LIGHT\d+|FOG|TEXTURE_\dD|CLIP_PLANE\d)\s*\)",
        r"\bglLight[if]\s*\(",
        r"\bglLightModel[if]\s*\(",
        r"\bglMaterial[if]\s*\(",
        r"\bglTexEnv[if]\s*\(",
        r"\bglTexGeni\s*\(",
        r"\bglShadeModel\s*\(",
        r"\bglPolygonMode\s*\(",
        r"\bglFogi\s*\(",
        r"\bglFogf\s*\(",
        r"\bglFogfv\s*\(",
        r"\bglColorMaterial\s*\(",
    ],
    "LegacyStateManagement": [
        r"\bglPushAttrib\s*\(",
        r"\bglPopAttrib\s*\(",
        r"\bglClientActiveTexture\s*\(",
        r"\bglEnableClientState\s*\(",
        r"\bglDisableClientState\s*\(",
        r"\bglVertexPointer\s*\(",
        r"\bglNormalPointer\s*\(",
        r"\bglColorPointer\s*\(",
        r"\bglTexCoordPointer\s*\(",
    ],
}

# High-impact files we always surface in the report.
HIGH_IMPACT_HINTS = [
    "GLPainter.cpp",
    "NavigationStyle.cpp",
    "NaviCube.cpp",
    "Overlay.cpp",
    "SoTextLabel.cpp",
    "View3DInventorViewer.cpp",
    "SoFCShapeObject.cpp",
    "SoFCMeshObject.cpp",
    "SoBrep",
]


@dataclasses.dataclass
class Hit:
    category: str
    symbol: str
    relpath: Path
    lineno: int
    line: str


def iter_source_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Strip directories we should skip.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            if Path(name).suffix.lower() in SOURCE_SUFFIXES:
                yield Path(dirpath, name)


def compile_patterns() -> dict[str, list[tuple[re.Pattern[str], str]]]:
    compiled: dict[str, list[tuple[re.Pattern[str], str]]] = {}
    for category, expressions in LEGACY_PATTERNS.items():
        compiled[category] = []
        for expr in expressions:
            compiled[category].append((re.compile(expr), expr))
    return compiled


def find_hits(root: Path, compiled_patterns: dict[str, list[tuple[re.Pattern[str], str]]]) -> list[Hit]:
    hits: list[Hit] = []
    for file_path in iter_source_files(root):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:  # pragma: no cover - diagnostic output only
            print(f"[warn] failed to read {file_path}: {exc}", file=sys.stderr)
            continue

        for lineno, line in enumerate(text.splitlines(), 1):
            for category, patterns in compiled_patterns.items():
                for regex, expr in patterns:
                    if regex.search(line):
                        symbol = extract_symbol(line, expr)
                        hits.append(
                            Hit(
                                category=category,
                                symbol=symbol,
                                relpath=file_path.relative_to(root),
                                lineno=lineno,
                                line=line.strip(),
                            )
                        )
    return hits


def extract_symbol(line: str, expr: str) -> str:
    """Attempt to infer the API symbol matched by the regex."""
    # Simple heuristic: look for glSomething pattern in the line.
    match = re.search(r"\b(gl[A-Za-z0-9_]+)\b", line)
    if match:
        return match.group(1)
    # Fall back to the expression if we couldn't find a symbol.
    return expr


def classify_module(relpath: Path) -> str:
    parts = relpath.parts
    if not parts:
        return "root"

    # Derive a module name based on the path within the FreeCAD tree.
    if parts[0] == "src":
        if len(parts) >= 2 and parts[1] == "Mod":
            if len(parts) >= 3:
                return f"Mod/{parts[2]}"
            return "Mod"
        return parts[1] if len(parts) >= 2 else "src"

    # For nested repositories (e.g. coin), expose the top-level directory.
    return parts[0]


def summarise_hits(hits: Iterable[Hit]) -> dict[str, dict[str, list[Hit]]]:
    modules: dict[str, dict[str, list[Hit]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for hit in hits:
        module = classify_module(hit.relpath)
        file_key = str(hit.relpath)
        modules[module][file_key].append(hit)
    return modules


def highlight_files(files: Iterable[str]) -> list[str]:
    highlighted = []
    for filename in files:
        if any(hint in filename for hint in HIGH_IMPACT_HINTS):
            highlighted.append(filename)
    return sorted(set(highlighted))


def format_report(root: Path, modules: dict[str, dict[str, list[Hit]]], output_format: str = "markdown") -> str:
    timestamp = _dt.datetime.now().isoformat(timespec="seconds")
    if output_format == "json":
        serialisable = {
            "generated_at": timestamp,
            "root": str(root),
            "modules": {
                module: {
                    "file_count": len(files),
                    "hit_count": sum(len(hits) for hits in files.values()),
                    "files": {
                        filename: [
                            {
                                "category": hit.category,
                                "symbol": hit.symbol,
                                "line_number": hit.lineno,
                                "source_line": hit.line,
                            }
                            for hit in sorted(file_hits, key=lambda h: h.lineno)
                        ]
                        for filename, file_hits in sorted(files.items())
                    },
                }
                for module, files in sorted(modules.items())
            },
        }
        return json.dumps(serialisable, indent=2)

    lines: list[str] = []
    lines.append("# Legacy OpenGL Usage Report")
    lines.append("")
    lines.append(f"- Generated: {timestamp}")
    lines.append(f"- Root: `{root}`")
    total_hits = sum(len(hits) for files in modules.values() for hits in files.values())
    total_files = sum(len(files) for files in modules.values())
    lines.append(f"- Total hits: {total_hits} across {total_files} files")
    lines.append("")

    lines.append("## Summary by module")
    for module, files in sorted(modules.items(), key=lambda item: -sum(len(hits) for hits in item[1].values())):
        hit_count = sum(len(hits) for hits in files.values())
        lines.append(f"- `{module}`: {hit_count} hits in {len(files)} files")
    lines.append("")

    lines.append("## High-impact files")
    highlighted: list[str] = []
    for module_files in modules.values():
        highlighted.extend(highlight_files(module_files.keys()))
    if highlighted:
        for filename in sorted(set(highlighted)):
            lines.append(f"- `{filename}`")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Detailed breakdown")
    for module, files in sorted(modules.items()):
        lines.append(f"### Module `{module}`")
        for filename, file_hits in sorted(files.items()):
            lines.append(f"- `{filename}` ({len(file_hits)} hit{'s' if len(file_hits) != 1 else ''})")
            for hit in sorted(file_hits, key=lambda h: (h.category, h.lineno)):
                preview = hit.line.strip()
                if len(preview) > 100:
                    preview = preview[:97] + "..."
                lines.append(
                    f"  - L{hit.lineno}: `{hit.symbol}` [{hit.category}] — `{preview}`"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report legacy OpenGL usage.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "src",
        help="Root directory to scan (defaults to FreeCAD/src relative to this script).",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if not root.exists():
        print(f"error: root path '{root}' does not exist", file=sys.stderr)
        return 2

    patterns = compile_patterns()
    hits = find_hits(root, patterns)
    modules = summarise_hits(hits)
    report = format_report(root, modules, output_format=args.format)
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

