#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed WASM-side definitions for host adapters not projected from ``.pyi``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from python_api_model.metadata import ExtensionEffect, TransactionPolicy

from .lock import AbiLockEntry
from .naming import guest_method_name, operation_name
from .types import Ownership, WasmAbiType, WireKind


@dataclass(frozen=True)
class WasmAdapterParameter:
    """One explicitly authored adapter parameter."""

    name: str
    type: WasmAbiType
    ownership: Ownership | None = None

    def as_json(self) -> dict[str, Any]:
        value: dict[str, Any] = {"name": self.name, "type": self.type.as_json()}
        if self.ownership is not None:
            value["ownership"] = self.ownership.value
        return value


class AdapterKind(str, Enum):
    """Semantic category for an operation without a one-to-one .pyi source."""

    HOST = "host"
    COMPOSITE = "composite"


@dataclass(frozen=True)
class WasmAdapterDeclaration:
    """Typed adapter declaration whose compatibility identity comes from the ABI lock."""

    stable_id: str
    permission: str | None
    effect: ExtensionEffect | None
    parameters: tuple[WasmAdapterParameter, ...]
    returns: WasmAbiType
    wire_returns: WasmAbiType | None = None
    source: str | None = None
    transaction: TransactionPolicy = TransactionPolicy.NONE
    requires: tuple[str, ...] = ()
    consumes: bool = False
    kind: AdapterKind = AdapterKind.HOST
    sdk_service: str | None = None

    @property
    def name(self) -> str:
        return operation_name(self.stable_id, source=self.source)

    @property
    def guest_method(self) -> str:
        return guest_method_name(self.stable_id, source=self.source)

    def as_catalog_operation(self, lock_entry: AbiLockEntry) -> dict[str, Any]:
        """Lower the typed declaration with its separately locked identity."""

        if lock_entry.stable_id != self.stable_id:
            raise ValueError(
                f"WASM adapter '{self.name}' does not match ABI lock entry "
                f"'{lock_entry.stable_id}'"
            )
        operation: dict[str, Any] = {
            "stable_id": self.stable_id,
            "name": self.name,
            "wire_name": lock_entry.wire_name,
            "id": lock_entry.opcode,
            "guest_method": self.guest_method,
            "origin": "adapter",
            "adapter_kind": self.kind.value,
            "permission": self.permission,
            "effect": self.effect.value if self.effect is not None else None,
            "params": [parameter.as_json() for parameter in self.parameters],
            "returns": self.returns.as_json(),
            "signature": lock_entry.signature,
        }
        if self.wire_returns is not None:
            operation["wire_returns"] = self.wire_returns.as_json()
        if self.source is not None:
            operation["source"] = self.source
        if self.transaction is not TransactionPolicy.NONE:
            operation["transaction"] = self.transaction.value
        if self.requires:
            operation["requires"] = list(self.requires)
        if self.consumes:
            operation["consumes"] = True
        if self.sdk_service is not None:
            operation["sdk_service"] = self.sdk_service
        return operation


def _type(kind: WireKind, **kwargs: Any) -> WasmAbiType:
    return WasmAbiType(kind=kind, **kwargs)


def _parameter(name: str, parameter_type: WasmAbiType) -> WasmAdapterParameter:
    return WasmAdapterParameter(name=name, type=parameter_type)


_STRING = _type(WireKind.STRING, annotation="str")
_FLOAT64 = _type(WireKind.F64, annotation="float")
_DOCUMENT = _type(
    WireKind.HANDLE,
    type_name="FreeCAD.Document",
    annotation="Document",
    ownership=Ownership.OWNED,
    nullable=False,
)
_DOCUMENT_OBJECT = _type(
    WireKind.HANDLE,
    type_name="FreeCAD.DocumentObject",
    annotation="DocumentObject",
    ownership=Ownership.OWNED,
    nullable=False,
)
_SHAPE = _type(
    WireKind.HANDLE,
    type_name="Part.TopoShape",
    annotation="TopoShape",
    ownership=Ownership.OWNED,
    nullable=False,
)
_HANDLE = _type(WireKind.HANDLE, type_name="Wasm.Handle", annotation="Handle")
_VECTOR = _type(
    WireKind.VALUE,
    type_name="FreeCAD.Base.Vector",
    encoding="vector3-f64",
    annotation="Vector",
)
_NONE = _type(WireKind.NONE)
_BOOL = _type(WireKind.BOOL, annotation="bool", nullable=False)


WASM_ADAPTERS: tuple[WasmAdapterDeclaration, ...] = (
    WasmAdapterDeclaration(
        stable_id="org.freecad.host@1/document_new",
        permission="document.create",
        effect=ExtensionEffect.CREATE,
        parameters=(_parameter("name", _STRING),),
        returns=_DOCUMENT,
        requires=("src/App/Document.pyi",),
        sdk_service="documents",
    ),
    WasmAdapterDeclaration(
        stable_id="org.freecad.part@1/make_box",
        permission="geometry.create",
        effect=ExtensionEffect.CREATE,
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
        permission="document.modify",
        effect=ExtensionEffect.CREATE,
        parameters=(
            _parameter(
                "document",
                _type(
                    WireKind.HANDLE,
                    type_name="FreeCAD.Document",
                    annotation="Document",
                ),
            ),
            _parameter(
                "shape",
                _type(
                    WireKind.HANDLE,
                    type_name="Part.TopoShape",
                    annotation="TopoShape",
                ),
            ),
            _parameter("name", _STRING),
        ),
        returns=_DOCUMENT_OBJECT,
        source="FreeCAD.Document.addObject",
        transaction=TransactionPolicy.REQUIRED,
        requires=("src/App/Document.pyi", "src/Mod/Part/App/TopoShape.pyi"),
        kind=AdapterKind.COMPOSITE,
    ),
    WasmAdapterDeclaration(
        stable_id="org.freecad.host@1/handle_release",
        permission=None,
        effect=ExtensionEffect.MODIFY,
        parameters=(
            WasmAdapterParameter(
                name="handle",
                type=_HANDLE,
                ownership=Ownership.CONSUMED,
            ),
        ),
        returns=_BOOL,
        wire_returns=_NONE,
        consumes=True,
    ),
    WasmAdapterDeclaration(
        stable_id="org.freecad.geometry@1/vector_new",
        permission="geometry.compute",
        effect=ExtensionEffect.COMPUTE,
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
