# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import generate_wasm_api  # noqa: E402
from python_api_model.types import parse_annotation  # noqa: E402


ROOT = TOOLS_DIR.parents[2]


def model_for(annotation: str) -> dict:
    return generate_wasm_api._wasm_type(
        parse_annotation(annotation, "Part"),
        annotation,
        "Part",
    )


class GenerateWasmApiTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
