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

#include <map>
#include <string>

#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/SavedView.h>
#include <Base/Exception.h>

#include "Application.h"
#include "ClippingPlaneManager.h"
#include "SavedViewManager.h"
#include "View3DInventor.h"
#include "ViewProviderDocumentObject.h"

using namespace Gui;

namespace
{

std::map<std::string, std::string> captureVisibilityState(const App::SavedView& savedView)
{
    std::map<std::string, std::string> state;
    auto* doc = savedView.getDocument();
    if (!doc) {
        return state;
    }

    for (auto* obj : doc->getObjects()) {
        if (obj == &savedView) {
            continue;
        }

        auto* vp = Application::Instance->getViewProvider<ViewProviderDocumentObject>(obj);
        if (!vp) {
            continue;
        }

        state.emplace(obj->getNameInDocument(), vp->Visibility.getValue() ? "True" : "False");
    }

    return state;
}

void applyVisibilityState(const App::SavedView& savedView)
{
    auto* doc = savedView.getDocument();
    if (!doc) {
        return;
    }

    for (const auto& [name, visible] : savedView.VisibilityState.getValues()) {
        auto* obj = doc->getObject(name.c_str());
        if (!obj || obj == &savedView) {
            continue;
        }

        auto* vp = Application::Instance->getViewProvider<ViewProviderDocumentObject>(obj);
        if (!vp) {
            continue;
        }

        if (visible == "True") {
            vp->show();
        }
        else {
            vp->hide();
        }
    }
}

}  // namespace

bool SavedViewManager::capture(View3DInventor* view, App::SavedView* savedView)
{
    if (!view || !savedView || view->getAppDocument() != savedView->getDocument()) {
        return false;
    }

    savedView->CameraState.setValue(view->getCamera());
    savedView->VisibilityState.setValues(captureVisibilityState(*savedView));
    savedView->ClipPlane.setValue(ClippingPlaneManager::instance().activePlane(view));
    return true;
}

bool SavedViewManager::restore(View3DInventor* view, const App::SavedView* savedView)
{
    if (!view || !savedView || view->getAppDocument() != savedView->getDocument()) {
        return false;
    }

    if (savedView->RestoreCamera.getValue()) {
        const char* camera = savedView->CameraState.getValue();
        if (camera && *camera) {
            try {
                view->setCamera(camera);
            }
            catch (const Base::Exception&) {
                return false;
            }
        }
    }

    if (savedView->RestoreVisibility.getValue()) {
        applyVisibilityState(*savedView);
    }

    if (savedView->RestoreClipping.getValue()) {
        auto* plane = freecad_cast<App::ClippingPlane*>(savedView->ClipPlane.getValue());
        if (plane) {
            ClippingPlaneManager::instance().activate(view, plane);
        }
        else {
            ClippingPlaneManager::instance().deactivate(view);
        }
    }

    return true;
}
