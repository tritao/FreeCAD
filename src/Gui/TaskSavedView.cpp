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

#include "PreCompiled.h"

#include <QEvent>
#include <QListWidgetItem>
#include <QSignalBlocker>

#include <App/AutoTransaction.h>
#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/SavedView.h>

#include "Document.h"
#include "SavedViewManager.h"
#include "TaskSavedView.h"
#include "View3DInventor.h"
#include "ViewProviderSavedView.h"
#include "ui_TaskSavedView.h"

using namespace Gui;

class SavedViewWidget::Private
{
public:
    Ui::SavedViewWidget ui {};
    ViewProviderSavedView* viewProvider {nullptr};
};

/* TRANSLATOR Gui::SavedViewWidget */

SavedViewWidget::SavedViewWidget(ViewProviderSavedView* viewProvider, QWidget* parent)
    : QWidget(parent)
    , d(std::make_unique<Private>())
{
    d->viewProvider = viewProvider;
    d->ui.setupUi(this);
    setupConnections();
    refresh();
}

SavedViewWidget::~SavedViewWidget() = default;

ViewProviderSavedView* SavedViewWidget::getViewProvider() const
{
    return d->viewProvider;
}

App::SavedView* SavedViewWidget::getSavedView() const
{
    auto* vp = getViewProvider();
    return vp ? vp->getObject<App::SavedView>() : nullptr;
}

View3DInventor* SavedViewWidget::getCurrentView() const
{
    auto* vp = getViewProvider();
    auto* doc = vp ? vp->getDocument() : nullptr;
    return doc ? qobject_cast<View3DInventor*>(doc->getActiveView()) : nullptr;
}

void SavedViewWidget::refresh()
{
    auto* savedView = getSavedView();
    if (!savedView) {
        return;
    }

    {
        const QSignalBlocker cameraBlocker(d->ui.restoreCameraCheck);
        const QSignalBlocker visibilityBlocker(d->ui.restoreVisibilityCheck);
        const QSignalBlocker clippingBlocker(d->ui.restoreClippingCheck);

        d->ui.restoreCameraCheck->setChecked(savedView->RestoreCamera.getValue());
        d->ui.restoreVisibilityCheck->setChecked(savedView->RestoreVisibility.getValue());
        d->ui.restoreClippingCheck->setChecked(savedView->RestoreClipping.getValue());
    }

    refreshButtons();
    refreshSummary();
}

void SavedViewWidget::refreshButtons()
{
    const bool hasView = getCurrentView() != nullptr;
    d->ui.applyButton->setEnabled(hasView);
    d->ui.updateButton->setEnabled(hasView);
    d->ui.viewStateLabel->setVisible(!hasView);
    d->ui.viewStateLabel->setText(hasView ? QString() : tr("No active 3D view is available."));
}

void SavedViewWidget::refreshSummary()
{
    auto* savedView = getSavedView();
    if (!savedView) {
        return;
    }

    const bool hasCamera = savedView->CameraState.getValue() && *savedView->CameraState.getValue();
    d->ui.cameraStateValue->setText(hasCamera ? tr("Saved") : tr("Not saved"));
    d->ui.visibilityStateValue->setText(
        tr("%1 object states").arg(savedView->VisibilityState.getValues().size())
    );

    d->ui.clippingPlanesList->clear();
    QString singlePlaneLabel;
    for (auto* obj : savedView->ClipPlanes.getValues()) {
        auto* plane = freecad_cast<App::ClippingPlane*>(obj);
        if (!plane) {
            continue;
        }

        if (singlePlaneLabel.isEmpty()) {
            singlePlaneLabel = QString::fromUtf8(plane->Label.getValue());
        }
        auto* item = new QListWidgetItem(
            QString::fromUtf8(plane->Label.getValue()),
            d->ui.clippingPlanesList
        );
        item->setToolTip(QString::fromUtf8(plane->getNameInDocument()));
    }

    const int clippingPlaneCount = d->ui.clippingPlanesList->count();
    d->ui.clippingStateValue->setText(tr("%1 clipping plane(s)").arg(clippingPlaneCount));

    const bool hasSinglePlane = clippingPlaneCount == 1;
    const bool hasMultiplePlanes = clippingPlaneCount > 1;
    d->ui.singleClippingPlaneLabel->setVisible(hasSinglePlane);
    d->ui.singleClippingPlaneValue->setVisible(hasSinglePlane);
    d->ui.singleClippingPlaneValue->setText(hasSinglePlane ? singlePlaneLabel : QString());
    d->ui.clippingPlanesLabel->setVisible(hasMultiplePlanes);
    d->ui.clippingPlanesList->setVisible(hasMultiplePlanes);
}

void SavedViewWidget::setupConnections()
{
    connect(d->ui.applyButton, &QPushButton::clicked, this, &SavedViewWidget::onApplyClicked);
    connect(d->ui.updateButton, &QPushButton::clicked, this, &SavedViewWidget::onUpdateClicked);
    connect(d->ui.restoreCameraCheck, &QCheckBox::toggled, this, &SavedViewWidget::onRestoreCameraToggled);
    connect(
        d->ui.restoreVisibilityCheck,
        &QCheckBox::toggled,
        this,
        &SavedViewWidget::onRestoreVisibilityToggled
    );
    connect(
        d->ui.restoreClippingCheck,
        &QCheckBox::toggled,
        this,
        &SavedViewWidget::onRestoreClippingToggled
    );
}

void SavedViewWidget::onApplyClicked()
{
    auto* savedView = getSavedView();
    auto* view = getCurrentView();
    if (!savedView || !view) {
        refreshButtons();
        return;
    }

    SavedViewManager::restore(view, savedView);
    refresh();
}

void SavedViewWidget::onUpdateClicked()
{
    auto* savedView = getSavedView();
    auto* view = getCurrentView();
    auto* doc = getViewProvider() ? getViewProvider()->getDocument() : nullptr;
    if (!savedView || !view || !doc) {
        refreshButtons();
        return;
    }

    App::AutoTransaction guard(doc->openCommand(QT_TRANSLATE_NOOP("Command", "Update saved view")));
    SavedViewManager::capture(view, savedView);
    refresh();
}

void SavedViewWidget::onRestoreCameraToggled(bool on)
{
    if (auto* savedView = getSavedView()) {
        savedView->RestoreCamera.setValue(on);
    }
}

void SavedViewWidget::onRestoreVisibilityToggled(bool on)
{
    if (auto* savedView = getSavedView()) {
        savedView->RestoreVisibility.setValue(on);
    }
}

void SavedViewWidget::onRestoreClippingToggled(bool on)
{
    if (auto* savedView = getSavedView()) {
        savedView->RestoreClipping.setValue(on);
    }
}

void SavedViewWidget::changeEvent(QEvent* event)
{
    QWidget::changeEvent(event);
    if (event->type() == QEvent::LanguageChange) {
        d->ui.retranslateUi(this);
        refresh();
    }
}

TaskSavedView::TaskSavedView(ViewProviderSavedView* viewProvider)
    : widget(new SavedViewWidget(viewProvider))
    , viewProvider(viewProvider)
{
    addTaskBoxWithoutHeader(widget);

    if (viewProvider && viewProvider->getObject()) {
        setDocumentName(viewProvider->getObject()->getDocument()->getName());
        setAutoCloseOnDeletedDocument(true);
        associateToObject3dView(viewProvider->getObject());
    }
}

TaskSavedView::~TaskSavedView() = default;

void TaskSavedView::open()
{
    if (widget) {
        widget->refresh();
    }
    TaskDialog::open();
}

void TaskSavedView::activate()
{
    if (widget) {
        widget->refresh();
    }
    TaskDialog::activate();
}

bool TaskSavedView::accept()
{
    return finishEditing() && TaskDialog::accept();
}

bool TaskSavedView::reject()
{
    return finishEditing() && TaskDialog::reject();
}

bool TaskSavedView::finishEditing()
{
    if (auto* doc = viewProvider ? viewProvider->getDocument() : nullptr) {
        if (doc->hasPendingCommand()) {
            doc->commitCommand();
        }
        doc->resetEdit();
    }

    return true;
}

#include "moc_TaskSavedView.cpp"
