#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed WASM-side definitions for host adapters not projected from ``.pyi``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WasmAbiType:
    """A typed ABI value description used by an explicit adapter."""

    kind: str
    annotation: str | None = None
    type_name: str | None = None
    encoding: str | None = None
    ownership: str | None = None
    nullable: bool | None = None

    @classmethod
    def from_json(cls, value: Mapping[str, Any], label: str) -> "WasmAbiType":
        unknown_fields = set(value) - {
            "kind",
            "annotation",
            "type",
            "encoding",
            "ownership",
            "nullable",
        }
        if unknown_fields:
            raise ValueError(
                f"{label} has unknown fields: {', '.join(sorted(unknown_fields))}"
            )
        kind = value.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"{label} has an invalid type kind")
        annotation = value.get("annotation")
        type_name = value.get("type")
        encoding = value.get("encoding")
        ownership = value.get("ownership")
        for field, field_value in (
            ("annotation", annotation),
            ("type", type_name),
            ("encoding", encoding),
            ("ownership", ownership),
        ):
            if field_value is not None and not isinstance(field_value, str):
                raise ValueError(f"{label} has an invalid '{field}'")
        nullable = value.get("nullable")
        if nullable is not None and not isinstance(nullable, bool):
            raise ValueError(f"{label} has an invalid 'nullable' flag")
        return cls(
            kind=kind,
            annotation=annotation,
            type_name=type_name,
            encoding=encoding,
            ownership=ownership,
            nullable=nullable,
        )

    def as_json(self) -> dict[str, Any]:
        value: dict[str, Any] = {"kind": self.kind}
        for field, field_value in (
            ("annotation", self.annotation),
            ("type", self.type_name),
            ("encoding", self.encoding),
            ("ownership", self.ownership),
            ("nullable", self.nullable),
        ):
            if field_value is not None:
                value[field] = field_value
        return value


@dataclass(frozen=True)
class WasmAdapterParameter:
    """One explicitly authored adapter parameter."""

    name: str
    type: WasmAbiType
    ownership: str | None = None

    @classmethod
    def from_json(
        cls,
        value: Mapping[str, Any],
        label: str,
    ) -> "WasmAdapterParameter":
        unknown_fields = set(value) - {"name", "type", "ownership"}
        if unknown_fields:
            raise ValueError(
                f"{label} has unknown fields: {', '.join(sorted(unknown_fields))}"
            )
        name = value.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} has an invalid name")
        type_value = value.get("type")
        if not isinstance(type_value, dict):
            raise ValueError(f"{label} has an invalid type")
        ownership = value.get("ownership")
        if ownership is not None and not isinstance(ownership, str):
            raise ValueError(f"{label} has an invalid ownership")
        return cls(
            name=name,
            type=WasmAbiType.from_json(type_value, f"{label} type"),
            ownership=ownership,
        )

    def as_json(self) -> dict[str, Any]:
        value: dict[str, Any] = {"name": self.name, "type": self.type.as_json()}
        if self.ownership is not None:
            value["ownership"] = self.ownership
        return value


@dataclass(frozen=True)
class WasmExtensionAdapter:
    """One explicit host operation outside the canonical Python projection."""

    name: str
    wire_name: str
    operation_id: int
    guest_method: str
    permission: str | None
    mutates: bool
    parameters: tuple[WasmAdapterParameter, ...]
    returns: WasmAbiType
    wire_returns: WasmAbiType | None = None
    source: str | None = None
    transaction: str | None = None
    requires: tuple[str, ...] = ()
    consumes: bool = False

    @classmethod
    def from_json(cls, value: Mapping[str, Any], index: int) -> "WasmExtensionAdapter":
        """Parse one adapter into typed ABI metadata."""

        label = f"WASM adapter at index {index}"
        unknown_fields = set(value) - {
            "name",
            "wire_name",
            "id",
            "guest_method",
            "permission",
            "mutates",
            "transaction",
            "source",
            "requires",
            "params",
            "returns",
            "wire_returns",
            "consumes",
        }
        if unknown_fields:
            raise ValueError(
                f"{label} has unknown fields: {', '.join(sorted(unknown_fields))}"
            )
        required_strings = ("name", "wire_name", "guest_method")
        for field in required_strings:
            field_value = value.get(field)
            if not isinstance(field_value, str) or not field_value:
                raise ValueError(f"{label} has an invalid '{field}'")

        operation_id = value.get("id")
        if isinstance(operation_id, bool) or not isinstance(operation_id, int):
            raise ValueError(f"{label} has an invalid id")

        permission = value.get("permission")
        if permission is not None and not isinstance(permission, str):
            raise ValueError(f"{label} has an invalid permission")

        mutates = value.get("mutates")
        if not isinstance(mutates, bool):
            raise ValueError(f"{label} has an invalid mutates flag")

        transaction = value.get("transaction")
        if transaction is not None and not isinstance(transaction, str):
            raise ValueError(f"{label} has an invalid transaction policy")

        source = value.get("source")
        if source is not None and not isinstance(source, str):
            raise ValueError(f"{label} has an invalid source")

        requires = value.get("requires", [])
        if not isinstance(requires, list) or not all(
            isinstance(requirement, str) and requirement for requirement in requires
        ):
            raise ValueError(f"{label} has invalid requirements")

        parameters = value.get("params")
        if not isinstance(parameters, list):
            raise ValueError(f"{label} has invalid parameters")
        parsed_parameters = tuple(
            WasmAdapterParameter.from_json(
                parameter,
                f"{label} parameter at index {parameter_index}",
            )
            for parameter_index, parameter in enumerate(parameters)
            if isinstance(parameter, dict)
        )
        if len(parsed_parameters) != len(parameters):
            raise ValueError(f"{label} contains a non-object parameter")

        returns = value.get("returns")
        if not isinstance(returns, dict):
            raise ValueError(f"{label} has invalid returns")
        wire_returns = value.get("wire_returns")
        if wire_returns is not None and not isinstance(wire_returns, dict):
            raise ValueError(f"{label} has invalid wire_returns")

        consumes = value.get("consumes", False)
        if not isinstance(consumes, bool):
            raise ValueError(f"{label} has an invalid consumes flag")

        return cls(
            name=value["name"],
            wire_name=value["wire_name"],
            operation_id=operation_id,
            guest_method=value["guest_method"],
            permission=permission,
            mutates=mutates,
            parameters=parsed_parameters,
            returns=WasmAbiType.from_json(returns, f"{label} returns"),
            wire_returns=(
                WasmAbiType.from_json(wire_returns, f"{label} wire_returns")
                if wire_returns is not None
                else None
            ),
            source=source,
            transaction=transaction,
            requires=tuple(requires),
            consumes=consumes,
        )

    def as_catalog_operation(self) -> dict[str, Any]:
        """Return the legacy renderer shape without making it the source of truth."""

        operation: dict[str, Any] = {
            "name": self.name,
            "wire_name": self.wire_name,
            "id": self.operation_id,
            "guest_method": self.guest_method,
            "origin": "adapter",
            "permission": self.permission,
            "mutates": self.mutates,
            "params": [parameter.as_json() for parameter in self.parameters],
            "returns": self.returns.as_json(),
        }
        if self.wire_returns is not None:
            operation["wire_returns"] = self.wire_returns.as_json()
        if self.source is not None:
            operation["source"] = self.source
        if self.transaction is not None:
            operation["transaction"] = self.transaction
        if self.requires:
            operation["requires"] = list(self.requires)
        if self.consumes:
            operation["consumes"] = True
        return operation


def load_wasm_extension_adapters(path: Path) -> tuple[WasmExtensionAdapter, ...]:
    """Load the explicit adapter catalog used by the WASM ABI generator."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read WASM adapter catalog '{path}'") from exc
    if not isinstance(document, dict):
        raise ValueError("WASM adapter catalog must contain an object")
    if document.get("schema") != "org.freecad.wasm.adapters":
        raise ValueError("WASM adapter catalog has an unsupported schema")
    if document.get("schema_version") != 1:
        raise ValueError("WASM adapter catalog has an unsupported schema version")
    values = document.get("adapters")
    if not isinstance(values, list):
        raise ValueError("WASM adapter catalog must contain an adapters list")
    adapters: list[WasmExtensionAdapter] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            raise ValueError(f"WASM adapter at index {index} is not an object")
        adapters.append(WasmExtensionAdapter.from_json(value, index))
    return tuple(adapters)
