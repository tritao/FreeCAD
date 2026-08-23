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

    FreeCADDocumentObjectHandle queriedObject;
    if (!host.documentGetObject(document, "Box", &queriedObject)) {
        return 0x100000000ULL;
    }

    char label[128];
    unsigned int labelLength = 0U;
    if (!host.documentObjectGetLabel(object, label, sizeof(label), &labelLength)
        || labelLength != 3U || label[0] != 'B' || label[1] != 'o' || label[2] != 'x') {
        return 0x100000000ULL;
    }
    if (!host.documentOpenTransaction(document, "Set label")
        || !host.documentObjectSetLabel(object, "ConfiguredBox")
        || !host.documentCommitTransaction(document)) {
        return 0x100000000ULL;
    }
    if (!host.documentOpenTransaction(document, "Rollback label")
        || !host.documentObjectSetLabel(object, "TemporaryBox")
        || !host.documentAbortTransaction(document)
        || !host.documentObjectGetLabel(object, label, sizeof(label), &labelLength)
        || labelLength != 13U || label[0] != 'C' || label[1] != 'o' || label[2] != 'n'
        || label[3] != 'f' || label[4] != 'i' || label[5] != 'g' || label[6] != 'u'
        || label[7] != 'r' || label[8] != 'e' || label[9] != 'd' || label[10] != 'B'
        || label[11] != 'o' || label[12] != 'x') {
        return 0x100000000ULL;
    }

    double shapeLength = 0.0;
    double shapeArea = 0.0;
    double shapeVolume = 0.0;
    if (host.topoShapeIsNull(box)
        || !host.topoShapeIsValid(box)
        || !host.topoShapeLength(box, &shapeLength)
        || shapeLength != 480.0
        || !host.topoShapeArea(box, &shapeArea)
        || shapeArea != 2200.0
        || !host.topoShapeVolume(box, &shapeVolume)
        || shapeVolume != 6000.0) {
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
