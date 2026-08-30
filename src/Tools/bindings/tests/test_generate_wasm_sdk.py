# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import generate_wasm_api  # noqa: E402
import generate_wasm_sdk  # noqa: E402


ROOT = TOOLS_DIR.parents[2]


class GenerateWasmSdkTests(unittest.TestCase):
    def test_rust_and_cpp_outputs_share_api_version_and_types(self):
        model = generate_wasm_api.build_model(
            ROOT,
            [
                ROOT / "src/Base/Vector.pyi",
                ROOT / "src/App/Document.pyi",
                ROOT / "src/App/DocumentObject.pyi",
                ROOT / "src/Mod/Part/App/TopoShape.pyi",
            ],
        )
        cpp = generate_wasm_sdk.render_cpp(model)
        rust = generate_wasm_sdk.render_rust(model)
        python = generate_wasm_sdk.render_python(model)
        catalog_signature = model["abi"]["catalog_signature"]

        self.assertIn('ApiVersion[] = "org.freecad.wasm.api@0"', cpp)
        self.assertIn(f'ApiCatalogSignature[] = "{catalog_signature}"', cpp)
        self.assertIn('API_VERSION: &str = "org.freecad.wasm.api@0"', rust)
        self.assertIn(f'API_CATALOG_SIGNATURE: &str = "{catalog_signature}"', rust)
        self.assertIn('API_VERSION = "org.freecad.wasm.api@0"', python)
        self.assertIn(f'API_CATALOG_SIGNATURE = "{catalog_signature}"', python)
        self.assertIn("FreeCADBaseVectorValue", cpp)
        self.assertIn("FreeCADBaseVectorValue", rust)
        self.assertIn("FreeCADDocumentHandle", cpp)
        self.assertIn("FreeCADDocumentHandle", rust)
        self.assertIn("class Client", cpp)
        self.assertIn("class OwnedHandle", cpp)
        self.assertIn("documentIsSavedResult", cpp)
        self.assertIn("bool documentNew", cpp)
        self.assertIn("bool documentIsSaved", cpp)
        self.assertIn("bool documentGetObject", cpp)
        self.assertIn("bool documentOpenTransaction", cpp)
        self.assertIn("bool documentCommitTransaction", cpp)
        self.assertIn("bool documentObjectGetLabel", cpp)
        self.assertIn("bool documentObjectSetLabel", cpp)
        self.assertIn("bool partMakeBox", cpp)
        self.assertIn("bool vectorAdd", cpp)
        self.assertIn("bool vectorDot", cpp)
        self.assertIn("bool topoShapeArea", cpp)
        self.assertIn('documentNewPermission[] = "document.create"', cpp)
        self.assertIn('documentIsSavedPermission[] = "document.read"', cpp)
        self.assertIn("pub const DOCUMENT_NEW: u8 = 1", rust)
        self.assertIn("pub const VECTOR_DOT: u8 = 7", rust)
        self.assertIn("pub const TOPO_SHAPE_AREA: u8 = 14", rust)
        self.assertIn("pub struct Client", rust)
        self.assertIn("class Client:", python)
        self.assertIn("class OwnedHandle:", python)
        self.assertIn("class WasmHostError", python)
        self.assertIn("def document_new(self, name: str) -> FreeCADDocumentHandle:", python)
        self.assertIn(
            "def document_object_get_label(self, object: FreeCADDocumentObjectHandle)",
            python,
        )
        self.assertIn("DOCUMENT_OPEN_TRANSACTION_PERMISSION = \"document.modify\"", python)
        self.assertIn(
            "pub fn document_new(&self, name: &[u8]) -> Result<FreeCADDocumentHandle>",
            rust,
        )
        self.assertIn("pub struct Error", rust)
        self.assertIn("pub fn own(&self, value: Handle) -> OwnedHandle", rust)
        self.assertIn(
            "pub fn document_get_object(&self, document: FreeCADDocumentHandle, name: &[u8]) -> Result<FreeCADDocumentObjectHandle>",
            rust,
        )
        self.assertIn(
            "pub fn topo_shape_area(&self, shape: PartTopoShapeHandle) -> Result<f64>",
            rust,
        )
        self.assertIn(
            "pub fn document_object_get_label(&self, object: FreeCADDocumentObjectHandle, output: &mut [u8]) -> Result<usize>",
            rust,
        )
        self.assertIn("freecad_dispatch", rust)

    def test_outputs_are_stable_for_a_model(self):
        model = {
            "api": "org.freecad.wasm.api@0",
            "classes": [{"full_name": "Part.TopoShape"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            api_path = Path(directory) / "api.json"
            cpp_path = Path(directory) / "freecad_wasm_api.hpp"
            rust_path = Path(directory) / "freecad_wasm_api.rs"
            python_path = Path(directory) / "freecad_wasm_api.py"
            api_path.write_text(json.dumps(model), encoding="utf-8")
            cpp_path.write_text(generate_wasm_sdk.render_cpp(model), encoding="utf-8")
            rust_path.write_text(generate_wasm_sdk.render_rust(model), encoding="utf-8")
            python_path.write_text(generate_wasm_sdk.render_python(model), encoding="utf-8")

            self.assertEqual(
                cpp_path.read_text(encoding="utf-8").count("struct PartTopoShapeHandle"), 1
            )
            self.assertEqual(
                rust_path.read_text(encoding="utf-8").count("pub struct PartTopoShapeHandle"), 1
            )
            compile(python_path.read_text(encoding="utf-8"), str(python_path), "exec")

    def test_operations_follow_selected_api_inputs(self):
        model = generate_wasm_api.build_model(
            ROOT,
            [ROOT / "src/Base/Vector.pyi", ROOT / "src/App/Document.pyi"],
        )
        operation_names = {operation["name"] for operation in model["operations"]}
        self.assertEqual(
            operation_names,
            {
                "documentNew",
                "documentIsSaved",
                "documentGetObject",
                "documentOpenTransaction",
                "documentCommitTransaction",
                "documentAbortTransaction",
                "vectorNew",
                "vectorAdd",
                "vectorDot",
                "vectorCross",
                "release",
            },
        )


if __name__ == "__main__":
    unittest.main()
