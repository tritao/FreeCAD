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
#include "MainWindow.h"

#include <QLabel>
#include <QStatusBar>
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
