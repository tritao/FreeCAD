// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileNotice: Part of the FreeCAD project.
/******************************************************************************
 *                                                                            *
 *   © 2026 FreeCAD contributors                                              *
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   of the License, or (at your option) any later version.                   *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful,               *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty              *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                  *
 *   See the GNU Lesser General Public License for more details.              *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD. If not, see https://www.gnu.org/licenses     *
 *                                                                            *
 ******************************************************************************/

#pragma once

#include <memory>

#include <QDialogButtonBox>
#include <QWidget>

#include <Gui/TaskView/TaskDialog.h>

namespace App
{
class SavedView;
}  // namespace App

namespace Gui
{

class View3DInventor;
class ViewProviderSavedView;

class GuiExport SavedViewWidget: public QWidget
{
    Q_OBJECT

public:
    explicit SavedViewWidget(ViewProviderSavedView* viewProvider, QWidget* parent = nullptr);
    ~SavedViewWidget() override;

    void refresh();

private:
    ViewProviderSavedView* getViewProvider() const;
    App::SavedView* getSavedView() const;
    View3DInventor* getCurrentView() const;
    void refreshButtons();
    void refreshSummary();
    void setupConnections();

    void onApplyClicked();
    void onUpdateClicked();
    void onRestoreCameraToggled(bool on);
    void onRestoreVisibilityToggled(bool on);
    void onRestoreClippingToggled(bool on);

    void changeEvent(QEvent* event) override;

private:
    class Private;
    std::unique_ptr<Private> d;
};

class GuiExport TaskSavedView: public Gui::TaskView::TaskDialog
{
    Q_OBJECT

public:
    explicit TaskSavedView(ViewProviderSavedView* viewProvider);
    ~TaskSavedView() override;

    QDialogButtonBox::StandardButtons getStandardButtons() const override
    {
        return QDialogButtonBox::Close;
    }

    void open() override;
    void activate() override;
    bool accept() override;
    bool reject() override;

private:
    bool finishEditing();

    SavedViewWidget* widget {nullptr};
    ViewProviderSavedView* viewProvider {nullptr};
};

}  // namespace Gui
