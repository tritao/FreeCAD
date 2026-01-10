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
#include "MainWindow.h"
#include "ToolBarManager.h"

#include <QMainWindow>
#include <QMap>
#include <QMenuBar>
#include <QPointer>
#include <QString>
#include <QStatusBar>
#include <QUrl>

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
    QMap<QString, QPointer<UrlHandler>> urlHandlers;
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

void GuiShellServices::setUrlHandler(const QString& scheme, UrlHandler* handler)
{
    if (scheme.isEmpty()) {
        return;
    }
    if (!handler) {
        d->urlHandlers.remove(scheme);
        return;
    }
    d->urlHandlers[scheme] = handler;
}

void GuiShellServices::unsetUrlHandler(const QString& scheme)
{
    if (scheme.isEmpty()) {
        return;
    }
    d->urlHandlers.remove(scheme);
}

bool GuiShellServices::openUrl(App::Document* doc, const QUrl& url) const
{
    auto it = d->urlHandlers.find(url.scheme());
    if (it == d->urlHandlers.end() || it->isNull()) {
        return false;
    }

    (*it)->openUrl(doc, url);
    return true;
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
