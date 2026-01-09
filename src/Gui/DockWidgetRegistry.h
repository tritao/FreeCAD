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

#ifndef GUI_DOCKWIDGETREGISTRY_H
#define GUI_DOCKWIDGETREGISTRY_H

#include <FCGlobal.h>

#include <functional>

#include <QHash>
#include <QString>
#include <QStringList>

class QMainWindow;
class QWidget;

namespace Gui
{

class DockWindowItems;
class DockWindowManager;

class GuiExport DockWidgetRegistry
{
public:
    using Creator = std::function<QWidget*(QMainWindow*)>;
    using EnabledPredicate = std::function<bool()>;

    struct Registration
    {
        Creator creator;
        EnabledPredicate enabled;
        QStringList dependsOn;
    };

    static DockWidgetRegistry& instance();

    void registerDockWidget(const QString& id, Registration registration);
    void registerCreator(const QString& id, Creator creator);
    void unregisterCreator(const QString& id);
    bool hasCreator(const QString& id) const;

    QWidget* create(const QString& id, QMainWindow* hostWindow) const;

    QWidget* ensureRegistered(DockWindowManager* dockManager, QMainWindow* hostWindow, const QString& id) const;
    void ensureRegisteredForItems(
        DockWindowManager* dockManager,
        QMainWindow* hostWindow,
        const DockWindowItems& items
    ) const;

private:
    DockWidgetRegistry();

    const Registration* findRegistration(const QString& id) const;
    QWidget* ensureRegisteredImpl(
        DockWindowManager* dockManager,
        QMainWindow* hostWindow,
        const QString& id,
        QStringList& recursionStack
    ) const;

    QHash<QString, Registration> registrations_;
};

} // namespace Gui

#endif // GUI_DOCKWIDGETREGISTRY_H
