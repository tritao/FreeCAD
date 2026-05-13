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

#include <App/Document.h>
#include <App/ClippingPlane.h>
#include <App/Property.h>
#include <Gui/ClippingPlaneManager.h>
#include <Gui/Control.h>
#include <Gui/Document.h>
#include <Gui/View3DInventor.h>

#include <Mod/Part/App/FeatureSectionAnalysis.h>

#include "TaskSectionAnalysis.h"
#include "ViewProviderSectionAnalysis.h"

using namespace PartGui;

PROPERTY_SOURCE(PartGui::ViewProviderSectionAnalysis, PartGui::ViewProviderPart)

namespace
{

constexpr long EdgeResultMode = 0;
constexpr long FaceResultMode = 1;
constexpr long BothResultMode = 2;

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

}  // namespace

ViewProviderSectionAnalysis::ViewProviderSectionAnalysis()
{
    sPixmap = "Part_Section";
    LineColor.setValue(Base::Color(0.80F, 0.33F, 0.0F));
    LineWidth.setValue(2.0F);
    ShapeAppearance.setDiffuseColor(0.96F, 0.64F, 0.26F);
    Transparency.setValue(25);
}

ViewProviderSectionAnalysis::~ViewProviderSectionAnalysis() = default;

void ViewProviderSectionAnalysis::attach(App::DocumentObject* object)
{
    ViewProviderPart::attach(object);
    syncDisplayForResultMode();
}

void ViewProviderSectionAnalysis::updateData(const App::Property* prop)
{
    ViewProviderPart::updateData(prop);

    auto* analysis = getObject<Part::SectionAnalysis>();
    if (analysis && prop == &analysis->ResultMode) {
        syncDisplayForResultMode();
    }
}

void ViewProviderSectionAnalysis::syncDisplayForResultMode()
{
    auto* analysis = getObject<Part::SectionAnalysis>();
    if (!analysis) {
        return;
    }

    const char* modeName = displayModeForResultMode(analysis->ResultMode.getValue());
    if (std::string_view(DisplayMode.getValueAsString()) != modeName) {
        DisplayMode.setValue(modeName);
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
