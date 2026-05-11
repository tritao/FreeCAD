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

#include "GeoFeature.h"
#include "PropertyLinks.h"
#include "PropertyStandard.h"

namespace App
{

class AppExport ClippingPlane: public GeoFeature
{
    PROPERTY_HEADER_WITH_OVERRIDE(App::ClippingPlane);

public:
    ClippingPlane();
    ~ClippingPlane() override = default;

    App::PropertyEnumeration ScopeMode;
    App::PropertyLinkList Targets;
    App::PropertyBool Reverse;

    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderClippingPlane";
    }
};

}  // namespace App
