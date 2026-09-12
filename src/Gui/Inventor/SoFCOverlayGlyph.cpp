// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 FreeCAD contributors

#include <algorithm>
#include <cstdlib>
#include <string>

#include <Inventor/SoLists.h>
#include <Inventor/fields/SoField.h>
#include <Inventor/nodes/SoAnnotation.h>
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoLightModel.h>
#include <Inventor/nodes/SoMarkerSet.h>
#include <Inventor/nodes/SoMaterial.h>

#include "MarkerBitmaps.h"
#include "SoFCOverlayGlyph.h"

using namespace Gui::Inventor;

SO_NODE_SOURCE(SoFCOverlayGlyph)

void SoFCOverlayGlyph::initClass()
{
    SO_NODE_INIT_CLASS(SoFCOverlayGlyph, SoSeparator, "Separator");
}

void SoFCOverlayGlyph::finish()
{
    atexit_cleanup();
}

SoFCOverlayGlyph::SoFCOverlayGlyph()
{
    SO_NODE_CONSTRUCTOR(SoFCOverlayGlyph);
    SO_NODE_ADD_FIELD(position, (SbVec3f(0.0F, 0.0F, 0.0F)));
    SO_NODE_ADD_FIELD(color, (SbColor(0.95F, 0.35F, 0.05F)));
    SO_NODE_ADD_FIELD(glyph, (CIRCLE));
    SO_NODE_ADD_FIELD(size, (9));
    SO_NODE_DEFINE_ENUM_VALUE(Glyph, CIRCLE);
    SO_NODE_DEFINE_ENUM_VALUE(Glyph, SQUARE);
    SO_NODE_DEFINE_ENUM_VALUE(Glyph, DIAMOND);
    SO_NODE_DEFINE_ENUM_VALUE(Glyph, CROSS);
    SO_NODE_DEFINE_ENUM_VALUE(Glyph, PLUS);
    SO_NODE_SET_SF_ENUM_TYPE(glyph, Glyph);

    auto* annotation = new SoAnnotation;
    auto* contents = new SoSeparator;
    auto* lightModel = new SoLightModel;
    lightModel->model = SoLightModel::BASE_COLOR;
    material = new SoMaterial;
    coordinates = new SoCoordinate3;
    marker = new SoMarkerSet;
    marker->numPoints = 1;

    contents->addChild(lightModel);
    contents->addChild(material);
    contents->addChild(coordinates);
    contents->addChild(marker);
    annotation->addChild(contents);
    addChild(annotation);
    updateGlyph();
}

SoFCOverlayGlyph::~SoFCOverlayGlyph() = default;

void SoFCOverlayGlyph::notify(SoNotList* list)
{
    const auto* field = list ? list->getLastField() : nullptr;
    if (field == &position || field == &color || field == &glyph || field == &size) {
        updateGlyph();
    }
    inherited::notify(list);
}

void SoFCOverlayGlyph::updateGlyph()
{
    if (!material || !coordinates || !marker) {
        return;
    }
    material->diffuseColor = color.getValue();
    coordinates->point.set1Value(0, position.getValue());

    std::string markerName;
    switch (static_cast<Glyph>(glyph.getValue())) {
        case SQUARE:
            markerName = "SQUARE_FILLED";
            break;
        case DIAMOND:
            markerName = "DIAMOND_FILLED";
            break;
        case CROSS:
            markerName = "CROSS";
            break;
        case PLUS:
            markerName = "PLUS";
            break;
        case CIRCLE:
        default:
            markerName = "CIRCLE_FILLED";
            break;
    }

    const auto supported = MarkerBitmaps::getSupportedSizes(markerName);
    const int requested = std::max(1, size.getValue());
    auto selected = requested;
    if (!supported.empty()) {
        selected = *std::min_element(
            supported.begin(),
            supported.end(),
            [requested](int lhs, int rhs) {
                return std::abs(lhs - requested) < std::abs(rhs - requested);
            });
    }
    marker->markerIndex = MarkerBitmaps::getMarkerIndex(markerName, selected);
}
