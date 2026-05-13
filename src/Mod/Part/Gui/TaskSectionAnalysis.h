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
class ClippingPlane;
class DocumentObject;
}  // namespace App

namespace Gui
{
class View3DInventor;
}  // namespace Gui

namespace Part
{
class SectionAnalysis;
}

namespace PartGui
{

class ViewProviderSectionAnalysis;

class PartGuiExport SectionAnalysisWidget: public QWidget
{
    Q_OBJECT

public:
    explicit SectionAnalysisWidget(ViewProviderSectionAnalysis* viewProvider, QWidget* parent = nullptr);
    ~SectionAnalysisWidget() override;

    void refresh();

private:
    ViewProviderSectionAnalysis* getViewProvider() const;
    Part::SectionAnalysis* getSectionAnalysis() const;
    App::ClippingPlane* getClippingPlane() const;
    Gui::View3DInventor* getCurrentView() const;
    void refreshClippingPlane();
    void refreshSources();
    void refreshResult();
    void refreshActivation();
    void refreshButtons();
    void setSources(const std::vector<App::DocumentObject*>& sources);
    void selectObjects(const std::vector<App::DocumentObject*>& objects);
    void setupConnections();

    void onResultModeChanged(int index);
    void onRecomputeClicked();
    void onUseCurrentSelectionAsSources();
    void onSelectSources();
    void onActivationToggled(bool on);
    void onSelectClippingPlane();
    void onEditClippingPlane();

    void changeEvent(QEvent* event) override;

private:
    class Private;
    std::unique_ptr<Private> d;
};

class PartGuiExport TaskSectionAnalysis: public Gui::TaskView::TaskDialog
{
    Q_OBJECT

public:
    explicit TaskSectionAnalysis(ViewProviderSectionAnalysis* viewProvider);
    ~TaskSectionAnalysis() override;

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

    SectionAnalysisWidget* widget {nullptr};
    ViewProviderSectionAnalysis* viewProvider {nullptr};
};

}  // namespace PartGui
