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

#include <algorithm>
#include <array>
#include <vector>

#include <App/DocumentObject.h>
#include <Base/BoundBox.h>
#include <Base/Placement.h>
#include <Base/Vector3D.h>

#include "Document.h"
#include "ViewProvider.h"
#include "ViewProviderClippingPlane.h"

namespace Gui
{
namespace ClippingPlaneHelperFit
{

struct FittedHelper
{
    double length {100.0};
    double height {100.0};
    double arrow {35.0};
};

inline Base::BoundBox3d collectBounds(
    Gui::Document* guiDocument,
    Gui::MDIView* view,
    const std::vector<App::DocumentObject*>& objects,
    const App::DocumentObject* excludedObject
)
{
    Base::BoundBox3d bbox;

    if (!guiDocument) {
        return bbox;
    }

    for (auto* object : objects) {
        if (!object || object == excludedObject) {
            continue;
        }

        if (auto* viewProvider = guiDocument->getViewProvider(object)) {
            const auto objectBox = viewProvider->getBoundingBox(nullptr, true, view);
            if (objectBox.IsValid()) {
                bbox.Add(objectBox);
            }
        }
    }

    return bbox;
}

inline FittedHelper fittedHelper(const Base::Placement& placement, const Base::BoundBox3d& bbox)
{
    if (!bbox.IsValid()) {
        return {};
    }

    const Base::Vector3d center = bbox.GetCenter();
    const Base::Rotation rotation = placement.getRotation();
    const Base::Vector3d planeX = rotation.multVec(Base::Vector3d(1.0, 0.0, 0.0));
    const Base::Vector3d planeY = rotation.multVec(Base::Vector3d(0.0, 1.0, 0.0));
    const std::array<double, 2> xs = {bbox.MinX, bbox.MaxX};
    const std::array<double, 2> ys = {bbox.MinY, bbox.MaxY};
    const std::array<double, 2> zs = {bbox.MinZ, bbox.MaxZ};

    double halfLength = 0.0;
    double halfHeight = 0.0;
    for (double x : xs) {
        for (double y : ys) {
            for (double z : zs) {
                const Base::Vector3d delta(x - center.x, y - center.y, z - center.z);
                halfLength = std::max(halfLength, std::abs(delta * planeX));
                halfHeight = std::max(halfHeight, std::abs(delta * planeY));
            }
        }
    }

    constexpr double helperPadding = 1.10;
    FittedHelper helper;
    helper.length = std::max(1.0, halfLength * 2.0 * helperPadding);
    helper.height = std::max(1.0, halfHeight * 2.0 * helperPadding);
    helper.arrow = std::max(10.0, std::max(helper.length, helper.height) * 0.35);
    return helper;
}

inline void applyFittedHelper(
    Gui::ViewProviderClippingPlane* viewProvider,
    const Base::Placement& placement,
    const Base::BoundBox3d& bbox
)
{
    if (!viewProvider || !bbox.IsValid()) {
        return;
    }

    const auto helper = fittedHelper(placement, bbox);
    viewProvider->HelperSizeMode.setValue(
        static_cast<long>(Gui::ViewProviderClippingPlane::HelperSizeModeOption::Fit)
    );
    viewProvider->DisplayLength.setValue(static_cast<float>(helper.length));
    viewProvider->DisplayHeight.setValue(static_cast<float>(helper.height));
    viewProvider->ArrowSize.setValue(static_cast<float>(helper.arrow));
}

}  // namespace ClippingPlaneHelperFit
}  // namespace Gui
