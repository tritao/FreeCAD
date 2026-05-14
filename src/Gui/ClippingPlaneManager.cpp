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
#include <map>
#include <numbers>
#include <ranges>
#include <unordered_set>

#include <Inventor/So3DAnnotation.h>
#include <Inventor/nodes/SoClipPlane.h>
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoDrawStyle.h>
#include <Inventor/nodes/SoIndexedLineSet.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoMatrixTransform.h>
#include <Inventor/nodes/SoSeparator.h>

#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/GeoFeature.h>

#include "Application.h"
#include "ClippingPlaneManager.h"
#include "Inventor/SoAxisCrossKit.h"
#include "Utilities.h"
#include "View3DInventor.h"
#include "View3DInventorViewer.h"
#include "ViewProviderClippingPlane.h"

using namespace Gui;

namespace
{

constexpr long WholeDocumentScope = 0;
constexpr long IncludeOnlyScope = 1;
constexpr long ExcludeScope = 2;
constexpr long HelperSizeModeScreen = 0;
double helperMargin(const App::ClippingPlane& plane)
{
    double margin = 0.01;
    if (auto* vp = Application::Instance->getViewProvider<ViewProviderClippingPlane>(&plane)) {
        const auto size = std::max(vp->DisplayLength.getValue(), vp->DisplayHeight.getValue());
        margin = std::max(0.01, static_cast<double>(size) * 1e-4);
    }
    return margin;
}

SoNode* buildActiveCue(const App::ClippingPlane& plane, const Base::Placement& placement)
{
    auto* vp = Application::Instance->getViewProvider<ViewProviderClippingPlane>(&plane);
    if (!vp || !vp->Visibility.getValue()) {
        return nullptr;
    }

    const float halfX = vp->DisplayLength.getValue() * 0.5F;
    const float halfY = vp->DisplayHeight.getValue() * 0.5F;
    float arrow = vp->ArrowSize.getValue();
    if (plane.Reverse.getValue()) {
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

    auto* coords = new SoCoordinate3;
    coords->point.setNum(6);
    coords->point.setValues(0, 6, verts);

    auto* lines = new SoIndexedLineSet;
    static constexpr int32_t lineIndices[] = {0, 1, 2, 3, 0, -1, 4, 5, -1};
    lines->coordIndex.setNum(9);
    lines->coordIndex.setValues(0, 9, lineIndices);

    const auto colorValue = vp->ShapeAppearance.getDiffuseColor();
    SbColor color(colorValue.r, colorValue.g, colorValue.b);

    auto* material = new SoMaterial;
    material->ambientColor.setValue(color);
    material->diffuseColor.setValue(color);
    material->emissiveColor.setValue(color);
    material->transparency = 0.0F;

    auto* drawStyle = new SoDrawStyle;
    drawStyle->lineWidth = 3.0F;

    auto* shape = new SoSeparator;
    shape->addChild(coords);
    shape->addChild(material);
    shape->addChild(drawStyle);
    shape->addChild(lines);

    auto* scale = new SoShapeScale;
    scale->active = vp->HelperSizeMode.getValue() == HelperSizeModeScreen;
    scale->scaleFactor = 1.0F;
    scale->setPart("shape", shape);

    auto* annotation = new So3DAnnotation;
    annotation->addChild(scale);

    auto* transform = new SoMatrixTransform;
    transform->matrix = Base::convertTo<SbMatrix>(placement.toMatrix());

    auto* root = new SoSeparator;
    root->addChild(transform);
    root->addChild(annotation);
    return root;
}

std::unordered_set<std::string> collectTargetNames(const App::ClippingPlane& plane)
{
    std::unordered_set<std::string> targetNames;
    for (auto* obj : plane.Targets.getValues()) {
        if (obj && obj != &plane) {
            targetNames.emplace(obj->getNameInDocument());
        }
    }

    return targetNames;
}

}  // namespace

ClippingPlaneManager& ClippingPlaneManager::instance()
{
    static ClippingPlaneManager manager;
    return manager;
}

ClippingPlaneManager::ViewState* ClippingPlaneManager::findViewState(View3DInventor* view)
{
    auto it = std::ranges::find_if(viewStates, [view](const ViewState& state) {
        return state.view == view;
    });
    return it == viewStates.end() ? nullptr : &*it;
}

const ClippingPlaneManager::ViewState* ClippingPlaneManager::findViewState(View3DInventor* view) const
{
    auto it = std::ranges::find_if(viewStates, [view](const ViewState& state) {
        return state.view == view;
    });
    return it == viewStates.end() ? nullptr : &*it;
}

void ClippingPlaneManager::activate(View3DInventor* view, App::ClippingPlane* plane)
{
    garbageCollect();
    if (!view || !plane) {
        return;
    }

    auto* state = findViewState(view);
    if (!state) {
        viewStates.push_back(ViewState {view, {}, {}});
        state = &viewStates.back();
    }

    if (std::ranges::find(state->planes, plane) != state->planes.end()) {
        return;
    }

    state->planes.push_back(plane);
    rebuild(*state);
}

void ClippingPlaneManager::deactivate(View3DInventor* view)
{
    garbageCollect();
    if (!view) {
        return;
    }

    auto it = std::ranges::find_if(viewStates, [view](const ViewState& state) {
        return state.view == view;
    });
    if (it == viewStates.end()) {
        return;
    }

    clearApplied(*it);
    viewStates.erase(it);
}

void ClippingPlaneManager::deactivate(View3DInventor* view, const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!view || !plane) {
        return;
    }

    auto* state = findViewState(view);
    if (!state) {
        return;
    }

    auto it = std::ranges::find(state->planes, plane);
    if (it == state->planes.end()) {
        return;
    }

    clearApplied(*state);
    state->planes.erase(it);
    if (state->planes.empty()) {
        std::erase_if(viewStates, [view](const ViewState& current) { return current.view == view; });
        return;
    }

    rebuild(*state);
}

void ClippingPlaneManager::deactivate(const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    for (auto& state : viewStates) {
        auto it = std::ranges::find(state.planes, plane);
        if (it == state.planes.end()) {
            continue;
        }

        clearApplied(state);
        state.planes.erase(it);
        if (!state.planes.empty()) {
            rebuild(state);
        }
    }

    std::erase_if(viewStates, [](const ViewState& state) { return state.planes.empty(); });
}

void ClippingPlaneManager::refresh(const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    for (auto& state : viewStates) {
        if (std::ranges::find(state.planes, plane) != state.planes.end()) {
            rebuild(state);
        }
    }
}

void ClippingPlaneManager::setPreviewPlacement(
    const App::ClippingPlane* plane,
    const Base::Placement& placement
)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    previewPlacements[plane] = placement;
    refresh(plane);
}

void ClippingPlaneManager::clearPreviewPlacement(const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    if (previewPlacements.erase(plane) > 0) {
        refresh(plane);
    }
}

bool ClippingPlaneManager::isActive(View3DInventor* view, const App::ClippingPlane* plane) const
{
    if (!view || !plane) {
        return false;
    }

    auto* state = findViewState(view);
    return state && std::ranges::find(state->planes, plane) != state->planes.end();
}

bool ClippingPlaneManager::isActive(const App::ClippingPlane* plane) const
{
    if (!plane) {
        return false;
    }

    return std::ranges::any_of(viewStates, [plane](const ViewState& state) {
        return std::ranges::find(state.planes, plane) != state.planes.end();
    });
}

std::vector<App::ClippingPlane*> ClippingPlaneManager::activePlanes(View3DInventor* view) const
{
    auto* state = findViewState(view);
    return state ? state->planes : std::vector<App::ClippingPlane*> {};
}

App::ClippingPlane* ClippingPlaneManager::activePlane(View3DInventor* view) const
{
    auto planes = activePlanes(view);
    return planes.empty() ? nullptr : planes.back();
}

void ClippingPlaneManager::garbageCollect()
{
    std::erase_if(viewStates, [](const ViewState& state) { return state.view.isNull(); });
}

Base::Placement ClippingPlaneManager::planePlacement(const App::ClippingPlane& plane) const
{
    Base::Placement placement;
    if (auto it = previewPlacements.find(&plane); it != previewPlacements.end()) {
        placement = it->second;
    }
    else {
        placement = App::GeoFeature::getGlobalPlacement(&plane);
    }

    if (plane.Reverse.getValue()) {
        Base::Rotation flip(Base::Vector3d(1, 0, 0), std::numbers::pi_v<double>);
        placement.setRotation(placement.getRotation() * flip);
    }
    return placement;
}

Base::Placement ClippingPlaneManager::clipPlacement(const App::ClippingPlane& plane) const
{
    Base::Placement placement = planePlacement(plane);

    Base::Vector3d normal;
    placement.getRotation().multVec(Base::Vector3d(0, 0, -1), normal);
    placement.setPosition(placement.getPosition() - normal * helperMargin(plane));
    return placement;
}

Base::Placement ClippingPlaneManager::helperPlacement(const App::ClippingPlane& plane) const
{
    Base::Placement placement = planePlacement(plane);
    Base::Vector3d normal;
    placement.getRotation().multVec(Base::Vector3d(0, 0, -1), normal);

    // Keep the visible helper fully on the kept side of the clip plane.
    placement.setPosition(placement.getPosition() - normal * (helperMargin(plane) * 2.0));
    return placement;
}

SoNode* ClippingPlaneManager::buildClipNode(const App::ClippingPlane& plane, const char* name) const
{
    auto* clip = new SoClipPlane;
    clip->setName(name);

    Base::Placement placement = clipPlacement(plane);
    Base::Vector3d dir;
    placement.getRotation().multVec(Base::Vector3d(0, 0, -1), dir);
    Base::Vector3d base = placement.getPosition();
    clip->plane.setValue(SbPlane(Base::convertTo<SbVec3f>(dir), Base::convertTo<SbVec3f>(base)));
    return clip;
}

void ClippingPlaneManager::clearApplied(ViewState& state)
{
    if (!state.view || !state.view->getViewer()) {
        state.wrappedTargets.clear();
        return;
    }

    auto* view = state.view.data();
    auto* viewer = view->getViewer();

    for (auto* plane : state.planes) {
        if (!plane) {
            continue;
        }

        viewer->removeRuntimeNode(plane, View3DInventorViewer::RuntimeNodeLayer::Clip);
        viewer->removeRuntimeNode(plane, View3DInventorViewer::RuntimeNodeLayer::Foreground);
    }

    std::ranges::sort(state.wrappedTargets, [](const WrappedTarget& left, const WrappedTarget& right) {
        if (left.parent == right.parent) {
            return left.index < right.index;
        }
        return left.parent < right.parent;
    });

    auto* doc = view->getAppDocument();
    for (const auto& wrapped : state.wrappedTargets) {
        if (!wrapped.parent) {
            continue;
        }

        auto* obj = doc ? doc->getObject(wrapped.objectName.c_str()) : nullptr;
        auto* vp = obj ? Application::Instance->getViewProvider(obj) : nullptr;
        auto* root = vp ? vp->getRoot() : nullptr;

        if (wrapped.wrapper && root) {
            int childIndex = wrapped.wrapper->findChild(root);
            if (childIndex >= 0) {
                wrapped.wrapper->removeChild(childIndex);
            }
        }

        int wrapperIndex = wrapped.wrapper ? wrapped.parent->findChild(wrapped.wrapper) : -1;
        if (wrapperIndex >= 0) {
            wrapped.parent->removeChild(wrapperIndex);
        }

        if (root && wrapped.parent->findChild(root) < 0) {
            int insertIndex = std::min(wrapped.index, wrapped.parent->getNumChildren());
            wrapped.parent->insertChild(root, insertIndex);
        }
    }

    state.wrappedTargets.clear();
}

void ClippingPlaneManager::rebuild(ViewState& state)
{
    clearApplied(state);

    if (!state.view || !state.view->getViewer() || state.planes.empty()) {
        return;
    }

    auto* view = state.view.data();
    auto* viewer = view->getViewer();
    auto* doc = view->getAppDocument();
    if (!doc) {
        return;
    }

    std::vector<App::ClippingPlane*> wholeDocumentPlanes;
    std::map<std::string, std::vector<App::ClippingPlane*>> scopedApplications;

    for (auto* plane : state.planes) {
        if (!plane) {
            continue;
        }

        auto targetNames = collectTargetNames(*plane);
        switch (plane->ScopeMode.getValue()) {
            case WholeDocumentScope:
                wholeDocumentPlanes.push_back(plane);
                break;
            case IncludeOnlyScope:
                for (const auto& name : targetNames) {
                    auto* obj = doc->getObject(name.c_str());
                    auto* vp = obj ? Application::Instance->getViewProvider(obj) : nullptr;
                    if (vp && vp->getRoot()) {
                        scopedApplications[name].push_back(plane);
                    }
                }
                break;
            case ExcludeScope:
                if (targetNames.empty()) {
                    wholeDocumentPlanes.push_back(plane);
                    break;
                }

                for (auto* obj : doc->getObjects()) {
                    if (!obj || obj == plane) {
                        continue;
                    }

                    const auto name = obj->getNameInDocument();
                    if (targetNames.contains(name)) {
                        continue;
                    }

                    auto* vp = Application::Instance->getViewProvider(obj);
                    if (vp && vp->getRoot()) {
                        scopedApplications[name].push_back(plane);
                    }
                }
                break;
            default:
                wholeDocumentPlanes.push_back(plane);
                break;
        }
    }

    for (auto* plane : wholeDocumentPlanes) {
        viewer->addRuntimeNode(
            plane,
            buildClipNode(*plane, "FCWholeClipPlaneRuntime"),
            View3DInventorViewer::RuntimeNodeLayer::Clip
        );
    }

    for (const auto& [name, planes] : scopedApplications) {
        auto* obj = doc->getObject(name.c_str());
        auto* vp = obj ? Application::Instance->getViewProvider(obj) : nullptr;
        if (!vp || !vp->getRoot()) {
            continue;
        }

        auto location = viewer->locateViewProvider(vp);
        if (!location) {
            continue;
        }

        auto* wrapper = new SoSeparator;
        wrapper->setName("FCScopedClipPlaneRuntime");
        for (auto* plane : planes) {
            wrapper->addChild(buildClipNode(*plane, "FCScopedClipPlane"));
        }

        location.parent->removeChild(location.index);
        wrapper->addChild(vp->getRoot());
        location.parent->insertChild(wrapper, location.index);
        state.wrappedTargets.push_back({name, location.parent, location.index, wrapper});
    }

    for (auto* plane : state.planes) {
        if (plane) {
            installActiveCue(view, *plane);
        }
    }
}

void ClippingPlaneManager::installActiveCue(View3DInventor* view, const App::ClippingPlane& plane) const
{
    if (view && view->getViewer()) {
        view->getViewer()->addRuntimeNode(
            &plane,
            buildActiveCue(plane, helperPlacement(plane)),
            View3DInventorViewer::RuntimeNodeLayer::Foreground
        );
    }
}
