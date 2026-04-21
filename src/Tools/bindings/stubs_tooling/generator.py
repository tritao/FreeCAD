# pyright: strict

"""Core generation pipeline for FreeCAD Python binding stubs.

This is the main implementation module for the stub tooling. It performs the
end-to-end pipeline:
- discover Python-facing registrations and binding classes from C++ and ``.pyi``
  sources
- map raw findings onto public FreeCAD module names
- merge curated overlays and checker-only class augmentations
- emit both debug artifacts and the final public stub tree

It relies on ``type_context_rules`` only for cases that cannot be derived
mechanically from the scanned sources and binding specs.

Navigation guidance:
- changes to scanning heuristics usually live near the discovery helpers
- changes to public module shape usually live near the grouping and merge code
- changes to on-disk output layout usually live in ``write_outputs`` and the
  functions it delegates to
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
import copy
import keyword
from pathlib import Path
import re
import shutil
from typing import Iterable

from .model import (
    ADDTYPE_RE,
    ADD_METHOD_RE,
    BEHAVIOR_NAME_RE,
    BindingClass,
    BindingMethod,
    CPP_TYPE_NAME_RE,
    ContextEntry,
    ContextKind,
    EXTENSION_MODULE_RE,
    GETATTR_MODULE_RE,
    HELPER_PYI_FILES,
    ImportBinding,
    ImportTarget,
    INIT_MODULE_RE,
    MethodKind,
    ModuleDef,
    PUBLIC_STUB_DECORATORS,
    PYMETHODDEF_RE,
    PYMETHOD_ALIAS_RE,
    PYIMPORT_ADD_MODULE_RE,
    PYMODULEDEF_RE,
    PYMODULE_ADD_FUNCTIONS_RE,
    PYMODULE_ADD_OBJECT_RE,
    PYMODULE_CREATE_RE,
    PYMODULE_IMPORT_RE,
    PY_OBJECT_WRAPPER_RE,
    PublicClassStub,
    PublicTypeGroup,
    PublicTypeTarget,
    StubSignature,
    StubSignatureOverrides,
)
from .parsing import (
    decorator_kwargs,
    decorator_name,
    extract_balanced,
    first_string_literal,
    generated_source,
    iter_binding_pyi_files,
    iter_source_files,
    line_number,
    normalize_doc,
    normalize_expr,
    parse_python_source,
    split_top_level,
    strip_comments,
)
from .type_context_rules import type_context_internal_reason, type_context_public_targets


def discover_contexts(source: str) -> list[ContextEntry]:
    contexts: list[ContextEntry] = []
    for match in BEHAVIOR_NAME_RE.finditer(source):
        contexts.append((match.start(), "python_type", match.group(1)))
    for match in EXTENSION_MODULE_RE.finditer(source):
        contexts.append((match.start(), "pycxx_module", match.group("python_name")))
    contexts.sort(key=lambda item: item[0])
    return contexts


def nearest_context(contexts: list[ContextEntry], position: int) -> tuple[ContextKind, str]:
    selected: tuple[ContextKind, str] = ("unknown", "unknown")
    for context_position, kind, name in contexts:
        if context_position > position:
            break
        selected = (kind, name)
    return selected


def normalize_table_reference(table: str | None, aliases: dict[str, str]) -> str | None:
    if table is None:
        return None
    normalized = normalize_expr(table)
    seen: set[str] = set()
    while normalized in aliases and normalized not in seen:
        seen.add(normalized)
        normalized = aliases[normalized]
    return normalized


def collect_module_definitions(
    root: Path, files: Iterable[Path]
) -> tuple[dict[tuple[str, str], ModuleDef], dict[str, str], dict[tuple[str, str], str]]:
    module_defs: dict[tuple[str, str], ModuleDef] = {}
    aliases: dict[str, str] = {}
    table_modules: dict[tuple[str, str], str] = {}

    file_data: dict[Path, str] = {}
    for path in files:
        try:
            file_data[path] = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue

    for path, source in file_data.items():
        rel = path.relative_to(root).as_posix()
        for match in PYMETHOD_ALIAS_RE.finditer(source):
            table = normalize_expr(match.group("table"))
            if "::Methods" in table or table.endswith("_methods"):
                aliases[match.group("alias")] = table

        for match in PYMODULEDEF_RE.finditer(source):
            try:
                body, _ = extract_balanced(source, match.end() - 1, "{", "}")
            except ValueError:
                continue
            fields = split_top_level(body)
            if len(fields) < 5:
                continue
            name = first_string_literal(fields[1])
            if not name:
                continue
            table = normalize_table_reference(fields[4], aliases)
            table = None if table in {None, "nullptr", "NULL", "0"} else table
            definition = match.group("definition")
            module_def = ModuleDef(source=rel, name=name, table=table)
            module_defs[(rel, definition)] = module_def
            if table:
                table_modules[(rel, table)] = name

    for path, source in file_data.items():
        rel = path.relative_to(root).as_posix()
        variable_modules: dict[str, str] = {}
        variable_tables: dict[str, str] = {}

        for match in PYMODULE_IMPORT_RE.finditer(source):
            variable_modules[match.group("variable")] = match.group("module")

        for match in PYMODULE_CREATE_RE.finditer(source):
            module_def = module_defs.get((rel, match.group("definition")))
            if not module_def:
                continue
            variable = match.group("variable")
            variable_modules[variable] = module_def.name
            if module_def.table:
                variable_tables[variable] = module_def.table

        for match in PYMODULE_ADD_OBJECT_RE.finditer(source):
            parent = variable_modules.get(match.group("parent"))
            child_table = variable_tables.get(match.group("child"))
            if not parent or not child_table:
                continue
            public_name = f"{parent}.{match.group('name')}"
            table_modules[(rel, child_table)] = public_name

        for match in PYMODULE_ADD_FUNCTIONS_RE.finditer(source):
            module_name = variable_modules.get(match.group("module"))
            table = normalize_table_reference(match.group("table"), aliases)
            if module_name and table:
                table_modules[(rel, table)] = module_name

    return module_defs, aliases, table_modules


def normalize_cpp_qualified_name(name: str) -> str:
    return "::".join(part.strip() for part in name.split("::"))


def cpp_namespace_for_source(rel_path: str) -> str | None:
    parts = rel_path.split("/")
    if len(parts) < 3 or parts[0] != "src":
        return None
    if parts[1] in {"App", "Base", "Gui"}:
        return parts[1]
    if parts[1] == "Mod" and len(parts) >= 4:
        if parts[3] == "Gui":
            return f"{parts[2]}Gui"
        return parts[2]
    return None


def contextual_cpp_type_name(rel_path: str, type_name: str) -> str | None:
    if "::" in type_name:
        return type_name
    namespace = cpp_namespace_for_source(rel_path)
    if not namespace:
        return None
    return f"{namespace}::{type_name}"


def cpp_type_name(expression: str) -> str | None:
    match = CPP_TYPE_NAME_RE.search(expression)
    if match:
        return normalize_cpp_qualified_name(match.group(1))
    match = re.search(
        r"((?:[A-Za-z_]\w*\s*::\s*)*[A-Za-z_]\w*)\s*::\s*type_object\s*\(\s*\)",
        expression,
    )
    if match:
        return normalize_cpp_qualified_name(match.group(1))
    return None


def collect_type_registrations(root: Path, files: Iterable[Path]) -> dict[str, list[str]]:
    registrations: dict[str, list[str]] = defaultdict(list)

    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            source = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue

        module_vars: dict[str, str] = {}
        module_wrappers: dict[str, str] = {}

        for match in PYMODULE_IMPORT_RE.finditer(source):
            module_vars[match.group("variable")] = match.group("module")
        for match in PYIMPORT_ADD_MODULE_RE.finditer(source):
            module_vars[match.group("variable")] = match.group("module")
        for match in INIT_MODULE_RE.finditer(source):
            module_vars[match.group("variable")] = match.group("namespace")
        for match in PY_OBJECT_WRAPPER_RE.finditer(source):
            source_module = module_vars.get(match.group("source"))
            if source_module:
                module_wrappers[match.group("variable")] = source_module
        for match in GETATTR_MODULE_RE.finditer(source):
            owner_module = module_wrappers.get(match.group("owner")) or module_vars.get(
                match.group("owner")
            )
            if owner_module:
                module_vars[match.group("variable")] = f"{owner_module}.{match.group('name')}"

        for match in PYMODULE_ADD_OBJECT_RE.finditer(source):
            parent_module = module_vars.get(match.group("parent"))
            child_module = module_vars.get(match.group("child"))
            if parent_module and child_module:
                module_vars[match.group("child")] = f"{parent_module}.{match.group('name')}"

        for match in ADDTYPE_RE.finditer(source):
            module_name = module_vars.get(match.group("module"))
            type_name = cpp_type_name(match.group("type"))
            if not module_name or not type_name:
                continue
            public_name = f"{module_name}.{match.group('name')}"
            keys = [type_name]
            context_name = contextual_cpp_type_name(rel, type_name)
            if context_name:
                keys.append(context_name)
            if "::" in type_name:
                keys.append(type_name.rsplit("::", 1)[-1])
            for key in dict.fromkeys(keys):
                if public_name not in registrations[key]:
                    registrations[key].append(public_name)

    return dict(registrations)


def binding_export_name(class_name: str, export_kwargs: dict[str, object]) -> str:
    name = export_kwargs.get("Name")
    if isinstance(name, str) and name:
        return name
    if class_name == "PyObjectBase":
        return class_name
    return f"{class_name}Py"


def fallback_public_name(rel_path: str, class_name: str) -> str | None:
    parts = rel_path.split("/")
    if len(parts) < 3 or parts[0] != "src":
        return None
    if parts[1] == "Base":
        return f"FreeCAD.Base.{class_name}"
    if parts[1] == "App":
        return f"FreeCAD.{class_name}"
    if parts[1] == "Gui":
        return f"FreeCADGui.{class_name}"
    if parts[1] == "Mod" and len(parts) >= 3:
        module_name = parts[2]
        if "Gui" in parts[3:4]:
            return f"{module_name}Gui.{class_name}"
        return f"{module_name}.{class_name}"
    return None


def public_names_for_class(
    rel_path: str,
    class_name: str,
    export_name: str,
    python_name: str | None,
    export_kwargs: dict[str, object],
    type_registrations: dict[str, list[str]],
) -> list[str]:
    candidate_keys: list[str] = []
    namespace = export_kwargs.get("Namespace")
    if isinstance(namespace, str) and namespace:
        candidate_keys.append(f"{namespace}::{export_name}")
    contextual_name = contextual_cpp_type_name(rel_path, export_name)
    if contextual_name:
        candidate_keys.append(contextual_name)

    for key in dict.fromkeys(candidate_keys):
        names = list(dict.fromkeys(type_registrations.get(key, [])))
        if names:
            return names

    fallback_name = fallback_public_name(rel_path, class_name)
    unqualified_names = list(dict.fromkeys(type_registrations.get(export_name, [])))
    if unqualified_names and fallback_name in unqualified_names and len(unqualified_names) == 1:
        return unqualified_names

    names: list[str] = []
    if python_name:
        names.append(python_name)
    if fallback_name and not names:
        names.append(fallback_name)
    return names


def parse_binding_class_file(
    root: Path,
    path: Path,
    type_registrations: dict[str, list[str]],
) -> list[BindingClass]:
    rel = path.relative_to(root).as_posix()
    tree = parse_python_source(path)
    if not tree:
        return []

    classes: list[BindingClass] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        export_kwargs: dict[str, object] = {}
        explicit_export = False
        for decorator in node.decorator_list:
            if decorator_name(decorator) == "export":
                explicit_export = True
                export_kwargs = decorator_kwargs(decorator)
                break

        python_name = export_kwargs.get("PythonName")
        python_name = python_name if isinstance(python_name, str) and python_name else None
        export_name = binding_export_name(node.name, export_kwargs)
        base_class = None
        if node.bases:
            base_class = ast.unparse(node.bases[0]).split("[", 1)[0].split(".")[-1]

        classes.append(
            BindingClass(
                source=rel,
                line=node.lineno,
                class_name=node.name,
                export_name=export_name,
                python_name=python_name,
                public_names=public_names_for_class(
                    rel, node.name, export_name, python_name, export_kwargs, type_registrations
                ),
                base_class=base_class,
                explicit_export=explicit_export,
            )
        )

    return classes


def collect_binding_classes(
    root: Path,
    source_dir: Path,
    type_registrations: dict[str, list[str]] | None = None,
) -> list[BindingClass]:
    if type_registrations is None:
        source_files = list(iter_source_files(root, source_dir))
        type_registrations = collect_type_registrations(root, source_files)

    classes: list[BindingClass] = []
    for path in iter_binding_pyi_files(root, source_dir):
        classes.extend(parse_binding_class_file(root, path, type_registrations))

    return sorted(classes, key=lambda klass: (klass.source, klass.line, klass.class_name))


def public_type_target(public_name: str) -> PublicTypeTarget | None:
    if "." not in public_name:
        return None
    module_name, class_symbol = public_name.rsplit(".", 1)
    if not valid_identifier(class_symbol):
        return None
    return PublicTypeTarget(module_name=module_name, class_symbol=class_symbol)


def public_type_targets_for_context(
    context_name: str,
    methods: list[BindingMethod],
    type_registrations: dict[str, list[str]],
) -> list[PublicTypeTarget]:
    targets: list[PublicTypeTarget] = []
    candidate_keys = [context_name, f"{context_name}Py"]

    for method in methods:
        targets.extend(type_context_public_targets(method.source, context_name))
        owner = cxx_owner_hint(method.cxx_callable)
        if owner:
            candidate_keys.append(owner)

    for key in dict.fromkeys(candidate_keys):
        for public_name in type_registrations.get(key, []):
            target = public_type_target(public_name)
            if target:
                targets.append(target)

    return list(dict.fromkeys(targets))


def known_module_hint(rel_path: str, table: str) -> str | None:
    known = {
        ("src/App/ApplicationPy.cpp", "ApplicationPy::Methods"): "FreeCAD",
        ("src/Base/Console.cpp", "ConsoleSingleton::Methods"): "FreeCAD.Console",
        ("src/Base/UnitsApiPy.cpp", "UnitsApi::Methods"): "FreeCAD.Units",
        ("src/Gui/ApplicationPy.cpp", "ApplicationPy::Methods"): "FreeCADGui",
        ("src/Gui/Selection/Selection.cpp", "SelectionSingleton::Methods"): "FreeCADGui.Selection",
        ("src/Main/FreeCADGuiPy.cpp", "FreeCADGui_methods"): "FreeCADGui",
        ("src/Gui/Application.cpp", "FreeCADGui_methods"): "FreeCADGui",
        (
            "src/Mod/Part/Gui/AttacherTexts.cpp",
            "AttacherGuiPy::Methods",
        ): "PartGui.AttachEngineResources",
    }
    return known.get((rel_path, table))


def known_pycxx_module_hint(rel_path: str, module_name: str) -> str | None:
    known = {
        ("src/Base/Translate.cpp", "__Translate__"): "FreeCAD.Qt",
        ("src/Gui/UiLoader.cpp", "PySideUic"): "FreeCADGui.PySideUic",
        ("src/Mod/Part/App/AppPartPy.cpp", "ShapeFix"): "Part.ShapeFix",
    }
    return known.get((rel_path, module_name))


def cxx_owner_hint(cxx_callable: str) -> str | None:
    match = re.search(r"&\s*(?P<owner>[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)(?:<[^>]+>)?::", cxx_callable)
    if not match:
        return None
    return match.group("owner").rsplit("::", 1)[-1]


def inferred_pymethoddef_module(
    rel_path: str,
    table: str,
    table_modules: dict[tuple[str, str], str],
) -> str | None:
    hint = known_module_hint(rel_path, table)
    if hint:
        return hint

    candidates = {
        module_name
        for (source_path, table_name), module_name in table_modules.items()
        if source_path == rel_path and table_name == table
    }
    if len(candidates) == 1:
        return next(iter(candidates))

    candidates = {
        module_name for (_, table_name), module_name in table_modules.items() if table_name == table
    }
    if len(candidates) == 1:
        return next(iter(candidates))

    return None


def extract_pycxx_methods(root: Path, path: Path, source: str) -> list[BindingMethod]:
    rel = path.relative_to(root).as_posix()
    contexts = discover_contexts(source)
    methods: list[BindingMethod] = []

    for match in ADD_METHOD_RE.finditer(source):
        try:
            args, _ = extract_balanced(source, match.end() - 1, "(", ")")
        except ValueError:
            continue
        fields = split_top_level(args)
        if len(fields) < 2:
            continue
        python_name = first_string_literal(fields[0])
        if not python_name:
            continue
        kind, context = nearest_context(contexts, match.start())
        match match.group("kind"):
            case "add_keyword_method":
                method_kind: MethodKind = "keyword"
            case "add_noargs_method":
                method_kind = "noargs"
            case "add_varargs_method":
                method_kind = "varargs"
            case _:
                raise AssertionError("unexpected PyCXX method registration kind")
        cxx_callable = normalize_expr(fields[1])
        doc = normalize_doc(fields[2]) if len(fields) >= 3 else ""
        if kind == "unknown":
            owner = cxx_owner_hint(cxx_callable)
            if owner:
                kind = "python_type"
                context = owner
        inferred_module = None
        if kind == "pycxx_module":
            inferred_module = known_pycxx_module_hint(rel, context) or context

        methods.append(
            BindingMethod(
                family="pycxx_add_method",
                source=rel,
                line=line_number(source, match.start()),
                table=None,
                context_kind=kind,
                context_name=context,
                inferred_module=inferred_module,
                method_kind=method_kind,
                python_name=python_name,
                cxx_callable=cxx_callable,
                flags="",
                doc=doc,
                generated_source=generated_source(rel),
            )
        )

    return methods


def extract_pymethoddef_methods(
    root: Path,
    path: Path,
    source: str,
    table_modules: dict[tuple[str, str], str],
) -> list[BindingMethod]:
    rel = path.relative_to(root).as_posix()
    methods: list[BindingMethod] = []

    for match in PYMETHODDEF_RE.finditer(source):
        table = normalize_expr(match.group("table"))
        try:
            body, _ = extract_balanced(source, match.end() - 1, "{", "}")
        except ValueError:
            continue
        for entry in split_top_level(body):
            if not entry.startswith("{"):
                continue
            try:
                entry_body, _ = extract_balanced(entry, 0, "{", "}")
            except ValueError:
                continue
            fields = split_top_level(entry_body)
            if len(fields) < 3:
                continue
            python_name = first_string_literal(fields[0])
            if not python_name:
                continue
            cxx_callable = normalize_expr(fields[1])
            if cxx_callable in {"nullptr", "NULL", "0"}:
                continue
            flags = normalize_expr(fields[2])
            doc = normalize_doc(fields[3]) if len(fields) >= 4 else ""
            module_name = inferred_pymethoddef_module(rel, table, table_modules)

            methods.append(
                BindingMethod(
                    family="pymethoddef",
                    source=rel,
                    line=line_number(source, match.start() + body.find(entry)),
                    table=table,
                    context_kind="pymethoddef_table",
                    context_name=table,
                    inferred_module=module_name,
                    method_kind=flags_to_method_kind(flags),
                    python_name=python_name,
                    cxx_callable=cxx_callable,
                    flags=flags,
                    doc=doc,
                    generated_source=generated_source(rel),
                )
            )

    return methods


def flags_to_method_kind(flags: str) -> MethodKind:
    match flags:
        case value if "METH_KEYWORDS" in value:
            return "keyword"
        case value if "METH_NOARGS" in value:
            return "noargs"
        case _:
            return "varargs"


def collect_methods(root: Path, source_dir: Path) -> list[BindingMethod]:
    files = list(iter_source_files(root, source_dir))
    _, _, table_modules = collect_module_definitions(root, files)

    methods: list[BindingMethod] = []
    for path in files:
        try:
            source = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        methods.extend(extract_pycxx_methods(root, path, source))
        methods.extend(extract_pymethoddef_methods(root, path, source, table_modules))

    return sorted(methods, key=lambda method: (method.source, method.line, method.python_name))


def signature(method: BindingMethod, class_method: bool = False) -> str:
    self_arg = "self, " if class_method else ""
    if method.method_kind == "noargs":
        return "(self)" if class_method else "()"
    if method.method_kind == "keyword":
        return f"({self_arg}*args: Any, **kwargs: Any)"
    return f"({self_arg}*args: Any)"


def known_stub_signature(
    method: BindingMethod,
    class_method: bool,
    stub_signature_overrides: StubSignatureOverrides,
) -> StubSignature | None:
    if not class_method:
        return None
    return stub_signature_overrides.get((method.source, method.context_name, method.python_name))


def resolve_signature_placeholders(
    text: str,
    class_symbol: str | None,
    source_class_symbol: str | None = None,
) -> str:
    if not class_symbol:
        return text
    text = text.replace("{class}", class_symbol)
    if source_class_symbol and source_class_symbol != class_symbol:
        text = re.sub(rf"\b{re.escape(source_class_symbol)}\b", class_symbol, text)
    return text


def format_signature(parameters: str, class_method: bool) -> str:
    if class_method:
        if parameters:
            return f"(self, {parameters})"
        return "(self)"
    return f"({parameters})" if parameters else "()"


def valid_identifier(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def stub_line(
    method: BindingMethod,
    class_method: bool = False,
    class_symbol: str | None = None,
    stub_signature_overrides: StubSignatureOverrides | None = None,
) -> str:
    if valid_identifier(method.python_name):
        known_signature = known_stub_signature(
            method,
            class_method,
            stub_signature_overrides or {},
        )
        if known_signature:
            parameters = resolve_signature_placeholders(
                known_signature.parameters,
                class_symbol,
                known_signature.class_symbol,
            )
            returns = resolve_signature_placeholders(
                known_signature.returns,
                class_symbol,
                known_signature.class_symbol,
            )
            signature_text = format_signature(parameters, class_method)
            return f"def {method.python_name}{signature_text} -> {returns}: ..."
        return f"def {method.python_name}{signature(method, class_method)} -> Any: ..."
    return f"# TODO: invalid Python identifier from binding table: {method.python_name!r}"


def write_stub_file(
    path: Path,
    methods: list[BindingMethod],
    class_name: str | None = None,
    stub_signature_overrides: StubSignatureOverrides | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# This is a generated inventory skeleton. Refine signatures before publishing.",
        "from __future__ import annotations",
        "from typing import Any",
        "",
    ]
    seen: set[str] = set()

    if class_name:
        safe_class_name = class_name.rsplit(".", 1)[-1]
        if not valid_identifier(safe_class_name):
            safe_class_name = "BindingType"
        class_start = len(lines)
        lines.append(f"class {safe_class_name}:")
        for method in methods:
            rendered = "    " + stub_line(
                method,
                class_method=True,
                class_symbol=safe_class_name,
                stub_signature_overrides=stub_signature_overrides,
            )
            if rendered in seen:
                continue
            lines.append(rendered)
            seen.add(rendered)
        if len(lines) == class_start + 1:
            lines.append("    pass")
    else:
        for method in methods:
            rendered = stub_line(method, stub_signature_overrides=stub_signature_overrides)
            if rendered in seen:
                continue
            lines.append(rendered)
            seen.add(rendered)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def safe_stub_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip(".") or "unknown"


def group_methods(methods: list[BindingMethod]) -> tuple[
    dict[str, list[BindingMethod]],
    dict[str, list[BindingMethod]],
    dict[str, list[BindingMethod]],
]:
    module_methods: dict[str, list[BindingMethod]] = defaultdict(list)
    type_methods: dict[str, list[BindingMethod]] = defaultdict(list)
    unknown_methods: dict[str, list[BindingMethod]] = defaultdict(list)

    for method in methods:
        if method.inferred_module:
            module_methods[method.inferred_module].append(method)
        elif method.context_kind == "python_type":
            type_methods[method.context_name].append(method)
        else:
            key = f"{method.source}:{method.context_name}"
            unknown_methods[key].append(method)

    return module_methods, type_methods, unknown_methods


def public_type_context_index(
    methods: list[BindingMethod],
    type_registrations: dict[str, list[str]],
) -> dict[tuple[str, str], list[tuple[str, str]]]:
    _, type_methods, _ = group_methods(methods)
    index: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)

    for context_name, group in sorted(type_methods.items()):
        context_sources = sorted({method.source for method in group})
        for target in public_type_targets_for_context(context_name, group, type_registrations):
            key = (target.module_name, target.class_symbol)
            for source in context_sources:
                context_key = (source, context_name)
                if context_key not in index[key]:
                    index[key].append(context_key)

    return dict(index)


def stub_signature_from_function_node(
    path: Path,
    source: str,
    class_symbol: str,
    node: ast.FunctionDef,
) -> StubSignature:
    if node.returns is None:
        raise ValueError(f"{path}: {class_symbol}.{node.name} is missing a return annotation")
    definition = ast.get_source_segment(source, node) or ""
    if definition:
        start = definition.find("(")
        if start == -1:
            raise ValueError(f"{path}: {class_symbol}.{node.name} has no parameter list")
        parameters, end = extract_balanced(definition, start, "(", ")")
        return_match = re.match(r"\s*->\s*(?P<returns>.+?)\s*:", definition[end:], re.DOTALL)
        if not return_match:
            raise ValueError(f"{path}: {class_symbol}.{node.name} is missing a return annotation")
        returns = " ".join(return_match.group("returns").split())
    else:
        parameters = ast.unparse(node.args)
        returns = ast.unparse(node.returns)
    parameters = parameters.strip()
    if parameters == "self":
        parameters = ""
    elif parameters.startswith("self,"):
        parameters = parameters.removeprefix("self,").lstrip()
    else:
        raise ValueError(f"{path}: {class_symbol}.{node.name} must be an instance method")
    return StubSignature(parameters, returns, class_symbol)


def parse_stub_signature_overrides(
    override_dir: Path,
) -> dict[tuple[str, str, str], tuple[StubSignature, Path]]:
    signatures: dict[tuple[str, str, str], tuple[StubSignature, Path]] = {}
    pycxx_override_dir = (
        override_dir / "pycxx" if (override_dir / "pycxx").exists() else override_dir
    )
    if not pycxx_override_dir.exists():
        return signatures

    for path in sorted(pycxx_override_dir.rglob("*.pyi")):
        relative = path.relative_to(pycxx_override_dir)
        module_name = ".".join(relative.parent.parts)
        if not module_name:
            raise ValueError(f"{path}: PyCXX override files must live below a module directory")
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            raise ValueError(f"{path}: invalid stub override syntax: {exc}") from exc

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, ast.FunctionDef):
                    continue
                key = (module_name, node.name, item.name)
                signature = stub_signature_from_function_node(path, source, node.name, item)
                if key in signatures:
                    _, earlier_path = signatures[key]
                    raise ValueError(
                        f"{path}: duplicate signature for {module_name}.{node.name}.{item.name}; "
                        f"already defined in {earlier_path}"
                    )
                signatures[key] = (signature, path)

    return signatures


def load_stub_signature_overrides(
    override_dir: Path,
    methods: list[BindingMethod],
    type_registrations: dict[str, list[str]],
) -> StubSignatureOverrides:
    public_signatures = parse_stub_signature_overrides(override_dir)
    if not public_signatures:
        return {}

    context_index = public_type_context_index(methods, type_registrations)
    method_keys = {
        (method.source, method.context_name, method.python_name)
        for method in methods
        if method.context_kind == "python_type"
    }
    overrides: StubSignatureOverrides = {}
    errors: list[str] = []

    for public_key, (signature_override, path) in sorted(public_signatures.items()):
        module_name, class_symbol, method_name = public_key
        context_keys = context_index.get((module_name, class_symbol), [])
        if not context_keys:
            errors.append(f"{path}: no mapped PyCXX type context for {module_name}.{class_symbol}")
            continue

        matched_keys = [
            (source, context_name, method_name)
            for source, context_name in context_keys
            if (source, context_name, method_name) in method_keys
        ]
        if not matched_keys:
            contexts = ", ".join(
                f"{source}:{context_name}" for source, context_name in context_keys
            )
            errors.append(
                f"{path}: {module_name}.{class_symbol}.{method_name} is not registered "
                f"in mapped contexts: {contexts}"
            )
            continue

        for override_key in matched_keys:
            existing = overrides.get(override_key)
            if existing and existing != signature_override:
                errors.append(f"{path}: conflicting override for {override_key}")
                continue
            overrides[override_key] = signature_override

    if errors:
        raise ValueError("invalid PyCXX stub signature overrides:\n  " + "\n  ".join(errors))
    return overrides


def write_stubs(
    out_dir: Path,
    methods: list[BindingMethod],
    stub_signature_overrides: StubSignatureOverrides,
) -> None:
    module_methods, type_methods, unknown_methods = group_methods(methods)

    for module_name, group in sorted(module_methods.items()):
        write_stub_file(
            out_dir / "modules" / f"{safe_stub_name(module_name)}.pyi",
            group,
            stub_signature_overrides=stub_signature_overrides,
        )

    for type_name, group in sorted(type_methods.items()):
        write_stub_file(
            out_dir / "types" / f"{safe_stub_name(type_name)}.pyi",
            group,
            class_name=type_name,
            stub_signature_overrides=stub_signature_overrides,
        )

    for key, group in sorted(unknown_methods.items()):
        write_stub_file(
            out_dir / "unknown" / f"{safe_stub_name(key)}.pyi",
            group,
            stub_signature_overrides=stub_signature_overrides,
        )


def module_names_from_methods(methods: list[BindingMethod]) -> set[str]:
    return {method.inferred_module for method in methods if method.inferred_module}


def module_names_from_classes(classes: list[BindingClass]) -> set[str]:
    return {
        public_name.rsplit(".", 1)[0]
        for klass in classes
        for public_name in klass.public_names
        if "." in public_name
    }


def group_type_methods_by_public_module(
    methods: list[BindingMethod],
    type_registrations: dict[str, list[str]],
) -> dict[str, list[PublicTypeGroup]]:
    _, type_methods, _ = group_methods(methods)
    grouped: dict[str, list[PublicTypeGroup]] = defaultdict(list)
    seen: set[tuple[str, str, str | None, tuple[str, ...]]] = set()

    for context_name, group in sorted(type_methods.items()):
        for target in public_type_targets_for_context(context_name, group, type_registrations):
            if not valid_identifier(target.class_symbol):
                continue
            if target.variable_symbol and not valid_identifier(target.variable_symbol):
                continue
            if any(not valid_identifier(base_symbol) for base_symbol in target.base_symbols):
                continue
            key = (
                target.module_name,
                target.class_symbol,
                target.variable_symbol,
                target.base_symbols,
            )
            if key in seen:
                continue
            seen.add(key)
            grouped[target.module_name].append(
                (target.class_symbol, target.variable_symbol, target.base_symbols, group)
            )

    return grouped


def module_names_from_type_methods(
    methods: list[BindingMethod],
    type_registrations: dict[str, list[str]],
) -> set[str]:
    return set(group_type_methods_by_public_module(methods, type_registrations))


def unmapped_type_contexts(
    methods: list[BindingMethod],
    type_registrations: dict[str, list[str]],
) -> list[str]:
    _, type_methods, _ = group_methods(methods)
    return [
        context_name
        for context_name, group in sorted(type_methods.items())
        if not public_type_targets_for_context(context_name, group, type_registrations)
        and not internal_type_context_reason(context_name, group)
    ]


def internal_type_context_reason(context_name: str, methods: list[BindingMethod]) -> str | None:
    reasons = {
        reason
        for method in methods
        if (reason := type_context_internal_reason(method.source, context_name)) is not None
    }
    if not reasons:
        return None
    if any(type_context_internal_reason(method.source, context_name) is None for method in methods):
        return None
    return "; ".join(sorted(reasons))


def overlay_module_name(relative: Path) -> str | None:
    if relative.suffix != ".pyi":
        return None
    if relative.name == "__init__.pyi" and relative.parent.parts:
        return ".".join(relative.parent.parts)
    return ".".join(relative.with_suffix("").parts)


def module_names_from_overlays(overlay_dir: Path | None) -> set[str]:
    if not overlay_dir or not overlay_dir.exists():
        return set()
    names: set[str] = set()
    for source in overlay_dir.rglob("*.pyi"):
        module_name = overlay_module_name(source.relative_to(overlay_dir))
        if module_name:
            names.add(module_name)
    return names


def public_module_names(
    methods: list[BindingMethod],
    classes: list[BindingClass],
    type_registrations: dict[str, list[str]],
    overlay_dir: Path | None,
    class_overlay_dir: Path | None,
) -> set[str]:
    return (
        module_names_from_methods(methods)
        | module_names_from_classes(classes)
        | module_names_from_type_methods(methods, type_registrations)
        | module_names_from_overlays(overlay_dir)
        | module_names_from_overlays(class_overlay_dir)
    )


def has_child_module(module_name: str, module_names: set[str]) -> bool:
    prefix = f"{module_name}."
    return any(name.startswith(prefix) for name in module_names)


def module_stub_path(out_dir: Path, module_name: str, module_names: set[str]) -> Path:
    parts = module_name.split(".")
    if len(parts) == 1 or has_child_module(module_name, module_names):
        return out_dir.joinpath(*parts, "__init__.pyi")
    return out_dir.joinpath(*parts[:-1], f"{parts[-1]}.pyi")


def ensure_parent_package_stubs(out_dir: Path, module_names: set[str]) -> None:
    for module_name in module_names:
        parts = module_name.split(".")
        for index in range(1, len(parts)):
            package_dir = out_dir.joinpath(*parts[:index])
            package_dir.mkdir(parents=True, exist_ok=True)
            init_path = package_dir / "__init__.pyi"
            if not init_path.exists():
                init_path.write_text(
                    "from __future__ import annotations\n",
                    encoding="utf-8",
                )


def write_public_module_stubs(
    out_dir: Path,
    methods: list[BindingMethod],
    module_names: set[str],
    stub_signature_overrides: StubSignatureOverrides,
) -> None:
    module_methods, _, _ = group_methods(methods)
    ensure_parent_package_stubs(out_dir, module_names)
    for module_name, group in sorted(module_methods.items()):
        write_stub_file(
            module_stub_path(out_dir, module_name, module_names),
            group,
            stub_signature_overrides=stub_signature_overrides,
        )


def type_stub_lines(
    type_groups: list[PublicTypeGroup],
    stub_signature_overrides: StubSignatureOverrides,
    include_future_import: bool = True,
) -> list[str]:
    lines = [
        "# Generated public type stubs from PyCXX binding method tables.",
    ]
    if include_future_import:
        lines.append("from __future__ import annotations")
    lines.extend(["from typing import Any", ""])

    for class_symbol, variable_symbol, base_symbols, methods in type_groups:
        base_clause = f"({', '.join(base_symbols)})" if base_symbols else ""
        lines.append(f"class {class_symbol}{base_clause}:")
        seen: set[str] = set()
        class_start = len(lines)
        for method in methods:
            rendered = "    " + stub_line(
                method,
                class_method=True,
                class_symbol=class_symbol,
                stub_signature_overrides=stub_signature_overrides,
            )
            if rendered in seen:
                continue
            lines.append(rendered)
            seen.add(rendered)
        if len(lines) == class_start:
            lines.append("    pass")
        if variable_symbol:
            lines.extend(["", f"{variable_symbol}: {class_symbol}"])
        lines.append("")

    return lines


def append_type_stubs(
    out_dir: Path,
    methods: list[BindingMethod],
    type_registrations: dict[str, list[str]],
    stub_signature_overrides: StubSignatureOverrides,
    module_names: set[str] | None = None,
    supplemental_groups: dict[str, list[PublicTypeGroup]] | None = None,
) -> int:
    module_names = module_names or module_names_from_type_methods(methods, type_registrations)
    grouped = group_type_methods_by_public_module(methods, type_registrations)
    seen = {
        (module_name, class_symbol, variable_symbol)
        for module_name, type_groups in grouped.items()
        for class_symbol, variable_symbol, _, _ in type_groups
    }
    for module_name, type_groups in (supplemental_groups or {}).items():
        for type_group in type_groups:
            class_symbol, variable_symbol, _, _ = type_group
            key = (module_name, class_symbol, variable_symbol)
            if key in seen:
                continue
            seen.add(key)
            grouped[module_name].append(type_group)
    count = 0
    for module_name, type_groups in sorted(grouped.items()):
        path = module_stub_path(out_dir, module_name, module_names)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        existing_symbols = public_stub_symbols(existing)
        type_groups = [
            type_group
            for type_group in type_groups
            if type_group[0] not in existing_symbols
            and (not type_group[1] or type_group[1] not in existing_symbols)
        ]
        if not type_groups:
            continue
        lines = "\n".join(
            type_stub_lines(
                type_groups,
                stub_signature_overrides,
                include_future_import=not existing.strip(),
            )
        ).rstrip()
        separator = "\n\n" if existing else ""
        path.write_text(existing.rstrip() + separator + lines + "\n", encoding="utf-8")
        count += len(type_groups)
    return count


def public_stub_symbols(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    symbols: set[str] = set()
    for node in tree.body:
        match node:
            case (
                ast.ClassDef(name=name)
                | ast.FunctionDef(name=name)
                | ast.AsyncFunctionDef(name=name)
            ):
                symbols.add(name)
            case ast.AnnAssign(target=ast.Name(id=name)):
                symbols.add(name)
            case ast.Assign(targets=targets):
                for target in targets:
                    if isinstance(target, ast.Name):
                        symbols.add(target.id)
            case ast.ImportFrom(names=names):
                for alias in names:
                    if alias.name == "*" or not alias.asname:
                        continue
                    symbols.add(alias.asname)
            case _:
                pass
    return symbols


def keep_public_stub_decorator(decorator: ast.expr) -> bool:
    name = decorator_name(decorator).split(".", 1)[-1]
    return name in PUBLIC_STUB_DECORATORS


class PublicClassStubTransformer(ast.NodeTransformer):
    def __init__(
        self,
        module_name: str,
        public_symbol: str,
        renames: dict[str, str],
        public_base_names: set[str],
        public_base_modules: set[str],
    ):
        self.module_name = module_name
        self.public_symbol = public_symbol
        self.renames = renames
        self.public_base_names = public_base_names
        self.public_base_modules = public_base_modules
        self.class_depth = 0
        self.shadowed_annotation_names: set[str] = set()
        self.annotation_module_roots_needed: set[str] = set()

    def rewrite_annotation(self, annotation: ast.expr | None) -> ast.expr | None:
        if annotation is None:
            return None
        rewritten = self.visit(annotation)
        shadowed_names = {
            child.id
            for child in ast.walk(rewritten)
            if isinstance(child, ast.Name) and child.id in self.shadowed_annotation_names
        }
        if shadowed_names:
            self.annotation_module_roots_needed.add(self.module_name.split(".", 1)[0])
            qualified = QualifyAnnotationNames(self.module_name, shadowed_names).visit(
                copy.deepcopy(rewritten)
            )
            return ast.Constant(value=ast.unparse(qualified))
        return rewritten

    @staticmethod
    def top_level_class_member_names(body: list[ast.stmt]) -> set[str]:
        names: set[str] = set()
        for item in body:
            match item:
                case (
                    ast.ClassDef(name=name)
                    | ast.FunctionDef(name=name)
                    | ast.AsyncFunctionDef(name=name)
                ):
                    names.add(name)
                case ast.AnnAssign(target=ast.Name(id=name)):
                    names.add(name)
                case ast.Assign(targets=targets):
                    names.update(target.id for target in targets if isinstance(target, ast.Name))
                case _:
                    pass
        return names

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        is_public_class = self.class_depth == 0
        if is_public_class:
            node.name = self.public_symbol
        node.decorator_list = [
            decorator for decorator in node.decorator_list if keep_public_stub_decorator(decorator)
        ]
        node.bases = [self.visit(base) for base in node.bases]
        if is_public_class:
            node.bases = [
                base
                for base in node.bases
                if (
                    (isinstance(base, ast.Name) and base.id in self.public_base_names)
                    or (
                        isinstance(base, ast.Attribute)
                        and isinstance(base.value, ast.Name)
                        and base.value.id in self.public_base_modules
                    )
                )
            ]
            node.keywords = []
            self.shadowed_annotation_names = self.top_level_class_member_names(node.body)
        self.class_depth += 1
        try:
            node.body = [self.visit(item) for item in node.body]
        finally:
            self.class_depth -= 1
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        node.decorator_list = [
            decorator for decorator in node.decorator_list if keep_public_stub_decorator(decorator)
        ]
        node.args = self.visit(node.args)
        node.returns = self.rewrite_annotation(node.returns)
        node.body = [self.visit(item) for item in node.body]
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        node.decorator_list = [
            decorator for decorator in node.decorator_list if keep_public_stub_decorator(decorator)
        ]
        node.args = self.visit(node.args)
        node.returns = self.rewrite_annotation(node.returns)
        node.body = [self.visit(item) for item in node.body]
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.annotation = self.rewrite_annotation(node.annotation)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> ast.AnnAssign:
        node.target = self.visit(node.target)
        annotation = self.rewrite_annotation(node.annotation)
        if annotation is None:
            raise ValueError("annotated assignment must keep an annotation")
        node.annotation = annotation
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            node.value = ast.Constant(value=Ellipsis)
        else:
            node.value = self.visit(node.value) if node.value else None
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self.renames:
            node.id = self.renames[node.id]
        return node


class QualifyAnnotationNames(ast.NodeTransformer):
    def __init__(self, module_name: str, names: set[str]):
        self.module_name = module_name
        self.names = names

    def qualified_name_expr(self, name: str) -> ast.expr:
        head, *tail = self.module_name.split(".")
        expr: ast.expr = ast.Name(id=head, ctx=ast.Load())
        for part in tail:
            expr = ast.Attribute(value=expr, attr=part, ctx=ast.Load())
        return ast.Attribute(value=expr, attr=name, ctx=ast.Load())

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if node.id in self.names:
            return ast.copy_location(self.qualified_name_expr(node.id), node)
        return node


def group_classes_by_module(classes: list[BindingClass]) -> dict[str, list[BindingClass]]:
    grouped: dict[str, list[BindingClass]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for klass in classes:
        for public_name in klass.public_names:
            if "." not in public_name:
                continue
            module_name = public_name.rsplit(".", 1)[0]
            symbol = public_name.rsplit(".", 1)[1]
            key = (module_name, symbol)
            if key in seen:
                continue
            seen.add(key)
            grouped[module_name].append(klass)
    return grouped


def class_node(root: Path, klass: BindingClass) -> ast.ClassDef | None:
    tree = parse_python_source(root / klass.source)
    if not tree:
        return None

    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == klass.class_name
            and node.lineno == klass.line
        ):
            return node
    return None


def type_checking_test(node: ast.expr) -> bool:
    match node:
        case ast.Name(id="TYPE_CHECKING"):
            return True
        case ast.Attribute(attr="TYPE_CHECKING", value=ast.Name(id="typing")):
            return True
        case _:
            return False


def import_stmt_line(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        names = ", ".join(
            alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names
        )
        return f"import {names}"

    module = "." * node.level + (node.module or "")
    names = ", ".join(
        alias.name + (f" as {alias.asname}" if alias.asname else "") for alias in node.names
    )
    return f"from {module} import {names}"


def source_import_bindings(root: Path, source: str) -> dict[str, ImportBinding]:
    tree = parse_python_source(root / source)
    if not tree:
        return {}

    bindings: dict[str, ImportBinding] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                exposed_name = alias.asname or alias.name.split(".", 1)[0]
                bindings[exposed_name] = ImportBinding(module=alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module = node.module or ""
            if not module:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                exposed_name = alias.asname or alias.name
                bindings[exposed_name] = ImportBinding(module=module, name=alias.name)

    return bindings


def module_prefixes(parts: tuple[str, ...]) -> set[str]:
    return {".".join(parts[:index]) for index in range(1, len(parts) + 1)}


def class_source_module_aliases(klass: BindingClass) -> set[str]:
    path = Path(klass.source).with_suffix("")
    parts = path.parts
    aliases: set[str] = {path.name}
    if len(parts) < 3 or parts[0] != "src":
        return aliases

    if parts[1] in {"Base", "App", "Gui"}:
        aliases |= module_prefixes(parts[1:])
    elif parts[1] == "Mod" and len(parts) >= 5:
        workbench = parts[2]
        impl_parts = parts[3:]
        public_parts = (workbench, *parts[4:])
        aliases |= module_prefixes(public_parts)
        aliases |= module_prefixes((workbench, *impl_parts))

    aliases |= {module_name for module_name, _ in class_public_targets(klass)}
    return aliases


def public_import_target_index(classes: list[BindingClass]) -> dict[ImportTarget, ImportTarget]:
    index: dict[ImportTarget, ImportTarget] = {}
    ambiguous: set[ImportTarget] = set()
    for klass in classes:
        target = canonical_class_public_target(klass)
        if not target:
            continue
        candidate_names = {
            klass.class_name,
            klass.export_name,
            *(symbol for _, symbol in class_public_targets(klass)),
        }
        for module_name in class_source_module_aliases(klass):
            for name in candidate_names:
                key = (module_name, name)
                existing = index.get(key)
                if existing and existing != target:
                    ambiguous.add(key)
                    continue
                index[key] = target

    for key in ambiguous:
        index.pop(key, None)
    return index


def known_stub_module_roots(classes: list[BindingClass]) -> set[str]:
    roots = {"App", "Base", "Data", "Gui"}
    for klass in classes:
        for module_name in class_source_module_aliases(klass):
            roots.add(module_name.split(".", 1)[0])
    for helper_source in HELPER_PYI_FILES:
        roots.add(Path(helper_source).with_suffix("").name)
    return roots


def transformed_import_bindings(
    import_bindings: dict[str, ImportBinding],
    renames: dict[str, str],
) -> dict[str, ImportBinding]:
    transformed: dict[str, ImportBinding] = {}
    for name, binding in import_bindings.items():
        transformed.setdefault(renames.get(name, name), binding)
    return transformed


def import_line_for_binding(
    binding: ImportBinding,
    symbol_name: str,
    module_name: str,
    import_targets: dict[ImportTarget, ImportTarget],
    internal_roots: set[str],
) -> str | None:
    if binding.name is not None:
        if binding.module == "typing":
            return None

        if target := import_targets.get((binding.module, binding.name)):
            target_module, target_symbol = target
            if target_module == module_name:
                return None
            if symbol_name == target_symbol:
                return f"from {target_module} import {target_symbol}"
            return f"from {target_module} import {target_symbol} as {symbol_name}"

        if binding.module.split(".", 1)[0] in internal_roots:
            return None
        if symbol_name == binding.name:
            return f"from {binding.module} import {binding.name}"
        return f"from {binding.module} import {binding.name} as {symbol_name}"

    root_name = binding.module.split(".", 1)[0]
    if root_name in internal_roots:
        return None
    if symbol_name == root_name:
        return f"import {binding.module}"
    return f"import {binding.module} as {symbol_name}"


def referenced_import_lines(
    node: ast.ClassDef,
    import_bindings: dict[str, ImportBinding],
    module_symbols: set[str],
    module_name: str,
    import_targets: dict[ImportTarget, ImportTarget],
    internal_roots: set[str],
) -> tuple[str, ...]:
    lines: list[str] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            if child.id in module_symbols or child.id == "object":
                continue
            binding = import_bindings.get(child.id)
            if not binding:
                continue
            if line := import_line_for_binding(
                binding, child.id, module_name, import_targets, internal_roots
            ):
                if line not in seen:
                    seen.add(line)
                    lines.append(line)
        elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            binding = import_bindings.get(child.value.id)
            if not binding or binding.name is not None:
                continue
            if line := import_line_for_binding(
                binding,
                child.value.id,
                module_name,
                import_targets,
                internal_roots,
            ):
                if line not in seen:
                    seen.add(line)
                    lines.append(line)

    return tuple(lines)


def type_checking_import_lines(
    root: Path,
    classes: list[BindingClass],
    existing_source: str = "",
) -> list[str]:
    lines: list[str] = []
    for source in sorted({klass.source for klass in classes}):
        tree = parse_python_source(root / source)
        if not tree:
            continue
        for node in tree.body:
            if not isinstance(node, ast.If) or not type_checking_test(node.test):
                continue
            for item in node.body:
                if isinstance(item, (ast.Import, ast.ImportFrom)):
                    line = import_stmt_line(item)
                    if line not in existing_source and line not in lines:
                        lines.append(line)

    if not lines:
        return []
    return ["if TYPE_CHECKING:", *(f"    {line}" for line in lines), ""]


def module_symbol_renames(classes: list[BindingClass], module_name: str) -> dict[str, str]:
    renames: dict[str, str] = {}
    for klass in classes:
        symbol = class_public_symbol(klass, module_name)
        if not symbol:
            continue
        renames.setdefault(klass.class_name, symbol)
        renames.setdefault(klass.export_name, symbol)
    return renames


def public_name_target(public_name: str) -> tuple[str, str] | None:
    if "." not in public_name:
        return None
    module_name, symbol = public_name.rsplit(".", 1)
    if not module_name or not valid_identifier(symbol):
        return None
    return module_name, symbol


def class_public_targets(klass: BindingClass) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for public_name in klass.public_names:
        target = public_name_target(public_name)
        if not target or target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return targets


def canonical_class_public_target(klass: BindingClass) -> tuple[str, str] | None:
    targets = class_public_targets(klass)
    if not targets:
        return None
    if klass.source.startswith("src/Base/"):
        for target in targets:
            if target[0] == "FreeCAD.Base":
                return target
    return targets[0]


def class_public_symbol(klass: BindingClass, module_name: str) -> str | None:
    for public_module_name, symbol in class_public_targets(klass):
        if public_module_name == module_name:
            return symbol
    return None


def class_alias_stub_line(
    module_name: str,
    symbol: str,
    target_module_name: str,
    target_symbol: str,
) -> str:
    if module_name == target_module_name:
        return f"{symbol} = {target_symbol}"
    if target_module_name.startswith(f"{module_name}."):
        relative_module = target_module_name.removeprefix(module_name)
        return f"from {relative_module} import {target_symbol} as {symbol}"
    return f"from {target_module_name} import {target_symbol} as {symbol}"


def class_public_alias_targets(
    klass: BindingClass,
) -> list[tuple[str, str, str, str]]:
    canonical_target = canonical_class_public_target(klass)
    if not canonical_target:
        return []
    target_module_name, target_symbol = canonical_target
    return [
        (module_name, symbol, target_module_name, target_symbol)
        for module_name, symbol in class_public_targets(klass)
        if (module_name, symbol) != canonical_target
    ]


def class_public_alias_line(klass: BindingClass, module_name: str) -> tuple[str, str] | None:
    for public_module_name, symbol, target_module_name, target_symbol in class_public_alias_targets(
        klass
    ):
        if public_module_name == module_name:
            return (
                symbol,
                class_alias_stub_line(module_name, symbol, target_module_name, target_symbol),
            )
    return None


def validate_public_class_aliases(classes: list[BindingClass]) -> None:
    errors: list[str] = []
    for klass in classes:
        public_names = list(dict.fromkeys(klass.public_names))
        if len(public_names) < 2:
            continue
        targets = class_public_targets(klass)
        if len(targets) != len(public_names):
            errors.append(
                f"{klass.source}:{klass.line} {klass.class_name} has unsupported public names: "
                + ", ".join(public_names)
            )
            continue
        if not canonical_class_public_target(klass):
            errors.append(f"{klass.source}:{klass.line} {klass.class_name} has no canonical target")
            continue
        aliases = class_public_alias_targets(klass)
        if len(aliases) != len(targets) - 1:
            errors.append(
                f"{klass.source}:{klass.line} {klass.class_name} has {len(targets)} public "
                f"targets but only {len(aliases)} generated aliases"
            )
    if errors:
        raise ValueError("invalid multi-public class alias plan:\n  " + "\n  ".join(errors))


def public_class_stub_source(
    root: Path,
    klass: BindingClass,
    module_name: str,
    renames: dict[str, str],
    module_symbols: set[str],
    import_targets: dict[ImportTarget, ImportTarget],
    internal_roots: set[str],
) -> PublicClassStub | None:
    symbol = class_public_symbol(klass, module_name)
    if not symbol:
        return None
    node = class_node(root, klass)
    if not node:
        return None
    import_bindings = transformed_import_bindings(
        source_import_bindings(root, klass.source), renames
    )
    public_base_names = set(module_symbols)
    public_base_modules: set[str] = set()
    for base in node.bases:
        match base:
            case ast.Name(id=base_name):
                transformed_name = renames.get(base_name, base_name)
                if transformed_name == "object":
                    public_base_names.add("object")
                    continue
                binding = import_bindings.get(transformed_name)
                if not binding:
                    continue
                if import_line_for_binding(
                    binding,
                    transformed_name,
                    module_name,
                    import_targets,
                    internal_roots,
                ):
                    public_base_names.add(transformed_name)
                elif (
                    binding.name is not None
                    and (target := import_targets.get((binding.module, binding.name)))
                    and target[0] == module_name
                ):
                    public_base_names.add(transformed_name)
            case ast.Attribute(value=ast.Name(id=module_alias)):
                binding = import_bindings.get(module_alias)
                if not binding or binding.name is not None:
                    continue
                if import_line_for_binding(
                    binding,
                    module_alias,
                    module_name,
                    import_targets,
                    internal_roots,
                ):
                    public_base_modules.add(module_alias)
            case _:
                continue

    transformer = PublicClassStubTransformer(
        module_name,
        symbol,
        renames,
        public_base_names,
        public_base_modules,
    )
    transformed = transformer.visit(copy.deepcopy(node))
    ast.fix_missing_locations(transformed)
    import_lines = list(
        referenced_import_lines(
            transformed,
            import_bindings,
            module_symbols,
            module_name,
            import_targets,
            internal_roots,
        )
    )
    for root_name in sorted(transformer.annotation_module_roots_needed):
        line = f"import {root_name}"
        if line not in import_lines:
            import_lines.insert(0, line)
    return PublicClassStub(
        source=ast.unparse(transformed),
        import_lines=tuple(import_lines),
    )


def class_stub_lines(
    root: Path,
    module_classes: list[BindingClass],
    module_name: str,
    all_classes: list[BindingClass] | None = None,
    include_future_import: bool = True,
    skip_symbols: set[str] | None = None,
    existing_source: str = "",
) -> list[str]:
    all_classes = all_classes or module_classes
    header = [
        "# Generated public class stubs from binding .pyi specs.",
    ]
    if include_future_import:
        header.append("from __future__ import annotations")
    body: list[str] = []
    extra_import_lines: list[str] = []
    seen: set[str] = set()
    skip_symbols = skip_symbols or set()
    renames = module_symbol_renames(module_classes, module_name)
    module_symbols = {
        symbol
        for klass in module_classes
        if (symbol := class_public_symbol(klass, module_name)) is not None
    }
    import_targets = public_import_target_index(all_classes)
    internal_roots = known_stub_module_roots(all_classes)
    alias_lines: list[str] = []
    for klass in module_classes:
        alias = class_public_alias_line(klass, module_name)
        if not alias:
            continue
        symbol, line = alias
        if symbol in seen or symbol in skip_symbols:
            continue
        alias_lines.append(line)
        seen.add(symbol)
    body.extend(alias_lines)
    if alias_lines:
        body.append("")
    for klass in module_classes:
        symbol = class_public_symbol(klass, module_name)
        if not symbol or symbol in seen or symbol in skip_symbols:
            continue
        stub = public_class_stub_source(
            root,
            klass,
            module_name,
            renames,
            module_symbols,
            import_targets,
            internal_roots,
        )
        if stub:
            for line in stub.import_lines:
                if line not in existing_source and line not in extra_import_lines:
                    extra_import_lines.append(line)
            body.append(f"# {klass.source}:{klass.line}")
            body.append(stub.source)
        else:
            body.append(f"class {symbol}:  # {klass.source}:{klass.line}")
            body.append("    ...")
        body.append("")
        seen.add(symbol)
    if not body:
        return []
    header.extend(extra_import_lines)
    if extra_import_lines:
        header.append("")
    header.extend(["from typing import *", ""])
    header.extend(type_checking_import_lines(root, module_classes, existing_source))
    return header + body


def write_class_stubs(out_dir: Path, root: Path, classes: list[BindingClass]) -> None:
    for module_name, group in sorted(group_classes_by_module(classes).items()):
        path = out_dir / "modules" / f"{safe_stub_name(module_name)}.pyi"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(class_stub_lines(root, group, module_name, all_classes=classes)).rstrip()
            + "\n",
            encoding="utf-8",
        )


def append_class_stubs(
    out_dir: Path,
    root: Path,
    classes: list[BindingClass],
    module_names: set[str] | None = None,
) -> int:
    module_names = module_names or module_names_from_classes(classes)
    suppressed = 0
    for module_name, group in sorted(group_classes_by_module(classes).items()):
        path = module_stub_path(out_dir, module_name, module_names)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        existing_symbols = public_stub_symbols(existing)
        suppressed += sum(
            1
            for klass in group
            if (symbol := class_public_symbol(klass, module_name)) and symbol in existing_symbols
        )
        class_lines = "\n".join(
            class_stub_lines(
                root,
                group,
                module_name,
                all_classes=classes,
                include_future_import=not existing.strip(),
                skip_symbols=existing_symbols,
                existing_source=existing,
            )
        ).rstrip()
        if not class_lines:
            continue
        separator = "\n\n" if existing else ""
        path.write_text(existing.rstrip() + separator + class_lines + "\n", encoding="utf-8")
    return suppressed


def copy_overlay_stubs(
    overlay_dir: Path,
    target_dir: Path,
    module_names: set[str] | None = None,
) -> int:
    count = 0
    if not overlay_dir.exists():
        return count

    for source in sorted(overlay_dir.rglob("*.pyi")):
        relative = source.relative_to(overlay_dir)
        module_name = overlay_module_name(relative)
        target = (
            module_stub_path(target_dir, module_name, module_names)
            if module_names and module_name
            else target_dir / relative
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        count += 1

    return count


def leading_comment_block(source: str) -> str:
    lines = source.splitlines()
    leading: list[str] = []
    for line in lines:
        if line.startswith("#") or not line.strip():
            leading.append(line)
            continue
        break
    return "\n".join(leading).rstrip()


def top_level_symbol_names(node: ast.stmt) -> set[str]:
    match node:
        case ast.ClassDef(name=name) | ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name):
            return {name}
        case ast.AnnAssign(target=ast.Name(id=name)):
            return {name}
        case ast.Assign(targets=targets):
            return {target.id for target in targets if isinstance(target, ast.Name)}
        case ast.Import(names=names):
            return {alias.asname or alias.name.split(".", 1)[0] for alias in names}
        case ast.ImportFrom(names=names):
            return {alias.asname or alias.name for alias in names if alias.name != "*"}
        case _:
            return set()


def class_member_name(node: ast.stmt) -> str | None:
    match node:
        case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name) | ast.ClassDef(name=name):
            return name
        case ast.AnnAssign(target=ast.Name(id=name)):
            return name
        case ast.Assign(targets=targets):
            for target in targets:
                if isinstance(target, ast.Name):
                    return target.id
            return None
        case _:
            return None


def merge_class_overlay_module(target_source: str, overlay_source: str) -> str:
    target_tree = ast.parse(target_source)
    overlay_tree = ast.parse(overlay_source)

    target_classes = {
        node.name: node for node in target_tree.body if isinstance(node, ast.ClassDef)
    }
    target_symbols = public_stub_symbols(target_source)

    for node in overlay_tree.body:
        if isinstance(node, ast.ClassDef):
            existing = target_classes.get(node.name)
            if existing is None:
                copied_node = copy.deepcopy(node)
                target_tree.body.append(copied_node)
                target_classes[node.name] = copied_node
                target_symbols.add(node.name)
                continue

            overlay_docstring = (
                len(node.body) > 0
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            overlay_members = node.body[1:] if overlay_docstring else node.body
            replacement_names = {
                name
                for member in overlay_members
                if (name := class_member_name(member)) is not None
            }
            preserved_body: list[ast.stmt] = []
            for member in existing.body:
                member_name = class_member_name(member)
                if member_name is not None and member_name in replacement_names:
                    continue
                preserved_body.append(member)
            existing.body = preserved_body + [copy.deepcopy(member) for member in overlay_members]
            continue

        names = top_level_symbol_names(node)
        if names and names.issubset(target_symbols):
            continue
        insertion_index = 0
        while insertion_index < len(target_tree.body):
            current = target_tree.body[insertion_index]
            if (
                isinstance(current, ast.Expr)
                and isinstance(current.value, ast.Constant)
                and isinstance(current.value.value, str)
            ):
                insertion_index += 1
                continue
            if isinstance(current, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)):
                insertion_index += 1
                continue
            break
        target_tree.body.insert(insertion_index, copy.deepcopy(node))
        target_symbols |= names

    merged = ast.unparse(target_tree).rstrip() + "\n"
    preamble = leading_comment_block(target_source)
    if preamble:
        return f"{preamble}\n\n{merged}"
    return merged


def apply_class_overlay_stubs(
    class_overlay_dir: Path,
    target_dir: Path,
    module_names: set[str] | None = None,
) -> int:
    count = 0
    if not class_overlay_dir.exists():
        return count

    for source in sorted(class_overlay_dir.rglob("*.pyi")):
        relative = source.relative_to(class_overlay_dir)
        module_name = overlay_module_name(relative)
        target = (
            module_stub_path(target_dir, module_name, module_names)
            if module_names and module_name
            else target_dir / relative
        )
        if not target.exists():
            continue
        merged = merge_class_overlay_module(
            target.read_text(encoding="utf-8"),
            source.read_text(encoding="utf-8"),
        )
        target.write_text(merged, encoding="utf-8")
        count += 1

    return count


def markdown_report(methods: list[BindingMethod]) -> str:
    by_family = Counter(method.family for method in methods)
    by_context = Counter(
        method.inferred_module or f"{method.context_kind}:{method.context_name}"
        for method in methods
    )
    generated_count = sum(method.generated_source for method in methods)

    lines = [
        "# FreeCAD Python Binding Inventory",
        "",
        f"Total registrations: {len(methods)}",
        f"Generated implementation sources included: {generated_count}",
        "",
        "## Families",
        "",
    ]
    for family, count in by_family.most_common():
        lines.append(f"- `{family}`: {count}")

    lines.extend(["", "## Contexts", ""])
    for context, count in by_context.most_common():
        lines.append(f"- `{context}`: {count}")

    lines.extend(["", "## Registrations", ""])
    for method in methods:
        context = method.inferred_module or f"{method.context_kind}:{method.context_name}"
        doc = method.doc.splitlines()[0].strip() if method.doc else ""
        doc_suffix = f" - {doc}" if doc else ""
        lines.append(
            f"- `{context}.{method.python_name}` "
            f"({method.family}, {method.method_kind}) "
            f"[`{method.source}:{method.line}`]{doc_suffix}"
        )

    return "\n".join(lines) + "\n"


def write_outputs(
    out_dir: Path,
    root: Path,
    methods: list[BindingMethod],
    classes: list[BindingClass],
    type_registrations: dict[str, list[str]],
    stub_signature_overrides: StubSignatureOverrides,
    overlay_dir: Path | None = None,
    class_overlay_dir: Path | None = None,
) -> int:
    validate_public_class_aliases(classes)
    out_dir.mkdir(parents=True, exist_ok=True)
    registration_stub_dir = Path("debug/registration-stubs")
    class_stub_dir = Path("debug/class-stubs")
    for generated_dir in (
        "generated-stubs",
        "generated-class-stubs",
        "stubs",
        registration_stub_dir,
        class_stub_dir,
    ):
        shutil.rmtree(out_dir / generated_dir, ignore_errors=True)

    write_stubs(out_dir / registration_stub_dir, methods, stub_signature_overrides)
    write_class_stubs(out_dir / class_stub_dir, root, classes)
    module_names = public_module_names(
        methods, classes, type_registrations, overlay_dir, class_overlay_dir
    )
    write_public_module_stubs(out_dir / "stubs", methods, module_names, stub_signature_overrides)
    overlay_count = (
        copy_overlay_stubs(overlay_dir, out_dir / "stubs", module_names) if overlay_dir else 0
    )
    append_type_stubs(
        out_dir / "stubs",
        methods,
        type_registrations,
        stub_signature_overrides,
        module_names,
    )
    append_class_stubs(out_dir / "stubs", root, classes, module_names)
    if class_overlay_dir:
        apply_class_overlay_stubs(class_overlay_dir, out_dir / "stubs", module_names)
    return overlay_count
