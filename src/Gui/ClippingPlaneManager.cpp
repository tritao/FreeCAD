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
#include <unordered_set>

#include <Inventor/nodes/SoClipPlane.h>
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoDrawStyle.h>
#include <Inventor/nodes/SoIndexedLineSet.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoMatrixTransform.h>
#include <Inventor/nodes/SoSeparator.h>

#include <Inventor/So3DAnnotation.h>
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

SoNode* buildActiveCue(const App::ClippingPlane& plane)
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

    auto coords = new SoCoordinate3;
    coords->point.setNum(6);
    coords->point.setValues(0, 6, verts);

    auto lines = new SoIndexedLineSet;
    static constexpr int32_t lineIndices[] = {0, 1, 2, 3, 0, -1, 4, 5, -1};
    lines->coordIndex.setNum(9);
    lines->coordIndex.setValues(0, 9, lineIndices);

    const auto colorValue = vp->ShapeAppearance.getDiffuseColor();
    SbColor color(colorValue.r, colorValue.g, colorValue.b);

    auto material = new SoMaterial;
    material->ambientColor.setValue(color);
    material->diffuseColor.setValue(color);
    material->emissiveColor.setValue(color);
    material->transparency = 0.0f;

    auto drawStyle = new SoDrawStyle;
    drawStyle->lineWidth = 3.0F;

    auto shape = new SoSeparator;
    shape->addChild(coords);
    shape->addChild(material);
    shape->addChild(drawStyle);
    shape->addChild(lines);

    auto scale = new SoShapeScale;
    scale->active = vp->AutoSize.getValue();
    scale->scaleFactor = 1.0F;
    scale->setPart("shape", shape);

    auto annotation = new So3DAnnotation;
    annotation->addChild(scale);

    auto transform = new SoMatrixTransform;
    transform->matrix = Base::convertTo<SbMatrix>(
        App::GeoFeature::getGlobalPlacement(&plane).toMatrix()
    );

    auto root = new SoSeparator;
    root->addChild(transform);
    root->addChild(annotation);
    return root;
}

}  // namespace

ClippingPlaneManager& ClippingPlaneManager::instance()
{
    static ClippingPlaneManager manager;
    return manager;
}

void ClippingPlaneManager::activate(View3DInventor* view, App::ClippingPlane* plane)
{
    garbageCollect();
    if (!view || !plane) {
        return;
    }

    deactivate(view);
    ActiveClip clip;
    clip.view = view;
    clip.plane = plane;
    apply(clip);
    activeClips.push_back(std::move(clip));
}

void ClippingPlaneManager::deactivate(View3DInventor* view)
{
    garbageCollect();
    if (!view) {
        return;
    }

    auto it = std::ranges::find_if(activeClips, [view](const ActiveClip& clip) {
        return clip.view == view;
    });
    if (it == activeClips.end()) {
        return;
    }

    clear(*it);
    activeClips.erase(it);
}

void ClippingPlaneManager::deactivate(const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    for (auto& clip : activeClips) {
        if (clip.plane == plane && clip.view) {
            clear(clip);
        }
    }

    std::erase_if(activeClips, [plane](const ActiveClip& clip) { return clip.plane == plane; });
}

void ClippingPlaneManager::refresh(const App::ClippingPlane* plane)
{
    garbageCollect();
    if (!plane) {
        return;
    }

    for (auto& clip : activeClips) {
        if (clip.plane == plane && clip.view) {
            clear(clip);
            apply(clip);
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
    std::erase_if(activeClips, [](const ActiveClip& clip) { return clip.view.isNull(); });
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

SoNode* ClippingPlaneManager::buildScopedClipNode(const App::ClippingPlane& plane)
{
    auto* root = new SoSeparator;
    root->setName("FCScopedClipPlaneRuntime");

    auto* clip = new SoClipPlane;
    clip->setName("FCScopedClipPlane");

    Base::Placement placement = clipPlacement(plane);
    Base::Vector3d dir;
    placement.getRotation().multVec(Base::Vector3d(0, 0, -1), dir);
    Base::Vector3d base = placement.getPosition();
    clip->plane.setValue(SbPlane(Base::convertTo<SbVec3f>(dir), Base::convertTo<SbVec3f>(base)));

    root->addChild(clip);
    return root;
}

std::vector<ClippingPlaneManager::ActiveClip::MovedTarget> ClippingPlaneManager::resolveScopedTargets(
    View3DInventor* view,
    const App::ClippingPlane& plane
)
{
    std::vector<ActiveClip::MovedTarget> targets;
    if (!view || !view->getViewer()) {
        return targets;
    }

    const auto scopeMode = plane.ScopeMode.getValue();
    if (scopeMode == WholeDocumentScope) {
        return targets;
    }

    std::unordered_set<std::string> targetNames;
    for (auto* obj : plane.Targets.getValues()) {
        if (obj && obj != &plane) {
            targetNames.emplace(obj->getNameInDocument());
        }
    }

    if (scopeMode == IncludeOnlyScope) {
        for (const auto& name : targetNames) {
            auto* obj = view->getAppDocument()->getObject(name.c_str());
            auto* vp = obj ? Application::Instance->getViewProvider(obj) : nullptr;
            if (!vp || !vp->getRoot()) {
                continue;
            }

            auto location = view->getViewer()->locateViewProvider(vp);
            if (!location) {
                continue;
            }

            targets.push_back({name, location.parent, location.index});
        }
        return targets;
    }

    if (scopeMode != ExcludeScope) {
        return targets;
    }

    auto* doc = view->getAppDocument();
    if (!doc) {
        return targets;
    }

    std::unordered_set<std::string> seen;
    for (auto* obj : doc->getObjects()) {
        if (!obj || obj == &plane) {
            continue;
        }

        const auto name = obj->getNameInDocument();
        if (targetNames.contains(name) || !seen.emplace(name).second) {
            continue;
        }

        auto* vp = Application::Instance->getViewProvider(obj);
        if (!vp || !vp->getRoot()) {
            continue;
        }

        auto location = view->getViewer()->locateViewProvider(vp);
        if (!location) {
            continue;
        }

        targets.push_back({name, location.parent, location.index});
    }

    return targets;
}

void ClippingPlaneManager::apply(ActiveClip& clip)
{
    if (!clip.view || !clip.view->getViewer() || !clip.plane) {
        return;
    }

    clip.wholeDocument = true;
    clip.movedTargets.clear();

    const auto scopeMode = clip.plane->ScopeMode.getValue();
    const bool includeOnlyScope = scopeMode == IncludeOnlyScope;
    const bool excludeScope = scopeMode == ExcludeScope;
    const bool hasRequestedTargets = std::ranges::any_of(
        clip.plane->Targets.getValues(),
        [plane = clip.plane](const App::DocumentObject* obj) { return obj && obj != plane; }
    );
    auto targets = resolveScopedTargets(clip.view, *clip.plane);
    if (includeOnlyScope && targets.empty()) {
        clip.wholeDocument = false;
        installActiveCue(clip.view, *clip.plane);
        return;
    }
    if (excludeScope && hasRequestedTargets && targets.empty()) {
        clip.wholeDocument = false;
        installActiveCue(clip.view, *clip.plane);
        return;
    }

    if (!targets.empty()) {
        auto* scopedRoot = static_cast<SoSeparator*>(buildScopedClipNode(*clip.plane));
        if (scopedRoot) {
            auto removeOrder = targets;
            std::ranges::sort(removeOrder, [](const auto& left, const auto& right) {
                if (left.parent == right.parent) {
                    return left.index > right.index;
                }
                return left.parent < right.parent;
            });

            for (const auto& target : removeOrder) {
                auto* obj = clip.view->getAppDocument()->getObject(target.objectName.c_str());
                auto* vp = obj ? Application::Instance->getViewProvider(obj) : nullptr;
                if (!vp || !target.parent) {
                    continue;
                }
                auto location = clip.view->getViewer()->locateViewProvider(vp);
                if (location && location.parent == target.parent && location.index >= 0) {
                    target.parent->removeChild(location.index);
                }
            }

            for (const auto& target : targets) {
                auto* obj = clip.view->getAppDocument()->getObject(target.objectName.c_str());
                auto* vp = obj ? Application::Instance->getViewProvider(obj) : nullptr;
                if (vp && vp->getRoot()) {
                    scopedRoot->addChild(vp->getRoot());
                }
            }

            clip.wholeDocument = false;
            clip.movedTargets = std::move(targets);
            clip.view->getViewer()->addRuntimeNode(
                clip.plane,
                scopedRoot,
                View3DInventorViewer::RuntimeNodeLayer::Scene
            );
            installActiveCue(clip.view, *clip.plane);
            return;
        }
    }

    clip.view->getViewer()->toggleClippingPlane(1, false, true, clipPlacement(*clip.plane));
    installActiveCue(clip.view, *clip.plane);
}

void ClippingPlaneManager::clear(ActiveClip& clip)
{
    if (!clip.view || !clip.view->getViewer() || !clip.plane) {
        return;
    }

    if (!clip.wholeDocument) {
        clip.view->getViewer()->removeRuntimeNode(
            clip.plane,
            View3DInventorViewer::RuntimeNodeLayer::Scene
        );

        auto restoreOrder = clip.movedTargets;
        std::ranges::sort(restoreOrder, [](const auto& left, const auto& right) {
            if (left.parent == right.parent) {
                return left.index < right.index;
            }
            return left.parent < right.parent;
        });

        for (const auto& target : restoreOrder) {
            auto* obj = clip.view->getAppDocument()->getObject(target.objectName.c_str());
            auto* vp = obj ? Application::Instance->getViewProvider(obj) : nullptr;
            if (vp && target.parent) {
                clip.view->getViewer()->moveViewProvider(vp, target.parent, target.index);
            }
        }
        clip.movedTargets.clear();
    }
    else if (clip.view->getViewer()->hasClippingPlane()) {
        clip.view->getViewer()->toggleClippingPlane(0, false, true);
    }

    clip.view->getViewer()->removeRuntimeNode(
        clip.plane,
        View3DInventorViewer::RuntimeNodeLayer::Foreground
    );
}

void ClippingPlaneManager::installActiveCue(View3DInventor* view, const App::ClippingPlane& plane)
{
    if (view && view->getViewer()) {
        view->getViewer()->addRuntimeNode(
            &plane,
            buildActiveCue(plane),
            View3DInventorViewer::RuntimeNodeLayer::Foreground
        );
    }
}
