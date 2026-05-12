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

#include <QMenu>

#include <App/Document.h>
#include <App/SavedView.h>

#include "Application.h"
#include "Control.h"
#include "Command.h"
#include "Document.h"
#include "SavedViewManager.h"
#include "TaskSavedView.h"
#include "View3DInventor.h"
#include "ViewProviderSavedView.h"

using namespace Gui;

PROPERTY_SOURCE(Gui::ViewProviderSavedView, Gui::ViewProviderDocumentObject)

ViewProviderSavedView::ViewProviderSavedView()
{
    sPixmap = "Std_ViewScreenShot";
}

bool ViewProviderSavedView::doubleClicked()
{
    auto* view = qobject_cast<View3DInventor*>(getActiveView());
    auto* savedView = getObject<App::SavedView>();
    return SavedViewManager::restore(view, savedView);
}

bool ViewProviderSavedView::setEdit(int ModNum)
{
    if (ModNum != ViewProvider::Default) {
        return ViewProviderDocumentObject::setEdit(ModNum);
    }
    if (Gui::Control().activeDialog(getDocument()->getDocument())) {
        return false;
    }

    Gui::Control().showDialog(new TaskSavedView(this), getDocument()->getDocument());
    return true;
}

void ViewProviderSavedView::unsetEdit(int ModNum)
{
    if (ModNum == ViewProvider::Default) {
        Gui::Control().closeDialog(getDocument()->getDocument());
    }
    else {
        ViewProviderDocumentObject::unsetEdit(ModNum);
    }
}

void ViewProviderSavedView::setupContextMenu(QMenu* menu, QObject* receiver, const char* member)
{
    Q_UNUSED(receiver);
    Q_UNUSED(member);

    if (qobject_cast<View3DInventor*>(getActiveView()) && getObject<App::SavedView>()) {
        menu->addAction(QObject::tr("Restore saved view"), []() {
            Application::Instance->commandManager().runCommandByName("Std_ApplySavedView");
        });
        menu->addAction(QObject::tr("Update from current view"), []() {
            Application::Instance->commandManager().runCommandByName("Std_UpdateSavedView");
        });
        menu->addAction(QObject::tr("Edit saved view"), [this]() {
            if (auto* doc = getDocument()) {
                doc->setEdit(this, ViewProvider::Default);
            }
        });
    }

    ViewProviderDocumentObject::setupContextMenu(menu, receiver, member);
}
