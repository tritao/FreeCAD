# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import sys
from pathlib import Path
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parents[1]
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(TOOLS_DIR / "typing"))

from extension_api_model import load_extension_namespace, project_api_model  # noqa: E402
from stubgen.api_extract import extract_curated_api_model_with_diagnostics  # noqa: E402


INPUTS = [
    ROOT / "src/Base/Vector.pyi",
    ROOT / "src/App/Document.pyi",
    ROOT / "src/App/DocumentObject.pyi",
    ROOT / "src/Mod/Part/App/TopoShape.pyi",
]


class ExtensionProjectTests(unittest.TestCase):
    def model(self):
        model, diagnostics = extract_curated_api_model_with_diagnostics(
            ROOT,
            ROOT / "src",
            source_paths=INPUTS,
        )
        self.assertFalse([item for item in diagnostics if item.severity.value == "error"])
        return model

    def test_projects_scoped_operation_ids(self) -> None:
        extension = project_api_model(
            self.model(),
            namespace=load_extension_namespace(ROOT / "src/Mod/Wasm/WasmExtensionApi.json"),
        )
        operations = {item.stable_id: item for item in extension.operations}
        self.assertEqual(
            set(operations),
            {
                "org.freecad.document@1/abort_transaction",
                "org.freecad.document@1/commit_transaction",
                "org.freecad.document@1/get_object",
                "org.freecad.document@1/is_saved",
                "org.freecad.document@1/open_transaction",
                "org.freecad.geometry@1/vector_add",
                "org.freecad.geometry@1/vector_cross",
                "org.freecad.geometry@1/vector_dot",
                "org.freecad.part@1/shape_is_null",
                "org.freecad.part@1/shape_is_valid",
            },
        )
        is_saved = operations["org.freecad.document@1/is_saved"]
        self.assertEqual(is_saved.receiver, "FreeCAD.Document")
        self.assertEqual(is_saved.parameters, ())
        self.assertEqual(is_saved.returns.annotation, "bool")
        self.assertEqual(is_saved.permission, "document.read")
        self.assertEqual(extension.type_representations["FreeCAD.Base.Vector"].value, "value")

    def test_namespace_manifest_is_validated(self) -> None:
        self.assertEqual(
            load_extension_namespace(ROOT / "src/Mod/Wasm/WasmExtensionApi.json"),
            "org.freecad",
        )


if __name__ == "__main__":
    unittest.main()
