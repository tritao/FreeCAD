"""Shared definitions for the stub generation pipeline.

This module is the schema layer for the tooling. It centralizes:
- immutable configuration such as default input directories
- regexes used to recognize C++ binding patterns
- enums and type aliases shared across parsing and generation
- dataclasses that represent discovered bindings and emitted stub fragments

It intentionally contains only inert definitions. Parsing behavior, manual rule
interpretation, and output generation live elsewhere so this file stays safe to
read first when orienting within the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
import re
from typing import Literal, TypeAlias

SOURCE_EXTENSIONS = {".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
SKIPPED_SOURCE_PREFIXES = (
    ("src", "3rdParty"),
    ("src", "Tools", "bindings", "stubs", "generated"),
    ("src", "Tools", "bindings", "stubs", "inputs"),
    ("src", "Tools", "bindings", "templates"),
)
DEFAULT_OVERLAY_DIR = Path("src/Tools/bindings/stubs/inputs/overlays")
DEFAULT_OVERRIDE_DIR = Path("src/Tools/bindings/stubs/inputs/pycxx-overrides")
MODULE_STUB_PYI_SUFFIX = ".module.pyi"

ADD_METHOD_RE = re.compile(r"\b(?P<kind>add_(?:varargs|keyword|noargs)_method)\s*\(")
BEHAVIOR_NAME_RE = re.compile(r"\bbehaviors\s*\(\s*\)\s*\.\s*name\s*\(\s*\"([^\"]+)\"\s*\)")
EXTENSION_MODULE_RE = re.compile(
    r"\bPy::ExtensionModule\s*<\s*(?P<cpp_name>[\w:]+)\s*>\s*"
    r"\(\s*\"(?P<python_name>[^\"]+)\"\s*\)"
)
PYMETHODDEF_RE = re.compile(
    r"(?:static\s+)?(?:const\s+)?(?:struct\s+)?PyMethodDef\s+"
    r"(?P<table>(?:[A-Za-z_]\w*::)*[A-Za-z_]\w*)\s*\[\s*\]\s*=\s*\{"
)
PYMODULEDEF_RE = re.compile(
    r"(?:static\s+)?(?:struct\s+)?PyModuleDef\s+" r"(?P<definition>[A-Za-z_]\w*)\s*=\s*\{"
)
PYMODULE_CREATE_RE = re.compile(
    r"(?:PyObject\s*\*\s*)?(?P<variable>[A-Za-z_]\w*)\s*=\s*"
    r"PyModule_Create\s*\(\s*&(?P<definition>[A-Za-z_]\w*)\s*\)"
)
PYMODULE_IMPORT_RE = re.compile(
    r"(?:PyObject\s*\*\s*)?(?P<variable>[A-Za-z_]\w*)\s*=\s*"
    r"PyImport_ImportModule\s*\(\s*\"(?P<module>[^\"]+)\"\s*\)"
)
PYMODULE_ADD_OBJECT_RE = re.compile(
    r"PyModule_AddObject\s*\(\s*(?P<parent>[A-Za-z_]\w*)\s*,\s*"
    r"\"(?P<name>[^\"]+)\"\s*,\s*(?P<child>[A-Za-z_]\w*)\s*\)"
)
PYMODULE_ADD_FUNCTIONS_RE = re.compile(
    r"PyModule_AddFunctions\s*\(\s*(?P<module>[A-Za-z_]\w*)\s*,\s*"
    r"(?P<table>(?:[A-Za-z_]\w*::)*[A-Za-z_]\w*)\s*\)"
)
PYMETHOD_ALIAS_RE = re.compile(
    r"\b(?P<alias>[A-Za-z_]\w*)\s*=\s*" r"(?P<table>(?:[A-Za-z_]\w*::)*[A-Za-z_]\w*)\s*;"
)
STRING_LITERAL_RE = re.compile(r'(?:u8|u|U|L)?("(?:\\.|[^"\\])*")')
INIT_MODULE_RE = re.compile(
    r"(?:PyObject\s*\*\s*)?(?P<variable>[A-Za-z_]\w*)\s*=\s*"
    r"(?P<namespace>[A-Za-z_]\w*)::initModule\s*\(\s*\)"
)
PY_OBJECT_WRAPPER_RE = re.compile(
    r"Py::Object\s+(?P<variable>[A-Za-z_]\w*)\s*\(\s*(?P<source>[A-Za-z_]\w*)\s*\)"
)
PYIMPORT_ADD_MODULE_RE = re.compile(
    r"(?:PyObject\s*\*\s*)?(?P<variable>[A-Za-z_]\w*)\s*=\s*"
    r"PyImport_AddModule\s*\(\s*\"(?P<module>[^\"]+)\"\s*\)"
)
GETATTR_MODULE_RE = re.compile(
    r"PyObject\s*\*\s*(?P<variable>[A-Za-z_]\w*)\s*"
    r"\(\s*(?P<owner>[A-Za-z_]\w*)\.getAttr\s*\(\s*\"(?P<name>[^\"]+)\"\s*\)\.ptr\s*\(\s*\)\s*\)"
)
ADDTYPE_RE = re.compile(
    r"\baddType\s*\(\s*(?P<type>.+?)\s*,\s*(?P<module>[A-Za-z_]\w*)\s*,\s*" r"\"(?P<name>[^\"]+)\"",
    re.DOTALL,
)
CPP_TYPE_NAME_RE = re.compile(r"((?:[A-Za-z_]\w*\s*::\s*)*[A-Za-z_]\w*)\s*::\s*Type\b")
HELPER_PYI_FILES = {
    "src/Base/Metadata.pyi",
    "src/Base/PyObjectBase.pyi",
}
PUBLIC_STUB_DECORATORS = {
    "classmethod",
    "overload",
    "staticmethod",
}

BindingFamily: TypeAlias = Literal["pycxx_add_method", "pymethoddef"]
ContextKind: TypeAlias = Literal["pycxx_module", "pymethoddef_table", "python_type", "unknown"]
MethodKind: TypeAlias = Literal["keyword", "noargs", "varargs"]
ContextEntry: TypeAlias = tuple[int, ContextKind, str]
ImportTarget: TypeAlias = tuple[str, str]


class ScannerState(Enum):
    CODE = auto()
    LINE_COMMENT = auto()
    BLOCK_COMMENT = auto()
    STRING = auto()
    CHAR = auto()


@dataclass(frozen=True)
class BindingMethod:
    family: BindingFamily
    source: str
    line: int
    table: str | None
    context_kind: ContextKind
    context_name: str
    inferred_module: str | None
    method_kind: MethodKind
    python_name: str
    cxx_callable: str
    flags: str
    doc: str
    generated_source: bool


@dataclass(frozen=True)
class ModuleDef:
    source: str
    name: str
    table: str | None


@dataclass(frozen=True)
class BindingClass:
    source: str
    line: int
    class_name: str
    export_name: str
    python_name: str | None
    public_names: list[str]
    base_class: str | None
    explicit_export: bool


@dataclass(frozen=True)
class PublicTypeTarget:
    module_name: str
    class_symbol: str
    variable_symbol: str | None = None
    base_symbols: tuple[str, ...] = ()


PublicTypeGroup = tuple[str, str | None, tuple[str, ...], list[BindingMethod]]


@dataclass(frozen=True)
class StubSignature:
    parameters: str
    returns: str
    class_symbol: str | None = None


@dataclass(frozen=True)
class ImportBinding:
    module: str
    name: str | None = None


@dataclass(frozen=True)
class PublicClassStub:
    source: str
    import_lines: tuple[str, ...] = ()


StubSignatureKey: TypeAlias = tuple[str, str, str]
StubSignatureGroup: TypeAlias = tuple[StubSignature, ...]
StubSignatureOverrides: TypeAlias = dict[StubSignatureKey, StubSignatureGroup]
