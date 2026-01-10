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

#ifndef GUI_GUISHELLSERVICES_H
#define GUI_GUISHELLSERVICES_H

#include <FCGlobal.h>

#include <memory>
#include <string>

class QMainWindow;
class QMenuBar;
class QStatusBar;
class QString;
class QUrl;

namespace App
{
class Document;
}

namespace Gui
{

class DockWindowManager;
class ToolBarManager;
class UrlHandler;

class GuiExport GuiShellServices
{
public:
    GuiShellServices(QMainWindow* hostWindow, std::string statePrefix);
    ~GuiShellServices();

    QMainWindow* hostWindow() const;
    const std::string& statePrefix() const;

    QMenuBar* menuBar() const;
    QStatusBar* statusBar() const;

    void setUrlHandler(const QString& scheme, UrlHandler* handler);
    void unsetUrlHandler(const QString& scheme);
    bool openUrl(App::Document* doc, const QUrl& url) const;

    ToolBarManager* toolBars();
    DockWindowManager* docking();

private:
    class Impl;
    std::unique_ptr<Impl> d;
};

} // namespace Gui

#endif // GUI_GUISHELLSERVICES_H
