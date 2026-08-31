#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed WASM-side definitions for host adapters not projected from ``.pyi``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .lock import AbiLockEntry
from .types import WasmAbiType


@dataclass(frozen=True)
class WasmAdapterParameter:
    """One explicitly authored adapter parameter."""

    name: str
    type: WasmAbiType
    ownership: str | None = None

    def as_json(self) -> dict[str, Any]:
        value: dict[str, Any] = {"name": self.name, "type": self.type.as_json()}
        if self.ownership is not None:
            value["ownership"] = self.ownership
        return value


class AdapterKind(str, Enum):
    """Semantic category for an operation without a one-to-one .pyi source."""

    HOST = "host"
    COMPOSITE = "composite"


@dataclass(frozen=True)
class WasmAdapterDeclaration:
    """Typed adapter declaration whose compatibility identity comes from the ABI lock."""

    stable_id: str
    name: str
    guest_method: str
    permission: str | None
    effect: str | None
    mutates: bool
    parameters: tuple[WasmAdapterParameter, ...]
    returns: WasmAbiType
    wire_returns: WasmAbiType | None = None
    source: str | None = None
    transaction: str | None = None
    requires: tuple[str, ...] = ()
    consumes: bool = False
    kind: AdapterKind = AdapterKind.HOST

    def as_catalog_operation(self, lock_entry: AbiLockEntry) -> dict[str, Any]:
        """Lower the typed declaration with its separately locked identity."""

        if lock_entry.stable_id != self.stable_id:
            raise ValueError(
                f"WASM adapter '{self.name}' does not match ABI lock entry "
                f"'{lock_entry.stable_id}'"
            )
        if lock_entry.name != self.name:
            raise ValueError(
                f"WASM adapter '{self.stable_id}' name differs from its ABI lock entry"
            )
        if lock_entry.guest_method != self.guest_method:
            raise ValueError(
                f"WASM adapter '{self.stable_id}' guest method differs from its ABI lock entry"
            )

        operation: dict[str, Any] = {
            "stable_id": self.stable_id,
            "name": lock_entry.name,
            "wire_name": lock_entry.wire_name,
            "id": lock_entry.opcode,
            "guest_method": lock_entry.guest_method,
            "origin": "adapter",
            "adapter_kind": self.kind.value,
            "permission": self.permission,
            "effect": self.effect,
            "mutates": self.mutates,
            "params": [parameter.as_json() for parameter in self.parameters],
            "returns": self.returns.as_json(),
            "wire_signature": lock_entry.signature,
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


def _type(kind: str, **kwargs: Any) -> WasmAbiType:
    return WasmAbiType(kind=kind, **kwargs)


def _parameter(name: str, parameter_type: WasmAbiType) -> WasmAdapterParameter:
    return WasmAdapterParameter(name=name, type=parameter_type)


_STRING = _type("string", annotation="str")
_FLOAT64 = _type("float64", annotation="float")
_DOCUMENT = _type(
    "handle",
    type_name="FreeCAD.Document",
    annotation="Document",
    ownership="owned",
    nullable=False,
)
_DOCUMENT_OBJECT = _type(
    "handle",
    type_name="FreeCAD.DocumentObject",
    annotation="DocumentObject",
    ownership="owned",
    nullable=False,
)
_SHAPE = _type(
    "handle",
    type_name="Part.TopoShape",
    annotation="TopoShape",
    ownership="owned",
    nullable=False,
)
_HANDLE = _type("handle", type_name="Wasm.Handle", annotation="Handle")
_VECTOR = _type(
    "value",
    type_name="FreeCAD.Base.Vector",
    encoding="vector3-f64",
    annotation="Vector",
)
_NONE = _type("none")
_BOOL = _type("bool", annotation="bool", nullable=False)


WASM_ADAPTERS: tuple[WasmAdapterDeclaration, ...] = (
    WasmAdapterDeclaration(
        stable_id="org.freecad.host@1/document_new",
        name="documentNew",
        guest_method="documentNew",
        permission="document.create",
        effect="create",
        mutates=True,
        parameters=(_parameter("name", _STRING),),
        returns=_DOCUMENT,
        requires=("src/App/Document.pyi",),
    ),
    WasmAdapterDeclaration(
        stable_id="org.freecad.part@1/make_box",
        name="partMakeBox",
        guest_method="partMakeBox",
        permission="geometry.create",
        effect="create",
        mutates=True,
        parameters=(
            _parameter("length", _FLOAT64),
            _parameter("width", _FLOAT64),
            _parameter("height", _FLOAT64),
        ),
        returns=_SHAPE,
        requires=("src/Mod/Part/App/TopoShape.pyi",),
    ),
    WasmAdapterDeclaration(
        stable_id="org.freecad.document@1/add_object",
        name="documentAddObject",
        guest_method="documentAddObject",
        permission="document.modify",
        effect="create",
        mutates=True,
        parameters=(
            _parameter("document", _type("handle", type_name="FreeCAD.Document", annotation="Document")),
            _parameter("shape", _type("handle", type_name="Part.TopoShape", annotation="TopoShape")),
            _parameter("name", _STRING),
        ),
        returns=_DOCUMENT_OBJECT,
        source="FreeCAD.Document.addObject",
        transaction="required",
        requires=("src/App/Document.pyi", "src/Mod/Part/App/TopoShape.pyi"),
        kind=AdapterKind.COMPOSITE,
    ),
    WasmAdapterDeclaration(
        stable_id="org.freecad.host@1/handle_release",
        name="release",
        guest_method="release",
        permission=None,
        effect="modify",
        mutates=False,
        parameters=(_parameter("handle", _HANDLE),),
        returns=_BOOL,
        wire_returns=_NONE,
        consumes=True,
    ),
    WasmAdapterDeclaration(
        stable_id="org.freecad.geometry@1/vector_new",
        name="vectorNew",
        guest_method="vectorNew",
        permission="geometry.compute",
        effect="compute",
        mutates=False,
        parameters=(
            _parameter("x", _FLOAT64),
            _parameter("y", _FLOAT64),
            _parameter("z", _FLOAT64),
        ),
        returns=_VECTOR,
        source="FreeCAD.Base.Vector.__init__",
        requires=("src/Base/Vector.pyi",),
    ),
)


def load_wasm_adapters() -> tuple[WasmAdapterDeclaration, ...]:
    """Return typed adapter declarations used by the authoritative generator."""

    return WASM_ADAPTERS
