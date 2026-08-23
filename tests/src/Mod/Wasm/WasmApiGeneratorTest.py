# SPDX-License-Identifier: LGPL-2.1-or-later

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
GENERATOR = ROOT / "src/Tools/bindings/generate_wasm_api.py"
INPUTS = [
    ROOT / "src/Base/Vector.pyi",
    ROOT / "src/App/Document.pyi",
    ROOT / "src/Mod/Part/App/TopoShape.pyi",
]


def find_class(model, name):
    return next(item for item in model["classes"] if item["name"] == name)


def find_attribute(class_model, name):
    return next(item for item in class_model["attributes"] if item["name"] == name)


def find_method(class_model, name):
    return next(item for item in class_model["methods"] if item["name"] == name)


with tempfile.TemporaryDirectory(prefix="freecad-wasm-api-") as temporary_directory:
    output = Path(temporary_directory) / "api.json"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(output), *(str(path) for path in INPUTS)],
        check=True,
    )
    model = json.loads(output.read_text(encoding="utf-8"))

assert model["schema"] == "org.freecad.wasm.api"
assert model["api"] == "org.freecad.wasm.api@0"
assert model["permission_policy"] == "deny-by-default"

topo_shape = find_class(model, "TopoShape")
for attribute_name in ("Faces", "Edges"):
    attribute_type = find_attribute(topo_shape, attribute_name)["type"]
    assert attribute_type["kind"] == "list"
    assert attribute_type["item"]["kind"] == "value"

fuse = find_method(topo_shape, "fuse")["signatures"][0]
tools = fuse["params"][0]["type"]
assert tools["kind"] == "tuple"
assert tools["variadic"] is True
assert tools["item"] == {
    "kind": "handle",
    "type": "Part.TopoShape",
    "annotation": "TopoShape",
}

document = find_class(model, "Document")
save_as = find_method(document, "saveAs")["signatures"][0]
assert save_as["exposed"] is False
assert save_as["permission"] is None

print("Wasm API generator regression test passed")
