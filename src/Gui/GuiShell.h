/***************************************************************************
 *   Copyright (c) 2026                                                   *
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

#ifndef GUI_GUISHELL_H
#define GUI_GUISHELL_H

#include <FCGlobal.h>

#include <memory>
#include <string>

class QMainWindow;
class QString;

namespace Gui
{

class GuiShellServices;

class GuiExport IGuiShell
{
public:
    virtual ~IGuiShell() = default;

    virtual QMainWindow* mainWindow() const = 0;
    virtual std::string chromeStatePrefix() const = 0;
    virtual GuiShellServices& services() = 0;
    virtual void updateActions(bool delay = false) = 0;
    virtual void showMessage(const QString& message, int timeout = 0) = 0;
};

GuiExport IGuiShell* activeShell();
GuiExport QMainWindow* activeMainWindow();
GuiExport void setActiveShell(std::unique_ptr<IGuiShell> shell);

GuiExport std::unique_ptr<IGuiShell> createClassicShell(QMainWindow* mainWindow);

} // namespace Gui

#endif // GUI_GUISHELL_H
