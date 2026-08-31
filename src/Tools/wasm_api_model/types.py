# SPDX-License-Identifier: LGPL-2.1-or-later

"""Neutral typed WASM wire types shared by projections and adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class WireKind(str, Enum):
    """Wire-level categories understood by the current Wasm ABI."""

    BOOL = "bool"
    I64 = "int64"
    F64 = "float64"
    STRING = "string"
    HANDLE = "handle"
    VALUE = "value"
    NONE = "none"


class Ownership(str, Enum):
    """Lifetime contract for a resource crossing the Wasm ABI."""

    BORROWED = "borrowed"
    OWNED = "owned"
    CONSUMED = "consumed"


@dataclass(frozen=True)
class WasmAbiType:
    """A typed ABI value description used during wire lowering."""

    kind: WireKind
    annotation: str | None = None
    type_name: str | None = None
    encoding: str | None = None
    ownership: Ownership | None = None
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
        try:
            wire_kind = WireKind(kind)
        except ValueError as exc:
            raise ValueError(f"{label} has an invalid type kind '{kind}'") from exc
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
        try:
            parsed_ownership = (
                Ownership(ownership) if ownership is not None else None
            )
        except ValueError as exc:
            raise ValueError(
                f"{label} has an invalid ownership '{ownership}'"
            ) from exc
        return cls(
            kind=wire_kind,
            annotation=annotation,
            type_name=type_name,
            encoding=encoding,
            ownership=parsed_ownership,
            nullable=nullable,
        )

    def as_json(self) -> dict[str, Any]:
        value: dict[str, Any] = {"kind": self.kind.value}
        for field, field_value in (
            ("annotation", self.annotation),
            ("type", self.type_name),
            ("encoding", self.encoding),
            (
                "ownership",
                self.ownership.value if self.ownership is not None else None,
            ),
            ("nullable", self.nullable),
        ):
            if field_value is not None:
                value[field] = field_value
        return value
