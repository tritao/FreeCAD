#pragma once

#include <FCGlobal.h>

#include <memory>
#include <string>

class QMainWindow;

namespace Gui
{

class GuiShellServices;

class GuiExport IGuiShell
{
public:
    virtual ~IGuiShell() = default;

    virtual QMainWindow* mainWindow() const = 0;
    virtual std::string chromeStatePrefix() const = 0;
    virtual GuiShellServices& services() = 0;
};

GuiExport IGuiShell* activeShell();
GuiExport QMainWindow* activeMainWindow();
GuiExport void setActiveShell(std::unique_ptr<IGuiShell> shell);

GuiExport std::unique_ptr<IGuiShell> createClassicShell(QMainWindow* mainWindow);

} // namespace Gui
