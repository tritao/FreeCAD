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

#include "SavedView.h"

using namespace App;

PROPERTY_SOURCE(App::SavedView, App::DocumentObject)

SavedView::SavedView()
{
    ADD_PROPERTY_TYPE(CameraState,
                      (""),
                      "Saved View",
                      App::Prop_Hidden,
                      "Serialized camera settings for this saved view");
    ADD_PROPERTY_TYPE(VisibilityState,
                      (),
                      "Saved View",
                      App::Prop_Hidden,
                      "Saved visibility state for document objects");
    ADD_PROPERTY_TYPE(RestoreCamera,
                      (true),
                      "Saved View",
                      App::Prop_None,
                      "Restore the camera when applying this saved view");
    ADD_PROPERTY_TYPE(RestoreVisibility,
                      (true),
                      "Saved View",
                      App::Prop_None,
                      "Restore object visibilities when applying this saved view");
    ADD_PROPERTY_TYPE(RestoreClipping,
                      (true),
                      "Saved View",
                      App::Prop_None,
                      "Restore clipping when applying this saved view");
    ADD_PROPERTY_TYPE(ClipPlane,
                      (nullptr),
                      "Saved View",
                      App::Prop_None,
                      "Clipping plane captured by this saved view");
}
