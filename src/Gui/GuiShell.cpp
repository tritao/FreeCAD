#include "GuiShell.h"

#include "GuiShellServices.h"
#include "MainWindow.h"

#include <QMainWindow>
#include <QPointer>

namespace Gui
{
namespace
{

class ClassicShell final : public IGuiShell
{
public:
    explicit ClassicShell(QMainWindow* mainWindow)
        : mainWindow_(mainWindow)
        , services_(mainWindow, chromeStatePrefix())
    {}

    QMainWindow* mainWindow() const override
    {
        return mainWindow_.data();
    }

    std::string chromeStatePrefix() const override
    {
        return "BaseApp/MainWindow";
    }

    GuiShellServices& services() override
    {
        return services_;
    }

private:
    QPointer<QMainWindow> mainWindow_;
    GuiShellServices services_;
};

std::unique_ptr<IGuiShell> g_activeShell;

} // namespace

IGuiShell* activeShell()
{
    return g_activeShell.get();
}

QMainWindow* activeMainWindow()
{
    if (auto* shell = activeShell()) {
        return shell->mainWindow();
    }
    return getMainWindow();
}

void setActiveShell(std::unique_ptr<IGuiShell> shell)
{
    g_activeShell = std::move(shell);
}

std::unique_ptr<IGuiShell> createClassicShell(QMainWindow* mainWindow)
{
    return std::make_unique<ClassicShell>(mainWindow);
}

} // namespace Gui
