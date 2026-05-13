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

#include <App/PropertyLinks.h>
#include <App/PropertyStandard.h>
#include <App/PropertyUnits.h>

#include "PartFeature.h"
#include "PropertyTopoShape.h"

namespace Part
{

class PartExport SectionAnalysis: public Part::Feature
{
    PROPERTY_HEADER_WITH_OVERRIDE(Part::SectionAnalysis);

public:
    SectionAnalysis();
    ~SectionAnalysis() override = default;

    App::PropertyLinkList Sources;
    App::PropertyLink ClippingPlane;
    App::PropertyEnumeration ResultMode;
    App::PropertyBool ShowHatching;
    App::PropertyDistance HatchSpacing;
    App::PropertyAngle HatchAngle;
    PropertyPartShape HatchShape;

    App::DocumentObjectExecReturn* execute() override;
    short mustExecute() const override;
    const char* getViewProviderName() const override
    {
        return "PartGui::ViewProviderSectionAnalysis";
    }

private:
    static const char* ResultModeEnums[];
};

}  // namespace Part
