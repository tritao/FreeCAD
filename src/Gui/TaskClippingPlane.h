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

#include <Base/Placement.h>

#include <Gui/TaskView/TaskDialog.h>

namespace App
{
class ClippingPlane;
class DocumentObject;
}  // namespace App

namespace Gui
{

class PlaneGizmoEditor;
class View3DInventor;
class ViewProviderClippingPlane;

class GuiExport ClippingPlaneWidget: public QWidget
{
    Q_OBJECT

public:
    explicit ClippingPlaneWidget(ViewProviderClippingPlane* viewProvider, QWidget* parent = nullptr);
    ~ClippingPlaneWidget() override;

    void refresh();
    void stopPlaneEditing();

private:
    ViewProviderClippingPlane* getViewProvider() const;
    App::ClippingPlane* getPlane() const;
    View3DInventor* getCurrentView() const;
    Base::Placement currentEditablePlanePlacement() const;
    void refreshActivation();
    void refreshPlane();
    void refreshTargets();
    void refreshScopeControls();
    void refreshButtons();
    void setTargets(const std::vector<App::DocumentObject*>& targets);
    Gui::PlaneGizmoEditor* ensurePlaneEditor();
    void setupConnections();

    void onActivationToggled(bool on);
    void onReverseToggled(bool on);
    void onEditIn3DToggled(bool on);
    void onPlaneControlsChanged();
    void onApplyPlanePreset();
    void onScopeModeChanged(int index);
    void onAddSelected();
    void onRemoveSelectedTargets();
    void onClearTargets();
    void onAutoSizeToggled(bool on);
    void onShowHelperToggled(bool on);

    void changeEvent(QEvent* event) override;

private:
    class Private;
    std::unique_ptr<Private> d;
    std::unique_ptr<Gui::PlaneGizmoEditor> planeEditor;
};

class GuiExport TaskClippingPlane: public Gui::TaskView::TaskDialog
{
    Q_OBJECT

public:
    explicit TaskClippingPlane(ViewProviderClippingPlane* viewProvider);
    ~TaskClippingPlane() override;

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

    ClippingPlaneWidget* widget {nullptr};
    ViewProviderClippingPlane* viewProvider {nullptr};
};

}  // namespace Gui
