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
#include <vector>

#include <App/Placement.h>
#include <FCGlobal.h>

namespace App
{
class ClippingPlane;
}

namespace Gui
{

class View3DInventor;

class GuiExport ClippingPlaneManager
{
public:
    static ClippingPlaneManager& instance();

    void activate(View3DInventor* view, App::ClippingPlane* plane);
    void deactivate(View3DInventor* view);
    void deactivate(const App::ClippingPlane* plane);
    void refresh(const App::ClippingPlane* plane);

    bool isActive(View3DInventor* view, const App::ClippingPlane* plane) const;
    App::ClippingPlane* activePlane(View3DInventor* view) const;

private:
    struct ActiveClip
    {
        QPointer<View3DInventor> view;
        App::ClippingPlane* plane {nullptr};
    };

    std::vector<ActiveClip> activeClips;

    void garbageCollect();
    void syncViewProviderState(const App::ClippingPlane* plane) const;
    static Base::Placement clipPlacement(const App::ClippingPlane& plane);
    static void apply(View3DInventor* view, const App::ClippingPlane& plane);
    static void clear(View3DInventor* view);
};

}  // namespace Gui
