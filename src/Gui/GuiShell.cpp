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

#include "GuiShellEvents.h"
#include "GuiShellServices.h"
#include "InputHint.h"
#include "MainWindow.h"
#include "MDIView.h"

#include <QApplication>
#include <QDockWidget>
#include <QLabel>
#include <QMimeData>
#include <QStatusBar>
#include <QMainWindow>
#include <QPointer>
#include <QToolBar>
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
        , events_(mainWindow)
        , services_(mainWindow, chromeStatePrefix())
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            QObject::connect(
                mw, &MainWindow::workbenchActivated, &events_, &GuiShellEvents::workbenchActivated
            );
            QObject::connect(mw, &MainWindow::mainWindowClosed, &events_, &GuiShellEvents::mainWindowClosed);
        }
    }

    QMainWindow* mainWindow() const override
    {
        return mainWindow_.data();
    }

    GuiShellEvents* events() const override
    {
        return const_cast<GuiShellEvents*>(&events_);
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

    void setRightSideMessage(const QString& message) override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            mw->setRightSideMessage(message);
        }
    }

    bool isRightSideMessageVisible() const override
    {
        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
            return mw->isRightSideMessageVisible();
        }
        return false;
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

	    void addDockWidget(Qt::DockWidgetArea area, QDockWidget* dockWidget) override
	    {
	        if (!dockWidget) {
	            return;
	        }
	        if (auto* w = mainWindow_.data()) {
	            w->addDockWidget(area, dockWidget);
	        }
	    }

	    void tabifyDockWidget(QDockWidget* first, QDockWidget* second) override
	    {
	        if (!first || !second) {
	            return;
	        }
	        if (auto* w = mainWindow_.data()) {
	            w->tabifyDockWidget(first, second);
	        }
	    }

	    Qt::DockWidgetArea dockWidgetArea(QDockWidget* dockWidget) const override
	    {
	        if (!dockWidget) {
	            return Qt::NoDockWidgetArea;
	        }
	        if (auto* w = mainWindow_.data()) {
	            return w->dockWidgetArea(dockWidget);
	        }
	        return Qt::NoDockWidgetArea;
	    }

		    QList<QDockWidget*> tabifiedDockWidgets(QDockWidget* dockWidget) const override
		    {
		        if (!dockWidget) {
		            return {};
		        }
		        if (auto* w = mainWindow_.data()) {
		            return w->tabifiedDockWidgets(dockWidget);
		        }
		        return {};
		    }

		    void resizeDocks(const QList<QDockWidget*>& docks,
		                     const QList<int>& sizes,
		                     Qt::Orientation orientation) override
		    {
		        if (auto* w = mainWindow_.data()) {
		            w->resizeDocks(docks, sizes, orientation);
		        }
		    }

		    void addToolBar(QToolBar* toolBar) override
		    {
		        if (!toolBar) {
		            return;
		        }
		        if (auto* w = mainWindow_.data()) {
		            w->addToolBar(toolBar);
		        }
		    }

		    void addToolBar(Qt::ToolBarArea area, QToolBar* toolBar) override
		    {
		        if (!toolBar) {
		            return;
		        }
		        if (auto* w = mainWindow_.data()) {
		            w->addToolBar(area, toolBar);
		        }
		    }

		    void addToolBarBreak(Qt::ToolBarArea area) override
		    {
		        if (auto* w = mainWindow_.data()) {
		            w->addToolBarBreak(area);
		        }
		    }

		    Qt::ToolBarArea toolBarArea(QToolBar* toolBar) const override
		    {
		        if (!toolBar) {
		            return Qt::NoToolBarArea;
		        }
		        if (auto* w = mainWindow_.data()) {
		            return w->toolBarArea(toolBar);
		        }
		        return Qt::NoToolBarArea;
		    }

		    bool toolBarBreak(QToolBar* toolBar) const override
		    {
		        if (!toolBar) {
		            return false;
		        }
		        if (auto* w = mainWindow_.data()) {
		            return w->toolBarBreak(toolBar);
		        }
		        return false;
		    }

		    QMimeData* createMimeDataFromSelection() const override
		    {
		        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
		            return mw->createMimeDataFromSelection();
		        }
		        return nullptr;
		    }

		    bool canInsertFromMimeData(const QMimeData* mimeData) const override
		    {
		        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
		            return mw->canInsertFromMimeData(mimeData);
		        }
		        return false;
		    }

		    void insertFromMimeData(const QMimeData* mimeData) override
		    {
		        if (auto* mw = qobject_cast<MainWindow*>(mainWindow_.data())) {
		            mw->insertFromMimeData(mimeData);
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
    GuiShellEvents events_;
    GuiShellServices services_;
};

std::unique_ptr<IGuiShell> g_activeShell;

} // namespace

IGuiShell* activeShell()
{
    return g_activeShell.get();
}

IGuiShell* ensureActiveShell()
{
    if (auto* shell = activeShell()) {
        return shell;
    }

    // If a classic main window exists but no shell has been registered (yet),
    // create the default shell on demand so callsites don't need to special-case MainWindow.
    if (auto* mw = getMainWindow()) {
        setActiveShell(createClassicShell(mw));
        return activeShell();
    }

    return nullptr;
}

GuiShellEvents* activeShellEvents()
{
    if (auto* shell = activeShell()) {
        return shell->events();
    }
    return nullptr;
}

QMainWindow* activeMainWindow()
{
    if (auto* shell = activeShell()) {
        return shell->mainWindow();
    }
    return getMainWindow();
}

QWidget* uiParentWidget()
{
    if (auto* mw = activeMainWindow()) {
        return mw;
    }
    return QApplication::activeWindow();
}

QObject* uiParentObject()
{
    if (auto* w = uiParentWidget()) {
        return w;
    }
    return QApplication::instance();
}

void setRightSideMessage(const QString& message)
{
    if (auto* shell = activeShell()) {
        shell->setRightSideMessage(message);
        return;
    }
    if (auto* mw = qobject_cast<MainWindow*>(getMainWindow())) {
        mw->setRightSideMessage(message);
    }
}

bool isRightSideMessageVisible()
{
    if (auto* shell = activeShell()) {
        return shell->isRightSideMessageVisible();
    }
    if (auto* mw = qobject_cast<MainWindow*>(getMainWindow())) {
        return mw->isRightSideMessageVisible();
    }
    return false;
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
