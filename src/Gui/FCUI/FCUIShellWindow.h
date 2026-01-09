#pragma once

#include <QMainWindow>

#include <fastsignals/connection.h>

#include "FCUIQtRuntime.h"
#include "FreeCADFCUIHost.h"

namespace Gui::FCUI
{

class FCUIShellWindow final : public QMainWindow
{
    Q_OBJECT

public:
    explicit FCUIShellWindow(const QString& modulePath, const QString& componentName = {}, QWidget* parent = nullptr);
    ~FCUIShellWindow() override;

private:
    void loadAndBuild(const QString& modulePath, const QString& componentName);
    void applyWorkbenchChrome();

    FreeCADFCUIHost host_;
    FCUIQtRuntime runtime_;
    fastsignals::scoped_connection workbenchConn_;
};

}  // namespace Gui::FCUI
