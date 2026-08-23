# SPDX-License-Identifier: LGPL-2.1-or-later

add_executable(Wasm_tests_run
    WasmRuntime.cpp
)

add_test(
    NAME WasmApiGeneratorTest
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/WasmApiGeneratorTest.py
)

if(FREECAD_USE_WAMR)
    set(FREECAD_WASM_GUEST_COMPILER "" CACHE FILEPATH
        "Clang++ compiler used to build the Wasm guest test fixture")
    if(NOT FREECAD_WASM_GUEST_COMPILER)
        unset(FREECAD_WASM_GUEST_COMPILER CACHE)
        find_program(FREECAD_WASM_GUEST_COMPILER NAMES clang++ clang)
    endif()
    find_program(FREECAD_WASM_GUEST_LINKER NAMES wasm-ld)

    if(FREECAD_WASM_GUEST_COMPILER AND FREECAD_WASM_GUEST_LINKER)
        get_filename_component(FREECAD_WASM_GUEST_LINKER_DIR
            "${FREECAD_WASM_GUEST_LINKER}" DIRECTORY)
        set(FREECAD_WASM_CAPABILITY_FIXTURE
            ${CMAKE_CURRENT_BINARY_DIR}/freecad-capability-addon.wasm)
        add_custom_command(
            OUTPUT ${FREECAD_WASM_CAPABILITY_FIXTURE}
            COMMAND ${FREECAD_WASM_GUEST_COMPILER}
                    --target=wasm32-unknown-unknown
                    -std=c++20
                    -O0
                    -ffreestanding
                    -fno-exceptions
                    -fno-rtti
                    -nostdlib
                    -DFREECAD_WASM_FREESTANDING=1
                    -I${CMAKE_SOURCE_DIR}/src/Mod/Wasm
                    -B${FREECAD_WASM_GUEST_LINKER_DIR}
                    -Wl,--no-entry
                    -Wl,--export=freecad_addon_entry
                    -Wl,--export-memory
                    -Wl,--initial-memory=131072
                    -Wl,--max-memory=4194304
                    -o ${FREECAD_WASM_CAPABILITY_FIXTURE}
                    ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/Guest/examples/CapabilityAddon.cpp
            DEPENDS
                ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/WasmAbi.h
                ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/Guest/WasmGuest.h
                ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/Guest/WasmGuestFreestanding.h
                ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/Guest/examples/CapabilityAddon.cpp
            COMMENT "Building the FreeCAD Wasm capability guest fixture"
            VERBATIM
        )
        add_custom_target(WasmGuestFixture
            DEPENDS ${FREECAD_WASM_CAPABILITY_FIXTURE}
        )
        add_dependencies(Wasm_tests_run WasmGuestFixture)
        target_compile_definitions(Wasm_tests_run PRIVATE
            FREECAD_WASM_CAPABILITY_FIXTURE="${FREECAD_WASM_CAPABILITY_FIXTURE}"
        )

        set(FREECAD_WASM_RUST_COMPILER "" CACHE FILEPATH
            "Rust compiler used to build the Rust Wasm guest test fixture")
        if(NOT FREECAD_WASM_RUST_COMPILER)
            unset(FREECAD_WASM_RUST_COMPILER CACHE)
            find_program(FREECAD_WASM_RUST_COMPILER NAMES rustc)
        endif()

        if(FREECAD_WASM_RUST_COMPILER)
            execute_process(
                COMMAND ${FREECAD_WASM_RUST_COMPILER}
                        --print target-libdir
                        --target wasm32-unknown-unknown
                OUTPUT_VARIABLE _freecad_wasm_rust_target_libdir
                OUTPUT_STRIP_TRAILING_WHITESPACE
                RESULT_VARIABLE _freecad_wasm_rust_target_result
            )
            file(GLOB _freecad_wasm_rust_core
                "${_freecad_wasm_rust_target_libdir}/libcore-*.rlib"
            )
        endif()

        if(_freecad_wasm_rust_target_result EQUAL 0 AND _freecad_wasm_rust_core)
            set(FREECAD_WASM_RUST_CAPABILITY_FIXTURE
                ${CMAKE_CURRENT_BINARY_DIR}/freecad-rust-capability-addon.wasm)
            add_custom_command(
                OUTPUT ${FREECAD_WASM_RUST_CAPABILITY_FIXTURE}
                COMMAND ${FREECAD_WASM_RUST_COMPILER}
                        --target wasm32-unknown-unknown
                        --edition 2021
                        --crate-type cdylib
                        -C opt-level=z
                        -C panic=abort
                        -C link-arg=-z
                        -C link-arg=stack-size=65536
                        -C link-arg=--no-entry
                        -C link-arg=--export=freecad_addon_entry
                        -C link-arg=--export-memory
                        -C link-arg=--initial-memory=262144
                        -C link-arg=--max-memory=4194304
                        -o ${FREECAD_WASM_RUST_CAPABILITY_FIXTURE}
                        ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/Guest/examples/CapabilityAddon.rs
                DEPENDS
                    ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/Guest/examples/CapabilityAddon.rs
                    ${_freecad_wasm_rust_core}
                COMMENT "Building the FreeCAD Rust Wasm capability guest fixture"
                VERBATIM
            )
            add_custom_target(WasmRustGuestFixture
                DEPENDS ${FREECAD_WASM_RUST_CAPABILITY_FIXTURE}
            )
            add_dependencies(Wasm_tests_run WasmRustGuestFixture)
            target_compile_definitions(Wasm_tests_run PRIVATE
                FREECAD_WASM_RUST_CAPABILITY_FIXTURE="${FREECAD_WASM_RUST_CAPABILITY_FIXTURE}"
            )
        else()
            message(WARNING
                "Skipping the Rust Wasm guest fixture: rustc with the "
                "wasm32-unknown-unknown target is required")
        endif()

        if(FREECAD_WAMR_PROFILE STREQUAL "AOT")
            set(FREECAD_WASM_AOT_COMPILER "" CACHE FILEPATH
                "WAMR compiler used to build the AOT guest test fixture")
            if(NOT FREECAD_WASM_AOT_COMPILER)
                unset(FREECAD_WASM_AOT_COMPILER CACHE)
                find_program(FREECAD_WASM_AOT_COMPILER NAMES wamrc)
            endif()

            if(FREECAD_WASM_AOT_COMPILER)
                set(FREECAD_WASM_AOT_FIXTURE
                    ${CMAKE_CURRENT_BINARY_DIR}/freecad-capability-addon.aot)
                add_custom_command(
                    OUTPUT ${FREECAD_WASM_AOT_FIXTURE}
                    COMMAND ${FREECAD_WASM_AOT_COMPILER}
                            -o ${FREECAD_WASM_AOT_FIXTURE}
                            ${FREECAD_WASM_CAPABILITY_FIXTURE}
                    DEPENDS ${FREECAD_WASM_CAPABILITY_FIXTURE}
                    COMMENT "Building the FreeCAD WAMR AOT capability fixture"
                    VERBATIM
                )
                add_custom_target(WasmAotFixture
                    DEPENDS ${FREECAD_WASM_AOT_FIXTURE}
                )
                add_dependencies(Wasm_tests_run WasmAotFixture)
                target_compile_definitions(Wasm_tests_run PRIVATE
                    FREECAD_WASM_AOT_FIXTURE="${FREECAD_WASM_AOT_FIXTURE}"
                )
            else()
                message(WARNING
                    "Skipping the AOT Wasm guest fixture: wamrc is required")
            endif()
        endif()

        add_dependencies(Wasm_tests_run FreeCADMainCmd)

        add_test(
            NAME WasmPythonIntegrationTest
            COMMAND $<TARGET_FILE:FreeCADMainCmd>
                    ${CMAKE_CURRENT_SOURCE_DIR}/WasmPythonIntegration.py
        )

        set(_wasm_python_path "${CMAKE_BINARY_DIR}/Mod/Wasm")
        list(JOIN _wasm_python_path "${CMAKE_HOST_SYSTEM_PATH_SEPARATOR}" _wasm_python_path)
        set(_wasm_python_test_environment
            "FREECAD_WASM_CAPABILITY_FIXTURE=${FREECAD_WASM_CAPABILITY_FIXTURE}"
            "PYTHONPATH=${_wasm_python_path}"
        )
        if(WIN32)
            set(_wasm_runtime_path
                "${CMAKE_BINARY_DIR}/bin"
                "${CMAKE_BINARY_DIR}/Mod/Part"
                "${CMAKE_BINARY_DIR}/Mod/Material"
                "${CMAKE_PREFIX_PATH}/Library/bin"
                "${CMAKE_PREFIX_PATH}/bin"
            )
            list(JOIN _wasm_runtime_path
                "${CMAKE_HOST_SYSTEM_PATH_SEPARATOR}" _wasm_runtime_path)
            list(APPEND _wasm_python_test_environment "PATH=${_wasm_runtime_path}")
        else()
            set(_wasm_runtime_path
                "${CMAKE_BINARY_DIR}/lib"
                "${CMAKE_BINARY_DIR}/Mod/Part"
                "${CMAKE_BINARY_DIR}/Mod/Material"
                "${CMAKE_PREFIX_PATH}/lib"
            )
            list(JOIN _wasm_runtime_path
                "${CMAKE_HOST_SYSTEM_PATH_SEPARATOR}" _wasm_runtime_path)
            if(APPLE)
                list(APPEND _wasm_python_test_environment
                    "DYLD_LIBRARY_PATH=${_wasm_runtime_path}"
                )
            else()
                list(APPEND _wasm_python_test_environment
                    "LD_LIBRARY_PATH=${_wasm_runtime_path}"
                )
            endif()
        endif()
        set_tests_properties(WasmPythonIntegrationTest PROPERTIES
            ENVIRONMENT "${_wasm_python_test_environment}"
        )
    else()
        message(WARNING
            "Skipping the compiled Wasm guest fixture: clang++ and wasm-ld are required")
    endif()
endif()

target_include_directories(Wasm_tests_run PRIVATE
    ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/App
    ${CMAKE_SOURCE_DIR}/src/Mod/Wasm
)

if(FREECAD_USE_WAMR)
    target_compile_definitions(Wasm_tests_run PRIVATE FREECAD_HAS_WAMR=1)
    if(FREECAD_WAMR_PROFILE STREQUAL "AOT"
       OR FREECAD_WAMR_PROFILE STREQUAL "JIT")
        target_compile_definitions(Wasm_tests_run PRIVATE FREECAD_WAMR_SUPPORTS_AOT=1)
    endif()
    if(FREECAD_WAMR_PROFILE STREQUAL "JIT")
        target_compile_definitions(Wasm_tests_run PRIVATE FREECAD_WAMR_SUPPORTS_JIT=1)
    endif()
    target_compile_definitions(Wasm_tests_run PRIVATE FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING=1)
endif()

if(BUILD_PART)
    target_compile_definitions(Wasm_tests_run PRIVATE FREECAD_WASM_HAS_PART=1)
    if(BUILD_MATERIAL)
        add_dependencies(Wasm_tests_run MaterialLib)
    endif()
endif()

target_link_libraries(Wasm_tests_run PRIVATE
    GTest::gtest_main
    GTest::gmock_main
    ${Google_Tests_LIBS}
    Wasm
)

if(BUILD_PART)
    target_link_libraries(Wasm_tests_run PRIVATE Part)
endif()
