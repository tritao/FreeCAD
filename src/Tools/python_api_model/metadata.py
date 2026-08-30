# pyright: strict

"""Typed extension metadata authored alongside public API declarations."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
import re


class ExtensionMetadataError(ValueError):
    """Raised when an extension metadata decorator is malformed."""


class ExtensionEffect(str, Enum):
    READ = "read"
    COMPUTE = "compute"
    CREATE = "create"
    MODIFY = "modify"


class TransactionPolicy(str, Enum):
    NONE = "none"
    REQUIRED = "required"
    OPEN = "open"
    COMMIT = "commit"
    ABORT = "abort"


class ExtensionRepresentation(str, Enum):
    VALUE = "value"
    RESOURCE = "resource"


_LOCAL_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
_INTERFACE_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_.-]*\Z")


@dataclass(frozen=True)
class ExtensionInterfaceMetadata:
    """Local interface scope inherited by extension operations."""

    name: str
    version: int

    def __post_init__(self) -> None:
        if not _INTERFACE_NAME_PATTERN.fullmatch(self.name):
            raise ExtensionMetadataError(
                "extension_interface name must contain lowercase identifier segments"
            )
        if (
            isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version < 1
        ):
            raise ExtensionMetadataError(
                "extension_interface version must be a positive integer"
            )


@dataclass(frozen=True)
class ExtensionApiMetadata:
    """Extension-facing semantics for one callable."""

    local_id: str
    permission: str | None = None
    effect: ExtensionEffect | None = None
    transaction: TransactionPolicy = TransactionPolicy.NONE
    since: str | None = None

    def __post_init__(self) -> None:
        if not _LOCAL_ID_PATTERN.fullmatch(self.local_id):
            raise ExtensionMetadataError(
                "extension_api id must be a lowercase identifier"
            )
        if self.permission is not None and not self.permission.strip():
            raise ExtensionMetadataError("extension_api permission must not be empty")
        if self.since is not None and not self.since.strip():
            raise ExtensionMetadataError("extension_api since must not be empty")
        if (
            self.effect is ExtensionEffect.READ
            and self.transaction is not TransactionPolicy.NONE
        ):
            raise ExtensionMetadataError(
                "read-only extension_api cannot require a transaction"
            )


@dataclass(frozen=True)
class ExtensionTypeMetadata:
    """Extension-facing representation for one public class."""

    representation: ExtensionRepresentation


@dataclass(frozen=True)
class ApiMetadata:
    """Typed metadata shared by all neutral API model declarations."""

    extension_api: ExtensionApiMetadata | None = None
    extension_type: ExtensionTypeMetadata | None = None
    extension_interface: ExtensionInterfaceMetadata | None = None


def _decorator_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_call(
    decorators: Iterable[ast.expr],
    name: str,
    subject: str,
) -> ast.Call | None:
    match: ast.Call | None = None
    for decorator in decorators:
        if _decorator_name(decorator) != name:
            continue
        if not isinstance(decorator, ast.Call):
            raise ExtensionMetadataError(f"{subject}: @{name} requires keyword arguments")
        if match is not None:
            raise ExtensionMetadataError(f"{subject}: duplicate @{name} decorator")
        match = decorator
    return match


def _annotation_metadata_nodes(annotation: ast.expr | None) -> tuple[ast.expr, ...]:
    """Return metadata expressions carried by an ``Annotated`` type."""

    node = annotation
    while isinstance(node, ast.Subscript):
        base = _decorator_name(node.value)
        if base != "Final":
            break
        if isinstance(node.slice, ast.Tuple):
            if not node.slice.elts:
                return ()
            node = node.slice.elts[0]
        else:
            node = node.slice
    if (
        not isinstance(node, ast.Subscript)
        or _decorator_name(node.value) != "Annotated"
    ):
        return ()
    if isinstance(node.slice, ast.Tuple):
        return tuple(node.slice.elts[1:])
    return ()


def _literal_keyword_values(call: ast.Call, subject: str) -> dict[str, object]:
    if call.args:
        raise ExtensionMetadataError(f"{subject}: extension metadata is keyword-only")
    values: dict[str, object] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise ExtensionMetadataError(f"{subject}: **kwargs are not valid extension metadata")
        if keyword.arg in values:
            raise ExtensionMetadataError(f"{subject}: duplicate metadata field '{keyword.arg}'")
        try:
            values[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, SyntaxError) as exc:
            raise ExtensionMetadataError(
                f"{subject}: metadata field '{keyword.arg}' must be a literal"
            ) from exc
    return values


def _optional_string(value: object, field: str, subject: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ExtensionMetadataError(f"{subject}: '{field}' must be a string or None")
    return value


def parse_extension_api_metadata(
    decorators: Iterable[ast.expr],
    *,
    subject: str,
) -> ExtensionApiMetadata | None:
    """Parse one ``extension_api`` decorator into typed metadata."""

    call = _decorator_call(decorators, "extension_api", subject)
    if call is None:
        return None
    values = _literal_keyword_values(call, subject)
    allowed = {"id", "permission", "effect", "transaction", "since"}
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ExtensionMetadataError(f"{subject}: unknown extension_api field '{unknown[0]}'")
    local_id = values.get("id")
    if not isinstance(local_id, str):
        raise ExtensionMetadataError(f"{subject}: extension_api id must be a string")
    permission = _optional_string(values.get("permission"), "permission", subject)
    since = _optional_string(values.get("since"), "since", subject)

    effect_value = values.get("effect")
    if effect_value is not None and (
        not isinstance(effect_value, str)
        or effect_value not in {effect.value for effect in ExtensionEffect}
    ):
        raise ExtensionMetadataError(f"{subject}: invalid extension_api effect '{effect_value}'")
    effect = ExtensionEffect(effect_value) if effect_value is not None else None

    transaction_value = values.get("transaction")
    if transaction_value is not None and (
        not isinstance(transaction_value, str)
        or transaction_value not in {
            policy.value for policy in TransactionPolicy if policy is not TransactionPolicy.NONE
        }
    ):
        raise ExtensionMetadataError(
            f"{subject}: invalid extension_api transaction '{transaction_value}'"
        )
    transaction = (
        TransactionPolicy(transaction_value)
        if transaction_value is not None
        else TransactionPolicy.NONE
    )
    return ExtensionApiMetadata(
        local_id=local_id,
        permission=permission,
        effect=effect,
        transaction=transaction,
        since=since,
    )


def parse_extension_type_metadata(
    decorators: Iterable[ast.expr],
    *,
    subject: str,
) -> ExtensionTypeMetadata | None:
    """Parse one ``extension_type`` decorator into typed metadata."""

    call = _decorator_call(decorators, "extension_type", subject)
    if call is None:
        return None
    values = _literal_keyword_values(call, subject)
    if set(values) != {"representation"}:
        unknown = sorted(set(values) - {"representation"})
        if unknown:
            raise ExtensionMetadataError(f"{subject}: unknown extension_type field '{unknown[0]}'")
        raise ExtensionMetadataError(f"{subject}: extension_type representation is required")
    representation = values["representation"]
    if not isinstance(representation, str) or representation not in {
        item.value for item in ExtensionRepresentation
    }:
        raise ExtensionMetadataError(f"{subject}: invalid extension_type representation")
    return ExtensionTypeMetadata(ExtensionRepresentation(representation))


def parse_extension_interface_metadata(
    decorators: Iterable[ast.expr],
    *,
    subject: str,
) -> ExtensionInterfaceMetadata | None:
    """Parse one interface-scope decorator into typed metadata."""

    call = _decorator_call(decorators, "extension_interface", subject)
    if call is None:
        return None
    values = _literal_keyword_values(call, subject)
    unknown = sorted(set(values) - {"name", "version"})
    if unknown:
        raise ExtensionMetadataError(
            f"{subject}: unknown extension_interface field '{unknown[0]}'"
        )
    name = values.get("name")
    if not isinstance(name, str):
        raise ExtensionMetadataError(f"{subject}: extension_interface name must be a string")
    version = values.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ExtensionMetadataError(
            f"{subject}: extension_interface version must be an integer"
        )
    return ExtensionInterfaceMetadata(name=name, version=version)


def parse_api_metadata(
    decorators: Iterable[ast.expr],
    *,
    subject: str,
    annotation: ast.expr | None = None,
) -> ApiMetadata:
    """Parse all extension metadata decorators on one declaration."""

    annotation_decorators = _annotation_metadata_nodes(annotation)
    parsed_decorators = tuple(decorators)
    for metadata_node in annotation_decorators:
        if _decorator_name(metadata_node) in {
            "extension_api",
            "extension_type",
            "extension_interface",
        }:
            parsed_decorators += (metadata_node,)
    return ApiMetadata(
        extension_api=parse_extension_api_metadata(parsed_decorators, subject=subject),
        extension_type=parse_extension_type_metadata(parsed_decorators, subject=subject),
        extension_interface=parse_extension_interface_metadata(
            parsed_decorators,
            subject=subject,
        ),
    )
