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
class WasmExtensionAdapter:
    """One explicit host operation outside the canonical Python projection."""

    name: str
    wire_name: str
    operation_id: int
    guest_method: str
    permission: str | None
    mutates: bool
    parameters: tuple[dict[str, Any], ...]
    returns: dict[str, Any]
    source: str | None = None
    transaction: str | None = None
    requires: tuple[str, ...] = ()
    consumes: bool = False

    @classmethod
    def from_json(cls, value: Mapping[str, Any], index: int) -> "WasmExtensionAdapter":
        """Parse one adapter while preserving ABI-specific type metadata."""

        label = f"WASM adapter at index {index}"
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
        parsed_parameters: list[dict[str, Any]] = []
        for parameter_index, parameter in enumerate(parameters):
            if not isinstance(parameter, dict):
                raise ValueError(
                    f"{label} parameter at index {parameter_index} is not an object"
                )
            parameter_name = parameter.get("name")
            parameter_type = parameter.get("type")
            if not isinstance(parameter_name, str) or not parameter_name:
                raise ValueError(
                    f"{label} parameter at index {parameter_index} has an invalid name"
                )
            if not isinstance(parameter_type, dict):
                raise ValueError(
                    f"{label} parameter '{parameter_name}' has an invalid type"
                )
            parsed_parameters.append(dict(parameter))

        returns = value.get("returns")
        if not isinstance(returns, dict):
            raise ValueError(f"{label} has invalid returns")

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
            parameters=tuple(parsed_parameters),
            returns=dict(returns),
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
            "permission": self.permission,
            "mutates": self.mutates,
            "params": [dict(parameter) for parameter in self.parameters],
            "returns": dict(self.returns),
        }
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
