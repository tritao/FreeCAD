#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Project the canonical Python API model into the FreeCAD WASM schema."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/Tools"))
sys.path.insert(0, str(ROOT / "src/Tools/typing"))

from python_api_model.model import ApiAttribute, ApiCallableGroup, ApiClass, ApiModule  # noqa: E402
from python_api_model.signatures import (  # noqa: E402
    ArgumentKind,
    CallableSignature,
    SignatureParameter,
)
from python_api_model.types import ApiType, ApiTypeKind, parse_annotation  # noqa: E402
from stubgen.api_extract import extract_curated_api_model_with_diagnostics  # noqa: E402


SCHEMA_VERSION = 0

# These types are represented inline in the guest ABI rather than as host
# object handles. Keep this list explicit until the API metadata has a first
# class value-type annotation.
WASM_VALUE_TYPES = {
    "FreeCAD.Base.Vector": {"encoding": "vector3-f64"},
}


def _literal_kwargs(decorator: str, name: str) -> dict[str, Any]:
    try:
        node = ast.parse(decorator, mode="eval").body
    except SyntaxError:
        return {}
    if not isinstance(node, ast.Call):
        return {}
    target = node.func
    target_name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", "")
    if target_name != name:
        return {}

    result: dict[str, Any] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        try:
            result[keyword.arg] = ast.literal_eval(keyword.value)
        except (SyntaxError, ValueError):
            continue
    return result


def _export_kwargs(api_class: ApiClass) -> dict[str, Any]:
    for decorator in api_class.decorators:
        kwargs = _literal_kwargs(decorator, "export")
        if kwargs:
            return kwargs
    return {}


def _native_metadata(api_class: ApiClass) -> dict[str, Any]:
    kwargs = _export_kwargs(api_class)
    return {
        "namespace": kwargs.get("Namespace", api_class.module_name),
        "type": kwargs.get("Twin", api_class.name),
        "pointer": kwargs.get("TwinPointer", kwargs.get("Twin", api_class.name)),
        "include": kwargs.get("Include"),
    }


def _json_literal(value: object) -> object:
    if isinstance(value, tuple):
        return [_json_literal(item) for item in value]
    if isinstance(value, list):
        return [_json_literal(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_literal(item) for key, item in value.items()}
    return value


def _wasm_type(api_type: ApiType | None, annotation: str | None, module_name: str) -> dict[str, Any]:
    if api_type is None:
        api_type = parse_annotation(annotation, module_name)
    if api_type is None:
        api_type = ApiType(kind=ApiTypeKind.VALUE, annotation="object")

    result: dict[str, Any] = {"kind": api_type.kind.value, "annotation": api_type.annotation}
    if api_type.kind is ApiTypeKind.INTEGER:
        result["kind"] = "int64"
    elif api_type.kind is ApiTypeKind.FLOAT:
        result["kind"] = "float64"
    elif api_type.kind is ApiTypeKind.BOOLEAN:
        result["kind"] = "bool"
    elif api_type.kind is ApiTypeKind.HANDLE:
        handle_name = api_type.handle or api_type.annotation
        value_type = WASM_VALUE_TYPES.get(handle_name)
        if value_type:
            result["kind"] = "value"
            result["type"] = handle_name
            result["encoding"] = value_type["encoding"]
        else:
            result["kind"] = "handle"
            result["type"] = handle_name
    elif api_type.kind is ApiTypeKind.LIST:
        result["kind"] = "list"
        result["item"] = _wasm_type(api_type.item, None, module_name)
    elif api_type.kind is ApiTypeKind.TUPLE:
        result["kind"] = "tuple"
        result["items"] = [_wasm_type(item, None, module_name) for item in api_type.items]
        result["item"] = _wasm_type(api_type.item, None, module_name)
        result["variadic"] = api_type.variadic
    elif api_type.kind is ApiTypeKind.DICT:
        result["kind"] = "dict"
        result["key"] = _wasm_type(api_type.key, None, module_name)
        result["value"] = _wasm_type(api_type.value, None, module_name)
    elif api_type.kind is ApiTypeKind.OPTIONAL:
        result["kind"] = "optional"
        result["item"] = _wasm_type(api_type.item, None, module_name)
    elif api_type.kind is ApiTypeKind.UNION:
        result["kind"] = "union"
        result["items"] = [_wasm_type(item, None, module_name) for item in api_type.items]
    elif api_type.kind is ApiTypeKind.LITERAL:
        result["kind"] = "literal"
        result["values"] = [_json_literal(value) for value in api_type.literal_values]
    elif api_type.kind is ApiTypeKind.NONE:
        result["kind"] = "none"
    elif api_type.kind is ApiTypeKind.STRING:
        result["kind"] = "string"
    elif api_type.kind is ApiTypeKind.VALUE:
        result["kind"] = "value"
    return result


def _parameter_kind(parameter: SignatureParameter) -> str:
    return {
        ArgumentKind.POSITION_ONLY: "positional_only",
        ArgumentKind.POSITIONAL_OR_KEYWORD: "positional_or_keyword",
        ArgumentKind.VAR_POSITIONAL: "varargs",
        ArgumentKind.KEYWORD_ONLY: "keyword_only",
        ArgumentKind.VAR_KEYWORD: "kwargs",
    }[parameter.kind]


def _binding_metadata(signature: CallableSignature) -> dict[str, Any]:
    for decorator in signature.decorators:
        kwargs = _literal_kwargs(decorator, "binding")
        if kwargs:
            return kwargs
    return {}


def _parameter_model(parameter: SignatureParameter, module_name: str) -> dict[str, Any]:
    return {
        "name": parameter.name,
        "kind": _parameter_kind(parameter),
        "annotation": parameter.annotation,
        "type": _wasm_type(parameter.annotation_type, parameter.annotation, module_name),
        "default": parameter.default,
    }


def _signature_model(
    signature: CallableSignature,
    module_name: str,
    *,
    is_method: bool,
) -> dict[str, Any]:
    parameters = signature.parameters
    if is_method and parameters and parameters[0].name in {"self", "cls"}:
        parameters = parameters[1:]
    metadata = _binding_metadata(signature)
    permission = metadata.get("permission")
    return {
        "name": signature.name,
        "params": [_parameter_model(parameter, module_name) for parameter in parameters],
        "returns": _wasm_type(signature.return_type, signature.return_annotation, module_name),
        "return_annotation": signature.return_annotation,
        "const": any(
            decorator.rsplit(".", 1)[-1] == "constmethod"
            for decorator in signature.decorators
        ),
        "static": signature.flags.staticmethod,
        "class": signature.flags.classmethod,
        "overload": signature.flags.overload,
        "permission": permission,
        "exposed": isinstance(permission, str) and bool(permission),
        "mutates": metadata.get("mutates"),
        "doc": signature.docstring or "",
    }


def _method_model(group: ApiCallableGroup, module_name: str) -> dict[str, Any]:
    return {
        "name": group.name,
        "signatures": [
            _signature_model(signature, module_name, is_method=group.is_method)
            for signature in group.signatures
        ],
    }


def _attribute_model(attribute: ApiAttribute, module_name: str) -> dict[str, Any]:
    return {
        "name": attribute.name,
        "annotation": attribute.annotation,
        "type": _wasm_type(attribute.annotation_type, attribute.annotation, module_name),
        "readonly": attribute.readonly,
        "default": attribute.value,
        "permission": None,
        "exposed": False,
        "doc": attribute.doc or "",
    }


def _class_model(api_class: ApiClass) -> dict[str, Any]:
    value_type = WASM_VALUE_TYPES.get(api_class.qualified_name)
    return {
        "module": api_class.module_name,
        "name": api_class.name,
        "full_name": api_class.qualified_name,
        "source": api_class.location.path if api_class.location else None,
        "base": api_class.bases[0] if api_class.bases else None,
        "handle_type": None if value_type else api_class.qualified_name,
        "representation": (
            {"kind": "value", **value_type}
            if value_type
            else {"kind": "handle"}
        ),
        "native": _native_metadata(api_class),
        "attributes": [
            _attribute_model(attribute, api_class.module_name)
            for attribute in api_class.attributes
        ],
        "methods": [_method_model(method, api_class.module_name) for method in api_class.methods],
        "doc": api_class.doc or "",
    }


def _module_functions(module: ApiModule) -> list[dict[str, Any]]:
    return [_method_model(function, module.name) for function in module.functions]


def _operation_sources(api_model: Any) -> set[str]:
    sources: set[str] = set()
    for module in api_model.modules:
        for function in module.functions:
            sources.add(f"{module.name}.{function.name}")
        for api_class in module.classes:
            sources.add(api_class.qualified_name)
            for attribute in api_class.attributes:
                sources.add(f"{api_class.qualified_name}.{attribute.name}")
            for method in api_class.methods:
                sources.add(f"{api_class.qualified_name}.{method.name}")
    return sources


def _validate_operation_catalog(operations: list[dict[str, Any]]) -> None:
    seen_names: set[str] = set()
    seen_wire_names: set[str] = set()
    seen_guest_methods: set[str] = set()
    seen_ids: dict[int, str] = {}
    required_string_fields = ("name", "wire_name", "guest_method")

    for operation in operations:
        for field in required_string_fields:
            value = operation.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(f"WASM operation has an invalid '{field}'")

        name = operation["name"]
        wire_name = operation["wire_name"]
        guest_method = operation["guest_method"]
        if name in seen_names:
            raise ValueError(f"WASM operation '{name}' is duplicated")
        if wire_name in seen_wire_names:
            raise ValueError(f"WASM wire name '{wire_name}' is duplicated")
        if guest_method in seen_guest_methods:
            raise ValueError(f"WASM guest method '{guest_method}' is duplicated")
        seen_names.add(name)
        seen_wire_names.add(wire_name)
        seen_guest_methods.add(guest_method)

        operation_id = operation.get("id")
        if (
            isinstance(operation_id, bool)
            or not isinstance(operation_id, int)
            or not 0 < operation_id <= 0xFF
        ):
            raise ValueError(f"WASM operation '{name}' has an invalid id")
        previous_name = seen_ids.get(operation_id)
        if previous_name is not None:
            raise ValueError(
                f"WASM operation id {operation_id} is used by both "
                f"'{previous_name}' and '{name}'"
            )
        seen_ids[operation_id] = name

        permission = operation.get("permission")
        if permission is not None and (not isinstance(permission, str) or not permission):
            raise ValueError(f"WASM operation '{name}' has an invalid permission")
        mutates = operation.get("mutates")
        if not isinstance(mutates, bool):
            raise ValueError(f"WASM operation '{name}' has an invalid mutates flag")
        transaction = operation.get("transaction")
        if transaction is not None and transaction not in {"required", "open", "commit", "abort"}:
            raise ValueError(f"WASM operation '{name}' has an invalid transaction policy")
        if transaction is not None and not mutates:
            raise ValueError(f"WASM operation '{name}' transaction policy must mutate")

        requirements = operation.get("requires", [])
        if not isinstance(requirements, list) or not all(
            isinstance(requirement, str) and requirement for requirement in requirements
        ):
            raise ValueError(f"WASM operation '{name}' has invalid requirements")
        if not isinstance(operation.get("params"), list):
            raise ValueError(f"WASM operation '{name}' has invalid parameters")
        for parameter in operation["params"]:
            parameter_type = parameter.get("type", {})
            if parameter_type.get("kind") == "handle":
                ownership = parameter.get("ownership", "borrowed")
                if ownership not in {"owned", "borrowed"}:
                    raise ValueError(
                        f"WASM operation '{name}' has invalid parameter ownership"
                    )
        if not isinstance(operation.get("returns"), dict):
            raise ValueError(f"WASM operation '{name}' has invalid return metadata")
        returns = operation["returns"]
        if returns.get("kind") == "handle":
            ownership = returns.get("ownership", "borrowed")
            if ownership not in {"owned", "borrowed"}:
                raise ValueError(f"WASM operation '{name}' has invalid handle ownership")
        if "nullable" in returns and not isinstance(returns["nullable"], bool):
            raise ValueError(f"WASM operation '{name}' has invalid nullability")
        if "consumes" in operation and not isinstance(operation["consumes"], bool):
            raise ValueError(f"WASM operation '{name}' has invalid consumes flag")


def _load_operations(root: Path, inputs: list[Path], api_model: Any) -> list[dict[str, Any]]:
    operations_path = root / "src/Mod/Wasm/WasmApiOperations.json"
    if not operations_path.exists():
        return []

    model = json.loads(operations_path.read_text(encoding="utf-8"))
    input_paths = {path.resolve().relative_to(root).as_posix() for path in inputs}
    sources = _operation_sources(api_model)
    operations = model.get("operations", [])
    defaults = model.get("defaults", {})
    if not isinstance(operations, list):
        raise ValueError("WASM operation catalog must contain an operations list")
    _validate_operation_catalog(operations)

    selected_operations = []
    for operation in operations:
        requirements = operation.get("requires", [])
        if not all(requirement in input_paths for requirement in requirements):
            continue
        source = operation.get("source")
        if source is not None and source not in sources:
            raise ValueError(
                f"WASM operation {operation.get('name', '<unnamed>')} references "
                f"missing .pyi symbol '{source}'"
            )
        operation.setdefault("fallible", defaults.get("fallible", True))
        returns = operation.setdefault("returns", {})
        returns.setdefault("nullable", defaults.get("nullable", False))
        if returns.get("kind") == "handle":
            returns.setdefault(
                "ownership", defaults.get("handle_ownership", "borrowed")
            )
        for parameter in operation.get("params", []):
            if parameter.get("type", {}).get("kind") == "handle":
                parameter.setdefault("ownership", "borrowed")
        selected_operations.append(operation)
    return selected_operations


def build_model(root: Path, inputs: list[Path]) -> dict[str, Any]:
    model, diagnostics = extract_curated_api_model_with_diagnostics(
        root,
        root / "src",
        source_paths=inputs,
    )
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        rendered = "\n".join(f"error: {diagnostic.message}" for diagnostic in errors)
        raise ValueError(rendered)

    classes = [
        _class_model(api_class)
        for module in model.modules
        for api_class in module.classes
    ]
    functions = [
        function
        for module in model.modules
        for function in _module_functions(module)
    ]
    aliases = [
        {"public_path": alias.public_path, "target_path": alias.target_path}
        for module in model.modules
        for alias in module.aliases
    ]
    return {
        "schema": "org.freecad.wasm.api",
        "schema_version": SCHEMA_VERSION,
        "api": f"org.freecad.wasm.api@{SCHEMA_VERSION}",
        "permission_policy": "deny-by-default",
        "abi": {
            "request_magic": "FCWA",
            "response_magic": "FCWR",
            "request_version": 1,
            "response_version": 1,
            "request_header_size": 12,
            "response_header_size": 12,
            "error_codes": {
                "none": 0,
                "invalid_request": 1,
                "permission_denied": 2,
                "invalid_handle": 3,
                "unsupported": 4,
                "limit_exceeded": 5,
                "host_failure": 6,
                "protocol": 7,
            },
        },
        "operations": _load_operations(root, inputs, model),
        "classes": classes,
        "functions": functions,
        "aliases": aliases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inputs = [path.resolve() for path in args.inputs]
    output = args.output.resolve()
    result = build_model(ROOT, inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
