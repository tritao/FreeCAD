# SPDX-License-Identifier: LGPL-2.1-or-later

include_guard(GLOBAL)

set(_FREECAD_WASM_GUEST_MODULE_DIR "${CMAKE_CURRENT_LIST_DIR}")
if(FREECAD_WASM_GUEST_INCLUDE_ROOT)
    set(_FREECAD_WASM_GUEST_DEFAULT_INCLUDE_ROOT
        "${FREECAD_WASM_GUEST_INCLUDE_ROOT}")
else()
    get_filename_component(
        _FREECAD_WASM_GUEST_DEFAULT_INCLUDE_ROOT
        "${_FREECAD_WASM_GUEST_MODULE_DIR}/../.."
        ABSOLUTE
    )
endif()

function(freecad_wasm_generate_guest_sdk target)
    set(_one_value_args
        OUTPUT_DIR PYTHON_EXECUTABLE API_GENERATOR SDK_GENERATOR
        API_MODEL_VARIABLE API_CPP_VARIABLE API_RUST_VARIABLE API_PYTHON_VARIABLE
        API_SIGNATURE_VARIABLE
    )
    set(_multi_value_args INPUTS DEPENDS)
    cmake_parse_arguments(
        _FREECAD_WASM_SDK
        ""
        "${_one_value_args}"
        "${_multi_value_args}"
        ${ARGN}
    )

    foreach(_required OUTPUT_DIR PYTHON_EXECUTABLE API_GENERATOR SDK_GENERATOR)
        if(NOT _FREECAD_WASM_SDK_${_required})
            message(FATAL_ERROR
                "freecad_wasm_generate_guest_sdk(${target}) requires ${_required}")
        endif()
    endforeach()
    if(NOT _FREECAD_WASM_SDK_INPUTS)
        message(FATAL_ERROR
            "freecad_wasm_generate_guest_sdk(${target}) requires INPUTS")
    endif()

    set(_FREECAD_WASM_SDK_MODEL
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/freecad_wasm_api.json")
    set(_FREECAD_WASM_SDK_SIGNATURE
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/freecad_wasm_api.signature")
    set(_FREECAD_WASM_SDK_CPP
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest/freecad_wasm_api.hpp")
    set(_FREECAD_WASM_SDK_RUST
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest/freecad_wasm_api.rs")
    set(_FREECAD_WASM_SDK_PYTHON
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest/freecad_wasm_api.py")

    add_custom_command(
        OUTPUT
            "${_FREECAD_WASM_SDK_MODEL}"
            "${_FREECAD_WASM_SDK_SIGNATURE}"
            "${_FREECAD_WASM_SDK_CPP}"
            "${_FREECAD_WASM_SDK_RUST}"
            "${_FREECAD_WASM_SDK_PYTHON}"
        COMMAND ${CMAKE_COMMAND} -E make_directory
                "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest"
        COMMAND ${_FREECAD_WASM_SDK_PYTHON_EXECUTABLE}
                "${_FREECAD_WASM_SDK_API_GENERATOR}"
                --output "${_FREECAD_WASM_SDK_MODEL}"
                --catalog-signature-output "${_FREECAD_WASM_SDK_SIGNATURE}"
                ${_FREECAD_WASM_SDK_INPUTS}
        COMMAND ${_FREECAD_WASM_SDK_PYTHON_EXECUTABLE}
                "${_FREECAD_WASM_SDK_SDK_GENERATOR}"
                --api-json "${_FREECAD_WASM_SDK_MODEL}"
                --cpp-output "${_FREECAD_WASM_SDK_CPP}"
                --rust-output "${_FREECAD_WASM_SDK_RUST}"
                --python-output "${_FREECAD_WASM_SDK_PYTHON}"
        DEPENDS
            "${_FREECAD_WASM_SDK_API_GENERATOR}"
            "${_FREECAD_WASM_SDK_SDK_GENERATOR}"
            ${_FREECAD_WASM_SDK_INPUTS}
            ${_FREECAD_WASM_SDK_DEPENDS}
        COMMENT "Generating the FreeCAD Wasm guest SDK for ${target}"
        VERBATIM
    )
    add_custom_target(${target}
        DEPENDS
            "${_FREECAD_WASM_SDK_MODEL}"
            "${_FREECAD_WASM_SDK_SIGNATURE}"
            "${_FREECAD_WASM_SDK_CPP}"
            "${_FREECAD_WASM_SDK_RUST}"
            "${_FREECAD_WASM_SDK_PYTHON}"
    )

    if(_FREECAD_WASM_SDK_API_MODEL_VARIABLE)
        set(${_FREECAD_WASM_SDK_API_MODEL_VARIABLE}
            "${_FREECAD_WASM_SDK_MODEL}" PARENT_SCOPE)
    endif()
    if(_FREECAD_WASM_SDK_API_CPP_VARIABLE)
        set(${_FREECAD_WASM_SDK_API_CPP_VARIABLE}
            "${_FREECAD_WASM_SDK_CPP}" PARENT_SCOPE)
    endif()
    if(_FREECAD_WASM_SDK_API_RUST_VARIABLE)
        set(${_FREECAD_WASM_SDK_API_RUST_VARIABLE}
            "${_FREECAD_WASM_SDK_RUST}" PARENT_SCOPE)
    endif()
    if(_FREECAD_WASM_SDK_API_PYTHON_VARIABLE)
        set(${_FREECAD_WASM_SDK_API_PYTHON_VARIABLE}
            "${_FREECAD_WASM_SDK_PYTHON}" PARENT_SCOPE)
    endif()
    if(_FREECAD_WASM_SDK_API_SIGNATURE_VARIABLE)
        set(${_FREECAD_WASM_SDK_API_SIGNATURE_VARIABLE}
            "${_FREECAD_WASM_SDK_SIGNATURE}" PARENT_SCOPE)
    endif()
endfunction()

function(freecad_wasm_addon target)
    set(_options ALL FREESTANDING OPTIONAL)
    set(_one_value_args
        SOURCE OUTPUT INCLUDE_ROOT OUTPUT_VARIABLE MANIFEST MANIFEST_OUTPUT
        BUNDLE_TARGET_VARIABLE MANIFEST_ABI_HASH_FILE
    )
    set(_multi_value_args DEPENDS INCLUDE_DIRS SOURCES)
    cmake_parse_arguments(
        _FREECAD_WASM
        "${_options}"
        "${_one_value_args}"
        "${_multi_value_args}"
        ${ARGN}
    )

    if(_FREECAD_WASM_SOURCE AND _FREECAD_WASM_SOURCES)
        message(FATAL_ERROR
            "freecad_wasm_addon(${target}) accepts SOURCE or SOURCES, not both")
    endif()
    if(_FREECAD_WASM_SOURCE)
        set(_FREECAD_WASM_SOURCES "${_FREECAD_WASM_SOURCE}")
    endif()
    if(NOT _FREECAD_WASM_SOURCES)
        message(FATAL_ERROR
            "freecad_wasm_addon(${target}) requires SOURCE or SOURCES")
    endif()

    if(NOT _FREECAD_WASM_OUTPUT)
        set(_FREECAD_WASM_OUTPUT
            "${CMAKE_CURRENT_BINARY_DIR}/${target}.wasm")
    endif()

    if(NOT _FREECAD_WASM_INCLUDE_ROOT)
        set(_FREECAD_WASM_INCLUDE_ROOT
            "${_FREECAD_WASM_GUEST_DEFAULT_INCLUDE_ROOT}")
    endif()

    set(FREECAD_WASM_GUEST_COMPILER "" CACHE FILEPATH
        "Clang compiler used to build a FreeCAD Wasm guest")
    if(FREECAD_WASM_GUEST_COMPILER)
        set(_FREECAD_WASM_COMPILER "${FREECAD_WASM_GUEST_COMPILER}")
    else()
        find_program(_FREECAD_WASM_COMPILER NAMES clang++ clang)
    endif()

    set(FREECAD_WASM_GUEST_LINKER "" CACHE FILEPATH
        "wasm-ld linker used to build a FreeCAD Wasm guest")
    if(FREECAD_WASM_GUEST_LINKER)
        set(_FREECAD_WASM_LINKER "${FREECAD_WASM_GUEST_LINKER}")
    else()
        find_program(_FREECAD_WASM_LINKER NAMES wasm-ld)
    endif()

    if(NOT _FREECAD_WASM_COMPILER OR NOT _FREECAD_WASM_LINKER)
        set(_FREECAD_WASM_MESSAGE
            "FreeCAD Wasm guest compilation requires clang++ and wasm-ld")
        if(_FREECAD_WASM_OPTIONAL)
            message(WARNING "Skipping ${target}: ${_FREECAD_WASM_MESSAGE}")
            if(_FREECAD_WASM_OUTPUT_VARIABLE)
                set(${_FREECAD_WASM_OUTPUT_VARIABLE} "" PARENT_SCOPE)
            endif()
            return()
        endif()
        message(FATAL_ERROR "${_FREECAD_WASM_MESSAGE}")
    endif()

    set(_FREECAD_WASM_ALL_INCLUDE_DIRS)
    if(_FREECAD_WASM_INCLUDE_ROOT)
        list(APPEND _FREECAD_WASM_ALL_INCLUDE_DIRS
            "${_FREECAD_WASM_INCLUDE_ROOT}")
    endif()
    list(APPEND _FREECAD_WASM_ALL_INCLUDE_DIRS ${_FREECAD_WASM_INCLUDE_DIRS})

    set(_FREECAD_WASM_COMPILE_COMMAND
        "${_FREECAD_WASM_COMPILER}"
        --target=wasm32-unknown-unknown
        -std=c++20
        -O0
        -fno-exceptions
        -fno-rtti
        -nostdlib
        "-fuse-ld=${_FREECAD_WASM_LINKER}"
        -Wl,--no-entry
        -Wl,--export=freecad_addon_entry
        -Wl,--export-memory
        -Wl,--initial-memory=131072
        -Wl,--max-memory=4194304
        -o
        "${_FREECAD_WASM_OUTPUT}"
    )
    list(APPEND _FREECAD_WASM_COMPILE_COMMAND ${_FREECAD_WASM_SOURCES})
    foreach(_FREECAD_WASM_INCLUDE_DIR IN LISTS _FREECAD_WASM_ALL_INCLUDE_DIRS)
        list(INSERT _FREECAD_WASM_COMPILE_COMMAND 7
            "-I${_FREECAD_WASM_INCLUDE_DIR}"
        )
    endforeach()
    if(_FREECAD_WASM_FREESTANDING)
        list(INSERT _FREECAD_WASM_COMPILE_COMMAND 4
            -ffreestanding
            -DFREECAD_WASM_FREESTANDING=1
        )
    endif()

    add_custom_command(
        OUTPUT "${_FREECAD_WASM_OUTPUT}"
        COMMAND ${_FREECAD_WASM_COMPILE_COMMAND}
        DEPENDS
            ${_FREECAD_WASM_SOURCES}
            ${_FREECAD_WASM_DEPENDS}
        COMMENT "Building the FreeCAD Wasm guest ${target}"
        VERBATIM
    )

    if(_FREECAD_WASM_ALL)
        add_custom_target(${target} ALL
            DEPENDS "${_FREECAD_WASM_OUTPUT}"
        )
    else()
        add_custom_target(${target}
            DEPENDS "${_FREECAD_WASM_OUTPUT}"
        )
    endif()

    if(_FREECAD_WASM_OUTPUT_VARIABLE)
        set(${_FREECAD_WASM_OUTPUT_VARIABLE}
            "${_FREECAD_WASM_OUTPUT}"
            PARENT_SCOPE
        )
    endif()

    if(_FREECAD_WASM_MANIFEST)
        if(NOT _FREECAD_WASM_MANIFEST_OUTPUT)
            set(_FREECAD_WASM_MANIFEST_OUTPUT
                "${CMAKE_CURRENT_BINARY_DIR}/manifest.json")
        endif()
        if(_FREECAD_WASM_MANIFEST MATCHES "\\.toml$")
            if(NOT _FREECAD_WASM_MANIFEST_ABI_HASH_FILE)
                message(FATAL_ERROR
                    "TOML extension manifests require the generated API signature")
            endif()
            get_filename_component(
                _FREECAD_WASM_MANIFEST_ENTRY
                "${_FREECAD_WASM_OUTPUT}"
                NAME
            )
            add_custom_command(
                OUTPUT "${_FREECAD_WASM_MANIFEST_OUTPUT}"
                COMMAND ${CMAKE_COMMAND}
                        -DINPUT=${_FREECAD_WASM_MANIFEST}
                        -DOUTPUT=${_FREECAD_WASM_MANIFEST_OUTPUT}
                        -DABI_HASH_FILE=${_FREECAD_WASM_MANIFEST_ABI_HASH_FILE}
                        -DENTRY=${_FREECAD_WASM_MANIFEST_ENTRY}
                        -P "${_FREECAD_WASM_GUEST_MODULE_DIR}/GenerateExtensionManifest.cmake"
                DEPENDS
                    "${_FREECAD_WASM_MANIFEST}"
                    "${_FREECAD_WASM_MANIFEST_ABI_HASH_FILE}"
                    "${_FREECAD_WASM_GUEST_MODULE_DIR}/GenerateExtensionManifest.cmake"
                COMMENT "Generating the FreeCAD Extension manifest for ${target}"
                VERBATIM
            )
        elseif(_FREECAD_WASM_MANIFEST_ABI_HASH_FILE)
            add_custom_command(
                OUTPUT "${_FREECAD_WASM_MANIFEST_OUTPUT}"
                COMMAND ${CMAKE_COMMAND}
                        -DINPUT=${_FREECAD_WASM_MANIFEST}
                        -DOUTPUT=${_FREECAD_WASM_MANIFEST_OUTPUT}
                        -DABI_HASH_FILE=${_FREECAD_WASM_MANIFEST_ABI_HASH_FILE}
                        -P "${_FREECAD_WASM_GUEST_MODULE_DIR}/ConfigureWasmManifest.cmake"
                DEPENDS
                    "${_FREECAD_WASM_MANIFEST}"
                    "${_FREECAD_WASM_MANIFEST_ABI_HASH_FILE}"
                COMMENT "Staging the FreeCAD Wasm addon manifest for ${target}"
                VERBATIM
            )
        else()
            add_custom_command(
                OUTPUT "${_FREECAD_WASM_MANIFEST_OUTPUT}"
                COMMAND ${CMAKE_COMMAND} -E copy_if_different
                        "${_FREECAD_WASM_MANIFEST}"
                        "${_FREECAD_WASM_MANIFEST_OUTPUT}"
                DEPENDS "${_FREECAD_WASM_MANIFEST}"
                COMMENT "Staging the FreeCAD Wasm addon manifest for ${target}"
                VERBATIM
            )
        endif()

        set(_FREECAD_WASM_BUNDLE_TARGET "${target}Bundle")
        if(_FREECAD_WASM_ALL)
            add_custom_target(${_FREECAD_WASM_BUNDLE_TARGET} ALL
                DEPENDS ${target} "${_FREECAD_WASM_MANIFEST_OUTPUT}"
            )
        else()
            add_custom_target(${_FREECAD_WASM_BUNDLE_TARGET}
                DEPENDS ${target} "${_FREECAD_WASM_MANIFEST_OUTPUT}"
            )
        endif()

        if(_FREECAD_WASM_BUNDLE_TARGET_VARIABLE)
            set(${_FREECAD_WASM_BUNDLE_TARGET_VARIABLE}
                "${_FREECAD_WASM_BUNDLE_TARGET}"
                PARENT_SCOPE
            )
        endif()
    elseif(_FREECAD_WASM_BUNDLE_TARGET_VARIABLE)
        set(${_FREECAD_WASM_BUNDLE_TARGET_VARIABLE} "" PARENT_SCOPE)
    endif()
endfunction()

# Preferred extension-facing SDK generation entry point. The signature is
# kept in the caller scope so a following freecad_add_extension() can consume
# it without exposing ABI plumbing in the extension project.
macro(freecad_extension_generate_sdk target)
    freecad_wasm_generate_guest_sdk(
        ${target}
        API_SIGNATURE_VARIABLE _FREECAD_EXTENSION_SDK_API_SIGNATURE
        ${ARGN}
    )
endmacro()

function(freecad_add_extension target)
    set(_options ALL FREESTANDING OPTIONAL)
    set(_one_value_args
        OUTPUT INCLUDE_ROOT OUTPUT_VARIABLE MANIFEST_OUTPUT
        BUNDLE_TARGET_VARIABLE
    )
    set(_multi_value_args SOURCES DEPENDS INCLUDE_DIRS)
    cmake_parse_arguments(
        _FREECAD_EXTENSION
        "${_options}"
        "${_one_value_args}"
        "${_multi_value_args}"
        ${ARGN}
    )

    if(_FREECAD_EXTENSION_UNPARSED_ARGUMENTS
       OR _FREECAD_EXTENSION_KEYWORDS_MISSING_VALUES)
        message(FATAL_ERROR
            "freecad_add_extension(${target}) received invalid arguments")
    endif()

    if(NOT _FREECAD_EXTENSION_SOURCES)
        message(FATAL_ERROR
            "freecad_add_extension(${target}) requires SOURCES")
    endif()
    set(_FREECAD_EXTENSION_MANIFEST
        "${CMAKE_CURRENT_SOURCE_DIR}/freecad-extension.toml")
    if(NOT EXISTS "${_FREECAD_EXTENSION_MANIFEST}")
        message(FATAL_ERROR
            "freecad_add_extension(${target}) requires ${_FREECAD_EXTENSION_MANIFEST}")
    endif()

    if(DEFINED _FREECAD_EXTENSION_SDK_API_SIGNATURE)
        set(_FREECAD_EXTENSION_SIGNATURE
            "${_FREECAD_EXTENSION_SDK_API_SIGNATURE}")
    elseif(DEFINED FreeCADExtensionSDK_API_SIGNATURE_FILE)
        set(_FREECAD_EXTENSION_SIGNATURE
            "${FreeCADExtensionSDK_API_SIGNATURE_FILE}")
    endif()
    if(NOT _FREECAD_EXTENSION_SIGNATURE)
        message(FATAL_ERROR
            "freecad_add_extension(${target}) requires a generated Extension SDK; "
            "call freecad_extension_generate_sdk() or find_package(FreeCADExtensionSDK)")
    endif()

    set(_freecad_extension_args
        SOURCES ${_FREECAD_EXTENSION_SOURCES}
        MANIFEST "${_FREECAD_EXTENSION_MANIFEST}"
        MANIFEST_ABI_HASH_FILE "${_FREECAD_EXTENSION_SIGNATURE}"
    )
    foreach(_argument OUTPUT INCLUDE_ROOT OUTPUT_VARIABLE MANIFEST_OUTPUT
                      BUNDLE_TARGET_VARIABLE)
        if(_FREECAD_EXTENSION_${_argument})
            list(APPEND _freecad_extension_args
                ${_argument} "${_FREECAD_EXTENSION_${_argument}}")
        endif()
    endforeach()
    if(_FREECAD_EXTENSION_DEPENDS)
        list(APPEND _freecad_extension_args
            DEPENDS ${_FREECAD_EXTENSION_DEPENDS})
    endif()
    if(_FREECAD_EXTENSION_INCLUDE_DIRS)
        list(APPEND _freecad_extension_args
            INCLUDE_DIRS ${_FREECAD_EXTENSION_INCLUDE_DIRS})
    endif()
    foreach(_option ALL FREESTANDING OPTIONAL)
        if(_FREECAD_EXTENSION_${_option})
            list(APPEND _freecad_extension_args ${_option})
        endif()
    endforeach()

    freecad_wasm_addon(${target} ${_freecad_extension_args})
endfunction()
