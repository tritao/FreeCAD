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

#include <Gui/ViewProviderGeometryObject.h>

class SoCoordinate3;
class SoIndexedLineSet;
class SoMaterial;
class SoSwitch;

namespace Gui
{

class SoShapeScale;

class GuiExport ViewProviderClippingPlane: public ViewProviderGeometryObject
{
    PROPERTY_HEADER_WITH_OVERRIDE(Gui::ViewProviderClippingPlane);
    using inherited = ViewProviderGeometryObject;

public:
    ViewProviderClippingPlane();
    ~ViewProviderClippingPlane() override;

    App::PropertyFloat DisplayLength;
    App::PropertyFloat DisplayHeight;
    App::PropertyFloat ArrowSize;
    App::PropertyBool AutoSize;

    void attach(App::DocumentObject* obj) override;
    void updateData(const App::Property* prop) override;
    std::vector<std::string> getDisplayModes() const override;
    void setDisplayMode(const char* ModeName) override;
    void setupContextMenu(QMenu* menu, QObject* receiver, const char* member) override;
    bool doubleClicked() override;
    void beforeDelete() override;

protected:
    void onChanged(const App::Property* prop) override;

private:
    void syncOverlayAppearance();
    void syncHelperVisibility();
    void updateGeometry();

    SoCoordinate3* overlayCoords {nullptr};
    SoIndexedLineSet* overlayLines {nullptr};
    SoMaterial* overlayMaterial {nullptr};
    SoSwitch* overlaySwitch {nullptr};
    SoShapeScale* overlayScale {nullptr};
};

}  // namespace Gui
