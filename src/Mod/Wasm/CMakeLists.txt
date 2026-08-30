# SPDX-License-Identifier: LGPL-2.1-or-later

include(CMakePackageConfigHelpers)

add_subdirectory(App)

set(Wasm_Guest_CONFIG
    ${CMAKE_CURRENT_BINARY_DIR}/FreeCADWasmGuestConfig.cmake)
configure_package_config_file(
    Guest/FreeCADWasmGuestConfig.cmake.in
    ${Wasm_Guest_CONFIG}
    INSTALL_DESTINATION ${CMAKE_INSTALL_DATADIR}/cmake/FreeCADWasmGuest
    PATH_VARS CMAKE_INSTALL_INCLUDEDIR CMAKE_INSTALL_DATADIR
)

set(Wasm_Scripts
    Init.py
)

set(Wasm_Guest_SDK
    WasmAbi.h
    WasmApiOperations.json
    WasmApiAdapters.json
    WasmExtensionApi.json
    Guest/FreeCADWasmGuest.cmake
    Guest/FreeCADWasmGuestConfig.cmake.in
    Guest/WasmGuest.h
    Guest/WasmGuestFreestanding.h
    ABI.md
)

add_custom_target(WasmScripts ALL
    SOURCES ${Wasm_Scripts} ${Wasm_Guest_SDK}
)

fc_target_copy_resource_flat(WasmScripts
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_BINARY_DIR}/Mod/Wasm
    ${Wasm_Scripts}
)

install(
    FILES
        ${Wasm_Scripts}
    DESTINATION
        Mod/Wasm
)

install(
    FILES
        WasmAbi.h
    DESTINATION
        ${CMAKE_INSTALL_INCLUDEDIR}/FreeCAD/Wasm
)

install(
    FILES
        Guest/FreeCADWasmGuest.cmake
        WasmApiOperations.json
        WasmApiAdapters.json
        WasmExtensionApi.json
    DESTINATION
        ${CMAKE_INSTALL_DATADIR}/FreeCAD/Wasm
)

install(
    FILES
        ${Wasm_Guest_CONFIG}
    DESTINATION
        ${CMAKE_INSTALL_DATADIR}/cmake/FreeCADWasmGuest
)

install(
    FILES
        Guest/WasmGuest.h
        Guest/WasmGuestFreestanding.h
    DESTINATION
        ${CMAKE_INSTALL_INCLUDEDIR}/FreeCAD/Wasm/Guest
)

install(
    FILES
        ${CMAKE_SOURCE_DIR}/examples/wasm/cpp/CapabilityAddon.cpp
        ${CMAKE_SOURCE_DIR}/examples/wasm/cpp/CMakeLists.txt
        ${CMAKE_SOURCE_DIR}/examples/wasm/cpp/manifest.json
        ${CMAKE_SOURCE_DIR}/examples/wasm/cpp/README.md
    DESTINATION
        ${CMAKE_INSTALL_DATADIR}/FreeCAD/Wasm/examples/cpp
)

install(
    FILES
        ABI.md
    DESTINATION
        share/doc/FreeCAD/Wasm
)
