#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


BINDINGS_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = BINDINGS_DIR.parent
sys.path.insert(0, str(BINDINGS_DIR))
sys.path.insert(0, str(TOOLS_DIR))

import manage_wasm_abi  # noqa: E402
from wasm_api_model import AbiLock, AbiLockEntry, load_abi_lock  # noqa: E402


def operation(stable_id: str, opcode: int, *, wire_name: str | None = None) -> dict:
    return {
        "stable_id": stable_id,
        "id": opcode,
        "name": stable_id.rsplit("/", 1)[-1],
        "wire_name": wire_name or stable_id.replace("/", "."),
        "guest_method": stable_id.rsplit("/", 1)[-1],
        "signature": "sha256:" + "0" * 64,
    }


def write_catalog(path: Path, operations: list[dict]) -> None:
    path.write_text(json.dumps({"operations": operations}), encoding="utf-8")


class ManageWasmAbiTests(unittest.TestCase):
    def lock(self) -> AbiLock:
        entry = AbiLockEntry(
            stable_id="org.freecad.test@1/first",
            opcode=1,
            wire_name="test.first",
            signature="sha256:" + "0" * 64,
        )
        retired = AbiLockEntry(
            stable_id="org.freecad.test@1/old",
            opcode=2,
            wire_name="test.old",
            signature="sha256:" + "1" * 64,
            reason="removed",
        )
        return AbiLock(1, {entry.stable_id: entry}, {retired.stable_id: retired})

    def write_lock(self, path: Path, lock: AbiLock) -> None:
        path.write_text(manage_wasm_abi._render_lock(lock), encoding="utf-8")

    def test_lock_rejects_derived_identity_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wasm_abi.lock.toml"
            path.write_text(
                """version = 1

[operations."org.freecad.test@1/first"]
opcode = 1
wire_name = "test.first"
signature = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
name = "first"
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown fields: name"):
                load_abi_lock(path)

    def test_check_reports_identity_and_shape_differences(self):
        lock = self.lock()
        catalog = {
            "org.freecad.test@1/first": operation(
                "org.freecad.test@1/first", 3, wire_name="test.changed"
            ),
            "org.freecad.test@1/new": operation("org.freecad.test@1/new", 4),
        }
        added, changed, removed = manage_wasm_abi._differences(lock, catalog)
        self.assertEqual(added, ["org.freecad.test@1/new"])
        self.assertEqual(changed, ["org.freecad.test@1/first"])
        self.assertEqual(removed, [])

    def test_check_allows_missing_operations_for_partial_catalog(self):
        lock = self.lock()
        entry = AbiLockEntry(
            stable_id="org.freecad.test@1/part",
            opcode=3,
            wire_name="test.part",
            signature="sha256:" + "2" * 64,
        )
        lock = AbiLock(1, {**lock.operations, entry.stable_id: entry}, lock.retired)
        catalog = {
            "org.freecad.test@1/first": operation(
                "org.freecad.test@1/first", 1, wire_name="test.first"
            )
        }

        added, changed, removed = manage_wasm_abi._differences(
            lock,
            catalog,
            True,
        )
        self.assertEqual((added, changed, removed), ([], [], []))

    def test_check_reports_missing_operations_in_strict_mode(self):
        lock = self.lock()
        catalog = {}

        _, _, removed = manage_wasm_abi._differences(
            lock,
            catalog,
            False,
        )
        self.assertEqual(removed, ["org.freecad.test@1/first"])

    def test_add_new_allocates_after_active_and_retired_opcodes(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "wasm_abi.lock.toml"
            catalog_path = Path(directory) / "catalog.json"
            self.write_lock(lock_path, self.lock())
            write_catalog(catalog_path, [operation("org.freecad.test@1/new", 99)])

            self.assertEqual(manage_wasm_abi._add_new(lock_path, catalog_path), 0)
            lock = load_abi_lock(lock_path)
            self.assertEqual(lock.operations["org.freecad.test@1/new"].opcode, 3)
            self.assertEqual(lock.retired["org.freecad.test@1/old"].opcode, 2)

    def test_retire_preserves_identity_and_requires_source_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "wasm_abi.lock.toml"
            catalog_path = Path(directory) / "catalog.json"
            self.write_lock(lock_path, self.lock())
            write_catalog(catalog_path, [])

            self.assertEqual(
                manage_wasm_abi._retire(
                    lock_path,
                    "org.freecad.test@1/first",
                    "superseded",
                    catalog_path,
                ),
                0,
            )
            lock = load_abi_lock(lock_path)
            retired = lock.retired["org.freecad.test@1/first"]
            self.assertEqual(retired.opcode, 1)
            self.assertEqual(retired.reason, "superseded")

    def test_retire_rejects_an_operation_still_in_the_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "wasm_abi.lock.toml"
            catalog_path = Path(directory) / "catalog.json"
            self.write_lock(lock_path, self.lock())
            write_catalog(
                catalog_path,
                [operation("org.freecad.test@1/first", 1, wire_name="test.first")],
            )

            with self.assertRaisesRegex(ValueError, "still present"):
                manage_wasm_abi._retire(
                    lock_path,
                    "org.freecad.test@1/first",
                    "superseded",
                    catalog_path,
                )

    def test_catalog_rejects_duplicate_wire_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog_path = Path(directory) / "catalog.json"
            write_catalog(
                catalog_path,
                [
                    operation("org.freecad.test@1/first", 1),
                    operation("org.freecad.test@1/second", 1),
                ],
            )
            with self.assertRaisesRegex(ValueError, "field 'id' is duplicated"):
                manage_wasm_abi._load_catalog(catalog_path)


if __name__ == "__main__":
    unittest.main()
