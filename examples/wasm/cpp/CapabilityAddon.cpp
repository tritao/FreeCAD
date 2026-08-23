// SPDX-License-Identifier: LGPL-2.1-or-later

#include <Wasm/Guest/freecad_wasm_api.hpp>

using FreeCAD::Wasm::Generated::FreeCADDocumentHandle;
using FreeCAD::Wasm::Generated::FreeCADDocumentObjectHandle;
using FreeCAD::Wasm::Generated::FreeCADBaseVectorValue;
using FreeCAD::Wasm::Generated::Host;
using FreeCAD::Wasm::Generated::PartTopoShapeHandle;

#if defined(__clang__) && defined(__wasm__)
# define FREECAD_WASM_EXPORT(name) __attribute__((export_name(name)))
#else
# define FREECAD_WASM_EXPORT(name)
#endif

extern "C" unsigned long long freecad_addon_entry(const unsigned char*, unsigned int)
    FREECAD_WASM_EXPORT("freecad_addon_entry");

extern "C" unsigned long long freecad_addon_entry(const unsigned char*, unsigned int)
{
    Host host;
    FreeCADBaseVectorValue left;
    FreeCADBaseVectorValue right;
    if (!host.vectorNew(1.0, 2.0, 3.0, &left)
        || !host.vectorNew(4.0, 5.0, 6.0, &right)) {
        return 0x100000000ULL;
    }

    FreeCADBaseVectorValue sum;
    if (!host.vectorAdd(left, right, &sum)
        || sum.x != 5.0 || sum.y != 7.0 || sum.z != 9.0) {
        return 0x100000000ULL;
    }

    double dot = 0.0;
    if (!host.vectorDot(left, right, &dot) || dot != 32.0) {
        return 0x100000000ULL;
    }

    FreeCADBaseVectorValue cross;
    if (!host.vectorCross(left, right, &cross)
        || cross.x != -3.0 || cross.y != 6.0 || cross.z != -3.0) {
        return 0x100000000ULL;
    }

    FreeCADDocumentHandle document;
    if (!host.documentNew("GuestCapabilityExample", &document)) {
        return 0x100000000ULL;
    }

    PartTopoShapeHandle box;
    if (!host.partMakeBox(10.0, 20.0, 30.0, &box)) {
        return 0x100000000ULL;
    }

    FreeCADDocumentObjectHandle object;
    if (!host.documentAddObject(document, box, "Box", &object)) {
        return 0x100000000ULL;
    }

    // The document and feature are host-owned. Release only the temporary
    // geometry handle; document lifecycle remains a host policy decision.
    bool released = false;
#if defined(FREECAD_WASM_FREESTANDING)
    released = host.release(box.value);
#else
    released = host.release(box.value);
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
