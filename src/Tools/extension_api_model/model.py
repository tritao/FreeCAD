# pyright: strict

"""Neutral extension API model independent of any runtime or ABI backend."""

from __future__ import annotations

from dataclasses import dataclass

from python_api_model.metadata import (
    ExtensionEffect,
    ExtensionRepresentation,
    TransactionPolicy,
)
from python_api_model.model import ApiAttribute, ApiCallableGroup, ApiSourceLocation
from python_api_model.signatures import ArgumentKind
from python_api_model.types import ApiType


@dataclass(frozen=True)
class ExtensionParameter:
    """One operation parameter derived from a Python API signature."""

    name: str
    kind: ArgumentKind
    type: ApiType
    annotation: str | None
    default: str | None


@dataclass(frozen=True)
class ExtensionType:
    """Representation metadata for one exposed Python class."""

    qualified_name: str
    representation: ExtensionRepresentation
    source_location: ApiSourceLocation | None = None


@dataclass(frozen=True)
class ExtensionOperation:
    """One operation with an ID derived from interface scope and local ID."""

    stable_id: str
    interface_id: str
    local_id: str
    source: ApiCallableGroup | ApiAttribute
    source_symbol: str
    source_location: ApiSourceLocation | None
    receiver: str | None
    parameters: tuple[ExtensionParameter, ...]
    returns: ApiType
    permission: str | None
    effect: ExtensionEffect | None
    transaction: TransactionPolicy
    since: str | None


@dataclass(frozen=True)
class ExtensionInterface:
    """One versioned extension interface and its projected operations."""

    namespace: str
    name: str
    version: int
    operations: tuple[ExtensionOperation, ...]

    @property
    def identifier(self) -> str:
        return f"{self.namespace}.{self.name}@{self.version}"


@dataclass(frozen=True)
class ExtensionApiModel:
    """All extension-facing types and operations for one package namespace."""

    namespace: str
    interfaces: tuple[ExtensionInterface, ...]
    types: tuple[ExtensionType, ...]

    @property
    def operations(self) -> tuple[ExtensionOperation, ...]:
        return tuple(
            operation
            for interface in self.interfaces
            for operation in interface.operations
        )

    @property
    def type_representations(self) -> dict[str, ExtensionRepresentation]:
        return {item.qualified_name: item.representation for item in self.types}
