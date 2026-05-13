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

#include <algorithm>
#include <ranges>
#include <set>

#include <QByteArray>
#include <QEvent>
#include <QFont>
#include <QListWidgetItem>
#include <QPalette>
#include <QSignalBlocker>

#include <App/ClippingPlane.h>
#include <App/Document.h>
#include <App/DocumentObject.h>

#include "ClippingPlaneManager.h"
#include "Document.h"
#include "Selection/Selection.h"
#include "TaskClippingPlane.h"
#include "View3DInventor.h"
#include "ViewProviderClippingPlane.h"
#include "ui_TaskClippingPlane.h"

using namespace Gui;

class ClippingPlaneWidget::Private
{
public:
    Gui::Ui_ClippingPlaneWidget ui {};
    ViewProviderClippingPlane* viewProvider {nullptr};
};

/* TRANSLATOR Gui::ClippingPlaneWidget */

ClippingPlaneWidget::ClippingPlaneWidget(ViewProviderClippingPlane* viewProvider, QWidget* parent)
    : QWidget(parent)
    , d(std::make_unique<Private>())
{
    d->viewProvider = viewProvider;
    d->ui.setupUi(this);

    QPalette hintPalette = d->ui.dragHintLabel->palette();
    hintPalette.setColor(
        QPalette::WindowText,
        palette().color(QPalette::Disabled, QPalette::WindowText)
    );
    d->ui.dragHintLabel->setPalette(hintPalette);

    QFont hintFont = d->ui.dragHintLabel->font();
    hintFont.setPointSizeF(std::max(8.0, hintFont.pointSizeF() - 1.0));
    d->ui.dragHintLabel->setFont(hintFont);

    setupConnections();
    refresh();
}

ClippingPlaneWidget::~ClippingPlaneWidget() = default;

ViewProviderClippingPlane* ClippingPlaneWidget::getViewProvider() const
{
    return d->viewProvider;
}

App::ClippingPlane* ClippingPlaneWidget::getPlane() const
{
    auto* vp = getViewProvider();
    return vp ? vp->getObject<App::ClippingPlane>() : nullptr;
}

View3DInventor* ClippingPlaneWidget::getCurrentView() const
{
    auto* vp = getViewProvider();
    auto* doc = vp ? vp->getDocument() : nullptr;
    return doc ? qobject_cast<View3DInventor*>(doc->getActiveView()) : nullptr;
}

void ClippingPlaneWidget::refresh()
{
    auto* vp = getViewProvider();
    auto* plane = getPlane();
    if (!vp || !plane) {
        return;
    }

    {
        const QSignalBlocker activeBlocker(d->ui.activeInCurrentView);
        const QSignalBlocker reverseBlocker(d->ui.reverseCheck);
        const QSignalBlocker scopeBlocker(d->ui.scopeModeCombo);
        const QSignalBlocker autoSizeBlocker(d->ui.autoSizeCheck);
        const QSignalBlocker helperBlocker(d->ui.showHelperCheck);

        d->ui.reverseCheck->setChecked(plane->Reverse.getValue());
        d->ui.scopeModeCombo->setCurrentIndex(static_cast<int>(plane->ScopeMode.getValue()));
        d->ui.autoSizeCheck->setChecked(vp->AutoSize.getValue());
        d->ui.showHelperCheck->setChecked(vp->Visibility.getValue());
    }

    refreshTargets();
    refreshScopeControls();
    refreshActivation();
}

void ClippingPlaneWidget::refreshActivation()
{
    auto* plane = getPlane();
    auto* view = getCurrentView();
    const QSignalBlocker blocker(d->ui.activeInCurrentView);

    if (!plane || !view) {
        d->ui.activeInCurrentView->setEnabled(false);
        d->ui.activeInCurrentView->setChecked(false);
        d->ui.activationStateLabel->setVisible(true);
        d->ui.activationStateLabel->setText(tr("No active 3D view is available."));
        return;
    }

    const bool active = ClippingPlaneManager::instance().isActive(view, plane);
    d->ui.activeInCurrentView->setEnabled(true);
    d->ui.activeInCurrentView->setChecked(active);
    d->ui.activationStateLabel->clear();
    d->ui.activationStateLabel->setVisible(false);
}

void ClippingPlaneWidget::refreshTargets()
{
    auto* plane = getPlane();
    if (!plane) {
        return;
    }

    d->ui.targetsList->clear();
    for (auto* target : plane->Targets.getValues()) {
        if (!target) {
            continue;
        }

        auto* item
            = new QListWidgetItem(QString::fromUtf8(target->Label.getValue()), d->ui.targetsList);
        item->setData(Qt::UserRole, QByteArray(target->getNameInDocument()));
        item->setToolTip(QString::fromUtf8(target->getNameInDocument()));
    }
}

void ClippingPlaneWidget::refreshScopeControls()
{
    const bool scoped = d->ui.scopeModeCombo->currentIndex() != 0;
    d->ui.targetsLabel->setVisible(scoped);
    d->ui.targetsList->setVisible(scoped);
    d->ui.addSelectedButton->setVisible(scoped);
    d->ui.removeSelectedButton->setVisible(scoped);
    d->ui.clearTargetsButton->setVisible(scoped);

    d->ui.targetsLabel->setEnabled(scoped);
    d->ui.targetsList->setEnabled(scoped);
    d->ui.addSelectedButton->setEnabled(scoped);
    d->ui.removeSelectedButton->setEnabled(scoped && !d->ui.targetsList->selectedItems().isEmpty());
    d->ui.clearTargetsButton->setEnabled(scoped && d->ui.targetsList->count() > 0);
}

void ClippingPlaneWidget::setTargets(const std::vector<App::DocumentObject*>& targets)
{
    auto* plane = getPlane();
    if (!plane) {
        return;
    }

    plane->Targets.setValues(targets);
    refreshTargets();
    refreshScopeControls();
}

void ClippingPlaneWidget::setupConnections()
{
    connect(d->ui.activeInCurrentView, &QCheckBox::toggled, this, &ClippingPlaneWidget::onActivationToggled);
    connect(d->ui.reverseCheck, &QCheckBox::toggled, this, &ClippingPlaneWidget::onReverseToggled);
    connect(
        d->ui.scopeModeCombo,
        qOverload<int>(&QComboBox::currentIndexChanged),
        this,
        &ClippingPlaneWidget::onScopeModeChanged
    );
    connect(d->ui.addSelectedButton, &QPushButton::clicked, this, &ClippingPlaneWidget::onAddSelected);
    connect(
        d->ui.targetsList,
        &QListWidget::itemSelectionChanged,
        this,
        &ClippingPlaneWidget::refreshScopeControls
    );
    connect(
        d->ui.removeSelectedButton,
        &QPushButton::clicked,
        this,
        &ClippingPlaneWidget::onRemoveSelectedTargets
    );
    connect(d->ui.clearTargetsButton, &QPushButton::clicked, this, &ClippingPlaneWidget::onClearTargets);
    connect(d->ui.autoSizeCheck, &QCheckBox::toggled, this, &ClippingPlaneWidget::onAutoSizeToggled);
    connect(d->ui.showHelperCheck, &QCheckBox::toggled, this, &ClippingPlaneWidget::onShowHelperToggled);
}

void ClippingPlaneWidget::onActivationToggled(bool on)
{
    auto* plane = getPlane();
    auto* view = getCurrentView();
    if (!plane || !view) {
        refreshActivation();
        return;
    }

    if (on) {
        ClippingPlaneManager::instance().activate(view, plane);
    }
    else {
        ClippingPlaneManager::instance().deactivate(view, plane);
    }

    refreshActivation();
}

void ClippingPlaneWidget::onReverseToggled(bool on)
{
    if (auto* plane = getPlane()) {
        plane->Reverse.setValue(on);
    }
}

void ClippingPlaneWidget::onScopeModeChanged(int index)
{
    if (auto* plane = getPlane()) {
        plane->ScopeMode.setValue(index);
    }

    refreshScopeControls();
}

void ClippingPlaneWidget::onAddSelected()
{
    auto* plane = getPlane();
    if (!plane || !plane->getDocument()) {
        return;
    }

    std::vector<App::DocumentObject*> targets = plane->Targets.getValues();
    std::set<std::string> targetNames;
    for (auto* target : targets) {
        if (target) {
            targetNames.emplace(target->getNameInDocument());
        }
    }

    for (const auto& sel :
         Gui::Selection().getSelection(plane->getDocument()->getName(), ResolveMode::NoResolve)) {
        auto* obj = sel.pObject;
        if (!obj || obj == plane || obj->getDocument() != plane->getDocument()) {
            continue;
        }
        if (targetNames.insert(obj->getNameInDocument()).second) {
            targets.push_back(obj);
        }
    }

    setTargets(targets);
}

void ClippingPlaneWidget::onRemoveSelectedTargets()
{
    auto* plane = getPlane();
    if (!plane) {
        return;
    }

    std::set<std::string> removed;
    for (auto* item : d->ui.targetsList->selectedItems()) {
        removed.emplace(item->data(Qt::UserRole).toByteArray().constData());
    }

    std::vector<App::DocumentObject*> remaining;
    for (auto* target : plane->Targets.getValues()) {
        if (!target) {
            continue;
        }
        if (!removed.contains(target->getNameInDocument())) {
            remaining.push_back(target);
        }
    }

    setTargets(remaining);
}

void ClippingPlaneWidget::onClearTargets()
{
    setTargets({});
}

void ClippingPlaneWidget::onAutoSizeToggled(bool on)
{
    if (auto* vp = getViewProvider()) {
        vp->AutoSize.setValue(on);
    }
}

void ClippingPlaneWidget::onShowHelperToggled(bool on)
{
    if (auto* vp = getViewProvider()) {
        vp->Visibility.setValue(on);
    }
}

void ClippingPlaneWidget::changeEvent(QEvent* event)
{
    QWidget::changeEvent(event);
    if (event->type() == QEvent::LanguageChange) {
        d->ui.retranslateUi(this);
        refresh();
    }
}

TaskClippingPlane::TaskClippingPlane(ViewProviderClippingPlane* viewProvider)
    : widget(new ClippingPlaneWidget(viewProvider))
    , viewProvider(viewProvider)
{
    addTaskBoxWithoutHeader(widget);

    if (viewProvider && viewProvider->getObject()) {
        setDocumentName(viewProvider->getObject()->getDocument()->getName());
        setAutoCloseOnDeletedDocument(true);
        associateToObject3dView(viewProvider->getObject());
    }
}

TaskClippingPlane::~TaskClippingPlane() = default;

void TaskClippingPlane::open()
{
    if (widget) {
        widget->refresh();
    }
    TaskDialog::open();
}

void TaskClippingPlane::activate()
{
    if (widget) {
        widget->refresh();
    }
    TaskDialog::activate();
}

bool TaskClippingPlane::accept()
{
    return finishEditing() && TaskDialog::accept();
}

bool TaskClippingPlane::reject()
{
    return finishEditing() && TaskDialog::reject();
}

bool TaskClippingPlane::finishEditing()
{
    if (auto* doc = viewProvider ? viewProvider->getDocument() : nullptr) {
        if (doc->hasPendingCommand()) {
            doc->commitCommand();
        }
        doc->resetEdit();
    }

    return true;
}

#include "moc_TaskClippingPlane.cpp"
