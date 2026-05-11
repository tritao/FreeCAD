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

#include "ClippingPlane.h"

using namespace App;

PROPERTY_SOURCE(App::ClippingPlane, App::GeoFeature)

namespace
{

const char* scopeModeEnums[] = {"WholeDocument", "IncludeOnly", nullptr};

}

ClippingPlane::ClippingPlane()
{
    ADD_PROPERTY_TYPE(ScopeMode,
                      (static_cast<long>(0)),
                      "ClippingPlane",
                      App::Prop_None,
                      "How the clipping plane applies to the document");
    ScopeMode.setEnums(scopeModeEnums);
    ADD_PROPERTY_TYPE(Targets,
                      (),
                      "ClippingPlane",
                      App::Prop_None,
                      "Objects affected by the clipping plane when ScopeMode is IncludeOnly");
    ADD_PROPERTY_TYPE(Reverse,
                      (false),
                      "ClippingPlane",
                      App::Prop_None,
                      "Reverse the clipping direction");
}
