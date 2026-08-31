# SPDX-License-Identifier: LGPL-2.1-or-later

"""Neutral typed WASM wire types shared by projections and adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WasmAbiType:
    """A typed ABI value description used during wire lowering."""

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
