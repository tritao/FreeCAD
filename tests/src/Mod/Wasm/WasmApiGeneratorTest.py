# SPDX-License-Identifier: LGPL-2.1-or-later

import json
import re
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
assert model["abi"]["catalog_signature"].startswith("sha256:")
assert len(model["abi"]["catalog_signature"]) == len("sha256:") + 64
assert model["abi"]["response_magic"] == "FCWR"
assert model["abi"]["error_codes"]["permission_denied"] == 2
operations = {operation["name"]: operation for operation in model["operations"]}
assert operations["documentNew"]["permission"] == "document.create"
assert operations["partMakeBox"]["id"] == 2
assert operations["documentAddObject"]["mutates"] is True
assert operations["documentAddObject"]["transaction"] == "required"
assert operations["documentAddObject"]["source"] == "FreeCAD.Document.addObject"
assert operations["vectorDot"]["source"] == "FreeCAD.Base.Vector.dot"
assert operations["documentIsSaved"]["permission"] == "document.read"
assert operations["topoShapeArea"]["source"] == "Part.TopoShape.Area"
assert operations["documentOpenTransaction"]["permission"] == "document.modify"
assert operations["documentOpenTransaction"]["transaction"] == "open"
assert operations["documentOpenTransaction"]["source"] == "FreeCAD.Document.openTransaction"
assert operations["documentOpenTransaction"]["origin"] == "projection"
assert operations["documentOpenTransaction"]["returns"]["kind"] == "bool"
assert operations["documentCommitTransaction"]["transaction"] == "commit"
assert operations["documentAbortTransaction"]["transaction"] == "abort"
assert operations["documentObjectGetLabel"]["source"] == "FreeCAD.DocumentObject.Label"
assert operations["documentObjectSetLabel"]["transaction"] == "required"
assert operations["documentNew"]["returns"]["ownership"] == "owned"
assert operations["documentNew"]["origin"] == "adapter"
assert operations["documentNew"]["returns"]["nullable"] is False
assert operations["documentNew"]["fallible"] is True

extension = model["extension_api"]
assert extension["namespace"] == "org.freecad"
extension_operations = {
    operation["id"]: operation
    for interface in extension["interfaces"]
    for operation in interface["operations"]
}
assert extension_operations["org.freecad.document@1/is_saved"]["source"] == "FreeCAD.Document.isSaved"
assert extension_operations["org.freecad.geometry@1/vector_dot"]["returns"]["kind"] == "float64"
assert extension_operations["org.freecad.part@1/shape_is_valid"]["permission"] == "geometry.read"
assert extension_operations["org.freecad.document@1/object_get_label"]["property_access"] == "read"
assert extension_operations["org.freecad.document@1/object_set_label"]["property_access"] == "write"

abi_header = (ROOT / "src/Mod/Wasm/WasmAbi.h").read_text(encoding="utf-8")
abi_enum = re.search(
    r"enum class Operation : std::uint8_t\s*\{(?P<body>.*?)\};",
    abi_header,
    re.DOTALL,
)
assert abi_enum is not None
abi_operations = {
    name: int(operation_id)
    for name, operation_id in re.findall(
        r"^\s*(\w+)\s*=\s*(\d+),", abi_enum.group("body"), re.MULTILINE
    )
}
host_source = (ROOT / "src/Mod/Wasm/App/WasmHostApi.cpp").read_text(encoding="utf-8")
known_permissions = set(
    re.findall(
        r'"([^"\n]+)"',
        (ROOT / "src/Mod/Wasm/App/WasmPermissions.h").read_text(encoding="utf-8"),
    )
)


def operation_enum_name(operation_name):
    return (
        "HandleRelease"
        if operation_name == "release"
        else operation_name[0].upper() + operation_name[1:]
    )


assert set(abi_operations) == {
    operation_enum_name(operation["name"]) for operation in model["operations"]
}
for operation in model["operations"]:
    enum_name = operation_enum_name(operation["name"])
    assert abi_operations[enum_name] == operation["id"]
    assert f"case Abi::Operation::{enum_name}:" in host_source
    permission = operation["permission"]
    if permission is not None:
        assert permission in known_permissions

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
