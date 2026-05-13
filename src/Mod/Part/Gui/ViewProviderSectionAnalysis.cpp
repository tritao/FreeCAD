// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileNotice: Part of the FreeCAD project.
/******************************************************************************
 *                                                                            *
 *   © 2026 FreeCAD contributors                                              *
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   of the License, or (at your option) any later version.                   *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful,               *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty              *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                  *
 *   See the GNU Lesser General Public License for more details.              *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD. If not, see https://www.gnu.org/licenses     *
 *                                                                            *
 ******************************************************************************/

#include "PreCompiled.h"

#include <QMenu>

#include <Inventor/nodes/SoSeparator.h>

#include <App/Document.h>
#include <App/ClippingPlane.h>
#include <App/Property.h>
#include <Gui/ClippingPlaneManager.h>
#include <Gui/Control.h>
#include <Gui/Document.h>
#include <Gui/Utilities.h>
#include <Gui/View3DInventor.h>

#include <Mod/Part/App/FeatureSectionAnalysis.h>

#include "TaskSectionAnalysis.h"
#include "ViewProviderPreviewExtension.h"
#include "ViewProviderSectionAnalysis.h"

using namespace PartGui;

PROPERTY_SOURCE(PartGui::ViewProviderSectionAnalysis, PartGui::ViewProviderPart)

namespace
{

constexpr long EdgeResultMode = 0;
constexpr long FaceResultMode = 1;
constexpr long BothResultMode = 2;
App::PropertyFloatConstraint::Constraints HatchLineWidthRange = {1.0, 16.0, 0.5};

const char* displayModeForResultMode(long resultMode)
{
    switch (resultMode) {
        case EdgeResultMode:
            return "Wireframe";
        case FaceResultMode:
            return "Shaded";
        case BothResultMode:
            return "Flat Lines";
        default:
            return "Flat Lines";
    }
}

const char* displayModeForSectionAnalysis(const Part::SectionAnalysis& analysis)
{
    return displayModeForResultMode(analysis.ResultMode.getValue());
}

}  // namespace

ViewProviderSectionAnalysis::ViewProviderSectionAnalysis()
{
    static const char* appearanceGroup = "Section Appearance";

    sPixmap = "Part_Section";

    ADD_PROPERTY_TYPE(
        SectionFaceColor,
        (Base::Color(0.96F, 0.64F, 0.26F)),
        appearanceGroup,
        App::Prop_None,
        "Face color used for section analysis results"
    );
    ADD_PROPERTY_TYPE(
        SectionEdgeColor,
        (Base::Color(0.80F, 0.33F, 0.0F)),
        appearanceGroup,
        App::Prop_None,
        "Edge color used for section analysis results"
    );
    ADD_PROPERTY_TYPE(
        SectionFaceTransparency,
        (25),
        appearanceGroup,
        App::Prop_None,
        "Face transparency used for section analysis results"
    );
    ADD_PROPERTY_TYPE(
        HatchColor,
        (Base::Color(0.80F, 0.33F, 0.0F)),
        appearanceGroup,
        App::Prop_None,
        "Color used for section analysis hatch lines"
    );
    ADD_PROPERTY_TYPE(
        HatchLineWidth,
        (1.0F),
        appearanceGroup,
        App::Prop_None,
        "Line width used for section analysis hatch lines"
    );
    HatchLineWidth.setConstraints(&HatchLineWidthRange);
    ADD_PROPERTY_TYPE(
        UseSectionEdgeColorForHatching,
        (true),
        appearanceGroup,
        App::Prop_None,
        "Use the section edge color for hatch lines"
    );

    LineWidth.setValue(2.0F);
}

ViewProviderSectionAnalysis::~ViewProviderSectionAnalysis() = default;

void ViewProviderSectionAnalysis::attach(App::DocumentObject* object)
{
    ViewProviderPart::attach(object);

    pcHatchRoot = new SoSeparator;
    pcHatchShape = new SoPreviewShape;
    pcHatchShape->transparency = 0.0F;
    pcHatchRoot->addChild(pcHatchShape);
    getOrCreateAnnotation()->addChild(pcHatchRoot);

    syncAppearanceProperties();
    syncDisplayForResultMode();
    syncHatchAppearance();
    syncHatchGeometry();
}

void ViewProviderSectionAnalysis::onChanged(const App::Property* prop)
{
    if (prop == &SectionFaceColor || prop == &SectionEdgeColor || prop == &SectionFaceTransparency) {
        syncAppearanceProperties();
        if (prop == &SectionEdgeColor) {
            syncHatchAppearance();
        }
        return;
    }

    if (prop == &HatchColor || prop == &HatchLineWidth || prop == &UseSectionEdgeColorForHatching) {
        syncHatchAppearance();
        return;
    }

    ViewProviderPart::onChanged(prop);
}

void ViewProviderSectionAnalysis::updateData(const App::Property* prop)
{
    ViewProviderPart::updateData(prop);

    auto* analysis = getObject<Part::SectionAnalysis>();
    if (analysis && (prop == &analysis->ResultMode || prop == &analysis->ShowHatching)) {
        syncDisplayForResultMode();
    }
    if (analysis
        && (prop == &analysis->ShowHatching || prop == &analysis->HatchShape
            || prop == &analysis->ResultMode)) {
        syncHatchGeometry();
    }
}

void ViewProviderSectionAnalysis::syncDisplayForResultMode()
{
    auto* analysis = getObject<Part::SectionAnalysis>();
    if (!analysis) {
        return;
    }

    const char* modeName = displayModeForSectionAnalysis(*analysis);
    if (std::string_view(DisplayMode.getValueAsString()) != modeName) {
        DisplayMode.setValue(modeName);
    }
}

void ViewProviderSectionAnalysis::syncAppearanceProperties()
{
    LineColor.setValue(SectionEdgeColor.getValue());
    ShapeAppearance.setDiffuseColor(SectionFaceColor.getValue());
    Transparency.setValue(SectionFaceTransparency.getValue());
}

void ViewProviderSectionAnalysis::syncHatchAppearance()
{
    if (!pcHatchShape) {
        return;
    }

    const Base::Color hatchColor = UseSectionEdgeColorForHatching.getValue()
        ? SectionEdgeColor.getValue()
        : HatchColor.getValue();
    pcHatchShape->color.setValue(Base::convertTo<SbColor>(hatchColor));
    pcHatchShape->lineWidth.setValue(HatchLineWidth.getValue());
}

void ViewProviderSectionAnalysis::syncHatchGeometry()
{
    if (!pcHatchRoot || !pcHatchShape) {
        return;
    }

    auto* analysis = getObject<Part::SectionAnalysis>();
    if (!analysis || !analysis->ShowHatching.getValue()) {
        pcHatchRoot->removeAllChildren();
        return;
    }

    const Part::TopoShape& hatchShape = analysis->HatchShape.getShape();
    if (hatchShape.isNull()) {
        pcHatchRoot->removeAllChildren();
        return;
    }

    ViewProviderPartExt::setupCoinGeometry(
        hatchShape.getShape(),
        pcHatchShape,
        Deviation.getValue(),
        AngularDeflection.getValue()
    );
    pcHatchShape->transform.setValue(Base::convertTo<SbMatrix>(hatchShape.getTransform()));
    syncHatchAppearance();

    const unsigned lineCoordsCount = pcHatchShape->lineset->coordIndex.getNum();
    unsigned lineCount = 1;
    for (unsigned i = 0; i < lineCoordsCount; ++i) {
        if (pcHatchShape->lineset->coordIndex[i] < 0) {
            ++lineCount;
        }
    }

    pcHatchShape->lineset->materialIndex.setNum(lineCount);
    for (unsigned i = 0; i < lineCount; ++i) {
        pcHatchShape->lineset->materialIndex.set1Value(i, 0);
    }

    if (pcHatchRoot->findChild(pcHatchShape) < 0) {
        pcHatchRoot->addChild(pcHatchShape);
    }
}

bool ViewProviderSectionAnalysis::doubleClicked()
{
    return getDocument() ? getDocument()->setEdit(this, ViewProvider::Default) : false;
}

bool ViewProviderSectionAnalysis::setEdit(int ModNum)
{
    if (ModNum != ViewProvider::Default) {
        return ViewProviderPart::setEdit(ModNum);
    }
    if (Gui::Control().activeDialog(getDocument()->getDocument())) {
        return false;
    }

    Gui::Control().showDialog(new TaskSectionAnalysis(this), getDocument()->getDocument());
    return true;
}

void ViewProviderSectionAnalysis::unsetEdit(int ModNum)
{
    if (ModNum == ViewProvider::Default) {
        Gui::Control().closeDialog(getDocument()->getDocument());
    }
    else {
        ViewProviderPart::unsetEdit(ModNum);
    }
}

void ViewProviderSectionAnalysis::setupContextMenu(QMenu* menu, QObject* receiver, const char* member)
{
    Q_UNUSED(receiver);
    Q_UNUSED(member);

    auto* analysis = getObject<Part::SectionAnalysis>();
    auto* plane = analysis ? freecad_cast<App::ClippingPlane*>(analysis->ClippingPlane.getValue())
                           : nullptr;
    auto* view = qobject_cast<Gui::View3DInventor*>(getActiveView());

    menu->addAction(QObject::tr("Edit section analysis"), [this]() {
        if (auto* doc = getDocument()) {
            doc->setEdit(this, ViewProvider::Default);
        }
    });

    if (analysis && analysis->getDocument()) {
        menu->addAction(QObject::tr("Recompute section analysis"), [analysis]() {
            if (auto* doc = analysis->getDocument()) {
                doc->recompute();
            }
        });
    }

    if (view && plane) {
        if (Gui::ClippingPlaneManager::instance().isActive(view, plane)) {
            menu->addAction(QObject::tr("Deactivate linked clipping plane"), [view, plane]() {
                Gui::ClippingPlaneManager::instance().deactivate(view, plane);
            });
        }
        else {
            menu->addAction(QObject::tr("Activate linked clipping plane"), [view, plane]() {
                Gui::ClippingPlaneManager::instance().activate(view, plane);
            });
        }
    }

    if (plane) {
        menu->addAction(QObject::tr("Edit linked clipping plane"), [this, plane]() {
            if (auto* doc = getDocument()) {
                if (auto* planeViewProvider = doc->getViewProvider(plane)) {
                    doc->setEdit(planeViewProvider, ViewProvider::Default);
                }
            }
        });
    }

    ViewProviderPart::setupContextMenu(menu, receiver, member);
}
