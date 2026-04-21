"""Command-line front end for the binding stub generation pipeline.

This module is intentionally thin. Its job is to expose a stable user-facing
entrypoint, resolve repository-relative paths, and dispatch to the generator in
either ``generate`` or ``check`` mode.

Keep policy and parsing logic out of this file:
- binding discovery belongs in ``generator``
- syntax helpers belong in ``parsing``
- shared constants and defaults belong in ``model``

The ``check`` flow is also coordinated here so the external tools invoked after
stub generation, and the log files they write, are defined in one place.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from .generator import (
    collect_binding_classes,
    collect_methods,
    collect_type_registrations,
    load_stub_signature_overrides,
    markdown_report,
    write_outputs,
)
from .model import DEFAULT_CLASS_OVERLAY_DIR, DEFAULT_OVERLAY_DIR, DEFAULT_OVERRIDE_DIR
from .parsing import iter_source_files

DESCRIPTION = """Generate type-checker stubs for FreeCAD Python bindings.

The command inventories hand-written C++ Python registrations, merges them with
binding .pyi class specs and curated overlays, and writes public import-shaped
stubs for type-checker use.
"""

DEFAULT_STUBS_OUT_DIR = Path("src/Tools/bindings/stubs/generated")
PYRIGHT_VERSION = "1.1.408"
PYREFLY_VERSION = "0.60.2"


def resolve_optional_dir(root: Path, path: Path | None, default: Path | None = None) -> Path | None:
    if path is not None:
        return path if path.is_absolute() else root / path
    if default is None:
        return None
    candidate = root / default
    return candidate if candidate.exists() else None


def add_common_path_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="FreeCAD source checkout root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("src"),
        help="Source directory to scan, relative to --root unless absolute. Defaults to src.",
    )


def add_generation_args(parser: argparse.ArgumentParser) -> None:
    add_common_path_args(parser)
    parser.add_argument(
        "--out-dir",
        type=Path,
        help=(
            "Directory for generated debug skeletons and merged public stub output. "
            "If omitted, print the inventory report as Markdown."
        ),
    )
    parser.add_argument(
        "--overlay-dir",
        type=Path,
        help=(
            "Curated stub overlay directory to apply over generated skeletons. "
            f"Defaults to {DEFAULT_OVERLAY_DIR} when that directory exists."
        ),
    )
    parser.add_argument(
        "--override-dir",
        type=Path,
        help=(
            "Curated PyCXX source-signature override directory for generated skeletons. "
            f"Defaults to {DEFAULT_OVERRIDE_DIR} when that directory exists."
        ),
    )
    parser.add_argument(
        "--class-overlay-dir",
        type=Path,
        help=(
            "Curated checker-only class overlay directory to merge into generated public stubs. "
            f"Defaults to {DEFAULT_CLASS_OVERLAY_DIR} when that directory exists."
        ),
    )
    parser.add_argument(
        "--no-overlays",
        action="store_true",
        help="Do not apply curated stub overlays to the merged output.",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    if argv and argv[0] == "check":
        parser = argparse.ArgumentParser(
            description="Generate binding stubs and run the smoke type checks."
        )
        add_generation_args(parser)
        parser.add_argument(
            "--log-dir",
            type=Path,
            help="Optional directory for individual generator and checker logs.",
        )
        parser.set_defaults(command="check")
        return parser.parse_args(argv[1:])

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    add_generation_args(parser)
    parser.set_defaults(command="generate")
    return parser.parse_args(argv)


def write_log(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_logged_command(
    name: str,
    cmd: list[str],
    cwd: Path,
    log_dir: Path | None,
) -> tuple[int, str]:
    if log_dir is None:
        result = subprocess.run(cmd, cwd=cwd)
        return result.returncode, ""

    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = result.stdout + result.stderr
    write_log(log_dir / f"{name}.log", output)
    return result.returncode, output


def run_generate(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    source_dir = args.source_dir if args.source_dir.is_absolute() else root / args.source_dir
    if not source_dir.exists():
        sys.stderr.write(f"source directory does not exist: {source_dir}\n")
        return 2

    type_registrations = collect_type_registrations(root, list(iter_source_files(root, source_dir)))
    methods = collect_methods(root, source_dir)
    classes = collect_binding_classes(root, source_dir, type_registrations)
    override_dir = resolve_optional_dir(root, args.override_dir, DEFAULT_OVERRIDE_DIR)
    stub_signature_overrides = (
        load_stub_signature_overrides(override_dir, methods, type_registrations)
        if override_dir
        else {}
    )
    overlay_dir = (
        None
        if args.no_overlays
        else resolve_optional_dir(root, args.overlay_dir, DEFAULT_OVERLAY_DIR)
    )
    class_overlay_dir = (
        None
        if args.no_overlays
        else resolve_optional_dir(root, args.class_overlay_dir, DEFAULT_CLASS_OVERLAY_DIR)
    )

    if args.out_dir:
        out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
        overlay_count = write_outputs(
            out_dir,
            root,
            methods,
            classes,
            type_registrations,
            stub_signature_overrides,
            overlay_dir,
            class_overlay_dir,
        )
        summary = (
            f"Wrote {len(methods)} registrations and {len(classes)} class bindings to {out_dir} "
            f"({overlay_count} overlay stub files applied)"
        )
        print(summary)
        if getattr(args, "log_dir", None):
            log_dir = args.log_dir.resolve()
            write_log(log_dir / "python-stubs-generate.log", summary + "\n")
    else:
        sys.stdout.write(markdown_report(methods))
    return 0


def run_check(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if args.out_dir is None:
        args.out_dir = DEFAULT_STUBS_OUT_DIR
    generation_code = run_generate(args)
    if generation_code != 0:
        return generation_code

    stubs_dir = root / "src/Tools/bindings/stubs"
    log_dir = args.log_dir.resolve() if args.log_dir else None

    pyright_code, _ = run_logged_command(
        "python-stubs-pyright",
        ["npx", "--yes", f"pyright@{PYRIGHT_VERSION}", "-p", "smoke/pyrightconfig.json"],
        stubs_dir,
        log_dir,
    )
    pyrefly_code, _ = run_logged_command(
        "python-stubs-pyrefly",
        [
            "uvx",
            "--from",
            f"pyrefly=={PYREFLY_VERSION}",
            "pyrefly",
            "check",
            "--config",
            "smoke/pyrefly.toml",
        ],
        stubs_dir,
        log_dir,
    )
    return 0 if pyright_code == 0 and pyrefly_code == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "check":
        return run_check(args)
    return run_generate(args)
