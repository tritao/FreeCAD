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
#include <array>
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
#include <App/GeoFeature.h>

#include "ClippingPlaneManager.h"
#include "Document.h"
#include "Inventor/Draggers/Gizmo.h"
#include "PlaneGizmoEditor.h"
#include "QuantitySpinBox.h"
#include "Selection/Selection.h"
#include "TaskClippingPlane.h"
#include "ViewProvider.h"
#include "View3DInventor.h"
#include "ViewProviderClippingPlane.h"
#include "ui_TaskClippingPlane.h"

using namespace Gui;

namespace
{

struct FittedClippingPlaneHelper
{
    double length {100.0};
    double height {100.0};
    double arrow {35.0};
};

Base::BoundBox3d collectClippingPlaneHelperBounds(
    Gui::Document* guiDocument,
    Gui::MDIView* view,
    const std::vector<App::DocumentObject*>& objects,
    const App::DocumentObject* excludedObject
)
{
    Base::BoundBox3d bbox;

    if (!guiDocument) {
        return bbox;
    }

    for (auto* object : objects) {
        if (!object || object == excludedObject) {
            continue;
        }

        if (auto* viewProvider = guiDocument->getViewProvider(object)) {
            const auto objectBox = viewProvider->getBoundingBox(nullptr, true, view);
            if (objectBox.IsValid()) {
                bbox.Add(objectBox);
            }
        }
    }

    return bbox;
}

FittedClippingPlaneHelper fittedClippingPlaneHelper(
    const Base::Placement& placement,
    const Base::BoundBox3d& bbox
)
{
    if (!bbox.IsValid()) {
        return {};
    }

    const Base::Vector3d center = bbox.GetCenter();
    const Base::Rotation rotation = placement.getRotation();
    const Base::Vector3d planeX = rotation.multVec(Base::Vector3d(1.0, 0.0, 0.0));
    const Base::Vector3d planeY = rotation.multVec(Base::Vector3d(0.0, 1.0, 0.0));
    const std::array<double, 2> xs = {bbox.MinX, bbox.MaxX};
    const std::array<double, 2> ys = {bbox.MinY, bbox.MaxY};
    const std::array<double, 2> zs = {bbox.MinZ, bbox.MaxZ};

    double halfLength = 0.0;
    double halfHeight = 0.0;
    for (double x : xs) {
        for (double y : ys) {
            for (double z : zs) {
                const Base::Vector3d delta(x - center.x, y - center.y, z - center.z);
                halfLength = std::max(halfLength, std::abs(delta * planeX));
                halfHeight = std::max(halfHeight, std::abs(delta * planeY));
            }
        }
    }

    constexpr double helperPadding = 1.10;
    FittedClippingPlaneHelper helper;
    helper.length = std::max(1.0, halfLength * 2.0 * helperPadding);
    helper.height = std::max(1.0, halfHeight * 2.0 * helperPadding);
    helper.arrow = std::max(10.0, std::max(helper.length, helper.height) * 0.35);
    return helper;
}

void applyFittedClippingPlaneHelper(
    Gui::ViewProviderClippingPlane* viewProvider,
    const Base::Placement& placement,
    const Base::BoundBox3d& bbox
)
{
    if (!viewProvider || !bbox.IsValid()) {
        return;
    }

    const auto helper = fittedClippingPlaneHelper(placement, bbox);
    viewProvider->AutoSize.setValue(false);
    viewProvider->DisplayLength.setValue(static_cast<float>(helper.length));
    viewProvider->DisplayHeight.setValue(static_cast<float>(helper.height));
    viewProvider->ArrowSize.setValue(static_cast<float>(helper.arrow));
}

}  // namespace

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

    d->ui.planeOffsetSpin->setUnit(Base::Unit::Length);
    d->ui.planeOffsetSpin->setRange(-1.0e9, 1.0e9);
    d->ui.planeOffsetSpin->setSingleStep(1.0);

    d->ui.planeTiltXSpin->setUnit(Base::Unit::Angle);
    d->ui.planeTiltXSpin->setRange(-89.99, 89.99);
    d->ui.planeTiltXSpin->setSingleStep(1.0);

    d->ui.planeTiltYSpin->setUnit(Base::Unit::Angle);
    d->ui.planeTiltYSpin->setRange(-180.0, 180.0);
    d->ui.planeTiltYSpin->setSingleStep(1.0);

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

ClippingPlaneWidget::~ClippingPlaneWidget()
{
    stopPlaneEditing();
}

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

Base::Placement ClippingPlaneWidget::currentEditablePlanePlacement() const
{
    if (planeEditor) {
        return planeEditor->currentPlacement();
    }

    if (auto* plane = getPlane()) {
        return App::GeoFeature::getGlobalPlacement(plane);
    }

    return {};
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

    refreshPlane();
    refreshTargets();
    refreshScopeControls();
    refreshActivation();
    refreshButtons();
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

void ClippingPlaneWidget::refreshPlane()
{
    auto* plane = getPlane();

    const QSignalBlocker reverseBlocker(d->ui.reverseCheck);
    const QSignalBlocker offsetBlocker(d->ui.planeOffsetSpin);
    const QSignalBlocker tiltXBlocker(d->ui.planeTiltXSpin);
    const QSignalBlocker tiltYBlocker(d->ui.planeTiltYSpin);

    if (!plane) {
        d->ui.reverseCheck->setChecked(false);
        d->ui.planeOffsetSpin->setValue(0.0);
        d->ui.planeTiltXSpin->setValue(0.0);
        d->ui.planeTiltYSpin->setValue(0.0);
        return;
    }

    d->ui.reverseCheck->setChecked(plane->Reverse.getValue());
    const auto state = Gui::PlaneGizmoEditor::stateFromPlacement(currentEditablePlanePlacement());
    d->ui.planeOffsetSpin->setValue(Base::Quantity(state.offset, Base::Unit::Length));
    d->ui.planeTiltXSpin->setValue(Base::Quantity(state.tiltXDegrees, Base::Unit::Angle));
    d->ui.planeTiltYSpin->setValue(Base::Quantity(state.tiltYDegrees, Base::Unit::Angle));
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

void ClippingPlaneWidget::refreshButtons()
{
    auto* plane = getPlane();
    auto* vp = getViewProvider();
    const bool hasPlane = plane != nullptr;
    const bool hasView = getCurrentView() != nullptr;
    const bool editingPlaneIn3D = (planeEditor && planeEditor->isActive())
        || (vp && vp->isPanelPlaneEditActive());
    const bool presetNeedsView = d->ui.planePresetCombo->currentIndex()
        == static_cast<int>(Gui::PlaneGizmoEditor::Preset::View);

    {
        const QSignalBlocker blocker(d->ui.editIn3DButton);
        d->ui.editIn3DButton->setChecked(editingPlaneIn3D);
    }

    d->ui.editIn3DButton->setEnabled(hasPlane && hasView);
    d->ui.reverseCheck->setEnabled(hasPlane);
    d->ui.planeOffsetSpin->setEnabled(hasPlane);
    d->ui.planeTiltXSpin->setEnabled(hasPlane);
    d->ui.planeTiltYSpin->setEnabled(hasPlane);
    d->ui.planePresetCombo->setEnabled(hasPlane);
    d->ui.applyPlanePresetButton->setEnabled(hasPlane && (!presetNeedsView || hasView));
    d->ui.fitToSelectionButton->setEnabled(hasPlane && hasView);
    d->ui.fitToTargetsButton->setEnabled(hasPlane && plane && !plane->Targets.getValues().empty());
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
    refreshButtons();
}

Gui::PlaneGizmoEditor* ClippingPlaneWidget::ensurePlaneEditor()
{
    auto* vp = getViewProvider();
    if (!vp) {
        planeEditor.reset();
        return nullptr;
    }

    if (planeEditor && planeEditor->getViewProvider() == vp) {
        return planeEditor.get();
    }

    planeEditor = std::make_unique<Gui::PlaneGizmoEditor>(vp, this);
    connect(planeEditor.get(), &Gui::PlaneGizmoEditor::stateChanged, this, [this]() {
        refreshPlane();
        refreshActivation();
        refreshButtons();
    });
    connect(planeEditor.get(), &Gui::PlaneGizmoEditor::editingChanged, this, [this](bool) {
        refreshButtons();
    });
    connect(planeEditor.get(), &Gui::PlaneGizmoEditor::committed, this, [this]() { refresh(); });
    return planeEditor.get();
}

void ClippingPlaneWidget::stopPlaneEditing()
{
    if (planeEditor && planeEditor->isActive()) {
        planeEditor->finish(true);
    }
    else if (auto* vp = getViewProvider()) {
        vp->finishPanelPlaneEdit();
    }
}

void ClippingPlaneWidget::setupConnections()
{
    connect(d->ui.activeInCurrentView, &QCheckBox::toggled, this, &ClippingPlaneWidget::onActivationToggled);
    connect(d->ui.reverseCheck, &QCheckBox::toggled, this, &ClippingPlaneWidget::onReverseToggled);
    connect(d->ui.editIn3DButton, &QPushButton::toggled, this, &ClippingPlaneWidget::onEditIn3DToggled);
    connect(
        d->ui.planeOffsetSpin,
        qOverload<double>(&Gui::QuantitySpinBox::valueChanged),
        this,
        &ClippingPlaneWidget::onPlaneControlsChanged
    );
    connect(
        d->ui.planeTiltXSpin,
        qOverload<double>(&Gui::QuantitySpinBox::valueChanged),
        this,
        &ClippingPlaneWidget::onPlaneControlsChanged
    );
    connect(
        d->ui.planeTiltYSpin,
        qOverload<double>(&Gui::QuantitySpinBox::valueChanged),
        this,
        &ClippingPlaneWidget::onPlaneControlsChanged
    );
    connect(
        d->ui.planePresetCombo,
        qOverload<int>(&QComboBox::currentIndexChanged),
        this,
        &ClippingPlaneWidget::refreshButtons
    );
    connect(
        d->ui.applyPlanePresetButton,
        &QPushButton::clicked,
        this,
        &ClippingPlaneWidget::onApplyPlanePreset
    );
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
    connect(
        d->ui.fitToSelectionButton,
        &QPushButton::clicked,
        this,
        &ClippingPlaneWidget::onFitHelperToSelection
    );
    connect(
        d->ui.fitToTargetsButton,
        &QPushButton::clicked,
        this,
        &ClippingPlaneWidget::onFitHelperToTargets
    );
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

    refreshActivation();
    refreshButtons();
}

void ClippingPlaneWidget::onEditIn3DToggled(bool on)
{
    auto* vp = getViewProvider();
    auto* view = getCurrentView();
    auto* editor = ensurePlaneEditor();
    if (!vp || !view || !editor) {
        const QSignalBlocker blocker(d->ui.editIn3DButton);
        d->ui.editIn3DButton->setChecked(false);
        return;
    }

    if (!Gui::GizmoContainer::isEnabled()) {
        if (on) {
            const bool started = vp->startPanelPlaneEdit(view->getViewer(), [this]() { refresh(); });
            if (!started) {
                const QSignalBlocker blocker(d->ui.editIn3DButton);
                d->ui.editIn3DButton->setChecked(false);
            }
        }
        else {
            vp->finishPanelPlaneEdit();
        }

        refreshButtons();
        return;
    }

    if (on) {
        if (!editor->start(view->getViewer())) {
            const QSignalBlocker blocker(d->ui.editIn3DButton);
            d->ui.editIn3DButton->setChecked(false);
        }
    }
    else {
        editor->finish(true);
    }

    refreshButtons();
}

void ClippingPlaneWidget::onPlaneControlsChanged()
{
    auto* editor = ensurePlaneEditor();
    if (!editor) {
        refreshPlane();
        refreshButtons();
        return;
    }

    Gui::PlaneGizmoEditor::State state;
    state.offset = d->ui.planeOffsetSpin->rawValue();
    state.tiltXDegrees = d->ui.planeTiltXSpin->rawValue();
    state.tiltYDegrees = d->ui.planeTiltYSpin->rawValue();
    editor->setState(state, !editor->isActive());
}

void ClippingPlaneWidget::onApplyPlanePreset()
{
    auto* editor = ensurePlaneEditor();
    if (!editor) {
        refreshPlane();
        refreshButtons();
        return;
    }

    const auto preset = static_cast<Gui::PlaneGizmoEditor::Preset>(
        d->ui.planePresetCombo->currentIndex()
    );
    if (preset == Gui::PlaneGizmoEditor::Preset::View && !getCurrentView()) {
        refreshButtons();
        return;
    }

    editor->setPreset(preset, getCurrentView(), !editor->isActive());
}

void ClippingPlaneWidget::onScopeModeChanged(int index)
{
    if (auto* plane = getPlane()) {
        plane->ScopeMode.setValue(index);
    }

    refreshScopeControls();
    refreshButtons();
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

void ClippingPlaneWidget::onFitHelperToSelection()
{
    auto* plane = getPlane();
    auto* view = getCurrentView();
    auto* viewProvider = getViewProvider();
    if (!plane || !view || !viewProvider || !plane->getDocument()) {
        return;
    }

    std::vector<App::DocumentObject*> selectionObjects;
    for (const auto& selected :
         Gui::Selection().getSelection(plane->getDocument()->getName(), ResolveMode::NoResolve)) {
        auto* object = selected.pObject;
        if (!object || object->getDocument() != plane->getDocument()) {
            continue;
        }

        selectionObjects.push_back(object);
    }

    auto* guiDocument = viewProvider->getDocument();
    const auto bbox = collectClippingPlaneHelperBounds(guiDocument, view, selectionObjects, plane);
    if (!bbox.IsValid()) {
        return;
    }

    applyFittedClippingPlaneHelper(viewProvider, currentEditablePlanePlacement(), bbox);
    refresh();
}

void ClippingPlaneWidget::onFitHelperToTargets()
{
    auto* plane = getPlane();
    auto* view = getCurrentView();
    auto* viewProvider = getViewProvider();
    if (!plane || !view || !viewProvider) {
        return;
    }

    auto* guiDocument = viewProvider->getDocument();
    const auto bbox
        = collectClippingPlaneHelperBounds(guiDocument, view, plane->Targets.getValues(), plane);
    if (!bbox.IsValid()) {
        return;
    }

    applyFittedClippingPlaneHelper(viewProvider, currentEditablePlanePlacement(), bbox);
    refresh();
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
    if (widget) {
        widget->stopPlaneEditing();
    }

    if (auto* doc = viewProvider ? viewProvider->getDocument() : nullptr) {
        if (doc->hasPendingCommand()) {
            doc->commitCommand();
        }
        doc->resetEdit();
    }

    return true;
}

#include "moc_TaskClippingPlane.cpp"
