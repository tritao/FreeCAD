#include "FCUIShellWindow.h"

#include <QMessageBox>
#include <QTimer>

#include "Application.h"
#include "Workbench.h"
#include "WorkbenchManager.h"

using namespace Gui::FCUI;

FCUIShellWindow::FCUIShellWindow(const QString& modulePath, const QString& componentName, QWidget* parent)
    : QMainWindow(parent), host_(this), runtime_(&host_, this)
{
    setAttribute(Qt::WA_DeleteOnClose, true);

    if (Gui::Application::Instance) {
        workbenchConn_ = fastsignals::scoped_connection(
            Gui::Application::Instance->signalActivateWorkbench.connect([this](const char*) {
                QTimer::singleShot(0, this, [this]() { applyWorkbenchChrome(); });
            })
        );
    }

    loadAndBuild(modulePath, componentName);
}

FCUIShellWindow::~FCUIShellWindow() = default;

void FCUIShellWindow::applyWorkbenchChrome()
{
    if (auto* wb = Gui::WorkbenchManager::instance()->active()) {
        wb->applyChromeTo(this, "BaseApp/FCUI");
    }
}

void FCUIShellWindow::loadAndBuild(const QString& modulePath, const QString& componentName)
{
    QString err;
    if (!runtime_.loadModuleFile(modulePath, &err)) {
        QMessageBox::critical(this, tr("FCUI"), err);
        return;
    }

    const QString comp = !componentName.isEmpty() ? componentName : runtime_.componentNames().value(0);
    QWidget* root = runtime_.instantiate(comp, &err);
    if (!root) {
        QMessageBox::critical(this, tr("FCUI"), err);
        return;
    }

    setCentralWidget(root);
    setWindowTitle(QStringLiteral("FCUI — %1").arg(comp));
    resize(1200, 800);

    applyWorkbenchChrome();
}
