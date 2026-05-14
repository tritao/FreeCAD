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
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoDrawStyle.h>
#include <Inventor/nodes/SoIndexedLineSet.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoSwitch.h>

#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/GeoFeature.h>

#include "Application.h"
#include "ClippingPlaneManager.h"
#include "Command.h"
#include "Control.h"
#include "Inventor/SoAxisCrossKit.h"
#include "Inventor/So3DAnnotation.h"
#include "Selection/Selection.h"
#include "TaskClippingPlane.h"
#include "View3DInventor.h"
#include "ViewProviderClippingPlane.h"

using namespace Gui;

PROPERTY_SOURCE(Gui::ViewProviderClippingPlane, Gui::ViewProviderGeometryObject)

ViewProviderClippingPlane::ViewProviderClippingPlane()
{
    ADD_PROPERTY_TYPE(
        DisplayLength,
        (100.0F),
        "Clipping Plane",
        App::Prop_None,
        "Displayed width of the clipping plane"
    );
    ADD_PROPERTY_TYPE(
        DisplayHeight,
        (100.0F),
        "Clipping Plane",
        App::Prop_None,
        "Displayed height of the clipping plane"
    );
    ADD_PROPERTY_TYPE(ArrowSize, (35.0F), "Clipping Plane", App::Prop_None, "Displayed normal arrow length");
    ADD_PROPERTY_TYPE(
        AutoSize,
        (true),
        "Clipping Plane",
        App::Prop_None,
        "Keep the clipping plane helper at a constant on-screen size"
    );

    sPixmap = "Std_ToggleClipPlane";
    ShapeAppearance.setDiffuseColor(0.0F, 0.75F, 0.75F);
    Transparency.setValue(80);
}

ViewProviderClippingPlane::~ViewProviderClippingPlane() = default;

void ViewProviderClippingPlane::attach(App::DocumentObject* obj)
{
    inherited::attach(obj);

    overlayCoords = new SoCoordinate3;
    overlayLines = new SoIndexedLineSet;
    overlaySwitch = new SoSwitch;
    overlayMaterial = new SoMaterial;

    overlaySwitch->whichChild = Visibility.getValue() ? SO_SWITCH_ALL : SO_SWITCH_NONE;
    overlayMaterial->transparency = 0.0f;

    static constexpr int32_t lineIndices[] = {0, 1, 2, 3, 0, -1, 4, 5, -1};
    overlayLines->coordIndex.setNum(9);
    overlayLines->coordIndex.setValues(0, 9, lineIndices);
    addDisplayMaskMode(new SoSeparator, "Base");

    auto overlayLineStyle = new SoDrawStyle;
    overlayLineStyle->lineWidth = 2.0F;

    auto overlayRoot = new SoSeparator;
    overlayRoot->addChild(overlayCoords);
    overlayRoot->addChild(overlayMaterial);
    overlayRoot->addChild(overlayLineStyle);
    overlayRoot->addChild(overlayLines);

    overlayScale = new SoShapeScale;
    overlayScale->setPart("shape", overlayRoot);

    auto overlayAnnotation = new So3DAnnotation;
    overlayAnnotation->addChild(overlayScale);

    overlaySwitch->addChild(overlayAnnotation);
    getOrCreateAnnotation()->addChild(overlaySwitch);

    syncOverlayAppearance();
    syncHelperVisibility();
    updateGeometry();
}

void ViewProviderClippingPlane::updateData(const App::Property* prop)
{
    inherited::updateData(prop);

    auto plane = getObject<App::ClippingPlane>();
    if (!plane) {
        return;
    }

    if (prop == &plane->Placement || prop == &plane->Reverse || prop == &plane->ScopeMode
        || prop == &plane->Targets) {
        updateGeometry();
        ClippingPlaneManager::instance().refresh(plane);
    }
}

std::vector<std::string> ViewProviderClippingPlane::getDisplayModes() const
{
    return {"Base"};
}

void ViewProviderClippingPlane::setDisplayMode(const char* ModeName)
{
    if (strcmp(ModeName, "Base") == 0) {
        setDisplayMaskMode("Base");
    }
    inherited::setDisplayMode(ModeName);
}

void ViewProviderClippingPlane::setupContextMenu(QMenu* menu, QObject* receiver, const char* member)
{
    Q_UNUSED(receiver);
    Q_UNUSED(member);

    addDefaultAction(menu, QObject::tr("Edit clipping plane"));

    auto view = qobject_cast<View3DInventor*>(getActiveView());
    auto plane = getObject<App::ClippingPlane>();
    if (view && plane) {
        if (ClippingPlaneManager::instance().isActive(view, plane)) {
            menu->addAction(QObject::tr("Deactivate clipping in active view"), [view, plane]() {
                ClippingPlaneManager::instance().deactivate(view, plane);
            });
        }
        else {
            menu->addAction(QObject::tr("Activate clipping in active view"), [view, plane]() {
                ClippingPlaneManager::instance().activate(view, plane);
            });
        }
    }

    if (plane) {
        const std::string docName = plane->getDocument()->getName();
        const std::string planeName = plane->getNameInDocument();
        menu->addAction(QObject::tr("Create section analysis"), [docName, planeName]() {
            std::vector<std::pair<std::string, std::string>> sources;
            for (const auto& selected :
                 Selection().getCompleteSelection(Gui::ResolveMode::FollowLink)) {
                if (!selected.DocName || !selected.FeatName || docName != selected.DocName
                    || planeName == selected.FeatName) {
                    continue;
                }

                sources.emplace_back(selected.DocName, selected.FeatName);
            }

            Selection().clearSelection(docName.c_str());
            Selection().addSelection(docName.c_str(), planeName.c_str());
            for (const auto& [sourceDoc, sourceObject] : sources) {
                Selection().addSelection(sourceDoc.c_str(), sourceObject.c_str());
            }

            Application::Instance->commandManager().runCommandByName("Part_SectionAnalysis");
        });
    }

    inherited::setupContextMenu(menu, receiver, member);
}

bool ViewProviderClippingPlane::setEdit(int ModNum)
{
    auto* appDoc = getObject() ? getObject()->getDocument() : nullptr;
    editModeActive = true;
    syncHelperVisibility();

    if (ModNum != static_cast<int>(ViewProvider::Default)) {
        if (inherited::setEdit(ModNum)) {
            return true;
        }

        editModeActive = false;
        syncHelperVisibility();
        return false;
    }
    if (Gui::Control().activeDialog(appDoc)) {
        editModeActive = false;
        syncHelperVisibility();
        return false;
    }

    Gui::Control().showDialog(new TaskClippingPlane(this), appDoc);
    return true;
}

void ViewProviderClippingPlane::unsetEdit(int ModNum)
{
    auto* appDoc = getObject() ? getObject()->getDocument() : nullptr;
    ClippingPlaneManager::instance().clearPreviewPlacement(getObject<App::ClippingPlane>());

    if (ModNum == static_cast<int>(ViewProvider::Default)) {
        Gui::Control().closeDialog(appDoc);
    }
    else {
        inherited::unsetEdit(ModNum);
    }

    editModeActive = false;
    syncHelperVisibility();
}

bool ViewProviderClippingPlane::doubleClicked()
{
    return inherited::doubleClicked();
}

bool ViewProviderClippingPlane::startPanelPlaneEdit(
    View3DInventorViewer* viewer,
    std::function<void()> onDragFinish
)
{
    if (!startExternalTransformEdit(viewer)) {
        return false;
    }

    setExternalDragFinishHandler(std::move(onDragFinish));
    setPanelPlaneEditActive(true);
    return true;
}

void ViewProviderClippingPlane::finishPanelPlaneEdit()
{
    ClippingPlaneManager::instance().clearPreviewPlacement(getObject<App::ClippingPlane>());
    finishExternalTransformEdit();
    setPanelPlaneEditActive(false);
}

void ViewProviderClippingPlane::setPanelPlaneEditActive(bool active)
{
    if (panelPlaneEditActive == active) {
        return;
    }

    panelPlaneEditActive = active;
    syncHelperVisibility();
}

bool ViewProviderClippingPlane::isPanelPlaneEditActive() const
{
    return panelPlaneEditActive;
}

void ViewProviderClippingPlane::beforeDelete()
{
    ClippingPlaneManager::instance().clearPreviewPlacement(getObject<App::ClippingPlane>());
    ClippingPlaneManager::instance().deactivate(getObject<App::ClippingPlane>());
    inherited::beforeDelete();
}

void ViewProviderClippingPlane::onChanged(const App::Property* prop)
{
    inherited::onChanged(prop);
    if (prop == &DisplayLength || prop == &DisplayHeight || prop == &ArrowSize || prop == &AutoSize) {
        updateGeometry();
        ClippingPlaneManager::instance().refresh(getObject<App::ClippingPlane>());
    }
    else if (prop == &ShapeAppearance) {
        syncOverlayAppearance();
        ClippingPlaneManager::instance().refresh(getObject<App::ClippingPlane>());
    }
    else if (prop == &Visibility) {
        syncHelperVisibility();
        ClippingPlaneManager::instance().refresh(getObject<App::ClippingPlane>());
    }
}

void ViewProviderClippingPlane::syncOverlayAppearance()
{
    if (!overlayMaterial) {
        return;
    }

    const auto colorValue = ShapeAppearance.getDiffuseColor();
    SbColor color(colorValue.r, colorValue.g, colorValue.b);
    overlayMaterial->ambientColor.setValue(color);
    overlayMaterial->diffuseColor.setValue(color);
}

void ViewProviderClippingPlane::syncHelperVisibility()
{
    if (overlaySwitch) {
        const bool hideDuringActiveEdit = (editModeActive || panelPlaneEditActive)
            && ClippingPlaneManager::instance().isActive(getObject<App::ClippingPlane>());
        overlaySwitch->whichChild = (Visibility.getValue() && !hideDuringActiveEdit)
            ? SO_SWITCH_ALL
            : SO_SWITCH_NONE;
    }
}

void ViewProviderClippingPlane::syncRuntimePreview()
{
    auto* plane = getObject<App::ClippingPlane>();
    if (!plane || !editModeActive) {
        return;
    }

    const auto originPlacement = App::GeoFeature::getGlobalPlacement(plane)
        * getObjectPlacement().inverse();
    const auto previewPlacement = originPlacement
        * (getDraggerPlacement() * getTransformOrigin().inverse());
    ClippingPlaneManager::instance().setPreviewPlacement(plane, previewPlacement);
}

void ViewProviderClippingPlane::updateGeometry()
{
    if (!overlayCoords || !getObject()) {
        return;
    }

    const float halfX = DisplayLength.getValue() * 0.5F;
    const float halfY = DisplayHeight.getValue() * 0.5F;
    float arrow = ArrowSize.getValue();

    if (auto plane = getObject<App::ClippingPlane>(); plane && plane->Reverse.getValue()) {
        arrow = -arrow;
    }

    SbVec3f verts[6] = {
        SbVec3f(halfX, halfY, 0.0F),
        SbVec3f(halfX, -halfY, 0.0F),
        SbVec3f(-halfX, -halfY, 0.0F),
        SbVec3f(-halfX, halfY, 0.0F),
        SbVec3f(0.0F, 0.0F, 0.0F),
        SbVec3f(0.0F, 0.0F, arrow),
    };

    overlayCoords->point.setNum(6);
    overlayCoords->point.setValues(0, 6, verts);

    if (overlayScale) {
        overlayScale->active = AutoSize.getValue();
        overlayScale->scaleFactor = 1.0F;
    }
}

void ViewProviderClippingPlane::onDragMotion()
{
    syncRuntimePreview();
}

void ViewProviderClippingPlane::onDragFinish()
{
    ClippingPlaneManager::instance().clearPreviewPlacement(getObject<App::ClippingPlane>());
}
