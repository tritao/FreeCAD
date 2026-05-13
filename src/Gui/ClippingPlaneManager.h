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

#pragma once

#include <QPointer>
#include <string>
#include <unordered_map>
#include <vector>

#include <App/Placement.h>
#include <FCGlobal.h>

namespace App
{
class ClippingPlane;
}

class SoGroup;
class SoNode;

namespace Gui
{

class View3DInventor;

class GuiExport ClippingPlaneManager
{
public:
    static ClippingPlaneManager& instance();

    void activate(View3DInventor* view, App::ClippingPlane* plane);
    void deactivate(View3DInventor* view);
    void deactivate(View3DInventor* view, const App::ClippingPlane* plane);
    void deactivate(const App::ClippingPlane* plane);
    void refresh(const App::ClippingPlane* plane);
    void setPreviewPlacement(const App::ClippingPlane* plane, const Base::Placement& placement);
    void clearPreviewPlacement(const App::ClippingPlane* plane);

    bool isActive(View3DInventor* view, const App::ClippingPlane* plane) const;
    bool isActive(const App::ClippingPlane* plane) const;
    std::vector<App::ClippingPlane*> activePlanes(View3DInventor* view) const;
    App::ClippingPlane* activePlane(View3DInventor* view) const;

private:
    struct WrappedTarget
    {
        std::string objectName;
        SoGroup* parent {nullptr};
        int index {-1};
        SoGroup* wrapper {nullptr};
    };

    struct ViewState
    {
        QPointer<View3DInventor> view;
        std::vector<App::ClippingPlane*> planes;
        std::vector<WrappedTarget> wrappedTargets;
    };

    std::vector<ViewState> viewStates;
    std::unordered_map<const App::ClippingPlane*, Base::Placement> previewPlacements;

    void garbageCollect();
    ViewState* findViewState(View3DInventor* view);
    const ViewState* findViewState(View3DInventor* view) const;
    Base::Placement planePlacement(const App::ClippingPlane& plane) const;
    Base::Placement clipPlacement(const App::ClippingPlane& plane) const;
    Base::Placement helperPlacement(const App::ClippingPlane& plane) const;
    SoNode* buildClipNode(const App::ClippingPlane& plane, const char* name) const;
    void installActiveCue(View3DInventor* view, const App::ClippingPlane& plane) const;
    static void clearApplied(ViewState& state);
    void rebuild(ViewState& state);
};

}  // namespace Gui
