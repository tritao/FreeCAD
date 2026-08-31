# SPDX-License-Identifier: LGPL-2.1-or-later

cmake_minimum_required(VERSION 3.16)
project(FreeCADWasmCppAddon LANGUAGES NONE)

get_filename_component(
    _freecad_source_dir
    "${CMAKE_CURRENT_LIST_DIR}/../../.."
    ABSOLUTE
)
option(FREECAD_WASM_USE_INSTALLED_SDK
    "Build against an installed FreeCAD Wasm guest SDK" OFF)

if(FREECAD_WASM_USE_INSTALLED_SDK)
    find_package(FreeCADWasmGuest CONFIG REQUIRED)
    set(_freecad_wasm_guest_cmake
        "${FreeCADWasmGuest_CMAKE_MODULE}")
    set(_freecad_wasm_guest_include_root
        "${FreeCADWasmGuest_INCLUDE_DIR}")
    set(_freecad_wasm_guest_api_signature
        "${FreeCADWasmGuest_API_SIGNATURE_FILE}")
else()
    set(FREECAD_SOURCE_DIR "${_freecad_source_dir}" CACHE PATH
        "FreeCAD source tree containing the Wasm guest SDK")
    set(_freecad_wasm_guest_cmake
        "${FREECAD_SOURCE_DIR}/src/Mod/Wasm/Guest/FreeCADWasmGuest.cmake")
    set(_freecad_wasm_guest_include_root
        "${FREECAD_SOURCE_DIR}/src/Mod")
endif()

if(NOT EXISTS "${_freecad_wasm_guest_cmake}")
    message(FATAL_ERROR
        "FreeCAD Wasm guest helper was not found: ${_freecad_wasm_guest_cmake}")
endif()

include("${_freecad_wasm_guest_cmake}")

set(_freecad_wasm_guest_api_dependencies)
set(_freecad_wasm_guest_api_include_dirs)
if(FREECAD_WASM_USE_INSTALLED_SDK)
    list(APPEND _freecad_wasm_guest_api_dependencies
        "${_freecad_wasm_guest_include_root}/Wasm/Guest/freecad_wasm_api.hpp"
    )
else()
    find_package(Python3 COMPONENTS Interpreter REQUIRED)
    set(_freecad_wasm_api_inputs
        "${FREECAD_SOURCE_DIR}/src/Base/Vector.pyi"
        "${FREECAD_SOURCE_DIR}/src/App/Document.pyi"
        "${FREECAD_SOURCE_DIR}/src/App/DocumentObject.pyi"
        "${FREECAD_SOURCE_DIR}/src/Mod/Part/App/TopoShape.pyi"
    )
    set(_freecad_wasm_guest_api_dir
        "${CMAKE_CURRENT_BINARY_DIR}/generated")
    freecad_wasm_generate_guest_sdk(FreeCADCapabilityAddonApi
        OUTPUT_DIR "${_freecad_wasm_guest_api_dir}"
        PYTHON_EXECUTABLE "${Python3_EXECUTABLE}"
        API_GENERATOR
            "${FREECAD_SOURCE_DIR}/src/Tools/bindings/generate_wasm_api.py"
        SDK_GENERATOR
            "${FREECAD_SOURCE_DIR}/src/Tools/bindings/generate_wasm_sdk.py"
        API_SIGNATURE_VARIABLE _freecad_wasm_guest_api_signature
        INPUTS ${_freecad_wasm_api_inputs}
        DEPENDS
            "${FREECAD_SOURCE_DIR}/src/Mod/Wasm/wasm_abi.lock.toml"
            "${FREECAD_SOURCE_DIR}/src/Tools/wasm_api_model/__init__.py"
            "${FREECAD_SOURCE_DIR}/src/Tools/wasm_api_model/adapters.py"
            "${FREECAD_SOURCE_DIR}/src/Tools/wasm_api_model/lock.py"
            "${FREECAD_SOURCE_DIR}/src/Tools/wasm_api_model/model.py"
            "${FREECAD_SOURCE_DIR}/src/Tools/wasm_api_model/types.py"
    )
    list(APPEND _freecad_wasm_guest_api_include_dirs
        "${_freecad_wasm_guest_api_dir}")
    list(APPEND _freecad_wasm_guest_api_dependencies
        "${_freecad_wasm_guest_api_dir}/Wasm/Guest/freecad_wasm_api.hpp")
endif()

freecad_wasm_addon(FreeCADCapabilityAddon
    ALL
    FREESTANDING
    SOURCE "${CMAKE_CURRENT_LIST_DIR}/CapabilityAddon.cpp"
    INCLUDE_ROOT "${_freecad_wasm_guest_include_root}"
    INCLUDE_DIRS ${_freecad_wasm_guest_api_include_dirs}
    OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/freecad-capability-addon.wasm"
    MANIFEST "${CMAKE_CURRENT_LIST_DIR}/manifest.json"
    MANIFEST_OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/manifest.json"
    MANIFEST_ABI_HASH_FILE "${_freecad_wasm_guest_api_signature}"
    BUNDLE_TARGET_VARIABLE _freecad_wasm_bundle_target
    DEPENDS
        "${CMAKE_CURRENT_LIST_DIR}/manifest.json"
        ${_freecad_wasm_guest_api_dependencies}
        "${_freecad_wasm_guest_include_root}/Wasm/WasmAbi.h"
        "${_freecad_wasm_guest_include_root}/Wasm/Guest/WasmGuest.h"
        "${_freecad_wasm_guest_include_root}/Wasm/Guest/WasmGuestFreestanding.h"
)

if(TARGET FreeCADCapabilityAddonApi)
    add_dependencies(FreeCADCapabilityAddon FreeCADCapabilityAddonApi)
endif()
