# SPDX-License-Identifier: LGPL-2.1-or-later

set(Wasm_LIBS
    FreeCADApp
)

set(Wasm_API_INPUTS
    ${CMAKE_SOURCE_DIR}/src/Base/Vector.pyi
    ${CMAKE_SOURCE_DIR}/src/App/Document.pyi
)

if(BUILD_PART)
    list(APPEND Wasm_API_INPUTS
        ${CMAKE_SOURCE_DIR}/src/Mod/Part/App/TopoShape.pyi
    )
    list(APPEND Wasm_LIBS Part)
endif()

set(Wasm_API_MODEL ${CMAKE_BINARY_DIR}/Mod/Wasm/freecad_wasm_api.json)
set(Wasm_API_GENERATOR ${CMAKE_SOURCE_DIR}/src/Tools/bindings/generate_wasm_api.py)

add_custom_command(
    OUTPUT ${Wasm_API_MODEL}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/Mod/Wasm
    COMMAND ${Python3_EXECUTABLE} ${Wasm_API_GENERATOR}
            --output ${Wasm_API_MODEL}
            ${Wasm_API_INPUTS}
    MAIN_DEPENDENCY ${Wasm_API_GENERATOR}
    DEPENDS ${Wasm_API_INPUTS}
    COMMENT "Generating experimental FreeCAD Wasm API model"
)

add_custom_target(WasmApiModel ALL
    DEPENDS ${Wasm_API_MODEL}
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
add_dependencies(Wasm WasmApiModel)

if(BUILD_PART)
    target_compile_definitions(Wasm PRIVATE FREECAD_WASM_HAS_PART=1)
endif()

target_include_directories(
    Wasm
    SYSTEM
    PRIVATE
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
install(FILES ${Wasm_API_MODEL} DESTINATION Mod/Wasm)
