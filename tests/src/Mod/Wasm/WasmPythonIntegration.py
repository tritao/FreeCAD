# SPDX-License-Identifier: LGPL-2.1-or-later

import json
import os
import shutil
import tempfile
from pathlib import Path

import FreeCAD
import Wasm


def require(condition, message):
    if not condition:
        raise AssertionError(message)


fixture = Path(os.environ["FREECAD_WASM_CAPABILITY_FIXTURE"])
require(fixture.is_file(), f"missing Wasm fixture: {fixture}")

runtime_info = Wasm.getRuntimeInfo()
require(runtime_info["available"], "WAMR is not available")
require(runtime_info["supports_sandbox"], "WAMR sandbox support is unavailable")
require(Wasm.listAddons() == [], "Wasm addon manager must start empty")

with tempfile.TemporaryDirectory(prefix="freecad-wasm-python-") as temporary_directory:
    addon_directory = Path(temporary_directory)
    shutil.copyfile(fixture, addon_directory / "capability.wasm")
    manifest_path = addon_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "PythonCapability",
                "api": "org.freecad.wasm.api@0",
                "abi_hash": runtime_info["api_catalog_signature"],
                "entry": "capability.wasm",
                "permissions": [
                    "document.create",
                    "document.modify",
                    "geometry.create",
                ],
            }
        ),
        encoding="utf-8",
    )

    denied_metadata = Wasm.loadAddon(str(manifest_path), [])
    require(denied_metadata["name"] == "PythonCapability", "denied addon metadata is incorrect")
    try:
        Wasm.invokeAddon("PythonCapability")
    except RuntimeError as error:
        require("document.create" in str(error), "denied capability error is incomplete")
    else:
        raise AssertionError("permission-denied addon invocation unexpectedly succeeded")
    require(Wasm.unloadAddon("PythonCapability"), "denied addon did not unload")

    metadata = Wasm.loadAddon(
        str(manifest_path),
        ["document.create", "document.modify", "geometry.create"],
    )
    require(metadata == denied_metadata, "load metadata changed between policy checks")
    require(Wasm.listAddons() == ["PythonCapability"], "loaded addon was not listed")
    require(Wasm.invokeAddon("PythonCapability") == b"OK", "addon response was not OK")

    document = FreeCAD.getDocument("GuestCapabilityExample")
    require(document is not None, "guest did not create its document")
    feature = document.getObject("Box")
    require(feature is not None, "guest did not create its feature")
    require(feature.Shape.Volume > 0, "guest feature has no solid shape")

    require(Wasm.unloadAddon("PythonCapability"), "granted addon did not unload")
    FreeCAD.closeDocument("GuestCapabilityExample")
    require(Wasm.listAddons() == [], "addon manager was not empty after unload")

print("Wasm Python integration passed")
