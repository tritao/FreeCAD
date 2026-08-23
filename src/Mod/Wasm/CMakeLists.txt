# SPDX-License-Identifier: LGPL-2.1-or-later

add_subdirectory(App)

set(Wasm_Scripts
    Init.py
)

set(Wasm_Guest_SDK
    WasmAbi.h
    Guest/WasmGuest.h
    Guest/WasmGuestFreestanding.h
    Guest/examples/CapabilityAddon.cpp
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
        include/FreeCAD/Wasm
)

install(
    FILES
        Guest/WasmGuest.h
        Guest/WasmGuestFreestanding.h
    DESTINATION
        include/FreeCAD/Wasm/Guest
)

install(
    FILES
        ABI.md
    DESTINATION
        share/doc/FreeCAD/Wasm
)
