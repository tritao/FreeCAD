# pyright: strict

"""Project the canonical Python API model into extension semantics."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Iterable

from python_api_model.metadata import (
    ExtensionInterfaceMetadata,
)
from python_api_model.model import (
    ApiAttribute,
    ApiCallableGroup,
    ApiClass,
    PythonApiModel,
)
from python_api_model.signatures import CallableSignature, SignatureParameter
from python_api_model.types import ApiType, parse_annotation

from .model import (
    ExtensionApiModel,
    ExtensionInterface,
    ExtensionOperation,
    ExtensionParameter,
    ExtensionType,
)


class ExtensionProjectionError(ValueError):
    """Raised when a Python API cannot be projected into extension semantics."""


_NAMESPACE_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)*\Z")


def load_extension_namespace(path: Path) -> str:
    """Load and validate the package namespace from an extension manifest."""

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtensionProjectionError(f"cannot read extension manifest '{path}'") from exc
    if not isinstance(manifest, dict):
        raise ExtensionProjectionError("extension manifest must contain an object")
    namespace = manifest.get("namespace")
    if not isinstance(namespace, str) or not _NAMESPACE_PATTERN.fullmatch(namespace):
        raise ExtensionProjectionError(
            "extension manifest namespace must be a reverse-domain identifier"
        )
    return namespace


def _interface_identifier(
    namespace: str,
    metadata: ExtensionInterfaceMetadata,
) -> str:
    return f"{namespace}.{metadata.name}@{metadata.version}"


def _parameter_type(parameter: SignatureParameter, module_name: str) -> ApiType:
    api_type = parameter.annotation_type or parse_annotation(parameter.annotation, module_name)
    if api_type is None:
        raise ExtensionProjectionError(
            f"parameter '{parameter.name}' has no usable annotation"
        )
    return api_type


def _return_type(signature: CallableSignature, module_name: str) -> ApiType:
    return_type = signature.return_type
    if return_type is not None:
        return return_type
    annotation = signature.return_annotation
    api_type = parse_annotation(annotation, module_name)
    if api_type is None:
        raise ExtensionProjectionError("extension operation has no return annotation")
    return api_type


def _project_operation(
    group: ApiCallableGroup,
    api_class: ApiClass | None,
    module_name: str,
    interface: ExtensionInterfaceMetadata,
    namespace: str,
) -> ExtensionOperation:
    metadata = [signature.metadata.extension_api for signature in group.signatures]
    if not metadata or any(item is None for item in metadata):
        raise ExtensionProjectionError(
            f"{module_name}.{group.name}: all overloads must declare extension_api"
        )
    first = metadata[0]
    assert first is not None
    if any(item != first for item in metadata[1:]):
        raise ExtensionProjectionError(
            f"{module_name}.{group.name}: overloads have conflicting extension metadata"
        )
    if len(group.signatures) != 1:
        raise ExtensionProjectionError(
            f"{module_name}.{group.name}: overloaded extension operations are not supported"
        )

    signature = group.signatures[0]
    parameters = signature.parameters
    if group.is_method and parameters and parameters[0].name in {"self", "cls"}:
        parameters = parameters[1:]
    projected_parameters = tuple(
        ExtensionParameter(
            name=parameter.name,
            kind=parameter.kind,
            type=_parameter_type(parameter, module_name),
            annotation=parameter.annotation,
            default=parameter.default,
        )
        for parameter in parameters
    )

    interface_id = _interface_identifier(namespace, interface)
    source_symbol = (
        f"{api_class.qualified_name}.{group.name}"
        if api_class is not None
        else f"{module_name}.{group.name}"
    )
    return ExtensionOperation(
        stable_id=f"{interface_id}/{first.local_id}",
        interface_id=interface_id,
        local_id=first.local_id,
        source=group,
        source_symbol=source_symbol,
        source_location=group.location,
        receiver=api_class.qualified_name if api_class is not None else None,
        parameters=projected_parameters,
        returns=_return_type(signature, module_name),
        permission=first.permission,
        effect=first.effect,
        transaction=first.transaction,
        since=first.since,
    )


def _project_attribute(
    attribute: ApiAttribute,
    api_class: ApiClass,
    module_name: str,
    interface: ExtensionInterfaceMetadata,
    namespace: str,
) -> ExtensionOperation:
    metadata = attribute.metadata.extension_api
    if metadata is None:
        raise ExtensionProjectionError(
            f"{api_class.qualified_name}.{attribute.name}: missing extension metadata"
        )
    return_type = attribute.annotation_type or parse_annotation(
        attribute.annotation,
        module_name,
    )
    if return_type is None:
        raise ExtensionProjectionError(
            f"{api_class.qualified_name}.{attribute.name}: no usable annotation"
        )
    interface_id = _interface_identifier(namespace, interface)
    source_symbol = f"{api_class.qualified_name}.{attribute.name}"
    return ExtensionOperation(
        stable_id=f"{interface_id}/{metadata.local_id}",
        interface_id=interface_id,
        local_id=metadata.local_id,
        source=attribute,
        source_symbol=source_symbol,
        source_location=attribute.location,
        receiver=api_class.qualified_name,
        parameters=(),
        returns=return_type,
        permission=metadata.permission,
        effect=metadata.effect,
        transaction=metadata.transaction,
        since=metadata.since,
    )


def _iter_operations(
    model: PythonApiModel,
    namespace: str,
) -> Iterable[tuple[ExtensionInterfaceMetadata, ExtensionOperation]]:
    for module in model.modules:
        module_interface = module.metadata.extension_interface
        for function in module.functions:
            metadata = [signature.metadata.extension_api for signature in function.signatures]
            if not any(item is not None for item in metadata):
                continue
            if module_interface is None:
                raise ExtensionProjectionError(
                    f"{module.name}.{function.name}: no extension interface scope"
                )
            yield module_interface, _project_operation(
                function,
                None,
                module.name,
                module_interface,
                namespace,
            )
        for api_class in module.classes:
            interface = api_class.metadata.extension_interface or module_interface
            for method in api_class.methods:
                if not any(
                    signature.metadata.extension_api is not None
                    for signature in method.signatures
                ):
                    continue
                if interface is None:
                    raise ExtensionProjectionError(
                        f"{api_class.qualified_name}.{method.name}: "
                        "no extension interface scope"
                    )
                yield interface, _project_operation(
                    method,
                    api_class,
                    module.name,
                    interface,
                    namespace,
                )
            for attribute in api_class.attributes:
                if attribute.metadata.extension_api is None:
                    continue
                if interface is None:
                    raise ExtensionProjectionError(
                        f"{api_class.qualified_name}.{attribute.name}: "
                        "no extension interface scope"
                    )
                yield interface, _project_attribute(
                    attribute,
                    api_class,
                    module.name,
                    interface,
                    namespace,
                )


def project_api_model(model: PythonApiModel, *, namespace: str) -> ExtensionApiModel:
    """Build extension interfaces and canonical operation IDs from Python APIs."""

    if not _NAMESPACE_PATTERN.fullmatch(namespace):
        raise ExtensionProjectionError("extension namespace is not a reverse-domain identifier")

    types: list[ExtensionType] = []
    for module in model.modules:
        for api_class in module.classes:
            metadata = api_class.metadata.extension_type
            if metadata is not None:
                types.append(
                    ExtensionType(
                        qualified_name=api_class.qualified_name,
                        representation=metadata.representation,
                        source_location=api_class.location,
                    )
                )

    grouped: dict[str, list[ExtensionOperation]] = {}
    declarations: dict[str, ExtensionInterfaceMetadata] = {}
    seen_operations: dict[str, str] = {}
    for declaration, operation in _iter_operations(model, namespace):
        interface_id = operation.interface_id
        previous_declaration = declarations.get(interface_id)
        if previous_declaration is not None and previous_declaration != declaration:
            raise ExtensionProjectionError(
                f"conflicting declarations for extension interface '{interface_id}'"
            )
        declarations[interface_id] = declaration
        previous_source = seen_operations.get(operation.stable_id)
        if previous_source is not None:
            raise ExtensionProjectionError(
                f"extension operation '{operation.stable_id}' is declared by both "
                f"'{previous_source}' and '{operation.source_symbol}'"
            )
        seen_operations[operation.stable_id] = operation.source_symbol
        grouped.setdefault(interface_id, []).append(operation)

    interfaces = tuple(
        ExtensionInterface(
            namespace=namespace,
            name=declaration.name,
            version=declaration.version,
            operations=tuple(sorted(grouped.get(interface_id, ()), key=lambda item: item.stable_id)),
        )
        for interface_id, declaration in sorted(declarations.items())
    )
    return ExtensionApiModel(
        namespace=namespace,
        interfaces=interfaces,
        types=tuple(sorted(types, key=lambda item: item.qualified_name)),
    )
