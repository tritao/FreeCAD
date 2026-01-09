#include "StandardDockWidgetFactory.h"

#include <QApplication>
#include <QDockWidget>
#include <QMainWindow>

#include <App/Application.h>

#include "BitmapFactory.h"
#include "ComboView.h"
#include "DAGView/DAGView.h"
#include "DockWindowManager.h"
#include "PropertyView.h"
#include "PythonConsole.h"
#include "ReportView.h"
#include "Selection/SelectionView.h"
#include "TaskView/TaskView.h"
#include "Tree.h"

using namespace Gui;

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
}  // namespace

bool StandardDockWidgetFactory::isStandardId(const QString& id)
{
    return id == QLatin1String("Std_TaskView") || id == QLatin1String("Std_SelectionView")
        || id == QLatin1String("Std_ReportView") || id == QLatin1String("Std_PythonView")
        || id == QLatin1String("Std_TreeView") || id == QLatin1String("Std_PropertyView")
        || id == QLatin1String("Std_ComboView") || id == QLatin1String("Std_DAGView");
}

bool StandardDockWidgetFactory::isEnabled(const QString& id)
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
    return isStandardId(id);
}

QWidget* StandardDockWidgetFactory::create(const QString& id, QMainWindow* hostWindow)
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

QWidget* StandardDockWidgetFactory::ensureRegistered(
    DockWindowManager* dockManager,
    QMainWindow* hostWindow,
    const QString& id
)
{
    if (!dockManager || !hostWindow) {
        return nullptr;
    }

    if (!isStandardId(id) || !isEnabled(id)) {
        return nullptr;
    }

    if (auto* existing = dockManager->findRegisteredDockWindow(id.toUtf8().constData())) {
        return existing;
    }

    QWidget* w = create(id, hostWindow);
    if (!w) {
        return nullptr;
    }

    dockManager->registerDockWindow(id.toUtf8().constData(), w);
    return w;
}

void StandardDockWidgetFactory::ensureRegisteredForItems(
    DockWindowManager* dockManager,
    QMainWindow* hostWindow,
    const DockWindowItems& items
)
{
    bool needsPython = false;
    bool needsReport = false;
    for (const auto& it : items.dockWidgets()) {
        if (it.name == QLatin1String("Std_PythonView")) {
            needsPython = true;
        }
        if (it.name == QLatin1String("Std_ReportView")) {
            needsReport = true;
        }
    }

    // Report view must be created before Python console.
    if (needsPython && !needsReport) {
        ensureRegistered(dockManager, hostWindow, QStringLiteral("Std_ReportView"));
    }

    for (const auto& it : items.dockWidgets()) {
        ensureRegistered(dockManager, hostWindow, it.name);
    }
}
