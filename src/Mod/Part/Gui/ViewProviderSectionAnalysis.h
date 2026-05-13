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

#include <Mod/Part/Gui/ViewProvider.h>
#include <Mod/Part/PartGlobal.h>

namespace PartGui
{

class PartGuiExport ViewProviderSectionAnalysis: public ViewProviderPart
{
    PROPERTY_HEADER_WITH_OVERRIDE(PartGui::ViewProviderSectionAnalysis);

public:
    ViewProviderSectionAnalysis();
    ~ViewProviderSectionAnalysis() override;

    bool doubleClicked() override;
    bool setEdit(int ModNum) override;
    void unsetEdit(int ModNum) override;
    void setupContextMenu(QMenu* menu, QObject* receiver, const char* member) override;
};

}  // namespace PartGui
