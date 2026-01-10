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

#include <QList>
#include <QMainWindow>
#include <Qt>

#include <list>
#include <memory>
#include <string>

class QMdiArea;
class QDockWidget;
class QToolBar;
class QString;
class QWidget;

namespace Gui
{

struct InputHint;
class MDIView;
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
    virtual void setRightSideMessage(const QString& message) = 0;
    virtual bool isRightSideMessageVisible() const = 0;
    virtual void setStatusPaneText(int pane, const QString& text) = 0;
    virtual void addStatusPermanentWidget(QWidget* widget, int stretch = 0) = 0;
    virtual void removeStatusWidget(QWidget* widget) = 0;
    virtual void addDockWidget(Qt::DockWidgetArea area, QDockWidget* dockWidget) = 0;
    virtual void tabifyDockWidget(QDockWidget* first, QDockWidget* second) = 0;
    virtual Qt::DockWidgetArea dockWidgetArea(QDockWidget* dockWidget) const = 0;
    virtual QList<QDockWidget*> tabifiedDockWidgets(QDockWidget* dockWidget) const = 0;
    virtual void addToolBar(QToolBar* toolBar) = 0;
    virtual void addToolBar(Qt::ToolBarArea area, QToolBar* toolBar) = 0;
    virtual void addToolBarBreak(Qt::ToolBarArea area) = 0;
    virtual Qt::ToolBarArea toolBarArea(QToolBar* toolBar) const = 0;
    virtual bool toolBarBreak(QToolBar* toolBar) const = 0;

    virtual void addWindow(MDIView* view) = 0;
    virtual void removeWindow(MDIView* view, bool close = true) = 0;
    virtual QList<QWidget*> windows() const = 0;
    virtual QMdiArea* mdiArea() const = 0;
    virtual MDIView* activeWindow() const = 0;
    virtual void setActiveWindow(MDIView* view) = 0;
    virtual void tabChanged(MDIView* view) = 0;

    virtual void tile() = 0;
    virtual void cascade() = 0;
    virtual void closeActiveWindow() = 0;
    virtual bool closeAllDocuments(bool close = true) = 0;
    virtual void activateNextWindow() = 0;
    virtual void activatePreviousWindow() = 0;

    virtual void showStatus(int type, const QString& message) = 0;
    virtual void showHints(const std::list<InputHint>& hints) = 0;
    virtual void hideHints() = 0;
    virtual void setUserSchema(int userSchema) = 0;
    virtual void initDockWindows(bool show) = 0;

    virtual void appendRecentFile(const QString& filename) = 0;
    virtual void appendRecentMacro(const QString& filename) = 0;
    virtual void setMainWindowTitle(const QString& title) = 0;
    virtual void setMainWindowModified(bool modified) = 0;
    virtual void setWaitCursor() = 0;
    virtual void unsetCursor() = 0;
    virtual void activateWorkbench(const QString& name) = 0;
};

GuiExport IGuiShell* activeShell();
GuiExport QMainWindow* activeMainWindow();
GuiExport QWidget* uiParentWidget();
GuiExport void setRightSideMessage(const QString& message);
GuiExport bool isRightSideMessageVisible();
GuiExport void setActiveShell(std::unique_ptr<IGuiShell> shell);

GuiExport std::unique_ptr<IGuiShell> createClassicShell(QMainWindow* mainWindow);

} // namespace Gui

#endif // GUI_GUISHELL_H
