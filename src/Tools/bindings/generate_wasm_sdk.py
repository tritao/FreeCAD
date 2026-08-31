#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Generate typed Python, Rust, and C++ guest layers from the WASM API model."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


CPP_KEYWORDS = {
    "class",
    "const",
    "enum",
    "explicit",
    "namespace",
    "struct",
    "template",
    "typename",
}
RUST_KEYWORDS = {
    "as",
    "crate",
    "enum",
    "extern",
    "fn",
    "impl",
    "in",
    "let",
    "match",
    "mod",
    "pub",
    "ref",
    "self",
    "struct",
    "trait",
    "type",
    "use",
}
SDK_INTERFACE_SERVICES = {
    "document": "documents",
}


@dataclass(frozen=True)
class SdkOperation:
    """Semantic SDK view of one projected or adapter operation."""

    stable_id: str
    local_id: str
    raw_method: str
    source: str | None
    receiver: str | None
    kind: str
    service: str | None
    public_name: str
    params: tuple[dict[str, Any], ...]
    returns: dict[str, Any]
    property_access: str | None
    transaction: str | None


@dataclass(frozen=True)
class SemanticSdkModel:
    """Language-neutral facade surface derived from ExtensionApiModel metadata."""

    operations: tuple[SdkOperation, ...]
    resources: tuple[str, ...]
    values: tuple[str, ...]
    services: tuple[str, ...]

    def for_receiver(self, receiver: str) -> tuple[SdkOperation, ...]:
        return tuple(item for item in self.operations if item.receiver == receiver)

    def for_service(self, service: str) -> tuple[SdkOperation, ...]:
        return tuple(item for item in self.operations if item.service == service)

    def transaction(self, role: str) -> SdkOperation | None:
        return next(
            (item for item in self.operations if item.transaction == role),
            None,
        )

    def transaction_owner(self) -> str | None:
        operation = self.transaction("open")
        return operation.receiver if operation else None


def _snake_case(value: str) -> str:
    return re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value),
    ).strip("_").lower()


def _camel_case(value: str) -> str:
    parts = [part for part in _snake_case(value).split("_") if part]
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _pascal_case(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in _snake_case(value).split("_"))


def _short_type(full_name: str | None) -> str | None:
    return full_name.rsplit(".", 1)[-1] if full_name else None


def _operation_scope(stable_id: str) -> str:
    scope = stable_id.split("/", 1)[0]
    return scope.rsplit("@", 1)[0].rsplit(".", 1)[-1]


def _interface_service(interface_name: str) -> str:
    return SDK_INTERFACE_SERVICES.get(interface_name, interface_name)


def _operation_receiver(
    semantic: dict[str, Any],
    operation: dict[str, Any],
) -> str | None:
    if "receiver" in semantic:
        receiver = semantic["receiver"]
        return receiver if isinstance(receiver, str) and receiver else None
    source = semantic.get("source") or operation.get("source")
    if not isinstance(source, str) or not source or source.endswith(".__init__"):
        return None
    parts = source.split(".")
    return ".".join(parts[:-1]) if len(parts) >= 3 else None


def _remove_receiver_parameter(
    receiver: str | None,
    params: list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    if receiver is None or not params:
        return tuple(params)
    receiver_name = _short_type(receiver)
    first_type = params[0].get("type", {})
    if _short_type(first_type.get("type")) == receiver_name:
        return tuple(params[1:])
    return tuple(params)


def _operation_public_name(
    local_id: str,
    source: str | None,
    receiver: str | None,
    kind: str,
    property_access: str | None,
    returns: dict[str, Any],
) -> str:
    if kind == "constructor":
        return _snake_case(_short_type(returns.get("type")) or local_id.removesuffix("_new"))
    member = source.rsplit(".", 1)[-1] if source else local_id
    name = _snake_case(member)
    if receiver is None and local_id.endswith("_new"):
        return "create" if returns.get("kind") == "handle" else name.removesuffix("_new")
    if property_access == "write":
        return f"set_{name}"
    return name


def _operation_service(
    stable_id: str,
    receiver: str | None,
    kind: str,
    interface_service: str | None,
    sdk_service: str | None,
) -> str | None:
    if receiver is not None or kind == "transaction":
        return None
    if sdk_service is not None and (
        not isinstance(sdk_service, str) or not sdk_service
    ):
        raise ValueError(f"operation '{stable_id}' has an invalid SDK service")
    return sdk_service or interface_service or _operation_scope(stable_id)


def _operation_types(operation: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield logical parameter and return types from one catalog operation."""

    for parameter in operation.get("params", []):
        type_model = parameter.get("type")
        if isinstance(type_model, dict):
            yield type_model
    returns = operation.get("returns")
    if isinstance(returns, dict):
        yield returns


def semantic_sdk_model(model: dict[str, Any]) -> SemanticSdkModel:
    """Build the facade surface from ExtensionApiModel and ABI metadata."""

    semantic_operations: dict[str, dict[str, Any]] = {}
    interface_services: dict[str, str] = {}
    for interface in model.get("extension_api", {}).get("interfaces", []):
        interface_name = interface.get("name")
        for operation in interface.get("operations", []):
            stable_id = operation.get("id")
            if not isinstance(stable_id, str):
                continue
            semantic_operations[stable_id] = operation
            if isinstance(interface_name, str) and interface_name:
                interface_services[stable_id] = _interface_service(interface_name)
    operations: list[SdkOperation] = []
    for operation in model.get("operations", []):
        stable_id = operation.get("stable_id")
        if not isinstance(stable_id, str) or stable_id.endswith("/handle_release"):
            continue
        semantic = semantic_operations.get(stable_id, {})
        source = semantic.get("source") or operation.get("source")
        receiver = _operation_receiver(semantic, operation)
        property_access = semantic.get("property_access") or operation.get("property_access")
        transaction = semantic.get("transaction") or operation.get("transaction")
        if transaction in {"open", "commit", "abort"}:
            kind = "transaction"
        elif property_access in {"read", "write"}:
            kind = f"property_{property_access}"
        elif isinstance(source, str) and source.endswith(".__init__"):
            kind = "constructor"
        elif receiver is not None:
            kind = "method"
        else:
            kind = "function"
        returns = operation.get("returns", {})
        operations.append(
            SdkOperation(
                stable_id=stable_id,
                local_id=stable_id.split("/", 1)[1],
                raw_method=operation.get("guest_method", operation.get("name", "")),
                source=source,
                receiver=receiver,
                kind=kind,
                service=_operation_service(
                    stable_id,
                    receiver,
                    kind,
                    interface_services.get(stable_id),
                    operation.get("sdk_service"),
                ),
                public_name=_operation_public_name(
                    stable_id.split("/", 1)[1],
                    source,
                    receiver,
                    kind,
                    property_access,
                    returns,
                ),
                params=_remove_receiver_parameter(receiver, operation.get("params", [])),
                returns=returns,
                property_access=property_access,
                transaction=transaction,
            )
        )

    resources = {
        type_model.get("type")
        for operation in model.get("operations", [])
        for type_model in _operation_types(operation)
        if type_model.get("kind") == "handle"
        and isinstance(type_model.get("type"), str)
        and type_model.get("type") != "Wasm.Handle"
    }
    values = {
        type_model.get("type")
        for operation in model.get("operations", [])
        for type_model in _operation_types(operation)
        if type_model.get("kind") == "value"
        and isinstance(type_model.get("type"), str)
        and type_model.get("type")
    }
    resources.discard(None)
    values.discard(None)
    return SemanticSdkModel(
        operations=tuple(operations),
        resources=tuple(sorted(resources)),
        values=tuple(sorted(values)),
        services=tuple(sorted({item.service for item in operations if item.service})),
    )


def type_name(full_name: str, keywords: set[str]) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", full_name)
    name = "".join(part[:1].upper() + part[1:] for part in parts) or "ApiType"
    if name[0].isdigit():
        name = f"Type{name}"
    if name.lower() in keywords:
        name += "Type"
    return f"{name}Handle"


def value_type_name(full_name: str, keywords: set[str]) -> str:
    handle_name = type_name(full_name, keywords)
    return f"{handle_name[:-len('Handle')]}Value"


def rust_method_name(name: str) -> str:
    return re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name),
    ).lower()


def operation_constant_name(name: str) -> str:
    return rust_method_name(name).upper()


def classes(model: dict[str, Any]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(full_name: str) -> None:
        if (
            not isinstance(full_name, str)
            or not full_name
            or full_name == "Wasm.Handle"
            or full_name in seen
        ):
            return
        seen.add(full_name)
        entries.append((full_name, type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)))

    for api_class in model.get("classes", []):
        if api_class.get("representation", {}).get("kind") != "value":
            add(api_class.get("full_name"))
    for operation in model.get("operations", []):
        for parameter in operation.get("params", []):
            type_model = parameter.get("type", {})
            if type_model.get("kind") == "handle":
                add(type_model.get("type"))
        return_type = operation.get("returns", {})
        if return_type.get("kind") == "handle":
            add(return_type.get("type"))
    return entries


def value_types(model: dict[str, Any]) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def add(full_name: str, encoding: str) -> None:
        if (
            not isinstance(full_name, str)
            or not full_name
            or full_name in seen
        ):
            return
        seen.add(full_name)
        entries.append(
            (
                full_name,
                value_type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS),
                encoding,
            )
        )

    for api_class in model.get("classes", []):
        representation = api_class.get("representation", {})
        if representation.get("kind") == "value":
            add(api_class.get("full_name"), representation.get("encoding", ""))
    for operation in model.get("operations", []):
        for parameter in operation.get("params", []):
            type_model = parameter.get("type", {})
            if type_model.get("kind") == "value":
                add(type_model.get("type"), type_model.get("encoding", ""))
        return_type = operation.get("returns", {})
        if return_type.get("kind") == "value":
            add(return_type.get("type"), return_type.get("encoding", ""))
    return entries


def render_cpp(model: dict[str, Any]) -> str:
    api = model.get("api", "org.freecad.wasm.api@0")
    abi = model.get("abi", {})
    class_names = dict(classes(model))
    value_names = {full_name: name for full_name, name, _ in value_types(model)}
    lines = [
        "// Generated by generate_wasm_sdk.py. Do not edit.",
        "#pragma once",
        "",
        "#include <Wasm/Guest/WasmGuest.h>",
        "",
        "namespace FreeCAD::Extension::Raw",
        "{",
        f'inline constexpr char ApiVersion[] = "{api}";',
        f'inline constexpr char ApiCatalogSignature[] = "{abi.get("catalog_signature", "")}";',
        f'inline constexpr char ResponseMagic[] = "{abi.get("response_magic", "FCWR")}";',
        f"inline constexpr unsigned char ResponseVersion = {int(abi.get('response_version', 1))}U;",
        f"inline constexpr unsigned char ResponseHeaderSize = {int(abi.get('response_header_size', 12))}U;",
        "using Handle = unsigned long long;",
        "",
    ]
    for _, name in class_names.items():
        lines.extend(
            [
                f"struct {name}",
                "{",
                "    Handle value = 0U;",
                "",
                "    constexpr explicit operator bool() const { return value != 0U; }",
                "};",
                "",
            ]
        )
    for _, name, encoding in value_types(model):
        if encoding != "vector3-f64":
            raise ValueError(f"unsupported C++ Wasm value encoding: {encoding}")
        lines.extend(
            [
                f"struct {name}",
                "{",
                "    double x = 0.0;",
                "    double y = 0.0;",
                "    double z = 0.0;",
                "};",
                "",
            ]
        )

    lines.extend(
        [
            "class OwnedHandle",
            "{",
            "public:",
            "    OwnedHandle() = default;",
            "",
            "    OwnedHandle(::Wasm::Guest::Client client, Handle value)",
            "        : client_(client)",
            "        , value(value)",
            "    {",
            "    }",
            "",
            "    ~OwnedHandle()",
            "    {",
            "        reset();",
            "    }",
            "",
            "    OwnedHandle(const OwnedHandle&) = delete;",
            "    OwnedHandle& operator=(const OwnedHandle&) = delete;",
            "",
            "    OwnedHandle(OwnedHandle&& other) noexcept",
            "        : client_(other.client_)",
            "        , value(other.value)",
            "    {",
            "        other.value = 0U;",
            "    }",
            "",
            "    OwnedHandle& operator=(OwnedHandle&& other) noexcept",
            "    {",
            "        if (this != &other) {",
            "            reset();",
            "            client_ = other.client_;",
            "            value = other.value;",
            "            other.value = 0U;",
            "        }",
            "        return *this;",
            "    }",
            "",
            "    explicit operator bool() const { return value != 0U; }",
            "    Handle get() const { return value; }",
            "",
            "    void reset()",
            "    {",
            "        if (value != 0U) {",
            "            static_cast<void>(client_.release(value));",
            "        }",
            "        value = 0U;",
            "    }",
            "",
            "private:",
            "    ::Wasm::Guest::Client client_;",
            "    Handle value = 0U;",
            "};",
            "",
            "class RawClient",
            "{",
            "public:",
            "    RawClient() = default;",
            "",
            "    explicit RawClient(::Wasm::Guest::Client client)",
            "        : client_(client)",
            "    {",
            "    }",
            "",
            "    auto allocateResponse(unsigned int size) const",
            "    {",
            "        return client_.allocateResponse(size);",
            "    }",
            "",
            "    OwnedHandle own(Handle value)",
            "    {",
            "        return OwnedHandle(client_, value);",
            "    }",
            "",
        ]
    )
    for operation in model.get("operations", []):
        params = operation.get("params", [])
        return_type = operation.get("returns", {})
        method = operation.get("guest_method", operation.get("name", ""))
        name = operation.get("name", "operation")
        lines.append(f"    // {operation.get('wire_name', name)}")
        permission = operation.get("permission")
        if permission:
            lines.append(
                f'    inline static constexpr char {name}Permission[] = "{permission}";'
            )
        returns_metadata = return_type
        if returns_metadata.get("kind") == "handle":
            lines.append(
                f'    inline static constexpr char {name}Ownership[] = "{returns_metadata.get("ownership", "borrowed")}";'
            )
        if operation.get("transaction"):
            lines.append(
                f'    inline static constexpr char {name}Transaction[] = "{operation["transaction"]}";'
            )
        lines.append(
            f"    inline static constexpr unsigned char {name}Operation = "
            f"{int(operation.get('id', 0))}U;"
        )
        lines.append(
            f"    inline static constexpr bool {name}Fallible = "
            f"{'true' if operation.get('fallible', True) else 'false'};"
        )
        lines.append(
            f"    inline static constexpr bool {name}Nullable = "
            f"{'true' if return_type.get('nullable', False) else 'false'};"
        )
        lines.append(
            f"    inline static constexpr bool {name}Consumes = "
            f"{'true' if operation.get('consumes', False) else 'false'};"
        )

        parameter_declarations = []
        call_arguments = []
        for parameter in params:
            parameter_type = parameter.get("type", {})
            kind = parameter_type.get("kind")
            if kind == "string":
                cpp_type = "const char*"
            elif kind == "float64":
                cpp_type = "double"
            elif kind == "bool":
                cpp_type = "bool"
            elif kind == "value":
                cpp_type = value_names[parameter_type["type"]]
            elif kind == "handle":
                full_name = parameter_type.get("type")
                cpp_type = "Handle" if full_name == "Wasm.Handle" else class_names[full_name]
            else:
                cpp_type = "Handle"
            parameter_name = parameter.get("name", "value")
            parameter_declarations.append(f"{cpp_type} {parameter_name}")
            if kind == "handle" and parameter_type.get("type") != "Wasm.Handle":
                call_arguments.append(f"{parameter_name}.value")
            elif kind == "value" and parameter_type.get("encoding") == "vector3-f64":
                call_arguments.append(
                    "::Wasm::Guest::Vector3{"
                    f"{parameter_name}.x, {parameter_name}.y, {parameter_name}.z}}"
                )
            else:
                call_arguments.append(parameter_name)

        result_parameter_declarations = list(parameter_declarations)

        if return_type.get("kind") == "string":
            parameter_declarations.extend(
                ["char* result", "unsigned int capacity", "unsigned int* length"]
            )
            lines.append(
                f"    bool {name}({', '.join(parameter_declarations)}) const"
            )
            lines.extend(
                [
                    "    {",
                    "        if (length == nullptr || (capacity != 0U && result == nullptr)) {",
                    "            return false;",
                    "        }",
                    f"        return client_.{method}({', '.join(call_arguments + ['result', 'capacity', 'length'])});",
                    "    }",
                    "",
                ]
            )
        elif return_type.get("kind") == "handle":
            result_type = return_type.get("type")
            result_cpp_type = "Handle" if result_type == "Wasm.Handle" else class_names[result_type]
            parameter_declarations.append(f"{result_cpp_type}* result")
            lines.append(
                f"    bool {name}({', '.join(parameter_declarations)}) const"
            )
            lines.extend(
                [
                    "    {",
                    "        if (result == nullptr) {",
                    "            return false;",
                    "        }",
                    "        ::Wasm::Guest::Handle raw = 0U;",
                    f"        if (!client_.{method}({', '.join(call_arguments + ['&raw'])})) {{",
                    "            return false;",
                    "        }",
                    "        result->value = raw;",
                    "        return true;",
                    "    }",
                    "",
                ]
            )
        elif return_type.get("kind") == "value":
            result_type = return_type.get("type")
            result_cpp_type = value_names[result_type]
            parameter_declarations.append(f"{result_cpp_type}* result")
            lines.append(
                f"    bool {name}({', '.join(parameter_declarations)}) const"
            )
            lines.extend(
                [
                    "    {",
                    "        if (result == nullptr) {",
                    "            return false;",
                    "        }",
                    "        ::Wasm::Guest::Vector3 raw;",
                    f"        if (!client_.{method}({', '.join(call_arguments + ['&raw'])})) {{",
                    "            return false;",
                    "        }",
                    "        result->x = raw.x;",
                    "        result->y = raw.y;",
                    "        result->z = raw.z;",
                    "        return true;",
                    "    }",
                    "",
                ]
            )
        elif return_type.get("kind") == "float64":
            parameter_declarations.append("double* result")
            lines.append(
                f"    bool {name}({', '.join(parameter_declarations)}) const"
            )
            lines.extend(
                [
                    "    {",
                    "        if (result == nullptr) {",
                    "            return false;",
                    "        }",
                    f"        return client_.{method}({', '.join(call_arguments + ['result'])});",
                    "    }",
                    "",
                ]
            )
        elif return_type.get("kind") == "bool":
            lines.append(
                f"    bool {name}({', '.join(parameter_declarations)}) const"
            )
            lines.extend(["    {"])
            if method == "release":
                lines.extend(
                    [
                        "#if defined(FREECAD_WASM_FREESTANDING)",
                        "        return client_.release(handle);",
                        "#else",
                        "        bool released = false;",
                        "        if (!client_.release(handle, &released)) {",
                        "            return false;",
                        "        }",
                        "        return released;",
                        "#endif",
                    ]
                )
            else:
                lines.extend(
                    [
                        "        bool value = false;",
                        f"        if (!client_.{method}({', '.join(call_arguments + ['&value'])})) {{",
                        "            return false;",
                        "        }",
                        "        return value;",
                    ]
                )
            lines.extend(["    }", ""])
        elif return_type.get("kind") == "none":
            lines.append(
                f"    bool {name}({', '.join(parameter_declarations)}) const"
            )
            lines.extend(
                [
                    "    {",
                    f"        return client_.{method}({', '.join(call_arguments)});",
                    "    }",
                    "",
                ]
            )

        # Hosted guests can use the structured transport result directly. Keep
        # the bool/out-parameter adapters above for freestanding guests.
        result_kinds = {
            "handle": "::Wasm::Guest::Handle",
            "value": "::Wasm::Guest::Vector3",
            "float64": "double",
            "bool": "bool",
            "string": "std::string",
            "none": "void",
        }
        result_cpp_type = result_kinds.get(return_type.get("kind"))
        if result_cpp_type is None:
            raise ValueError(f"unsupported C++ Wasm result type: {return_type.get('kind')}")
        result_call_arguments = [
            f"std::string_view({argument})"
            if parameter.get("type", {}).get("kind") == "string"
            else argument
            for parameter, argument in zip(params, call_arguments)
        ]
        lines.extend(
            [
                "#if !defined(FREECAD_WASM_FREESTANDING)",
                f"    ::Wasm::Guest::Result<{result_cpp_type}> {name}Result({', '.join(result_parameter_declarations)}) const",
                "    {",
            ]
        )
        for parameter in params:
            if parameter.get("type", {}).get("kind") == "string":
                parameter_name = parameter.get("name", "value")
                lines.extend(
                    [
                        f"        if ({parameter_name} == nullptr) {{",
                        (
                            '            return {false, "string parameter is null", '
                            '::Wasm::Abi::ErrorCode::InvalidRequest};'
                            if return_type.get("kind") == "none"
                            else '            return {false, {}, "string parameter is null"};'
                        ),
                        "        }",
                    ]
                )
        lines.append(
            f"        return client_.{method}({', '.join(result_call_arguments)});"
        )
        lines.extend(["    }", "#endif", ""])

    lines.extend(
        [
            "private:",
            "    ::Wasm::Guest::Client client_;",
            "};",
            "",
        ]
    )
    lines.extend(
        [
            "}  // namespace FreeCAD::Extension::Raw",
            "",
        ]
    )
    sdk = semantic_sdk_model(model)
    if sdk.operations:
        lines.extend(_cpp_extension_facade(sdk))
    return "\n".join(lines)



def _cpp_value_expression(type_model: dict[str, Any], name: str) -> str:
    kind = type_model.get("kind")
    if kind == "string":
        return f"{name}Value.c_str()"
    if kind == "value":
        return f"{name}.rawValue()"
    if kind == "handle":
        full_name = type_model.get("type")
        if full_name == "Wasm.Handle":
            return name
        return f"Raw::{type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)}{{{name}.value()}}"
    return name


def _cpp_result_type(type_model: dict[str, Any]) -> str:
    kind = type_model.get("kind")
    if kind == "handle":
        full_name = type_model.get("type")
        return "Raw::Handle" if full_name == "Wasm.Handle" else (_short_type(full_name) or "Handle")
    if kind == "value":
        return _short_type(type_model.get("type")) or "Value"
    return {
        "bool": "bool",
        "float64": "double",
        "string": "std::string",
        "none": "void",
    }.get(kind, "void")


def _cpp_parameter_declaration(parameter: dict[str, Any]) -> str:
    type_model = parameter.get("type", {})
    kind = type_model.get("kind")
    if kind == "string":
        cpp_type = "std::string_view"
    elif kind == "value":
        cpp_type = f"const {_short_type(type_model.get('type')) or 'Value'}&"
    elif kind == "handle":
        full_name = type_model.get("type")
        cpp_type = "Raw::Handle" if full_name == "Wasm.Handle" else f"const {_short_type(full_name) or 'Resource'}&"
    else:
        cpp_type = {"float64": "double", "bool": "bool"}.get(kind, "double")
    return f"{cpp_type} {parameter.get('name', 'value')}"


def _cpp_operation_call(
    sdk: SemanticSdkModel,
    operation: SdkOperation,
    target: str,
    receiver_expression: str | None = None,
) -> tuple[list[str], str]:
    call_arguments: list[str] = []
    setup: list[str] = []
    if operation.receiver is not None:
        if receiver_expression is None:
            raise ValueError(f"missing receiver expression for '{operation.stable_id}'")
        receiver_type = (
            receiver_expression
            if operation.receiver in sdk.values
            else f"Raw::{type_name(operation.receiver, CPP_KEYWORDS | RUST_KEYWORDS)}{{{receiver_expression}}}"
        )
        call_arguments.append(receiver_type)
    for parameter in operation.params:
        name = parameter.get("name", "value")
        if parameter.get("type", {}).get("kind") == "string":
            setup.append(f"        auto {name}Value = extensionString({name});")
        call_arguments.append(_cpp_value_expression(parameter.get("type", {}), name))
    return setup, f"{target}.{operation.raw_method}Result({', '.join(call_arguments)})"


def _cpp_operation_result(
    operation: SdkOperation,
    call: str,
    wrapper_client: str,
) -> list[str]:
    kind = operation.returns.get("kind")
    if kind not in {"handle", "value"}:
        return [f"        return {call};"]
    result_type = _short_type(operation.returns.get("type")) or "Value"
    owned = "true" if operation.returns.get("ownership") == "owned" else "false"
    if kind == "value":
        value = f"{result_type}({wrapper_client}, Raw::{value_type_name(operation.returns.get('type'), CPP_KEYWORDS | RUST_KEYWORDS)}{{result.value.x, result.value.y, result.value.z}})"
    else:
        value = f"{result_type}({wrapper_client}, result.value, {owned})"
    return [
        f"        auto result = {call};",
        "        if (!result.ok) {",
        "            return {false, {}, std::move(result.error), result.errorCode};",
        "        }",
        f"        return {{true, {value}, {{}}, ::Wasm::Abi::ErrorCode::None}};",
    ]


def _cpp_operation_method(
    sdk: SemanticSdkModel,
    operation: SdkOperation,
    *,
    receiver_expression: str | None,
    target: str,
) -> list[str]:
    method = _camel_case(operation.public_name)
    result_type = _cpp_result_type(operation.returns)
    declarations = [_cpp_parameter_declaration(parameter) for parameter in operation.params]
    lines = [f"    Result<{result_type}> {method}({', '.join(declarations)}) const", "    {"]
    setup, call = _cpp_operation_call(sdk, operation, target, receiver_expression)
    lines.extend(setup)
    lines.extend(_cpp_operation_result(operation, call, "client_"))
    lines.extend(["    }", ""])
    return lines


def _cpp_value_class(sdk: SemanticSdkModel, full_name: str, wrapper_names: list[str]) -> list[str]:
    public_name = _short_type(full_name) or "Value"
    lines = [
        f"class {public_name} final",
        "{",
        "public:",
        f"    {public_name}() = default;",
        "    double x() const { return value_.x; }",
        "    double y() const { return value_.y; }",
        "    double z() const { return value_.z; }",
        "    Raw::" + value_type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS) + " rawValue() const { return value_; }",
        "",
    ]
    for operation in sdk.for_receiver(full_name):
        if operation.kind == "transaction":
            continue
        lines.extend(_cpp_operation_method(sdk, operation, receiver_expression="value_", target="client_"))
    lines.extend(
        [
            "private:",
            f"    friend class {public_name};",
        ]
    )
    for wrapper in wrapper_names:
        lines.append(f"    friend class {wrapper};")
    lines.extend(
        [
            f"    {public_name}(RawClient client, Raw::{value_type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)} value)",
            "        : client_(client)",
            "        , value_(value)",
            "    {",
            "    }",
            "",
            "    RawClient client_;",
            f"    Raw::{value_type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)} value_{{}};",
            "};",
            "",
        ]
    )
    return lines


def _cpp_resource_class(
    sdk: SemanticSdkModel,
    full_name: str,
    wrapper_names: list[str],
) -> list[str]:
    public_name = _short_type(full_name) or "Resource"
    lines = [
        f"class {public_name} final: public Resource",
        "{",
        "public:",
        f"    {public_name}() = default;",
        "",
    ]
    for operation in sdk.for_receiver(full_name):
        if operation.kind == "transaction":
            continue
        lines.extend(
            _cpp_operation_method(
                sdk,
                operation,
                receiver_expression="value_",
                target="client_",
            )
        )
    open_transaction = (
        sdk.transaction("open")
        if full_name == sdk.transaction_owner()
        else None
    )
    if open_transaction is not None:
        setup, call = _cpp_operation_call(sdk, open_transaction, "client_", "value_")
        lines.extend(
            [
                "    Result<Transaction> transaction(std::string_view name) const",
                "    {",
                *setup,
                f"        auto result = {call};",
                "        auto checked = checkResult(std::move(result), \"host rejected document transaction\");",
                "        if (!checked.ok) {",
                "            return {false, {}, std::move(checked.error), checked.errorCode};",
                "        }",
                f"        return {{true, Transaction(client_, Raw::{type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)}{{value_}}), {{}},",
                "                ::Wasm::Abi::ErrorCode::None};",
                "    }",
                "",
            ]
        )
    lines.extend(["private:"])
    for wrapper in wrapper_names:
        lines.append(f"    friend class {wrapper};")
    lines.extend(
        [
            f"    {public_name}(RawClient client, Raw::Handle value, bool owned)",
            "        : Resource(client, value, owned)",
            "    {",
            "    }",
            "};",
            "",
        ]
    )
    return lines


def _cpp_transaction_class(sdk: SemanticSdkModel) -> list[str]:
    commit = sdk.transaction("commit")
    abort = sdk.transaction("abort")
    if commit is None or abort is None:
        return []
    owner = sdk.transaction_owner()
    if owner is None:
        return []
    owner_name = _short_type(owner) or "Resource"
    owner_handle = type_name(owner, CPP_KEYWORDS | RUST_KEYWORDS)
    commit_call = f"client_.{commit.raw_method}Result(document_)"
    abort_call = f"client_.{abort.raw_method}Result(document_)"
    return [
        "class Transaction final",
        "{",
        "public:",
        "    Transaction() = default;",
        "    ~Transaction()",
        "    {",
        "        if (active_) {",
        f"            static_cast<void>({abort_call});",
        "        }",
        "    }",
        "    Transaction(const Transaction&) = delete;",
        "    Transaction& operator=(const Transaction&) = delete;",
        "",
        "    Transaction(Transaction&& other) noexcept",
        "        : client_(other.client_)",
        "        , document_(other.document_)",
        "        , active_(other.active_)",
        "    {",
        "        other.active_ = false;",
        "    }",
        "",
        "    Result<void> commit()",
        "    {",
        "        if (!active_) {",
        "            return {true, {}, ::Wasm::Abi::ErrorCode::None};",
        "        }",
        f"        auto result = checkResult(client_.{commit.raw_method}Result(document_), \"host rejected transaction commit\");",
        "        if (result.ok) {",
        "            active_ = false;",
        "        }",
        "        return result;",
        "    }",
        "",
        "    Result<void> abort()",
        "    {",
        "        if (!active_) {",
        "            return {true, {}, ::Wasm::Abi::ErrorCode::None};",
        "        }",
        f"        auto result = checkResult(client_.{abort.raw_method}Result(document_), \"host rejected transaction abort\");",
        "        if (result.ok) {",
        "            active_ = false;",
        "        }",
        "        return result;",
        "    }",
        "",
        "private:",
        f"    friend class {owner_name};",
        f"    Transaction(RawClient client, Raw::{owner_handle} document)",
        "        : client_(client)",
        "        , document_(document)",
        "        , active_(true)",
        "    {",
        "    }",
        "",
        "    RawClient client_;",
        f"    Raw::{owner_handle} document_;",
        "    bool active_ = false;",
        "};",
        "",
    ]


def _cpp_service_class(sdk: SemanticSdkModel, service: str) -> list[str]:
    public_name = _pascal_case(service)
    lines = [
        f"class {public_name} final",
        "{",
        "public:",
        f"    explicit {public_name}(RawClient client)",
        "        : client_(client)",
        "    {",
        "    }",
        "",
    ]
    for operation in sdk.for_service(service):
        lines.extend(
            _cpp_operation_method(
                sdk,
                operation,
                receiver_expression=None,
                target="client_",
            )
        )
    lines.extend(
        [
            "private:",
            "    RawClient client_;",
            "};",
            "",
        ]
    )
    return lines


def _cpp_extension_facade(sdk: SemanticSdkModel) -> list[str]:
    """Render the hosted C++ facade from semantic SDK descriptors."""

    wrapper_names = [
        *[_short_type(item) or "Value" for item in sdk.values],
        *[_short_type(item) or "Resource" for item in sdk.resources],
        *[_pascal_case(item) for item in sdk.services],
        "Transaction",
    ]
    lines = [
        "",
        "#if !defined(FREECAD_WASM_FREESTANDING)",
        "namespace FreeCAD::Extension",
        "{",
        "using RawClient = Raw::RawClient;",
        "template<typename T>",
        "using Result = ::Wasm::Guest::Result<T>;",
        "",
        "inline Result<void> checkResult(Result<bool> result, const char* message)",
        "{",
        "    if (!result.ok) {",
        "        return {false, std::move(result.error), result.errorCode};",
        "    }",
        "    if (!result.value) {",
        "        return {false, message, ::Wasm::Abi::ErrorCode::HostFailure};",
        "    }",
        "    return {true, {}, ::Wasm::Abi::ErrorCode::None};",
        "}",
        "",
        "inline std::string extensionString(std::string_view value)",
        "{",
        "    return std::string(value);",
        "}",
        "",
        "class Resource",
        "{",
        "public:",
        "    Resource() = default;",
        "    ~Resource() { reset(); }",
        "    Resource(const Resource&) = delete;",
        "    Resource& operator=(const Resource&) = delete;",
        "",
        "    Resource(Resource&& other) noexcept",
        "        : client_(other.client_)",
        "        , value_(other.value_)",
        "        , owned_(other.owned_)",
        "    {",
        "        other.value_ = 0U;",
        "        other.owned_ = false;",
        "    }",
        "",
        "    Resource& operator=(Resource&& other) noexcept",
        "    {",
        "        if (this != &other) {",
        "            reset();",
        "            client_ = other.client_;",
        "            value_ = other.value_;",
        "            owned_ = other.owned_;",
        "            other.value_ = 0U;",
        "            other.owned_ = false;",
        "        }",
        "        return *this;",
        "    }",
        "",
        "    explicit operator bool() const { return value_ != 0U; }",
        "    Raw::Handle value() const { return value_; }",
        "",
        "protected:",
        "    Resource(RawClient client, Raw::Handle value, bool owned)",
        "        : client_(client)",
        "        , value_(value)",
        "        , owned_(owned)",
        "    {",
        "    }",
        "",
        "    void reset()",
        "    {",
        "        if (owned_ && value_ != 0U) {",
        "            static_cast<void>(client_.release(value_));",
        "        }",
        "        value_ = 0U;",
        "        owned_ = false;",
        "    }",
        "",
        "    RawClient client_;",
        "    Raw::Handle value_ = 0U;",
        "    bool owned_ = false;",
        "};",
        "",
    ]
    for full_name in sdk.values:
        lines.extend(_cpp_value_class(sdk, full_name, wrapper_names))
    transaction_owner = sdk.transaction_owner()
    resource_order = sorted(sdk.resources)
    for full_name in resource_order:
        if full_name != transaction_owner:
            lines.extend(_cpp_resource_class(sdk, full_name, wrapper_names))
    lines.extend(_cpp_transaction_class(sdk))
    if transaction_owner is not None:
        lines.extend(_cpp_resource_class(sdk, transaction_owner, wrapper_names))
    for service in sdk.services:
        lines.extend(_cpp_service_class(sdk, service))
    lines.extend(
        [
            "class Extension final",
            "{",
            "public:",
            "    explicit Extension(RawClient client = RawClient())",
            "        : client_(client)",
            "    {",
            "    }",
            "",
            "    RawClient& raw() { return client_; }",
            "    const RawClient& raw() const { return client_; }",
        ]
    )
    for service in sdk.services:
        lines.extend(
            [
                f"    {_pascal_case(service)} {service}() const {{ return {_pascal_case(service)}(client_); }}",
            ]
        )
    lines.extend(
        [
            "",
            "private:",
            "    RawClient client_;",
            "};",
            "",
            "}  // namespace FreeCAD::Extension",
            "#endif",
            "",
        ]
    )
    return lines


def _python_type_name(type_model: dict[str, Any]) -> str:
    kind = type_model.get("kind")
    if kind == "string":
        return "str"
    if kind == "float64":
        return "float"
    if kind == "bool":
        return "bool"
    if kind in {"handle", "value"}:
        return _short_type(type_model.get("type")) or "Handle"
    if kind == "none":
        return "None"
    raise ValueError(f"unsupported Python facade type: {kind}")


def _python_parameter_declaration(parameter: dict[str, Any]) -> str:
    return f"{parameter.get('name', 'value')}: {_python_type_name(parameter.get('type', {}))}"


def _python_raw_argument(type_model: dict[str, Any], name: str) -> str:
    kind = type_model.get("kind")
    if kind == "handle":
        full_name = type_model.get("type")
        if full_name == "Wasm.Handle":
            return f"int({name})"
        return f"{type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)}({name}.value)"
    if kind == "value":
        return f"{name}._value()"
    return name


def _python_raw_method(operation: SdkOperation) -> str:
    return rust_method_name(operation.raw_method)


def _python_operation_call(
    sdk: SemanticSdkModel,
    operation: SdkOperation,
    target: str,
    receiver_expression: str | None,
) -> tuple[list[str], str]:
    setup: list[str] = []
    arguments: list[str] = []
    if operation.receiver is not None:
        if receiver_expression is None:
            raise ValueError(f"missing receiver expression for '{operation.stable_id}'")
        receiver_type = (
            f"{type_name(operation.receiver, CPP_KEYWORDS | RUST_KEYWORDS)}({receiver_expression})"
            if operation.receiver not in sdk.values
            else f"{receiver_expression}._value()"
        )
        arguments.append(receiver_type)
    for parameter in operation.params:
        name = parameter.get("name", "value")
        arguments.append(_python_raw_argument(parameter.get("type", {}), name))
    return setup, f"{target}.{_python_raw_method(operation)}({', '.join(arguments)})"


def _python_result_lines(operation: SdkOperation, call: str) -> list[str]:
    kind = operation.returns.get("kind")
    if kind == "handle":
        public_name = _short_type(operation.returns.get("type")) or "Resource"
        owned = "True" if operation.returns.get("ownership") == "owned" else "False"
        return [
            f"        value = {call}",
            f"        return {public_name}(self._client, value, owned={owned})",
        ]
    if kind == "value":
        return [
            f"        return {_short_type(operation.returns.get('type')) or 'Value'}._from_value(self._client, {call})",
        ]
    return [f"        return {call}"]


def _python_operation_method(
    sdk: SemanticSdkModel,
    operation: SdkOperation,
    *,
    receiver_expression: str | None,
    target: str,
) -> list[str]:
    method = operation.public_name
    result_type = _python_type_name(operation.returns)
    declarations = [_python_parameter_declaration(parameter) for parameter in operation.params]
    if operation.returns.get("kind") == "string":
        result_type = "str"
    signature = "self" if not declarations else f"self, {', '.join(declarations)}"
    lines = [f"    def {method}({signature}) -> {result_type}:"]
    if operation.kind == "property_read":
        lines[0] = f"    @property\n    def {method}(self) -> {result_type}:"
    if operation.kind == "property_write":
        property_name = operation.public_name.removeprefix("set_")
        setter_signature = "self" if not declarations else f"self, {', '.join(declarations)}"
        lines[0] = f"    @{property_name}.setter\n    def {property_name}({setter_signature}) -> None:"
    setup, call = _python_operation_call(sdk, operation, target, receiver_expression)
    lines.extend(setup)
    lines.extend(_python_result_lines(operation, call))
    lines.append("")
    return lines


def _python_value_class(sdk: SemanticSdkModel, full_name: str) -> list[str]:
    public_name = _short_type(full_name) or "Value"
    lines = [
        "@dataclass(frozen=True)",
        f"class {public_name}:",
        "    _client: RawClient",
        "    x: float",
        "    y: float",
        "    z: float",
        "",
        "    def _value(self) -> FreeCADBaseVectorValue:",
        "        return FreeCADBaseVectorValue(self.x, self.y, self.z)",
        "",
        "    @classmethod",
        f"    def _from_value(cls, client: RawClient, value: FreeCADBaseVectorValue) -> {public_name}:",
        "        return cls(client, value.x, value.y, value.z)",
        "",
    ]
    for operation in sdk.for_receiver(full_name):
        if operation.kind != "transaction":
            lines.extend(
                _python_operation_method(
                    sdk,
                    operation,
                    receiver_expression="self",
                    target="self._client",
                )
            )
    return lines


def _python_resource_class(sdk: SemanticSdkModel, full_name: str) -> list[str]:
    public_name = _short_type(full_name) or "Resource"
    lines = [
        f"class {public_name}(_Resource):",
    ]
    operations = [item for item in sdk.for_receiver(full_name) if item.kind != "transaction"]
    if not operations:
        lines.append("    pass")
    for operation in operations:
        lines.extend(
            _python_operation_method(
                sdk,
                operation,
                receiver_expression="self.value",
                target="self._client",
            )
        )
    open_transaction = (
        sdk.transaction("open")
        if full_name == sdk.transaction_owner()
        else None
    )
    if open_transaction is not None:
        lines.extend(
            [
                "    def transaction(self, name: str) -> Transaction:",
                "        return Transaction(self, name)",
                "",
            ]
        )
    return lines


def _python_transaction_class(sdk: SemanticSdkModel) -> list[str]:
    open_operation = sdk.transaction("open")
    commit = sdk.transaction("commit")
    abort = sdk.transaction("abort")
    if open_operation is None or commit is None or abort is None:
        return []
    owner = sdk.transaction_owner()
    if owner is None:
        return []
    owner_name = _short_type(owner) or "Resource"
    owner_handle = type_name(owner, CPP_KEYWORDS | RUST_KEYWORDS)
    return [
        "class Transaction:",
        f"    def __init__(self, document: {owner_name}, name: str):",
        "        self._document = document",
        "        self._active = False",
        f"        if not document._client.{_python_raw_method(open_operation)}({owner_handle}(document.value), name):",
        '            raise WasmHostError("host rejected document transaction")',
        "        self._active = True",
        "",
        "    def commit(self) -> None:",
        "        if self._active:",
        f"            if not self._document._client.{_python_raw_method(commit)}({owner_handle}(self._document.value)):",
        '                raise WasmHostError("host rejected transaction commit")',
        "            self._active = False",
        "",
        "    def abort(self) -> None:",
        "        if self._active:",
        f"            if not self._document._client.{_python_raw_method(abort)}({owner_handle}(self._document.value)):",
        '                raise WasmHostError("host rejected transaction abort")',
        "            self._active = False",
        "",
        "    def __enter__(self) -> Transaction:",
        "        return self",
        "",
        "    def __exit__(self, error_type, _value, _traceback) -> None:",
        "        if error_type is None:",
        "            self.commit()",
        "        else:",
        "            self.abort()",
        "",
    ]


def _python_service_class(sdk: SemanticSdkModel, service: str) -> list[str]:
    public_name = _pascal_case(service)
    lines = [
        f"class {public_name}:",
        "    def __init__(self, client: RawClient):",
        "        self._client = client",
        "",
    ]
    for operation in sdk.for_service(service):
        lines.extend(
            _python_operation_method(
                sdk,
                operation,
                receiver_expression=None,
                target="self._client",
            )
        )
    return lines


def _python_extension_facade(sdk: SemanticSdkModel) -> list[str]:
    """Render the Python facade from semantic SDK descriptors."""

    lines = [
        "",
        "",
        "class _Resource:",
        "    \"\"\"Opaque extension resource with deterministic lifetime.\"\"\"",
        "",
        "    def __init__(self, client: RawClient, value: int, owned: bool = False):",
        "        self._client = client",
        "        self.value = int(value)",
        "        self._owned = owned",
        "        self._closed = False",
        "",
        "    def close(self) -> None:",
        "        if self._owned and not self._closed:",
        "            self._client.release(self.value)",
        "            self._closed = True",
        "",
        "    def __enter__(self):",
        "        return self",
        "",
        "    def __exit__(self, _type, _value, _traceback) -> None:",
        "        self.close()",
        "",
    ]
    for full_name in sdk.values:
        lines.extend(_python_value_class(sdk, full_name))
    resource_order = sorted(
        sdk.resources,
        key=lambda item: (1 if _short_type(item) == "Document" else 0, item),
    )
    for full_name in resource_order:
        lines.extend(_python_resource_class(sdk, full_name))
    lines.extend(_python_transaction_class(sdk))
    for service in sdk.services:
        lines.extend(_python_service_class(sdk, service))
    lines.extend(
        [
            "class Extension:",
            "    \"\"\"Public FreeCAD Extension API facade.\"\"\"",
            "",
            "    def __init__(self, dispatch: Callable[[bytes], bytes]):",
            "        self._raw = RawClient(dispatch)",
        ]
    )
    for service in sdk.services:
        lines.extend(
            [
                f"        self._{service} = {_pascal_case(service)}(self._raw)",
            ]
        )
    lines.extend(
        [
            "",
            "    @property",
            "    def raw(self) -> RawClient:",
            "        return self._raw",
            "",
        ]
    )
    for service in sdk.services:
        lines.extend(
            [
                f"    def {service}(self) -> {_pascal_case(service)}:",
                f"        return self._{service}",
                "",
            ]
        )
    return lines

def render_python(model: dict[str, Any]) -> str:
    api = model.get("api", "org.freecad.wasm.api@0")
    abi = model.get("abi", {})
    request_magic = abi.get("request_magic", "FCWA")
    request_version = int(abi.get("request_version", 1))
    class_names = dict(classes(model))
    value_names = {full_name: name for full_name, name, _ in value_types(model)}
    operations = model.get("operations", [])
    lines = [
        "# Generated by generate_wasm_sdk.py. Do not edit.",
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "from typing import Callable, NewType",
        "import struct",
        "",
        f'API_VERSION = "{api}"',
        f'API_CATALOG_SIGNATURE = "{abi.get("catalog_signature", "")}"',
        "Handle = int",
        f"REQUEST_HEADER_SIZE = {int(abi.get('request_header_size', 12))}",
        f"RESPONSE_HEADER_SIZE = {int(abi.get('response_header_size', 12))}",
        "REQUEST_CAPACITY = 512",
        "MAX_STRING_LENGTH = 128",
        "",
        "",
        "class WasmGuestError(RuntimeError):",
        "    \"\"\"Base error for Python guest transport failures.\"\"\"",
        "",
        "",
        "class WasmHostError(WasmGuestError):",
        "    \"\"\"A capability or host-side operation rejected the request.\"\"\"",
        "",
        "    def __init__(self, message: str, code: int = 6):",
        "        super().__init__(message)",
        "        self.code = code",
        "",
        "",
        "class WasmProtocolError(WasmGuestError):",
        "    \"\"\"The host returned a response that violates the WASM ABI.\"\"\"",
        "",
    ]
    for _, name in class_names.items():
        lines.append(f'{name} = NewType("{name}", int)')
    if class_names:
        lines.append("")
    for _, name, encoding in value_types(model):
        if encoding != "vector3-f64":
            raise ValueError(f"unsupported Python Wasm value encoding: {encoding}")
        lines.extend(
            [
                "@dataclass(frozen=True)",
                f"class {name}:",
                "    x: float",
                "    y: float",
                "    z: float",
                "",
            ]
        )

    lines.extend(["class operations:", ""])
    if operations:
        for operation in operations:
            constant = operation_constant_name(operation.get("name", "operation"))
            lines.append(f"    {constant} = {int(operation.get('id', 0))}")
            permission = operation.get("permission")
            if permission:
                lines.append(f'    {constant}_PERMISSION = "{permission}"')
            returns = operation.get("returns", {})
            if returns.get("kind") == "handle":
                lines.append(
                    f'    {constant}_OWNERSHIP = "{returns.get("ownership", "borrowed")}"'
                )
            if operation.get("transaction"):
                lines.append(
                    f'    {constant}_TRANSACTION = "{operation["transaction"]}"'
                )
            lines.append(
                f"    {constant}_FALLIBLE = {bool(operation.get('fallible', True))!r}"
            )
            lines.append(
                f"    {constant}_NULLABLE = {bool(operation.get('returns', {}).get('nullable', False))!r}"
            )
            lines.append(
                f"    {constant}_CONSUMES = {bool(operation.get('consumes', False))!r}"
            )
    else:
        lines.append("    pass")
    lines.extend(
        [
            "",
            "",
            "class _Request:",
            "    def __init__(self, operation: int):",
            "        self._operation = operation",
            "        self._payload = bytearray()",
            "",
            "    def push_u64(self, value: int) -> None:",
            "        self._payload.extend(struct.pack(\"<Q\", int(value)))",
            "",
            "    def push_f64(self, value: float) -> None:",
            "        self._payload.extend(struct.pack(\"<d\", float(value)))",
            "",
            "    def push_bool(self, value: bool) -> None:",
            "        self._payload.extend(struct.pack(\"<?\", value))",
            "",
            "    def push_string(self, value: str) -> None:",
            "        encoded = value.encode(\"utf-8\")",
            "        if len(encoded) > MAX_STRING_LENGTH:",
            "            raise WasmGuestError(\"string exceeds the ABI length limit\")",
            "        if b\"\\x00\" in encoded:",
            "            raise WasmGuestError(\"strings cannot contain NUL bytes\")",
            "        self._payload.extend(struct.pack(\"<I\", len(encoded)))",
            "        self._payload.extend(encoded)",
            "",
            "    def push_vector(self, value: FreeCADBaseVectorValue) -> None:",
            "        self.push_f64(value.x)",
            "        self.push_f64(value.y)",
            "        self.push_f64(value.z)",
            "",
            "    def finish(self) -> bytes:",
            "        if len(self._payload) > REQUEST_CAPACITY - REQUEST_HEADER_SIZE:",
            "            raise WasmGuestError(\"request exceeds the ABI capacity\")",
            "        return struct.pack(",
            f"            \"<4sBBHI\", b\"{request_magic}\", {request_version}, self._operation, 0, len(self._payload)",
            "        ) + bytes(self._payload)",
            "",
            "",
            "class RawClient:",
            "    \"\"\"Raw Python transport client over a host dispatch callback.\"\"\"",
            "",
            "    def __init__(self, dispatch: Callable[[bytes], bytes]):",
            "        self._dispatch = dispatch",
            "",
            "    def own(self, handle: int) -> OwnedHandle:",
            "        return OwnedHandle(self, handle)",
            "",
            "    def _response(self, request: _Request) -> bytes:",
            "        try:",
            "            response = self._dispatch(request.finish())",
            "        except WasmGuestError:",
            "            raise",
            "        except Exception as error:",
            "            raise WasmHostError(str(error)) from error",
            "        if not isinstance(response, (bytes, bytearray, memoryview)):",
            "            raise WasmProtocolError(\"host dispatch did not return bytes\")",
            "        response = bytes(response)",
            "        if len(response) < RESPONSE_HEADER_SIZE:",
            "            raise WasmProtocolError(\"host returned a truncated response envelope\")",
            "        magic, version, status, error_code, flags, payload_length = struct.unpack_from(\"<4sBBBBI\", response)",
            "        if magic != b\"FCWR\" or version != 1 or flags != 0:",
            "            raise WasmProtocolError(\"host returned an invalid response envelope\")",
            "        if payload_length != len(response) - RESPONSE_HEADER_SIZE:",
            "            raise WasmProtocolError(\"host returned an invalid response length\")",
            "        payload = response[RESPONSE_HEADER_SIZE:]",
            "        if status == 1:",
            "            raise WasmHostError(payload.decode(\"utf-8\", errors=\"replace\"), error_code)",
            "        if status != 0 or error_code != 0:",
            "            raise WasmProtocolError(\"host returned an invalid response status\")",
            "        return payload",
            "",
            "    def _call_handle(self, request: _Request) -> int:",
            "        response = self._response(request)",
            "        if len(response) != 8:",
            "            raise WasmProtocolError(\"host returned an invalid handle response\")",
            "        value = struct.unpack(\"<Q\", response)[0]",
            "        if value == 0:",
            "            raise WasmProtocolError(\"host returned an invalid handle response\")",
            "        return value",
            "",
            "    def _call_value(self, request: _Request) -> FreeCADBaseVectorValue:",
            "        response = self._response(request)",
            "        if len(response) != 24:",
            "            raise WasmProtocolError(\"host returned an invalid vector response\")",
            "        return FreeCADBaseVectorValue(*struct.unpack(\"<ddd\", response))",
            "",
            "    def _call_f64(self, request: _Request) -> float:",
            "        response = self._response(request)",
            "        if len(response) != 8:",
            "            raise WasmProtocolError(\"host returned an invalid f64 response\")",
            "        return struct.unpack(\"<d\", response)[0]",
            "",
            "    def _call_bool(self, request: _Request) -> bool:",
            "        response = self._response(request)",
            "        if len(response) != 1 or response[0] not in (0, 1):",
            "            raise WasmProtocolError(\"host returned an invalid boolean response\")",
            "        return bool(response[0])",
            "",
            "    def _call_empty(self, request: _Request) -> None:",
            "        response = self._response(request)",
            "        if response:",
            '            raise WasmProtocolError("host returned a non-empty response for a void operation")',
            "        return None",
            "",
            "    def _call_string(self, request: _Request) -> str:",
            "        response = self._response(request)",
            "        if len(response) < 4:",
            "            raise WasmProtocolError(\"host returned an invalid string response\")",
            "        length = struct.unpack_from(\"<I\", response)[0]",
            "        if length != len(response) - 4:",
            "            raise WasmProtocolError(\"host returned an invalid string length\")",
            "        try:",
            "            return response[4:].decode(\"utf-8\")",
            "        except UnicodeDecodeError as error:",
            "            raise WasmProtocolError(\"host returned invalid UTF-8\") from error",
            "",
            "    def _call_release(self, request: _Request) -> bool:",
            "        response = self._response(request)",
            "        if response:",
            "            raise WasmProtocolError(\"host returned a non-empty release response\")",
            "        return True",
        ]
    )

    def python_parameter_type(parameter: dict[str, Any]) -> str:
        parameter_type = parameter.get("type", {})
        kind = parameter_type.get("kind")
        if kind == "string":
            return "str"
        if kind == "float64":
            return "float"
        if kind == "bool":
            return "bool"
        if kind == "value":
            return value_names[parameter_type["type"]]
        if kind == "handle":
            full_name = parameter_type.get("type")
            return "Handle" if full_name == "Wasm.Handle" else class_names[full_name]
        raise ValueError(f"unsupported Python parameter type: {kind}")

    for operation in operations:
        name = operation.get("name", "operation")
        method = rust_method_name(name)
        params = operation.get("params", [])
        return_type = operation.get("returns", {})
        return_kind = return_type.get("kind")
        if return_kind == "handle":
            result_type = return_type.get("type")
            result_name = "Handle" if result_type == "Wasm.Handle" else class_names[result_type]
            result_signature = result_name
        elif return_kind == "value":
            result_signature = value_names[return_type["type"]]
        elif return_kind == "float64":
            result_signature = "float"
        elif return_kind == "string":
            result_signature = "str"
        elif return_kind == "bool":
            result_signature = "bool"
        elif return_kind == "none":
            result_signature = "None"
        else:
            raise ValueError(f"unsupported Python return type: {return_kind}")

        parameter_declarations = [
            f"{parameter.get('name', 'value')}: {python_parameter_type(parameter)}"
            for parameter in params
        ]
        signature = ", ".join(["self", *parameter_declarations])
        lines.extend(
            [
                f"    def {method}({signature}) -> {result_signature}:",
                f'        \"\"\"Call {operation.get("wire_name", name)}.\"\"\"',
                f"        request = _Request(operations.{operation_constant_name(name)})",
            ]
        )
        for parameter in params:
            parameter_name = parameter.get("name", "value")
            kind = parameter.get("type", {}).get("kind")
            if kind == "string":
                lines.append(f"        request.push_string({parameter_name})")
            elif kind == "float64":
                lines.append(f"        request.push_f64({parameter_name})")
            elif kind == "bool":
                lines.append(f"        request.push_bool({parameter_name})")
            elif kind == "value":
                lines.append(f"        request.push_vector({parameter_name})")
            elif kind == "handle":
                lines.append(f"        request.push_u64(int({parameter_name}))")
            else:
                raise ValueError(f"unsupported Python parameter type: {kind}")

        if return_kind == "handle":
            lines.extend(
                [
                    "        value = self._call_handle(request)",
                    f"        return {result_name}(value)",
                    "",
                ]
            )
        elif return_kind == "value":
            lines.extend(["        return self._call_value(request)", ""])
        elif return_kind == "float64":
            lines.extend(["        return self._call_f64(request)", ""])
        elif return_kind == "string":
            lines.extend(["        return self._call_string(request)", ""])
        elif return_kind == "bool" and name == "release":
            lines.extend(["        return self._call_release(request)", ""])
        elif return_kind == "bool":
            lines.extend(["        return self._call_bool(request)", ""])
        elif return_kind == "none":
            lines.extend(["        return self._call_empty(request)", ""])

    lines.extend(
        [
            "",
            "",
            "class OwnedHandle:",
            "    \"\"\"Explicitly owned guest handle with deterministic release.\"\"\"",
            "",
            "    def __init__(self, client: RawClient, value: int):",
            "        self._client = client",
            "        self.value = int(value)",
            "        self._closed = False",
            "",
            "    def close(self) -> None:",
            "        if not self._closed:",
            "            self._client.release(self.value)",
            "            self._closed = True",
            "",
            "    def __enter__(self) -> int:",
            "        return self.value",
            "",
            "    def __exit__(self, _type, _value, _traceback) -> None:",
            "        self.close()",
            "",
        ]
    )
    sdk = semantic_sdk_model(model)
    if sdk.operations:
        lines.extend(_python_extension_facade(sdk))
    return "\n".join(lines)



def _rust_type_name(type_model: dict[str, Any]) -> str:
    kind = type_model.get("kind")
    if kind == "string":
        return "&[u8]"
    if kind == "float64":
        return "f64"
    if kind == "bool":
        return "bool"
    if kind in {"handle", "value"}:
        return _short_type(type_model.get("type")) or "Handle"
    if kind == "none":
        return "()"
    raise ValueError(f"unsupported Rust facade type: {kind}")


def _rust_result_type_name(type_model: dict[str, Any]) -> str:
    if type_model.get("kind") == "string":
        return "usize"
    return _rust_type_name(type_model)


def _rust_parameter_declaration(parameter: dict[str, Any]) -> str:
    type_model = parameter.get("type", {})
    name = parameter.get("name", "value")
    if type_model.get("kind") == "handle" and type_model.get("type") != "Wasm.Handle":
        return f"{name}: &{_short_type(type_model.get('type')) or 'Resource'}"
    if type_model.get("kind") == "value":
        return f"{name}: &{_short_type(type_model.get('type')) or 'Value'}"
    return f"{name}: {_rust_type_name(type_model)}"


def _rust_raw_argument(type_model: dict[str, Any], name: str) -> str:
    kind = type_model.get("kind")
    if kind == "handle":
        if type_model.get("type") == "Wasm.Handle":
            return name
        return f"{name}.handle"
    if kind == "value":
        return f"{name}.raw_value()"
    return name


def _rust_operation_call(
    sdk: SemanticSdkModel,
    operation: SdkOperation,
    receiver_expression: str | None,
    target: str,
) -> str:
    arguments: list[str] = []
    if operation.receiver is not None:
        if receiver_expression is None:
            raise ValueError(f"missing receiver expression for '{operation.stable_id}'")
        arguments.append(receiver_expression)
    arguments.extend(
        _rust_raw_argument(parameter.get("type", {}), parameter.get("name", "value"))
        for parameter in operation.params
    )
    return f"{target}.{rust_method_name(operation.raw_method)}({', '.join(arguments)})"


def _rust_return_expression(operation: SdkOperation, call: str) -> str:
    kind = operation.returns.get("kind")
    if kind == "handle":
        public_name = _short_type(operation.returns.get("type")) or "Resource"
        owned = "true" if operation.returns.get("ownership") == "owned" else "false"
        return (
            f"{call}.map(|handle| {public_name} {{ raw: self.raw, handle, owned: {owned} }})"
        )
    if kind == "value":
        public_name = _short_type(operation.returns.get("type")) or "Value"
        return f"{call}.map(|value| {public_name} {{ raw: self.raw, value }})"
    return call


def _rust_operation_method(
    sdk: SemanticSdkModel,
    operation: SdkOperation,
    *,
    receiver_expression: str | None,
    target: str,
) -> list[str]:
    method = operation.public_name
    declarations = [_rust_parameter_declaration(parameter) for parameter in operation.params]
    if operation.returns.get("kind") == "string":
        declarations.append("output: &mut [u8]")
    result_type = _rust_result_type_name(operation.returns)
    signature = "&self" if not declarations else f"&self, {', '.join(declarations)}"
    lines = [f"    pub fn {method}({signature}) -> Result<{result_type}>", "{"]
    call = _rust_operation_call(sdk, operation, receiver_expression, target)
    if operation.returns.get("kind") == "string":
        call = f"{call[:-1]}, output)"
    lines.extend([f"        {_rust_return_expression(operation, call)}", "    }", ""])
    return lines


def _rust_value_class(sdk: SemanticSdkModel, full_name: str) -> list[str]:
    public_name = _short_type(full_name) or "Value"
    raw_name = value_type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)
    lines = [
        "pub struct " + public_name,
        "{",
        "    raw: RawClient,",
        f"    value: {raw_name},",
        "}",
        "",
        f"impl {public_name}",
        "{",
        "    pub fn x(&self) -> f64 { self.value.x }",
        "    pub fn y(&self) -> f64 { self.value.y }",
        "    pub fn z(&self) -> f64 { self.value.z }",
        f"    fn raw_value(&self) -> {raw_name} {{ self.value }}",
        "",
    ]
    for operation in sdk.for_receiver(full_name):
        if operation.kind != "transaction":
            lines.extend(
                _rust_operation_method(
                    sdk,
                    operation,
                    receiver_expression="self.value",
                    target="self.raw",
                )
            )
    lines.extend(["}", ""])
    return lines


def _rust_resource_class(sdk: SemanticSdkModel, full_name: str) -> list[str]:
    public_name = _short_type(full_name) or "Resource"
    raw_name = type_name(full_name, CPP_KEYWORDS | RUST_KEYWORDS)
    lines = [
        "pub struct " + public_name,
        "{",
        "    raw: RawClient,",
        f"    handle: {raw_name},",
        "    owned: bool,",
        "}",
        "",
        f"impl {public_name}",
        "{",
    ]
    for operation in sdk.for_receiver(full_name):
        if operation.kind != "transaction":
            lines.extend(
                _rust_operation_method(
                    sdk,
                    operation,
                    receiver_expression="self.handle",
                    target="self.raw",
                )
            )
    if full_name == sdk.transaction_owner() and sdk.transaction("open") is not None:
        open_operation = sdk.transaction("open")
        lines.extend(
            [
                "    pub fn transaction(&self, name: &[u8]) -> Result<Transaction>",
                "    {",
                f"        if !self.raw.{rust_method_name(open_operation.raw_method)}(self.handle, name)? {{",
                "            return Err(Error { code: ErrorCode::HostFailure });",
                "        }",
                "        Ok(Transaction { raw: self.raw, handle: self.handle, active: true })",
                "    }",
                "",
            ]
        )
    lines.extend(["}", "", f"impl Drop for {public_name}", "{", "    fn drop(&mut self)", "    {", "        if self.owned {", "            let _ = self.raw.release(self.handle.0);", "        }", "    }", "}", ""])
    return lines


def _rust_transaction_class(sdk: SemanticSdkModel) -> list[str]:
    commit = sdk.transaction("commit")
    abort = sdk.transaction("abort")
    if commit is None or abort is None:
        return []
    owner = sdk.transaction_owner()
    if owner is None:
        return []
    owner_handle = type_name(owner, CPP_KEYWORDS | RUST_KEYWORDS)
    return [
        "pub struct Transaction",
        "{",
        "    raw: RawClient,",
        f"    handle: {owner_handle},",
        "    active: bool,",
        "}",
        "",
        "impl Transaction",
        "{",
        "    pub fn commit(&mut self) -> Result<()>",
        "    {",
        f"        if self.active && !self.raw.{rust_method_name(commit.raw_method)}(self.handle)? {{",
        "            return Err(Error { code: ErrorCode::HostFailure });",
        "        }",
        "        self.active = false;",
        "        Ok(())",
        "    }",
        "",
        "    pub fn abort(&mut self) -> Result<()>",
        "    {",
        f"        if self.active && !self.raw.{rust_method_name(abort.raw_method)}(self.handle)? {{",
        "            return Err(Error { code: ErrorCode::HostFailure });",
        "        }",
        "        self.active = false;",
        "        Ok(())",
        "    }",
        "}",
        "",
        "impl Drop for Transaction",
        "{",
        "    fn drop(&mut self)",
        "    {",
        f"        if self.active {{ let _ = self.raw.{rust_method_name(abort.raw_method)}(self.handle); }}",
        "    }",
        "}",
        "",
    ]


def _rust_service_class(sdk: SemanticSdkModel, service: str) -> list[str]:
    public_name = _pascal_case(service)
    lines = [
        "#[derive(Clone, Copy)]",
        f"pub struct {public_name}",
        "{",
        "    raw: RawClient,",
        "}",
        "",
        f"impl {public_name}",
        "{",
    ]
    for operation in sdk.for_service(service):
        lines.extend(
            _rust_operation_method(
                sdk,
                operation,
                receiver_expression=None,
                target="self.raw",
            )
        )
    lines.extend(["}", ""])
    return lines


def _rust_extension_facade(sdk: SemanticSdkModel) -> list[str]:
    """Render the Rust facade from semantic SDK descriptors."""

    lines: list[str] = [
        "",
        "#[derive(Clone, Copy)]",
        "pub struct Extension",
        "{",
        "    raw: RawClient,",
        "}",
        "",
        "impl Extension",
        "{",
        "    pub const fn new() -> Self",
        "    {",
        "        Self { raw: RawClient::new() }",
        "    }",
        "",
        "    pub const fn raw(&self) -> RawClient",
        "    {",
        "        self.raw",
        "    }",
        "",
    ]
    for service in sdk.services:
        lines.extend(
            [
                f"    pub const fn {service}(&self) -> {_pascal_case(service)}",
                "    {",
                f"        {_pascal_case(service)} {{ raw: self.raw }}",
                "    }",
                "",
            ]
        )
    lines.extend(["}", ""])
    for full_name in sdk.values:
        lines.extend(_rust_value_class(sdk, full_name))
    resource_order = sorted(
        sdk.resources,
        key=lambda item: (1 if _short_type(item) == "Document" else 0, item),
    )
    for full_name in resource_order:
        lines.extend(_rust_resource_class(sdk, full_name))
    lines.extend(_rust_transaction_class(sdk))
    for service in sdk.services:
        lines.extend(_rust_service_class(sdk, service))
    return lines

def render_rust(model: dict[str, Any]) -> str:
    api = model.get("api", "org.freecad.wasm.api@0")
    abi = model.get("abi", {})
    request_magic = abi.get("request_magic", "FCWA")
    request_version = int(abi.get("request_version", 1))
    error_codes = abi.get("error_codes", {})

    def error_code(name: str, default: int) -> int:
        return int(error_codes.get(name, default))
    class_names = dict(classes(model))
    value_names = {full_name: name for full_name, name, _ in value_types(model)}
    lines = [
        "// Generated by generate_wasm_sdk.py. Do not edit.",
        "",
        "use core::convert::TryInto;",
        "use core::ptr;",
        "",
        "#[link(wasm_import_module = \"freecad\")]",
        "unsafe extern \"C\" {",
        "    fn freecad_alloc(size: u32) -> u32;",
        "    fn freecad_dispatch(request: *const u8, request_length: u32) -> u64;",
        "    fn freecad_release(response_address: u32);",
        "}",
        "",
        "#[allow(dead_code)]",
        f'pub const API_VERSION: &str = "{api}";',
        f'pub const API_CATALOG_SIGNATURE: &str = "{abi.get("catalog_signature", "")}";',
        "pub type Handle = u64;",
        "",
    ]
    for _, name, encoding in value_types(model):
        if encoding != "vector3-f64":
            raise ValueError(f"unsupported Rust Wasm value encoding: {encoding}")
        lines.extend(
            [
                "#[repr(C)]",
                "#[derive(Clone, Copy, Debug, PartialEq)]",
                f"pub struct {name}",
                "{",
                "    pub x: f64,",
                "    pub y: f64,",
                "    pub z: f64,",
                "}",
                "",
            ]
        )
    for _, name in classes(model):
        lines.extend(
            [
                "#[repr(transparent)]",
                "#[derive(Clone, Copy, Debug, Eq, PartialEq)]",
                f"pub struct {name}(pub Handle);",
                "",
            ]
        )
    operations = model.get("operations", [])
    if operations:
        lines.extend(["#[allow(dead_code)]", "pub mod operations {", ""])
        for operation in operations:
            constant = re.sub(
                r"[^A-Za-z0-9]+",
                "_",
                re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", operation.get("name", "operation")),
            ).upper()
            lines.append(f"    pub const {constant}: u8 = {int(operation.get('id', 0))};")
            permission = operation.get("permission")
            if permission:
                lines.append(
                    f'    pub const {constant}_PERMISSION: &str = "{permission}";'
                )
            returns = operation.get("returns", {})
            if returns.get("kind") == "handle":
                lines.append(
                    f'    pub const {constant}_OWNERSHIP: &str = "{returns.get("ownership", "borrowed")}";'
                )
            if operation.get("transaction"):
                lines.append(
                    f'    pub const {constant}_TRANSACTION: &str = "{operation["transaction"]}";'
                )
            lines.append(
                f"    pub const {constant}_FALLIBLE: bool = {'true' if operation.get('fallible', True) else 'false'};"
            )
            lines.append(
                f"    pub const {constant}_NULLABLE: bool = {'true' if operation.get('returns', {}).get('nullable', False) else 'false'};"
            )
            lines.append(
                f"    pub const {constant}_CONSUMES: bool = {'true' if operation.get('consumes', False) else 'false'};"
            )
        lines.extend(["", "}", ""])

    lines.extend(
        [
            f"const REQUEST_HEADER_SIZE: usize = {int(abi.get('request_header_size', 12))};",
            f"const RESPONSE_HEADER_SIZE: usize = {int(abi.get('response_header_size', 12))};",
            "const REQUEST_CAPACITY: usize = 512;",
            "const MAX_STRING_LENGTH: usize = 128;",
            "",
            "struct Request",
            "{",
            "    bytes: [u8; REQUEST_CAPACITY],",
            "    length: usize,",
            "}",
            "",
            "impl Request",
            "{",
            "    fn new(operation: u8, payload_length: usize) -> Option<Self>",
            "    {",
            "        if payload_length > REQUEST_CAPACITY - REQUEST_HEADER_SIZE",
            "            || payload_length > u32::MAX as usize",
            "        {",
            "            return None;",
            "        }",
            "        let mut request = Self {",
            "            bytes: [0; REQUEST_CAPACITY],",
            "            length: REQUEST_HEADER_SIZE,",
            "        };",
            f"        request.bytes[0..4].copy_from_slice(b\"{request_magic}\");",
            f"        request.bytes[4] = {request_version};",
            "        request.bytes[5] = operation;",
            "        request.bytes[8..12].copy_from_slice(&(payload_length as u32).to_le_bytes());",
            "        Some(request)",
            "    }",
            "",
            "    fn push_bytes(&mut self, bytes: &[u8]) -> Option<()>",
            "    {",
            "        let end = self.length.checked_add(bytes.len())?;",
            "        if end > REQUEST_CAPACITY {",
            "            return None;",
            "        }",
            "        self.bytes[self.length..end].copy_from_slice(bytes);",
            "        self.length = end;",
            "        Some(())",
            "    }",
            "",
            "    #[allow(dead_code)]",
            "    fn push_u8(&mut self, value: u8) -> Option<()>",
            "    {",
            "        self.push_bytes(&[value])",
            "    }",
            "",
            "    fn push_u32(&mut self, value: u32) -> Option<()>",
            "    {",
            "        self.push_bytes(&value.to_le_bytes())",
            "    }",
            "",
            "    fn push_u64(&mut self, value: u64) -> Option<()>",
            "    {",
            "        self.push_bytes(&value.to_le_bytes())",
            "    }",
            "",
            "    fn push_f64(&mut self, value: f64) -> Option<()>",
            "    {",
            "        self.push_u64(value.to_bits())",
            "    }",
            "",
            "    fn push_string(&mut self, value: &[u8]) -> Option<()>",
            "    {",
            "        if value.len() > MAX_STRING_LENGTH {",
            "            return None;",
            "        }",
            "        self.push_u32(value.len() as u32)?;",
            "        self.push_bytes(value)",
            "    }",
            "",
            "    fn push_vector(&mut self, value: FreeCADBaseVectorValue) -> Option<()>",
            "    {",
            "        self.push_f64(value.x)?;",
            "        self.push_f64(value.y)?;",
            "        self.push_f64(value.z)",
            "    }",
            "}",
            "",
            "#[allow(dead_code)]",
            "#[repr(u8)]",
            "#[derive(Clone, Copy, Debug, Eq, PartialEq)]",
            "pub enum ErrorCode",
            "{",
            f"    None = {error_code('none', 0)},",
            f"    InvalidRequest = {error_code('invalid_request', 1)},",
            f"    PermissionDenied = {error_code('permission_denied', 2)},",
            f"    InvalidHandle = {error_code('invalid_handle', 3)},",
            f"    Unsupported = {error_code('unsupported', 4)},",
            f"    LimitExceeded = {error_code('limit_exceeded', 5)},",
            f"    HostFailure = {error_code('host_failure', 6)},",
            f"    Protocol = {error_code('protocol', 7)},",
            "}",
            "",
            "#[derive(Clone, Copy, Debug, Eq, PartialEq)]",
            "pub struct Error { pub code: ErrorCode }",
            "",
            "impl Error",
            "{",
            "    const fn protocol() -> Self { Self { code: ErrorCode::Protocol } }",
            "}",
            "",
            "pub type Result<T> = core::result::Result<T, Error>;",
            "",
            "#[derive(Clone, Copy, Debug, Default)]",
            "pub struct RawClient;",
            "",
            "#[allow(dead_code)]",
            "pub struct OwnedHandle",
            "{",
            "    client: RawClient,",
            "    value: Handle,",
            "    closed: bool,",
            "}",
            "",
            "#[allow(dead_code)]",
            "impl OwnedHandle",
            "{",
            "    pub fn value(&self) -> Handle { self.value }",
            "",
            "    pub fn close(&mut self) -> Result<()> ",
            "    {",
            "        if self.closed { return Ok(()); }",
            "        self.client.release(self.value).map(|_| ())?;",
            "        self.closed = true;",
            "        Ok(())",
            "    }",
            "}",
            "",
            "#[allow(dead_code)]",
            "impl RawClient",
            "{",
            "    pub const fn new() -> Self",
            "    {",
            "        Self",
            "    }",
            "",
            "    pub fn own(&self, value: Handle) -> OwnedHandle",
            "    {",
            "        OwnedHandle { client: *self, value, closed: false }",
            "    }",
            "",
            "    pub fn allocate_response(&self, size: u32) -> u32",
            "    {",
            "        unsafe { freecad_alloc(size) }",
            "    }",
            "",
            "    fn release_response(address: u32)",
            "    {",
            "        if address != 0 {",
            "            unsafe { freecad_release(address); }",
            "        }",
            "    }",
            "",
            "    fn response(&self, request: &Request) -> Result<(u32, u32, u32)>",
            "    {",
            "        let response = unsafe { freecad_dispatch(request.bytes.as_ptr(), request.length as u32) };",
            "        let address = response as u32;",
            "        let length = (response >> 32) as u32;",
            "        if address == 0 || length < RESPONSE_HEADER_SIZE as u32 {",
            "            Self::release_response(address);",
            "            return Err(Error::protocol());",
            "        }",
            "        let bytes = address as *const u8;",
            "        let mut payload_length = 0u32;",
            "        unsafe {",
            "            if *bytes.add(0) != b'F' || *bytes.add(1) != b'C' || *bytes.add(2) != b'W' || *bytes.add(3) != b'R' || *bytes.add(4) != 1 || *bytes.add(7) != 0 {",
            "                Self::release_response(address);",
            "                return Err(Error::protocol());",
            "            }",
            "            for shift in 0..4 { payload_length |= (*bytes.add(8 + shift) as u32) << (shift * 8); }",
            "            if payload_length != length - RESPONSE_HEADER_SIZE as u32 {",
            "                Self::release_response(address);",
            "                return Err(Error::protocol());",
            "            }",
            "            if *bytes.add(5) == 1 {",
            "                let code = match *bytes.add(6) {",
            "                    1 => ErrorCode::InvalidRequest,",
            "                    2 => ErrorCode::PermissionDenied,",
            "                    3 => ErrorCode::InvalidHandle,",
            "                    4 => ErrorCode::Unsupported,",
            "                    5 => ErrorCode::LimitExceeded,",
            "                    6 => ErrorCode::HostFailure,",
            "                    7 => ErrorCode::Protocol,",
            "                    _ => ErrorCode::Protocol,",
            "                };",
            "                Self::release_response(address);",
            "                return Err(Error { code });",
            "            }",
            "            if *bytes.add(5) != 0 || *bytes.add(6) != 0 {",
            "                Self::release_response(address);",
            "                return Err(Error::protocol());",
            "            }",
            "        }",
            "        Ok((address, address + RESPONSE_HEADER_SIZE as u32, payload_length))",
            "    }",
            "",
            "    fn call_handle(&self, request: &Request) -> Result<Handle>",
            "    {",
            "        let (address, payload, length) = self.response(request)?;",
            "        if length != 8 { Self::release_response(address); return Err(Error::protocol()); }",
            "        let mut bytes = [0u8; 8];",
            "        unsafe { ptr::copy_nonoverlapping(payload as *const u8, bytes.as_mut_ptr(), bytes.len()); }",
            "        Self::release_response(address);",
            "        let value = u64::from_le_bytes(bytes);",
            "        if value == 0 { Err(Error::protocol()) } else { Ok(value) }",
            "    }",
            "",
            "    fn call_value(&self, request: &Request) -> Result<FreeCADBaseVectorValue>",
            "    {",
            "        let (address, payload, length) = self.response(request)?;",
            "        if length != 24 { Self::release_response(address); return Err(Error::protocol()); }",
            "        let mut bytes = [0u8; 24];",
            "        unsafe {",
            "            ptr::copy_nonoverlapping(payload as *const u8, bytes.as_mut_ptr(), bytes.len());",
            "        }",
            "        Self::release_response(address);",
            "        Ok(FreeCADBaseVectorValue {",
            "            x: f64::from_bits(u64::from_le_bytes(bytes[0..8].try_into().map_err(|_| Error::protocol())?)),",
            "            y: f64::from_bits(u64::from_le_bytes(bytes[8..16].try_into().map_err(|_| Error::protocol())?)),",
            "            z: f64::from_bits(u64::from_le_bytes(bytes[16..24].try_into().map_err(|_| Error::protocol())?)),",
            "        })",
            "    }",
            "",
            "    fn call_f64(&self, request: &Request) -> Result<f64>",
            "    {",
            "        let (address, payload, length) = self.response(request)?;",
            "        if length != 8 { Self::release_response(address); return Err(Error::protocol()); }",
            "        let mut bytes = [0u8; 8];",
            "        unsafe {",
            "            ptr::copy_nonoverlapping(payload as *const u8, bytes.as_mut_ptr(), bytes.len());",
            "        }",
            "        Self::release_response(address);",
            "        Ok(f64::from_bits(u64::from_le_bytes(bytes)))",
            "    }",
            "",
            "    fn call_bool(&self, request: &Request) -> Result<bool>",
            "    {",
            "        let (address, payload, length) = self.response(request)?;",
            "        if length != 1 { Self::release_response(address); return Err(Error::protocol()); }",
            "        let value = unsafe { *(payload as *const u8) };",
            "        Self::release_response(address);",
            "        match value {",
            "            0 => Ok(false),",
            "            1 => Ok(true),",
            "            _ => Err(Error::protocol()),",
            "        }",
            "    }",
            "",
            "    fn call_empty(&self, request: &Request) -> Result<()> ",
            "    {",
            "        let (address, _payload, length) = self.response(request)?;",
            "        if length != 0 { Self::release_response(address); return Err(Error::protocol()); }",
            "        Self::release_response(address);",
            "        Ok(())",
            "    }",
            "",
            "    fn call_string(&self, request: &Request, output: &mut [u8]) -> Result<usize>",
            "    {",
            "        let (address, payload, length) = self.response(request)?;",
            "        if length < 4 { Self::release_response(address); return Err(Error::protocol()); }",
            "        let bytes = payload as *const u8;",
            "        let mut value_length = 0u32;",
            "        unsafe {",
            "            for shift in 0..4 {",
            "                value_length |= (*bytes.add(shift) as u32) << (shift * 8);",
            "            }",
            "        }",
            "        if value_length != length - 4 || value_length as usize > output.len() {",
            "            Self::release_response(address);",
            "            return Err(Error::protocol());",
            "        }",
            "        unsafe {",
            "            ptr::copy_nonoverlapping(bytes.add(4), output.as_mut_ptr(), value_length as usize);",
            "        }",
            "        Self::release_response(address);",
            "        Ok(value_length as usize)",
            "    }",
            "",
        ]
    )

    def rust_parameter_type(parameter: dict[str, Any]) -> str:
        parameter_type = parameter.get("type", {})
        kind = parameter_type.get("kind")
        if kind == "string":
            return "&[u8]"
        if kind == "float64":
            return "f64"
        if kind == "bool":
            return "bool"
        if kind == "value":
            return value_names[parameter_type["type"]]
        if kind == "handle":
            full_name = parameter_type.get("type")
            return "Handle" if full_name == "Wasm.Handle" else class_names[full_name]
        raise ValueError(f"unsupported Rust parameter type: {kind}")

    def payload_size_expression(params: list[dict[str, Any]]) -> str:
        sizes = []
        for parameter in params:
            parameter_type = parameter.get("type", {})
            kind = parameter_type.get("kind")
            if kind == "string":
                sizes.append(f"4usize + {parameter.get('name', 'value')}.len()")
            elif kind in {"float64", "handle"}:
                sizes.append("8usize")
            elif kind == "bool":
                sizes.append("1usize")
            elif kind == "value":
                sizes.append("24usize")
            else:
                raise ValueError(f"unsupported Rust payload type: {kind}")
        return " + ".join(sizes) if sizes else "0usize"

    def append_parameter(parameter: dict[str, Any]) -> list[str]:
        parameter_type = parameter.get("type", {})
        kind = parameter_type.get("kind")
        name = parameter.get("name", "value")
        if kind == "string":
            return [f"        request.push_string({name}).ok_or(Error::protocol())?;"]
        if kind == "float64":
            return [f"        request.push_f64({name}).ok_or(Error::protocol())?;"]
        if kind == "bool":
            return [f"        request.push_u8({name} as u8).ok_or(Error::protocol())?;"]
        if kind == "value":
            if parameter_type.get("encoding") != "vector3-f64":
                raise ValueError(
                    f"unsupported Rust Wasm value encoding: {parameter_type.get('encoding')}"
                )
            return [f"        request.push_vector({name}).ok_or(Error::protocol())?;"]
        if kind == "handle":
            value = name if parameter_type.get("type") == "Wasm.Handle" else f"{name}.0"
            return [f"        request.push_u64({value}).ok_or(Error::protocol())?;"]
        raise ValueError(f"unsupported Rust parameter type: {kind}")

    for operation in operations:
        name = operation.get("name", "operation")
        method = rust_method_name(name)
        params = operation.get("params", [])
        return_type = operation.get("returns", {})
        return_kind = return_type.get("kind")
        if return_kind == "handle":
            result_type = return_type.get("type")
            result_name = "Handle" if result_type == "Wasm.Handle" else class_names[result_type]
            result_signature = f"Result<{result_name}>"
        elif return_kind == "value":
            result_signature = "Result<{}>".format(value_names[return_type["type"]])
        elif return_kind == "float64":
            result_signature = "Result<f64>"
        elif return_kind == "string":
            result_signature = "Result<usize>"
        elif return_kind == "bool":
            result_signature = "Result<bool>"
        elif return_kind == "none":
            result_signature = "Result<()>"
        else:
            raise ValueError(f"unsupported Rust return type: {return_kind}")
        declarations = [
            f"{parameter.get('name', 'value')}: {rust_parameter_type(parameter)}"
            for parameter in params
        ]
        if return_kind == "string":
            declarations.append("output: &mut [u8]")
        signature = ", ".join(["&self", *declarations])
        lines.append(f"    pub fn {method}({signature}) -> {result_signature}")
        lines.extend(["    {"])
        if any(parameter.get("type", {}).get("kind") == "string" for parameter in params):
            for parameter in params:
                if parameter.get("type", {}).get("kind") == "string":
                    lines.append(
                        f"        if {parameter.get('name', 'value')}.len() > MAX_STRING_LENGTH {{"
                    )
                    lines.append("            return Err(Error::protocol());")
                    lines.append("        }")
        operation_constant = re.sub(
            r"[^A-Za-z0-9]+",
            "_",
            re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name),
        ).upper()
        lines.append(
            f"        let mut request = Request::new(operations::{operation_constant}, "
            f"{payload_size_expression(params)}).ok_or(Error::protocol())?;"
        )
        for parameter in params:
            lines.extend(append_parameter(parameter))
        if return_kind == "handle":
            lines.extend(
                [
                    f"        self.call_handle(&request).map({result_name})",
                    "    }",
                    "",
                ]
            )
        elif return_kind == "value":
            lines.extend(["        self.call_value(&request)", "    }", ""])
        elif return_kind == "float64":
            lines.extend(["        self.call_f64(&request)", "    }", ""])
        elif return_kind == "string":
            lines.extend(["        self.call_string(&request, output)", "    }", ""])
        elif return_kind == "bool" and name == "release":
            lines.extend(
                [
                    "        self.call_empty(&request).map(|_| true)",
                    "    }",
                    "",
                ]
            )
        elif return_kind == "bool":
            lines.extend(["        self.call_bool(&request)", "    }", ""])
        elif return_kind == "none":
            lines.extend(["        self.call_empty(&request)", "    }", ""])
        else:
            raise ValueError(f"unsupported Rust return type: {return_type.get('kind')}")

    lines.extend(
        [
            "}",
            "",
        ]
    )
    sdk = semantic_sdk_model(model)
    if sdk.operations:
        lines.extend(_rust_extension_facade(sdk))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-json", required=True, type=Path)
    parser.add_argument("--cpp-output", required=True, type=Path)
    parser.add_argument("--rust-output", required=True, type=Path)
    parser.add_argument("--python-output", required=True, type=Path)
    args = parser.parse_args()

    model = json.loads(args.api_json.read_text(encoding="utf-8"))
    args.cpp_output.parent.mkdir(parents=True, exist_ok=True)
    args.rust_output.parent.mkdir(parents=True, exist_ok=True)
    args.python_output.parent.mkdir(parents=True, exist_ok=True)
    args.cpp_output.write_text(render_cpp(model), encoding="utf-8")
    args.rust_output.write_text(render_rust(model), encoding="utf-8")
    args.python_output.write_text(render_python(model), encoding="utf-8")


if __name__ == "__main__":
    main()
