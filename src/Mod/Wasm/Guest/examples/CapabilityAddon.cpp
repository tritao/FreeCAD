// SPDX-License-Identifier: LGPL-2.1-or-later

#include "../WasmGuest.h"

#if defined(__clang__) && defined(__wasm__)
# define FREECAD_WASM_EXPORT(name) __attribute__((export_name(name)))
#else
# define FREECAD_WASM_EXPORT(name)
#endif

extern "C" unsigned long long freecad_addon_entry(const unsigned char*, unsigned int)
    FREECAD_WASM_EXPORT("freecad_addon_entry");

extern "C" unsigned long long freecad_addon_entry(const unsigned char*, unsigned int)
{
    Wasm::Guest::Client host;
    Wasm::Guest::Handle document = 0U;
    if (!host.documentNew("GuestCapabilityExample", &document)) {
        return 0x100000000ULL;
    }

    Wasm::Guest::Handle box = 0U;
    if (!host.partMakeBox(10.0, 20.0, 30.0, &box)) {
        return 0x100000000ULL;
    }

    Wasm::Guest::Handle object = 0U;
    if (!host.documentAddObject(document, box, "Box", &object)) {
        return 0x100000000ULL;
    }

    // The document and feature are host-owned. Release only the temporary
    // geometry handle; document lifecycle remains a host policy decision.
    bool released = false;
#if defined(FREECAD_WASM_FREESTANDING)
    released = host.release(box);
#else
    if (!host.release(box, &released)) {
        return 0x100000000ULL;
    }
#endif
    if (!released) {
        return 0x100000000ULL;
    }

#if defined(FREECAD_WASM_FREESTANDING)
    auto response = host.allocateResponse(2U);
    if (!response.valid()) {
        return 0x100000000ULL;
    }
    response.data()[0] = 'O';
    response.data()[1] = 'K';
    return response.take();
#else
    auto response = host.allocateResponse(2U);
    if (!response.ok || !response.value.valid()) {
        return 0x100000000ULL;
    }
    response.value.data()[0] = 'O';
    response.value.data()[1] = 'K';
    return response.value.take();
#endif
}

#undef FREECAD_WASM_EXPORT
