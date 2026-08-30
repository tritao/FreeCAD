# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import generate_wasm_api  # noqa: E402
from extension_api_model import project_api_model  # noqa: E402
from stubgen.api_extract import extract_curated_api_model  # noqa: E402
from python_api_model.types import parse_annotation  # noqa: E402
from wasm_api_model import load_wasm_extension_adapters  # noqa: E402


ROOT = TOOLS_DIR.parents[2]


def model_for(annotation: str) -> dict:
    return generate_wasm_api._wasm_type(
        parse_annotation(annotation, "Part"),
        annotation,
        "Part",
    )


class GenerateWasmApiTests(unittest.TestCase):
    def extension_model(self):
        api_model = extract_curated_api_model(
            ROOT,
            ROOT / "src",
            source_paths=[
                ROOT / "src/Base/Vector.pyi",
                ROOT / "src/App/Document.pyi",
                ROOT / "src/App/DocumentObject.pyi",
                ROOT / "src/Mod/Part/App/TopoShape.pyi",
            ],
        )
        return project_api_model(api_model, namespace="org.freecad")

    def test_unparameterized_collections_are_not_handles(self):
        self.assertEqual(model_for("List")["kind"], "list")
        self.assertEqual(model_for("List")["item"]["kind"], "value")
        self.assertEqual(model_for("Sequence")["kind"], "list")

    def test_variadic_tuple_is_explicit(self):
        model = model_for("Tuple[TopoShape, ...]")
        self.assertEqual(model["kind"], "tuple")
        self.assertTrue(model["variadic"])
        self.assertEqual(model["item"]["kind"], "handle")
        self.assertEqual(model["items"], [])

    def test_fixed_tuple_and_mapping_are_structured(self):
        tuple_model = model_for("tuple[str, int]")
        self.assertFalse(tuple_model["variadic"])
        self.assertEqual(
            [item["kind"] for item in tuple_model["items"]],
            ["string", "int64"],
        )

        mapping_model = model_for("Mapping[str, float]")
        self.assertEqual(mapping_model["kind"], "dict")
        self.assertEqual(mapping_model["key"]["kind"], "string")
        self.assertEqual(mapping_model["value"]["kind"], "float64")

    def test_union_optional_and_literal_are_structured(self):
        self.assertEqual(model_for("Optional[str]")["kind"], "optional")
        self.assertEqual(model_for("Union[str, None]")["kind"], "optional")
        self.assertEqual(model_for("str | None")["kind"], "optional")

        literal_model = model_for("Literal['read', 'write']")
        self.assertEqual(literal_model["kind"], "literal")
        self.assertEqual(literal_model["values"], ["read", "write"])

    def test_operation_catalog_rejects_duplicate_ids(self):
        operations = [
            {
                "name": "first",
                "wire_name": "test.first",
                "id": 1,
                "guest_method": "first",
                "permission": None,
                "mutates": False,
                "params": [],
                "returns": {"kind": "none"},
            },
            {
                "name": "second",
                "wire_name": "test.second",
                "id": 1,
                "guest_method": "second",
                "permission": None,
                "mutates": False,
                "params": [],
                "returns": {"kind": "none"},
            },
        ]
        with self.assertRaisesRegex(ValueError, "operation id 1"):
            generate_wasm_api._validate_operation_catalog(operations)

    def test_abi_lock_rejects_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, "operation id 1"):
            generate_wasm_api._validate_abi_lock(
                {
                    "org.freecad.test@1/first": {
                        "id": 1,
                        "name": "first",
                        "wire_name": "test.first",
                        "guest_method": "first",
                    },
                    "org.freecad.test@1/second": {
                        "id": 1,
                        "name": "second",
                        "wire_name": "test.second",
                        "guest_method": "second",
                    },
                }
            )

    def test_projected_operations_require_lock_or_adapter(self):
        with self.assertRaisesRegex(ValueError, "missing projected operation"):
            generate_wasm_api._validate_projected_abi_lock(
                {
                    "org.freecad.geometry@1/vector_add": {
                        "id": 6,
                        "name": "vectorAdd",
                        "wire_name": "base.vector.add",
                        "guest_method": "vectorAdd",
                    }
                },
                self.extension_model(),
                {
                    "src/Base/Vector.pyi",
                    "src/App/Document.pyi",
                    "src/App/DocumentObject.pyi",
                    "src/Mod/Part/App/TopoShape.pyi",
                },
                {
                    "FreeCAD.Base.Vector.__init__": "vectorNew",
                },
            )

    def test_stale_lock_entries_must_be_retired(self):
        lock = json.loads(
            (ROOT / "src/Mod/Wasm/WasmApiOperations.json").read_text(encoding="utf-8")
        )["abi"]["operations"]
        lock["org.freecad.geometry@1/not_published"] = {
            "id": 21,
            "name": "notPublished",
            "wire_name": "test.not_published",
            "guest_method": "notPublished",
        }
        with self.assertRaisesRegex(ValueError, "stale active operation"):
            generate_wasm_api._validate_projected_abi_lock(
                lock,
                self.extension_model(),
                {
                    "src/Base/Vector.pyi",
                    "src/App/Document.pyi",
                    "src/App/DocumentObject.pyi",
                    "src/Mod/Part/App/TopoShape.pyi",
                },
                {
                    "FreeCAD.Base.Vector.__init__": "vectorNew",
                },
            )

    def test_retired_ids_cannot_be_reused(self):
        retired_ids = generate_wasm_api._validate_retired_abi_lock(
            {
                "org.freecad.geometry@1/removed": {
                    "id": 21,
                    "name": "removed",
                    "wire_name": "geometry.removed",
                    "guest_method": "removed",
                    "reason": "removed from the experimental surface",
                }
            },
            {},
        )
        self.assertEqual(retired_ids, {21})
        with self.assertRaisesRegex(ValueError, "reserved operation id 21"):
            generate_wasm_api._validate_reserved_catalog_ids(
                [{"id": 21, "name": "newOperation"}],
                retired_ids,
            )

    def test_adapters_are_loaded_from_the_separate_typed_catalog(self):
        adapters = load_wasm_extension_adapters(
            ROOT / "src/Mod/Wasm/WasmApiAdapters.json"
        )
        self.assertEqual(len(adapters), 5)
        document_new = next(adapter for adapter in adapters if adapter.name == "documentNew")
        self.assertEqual(document_new.operation_id, 1)
        self.assertEqual(document_new.requires, ("src/App/Document.pyi",))
        self.assertEqual(document_new.parameters[0].type.kind, "string")
        self.assertEqual(document_new.returns.ownership, "owned")
        self.assertEqual(
            document_new.as_catalog_operation()["origin"],
            "adapter",
        )
        operations = json.loads(
            (ROOT / "src/Mod/Wasm/WasmApiOperations.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("adapters", operations)

    def test_dispatch_metadata_is_rendered_from_merged_operations(self):
        model = generate_wasm_api.build_model(
            ROOT,
            [
                ROOT / "src/Base/Vector.pyi",
                ROOT / "src/App/Document.pyi",
                ROOT / "src/App/DocumentObject.pyi",
                ROOT / "src/Mod/Part/App/TopoShape.pyi",
            ],
        )
        metadata = generate_wasm_api.render_dispatch_metadata(model)
        self.assertIn("OperationMetadataTable", metadata)
        self.assertIn(
            'Abi::Operation::DocumentOpenTransaction, 16U',
            metadata,
        )
        self.assertIn("WireType::Vector3F64", metadata)
        self.assertIn('"projection"', metadata)
        self.assertIn('"adapter"', metadata)
        self.assertIn("std::span<const ParameterMetadata> parameters", metadata)
        self.assertIn("WireType returnType", metadata)

    def test_projection_uses_the_canonical_api_model(self):
        model = generate_wasm_api.build_model(
            ROOT,
            [
                ROOT / "src/Base/Vector.pyi",
                ROOT / "src/App/Document.pyi",
                ROOT / "src/App/DocumentObject.pyi",
                ROOT / "src/Mod/Part/App/TopoShape.pyi",
            ],
        )
        top_shape = next(item for item in model["classes"] if item["name"] == "TopoShape")
        faces = next(item for item in top_shape["attributes"] if item["name"] == "Faces")
        self.assertEqual(faces["type"]["kind"], "list")
        self.assertFalse(faces["exposed"])

        fuse = next(item for item in top_shape["methods"] if item["name"] == "fuse")
        tools = fuse["signatures"][0]["params"][0]["type"]
        self.assertTrue(tools["variadic"])
        self.assertEqual(tools["item"]["type"], "Part.TopoShape")

        document = next(item for item in model["classes"] if item["name"] == "Document")
        save_as = next(item for item in document["methods"] if item["name"] == "saveAs")
        self.assertFalse(save_as["signatures"][0]["exposed"])

        document_object = next(
            item for item in model["classes"] if item["name"] == "DocumentObject"
        )
        label = next(item for item in document_object["attributes"] if item["name"] == "Label")
        self.assertEqual(label["annotation"], "str")
        self.assertEqual(label["type"]["kind"], "string")

        extension = model["extension_api"]
        self.assertEqual(extension["namespace"], "org.freecad")
        self.assertEqual(
            {
                operation["id"]
                for interface in extension["interfaces"]
                for operation in interface["operations"]
            },
            {
                "org.freecad.document@1/is_saved",
                "org.freecad.document@1/get_object",
                "org.freecad.document@1/open_transaction",
                "org.freecad.document@1/commit_transaction",
                "org.freecad.document@1/abort_transaction",
                "org.freecad.document@1/object_get_label",
                "org.freecad.document@1/object_set_label",
                "org.freecad.geometry@1/vector_add",
                "org.freecad.geometry@1/vector_dot",
                "org.freecad.geometry@1/vector_cross",
                "org.freecad.part@1/shape_is_null",
                "org.freecad.part@1/shape_is_valid",
                "org.freecad.part@1/shape_length",
                "org.freecad.part@1/shape_area",
                "org.freecad.part@1/shape_volume",
            },
        )

        vector_add = next(
            operation
            for interface in extension["interfaces"]
            for operation in interface["operations"]
            if operation["id"] == "org.freecad.geometry@1/vector_add"
        )
        vector_add_catalog = next(
            operation for operation in model["operations"] if operation["name"] == "vectorAdd"
        )
        self.assertEqual(
            [parameter["name"] for parameter in vector_add_catalog["params"]],
            ["left", "right"],
        )
        self.assertEqual(vector_add["params"][0]["name"], "vector2")
        self.assertEqual(vector_add["returns"]["kind"], "value")

        shape_area = next(
            operation
            for interface in extension["interfaces"]
            for operation in interface["operations"]
            if operation["id"] == "org.freecad.part@1/shape_area"
        )
        self.assertEqual(shape_area["returns"]["kind"], "float64")
        shape_area_catalog = next(
            operation for operation in model["operations"] if operation["name"] == "topoShapeArea"
        )
        self.assertEqual(shape_area_catalog["params"][0]["name"], "shape")

        label_set = next(
            operation
            for interface in extension["interfaces"]
            for operation in interface["operations"]
            if operation["id"] == "org.freecad.document@1/object_set_label"
        )
        self.assertEqual(label_set["property_access"], "write")
        self.assertEqual(label_set["params"][0]["name"], "label")
        self.assertEqual(label_set["params"][0]["type"]["kind"], "string")
        label_set_catalog = next(
            operation
            for operation in model["operations"]
            if operation["name"] == "documentObjectSetLabel"
        )
        self.assertEqual(label_set_catalog["property_access"], "write")
        self.assertEqual(label_set_catalog["returns"]["kind"], "bool")
        self.assertEqual(label_set_catalog["params"][-1]["name"], "label")
        self.assertEqual(label_set_catalog["params"][-1]["annotation"], "str")

        transaction_catalog = next(
            operation
            for operation in model["operations"]
            if operation["name"] == "documentOpenTransaction"
        )
        self.assertEqual(transaction_catalog["source"], "FreeCAD.Document.openTransaction")
        self.assertEqual(transaction_catalog["origin"], "projection")
        self.assertEqual(transaction_catalog["returns"]["kind"], "bool")


if __name__ == "__main__":
    unittest.main()
