/***************************************************************************
 *   Copyright (c) 2013 Jürgen Riegel <FreeCAD@juergen-riegel.net>         *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/


#include <Gui/Control.h>
#include <Gui/Document.h>
#include <Gui/Application.h>
#include <Mod/Fem/App/FemSetNodesObject.h>
#include <Mod/Fem/Gui/TaskDlgCreateNodeSet.h>

#include "ViewProviderSetNodes.h"


using namespace FemGui;

PROPERTY_SOURCE(FemGui::ViewProviderSetNodes, Gui::ViewProviderGeometryObject)

bool ViewProviderSetNodes::doubleClicked()
{
    auto* document = getDocument()->getDocument();
    if (Gui::Control().activeDialog(document)) {
        return false;
    }

    Gui::TaskView::TaskDialog* dlg = new TaskDlgCreateNodeSet(getObject<Fem::FemSetNodesObject>());
    Gui::Control().showDialog(dlg, document);
    return true;
}


bool ViewProviderSetNodes::setEdit(int)
{
    auto* document = getDocument()->getDocument();
    if (Gui::Control().activeDialog(document)) {
        return false;
    }

    Gui::TaskView::TaskDialog* dlg = new TaskDlgCreateNodeSet(getObject<Fem::FemSetNodesObject>());
    Gui::Control().showDialog(dlg, document);
    return true;
}

void ViewProviderSetNodes::unsetEdit(int)
{
    Gui::Control().closeDialog(getDocument()->getDocument());
}
