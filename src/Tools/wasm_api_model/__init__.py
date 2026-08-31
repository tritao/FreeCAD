# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed intermediate models for the FreeCAD Wasm API."""

from .lock import AbiLock, AbiLockEntry, load_abi_lock
from .model import WasmAbiModel, WasmAbiOperation, WasmAbiParameter
from .naming import guest_method_name, operation_name
from .adapters import (
    AdapterKind,
    WasmAdapterDeclaration,
    WasmAdapterParameter,
    load_wasm_adapters,
)
from .types import Ownership, WasmAbiType, WireKind

__all__ = [
    "AbiLock",
    "AbiLockEntry",
    "AdapterKind",
    "WasmAdapterDeclaration",
    "WasmAdapterParameter",
    "WasmAbiModel",
    "WasmAbiOperation",
    "WasmAbiParameter",
    "WasmAbiType",
    "Ownership",
    "WireKind",
    "guest_method_name",
    "load_abi_lock",
    "load_wasm_adapters",
    "operation_name",
]
