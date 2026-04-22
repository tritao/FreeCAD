"""Runtime existence audit for curated source-adjacent stub inputs.

This module complements the static stub checks. It verifies that curated
source-adjacent APIs still map to real runtime objects in a live FreeCAD
interpreter, without trying to execute the full method surface.

Scope:
- top-level functions declared in import-stable ``*.module.pyi`` files

The audit intentionally skips helper-only compatibility shims, GUI bootstrap
surfaces, and type stubs that need explicit runtime construction. It does not
try to validate full call signatures. Its purpose is to catch missing or
misplaced import-stable symbols that would otherwise look plausible in the
generated public stubs.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from textwrap import dedent

from .model import MODULE_STUB_PYI_SUFFIX
from .parsing import iter_module_stub_pyi_files

SUPPORTED_RUNTIME_MODULES = {
    "FreeCAD",
    "FreeCAD.Console",
    "FreeCAD.Qt",
    "FreeCAD.Units",
    "Part",
}


@dataclass(frozen=True)
class RuntimeAuditIssue:
    kind: str
    target: str
    source: str
    error: str


@dataclass(frozen=True)
class RuntimeAuditReport:
    runtime_executable: Path
    files_checked: int
    symbols_checked: int
    issues: tuple[RuntimeAuditIssue, ...]
    command_output: str

    @property
    def ok(self) -> bool:
        return not self.issues

    def render(self, root: Path) -> str:
        exe = self.runtime_executable if self.runtime_executable.is_absolute() else root / self.runtime_executable
        lines = [
            f"Runtime executable: {exe}",
            f"Curated stub files checked: {self.files_checked}",
            f"Runtime-backed symbols checked: {self.symbols_checked}",
        ]
        if self.ok:
            lines.append("No runtime mapping issues found.")
            return "\n".join(lines) + "\n"

        lines.append(f"{len(self.issues)} runtime mapping issues found:")
        for issue in self.issues:
            source = issue.source
            try:
                source = str(Path(source).relative_to(root))
            except ValueError:
                pass
            lines.append(f"- {issue.target}: {issue.error} ({source})")
        return "\n".join(lines) + "\n"


def default_runtime_executable(root: Path) -> Path:
    for candidate in (
        root / "build/bin/FreeCAD",
        root / "build/bin/FreeCADCmd",
    ):
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def module_name_from_stub_path(path: Path) -> str:
    module_name = path.name.removesuffix(MODULE_STUB_PYI_SUFFIX)
    if not module_name:
        raise ValueError(f"{path}: invalid module stub filename")
    return module_name


def runtime_manifest(root: Path, source_dir: Path) -> tuple[list[dict[str, str]], int]:
    manifest: list[dict[str, str]] = []
    files_checked = 0

    for path in sorted(iter_module_stub_pyi_files(root, source_dir)):
        module_name = module_name_from_stub_path(path)
        if module_name not in SUPPORTED_RUNTIME_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        files_checked += 1
        seen_functions: set[str] = set()
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name in seen_functions:
                continue
            seen_functions.add(node.name)
            manifest.append(
                {
                    "kind": "function",
                    "module": module_name,
                    "name": node.name,
                    "source": str(path),
                }
            )

    return manifest, files_checked


def runtime_check_script(manifest_path: Path, result_path: Path) -> str:
    return dedent(
        f"""
        import importlib
        import json
        from pathlib import Path

        manifest = json.loads(Path(r"{manifest_path}").read_text(encoding="utf-8"))
        result_path = Path(r"{result_path}")

        cache = {{}}
        issues = []

        def resolve_module_target(module_name: str):
            cached = cache.get(module_name)
            if cached is not None:
                return cached

            try:
                target = importlib.import_module(module_name)
            except Exception as import_error:
                parts = module_name.split(".")
                try:
                    target = importlib.import_module(parts[0])
                    for part in parts[1:]:
                        target = getattr(target, part)
                except Exception:
                    cache[module_name] = import_error
                    return import_error

            cache[module_name] = target
            return target

        for entry in manifest:
            kind = entry["kind"]
            module_name = entry["module"]
            target = resolve_module_target(module_name)
            if isinstance(target, Exception):
                issues.append(
                    {{
                        "kind": kind,
                        "target": module_name if kind == "function" else (
                            f"{{module_name}}.{{entry['class_name']}}" if kind == "class"
                            else f"{{module_name}}.{{entry['class_name']}}.{{entry['name']}}"
                        ),
                        "source": entry["source"],
                        "error": f"module import failed: {{type(target).__name__}}: {{target}}",
                    }}
                )
                continue

            if kind == "function":
                name = entry["name"]
                if not hasattr(target, name):
                    issues.append(
                        {{
                            "kind": kind,
                            "target": f"{{module_name}}.{{name}}",
                            "source": entry["source"],
                            "error": "missing runtime attribute on module target",
                        }}
                    )
                continue

            class_name = entry["class_name"]
            klass = getattr(target, class_name, None)
            if klass is None:
                issues.append(
                    {{
                        "kind": kind,
                        "target": f"{{module_name}}.{{class_name}}",
                        "source": entry["source"],
                        "error": "missing runtime class on module target",
                    }}
                )
                continue

            if kind == "method":
                name = entry["name"]
                if not hasattr(klass, name):
                    issues.append(
                        {{
                            "kind": kind,
                            "target": f"{{module_name}}.{{class_name}}.{{name}}",
                            "source": entry["source"],
                            "error": "missing runtime method on class target",
                        }}
                    )

        result_path.write_text(json.dumps({{"issues": issues}}, indent=2), encoding="utf-8")
        """
    ).strip()


def audit_curated_runtime_symbols(
    root: Path,
    source_dir: Path,
    runtime_executable: Path,
) -> RuntimeAuditReport:
    manifest, files_checked = runtime_manifest(root, source_dir)

    with tempfile.TemporaryDirectory(prefix="freecad-stubs-runtime-audit-") as tmp:
        tmp_dir = Path(tmp)
        manifest_path = tmp_dir / "manifest.json"
        result_path = tmp_dir / "result.json"
        script_path = tmp_dir / "runtime_audit.py"

        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        script_path.write_text(runtime_check_script(manifest_path, result_path), encoding="utf-8")

        result = subprocess.run(
            [str(runtime_executable), "-c", f"exec(open(r'{script_path}').read())"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            issue = RuntimeAuditIssue(
                kind="runtime",
                target=str(runtime_executable),
                source=str(script_path),
                error=f"runtime command failed with exit code {result.returncode}",
            )
            return RuntimeAuditReport(
                runtime_executable=runtime_executable,
                files_checked=files_checked,
                symbols_checked=len(manifest),
                issues=(issue,),
                command_output=output,
            )
        if not result_path.is_file():
            issue = RuntimeAuditIssue(
                kind="runtime",
                target=str(runtime_executable),
                source=str(script_path),
                error="runtime command did not write an audit result file",
            )
            return RuntimeAuditReport(
                runtime_executable=runtime_executable,
                files_checked=files_checked,
                symbols_checked=len(manifest),
                issues=(issue,),
                command_output=output,
            )

        payload = json.loads(result_path.read_text(encoding="utf-8"))
        issues = tuple(
            RuntimeAuditIssue(
                kind=item["kind"],
                target=item["target"],
                source=item["source"],
                error=item["error"],
            )
            for item in payload.get("issues", [])
        )
        return RuntimeAuditReport(
            runtime_executable=runtime_executable,
            files_checked=files_checked,
            symbols_checked=len(manifest),
            issues=issues,
            command_output=output,
        )
