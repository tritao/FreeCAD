# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed loader and validation for the published Wasm ABI lock."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any


_SIGNATURE_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class AbiLockEntry:
    """Compatibility identity and wire fingerprint for one operation."""

    stable_id: str
    opcode: int
    wire_name: str
    signature: str
    name: str | None = None
    guest_method: str | None = None
    requires: tuple[str, ...] = ()
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the catalog-shaped view used by ABI lowering."""

        value: dict[str, Any] = {
            "id": self.opcode,
            "wire_name": self.wire_name,
            "wire_signature": self.signature,
        }
        if self.name is not None:
            value["name"] = self.name
        if self.guest_method is not None:
            value["guest_method"] = self.guest_method
        if self.requires:
            value["requires"] = list(self.requires)
        if self.reason is not None:
            value["reason"] = self.reason
        return value


@dataclass(frozen=True)
class AbiLock:
    """The active and permanently reserved Wasm operation identities."""

    version: int
    operations: Mapping[str, AbiLockEntry]
    retired: Mapping[str, AbiLockEntry]

    @property
    def reserved_opcodes(self) -> frozenset[int]:
        return frozenset(
            entry.opcode for entry in (*self.operations.values(), *self.retired.values())
        )


def _entry(
    value: Any,
    stable_id: str,
    *,
    retired: bool,
) -> AbiLockEntry:
    label = f"WASM ABI {'retired ' if retired else ''}lock entry '{stable_id}'"
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a table")

    allowed = {
        "opcode",
        "wire_name",
        "signature",
        "name",
        "guest_method",
        "requires",
        "reason",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")

    opcode = value.get("opcode")
    if isinstance(opcode, bool) or not isinstance(opcode, int) or not 0 < opcode <= 0xFF:
        raise ValueError(f"{label} has an invalid opcode")
    wire_name = value.get("wire_name")
    if not isinstance(wire_name, str) or not wire_name:
        raise ValueError(f"{label} has an invalid wire_name")
    signature = value.get("signature")
    if not isinstance(signature, str) or not _SIGNATURE_PATTERN.fullmatch(signature):
        raise ValueError(f"{label} has an invalid signature")

    name = value.get("name")
    if name is not None and (not isinstance(name, str) or not name):
        raise ValueError(f"{label} has an invalid name")
    guest_method = value.get("guest_method")
    if guest_method is not None and (not isinstance(guest_method, str) or not guest_method):
        raise ValueError(f"{label} has an invalid guest_method")

    requirements = value.get("requires", [])
    if not isinstance(requirements, list) or not all(
        isinstance(requirement, str) and requirement for requirement in requirements
    ):
        raise ValueError(f"{label} has invalid requirements")

    reason = value.get("reason")
    if retired:
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"{label} must contain a reason")
    elif reason is not None:
        raise ValueError(f"{label} cannot contain a reason")

    return AbiLockEntry(
        stable_id=stable_id,
        opcode=opcode,
        wire_name=wire_name,
        signature=signature,
        name=name,
        guest_method=guest_method,
        requires=tuple(requirements),
        reason=reason,
    )


def _validate_unique(entries: tuple[AbiLockEntry, ...]) -> None:
    fields: dict[str, set[object]] = {
        "opcode": set(),
        "wire_name": set(),
        "name": set(),
        "guest_method": set(),
    }
    for entry in entries:
        for field, value in (
            ("opcode", entry.opcode),
            ("wire_name", entry.wire_name),
            ("name", entry.name),
            ("guest_method", entry.guest_method),
        ):
            if value is None:
                continue
            if value in fields[field]:
                raise ValueError(f"WASM ABI lock field '{field}' is duplicated: '{value}'")
            fields[field].add(value)


def load_abi_lock(path: Path) -> AbiLock:
    """Load and validate one TOML ABI lock."""

    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"cannot read WASM ABI lock '{path}'") from exc
    if not isinstance(document, dict):
        raise ValueError("WASM ABI lock must contain a table")
    version = document.get("version")
    if version != 1:
        raise ValueError("WASM ABI lock has an unsupported version")

    active_values = document.get("operations", {})
    retired_values = document.get("retired", {})
    if not isinstance(active_values, dict) or not isinstance(retired_values, dict):
        raise ValueError("WASM ABI lock operations and retired entries must be tables")

    operations = {
        stable_id: _entry(value, stable_id, retired=False)
        for stable_id, value in active_values.items()
    }
    retired = {
        stable_id: _entry(value, stable_id, retired=True)
        for stable_id, value in retired_values.items()
    }
    if set(operations) & set(retired):
        raise ValueError("WASM ABI operation cannot be both active and retired")

    all_entries = tuple((*operations.values(), *retired.values()))
    _validate_unique(all_entries)
    return AbiLock(version=version, operations=operations, retired=retired)
