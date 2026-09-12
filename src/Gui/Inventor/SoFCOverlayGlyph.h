// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 FreeCAD contributors

#pragma once

#include <Inventor/fields/SoSFColor.h>
#include <Inventor/fields/SoSFEnum.h>
#include <Inventor/fields/SoSFInt32.h>
#include <Inventor/fields/SoSFVec3f.h>
#include <Inventor/nodes/SoSeparator.h>

#include <FCGlobal.h>

class SoCoordinate3;
class SoMarkerSet;
class SoMaterial;
class SoNotList;

namespace Gui::Inventor
{

/** A constant-pixel glyph anchored at a point in the 3D scene.
 *
 * The node is intentionally presentation-only. Ownership, semantic identity,
 * and interaction policy remain with the viewer overlay that contains it.
 */
class GuiExport SoFCOverlayGlyph: public SoSeparator
{
    using inherited = SoSeparator;

    SO_NODE_HEADER(Gui::Inventor::SoFCOverlayGlyph);

public:
    enum Glyph
    {
        CIRCLE,
        SQUARE,
        DIAMOND,
        CROSS,
        PLUS
    };

    static void initClass();
    static void finish();

    SoFCOverlayGlyph();

    SoSFVec3f position;
    SoSFColor color;
    SoSFEnum glyph;
    SoSFInt32 size;

protected:
    ~SoFCOverlayGlyph() override;
    void notify(SoNotList* list) override;

private:
    void updateGlyph();

    SoMaterial* material {nullptr};
    SoCoordinate3* coordinates {nullptr};
    SoMarkerSet* marker {nullptr};
};

}  // namespace Gui::Inventor
