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
                ROOT / "src/Mod/Part/App/TopoShape.pyi",
            ],
        )
        cpp = generate_wasm_sdk.render_cpp(model)
        rust = generate_wasm_sdk.render_rust(model)

        self.assertIn('ApiVersion[] = "org.freecad.wasm.api@0"', cpp)
        self.assertIn('API_VERSION: &str = "org.freecad.wasm.api@0"', rust)
        self.assertIn("FreeCADBaseVectorValue", cpp)
        self.assertIn("FreeCADBaseVectorValue", rust)
        self.assertIn("FreeCADDocumentHandle", cpp)
        self.assertIn("FreeCADDocumentHandle", rust)
        self.assertIn("class Host", cpp)
        self.assertIn("bool documentNew", cpp)
        self.assertIn("bool partMakeBox", cpp)
        self.assertIn("bool vectorAdd", cpp)
        self.assertIn("bool vectorDot", cpp)
        self.assertIn('documentNewPermission[] = "document.create"', cpp)
        self.assertIn("pub const DOCUMENT_NEW: u8 = 1", rust)
        self.assertIn("pub const VECTOR_DOT: u8 = 7", rust)

    def test_outputs_are_stable_for_a_model(self):
        model = {
            "api": "org.freecad.wasm.api@0",
            "classes": [{"full_name": "Part.TopoShape"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            api_path = Path(directory) / "api.json"
            cpp_path = Path(directory) / "freecad_wasm_api.hpp"
            rust_path = Path(directory) / "freecad_wasm_api.rs"
            api_path.write_text(json.dumps(model), encoding="utf-8")
            cpp_path.write_text(generate_wasm_sdk.render_cpp(model), encoding="utf-8")
            rust_path.write_text(generate_wasm_sdk.render_rust(model), encoding="utf-8")

            self.assertEqual(
                cpp_path.read_text(encoding="utf-8").count("struct PartTopoShapeHandle"), 1
            )
            self.assertEqual(
                rust_path.read_text(encoding="utf-8").count("pub struct PartTopoShapeHandle"), 1
            )

    def test_operations_follow_selected_api_inputs(self):
        model = generate_wasm_api.build_model(
            ROOT,
            [ROOT / "src/Base/Vector.pyi", ROOT / "src/App/Document.pyi"],
        )
        operation_names = {operation["name"] for operation in model["operations"]}
        self.assertEqual(
            operation_names,
            {"documentNew", "vectorNew", "vectorAdd", "vectorDot", "vectorCross", "release"},
        )


if __name__ == "__main__":
    unittest.main()
