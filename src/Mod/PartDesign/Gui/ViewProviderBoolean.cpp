// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2013 Jan Rheinländer                                    *
 *                                   <jrheinlaender@users.sourceforge.net> *
 *   Copyright (c) 2025 Kacper Donat <kacper@kadet.net>                    *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#include <QMenu>
#include <Inventor/nodes/SoTransform.h>

#include "ViewProviderBoolean.h"

#include "StyleParameters.h"
#include "TaskBooleanParameters.h"
#include "ViewProviderBody.h"

#include <Base/ServiceProvider.h>
#include <Base/Tools.h>
#include <Mod/PartDesign/App/FeatureBoolean.h>
#include <App/Document.h>
#include <App/GroupExtension.h>
#include <Gui/ActiveObjectList.h>
#include <Gui/Application.h>
#include <Gui/Control.h>
#include <Gui/Command.h>
#include <Gui/Document.h>
#include <Gui/MainWindow.h>
#include <Gui/MDIView.h>
#include <Gui/Utilities.h>
#include <Gui/ViewProviderDocumentObject.h>
#include <Mod/PartDesign/App/Body.h>
#include <Mod/Sketcher/Gui/TaskDlgEditSketch.h>


using namespace PartDesignGui;

PROPERTY_SOURCE_WITH_EXTENSIONS(PartDesignGui::ViewProviderBoolean, PartDesignGui::ViewProvider)

const char* PartDesignGui::ViewProviderBoolean::DisplayEnum[] = {"Result", "Tools", nullptr};


ViewProviderBoolean::ViewProviderBoolean()
    : pcToolsPreview(new SoGroup)
    , pcBasePreviewToggle(new SoToggleSwitch)
{
    sPixmap = "PartDesign_Boolean.svg";

    ViewProviderGeoFeatureGroupExtension::initExtension(this);

    ADD_PROPERTY(Display, ((long)0));
    Display.setEnums(DisplayEnum);
}

ViewProviderBoolean::~ViewProviderBoolean() = default;

void ViewProviderBoolean::attach(App::DocumentObject* pcObject)
{
    ViewProvider::attach(pcObject);
    _bodyActivationConn = getDocument()->signalActivatedViewProvider.connect(
        [this](const Gui::ViewProviderDocumentObject* vp, const char* name) {
            onBodyActivated(vp, name);
        }
    );
}

void ViewProviderBoolean::update(const App::Property* prop)
{
    if (_shownBodyName.empty() || prop == &getObject()->Visibility) {
        Gui::ViewProviderDocumentObject::update(prop);
        return;
    }

    // A tool body is temporarily shown via setDisplayMaskMode("Group").
    // The normal ViewProvider::update() briefly sets pcModeSwitch=-1 (hide/show
    // optimization) which hides the entire Group subtree, making the tool body flash.
    // Call updateData() directly to skip that cycle. User1 on Visibility suppresses
    // VP<->App Visibility syncing and extensionShow/Hide member propagation.
    if (isUpdatesEnabled()) {
        Base::ObjectStatusLocker<App::Property::Status, App::Property> guard(
            App::Property::User1,
            &Visibility
        );
        updateData(prop);
    }
}

const char* ViewProviderBoolean::getConfiguredDisplayMode() const
{
    if (Display.getValue() != 0) {
        return "Group";
    }

    if (auto bodyViewProvider = getBodyViewProvider()) {
        return bodyViewProvider->DisplayMode.getValueAsString();
    }

    return getDefaultDisplayMode();
}

// Returns true if target is contained anywhere inside container's Group hierarchy.
static bool containsRecursively(App::DocumentObject* container, App::DocumentObject* target)
{
    auto* ext = container->getExtensionByType<App::GroupExtension>(/*no_except=*/true);
    if (!ext) {
        return false;
    }
    for (auto* member : ext->Group.getValues()) {
        if (!member) {
            continue;
        }
        if (member == target || containsRecursively(member, target)) {
            return true;
        }
    }
    return false;
}

static void setBodyVisible(App::DocumentObject* body, bool visible)
{
    auto* rawVP = Gui::Application::Instance->getViewProvider(body);
    auto* vpdo = dynamic_cast<Gui::ViewProviderDocumentObject*>(rawVP);
    if (!vpdo) {
        return;
    }

    Base::ObjectStatusLocker<App::Property::Status, App::Property> guard(
        App::Property::User1,
        &vpdo->Visibility
    );
    if (visible) {
        rawVP->Gui::ViewProvider::show();
    }
    else {
        rawVP->Gui::ViewProvider::hide();
    }
}

void ViewProviderBoolean::restoreShownBody(bool restoreBooleanMode)
{
    if (_shownBodyName.empty()) {
        return;
    }

    auto* feature = getObject<PartDesign::Boolean>();
    App::DocumentObject* shownBody = feature
        ? feature->getDocument()->getObject(_shownBodyName.c_str())
        : nullptr;

    if (shownBody) {
        if (_indirectActivation) {
            auto* bodyVP = Gui::Application::Instance->getViewProvider(shownBody);
            const bool keepVisible = _shownBodyWasVisible;
            if (auto* vpBody = dynamic_cast<ViewProviderBody*>(bodyVP)) {
                vpBody->onChanged(&vpBody->DisplayModeBody);
                if (!keepVisible) {
                    setBodyVisible(shownBody, false);
                }
            }
            else if (bodyVP) {
                setBodyVisible(shownBody, keepVisible);
            }
        }
        else if (restoreBooleanMode) {
            setBodyVisible(shownBody, _shownBodyWasVisible);
        }
        else if (!_shownBodyWasVisible) {
            setBodyVisible(shownBody, false);
        }
    }

    if (restoreBooleanMode && Visibility.getValue()) {
        setDisplayMode(getConfiguredDisplayMode());
    }

    _shownBodyName.clear();
    _shownBodyWasVisible = false;
    _indirectActivation = false;
}

void ViewProviderBoolean::syncActiveBodyVisibility()
{
    auto* activeView = getDocument()->getActiveView();
    if (!activeView) {
        onBodyActivated(nullptr, PDBODYKEY);
        return;
    }

    auto* activeBody = activeView->getActiveObject<App::DocumentObject*>(PDBODYKEY);
    auto* activeBodyVP = activeBody ? dynamic_cast<Gui::ViewProviderDocumentObject*>(
                                          Gui::Application::Instance->getViewProvider(activeBody)
                                      )
                                    : nullptr;

    onBodyActivated(activeBodyVP, PDBODYKEY);
}

void ViewProviderBoolean::onBodyActivated(const Gui::ViewProviderDocumentObject* vp, const char* name)
{
    if (strcmp(name, PDBODYKEY) != 0) {
        return;
    }

    auto* feature = getObject<PartDesign::Boolean>();
    if (!feature) {
        return;
    }

    if (!Visibility.getValue()) {
        restoreShownBody(false);
        return;
    }

    const auto& group = feature->Group.getValues();
    App::DocumentObject* activatedBody = vp ? vp->getObject() : nullptr;

    // Find the direct Group member that is, or transitively contains, the activated body.
    App::DocumentObject* matchingMember = nullptr;
    if (activatedBody) {
        for (auto* obj : group) {
            if (obj == activatedBody || containsRecursively(obj, activatedBody)) {
                matchingMember = obj;
                break;
            }
        }
    }

    const bool indirectActivation = matchingMember && matchingMember != activatedBody;
    if (matchingMember && _shownBodyName == matchingMember->getNameInDocument()
        && _indirectActivation == indirectActivation) {
        return;
    }

    restoreShownBody();

    if (!matchingMember) {
        return;
    }

    auto* rawVP = Gui::Application::Instance->getViewProvider(matchingMember);
    if (!dynamic_cast<Gui::ViewProviderDocumentObject*>(rawVP)) {
        return;
    }

    setDisplayMode("Group");

    _shownBodyName = matchingMember->getNameInDocument();
    _shownBodyWasVisible = rawVP->Gui::ViewProvider::isShow();
    _indirectActivation = indirectActivation;

    if (_indirectActivation) {
        // For nested Booleans, the activated body may live inside an intermediate body that is
        // itself a direct Group member.
        rawVP->setDisplayMaskMode("Group");
    }
    else {
        // Bypass ViewProviderBody::show() to avoid mutating App Visibility while the active body is
        // only being exposed temporarily through the Boolean.
        setBodyVisible(matchingMember, true);
    }
}

void ViewProviderBoolean::setupContextMenu(QMenu* menu, QObject* receiver, const char* member)
{
    addDefaultAction(menu, QObject::tr("Edit Boolean"));

    ViewProvider::setupContextMenu(menu, receiver, member);
}

bool ViewProviderBoolean::onDelete(const std::vector<std::string>& s)
{
    auto* feature = getObject<PartDesign::Boolean>();

    // if abort command deleted the object the bodies are visible again
    for (auto body : feature->Group.getValues()) {
        if (auto vp = Gui::Application::Instance->getViewProvider(body)) {
            vp->show();
        }
    }

    return ViewProvider::onDelete(s);
}

const char* ViewProviderBoolean::getDefaultDisplayMode() const
{
    return "Flat Lines";
}

void ViewProviderBoolean::onChanged(const App::Property* prop)
{

    ViewProvider::onChanged(prop);

    if (prop == &Display) {
        if (_shownBodyName.empty()) {
            setDisplayMode(getConfiguredDisplayMode());
        }
    }

    if (prop == &Visibility) {
        updateBasePreviewVisibility();
        if (Visibility.getValue()) {
            syncActiveBodyVisibility();
        }
        else {
            restoreShownBody(false);
        }
    }
}

void ViewProviderBoolean::updateData(const App::Property* prop)
{
    auto feature = getObject<PartDesign::Boolean>();

    if (prop == &feature->Type) {
        const auto* styleParameterManager
            = Base::provideService<Gui::StyleParameters::ParameterManager>();
        const auto type = feature->Type.getValueAsString();

        const std::map<std::string_view, Gui::StyleParameters::ParameterDefinition<Base::Color>> lookup {
            {"Cut", StyleParameters::PreviewSubtractiveColor},
            {"Common", StyleParameters::PreviewCommonColor},
            {"Fuse", StyleParameters::PreviewAdditiveColor},
        };

        if (lookup.contains(type)) {
            PreviewColor.setValue(styleParameterManager->resolve(lookup.at(type)));
        }

        updateBasePreviewVisibility();
    }
    else if (prop == &feature->Group) {
        syncActiveBodyVisibility();
    }

    ViewProvider::updateData(prop);
}

void ViewProviderBoolean::attachPreview()
{
    ViewProvider::attachPreview();

    pcPreviewRoot->addChild(this->pcToolsPreview);
    pcPreviewRoot->addChild(this->pcBasePreviewToggle);
}

void ViewProviderBoolean::updatePreview()
{
    const auto* styleParameterManager = Base::provideService<Gui::StyleParameters::ParameterManager>();

    const double toolOpacity = styleParameterManager->resolve(StyleParameters::PreviewToolOpacity).value;
    const double toolTransparency = 1.0 - toolOpacity;

    auto boolean = getObject<PartDesign::Boolean>();

    if (!boolean) {
        return;
    }

    const auto addToolPreview = [this, toolTransparency](App::DocumentObject* tool) {
        const auto feature = freecad_cast<Part::Feature*>(tool);

        if (!feature) {
            return;
        }

        Part::TopoShape toolShape = feature->Shape.getShape();

        auto pcToolPreview = new PartGui::SoPreviewShape;
        updatePreviewShape(toolShape, pcToolPreview);

        pcToolPreview->transparency.setValue(static_cast<float>(toolTransparency));
        pcToolPreview->color.connectFrom(&pcPreviewShape->color);
        pcToolPreview->lineWidth.connectFrom(&pcPreviewShape->lineWidth);

        pcToolsPreview->addChild(pcToolPreview);
    };

    const auto addBaseShapePreview = [this, toolTransparency, boolean]() {
        auto baseFeature = dynamic_cast<PartDesign::Feature*>(boolean->BaseFeature.getValue());
        if (!baseFeature) {
            return;
        }

        auto baseFeatureViewProvider = freecad_cast<ViewProvider*>(
            Gui::Application::Instance->getViewProvider(baseFeature)
        );
        if (!baseFeatureViewProvider) {
            return;
        }

        auto pcBaseShapePreview = new PartGui::SoPreviewShape;
        updatePreviewShape(baseFeature->Shape.getShape(), pcBaseShapePreview);

        pcBaseShapePreview->transparency.setValue(static_cast<float>(toolTransparency));
        pcBaseShapePreview->color.setValue(
            baseFeatureViewProvider->ShapeAppearance.getDiffuseColor().asValue<SbColor>()
        );
        pcBaseShapePreview->lineWidth.connectFrom(&pcPreviewShape->lineWidth);

        pcBasePreviewToggle->addChild(pcBaseShapePreview);
    };

    try {
        const auto& tools = boolean->Group.getValues();

        if (tools.empty()) {
            return;
        }

        Gui::coinRemoveAllChildren(pcToolsPreview);
        Gui::coinRemoveAllChildren(pcBasePreviewToggle);

        addBaseShapePreview();
        std::ranges::for_each(tools, addToolPreview);
    }
    catch (const Base::Exception& e) {
        e.reportException();
    }

    ViewProvider::updatePreview();
}

TaskDlgFeatureParameters* ViewProviderBoolean::getEditDialog()
{
    return new TaskDlgBooleanParameters(this);
}

void ViewProviderBoolean::updateBasePreviewVisibility()
{
    auto feature = getObject<PartDesign::Boolean>();

    // enable base preview for Common operation only and when the final result is shown
    pcBasePreviewToggle->on = strcmp(feature->Type.getValueAsString(), "Common") == 0
        && Visibility.getValue();
}
