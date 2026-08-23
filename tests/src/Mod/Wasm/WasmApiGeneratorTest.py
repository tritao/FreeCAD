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
    ROOT / "src/App/DocumentObject.pyi",
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
operations = {operation["name"]: operation for operation in model["operations"]}
assert operations["documentNew"]["permission"] == "document.create"
assert operations["partMakeBox"]["id"] == 2
assert operations["documentAddObject"]["mutates"] is True
assert operations["documentAddObject"]["source"] == "FreeCAD.Document.addObject"
assert operations["vectorDot"]["source"] == "FreeCAD.Base.Vector.dot"
assert operations["documentIsSaved"]["permission"] == "document.read"
assert operations["topoShapeArea"]["source"] == "Part.TopoShape.Area"
assert operations["documentOpenTransaction"]["permission"] == "document.modify"
assert operations["documentObjectGetLabel"]["source"] == "FreeCAD.DocumentObject"

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

vector = find_class(model, "Vector")
assert vector["representation"] == {"kind": "value", "encoding": "vector3-f64"}
vector_add = find_method(vector, "add")["signatures"][0]
assert vector_add["params"][0]["type"] == {
    "kind": "value",
    "annotation": "'Vector'",
    "type": "FreeCAD.Base.Vector",
    "encoding": "vector3-f64",
}

print("Wasm API generator regression test passed")
