#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Check and maintain the published FreeCAD Wasm ABI lock."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/Tools"))

from wasm_api_model import AbiLock, AbiLockEntry, load_abi_lock  # noqa: E402


_SIGNATURE_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read generated Wasm API catalog '{path}'") from exc
    if not isinstance(document, dict) or not isinstance(document.get("operations"), list):
        raise ValueError("generated Wasm API catalog must contain an operations list")

    operations: dict[str, dict[str, Any]] = {}
    fields: dict[str, set[object]] = {
        "id": set(),
        "wire_name": set(),
        "name": set(),
        "guest_method": set(),
    }
    for operation in document["operations"]:
        if not isinstance(operation, dict):
            raise ValueError("generated Wasm API operation must be an object")
        stable_id = operation.get("stable_id")
        if not isinstance(stable_id, str) or not stable_id:
            raise ValueError("generated Wasm API operation has no stable_id")
        if stable_id in operations:
            raise ValueError(f"generated Wasm API stable_id is duplicated: '{stable_id}'")
        _catalog_entry(operation)
        for field in fields:
            value = operation.get(field)
            if value is None:
                continue
            if value in fields[field]:
                raise ValueError(
                    f"generated Wasm API field '{field}' is duplicated: '{value}'"
                )
            fields[field].add(value)
        operations[stable_id] = operation
    return operations


def _catalog_entry(operation: dict[str, Any]) -> AbiLockEntry:
    stable_id = operation.get("stable_id")
    opcode = operation.get("id")
    wire_name = operation.get("wire_name")
    signature = operation.get("wire_signature")
    name = operation.get("name")
    guest_method = operation.get("guest_method")
    requires = operation.get("requires", [])
    if not isinstance(stable_id, str) or not stable_id:
        raise ValueError("generated Wasm API operation has an invalid stable_id")
    if isinstance(opcode, bool) or not isinstance(opcode, int) or not 0 < opcode <= 0xFF:
        raise ValueError(f"generated Wasm API operation '{stable_id}' has an invalid id")
    if not isinstance(wire_name, str) or not wire_name:
        raise ValueError(f"generated Wasm API operation '{stable_id}' has an invalid wire_name")
    if not isinstance(signature, str) or not _SIGNATURE_PATTERN.fullmatch(signature):
        raise ValueError(
            f"generated Wasm API operation '{stable_id}' has an invalid wire_signature"
        )
    if not isinstance(name, str) or not name:
        raise ValueError(f"generated Wasm API operation '{stable_id}' has an invalid name")
    if not isinstance(guest_method, str) or not guest_method:
        raise ValueError(
            f"generated Wasm API operation '{stable_id}' has an invalid guest_method"
        )
    if not isinstance(requires, list) or not all(
        isinstance(requirement, str) and requirement for requirement in requires
    ):
        raise ValueError(
            f"generated Wasm API operation '{stable_id}' has invalid requirements"
        )
    try:
        return AbiLockEntry(
            stable_id=stable_id,
            opcode=opcode,
            wire_name=wire_name,
            signature=signature,
            name=name,
            guest_method=guest_method,
            requires=tuple(requires),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"generated Wasm API operation '{operation.get('stable_id', '<unknown>')}' "
            "is missing lock fields"
        ) from exc


def _lock_fields(entry: AbiLockEntry) -> tuple[Any, ...]:
    return (
        entry.opcode,
        entry.wire_name,
        entry.signature,
        entry.name,
        entry.guest_method,
        entry.requires,
    )


def _differences(
    lock: AbiLock,
    catalog: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    generated = {
        stable_id: _catalog_entry(operation)
        for stable_id, operation in catalog.items()
    }
    added = sorted(set(generated) - set(lock.operations))
    removed = sorted(set(lock.operations) - set(generated))
    changed = sorted(
        stable_id
        for stable_id in set(generated) & set(lock.operations)
        if _lock_fields(generated[stable_id]) != _lock_fields(lock.operations[stable_id])
    )
    return added, changed, removed


def _print_differences(
    added: list[str],
    changed: list[str],
    removed: list[str],
) -> None:
    print("Added:")
    for stable_id in added:
        print(f"  {stable_id}")
    print("Changed:")
    for stable_id in changed:
        print(f"  {stable_id}")
    print("Removed:")
    for stable_id in removed:
        print(f"  {stable_id}")


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _render_lock(lock: AbiLock) -> str:
    lines = [
        "# SPDX-License-Identifier: LGPL-2.1-or-later",
        "",
        "version = 1",
        "",
    ]
    active = sorted(lock.operations.values(), key=lambda entry: entry.opcode)
    retired = sorted(lock.retired.values(), key=lambda entry: entry.opcode)
    for entry in active:
        lines.append(f"[operations.{_toml_string(entry.stable_id)}]")
        lines.extend(_render_entry(entry))
        lines.append("")
    if retired:
        for entry in retired:
            lines.append(f"[retired.{_toml_string(entry.stable_id)}]")
            lines.extend(_render_entry(entry, include_reason=True))
            lines.append("")
    return "\n".join(lines)


def _render_entry(entry: AbiLockEntry, *, include_reason: bool = False) -> list[str]:
    lines = [
        f"opcode = {entry.opcode}",
        f"wire_name = {_toml_string(entry.wire_name)}",
        f"signature = {_toml_string(entry.signature)}",
    ]
    if entry.name is not None:
        lines.insert(1, f"name = {_toml_string(entry.name)}")
    if entry.guest_method is not None:
        insert_at = 2 if entry.name is not None else 1
        lines.insert(insert_at, f"guest_method = {_toml_string(entry.guest_method)}")
    if entry.requires:
        lines.append(
            "requires = [" + ", ".join(_toml_string(value) for value in entry.requires) + "]"
        )
    if include_reason:
        lines.append(f"reason = {_toml_string(entry.reason or '')}")
    return lines


def _write_lock(path: Path, lock: AbiLock) -> None:
    path.write_text(_render_lock(lock), encoding="utf-8")


def _entry_from_operation(operation: dict[str, Any], opcode: int) -> AbiLockEntry:
    entry = _catalog_entry(operation)
    return AbiLockEntry(
        stable_id=entry.stable_id,
        opcode=opcode,
        wire_name=entry.wire_name,
        signature=entry.signature,
        name=entry.name,
        guest_method=entry.guest_method,
        requires=entry.requires,
    )


def _add_new(lock_path: Path, catalog_path: Path) -> int:
    lock = load_abi_lock(lock_path)
    catalog = _load_catalog(catalog_path)
    retired = set(lock.retired) & set(catalog)
    if retired:
        raise ValueError(
            "generated catalog contains retired operation(s): "
            + ", ".join(sorted(retired))
        )
    additions = [
        operation
        for stable_id, operation in catalog.items()
        if stable_id not in lock.operations and stable_id not in lock.retired
    ]
    if not additions:
        print("No new operations.")
        return 0

    next_opcode = max(lock.reserved_opcodes, default=0) + 1
    operations = dict(lock.operations)
    for operation in sorted(additions, key=lambda value: value["stable_id"]):
        if next_opcode > 0xFF:
            raise ValueError("WASM ABI opcode space is exhausted")
        entry = _entry_from_operation(operation, next_opcode)
        operations[entry.stable_id] = entry
        print(f"Added {entry.stable_id} at opcode {entry.opcode}")
        next_opcode += 1
    _write_lock(lock_path, AbiLock(lock.version, operations, lock.retired))
    return 0


def _retire(lock_path: Path, stable_id: str, reason: str, catalog_path: Path | None) -> int:
    lock = load_abi_lock(lock_path)
    if stable_id not in lock.operations:
        if stable_id in lock.retired:
            raise ValueError(f"WASM ABI operation is already retired: '{stable_id}'")
        raise ValueError(f"WASM ABI operation is not active: '{stable_id}'")
    if catalog_path is not None and stable_id in _load_catalog(catalog_path):
        raise ValueError(
            f"cannot retire '{stable_id}' while it is still present in the generated catalog"
        )

    active = dict(lock.operations)
    entry = active.pop(stable_id)
    retired = dict(lock.retired)
    retired[stable_id] = AbiLockEntry(
        stable_id=entry.stable_id,
        opcode=entry.opcode,
        wire_name=entry.wire_name,
        signature=entry.signature,
        name=entry.name,
        guest_method=entry.guest_method,
        requires=entry.requires,
        reason=reason,
    )
    _write_lock(lock_path, AbiLock(lock.version, active, retired))
    print(f"Retired {stable_id} at opcode {entry.opcode}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--diff", action="store_true")
    actions.add_argument("--add-new", action="store_true")
    actions.add_argument("--retire", action="store_true")
    parser.add_argument(
        "--lock",
        type=Path,
        default=ROOT / "src/Mod/Wasm/wasm_abi.lock.toml",
    )
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--stable-id")
    parser.add_argument("--reason")
    args = parser.parse_args(argv)

    action = next(
        name
        for name in ("check", "diff", "add_new", "retire")
        if getattr(args, name)
    )
    if action in ("check", "diff", "add_new", "retire") and args.catalog is None:
        parser.error(f"--{action.replace('_', '-')} requires --catalog")
    if action == "retire" and (not args.stable_id or not args.reason):
        parser.error("--retire requires --stable-id and --reason")

    if action == "retire":
        return _retire(args.lock, args.stable_id, args.reason, args.catalog)

    if action == "add_new":
        return _add_new(args.lock, args.catalog)

    lock = load_abi_lock(args.lock)
    catalog = _load_catalog(args.catalog)
    retired = set(lock.retired) & set(catalog)
    if retired:
        raise ValueError(
            "generated catalog contains retired operation(s): "
            + ", ".join(sorted(retired))
        )
    differences = _differences(lock, catalog)
    _print_differences(*differences)
    return 1 if any(differences) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
