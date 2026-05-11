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

#include <algorithm>
#include <cmath>
#include <numbers>
#include <ranges>
#include <set>

#include <App/ClippingPlane.h>
#include <App/GeoFeature.h>

#include "Application.h"
#include "ClippingPlaneManager.h"
#include "View3DInventor.h"
#include "View3DInventorViewer.h"
#include "ViewProviderClippingPlane.h"

using namespace Gui;

ClippingPlaneManager& ClippingPlaneManager::instance()
{
    static ClippingPlaneManager manager;
    return manager;
}

void ClippingPlaneManager::syncViewProviderState(const App::ClippingPlane* plane) const
{
    if (!plane) {
        return;
    }

    if (auto* vp = Application::Instance->getViewProvider<ViewProviderClippingPlane>(plane)) {
        bool active = std::ranges::any_of(activeClips, [plane](const ActiveClip& clip) {
            return clip.plane == plane && !clip.view.isNull();
        });
        vp->setClipActive(active);
    }
}

void ClippingPlaneManager::activate(View3DInventor* view, App::ClippingPlane* plane)
{
    garbageCollect();
    if (!view || !plane) {
        return;
    }

    deactivate(view);
    apply(view, *plane);
    activeClips.push_back({view, plane});
    syncViewProviderState(plane);
}

void ClippingPlaneManager::deactivate(View3DInventor* view)
{
    garbageCollect();
    if (!view) {
        return;
    }

    auto plane = activePlane(view);
    clear(view);
    std::erase_if(activeClips, [view](const ActiveClip& clip) { return clip.view == view; });
    syncViewProviderState(plane);
}

void ClippingPlaneManager::deactivate(const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    for (const auto& clip : activeClips) {
        if (clip.plane == plane && clip.view) {
            clear(clip.view);
        }
    }

    std::erase_if(activeClips, [plane](const ActiveClip& clip) { return clip.plane == plane; });
    syncViewProviderState(plane);
}

void ClippingPlaneManager::refresh(const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    for (const auto& clip : activeClips) {
        if (clip.plane == plane && clip.view) {
            apply(clip.view, *plane);
        }
    }
}

bool ClippingPlaneManager::isActive(View3DInventor* view, const App::ClippingPlane* plane) const
{
    if (!view || !plane) {
        return false;
    }

    return std::ranges::any_of(activeClips, [view, plane](const ActiveClip& clip) {
        return clip.view == view && clip.plane == plane;
    });
}

App::ClippingPlane* ClippingPlaneManager::activePlane(View3DInventor* view) const
{
    if (!view) {
        return nullptr;
    }

    auto it = std::ranges::find_if(activeClips, [view](const ActiveClip& clip) {
        return clip.view == view;
    });
    return it == activeClips.end() ? nullptr : it->plane;
}

void ClippingPlaneManager::garbageCollect()
{
    std::set<const App::ClippingPlane*> affectedPlanes;
    std::erase_if(activeClips, [&affectedPlanes](const ActiveClip& clip) {
        if (clip.view.isNull()) {
            affectedPlanes.insert(clip.plane);
            return true;
        }
        return false;
    });

    for (const auto* plane : affectedPlanes) {
        syncViewProviderState(plane);
    }
}

Base::Placement ClippingPlaneManager::clipPlacement(const App::ClippingPlane& plane)
{
    Base::Placement placement = App::GeoFeature::getGlobalPlacement(&plane);
    if (plane.Reverse.getValue()) {
        Base::Rotation flip(Base::Vector3d(1, 0, 0), std::numbers::pi_v<double>);
        placement.setRotation(placement.getRotation() * flip);
    }

    // Keep the displayed helper just in front of the effective clip plane to avoid
    // clipping it exactly on its own surface, which causes visible flicker.
    double margin = 0.01;
    if (auto* vp = Application::Instance->getViewProvider<ViewProviderClippingPlane>(&plane)) {
        const auto size = std::max(vp->DisplayLength.getValue(), vp->DisplayHeight.getValue());
        margin = std::max(0.01, static_cast<double>(size) * 1e-4);
    }

    Base::Vector3d normal;
    placement.getRotation().multVec(Base::Vector3d(0, 0, -1), normal);
    placement.setPosition(placement.getPosition() - normal * margin);
    return placement;
}

void ClippingPlaneManager::apply(View3DInventor* view, const App::ClippingPlane& plane)
{
    clear(view);
    if (view) {
        view->getViewer()->toggleClippingPlane(1, false, true, clipPlacement(plane));
    }
}

void ClippingPlaneManager::clear(View3DInventor* view)
{
    if (view && view->getViewer()->hasClippingPlane()) {
        view->getViewer()->toggleClippingPlane(0, false, true);
    }
}
