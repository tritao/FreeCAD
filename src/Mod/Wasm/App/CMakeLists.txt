# SPDX-License-Identifier: LGPL-2.1-or-later

set(Wasm_LIBS
    FreeCADApp
)

set(Wasm_API_INPUTS
    ${CMAKE_SOURCE_DIR}/src/Base/Vector.pyi
    ${CMAKE_SOURCE_DIR}/src/App/Document.pyi
    ${CMAKE_SOURCE_DIR}/src/App/DocumentObject.pyi
)

if(BUILD_PART)
    list(APPEND Wasm_API_INPUTS
        ${CMAKE_SOURCE_DIR}/src/Mod/Part/App/TopoShape.pyi
    )
    list(APPEND Wasm_LIBS Part)
endif()

set(Wasm_API_MODEL ${CMAKE_BINARY_DIR}/Mod/Wasm/freecad_wasm_api.json)
set(Wasm_API_SIGNATURE ${CMAKE_BINARY_DIR}/Mod/Wasm/freecad_wasm_api.signature)
set(Wasm_API_DISPATCH_METADATA
    ${CMAKE_BINARY_DIR}/Mod/Wasm/freecad_wasm_dispatch_metadata.hpp)
set(Wasm_API_GENERATOR ${CMAKE_SOURCE_DIR}/src/Tools/bindings/generate_wasm_api.py)
set(Wasm_API_ABI_CHECKER ${CMAKE_SOURCE_DIR}/src/Tools/bindings/manage_wasm_abi.py)
set(Wasm_API_SDK_GENERATOR ${CMAKE_SOURCE_DIR}/src/Tools/bindings/generate_wasm_sdk.py)
set(Wasm_API_GENERATOR_SOURCES
    ${Wasm_API_GENERATOR}
    ${Wasm_API_ABI_CHECKER}
    ${CMAKE_SOURCE_DIR}/src/Tools/python_api_model/diagnostics.py
    ${CMAKE_SOURCE_DIR}/src/Tools/python_api_model/metadata.py
    ${CMAKE_SOURCE_DIR}/src/Tools/python_api_model/model.py
    ${CMAKE_SOURCE_DIR}/src/Tools/python_api_model/normalize.py
    ${CMAKE_SOURCE_DIR}/src/Tools/python_api_model/resolve.py
    ${CMAKE_SOURCE_DIR}/src/Tools/python_api_model/signatures.py
    ${CMAKE_SOURCE_DIR}/src/Tools/python_api_model/types.py
    ${CMAKE_SOURCE_DIR}/src/Tools/extension_api_model/__init__.py
    ${CMAKE_SOURCE_DIR}/src/Tools/extension_api_model/model.py
    ${CMAKE_SOURCE_DIR}/src/Tools/extension_api_model/project.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/api_extract.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/decorators.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/deprecation.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/discovery.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/model.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/module_merge.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/naming.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/parsing.py
    ${CMAKE_SOURCE_DIR}/src/Tools/typing/stubgen/source_inputs.py
    ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/wasm_abi.lock.toml
    ${CMAKE_SOURCE_DIR}/src/Mod/Wasm/WasmExtensionApi.json
    ${CMAKE_SOURCE_DIR}/src/Tools/wasm_api_model/__init__.py
    ${CMAKE_SOURCE_DIR}/src/Tools/wasm_api_model/adapters.py
    ${CMAKE_SOURCE_DIR}/src/Tools/wasm_api_model/lock.py
    ${CMAKE_SOURCE_DIR}/src/Tools/wasm_api_model/model.py
    ${CMAKE_SOURCE_DIR}/src/Tools/wasm_api_model/types.py
)

add_custom_command(
    OUTPUT
        ${Wasm_API_MODEL}
        ${Wasm_API_SIGNATURE}
        ${Wasm_API_DISPATCH_METADATA}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/Mod/Wasm
    COMMAND ${Python3_EXECUTABLE} ${Wasm_API_GENERATOR}
            --output ${Wasm_API_MODEL}
            --dispatch-metadata-output ${Wasm_API_DISPATCH_METADATA}
            --catalog-signature-output ${Wasm_API_SIGNATURE}
            ${Wasm_API_INPUTS}
    COMMAND ${Python3_EXECUTABLE} ${Wasm_API_ABI_CHECKER}
            --check
            --catalog ${Wasm_API_MODEL}
            --available-input ${Wasm_API_INPUTS}
    MAIN_DEPENDENCY ${Wasm_API_GENERATOR}
    DEPENDS ${Wasm_API_INPUTS} ${Wasm_API_GENERATOR_SOURCES}
    COMMENT "Generating experimental FreeCAD Wasm API model"
)

add_custom_target(WasmApiModel ALL
    DEPENDS ${Wasm_API_MODEL} ${Wasm_API_SIGNATURE} ${Wasm_API_DISPATCH_METADATA}
)

set(Wasm_API_CPP_SDK ${CMAKE_CURRENT_BINARY_DIR}/freecad_wasm_api.hpp)
set(Wasm_API_RUST_SDK ${CMAKE_CURRENT_BINARY_DIR}/freecad_wasm_api.rs)
set(Wasm_API_PYTHON_SDK ${CMAKE_CURRENT_BINARY_DIR}/freecad_wasm_api.py)

add_custom_command(
    OUTPUT
        ${Wasm_API_CPP_SDK}
        ${Wasm_API_RUST_SDK}
        ${Wasm_API_PYTHON_SDK}
    COMMAND ${Python3_EXECUTABLE} ${Wasm_API_SDK_GENERATOR}
            --api-json ${Wasm_API_MODEL}
            --cpp-output ${Wasm_API_CPP_SDK}
            --rust-output ${Wasm_API_RUST_SDK}
            --python-output ${Wasm_API_PYTHON_SDK}
    DEPENDS ${Wasm_API_MODEL} ${Wasm_API_SDK_GENERATOR}
    COMMENT "Generating experimental FreeCAD Wasm guest SDK types"
)

add_custom_target(WasmApiSdk ALL
    DEPENDS
        ${Wasm_API_CPP_SDK}
        ${Wasm_API_RUST_SDK}
        ${Wasm_API_PYTHON_SDK}
)

set(Wasm_SRCS
    AppWasm.cpp
    PreCompiled.h
    WasmAddon.cpp
    WasmAddon.h
    WasmAddonManager.cpp
    WasmAddonManager.h
    WasmHandleTable.cpp
    WasmHandleTable.h
    WasmHostApi.cpp
    WasmHostApi.h
    WasmPermissions.h
    WasmManifest.cpp
    WasmManifest.h
    WasmRuntime.cpp
    WasmRuntime.h
    WasmRuntimeFactory.cpp
    WasmRuntimeFactory.h
)

if(FREECAD_USE_WAMR)
    include(${CMAKE_SOURCE_DIR}/cMake/FreeCAD_Helpers/SetupWamr.cmake)
    list(APPEND Wasm_SRCS
        WamrHostBindings.cpp
        WamrHostBindings.h
        WamrInstance.cpp
        WamrInstance.h
        WamrRuntime.cpp
        WamrRuntime.h
    )
    list(APPEND Wasm_LIBS FreeCADWamr)
endif()

add_library(Wasm SHARED ${Wasm_SRCS})
add_dependencies(Wasm WasmApiModel WasmApiSdk)

if(BUILD_PART)
    target_compile_definitions(Wasm PRIVATE FREECAD_WASM_HAS_PART=1)
endif()

target_include_directories(
    Wasm
    SYSTEM
    PRIVATE
    ${CMAKE_BINARY_DIR}/Mod/Wasm
    ${CMAKE_CURRENT_BINARY_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src/3rdParty/json/single_include/
)

if(FREECAD_USE_WAMR)
    target_compile_definitions(Wasm PRIVATE FREECAD_HAS_WAMR=1)
    if(FREECAD_WAMR_SUPPORTS_AOT)
        target_compile_definitions(Wasm PRIVATE FREECAD_WAMR_SUPPORTS_AOT=1)
    endif()
    if(FREECAD_WAMR_SUPPORTS_JIT)
        target_compile_definitions(Wasm PRIVATE FREECAD_WAMR_SUPPORTS_JIT=1)
    endif()
    if(FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING)
        target_compile_definitions(Wasm PRIVATE FREECAD_WAMR_SUPPORTS_INSTRUCTION_METERING=1)
    endif()
endif()

target_link_libraries(Wasm ${Wasm_LIBS})

if(FREECAD_USE_PCH)
    target_precompile_headers(Wasm PRIVATE
            $<$<COMPILE_LANGUAGE:CXX>:"${CMAKE_CURRENT_LIST_DIR}/PreCompiled.h">
    )
endif(FREECAD_USE_PCH)

if (FREECAD_WARN_ERROR)
    target_compile_warn_error(Wasm)
endif()

SET_BIN_DIR(Wasm Wasm /Mod/Wasm)
SET_PYTHON_PREFIX_SUFFIX(Wasm)

install(TARGETS Wasm DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES ${Wasm_API_MODEL} DESTINATION Mod/Wasm COMPONENT WasmGuestSDK)
install(FILES ${Wasm_API_SIGNATURE}
    DESTINATION ${CMAKE_INSTALL_DATADIR}/FreeCAD/Wasm
    COMPONENT WasmGuestSDK
)
install(
    FILES
        ${Wasm_API_CPP_SDK}
        ${Wasm_API_RUST_SDK}
        ${Wasm_API_PYTHON_SDK}
    DESTINATION
        Mod/Wasm/Guest
    COMPONENT WasmGuestSDK
)
install(
    FILES ${Wasm_API_CPP_SDK} ${Wasm_API_RUST_SDK}
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/FreeCAD/Wasm/Guest
    COMPONENT WasmGuestSDK
)
