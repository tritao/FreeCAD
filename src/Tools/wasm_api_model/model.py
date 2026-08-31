# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed merged Wasm ABI model used between projection and SDK generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import Ownership, WasmAbiType


@dataclass(frozen=True)
class WasmAbiParameter:
    """One parameter in the lowered wire operation."""

    name: str
    type: WasmAbiType
    ownership: Ownership | None = None
    argument_kind: str | None = None
    annotation: str | None = None
    default: str | None = None

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "name": self.name,
            "type": self.type.as_json(),
        }
        if self.ownership is not None:
            value["ownership"] = self.ownership.value
        if self.argument_kind is not None:
            value["kind"] = self.argument_kind
        if self.annotation is not None:
            value["annotation"] = self.annotation
        if self.default is not None:
            value["default"] = self.default
        return value


@dataclass(frozen=True)
class WasmAbiOperation:
    """One merged projected or native operation with locked identity."""

    stable_id: str
    opcode: int
    name: str
    wire_name: str
    guest_method: str
    parameters: tuple[WasmAbiParameter, ...]
    returns: WasmAbiType
    wire_returns: WasmAbiType | None
    permission: str | None
    transaction: str | None
    origin: str
    signature: str
    fallible: bool = True
    nullable: bool = False
    source: str | None = None
    requires: tuple[str, ...] = ()
    consumes: bool = False
    adapter_kind: str | None = None
    effect: str | None = None
    property_access: str | None = None
    since: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WasmAbiOperation":
        stable_id = value.get("stable_id")
        if not isinstance(stable_id, str) or not stable_id:
            raise ValueError("WASM ABI operation has no stable_id")
        parameters = tuple(
            WasmAbiParameter(
                name=parameter["name"],
                type=WasmAbiType.from_json(parameter["type"], "WASM ABI parameter type"),
                ownership=(
                    Ownership(parameter["ownership"])
                    if parameter.get("ownership") is not None
                    else None
                ),
                argument_kind=parameter.get("kind"),
                annotation=parameter.get("annotation"),
                default=parameter.get("default"),
            )
            for parameter in value.get("params", [])
        )
        return cls(
            stable_id=stable_id,
            opcode=value["id"],
            name=value["name"],
            wire_name=value["wire_name"],
            guest_method=value["guest_method"],
            parameters=parameters,
            returns=WasmAbiType.from_json(value["returns"], "WASM ABI returns"),
            wire_returns=(
                WasmAbiType.from_json(value["wire_returns"], "WASM ABI wire returns")
                if value.get("wire_returns") is not None
                else None
            ),
            permission=value.get("permission"),
            transaction=value.get("transaction"),
            origin=value["origin"],
            signature=value["signature"],
            fallible=value.get("fallible", True),
            nullable=value.get("returns", {}).get("nullable", False),
            source=value.get("source"),
            requires=tuple(value.get("requires", [])),
            consumes=value.get("consumes", False),
            adapter_kind=value.get("adapter_kind"),
            effect=value.get("effect"),
            property_access=value.get("property_access"),
            since=value.get("since"),
        )

    def as_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "stable_id": self.stable_id,
            "name": self.name,
            "wire_name": self.wire_name,
            "id": self.opcode,
            "guest_method": self.guest_method,
            "origin": self.origin,
            "permission": self.permission,
            "params": [parameter.as_dict() for parameter in self.parameters],
            "returns": self.returns.as_json() | {"nullable": self.nullable},
            "signature": self.signature,
            "fallible": self.fallible,
        }
        if self.consumes:
            value["consumes"] = True
        if self.adapter_kind is not None:
            value["adapter_kind"] = self.adapter_kind
        if self.wire_returns is not None:
            value["wire_returns"] = self.wire_returns.as_json()
        if self.transaction is not None:
            value["transaction"] = self.transaction
        if self.source is not None:
            value["source"] = self.source
        if self.requires:
            value["requires"] = list(self.requires)
        if self.effect is not None:
            value["effect"] = self.effect
        if self.property_access is not None:
            value["property_access"] = self.property_access
        if self.since is not None:
            value["since"] = self.since
        return value


@dataclass(frozen=True)
class WasmAbiModel:
    """The complete ABI surface consumed by all SDK renderers."""

    operations: tuple[WasmAbiOperation, ...]

    @classmethod
    def from_dicts(cls, values: list[dict[str, Any]]) -> "WasmAbiModel":
        return cls(tuple(WasmAbiOperation.from_dict(value) for value in values))

    def as_dicts(self) -> list[dict[str, Any]]:
        return [operation.as_dict() for operation in self.operations]
