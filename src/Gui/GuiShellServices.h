#pragma once

#include <FCGlobal.h>

#include <string>

class QMainWindow;
class QMenuBar;
class QStatusBar;

namespace Gui
{

class DockWindowManager;
class ToolBarManager;

class GuiExport GuiShellServices
{
public:
    GuiShellServices(QMainWindow* hostWindow, std::string statePrefix);
    ~GuiShellServices();

    QMainWindow* hostWindow() const;
    const std::string& statePrefix() const;

    QMenuBar* menuBar() const;
    QStatusBar* statusBar() const;

    ToolBarManager* toolBars();
    DockWindowManager* docking();

private:
    class Impl;
    std::unique_ptr<Impl> d;
};

} // namespace Gui

