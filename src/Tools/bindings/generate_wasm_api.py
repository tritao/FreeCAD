#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Project the canonical Python API model into the FreeCAD WASM schema."""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping
import hashlib
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
from extension_api_model import (  # noqa: E402
    ExtensionApiModel,
    load_extension_namespace,
    project_api_model,
)
from stubgen.api_extract import extract_curated_api_model_with_diagnostics  # noqa: E402
from wasm_api_model import (  # noqa: E402
    AbiLock,
    WasmAbiModel,
    guest_method_name,
    load_abi_lock,
    load_wasm_adapters,
    operation_name,
)


SCHEMA_VERSION = 0

WASM_OPERATION_DEFAULTS = {
    "fallible": True,
    "nullable": False,
    "handle_ownership": "owned",
}

# This is ABI lowering, not API classification. The extension model decides
# whether a type is a value or resource; this table decides how a value is
# encoded on the current WASM wire format.
WASM_VALUE_ENCODINGS = {
    "FreeCAD.Base.Vector": "vector3-f64",
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


def _wasm_type(
    api_type: ApiType | None,
    annotation: str | None,
    module_name: str,
    *,
    value_type_encodings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
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
        value_encoding = (value_type_encodings or {}).get(handle_name)
        if value_encoding:
            result["kind"] = "value"
            result["type"] = handle_name
            result["encoding"] = value_encoding
        else:
            result["kind"] = "handle"
            result["type"] = handle_name
    elif api_type.kind is ApiTypeKind.LIST:
        result["kind"] = "list"
        result["item"] = _wasm_type(
            api_type.item,
            None,
            module_name,
            value_type_encodings=value_type_encodings,
        )
    elif api_type.kind is ApiTypeKind.TUPLE:
        result["kind"] = "tuple"
        result["items"] = [
            _wasm_type(item, None, module_name, value_type_encodings=value_type_encodings)
            for item in api_type.items
        ]
        result["item"] = _wasm_type(
            api_type.item,
            None,
            module_name,
            value_type_encodings=value_type_encodings,
        )
        result["variadic"] = api_type.variadic
    elif api_type.kind is ApiTypeKind.DICT:
        result["kind"] = "dict"
        result["key"] = _wasm_type(
            api_type.key,
            None,
            module_name,
            value_type_encodings=value_type_encodings,
        )
        result["value"] = _wasm_type(
            api_type.value,
            None,
            module_name,
            value_type_encodings=value_type_encodings,
        )
    elif api_type.kind is ApiTypeKind.OPTIONAL:
        result["kind"] = "optional"
        result["item"] = _wasm_type(
            api_type.item,
            None,
            module_name,
            value_type_encodings=value_type_encodings,
        )
    elif api_type.kind is ApiTypeKind.UNION:
        result["kind"] = "union"
        result["items"] = [
            _wasm_type(item, None, module_name, value_type_encodings=value_type_encodings)
            for item in api_type.items
        ]
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


def _argument_kind(kind: ArgumentKind) -> str:
    return {
        ArgumentKind.POSITION_ONLY: "positional_only",
        ArgumentKind.POSITIONAL_OR_KEYWORD: "positional_or_keyword",
        ArgumentKind.VAR_POSITIONAL: "varargs",
        ArgumentKind.KEYWORD_ONLY: "keyword_only",
        ArgumentKind.VAR_KEYWORD: "kwargs",
    }[kind]


def _parameter_kind(parameter: SignatureParameter) -> str:
    return _argument_kind(parameter.kind)


def _binding_metadata(signature: CallableSignature) -> dict[str, Any]:
    for decorator in signature.decorators:
        kwargs = _literal_kwargs(decorator, "binding")
        if kwargs:
            return kwargs
    return {}


def _parameter_model(
    parameter: SignatureParameter,
    module_name: str,
    *,
    value_type_encodings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "name": parameter.name,
        "kind": _parameter_kind(parameter),
        "annotation": parameter.annotation,
        "type": _wasm_type(
            parameter.annotation_type,
            parameter.annotation,
            module_name,
            value_type_encodings=value_type_encodings,
        ),
        "default": parameter.default,
    }


def _signature_model(
    signature: CallableSignature,
    module_name: str,
    *,
    is_method: bool,
    value_type_encodings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    parameters = signature.parameters
    if is_method and parameters and parameters[0].name in {"self", "cls"}:
        parameters = parameters[1:]
    metadata = _binding_metadata(signature)
    permission = metadata.get("permission")
    return {
        "name": signature.name,
        "params": [
            _parameter_model(
                parameter,
                module_name,
                value_type_encodings=value_type_encodings,
            )
            for parameter in parameters
        ],
        "returns": _wasm_type(
            signature.return_type,
            signature.return_annotation,
            module_name,
            value_type_encodings=value_type_encodings,
        ),
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


def _method_model(
    group: ApiCallableGroup,
    module_name: str,
    *,
    value_type_encodings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "name": group.name,
        "signatures": [
            _signature_model(
                signature,
                module_name,
                is_method=group.is_method,
                value_type_encodings=value_type_encodings,
            )
            for signature in group.signatures
        ],
    }


def _attribute_model(
    attribute: ApiAttribute,
    module_name: str,
    *,
    value_type_encodings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "name": attribute.name,
        "annotation": (
            attribute.annotation_type.annotation
            if attribute.annotation_type is not None
            else attribute.annotation
        ),
        "type": _wasm_type(
            attribute.annotation_type,
            attribute.annotation,
            module_name,
            value_type_encodings=value_type_encodings,
        ),
        "readonly": attribute.readonly,
        "default": attribute.value,
        "permission": None,
        "exposed": False,
        "doc": attribute.doc or "",
    }


def _class_model(
    api_class: ApiClass,
    *,
    value_type_encodings: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    type_metadata = api_class.metadata.extension_type
    is_value_type = type_metadata is not None and type_metadata.representation.value == "value"
    value_encoding = (value_type_encodings or {}).get(api_class.qualified_name)
    if is_value_type and value_encoding is None:
        raise ValueError(
            f"no WASM value encoding is registered for '{api_class.qualified_name}'"
        )
    return {
        "module": api_class.module_name,
        "name": api_class.name,
        "full_name": api_class.qualified_name,
        "source": api_class.location.path if api_class.location else None,
        "base": api_class.bases[0] if api_class.bases else None,
        "handle_type": None if is_value_type else api_class.qualified_name,
        "representation": (
            {"kind": "value", "encoding": value_encoding}
            if is_value_type
            else {"kind": "handle"}
        ),
        "native": _native_metadata(api_class),
        "attributes": [
            _attribute_model(
                attribute,
                api_class.module_name,
                value_type_encodings=value_type_encodings,
            )
            for attribute in api_class.attributes
        ],
        "methods": [
            _method_model(
                method,
                api_class.module_name,
                value_type_encodings=value_type_encodings,
            )
            for method in api_class.methods
        ],
        "doc": api_class.doc or "",
    }


def _module_functions(
    module: ApiModule,
    *,
    value_type_encodings: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    return [
        _method_model(
            function,
            module.name,
            value_type_encodings=value_type_encodings,
        )
        for function in module.functions
    ]


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

        origin = operation.get("origin")
        if origin is not None and origin not in {"projection", "adapter"}:
            raise ValueError(f"WASM operation '{name}' has an invalid origin")
        sdk_service = operation.get("sdk_service")
        if sdk_service is not None and (
            not isinstance(sdk_service, str) or not sdk_service
        ):
            raise ValueError(f"WASM operation '{name}' has an invalid SDK service")

        permission = operation.get("permission")
        if permission is not None and (not isinstance(permission, str) or not permission):
            raise ValueError(f"WASM operation '{name}' has an invalid permission")
        effect = operation.get("effect")
        if effect is not None and effect not in {"read", "compute", "create", "modify"}:
            raise ValueError(f"WASM operation '{name}' has an invalid effect")
        transaction = operation.get("transaction")
        if transaction is not None and transaction not in {"required", "open", "commit", "abort"}:
            raise ValueError(f"WASM operation '{name}' has an invalid transaction policy")
        if transaction is not None and effect not in {"create", "modify"}:
            raise ValueError(f"WASM operation '{name}' transaction policy requires a mutating effect")

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
                if ownership not in {"owned", "borrowed", "consumed"}:
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
        wire_returns = operation.get("wire_returns")
        if wire_returns is not None and not isinstance(wire_returns, dict):
            raise ValueError(f"WASM operation '{name}' has invalid wire return metadata")
        signature = operation.get("signature")
        if not isinstance(signature, str) or not signature:
            raise ValueError(f"WASM operation '{name}' has no ABI signature")
        if signature != _signature(operation):
            raise ValueError(
                f"WASM operation '{name}' ABI signature changed; update the ABI lock"
            )
        if "consumes" in operation and not isinstance(operation["consumes"], bool):
            raise ValueError(f"WASM operation '{name}' has invalid consumes flag")


def _validate_abi_lock(lock: Mapping[str, Any]) -> None:
    seen_ids: dict[int, str] = {}
    seen_wire_names: set[str] = set()
    for stable_id, entry in lock.items():
        if not isinstance(stable_id, str) or not stable_id:
            raise ValueError("WASM ABI lock contains an invalid operation identity")
        if not isinstance(entry, dict):
            raise ValueError(f"WASM ABI lock entry '{stable_id}' is not an object")
        for field in ("id", "wire_name", "signature"):
            value = entry.get(field)
            if field == "id":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or not 0 < value <= 0xFF
                ):
                    raise ValueError(f"WASM ABI lock entry '{stable_id}' has an invalid id")
                previous = seen_ids.get(value)
                if previous is not None:
                    raise ValueError(
                        f"WASM operation id {value} is used by both '{previous}' and '{stable_id}'"
                    )
                seen_ids[value] = stable_id
            elif not isinstance(value, str) or not value:
                raise ValueError(
                    f"WASM ABI lock entry '{stable_id}' has an invalid '{field}'"
                )
        value = entry["wire_name"]
        if value in seen_wire_names:
            raise ValueError(f"WASM ABI lock field 'wire_name' is duplicated: '{value}'")
        seen_wire_names.add(value)


def _validate_retired_abi_lock(
    retired: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> set[int]:
    """Validate retired ABI entries and return their permanently reserved IDs."""

    active_ids = {
        entry["id"]
        for entry in lock.values()
        if isinstance(entry, dict) and isinstance(entry.get("id"), int)
    }
    seen_ids = set(active_ids)
    seen_wire_names = {
        entry["wire_name"]
        for entry in lock.values()
        if isinstance(entry, dict) and isinstance(entry.get("wire_name"), str)
    }
    retired_ids: set[int] = set()

    for stable_id, entry in retired.items():
        if not isinstance(stable_id, str) or not stable_id:
            raise ValueError("WASM retired ABI lock contains an invalid operation identity")
        if stable_id in lock:
            raise ValueError(
                f"WASM ABI operation '{stable_id}' cannot be both active and retired"
            )
        if not isinstance(entry, dict):
            raise ValueError(f"WASM retired ABI entry '{stable_id}' is not an object")
        for field in ("id", "wire_name", "signature", "reason"):
            value = entry.get(field)
            if field == "id":
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or not 0 < value <= 0xFF
                ):
                    raise ValueError(
                        f"WASM retired ABI entry '{stable_id}' has an invalid id"
                    )
                if value in seen_ids:
                    raise ValueError(
                        f"WASM operation id {value} is reused by retired operation "
                        f"'{stable_id}'"
                    )
                seen_ids.add(value)
                retired_ids.add(value)
            elif not isinstance(value, str) or not value:
                raise ValueError(
                    f"WASM retired ABI entry '{stable_id}' has an invalid '{field}'"
                )
        value = entry["wire_name"]
        if value in seen_wire_names:
            raise ValueError(
                f"WASM retired ABI field 'wire_name' is reused: '{value}'"
            )
        seen_wire_names.add(value)

    return retired_ids


def _validate_projected_abi_lock(
    lock: Mapping[str, Any],
    extension_model: ExtensionApiModel,
    input_paths: set[str],
    adapter_sources: Mapping[str, str],
) -> None:
    """Require every selected extension operation to have one ABI owner."""

    projected: dict[str, Any] = {}
    for operation in extension_model.operations:
        location = operation.source_location
        if location is None or location.path in input_paths:
            projected[operation.stable_id] = operation

    missing: list[str] = []
    for stable_id, operation in projected.items():
        adapter_name = adapter_sources.get(operation.source_symbol)
        lock_entry = lock.get(stable_id)
        lock_selected = stable_id in lock
        if stable_id in lock and adapter_name is not None:
            raise ValueError(
                f"WASM extension operation '{stable_id}' is covered by both the ABI lock "
                f"and adapter '{adapter_name}'"
            )
        if not lock_selected and adapter_name is None:
            missing.append(stable_id)
    if missing:
        raise ValueError(
            "WASM ABI lock is missing projected operation(s): "
            + ", ".join(sorted(missing))
        )


def _validate_reserved_catalog_ids(
    operations: list[dict[str, Any]],
    reserved_ids: set[int],
) -> None:
    for operation in operations:
        operation_id = operation.get("id")
        if operation_id in reserved_ids:
            raise ValueError(
                f"WASM operation '{operation.get('name', '<unnamed>')}' reuses reserved "
                f"operation id {operation_id}"
            )


def _receiver_parameter(
    operation: Any,
    value_type_encodings: Mapping[str, str],
) -> dict[str, Any]:
    receiver = operation.receiver
    if receiver is None:
        raise ValueError(f"extension operation '{operation.stable_id}' has no receiver")
    receiver_name = receiver.rsplit(".", 1)[-1]
    parameter_name = {
        "Document": "document",
        "DocumentObject": "object",
        "TopoShape": "shape",
        "Vector": "left",
    }.get(receiver_name, receiver_name[:1].lower() + receiver_name[1:])
    annotation = receiver_name
    module_name = receiver.rsplit(".", 1)[0]
    api_type = parse_annotation(annotation, module_name)
    return {
        "name": parameter_name,
        "type": _wasm_type(
            api_type,
            annotation,
            module_name,
            value_type_encodings=value_type_encodings,
        ),
    }


def _extension_operation_catalog(
    operation: Any,
    lock_entry: Mapping[str, Any],
    value_type_encodings: Mapping[str, str],
) -> dict[str, Any]:
    module_name = (
        operation.receiver.rsplit(".", 1)[0]
        if operation.receiver is not None
        else operation.source_symbol.rsplit(".", 1)[0]
    )
    parameters: list[dict[str, Any]] = []
    if operation.receiver is not None:
        parameters.append(_receiver_parameter(operation, value_type_encodings))
    for parameter in operation.parameters:
        parameter_name = parameter.name
        if operation.receiver == "FreeCAD.Base.Vector" and len(operation.parameters) == 1:
            parameter_name = "right"
        parameters.append(
            {
                "name": parameter_name,
                "kind": _argument_kind(parameter.kind),
                "annotation": parameter.type.annotation,
                "type": _wasm_type(
                    parameter.type,
                    parameter.annotation,
                    module_name,
                    value_type_encodings=value_type_encodings,
                ),
                "default": parameter.default,
            }
        )
    effect = operation.effect
    property_access = (
        operation.property_access.value
        if operation.property_access is not None
        else None
    )
    wire_returns = operation.returns
    if (
        wire_returns.kind is ApiTypeKind.NONE
        and operation.transaction.value in {"open", "commit", "abort"}
    ):
        # These Python methods return None, while the established host ABI
        # exposes transaction status as a boolean payload.
        wire_returns = parse_annotation("bool", module_name)
        assert wire_returns is not None
    return {
        "stable_id": operation.stable_id,
        "name": operation_name(
            operation.stable_id,
            source=operation.source_symbol,
            property_access=property_access,
        ),
        "wire_name": lock_entry["wire_name"],
        "id": lock_entry["id"],
        "guest_method": guest_method_name(
            operation.stable_id,
            source=operation.source_symbol,
            property_access=property_access,
        ),
        "origin": "projection",
        "signature": lock_entry["signature"],
        "source": operation.source_symbol,
        "permission": operation.permission,
        "effect": effect.value if effect is not None else None,
        "property_access": property_access,
        "requires": [
            operation.source_location.path
            if operation.source_location is not None
            else ""
        ],
        "params": parameters,
        "returns": _wasm_type(
            wire_returns,
            wire_returns.annotation,
            module_name,
            value_type_encodings=value_type_encodings,
        ),
        **(
            {"transaction": operation.transaction.value}
            if operation.transaction.value != "none"
            else {}
        ),
    }


def _prepare_catalog_operation(
    operation: dict[str, Any],
    defaults: Mapping[str, Any],
) -> dict[str, Any]:
    operation.setdefault("fallible", defaults.get("fallible", True))
    returns = operation.setdefault("returns", {})
    returns.setdefault("nullable", defaults.get("nullable", False))
    if returns.get("kind") == "handle":
        returns.setdefault("ownership", defaults.get("handle_ownership", "borrowed"))
    for parameter in operation.get("params", []):
        if parameter.get("type", {}).get("kind") == "handle":
            parameter.setdefault("ownership", "borrowed")
    return operation


def _load_operations(
    root: Path,
    inputs: list[Path],
    api_model: Any,
    extension_model: ExtensionApiModel,
    value_type_encodings: Mapping[str, str],
) -> WasmAbiModel:
    lock_path = root / "src/Mod/Wasm/wasm_abi.lock.toml"
    input_paths = {path.resolve().relative_to(root).as_posix() for path in inputs}
    sources = _operation_sources(api_model)
    typed_adapters = load_wasm_adapters()
    abi_lock = load_abi_lock(lock_path)
    lock = {
        stable_id: entry.as_dict()
        for stable_id, entry in abi_lock.operations.items()
    }
    retired = {
        stable_id: entry.as_dict()
        for stable_id, entry in abi_lock.retired.items()
    }
    defaults = WASM_OPERATION_DEFAULTS
    _validate_abi_lock(lock)
    retired_ids = _validate_retired_abi_lock(retired, lock)
    adapters: list[dict[str, Any]] = []
    for adapter in typed_adapters:
        lock_entry = abi_lock.operations.get(adapter.stable_id)
        if lock_entry is None:
            raise ValueError(
                f"WASM adapter '{adapter.name}' is missing from the ABI lock"
            )
        operation = adapter.as_catalog_operation(lock_entry)
        adapters.append(operation)
    _validate_operation_catalog(adapters)
    _validate_reserved_catalog_ids(adapters, retired_ids)

    selected_adapters: list[dict[str, Any]] = []
    adapter_sources: dict[str, str] = {}
    for operation in adapters:
        requirements = operation.get("requires", [])
        if not all(requirement in input_paths for requirement in requirements):
            continue
        source = operation.get("source")
        if source is not None:
            if source not in sources:
                raise ValueError(
                    f"WASM operation {operation.get('name', '<unnamed>')} references "
                    f"missing .pyi symbol '{source}'"
                )
            previous = adapter_sources.get(source)
            if previous is not None:
                raise ValueError(
                    f"WASM source '{source}' is covered by adapters '{previous}' and "
                    f"'{operation.get('name', '<unnamed>')}'"
                )
            adapter_sources[source] = operation.get("name", "<unnamed>")
        selected_adapters.append(operation)

    _validate_projected_abi_lock(
        lock,
        extension_model,
        input_paths,
        adapter_sources,
    )

    selected_operations: list[dict[str, Any]] = []
    for extension_operation in extension_model.operations:
        lock_entry = lock.get(extension_operation.stable_id)
        if lock_entry is None:
            continue
        source_location = extension_operation.source_location
        if source_location is None or source_location.path not in input_paths:
            continue
        selected_operations.append(
            _prepare_catalog_operation(
                _extension_operation_catalog(
                    extension_operation,
                    lock_entry,
                    value_type_encodings,
                ),
                defaults,
            )
        )

    for operation in selected_adapters:
        selected_operations.append(_prepare_catalog_operation(operation, defaults))
    selected_operations.sort(key=lambda operation: operation["id"])
    _validate_operation_catalog(selected_operations)
    _validate_reserved_catalog_ids(selected_operations, retired_ids)
    return WasmAbiModel.from_dicts(selected_operations)


def _extension_type_encodings(extension_model: ExtensionApiModel) -> dict[str, str]:
    encodings: dict[str, str] = {}
    for api_type in extension_model.types:
        if api_type.representation.value != "value":
            continue
        encoding = WASM_VALUE_ENCODINGS.get(api_type.qualified_name)
        if encoding is None:
            raise ValueError(
                f"no WASM value encoding is registered for '{api_type.qualified_name}'"
            )
        encodings[api_type.qualified_name] = encoding
    return encodings


def _extension_model_json(
    extension_model: ExtensionApiModel,
    value_type_encodings: Mapping[str, str],
) -> dict[str, Any]:
    interfaces: list[dict[str, Any]] = []
    for interface in extension_model.interfaces:
        operations: list[dict[str, Any]] = []
        for operation in interface.operations:
            module_name = (
                operation.receiver.rsplit(".", 1)[0]
                if operation.receiver is not None
                else operation.source_symbol.rsplit(".", 1)[0]
            )
            operations.append(
                {
                    "id": operation.stable_id,
                    "local_id": operation.local_id,
                    "source": operation.source_symbol,
                    "source_location": (
                        operation.source_location.path
                        if operation.source_location is not None
                        else None
                    ),
                    "receiver": operation.receiver,
                    "params": [
                        {
                            "name": parameter.name,
                            "kind": _argument_kind(parameter.kind),
                            "annotation": parameter.annotation,
                            "type": _wasm_type(
                                parameter.type,
                                parameter.annotation,
                                module_name,
                                value_type_encodings=value_type_encodings,
                            ),
                            "default": parameter.default,
                        }
                        for parameter in operation.parameters
                    ],
                    "returns": _wasm_type(
                        operation.returns,
                        operation.returns.annotation,
                        module_name,
                        value_type_encodings=value_type_encodings,
                    ),
                    "permission": operation.permission,
                    "effect": operation.effect.value if operation.effect else None,
                    "property_access": (
                        operation.property_access.value
                        if operation.property_access is not None
                        else None
                    ),
                    "transaction": (
                        operation.transaction.value
                        if operation.transaction.value != "none"
                        else None
                    ),
                    "since": operation.since,
                }
            )
        interfaces.append(
            {
                "id": interface.identifier,
                "name": interface.name,
                "version": interface.version,
                "operations": operations,
            }
        )
    return {
        "namespace": extension_model.namespace,
        "types": [
            {
                "name": api_type.qualified_name,
                "representation": api_type.representation.value,
            }
            for api_type in extension_model.types
        ],
        "interfaces": interfaces,
    }


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

    extension_namespace = load_extension_namespace(
        root / "src/Mod/Wasm/WasmExtensionApi.json"
    )
    extension_model = project_api_model(model, namespace=extension_namespace)
    value_type_encodings = _extension_type_encodings(extension_model)

    classes = [
        _class_model(api_class, value_type_encodings=value_type_encodings)
        for module in model.modules
        for api_class in module.classes
    ]
    functions = [
        function
        for module in model.modules
        for function in _module_functions(
            module,
            value_type_encodings=value_type_encodings,
        )
    ]
    aliases = [
        {"public_path": alias.public_path, "target_path": alias.target_path}
        for module in model.modules
        for alias in module.aliases
    ]
    abi_model = _load_operations(
        root,
        inputs,
        model,
        extension_model,
        value_type_encodings,
    )
    operations = abi_model.as_dicts()
    return {
        "schema": "org.freecad.wasm.api",
        "schema_version": SCHEMA_VERSION,
        "api": f"org.freecad.wasm.api@{SCHEMA_VERSION}",
        "permission_policy": "deny-by-default",
        "extension_api": _extension_model_json(extension_model, value_type_encodings),
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
            "catalog_signature": _catalog_signature(operations),
        },
        "operations": operations,
        "classes": classes,
        "functions": functions,
        "aliases": aliases,
    }


def _operation_enum_name(name: str) -> str:
    if name == "release":
        return "HandleRelease"
    return name[:1].upper() + name[1:]


def _wire_type_name(type_model: Mapping[str, Any], label: str) -> str:
    kind = type_model.get("kind")
    if kind == "bool":
        return "Bool"
    if kind == "int64":
        return "Int64"
    if kind == "float64":
        return "Float64"
    if kind == "string":
        return "String"
    if kind == "handle":
        return "Handle"
    if kind == "value" and type_model.get("encoding") == "vector3-f64":
        return "Vector3F64"
    if kind == "none":
        return "None"
    raise ValueError(f"{label} uses an unsupported WASM wire type")


def _signature(operation: Mapping[str, Any]) -> str:
    """Return the stable fingerprint for the complete ABI contract."""

    name = operation.get("name", "<unnamed>")
    parameters = operation.get("params", [])
    returns = operation.get("returns", {})
    descriptor = {
        "params": [
            {
                "name": parameter["name"],
                "type": _wire_type_name(
                    parameter["type"],
                    f"WASM operation '{name}' parameter '{parameter['name']}'",
                ),
            }
            for parameter in parameters
        ],
        "return": _wire_type_name(
            operation.get("wire_returns", operation["returns"]),
            f"WASM operation '{name}' return",
        ),
        "permission": operation.get("permission"),
        "effect": operation.get("effect"),
        "transaction": operation.get("transaction"),
        "parameter_ownership": [
            {
                "ownership": (
                    parameter.get("ownership", "borrowed")
                    if parameter.get("type", {}).get("kind") == "handle"
                    else None
                )
            }
            for parameter in parameters
        ],
        "return_contract": {
            "ownership": (
                returns.get("ownership", "borrowed")
                if returns.get("kind") == "handle"
                else None
            ),
            "nullable": returns.get("nullable", False),
        },
        "fallible": operation.get("fallible", True),
        "consumes": operation.get("consumes", False),
        "property_access": operation.get("property_access"),
    }
    canonical = json.dumps(
        descriptor,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _catalog_type_descriptor(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _catalog_type_descriptor(item)
            for key, item in sorted(value.items())
            if key != "annotation"
        }
    if isinstance(value, list):
        return [_catalog_type_descriptor(item) for item in value]
    return value


def _catalog_signature(operations: list[dict[str, Any]]) -> str:
    """Return the stable fingerprint for the published operation catalog."""

    descriptor = []
    for operation in sorted(operations, key=lambda item: item["id"]):
        descriptor.append(
            {
                "id": operation["id"],
                "stable_id": operation["stable_id"],
                "wire_name": operation["wire_name"],
                "signature": operation["signature"],
                "permission": operation.get("permission"),
                "effect": operation.get("effect"),
                "transaction": operation.get("transaction"),
                "origin": operation["origin"],
                "consumes": operation.get("consumes", False),
                "params": [
                    {
                        "name": parameter["name"],
                        "type": _catalog_type_descriptor(parameter["type"]),
                    }
                    for parameter in operation["params"]
                ],
                "returns": _catalog_type_descriptor(operation["returns"]),
                "wire_returns": _catalog_type_descriptor(
                    operation.get("wire_returns")
                ),
            }
        )
    canonical = json.dumps(
        descriptor,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_dispatch_metadata(model: Mapping[str, Any]) -> str:
    """Render host dispatch metadata from the merged operation model."""

    operations = model.get("operations", [])
    if not isinstance(operations, list):
        raise ValueError("WASM API model operations must be a list")
    abi = model.get("abi", {})
    if not isinstance(abi, Mapping):
        raise ValueError("WASM API model ABI metadata must be an object")
    catalog_signature = abi.get("catalog_signature", "")
    if not isinstance(catalog_signature, str):
        raise ValueError("WASM API model has an invalid catalog signature")

    lines = [
        "// Generated by generate_wasm_api.py. Do not edit.",
        "#pragma once",
        "",
        "#include <WasmAbi.h>",
        "",
        "#include <array>",
        "#include <cstdint>",
        "#include <span>",
        "#include <string_view>",
        "",
        "namespace Wasm::Generated",
        "{",
        "",
        f'inline constexpr std::string_view ApiCatalogSignature = "{catalog_signature}";',
        "",
        "enum class WireType : std::uint8_t",
        "{",
        "    None,",
        "    Bool,",
        "    Int64,",
        "    Float64,",
        "    String,",
        "    Handle,",
        "    Vector3F64,",
        "};",
        "",
        "struct ParameterMetadata",
        "{",
        "    std::string_view name;",
        "    WireType type;",
        "};",
        "",
        "struct OperationMetadata",
        "{",
        "    Abi::Operation operation;",
        "    std::uint8_t id;",
        "    std::string_view name;",
        "    std::string_view wireName;",
        "    std::string_view permission;",
        "    std::string_view effect;",
        "    std::string_view transaction;",
        "    std::string_view origin;",
        "    std::span<const ParameterMetadata> parameters;",
        "    WireType returnType;",
        "};",
        "",
    ]
    for operation in operations:
        name = operation.get("name")
        operation_id = operation.get("id")
        permission = operation.get("permission") or ""
        transaction = operation.get("transaction") or ""
        origin = operation.get("origin")
        if not isinstance(name, str) or not name:
            raise ValueError("WASM operation metadata has an invalid name")
        if (
            isinstance(operation_id, bool)
            or not isinstance(operation_id, int)
            or not 0 < operation_id <= 0xFF
        ):
            raise ValueError(f"WASM operation '{name}' has an invalid id")
        if origin not in {"projection", "adapter"}:
            raise ValueError(f"WASM operation '{name}' has an invalid origin")
        parameters = operation.get("params", [])
        if not isinstance(parameters, list):
            raise ValueError(f"WASM operation '{name}' has invalid parameters")
        parameter_name = f"{_operation_enum_name(name)}Parameters"
        if parameters:
            lines.extend(
                [
                    f"inline constexpr std::array<ParameterMetadata, {len(parameters)}> "
                    f"{parameter_name} = {{ {{",
                ]
            )
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    raise ValueError(f"WASM operation '{name}' has an invalid parameter")
                parameter_name_value = parameter.get("name")
                parameter_type = parameter.get("type")
                if not isinstance(parameter_name_value, str) or not parameter_name_value:
                    raise ValueError(f"WASM operation '{name}' has an invalid parameter name")
                if not isinstance(parameter_type, dict):
                    raise ValueError(f"WASM operation '{name}' has an invalid parameter type")
                wire_type = _wire_type_name(
                    parameter_type,
                    f"WASM operation '{name}' parameter '{parameter_name_value}'",
                )
                lines.append(
                    f"    {{{json.dumps(parameter_name_value)}, WireType::{wire_type}}},"
                )
            lines.extend(["}};", ""])
        else:
            lines.extend(
                [
                    f"inline constexpr std::array<ParameterMetadata, 0> "
                    f"{parameter_name} = {{}};",
                    "",
                ]
            )
        returns = operation.get("wire_returns", operation.get("returns"))
        if not isinstance(returns, dict):
            raise ValueError(f"WASM operation '{name}' has invalid returns")
        _wire_type_name(returns, f"WASM operation '{name}' return")

    lines.extend(
        [
            f"inline constexpr std::array<OperationMetadata, {len(operations)}>"
            " OperationMetadataTable = {{",
        ]
    )
    for operation in operations:
        name = operation["name"]
        operation_id = operation["id"]
        permission = operation.get("permission") or ""
        effect = operation.get("effect") or ""
        transaction = operation.get("transaction") or ""
        origin = operation["origin"]
        parameter_name = f"{_operation_enum_name(name)}Parameters"
        return_type = _wire_type_name(
            operation.get("wire_returns", operation["returns"]),
            f"WASM operation '{name}' return",
        )
        lines.append(
            "    {"
            f"Abi::Operation::{_operation_enum_name(name)}, "
            f"{operation_id}U, "
            f"{json.dumps(name, ensure_ascii=True)}, "
            f"{json.dumps(operation.get('wire_name', ''), ensure_ascii=True)}, "
            f"{json.dumps(permission, ensure_ascii=True)}, "
            f"{json.dumps(effect, ensure_ascii=True)}, "
            f"{json.dumps(transaction, ensure_ascii=True)}, "
            f"{json.dumps(origin, ensure_ascii=True)}, "
            f"{parameter_name}, "
            f"WireType::{return_type}"
            "},"
        )
    lines.extend(
        [
            "}};",
            "",
            "inline constexpr const OperationMetadata* findOperationMetadata(",
            "    std::uint8_t id)",
            "{",
            "    for (const auto& operation : OperationMetadataTable) {",
            "        if (operation.id == id) {",
            "            return &operation;",
            "        }",
            "    }",
            "    return nullptr;",
            "}",
            "",
            "}  // namespace Wasm::Generated",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dispatch-metadata-output", type=Path)
    parser.add_argument("--catalog-signature-output", type=Path)
    args = parser.parse_args()
    inputs = [path.resolve() for path in args.inputs]
    output = args.output.resolve()
    result = build_model(ROOT, inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.dispatch_metadata_output is not None:
        metadata_output = args.dispatch_metadata_output.resolve()
        metadata_output.parent.mkdir(parents=True, exist_ok=True)
        metadata_output.write_text(
            render_dispatch_metadata(result),
            encoding="utf-8",
        )
    if args.catalog_signature_output is not None:
        signature_output = args.catalog_signature_output.resolve()
        signature_output.parent.mkdir(parents=True, exist_ok=True)
        signature_output.write_text(
            result["abi"]["catalog_signature"] + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
