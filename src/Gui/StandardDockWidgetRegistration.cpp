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

#include "StandardDockWidgetRegistration.h"

#include "DockWidgetRegistry.h"

#include <QApplication>
#include <QDockWidget>
#include <QMainWindow>

#include <App/Application.h>

#include "BitmapFactory.h"
#include "ComboView.h"
#include "DAGView/DAGView.h"
#include "PropertyView.h"
#include "PythonConsole.h"
#include "ReportView.h"
#include "Selection/SelectionView.h"
#include "TaskView/TaskView.h"
#include "Tree.h"

namespace Gui
{

namespace
{
ParameterGrp::handle dockPrefGroup(const char* name)
{
    return App::GetApplication()
        .GetUserParameter()
        .GetGroup("BaseApp")
        ->GetGroup("Preferences")
        ->GetGroup("DockWindows")
        ->GetGroup(name);
}

bool isEnabled(const QString& id)
{
    if (id == QLatin1String("Std_TreeView")) {
        return dockPrefGroup("TreeView")->GetBool("Enabled", false);
    }
    if (id == QLatin1String("Std_PropertyView")) {
        return dockPrefGroup("PropertyView")->GetBool("Enabled", false);
    }
    if (id == QLatin1String("Std_ComboView")) {
        return dockPrefGroup("ComboView")->GetBool("Enabled", true);
    }
    if (id == QLatin1String("Std_DAGView")) {
        return dockPrefGroup("DAGView")->GetBool("Enabled", false);
    }

    // Always available: task/selection/report/python are standard building blocks.
    return id == QLatin1String("Std_TaskView") || id == QLatin1String("Std_SelectionView")
        || id == QLatin1String("Std_ReportView") || id == QLatin1String("Std_PythonView");
}

QWidget* create(const QString& id, QMainWindow* hostWindow)
{
    if (!hostWindow) {
        return nullptr;
    }

    if (id == QLatin1String("Std_TaskView")) {
        auto group = dockPrefGroup("TaskView");
        auto* taskView = new Gui::TaskView::TaskView(hostWindow);
        bool restore = group->GetBool("RestoreWidth", taskView->shouldRestoreWidth());
        taskView->setRestoreWidth(restore);
        taskView->setObjectName(QStringLiteral("Tasks"));
        taskView->setWindowTitle(QDockWidget::tr("Tasks"));
        taskView->setMinimumWidth(210);
        return taskView;
    }

    if (id == QLatin1String("Std_SelectionView")) {
        auto* selectionView = new Gui::DockWnd::SelectionView(nullptr, hostWindow);
        selectionView->setObjectName(QStringLiteral("Selection view"));
        selectionView->setWindowTitle(QDockWidget::tr("Selection View"));
        selectionView->setMinimumWidth(210);
        return selectionView;
    }

    if (id == QLatin1String("Std_ReportView")) {
        auto* report = new Gui::DockWnd::ReportOutput(hostWindow);
        report->setWindowIcon(BitmapFactory().pixmap("MacroEditor"));
        report->setObjectName(QStringLiteral("Report view"));
        report->setWindowTitle(QDockWidget::tr("Report View"));

        auto* observer = new Gui::DockWnd::ReportOutputObserver(report);
        qApp->installEventFilter(observer);
        return report;
    }

    if (id == QLatin1String("Std_PythonView")) {
        auto* python = new PythonConsole(hostWindow);
        python->setWindowIcon(Gui::BitmapFactory().iconFromTheme("applications-python"));
        python->setObjectName(QStringLiteral("Python console"));
        python->setWindowTitle(QDockWidget::tr("Python Console"));
        return python;
    }

    if (id == QLatin1String("Std_TreeView")) {
        auto* tree = new TreeDockWidget(0, hostWindow);
        tree->setObjectName(QStringLiteral("Tree view"));
        tree->setWindowTitle(QDockWidget::tr("Tree View"));
        tree->setMinimumWidth(210);
        return tree;
    }

    if (id == QLatin1String("Std_PropertyView")) {
        auto* prop = new Gui::DockWnd::PropertyDockView(0, hostWindow);
        prop->setObjectName(QStringLiteral("Property view"));
        prop->setWindowTitle(QDockWidget::tr("Property View"));
        prop->setMinimumWidth(210);
        return prop;
    }

    if (id == QLatin1String("Std_ComboView")) {
        auto* combo = new Gui::DockWnd::ComboView(nullptr, hostWindow);
        combo->setObjectName(QStringLiteral("Model"));
        combo->setWindowTitle(QDockWidget::tr("Model"));
        combo->setMinimumWidth(150);
        return combo;
    }

    if (id == QLatin1String("Std_DAGView")) {
        auto* dag = new DAG::DockWindow(nullptr, hostWindow);
        dag->setObjectName(QStringLiteral("DAG View"));
        dag->setWindowTitle(QDockWidget::tr("DAG View"));
        return dag;
    }

    return nullptr;
}
}  // namespace

void registerStandardDockWidgets(DockWidgetRegistry& registry)
{
    // Standard "Std_*" dock widgets.
    registry.registerDockWidget(
        QStringLiteral("Std_TaskView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_TaskView"), w); },
            {},
            {}
        }
    );
    registry.registerDockWidget(
        QStringLiteral("Std_SelectionView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_SelectionView"), w); },
            {},
            {}
        }
    );
    registry.registerDockWidget(
        QStringLiteral("Std_ReportView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_ReportView"), w); },
            {},
            {}
        }
    );
    registry.registerDockWidget(
        QStringLiteral("Std_PythonView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_PythonView"), w); },
            {},
            {QStringLiteral("Std_ReportView")}
        }
    );

    registry.registerDockWidget(
        QStringLiteral("Std_TreeView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_TreeView"), w); },
            []() { return isEnabled(QStringLiteral("Std_TreeView")); },
            {}
        }
    );
    registry.registerDockWidget(
        QStringLiteral("Std_PropertyView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_PropertyView"), w); },
            []() { return isEnabled(QStringLiteral("Std_PropertyView")); },
            {}
        }
    );
    registry.registerDockWidget(
        QStringLiteral("Std_ComboView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_ComboView"), w); },
            []() { return isEnabled(QStringLiteral("Std_ComboView")); },
            {}
        }
    );
    registry.registerDockWidget(
        QStringLiteral("Std_DAGView"),
        DockWidgetRegistry::Registration{
            [](QMainWindow* w) { return create(QStringLiteral("Std_DAGView"), w); },
            []() { return isEnabled(QStringLiteral("Std_DAGView")); },
            {}
        }
    );
}

} // namespace Gui
