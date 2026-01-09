/***************************************************************************
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 ***************************************************************************/

#include <QFileDialog>

#include "Application.h"
#include "CommandT.h"
#include "MainWindow.h"

#include "FCUI/FCUIShellWindow.h"

using namespace Gui;

//===========================================================================
// Std_FCUIShell
//===========================================================================

DEF_STD_CMD(StdCmdFCUIShell)

StdCmdFCUIShell::StdCmdFCUIShell()
    : Command("Std_FCUIShell")
{
    sGroup = "View";
    sMenuText = QT_TR_NOOP("FCUI &Shell");
    sToolTipText = QT_TR_NOOP("Open an FCUI shell window from a compiled module (.fcuim.json)");
    sWhatsThis = "Std_FCUIShell";
    sStatusTip = sToolTipText;
    sPixmap = "Std_TreeView";  // placeholder icon
}

void StdCmdFCUIShell::activated(int iMsg)
{
    Q_UNUSED(iMsg);

    const QString path = QFileDialog::getOpenFileName(
        getMainWindow(),
        QObject::tr("Open FCUI Module"),
        QString(),
        QObject::tr("FCUI module (*.fcuim.json *.json);;All files (*)")
    );
    if (path.isEmpty()) {
        return;
    }

    auto* w = new Gui::FCUI::FCUIShellWindow(path, {}, getMainWindow());
    w->show();
}

namespace Gui
{

void CreateFCUICommands()
{
    CommandManager& rcCmdMgr = Application::Instance->commandManager();
    rcCmdMgr.addCommand(new StdCmdFCUIShell());
}

}  // namespace Gui
