# SPDX-License-Identifier: LGPL-2.1-or-later

if(NOT DEFINED INPUT OR NOT DEFINED OUTPUT OR NOT DEFINED ABI_HASH_FILE)
    message(FATAL_ERROR
        "ConfigureWasmManifest.cmake requires INPUT, OUTPUT, and ABI_HASH_FILE")
endif()

file(READ "${INPUT}" _freecad_wasm_manifest)
file(READ "${ABI_HASH_FILE}" _freecad_wasm_abi_hash)
string(STRIP "${_freecad_wasm_abi_hash}" _freecad_wasm_abi_hash)

string(LENGTH "${_freecad_wasm_abi_hash}" _freecad_wasm_abi_hash_length)
if(NOT _freecad_wasm_abi_hash_length EQUAL 71
   OR NOT _freecad_wasm_abi_hash MATCHES "^sha256:[0-9a-f]+$")
    message(FATAL_ERROR "invalid FreeCAD Wasm ABI hash: ${_freecad_wasm_abi_hash}")
endif()

if(NOT _freecad_wasm_manifest MATCHES "@FREECAD_WASM_ABI_HASH@")
    message(FATAL_ERROR
        "manifest must contain the @FREECAD_WASM_ABI_HASH@ placeholder")
endif()

string(REPLACE "@FREECAD_WASM_ABI_HASH@"
    "${_freecad_wasm_abi_hash}"
    _freecad_wasm_manifest
    "${_freecad_wasm_manifest}")

file(WRITE "${OUTPUT}" "${_freecad_wasm_manifest}")
