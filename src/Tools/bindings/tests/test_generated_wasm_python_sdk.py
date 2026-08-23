# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import struct
import sys
import types
from pathlib import Path
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import generate_wasm_api  # noqa: E402
import generate_wasm_sdk  # noqa: E402


ROOT = TOOLS_DIR.parents[2]


def _read_u64(payload: bytes, offset: int = 0) -> tuple[int, int]:
    return struct.unpack_from("<Q", payload, offset)[0], offset + 8


def _read_string(payload: bytes, offset: int = 0) -> tuple[str, int]:
    length = struct.unpack_from("<I", payload, offset)[0]
    offset += 4
    end = offset + length
    return payload[offset:end].decode("utf-8"), end


class MockHost:
    def __init__(self, operations, host_error):
        self.operations = operations
        self.host_error = host_error
        self.documents: dict[int, str] = {}
        self.objects: dict[int, str] = {}
        self.transactions: dict[int, list[dict[int, str]]] = {}
        self.next_handle = 1
        self.requests: list[int] = []

    def _handle(self) -> int:
        value = self.next_handle
        self.next_handle += 1
        return value

    def __call__(self, request: bytes) -> bytes:
        magic, version, operation, flags, payload_length = struct.unpack(
            "<4sBBHI", request[:12]
        )
        if magic != b"FCWA" or version != 1 or flags != 0:
            raise AssertionError("invalid request envelope")
        payload = request[12:]
        if payload_length != len(payload):
            raise AssertionError("invalid request payload length")
        self.requests.append(operation)

        if operation == self.operations.DOCUMENT_NEW:
            name, offset = _read_string(payload)
            if offset != len(payload):
                raise AssertionError("unexpected document.new payload")
            handle = self._handle()
            self.documents[handle] = name
            self.transactions[handle] = []
            return struct.pack("<Q", handle)

        if operation == self.operations.PART_MAKE_BOX:
            if len(payload) != 24:
                raise AssertionError("unexpected part.make_box payload")
            return struct.pack("<Q", self._handle())

        if operation == self.operations.DOCUMENT_ADD_OBJECT:
            document, offset = _read_u64(payload)
            shape, offset = _read_u64(payload, offset)
            name, offset = _read_string(payload, offset)
            del shape
            if offset != len(payload):
                raise AssertionError("unexpected document.add_object payload")
            if not self.transactions[document]:
                raise self.host_error(
                    "document.add_object requires an active transaction"
                )
            handle = self._handle()
            self.objects[handle] = name
            return struct.pack("<Q", handle)

        if operation == self.operations.DOCUMENT_OPEN_TRANSACTION:
            document, offset = _read_u64(payload)
            _, offset = _read_string(payload, offset)
            if offset != len(payload):
                raise AssertionError("unexpected transaction payload")
            self.transactions[document].append(dict(self.objects))
            return b"\x01"

        if operation == self.operations.DOCUMENT_COMMIT_TRANSACTION:
            document, offset = _read_u64(payload)
            if offset != len(payload) or not self.transactions[document]:
                raise self.host_error("no active transaction")
            self.transactions[document].pop()
            return b"\x01"

        if operation == self.operations.DOCUMENT_ABORT_TRANSACTION:
            document, offset = _read_u64(payload)
            if offset != len(payload) or not self.transactions[document]:
                raise self.host_error("no active transaction")
            snapshot = self.transactions[document].pop()
            self.objects = snapshot
            return b"\x01"

        if operation == self.operations.DOCUMENT_OBJECT_GET_LABEL:
            object_handle, offset = _read_u64(payload)
            if offset != len(payload):
                raise AssertionError("unexpected label payload")
            label = self.objects[object_handle].encode("utf-8")
            return struct.pack("<I", len(label)) + label

        if operation == self.operations.DOCUMENT_OBJECT_SET_LABEL:
            object_handle, offset = _read_u64(payload)
            label, offset = _read_string(payload, offset)
            if offset != len(payload):
                raise AssertionError("unexpected set-label payload")
            if not any(self.transactions.values()):
                raise self.host_error(
                    "document.object.set_label requires an active transaction"
                )
            self.objects[object_handle] = label
            return b"\x01"

        if operation == self.operations.VECTOR_ADD:
            left = struct.unpack_from("<ddd", payload, 0)
            right = struct.unpack_from("<ddd", payload, 24)
            return struct.pack(
                "<ddd", *(left[index] + right[index] for index in range(3))
            )

        raise AssertionError(f"unhandled operation {operation}")


class GeneratedWasmPythonSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model = generate_wasm_api.build_model(
            ROOT,
            [
                ROOT / "src/Base/Vector.pyi",
                ROOT / "src/App/Document.pyi",
                ROOT / "src/App/DocumentObject.pyi",
                ROOT / "src/Mod/Part/App/TopoShape.pyi",
            ],
        )
        module = types.ModuleType("freecad_wasm_api")
        sys.modules[module.__name__] = module
        source = generate_wasm_sdk.render_python(model)
        exec(compile(source, "freecad_wasm_api.py", "exec"), module.__dict__)
        namespace = module.__dict__
        cls.Client = namespace["Client"]
        cls.WasmGuestError = namespace["WasmGuestError"]
        cls.WasmHostError = namespace["WasmHostError"]
        cls.WasmProtocolError = namespace["WasmProtocolError"]
        cls.Vector = namespace["FreeCADBaseVectorValue"]
        cls.operations = namespace["operations"]

    def test_generated_client_uses_typed_transport_and_transaction_rollback(self):
        operations = self.operations
        host = MockHost(operations, self.WasmHostError)
        client = self.Client(host)

        with self.assertRaises(self.WasmGuestError):
            client.document_new("invalid\x00name")

        vector = client.vector_add(
            self.Vector(1.0, 2.0, 3.0), self.Vector(4.0, 5.0, 6.0)
        )
        self.assertEqual((vector.x, vector.y, vector.z), (5.0, 7.0, 9.0))

        document = client.document_new("PythonExample")
        shape = client.part_make_box(10.0, 20.0, 30.0)
        with self.assertRaisesRegex(self.WasmHostError, "active transaction"):
            client.document_add_object(document, shape, "Box")

        self.assertTrue(client.document_open_transaction(document, "Add object"))
        object_handle = client.document_add_object(document, shape, "Box")
        self.assertTrue(client.document_commit_transaction(document))
        self.assertEqual(client.document_object_get_label(object_handle), "Box")

        self.assertTrue(client.document_open_transaction(document, "Configure"))
        self.assertTrue(client.document_object_set_label(object_handle, "ConfiguredBox"))
        self.assertTrue(client.document_commit_transaction(document))
        self.assertEqual(client.document_object_get_label(object_handle), "ConfiguredBox")

        self.assertTrue(client.document_open_transaction(document, "Rollback"))
        self.assertTrue(client.document_object_set_label(object_handle, "Temporary"))
        self.assertTrue(client.document_abort_transaction(document))
        self.assertEqual(client.document_object_get_label(object_handle), "ConfiguredBox")
        self.assertIn(operations.DOCUMENT_ADD_OBJECT, host.requests)

    def test_host_capability_errors_and_protocol_errors_are_preserved(self):
        def denied(_request: bytes) -> bytes:
            raise self.WasmHostError(
                "host capability 'document.modify' is not granted"
            )

        client = self.Client(denied)
        with self.assertRaisesRegex(self.WasmHostError, "document.modify"):
            client.document_open_transaction(1, "Denied")

        malformed = self.Client(lambda _request: b"bad")
        with self.assertRaises(self.WasmProtocolError):
            malformed.document_new("Broken")


if __name__ == "__main__":
    unittest.main()
