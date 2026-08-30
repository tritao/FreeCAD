# SPDX-License-Identifier: LGPL-2.1-or-later

foreach(_required TEST_BINARY_DIR TEST_GENERATOR
                  TEST_GUEST_COMPILER TEST_GUEST_LINKER)
    if(NOT DEFINED ${_required} OR "${${_required}}" STREQUAL "")
        message(FATAL_ERROR
            "InstalledGuestSdkTest.cmake requires ${_required}")
    endif()
endforeach()

set(_install_prefix "${TEST_BINARY_DIR}/wasm-installed-sdk")
set(_consumer_build "${TEST_BINARY_DIR}/wasm-installed-sdk-consumer")
file(REMOVE_RECURSE "${_install_prefix}" "${_consumer_build}")

execute_process(
    COMMAND "${CMAKE_COMMAND}" --install "${TEST_BINARY_DIR}"
            --prefix "${_install_prefix}"
            --component WasmGuestSDK
    RESULT_VARIABLE _install_result
    OUTPUT_VARIABLE _install_output
    ERROR_VARIABLE _install_error
)
if(NOT _install_result EQUAL 0)
    message(FATAL_ERROR
        "FreeCAD Wasm guest SDK installation failed:\n${_install_output}\n${_install_error}")
endif()

set(_consumer_source
    "${_install_prefix}/share/FreeCAD/Wasm/examples/cpp")
if(NOT EXISTS "${_consumer_source}/CMakeLists.txt")
    message(FATAL_ERROR "installed FreeCAD Wasm C++ example was not found")
endif()

set(_configure_command
    "${CMAKE_COMMAND}"
    -S "${_consumer_source}"
    -B "${_consumer_build}"
    -G "${TEST_GENERATOR}"
    "-DCMAKE_PREFIX_PATH=${_install_prefix}"
    -DFREECAD_WASM_USE_INSTALLED_SDK=ON
    "-DFREECAD_WASM_GUEST_COMPILER=${TEST_GUEST_COMPILER}"
    "-DFREECAD_WASM_GUEST_LINKER=${TEST_GUEST_LINKER}"
)
if(TEST_MAKE_PROGRAM)
    list(APPEND _configure_command
        "-DCMAKE_MAKE_PROGRAM=${TEST_MAKE_PROGRAM}")
endif()
if(TEST_BUILD_TYPE)
    list(APPEND _configure_command
        "-DCMAKE_BUILD_TYPE=${TEST_BUILD_TYPE}")
endif()

execute_process(
    COMMAND ${_configure_command}
    RESULT_VARIABLE _configure_result
    OUTPUT_VARIABLE _configure_output
    ERROR_VARIABLE _configure_error
)
if(NOT _configure_result EQUAL 0)
    message(FATAL_ERROR
        "installed FreeCAD Wasm SDK consumer configuration failed:\n"
        "${_configure_output}\n${_configure_error}")
endif()

execute_process(
    COMMAND "${CMAKE_COMMAND}" --build "${_consumer_build}"
    RESULT_VARIABLE _build_result
    OUTPUT_VARIABLE _build_output
    ERROR_VARIABLE _build_error
)
if(NOT _build_result EQUAL 0)
    message(FATAL_ERROR
        "installed FreeCAD Wasm SDK consumer build failed:\n"
        "${_build_output}\n${_build_error}")
endif()

set(_manifest "${_consumer_build}/manifest.json")
set(_signature
    "${_install_prefix}/share/FreeCAD/Wasm/freecad_wasm_api.signature")
if(NOT EXISTS "${_manifest}" OR NOT EXISTS "${_signature}")
    message(FATAL_ERROR
        "installed SDK consumer did not produce its manifest and signature")
endif()

file(READ "${_manifest}" _manifest_contents)
file(READ "${_signature}" _signature_contents)
string(STRIP "${_signature_contents}" _signature_contents)
if(_manifest_contents MATCHES "@FREECAD_WASM_ABI_HASH@")
    message(FATAL_ERROR "installed SDK consumer manifest kept the ABI hash placeholder")
endif()
string(FIND "${_manifest_contents}" "${_signature_contents}" _signature_position)
if(_signature_position EQUAL -1)
    message(FATAL_ERROR
        "installed SDK consumer manifest does not contain the installed ABI signature")
endif()

set(_wasm "${_consumer_build}/freecad-capability-addon.wasm")
if(NOT EXISTS "${_wasm}")
    message(FATAL_ERROR "installed SDK consumer did not produce a Wasm module")
endif()

message(STATUS "Installed FreeCAD Wasm guest SDK consumer test passed")
