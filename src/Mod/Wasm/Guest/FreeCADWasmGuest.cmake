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
    set(_FREECAD_WASM_SDK_CPP
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest/freecad_wasm_api.hpp")
    set(_FREECAD_WASM_SDK_RUST
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest/freecad_wasm_api.rs")
    set(_FREECAD_WASM_SDK_PYTHON
        "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest/freecad_wasm_api.py")

    add_custom_command(
        OUTPUT
            "${_FREECAD_WASM_SDK_MODEL}"
            "${_FREECAD_WASM_SDK_CPP}"
            "${_FREECAD_WASM_SDK_RUST}"
            "${_FREECAD_WASM_SDK_PYTHON}"
        COMMAND ${CMAKE_COMMAND} -E make_directory
                "${_FREECAD_WASM_SDK_OUTPUT_DIR}/Wasm/Guest"
        COMMAND ${_FREECAD_WASM_SDK_PYTHON_EXECUTABLE}
                "${_FREECAD_WASM_SDK_API_GENERATOR}"
                --output "${_FREECAD_WASM_SDK_MODEL}"
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
endfunction()

function(freecad_wasm_addon target)
    set(_options ALL FREESTANDING OPTIONAL)
    set(_one_value_args
        SOURCE OUTPUT INCLUDE_ROOT OUTPUT_VARIABLE MANIFEST MANIFEST_OUTPUT
        BUNDLE_TARGET_VARIABLE
    )
    set(_multi_value_args DEPENDS INCLUDE_DIRS)
    cmake_parse_arguments(
        _FREECAD_WASM
        "${_options}"
        "${_one_value_args}"
        "${_multi_value_args}"
        ${ARGN}
    )

    if(NOT _FREECAD_WASM_SOURCE)
        message(FATAL_ERROR
            "freecad_wasm_addon(${target}) requires SOURCE")
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
        "${_FREECAD_WASM_SOURCE}"
    )
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
            "${_FREECAD_WASM_SOURCE}"
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
        add_custom_command(
            OUTPUT "${_FREECAD_WASM_MANIFEST_OUTPUT}"
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${_FREECAD_WASM_MANIFEST}"
                    "${_FREECAD_WASM_MANIFEST_OUTPUT}"
            DEPENDS "${_FREECAD_WASM_MANIFEST}"
            COMMENT "Staging the FreeCAD Wasm addon manifest for ${target}"
            VERBATIM
        )

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
