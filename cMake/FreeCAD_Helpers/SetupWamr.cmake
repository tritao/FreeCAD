# SPDX-License-Identifier: LGPL-2.1-or-later

if(NOT FREECAD_USE_WAMR OR DEFINED FREECAD_WAMR_SETUP_INCLUDED)
    return()
endif()
set(FREECAD_WAMR_SETUP_INCLUDED TRUE)

if(NOT DEFINED FREECAD_WAMR_PROVIDER)
    set(FREECAD_WAMR_PROVIDER "AUTO")
endif()

if(DEFINED ENV{FREECAD_WAMR_PROFILE}
   AND NOT "$ENV{FREECAD_WAMR_PROFILE}" STREQUAL "")
    set(FREECAD_WAMR_PROFILE "$ENV{FREECAD_WAMR_PROFILE}")
endif()
if(NOT DEFINED FREECAD_WAMR_PROFILE)
    set(FREECAD_WAMR_PROFILE "INTERP")
endif()
string(TOUPPER "${FREECAD_WAMR_PROFILE}" _freecad_wamr_profile)
if(NOT _freecad_wamr_profile MATCHES "^(INTERP|AOT|JIT)$")
    message(FATAL_ERROR
        "Unsupported FREECAD_WAMR_PROFILE='${FREECAD_WAMR_PROFILE}'. "
        "Use INTERP, AOT, or JIT.")
endif()

set(FREECAD_WAMR_SUPPORTS_AOT FALSE)
set(FREECAD_WAMR_SUPPORTS_JIT FALSE)
set(FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING FALSE)
if(_freecad_wamr_profile STREQUAL "INTERP")
    set(FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING TRUE)
endif()
if(_freecad_wamr_profile STREQUAL "AOT"
   OR _freecad_wamr_profile STREQUAL "JIT")
    set(FREECAD_WAMR_SUPPORTS_AOT TRUE)
endif()
if(_freecad_wamr_profile STREQUAL "JIT")
    set(FREECAD_WAMR_SUPPORTS_JIT TRUE)
endif()

set(FREECAD_WAMR_VERSION "2.4.5")
set(FREECAD_WAMR_URL
    "https://github.com/wasm-micro-runtime/wasm-micro-runtime/archive/refs/tags/WAMR-${FREECAD_WAMR_VERSION}.tar.gz")
set(FREECAD_WAMR_SHA256
    "1ab09d51099f276ca4a1d6629f6b589aab2bd0caa01445e05031a4bed22c199b")

string(TOUPPER "${FREECAD_WAMR_PROVIDER}" _freecad_wamr_provider)
set(_freecad_wamr_source_dir "")

if(FREECAD_WAMR_ROOT)
    if(EXISTS "${FREECAD_WAMR_ROOT}/build-scripts/runtime_lib.cmake")
        set(_freecad_wamr_source_dir "${FREECAD_WAMR_ROOT}")
    else()
        list(PREPEND CMAKE_PREFIX_PATH "${FREECAD_WAMR_ROOT}")
    endif()
endif()

if(_freecad_wamr_provider STREQUAL "SYSTEM")
    set(_freecad_wamr_provider PACKAGE)
endif()

if(NOT _freecad_wamr_provider MATCHES "^(AUTO|PACKAGE|SOURCE|FETCH)$")
    message(FATAL_ERROR
        "Unsupported FREECAD_WAMR_PROVIDER='${FREECAD_WAMR_PROVIDER}'. "
        "Use AUTO, PACKAGE, SOURCE, or FETCH.")
endif()

if(NOT _freecad_wamr_source_dir
   AND (_freecad_wamr_provider STREQUAL "AUTO"
        OR _freecad_wamr_provider STREQUAL "PACKAGE"))
    find_package(WAMR CONFIG QUIET)
    find_package(iwasm CONFIG QUIET)

    if(TARGET WAMR::wamr)
        if(NOT TARGET FreeCADWamr)
            add_library(FreeCADWamr INTERFACE)
        endif()
        target_link_libraries(FreeCADWamr INTERFACE WAMR::wamr)
        set(_freecad_wamr_package_target WAMR::wamr)
        set(_freecad_wamr_source_dir "PACKAGED")
    elseif(TARGET iwasm::vmlib)
        if(NOT TARGET FreeCADWamr)
            add_library(FreeCADWamr INTERFACE)
        endif()
        # The WAMR JIT package exports every LLVM archive as an interface
        # dependency even though libiwasm already carries libLLVM as a shared
        # runtime dependency. Link the imported shared object directly to
        # avoid loading LLVM twice in consumers.
        get_target_property(
            _freecad_wamr_iwasm_includes
            iwasm::vmlib
            INTERFACE_INCLUDE_DIRECTORIES
        )
        if(_freecad_wamr_iwasm_includes)
            target_include_directories(
                FreeCADWamr
                INTERFACE ${_freecad_wamr_iwasm_includes}
            )
        endif()
        target_link_libraries(
            FreeCADWamr
            INTERFACE "$<TARGET_FILE:iwasm::vmlib>"
        )
        set(_freecad_wamr_source_dir "PACKAGED")
    elseif(_freecad_wamr_provider STREQUAL "PACKAGE")
        message(FATAL_ERROR
            "FREECAD_WAMR_PROVIDER=PACKAGE could not find WAMR::wamr or "
            "iwasm::vmlib. Set CMAKE_PREFIX_PATH or FREECAD_WAMR_ROOT to the WAMR package.")
    endif()
endif()

if(_freecad_wamr_source_dir STREQUAL "PACKAGED")
    set(_freecad_wamr_profile_file "")
    foreach(_freecad_wamr_prefix IN LISTS CMAKE_PREFIX_PATH)
        if(EXISTS "${_freecad_wamr_prefix}/share/wamr/FreeCADWamrProfile.cmake")
            set(_freecad_wamr_profile_file
                "${_freecad_wamr_prefix}/share/wamr/FreeCADWamrProfile.cmake")
            break()
        endif()
    endforeach()
    if(NOT _freecad_wamr_profile_file)
        message(FATAL_ERROR
            "The packaged WAMR runtime does not provide profile metadata. "
            "Install a FreeCAD WAMR profile package matching '${_freecad_wamr_profile}'.")
    endif()
    include("${_freecad_wamr_profile_file}")
    if(NOT DEFINED FREECAD_WAMR_PACKAGE_PROFILE
       OR NOT DEFINED FREECAD_WAMR_PACKAGE_SUPPORTS_AOT
       OR NOT DEFINED FREECAD_WAMR_PACKAGE_SUPPORTS_JIT
       OR NOT DEFINED FREECAD_WAMR_PACKAGE_SUPPORTS_INSTRUCTION_METERING)
        message(FATAL_ERROR
            "Packaged WAMR profile metadata is incomplete: ${_freecad_wamr_profile_file}")
    endif()
    if(NOT "${FREECAD_WAMR_PACKAGE_PROFILE}" STREQUAL "${_freecad_wamr_profile}"
       OR NOT "${FREECAD_WAMR_PACKAGE_SUPPORTS_AOT}" STREQUAL "${FREECAD_WAMR_SUPPORTS_AOT}"
       OR NOT "${FREECAD_WAMR_PACKAGE_SUPPORTS_JIT}" STREQUAL "${FREECAD_WAMR_SUPPORTS_JIT}"
       OR NOT "${FREECAD_WAMR_PACKAGE_SUPPORTS_INSTRUCTION_METERING}" STREQUAL "${FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING}")
        message(FATAL_ERROR
            "WAMR package profile '${FREECAD_WAMR_PACKAGE_PROFILE}' does not match "
            "requested profile '${_freecad_wamr_profile}'")
    endif()

    # Some WAMR package exports list LLVM dependencies as bare -l names but
    # omit the package lib directory from the imported target interface.
    if(_freecad_wamr_package_target)
        foreach(_freecad_wamr_imported_config RELEASE RELWITHDEBINFO DEBUG)
            get_target_property(
                _freecad_wamr_imported_location
                ${_freecad_wamr_package_target}
                IMPORTED_LOCATION_${_freecad_wamr_imported_config}
            )
            if(_freecad_wamr_imported_location)
                break()
            endif()
        endforeach()
        if(NOT _freecad_wamr_imported_location)
            get_target_property(
                _freecad_wamr_imported_location
                ${_freecad_wamr_package_target}
                IMPORTED_LOCATION
            )
        endif()
        if(_freecad_wamr_imported_location)
            get_filename_component(
                _freecad_wamr_package_lib_dir
                "${_freecad_wamr_imported_location}"
                DIRECTORY
            )
            target_link_directories(
                FreeCADWamr
                INTERFACE "${_freecad_wamr_package_lib_dir}"
            )
        endif()
    endif()
    return()
endif()

if(_freecad_wamr_provider STREQUAL "SOURCE" AND NOT _freecad_wamr_source_dir)
    message(FATAL_ERROR
        "FREECAD_WAMR_PROVIDER=SOURCE requires FREECAD_WAMR_ROOT to contain "
        "build-scripts/runtime_lib.cmake.")
endif()

if(NOT _freecad_wamr_source_dir)
    if(NOT _freecad_wamr_provider STREQUAL "AUTO"
       AND NOT _freecad_wamr_provider STREQUAL "FETCH")
        message(FATAL_ERROR "No usable WAMR source or package was found.")
    endif()

    include(FetchContent)
    FetchContent_Declare(
        wamr
        URL "${FREECAD_WAMR_URL}"
        URL_HASH "SHA256=${FREECAD_WAMR_SHA256}"
        DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    )
    FetchContent_GetProperties(wamr)
    if(NOT wamr_POPULATED)
        cmake_policy(PUSH)
        if(POLICY CMP0169)
            cmake_policy(SET CMP0169 OLD)
        endif()
        FetchContent_Populate(wamr)
        cmake_policy(POP)
    endif()
    set(_freecad_wamr_source_dir "${wamr_SOURCE_DIR}")
endif()

if(NOT EXISTS "${_freecad_wamr_source_dir}/build-scripts/runtime_lib.cmake")
    message(FATAL_ERROR
        "WAMR source root is invalid: ${_freecad_wamr_source_dir}")
endif()

if(WIN32)
    set(WAMR_BUILD_PLATFORM windows)
elseif(APPLE)
    set(WAMR_BUILD_PLATFORM darwin)
elseif(CMAKE_SYSTEM_NAME STREQUAL "FreeBSD")
    set(WAMR_BUILD_PLATFORM freebsd)
else()
    set(WAMR_BUILD_PLATFORM linux)
endif()

set(WAMR_ROOT_DIR "${_freecad_wamr_source_dir}")

# Keep host-facing WASI, threading, and the mini-loader out of every profile.
# AOT and JIT are opt-in because they change the native-code execution model.
set(WAMR_BUILD_INTERP 1)
set(WAMR_BUILD_FAST_INTERP 0)
set(WAMR_BUILD_AOT 0)
set(WAMR_BUILD_JIT 0)
set(WAMR_BUILD_FAST_JIT 0)
set(WAMR_BUILD_INSTRUCTION_METERING 1)
if(_freecad_wamr_profile STREQUAL "AOT")
    set(WAMR_BUILD_FAST_INTERP 1)
    set(WAMR_BUILD_AOT 1)
    set(WAMR_BUILD_INSTRUCTION_METERING 0)
elseif(_freecad_wamr_profile STREQUAL "JIT")
    set(WAMR_BUILD_AOT 1)
    set(WAMR_BUILD_JIT 1)
    set(WAMR_BUILD_FAST_INTERP 0)
    set(WAMR_BUILD_INSTRUCTION_METERING 0)
endif()
set(WAMR_BUILD_LIBC_BUILTIN 1)
set(WAMR_BUILD_LIBC_WASI 0)
set(WAMR_BUILD_MULTI_MODULE 0)
set(WAMR_BUILD_BULK_MEMORY 1)
set(WAMR_BUILD_SHARED_MEMORY 0)
set(WAMR_BUILD_THREAD_MGR 0)
set(WAMR_BUILD_LIB_PTHREAD 0)
set(WAMR_BUILD_LIB_WASI_THREADS 0)
set(WAMR_BUILD_MINI_LOADER 0)
set(WAMR_BUILD_SIMD 1)
set(WAMR_BUILD_REF_TYPES 1)
set(WAMR_BUILD_MEMORY64 0)
set(WAMR_BUILD_MULTI_MEMORY 0)

include(${WAMR_ROOT_DIR}/build-scripts/runtime_lib.cmake)

if(NOT TARGET FreeCADWamr)
    add_library(FreeCADWamr STATIC ${WAMR_RUNTIME_LIB_SOURCE})
    set_target_properties(FreeCADWamr PROPERTIES POSITION_INDEPENDENT_CODE ON)

    find_package(Threads REQUIRED)
    target_include_directories(FreeCADWamr PUBLIC
        ${WAMR_ROOT_DIR}/core/iwasm/include
    )
    target_link_libraries(FreeCADWamr PUBLIC
        Threads::Threads
        ${CMAKE_DL_LIBS}
    )
    if(UNIX AND NOT APPLE)
        target_link_libraries(FreeCADWamr PUBLIC m)
    endif()
endif()
