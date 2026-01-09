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

#include "GuiShell.h"

#include "GuiShellServices.h"
#include "InputHint.h"
#include "MainWindow.h"
#include "MDIView.h"

#include <QLabel>
#include <QStatusBar>
#include <QMainWindow>
#include <QPointer>
#include <Qt>

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

    void updateActions(bool delay) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->updateActions(delay);
        }
    }

    void showMessage(const QString& message, int timeout) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->showMessage(message, timeout);
            return;
        }
        if (auto* w = mainWindow_.data()) {
            if (auto* sb = w->statusBar()) {
                sb->showMessage(message, timeout);
            }
        }
    }

    void setStatusPaneText(int pane, const QString& text) override
    {
        if (pane < 0) {
            return;
        }

        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->setPaneText(pane, text);
            return;
        }

        auto* w = mainWindow_.data();
        if (!w) {
            return;
        }
        auto* sb = w->statusBar();
        if (!sb) {
            return;
        }

        for (int i = 0; i <= pane; ++i) {
            const auto objectName = QStringLiteral("__GuiShell_StatusPane_%1").arg(i);
            if (auto* existing = sb->findChild<QLabel*>(objectName)) {
                if (i == pane) {
                    existing->setText(text);
                }
                continue;
            }

            auto* label = new QLabel(sb);
            label->setObjectName(objectName);
            label->setText(i == pane ? text : QString());
            sb->addWidget(label, 0);
        }
    }

    void addStatusPermanentWidget(QWidget* widget, int stretch) override
    {
        if (!widget) {
            return;
        }
        if (auto* w = mainWindow_.data()) {
            if (auto* sb = w->statusBar()) {
                sb->addPermanentWidget(widget, stretch);
            }
        }
    }

    void removeStatusWidget(QWidget* widget) override
    {
        if (!widget) {
            return;
        }
        if (auto* w = mainWindow_.data()) {
            if (auto* sb = w->statusBar()) {
                sb->removeWidget(widget);
            }
        }
    }

    void addWindow(MDIView* view) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->addWindow(view);
        }
    }

    void removeWindow(MDIView* view, bool close) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->removeWindow(view, close);
        }
    }

    QList<QWidget*> windows() const override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            return mw->windows();
        }
        return {};
    }

    QMdiArea* mdiArea() const override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            return mw->getMdiArea();
        }
        return nullptr;
    }

    MDIView* activeWindow() const override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            return mw->activeWindow();
        }
        return nullptr;
    }

    void setActiveWindow(MDIView* view) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->setActiveWindow(view);
        }
    }

    void tabChanged(MDIView* view) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->tabChanged(view);
        }
    }

    void tile() override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->tile();
        }
    }

    void cascade() override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->cascade();
        }
    }

    void closeActiveWindow() override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->closeActiveWindow();
        }
    }

    bool closeAllDocuments(bool close) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            return mw->closeAllDocuments(close);
        }
        return true;
    }

    void activateNextWindow() override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->activateNextWindow();
        }
    }

    void activatePreviousWindow() override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->activatePreviousWindow();
        }
    }

    void showStatus(int type, const QString& message) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->showStatus(type, message);
            return;
        }
        showMessage(message, 0);
    }

    void showHints(const std::list<InputHint>& hints) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->showHints(hints);
        }
    }

    void hideHints() override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->hideHints();
        }
    }

    void setUserSchema(int userSchema) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->setUserSchema(userSchema);
        }
    }

    void initDockWindows(bool show) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->initDockWindows(show);
        }
    }

    void appendRecentFile(const QString& filename) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->appendRecentFile(filename);
        }
    }

    void appendRecentMacro(const QString& filename) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->appendRecentMacro(filename);
        }
    }

    void setMainWindowTitle(const QString& title) override
    {
        if (auto* w = mainWindow_.data()) {
            w->setWindowTitle(title);
        }
    }

    void setMainWindowModified(bool modified) override
    {
        if (auto* w = mainWindow_.data()) {
            w->setWindowModified(modified);
        }
    }

    void setWaitCursor() override
    {
        if (auto* w = mainWindow_.data()) {
            w->setCursor(Qt::WaitCursor);
        }
    }

    void unsetCursor() override
    {
        if (auto* w = mainWindow_.data()) {
            w->unsetCursor();
        }
    }

    void activateWorkbench(const QString& name) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->activateWorkbench(name);
        }
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
