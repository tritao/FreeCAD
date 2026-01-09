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

