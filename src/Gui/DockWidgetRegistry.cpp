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

#include "DockWidgetRegistry.h"

#include "DockWindowManager.h"

#include <QMainWindow>

namespace Gui
{

DockWidgetRegistry& DockWidgetRegistry::instance()
{
    static DockWidgetRegistry reg;
    return reg;
}

DockWidgetRegistry::DockWidgetRegistry() = default;

void DockWidgetRegistry::registerDockWidget(const QString& id, Registration registration)
{
    if (id.isEmpty() || !registration.creator) {
        return;
    }
    registrations_.insert(id, std::move(registration));
}

void DockWidgetRegistry::registerCreator(const QString& id, Creator creator)
{
    if (id.isEmpty() || !creator) {
        return;
    }
    Registration reg;
    reg.creator = std::move(creator);
    registrations_.insert(id, std::move(reg));
}

void DockWidgetRegistry::unregisterCreator(const QString& id)
{
    registrations_.remove(id);
}

bool DockWidgetRegistry::hasCreator(const QString& id) const
{
    return registrations_.contains(id);
}

const DockWidgetRegistry::Registration* DockWidgetRegistry::findRegistration(const QString& id) const
{
    auto it = registrations_.find(id);
    if (it == registrations_.end()) {
        return nullptr;
    }
    return &it.value();
}

QWidget* DockWidgetRegistry::create(const QString& id, QMainWindow* hostWindow) const
{
    if (!hostWindow) {
        return nullptr;
    }

    if (const auto* reg = findRegistration(id)) {
        return reg->creator ? reg->creator(hostWindow) : nullptr;
    }

    return nullptr;
}

QWidget* DockWidgetRegistry::ensureRegistered(
    DockWindowManager* dockManager,
    QMainWindow* hostWindow,
    const QString& id
) const
{
    QStringList stack;
    return ensureRegisteredImpl(dockManager, hostWindow, id, stack);
}

QWidget* DockWidgetRegistry::ensureRegisteredImpl(
    DockWindowManager* dockManager,
    QMainWindow* hostWindow,
    const QString& id,
    QStringList& recursionStack
) const
{
    if (!dockManager || !hostWindow) {
        return nullptr;
    }

    if (auto* existing = dockManager->findRegisteredDockWindow(id.toUtf8().constData())) {
        return existing;
    }

    const auto* reg = findRegistration(id);
    if (!reg || !reg->creator) {
        return nullptr;
    }

    if (reg->enabled && !reg->enabled()) {
        return nullptr;
    }

    if (recursionStack.contains(id)) {
        return nullptr;
    }
    recursionStack.push_back(id);

    for (const auto& dep : reg->dependsOn) {
        ensureRegisteredImpl(dockManager, hostWindow, dep, recursionStack);
    }

    QWidget* w = create(id, hostWindow);
    if (!w) {
        recursionStack.pop_back();
        return nullptr;
    }

    dockManager->registerDockWindow(id.toUtf8().constData(), w);
    recursionStack.pop_back();
    return w;
}

void DockWidgetRegistry::ensureRegisteredForItems(
    DockWindowManager* dockManager,
    QMainWindow* hostWindow,
    const DockWindowItems& items
) const
{
    for (const auto& it : items.dockWidgets()) {
        ensureRegistered(dockManager, hostWindow, it.name);
    }
}

} // namespace Gui
