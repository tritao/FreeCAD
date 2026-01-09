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

#include "GuiShellServices.h"

#include "DockWindowManager.h"
#include "ToolBarManager.h"

#include <QMainWindow>
#include <QMenuBar>
#include <QPointer>
#include <QStatusBar>

namespace Gui
{

class GuiShellServices::Impl
{
public:
    Impl(QMainWindow* hostWindow, std::string statePrefix)
        : hostWindow(hostWindow)
        , statePrefix(std::move(statePrefix))
    {}

    QPointer<QMainWindow> hostWindow;
    std::string statePrefix;
};

GuiShellServices::GuiShellServices(QMainWindow* hostWindow, std::string statePrefix)
    : d(std::make_unique<Impl>(hostWindow, std::move(statePrefix)))
{}

GuiShellServices::~GuiShellServices() = default;

QMainWindow* GuiShellServices::hostWindow() const
{
    return d->hostWindow.data();
}

const std::string& GuiShellServices::statePrefix() const
{
    return d->statePrefix;
}

QMenuBar* GuiShellServices::menuBar() const
{
    if (auto* w = hostWindow()) {
        return w->menuBar();
    }
    return nullptr;
}

QStatusBar* GuiShellServices::statusBar() const
{
    if (auto* w = hostWindow()) {
        return w->statusBar();
    }
    return nullptr;
}

ToolBarManager* GuiShellServices::toolBars()
{
    return ToolBarManager::getInstance(hostWindow(), statePrefix());
}

DockWindowManager* GuiShellServices::docking()
{
    return DockWindowManager::instance(hostWindow(), statePrefix());
}

} // namespace Gui
