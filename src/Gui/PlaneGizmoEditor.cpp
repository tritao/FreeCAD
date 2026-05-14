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

#include "PlaneGizmoEditor.h"

#include <algorithm>

#include <QSignalBlocker>
#include <QTimer>

#include <App/ClippingPlane.h>
#include <App/GeoFeature.h>
#include <Base/Tools.h>

#include "ClippingPlaneManager.h"
#include "Inventor/Draggers/Gizmo.h"
#include "QuantitySpinBox.h"
#include "View3DInventor.h"
#include "View3DInventorViewer.h"
#include "ViewProviderClippingPlane.h"

using namespace Gui;

PlaneGizmoEditor::PlaneGizmoEditor(ViewProviderClippingPlane* viewProvider, QObject* parent)
    : QObject(parent)
    , viewProvider(viewProvider)
{
    offsetDeltaSpin = new QuantitySpinBox;
    offsetDeltaSpin->setUnit(Base::Unit::Length);
    offsetDeltaSpin->setRange(-1.0e9, 1.0e9);
    offsetDeltaSpin->hide();

    tiltXDeltaSpin = new QuantitySpinBox;
    tiltXDeltaSpin->setUnit(Base::Unit::Angle);
    tiltXDeltaSpin->setRange(-180.0, 180.0);
    tiltXDeltaSpin->hide();

    tiltYDeltaSpin = new QuantitySpinBox;
    tiltYDeltaSpin->setUnit(Base::Unit::Angle);
    tiltYDeltaSpin->setRange(-180.0, 180.0);
    tiltYDeltaSpin->hide();

    connect(
        offsetDeltaSpin,
        qOverload<double>(&QuantitySpinBox::valueChanged),
        this,
        &PlaneGizmoEditor::onDeltaChanged
    );
    connect(
        tiltXDeltaSpin,
        qOverload<double>(&QuantitySpinBox::valueChanged),
        this,
        &PlaneGizmoEditor::onDeltaChanged
    );
    connect(
        tiltYDeltaSpin,
        qOverload<double>(&QuantitySpinBox::valueChanged),
        this,
        &PlaneGizmoEditor::onDeltaChanged
    );

    rebaseTimer = new QTimer(this);
    rebaseTimer->setSingleShot(true);
    rebaseTimer->setInterval(150);
    connect(rebaseTimer, &QTimer::timeout, this, &PlaneGizmoEditor::rebaseGizmo);
}

PlaneGizmoEditor::~PlaneGizmoEditor()
{
    finish(false);
    delete offsetDeltaSpin;
    delete tiltXDeltaSpin;
    delete tiltYDeltaSpin;
}

ViewProviderClippingPlane* PlaneGizmoEditor::getViewProvider() const
{
    return viewProvider;
}

App::ClippingPlane* PlaneGizmoEditor::getPlane() const
{
    return viewProvider ? viewProvider->getObject<App::ClippingPlane>() : nullptr;
}

bool PlaneGizmoEditor::isActive() const
{
    return gizmoContainer != nullptr;
}

Base::Placement PlaneGizmoEditor::currentPlacement() const
{
    if (previewDirty) {
        return previewPlacement;
    }

    if (auto* plane = getPlane()) {
        return App::GeoFeature::getGlobalPlacement(plane);
    }

    return {};
}

PlaneGizmoEditor::State PlaneGizmoEditor::currentState() const
{
    return stateFromPlacement(currentPlacement());
}

bool PlaneGizmoEditor::start(View3DInventorViewer* activeViewer)
{
    auto* plane = getPlane();
    if (!plane || !viewProvider || !activeViewer) {
        return false;
    }

    if (gizmoContainer) {
        return viewer == activeViewer;
    }

    offsetGizmo = new LinearGizmo(offsetDeltaSpin);
    tiltXGizmo = new RotationGizmo(tiltXDeltaSpin);
    tiltYGizmo = new RotationGizmo(tiltYDeltaSpin);
    gizmoContainer = GizmoContainer::create({offsetGizmo, tiltXGizmo, tiltYGizmo}, viewProvider);

    viewer = activeViewer;
    Base::Placement origin;
    gizmoContainer->attachViewer(viewer, origin);
    gizmoContainer->visible = true;

    const State state = currentState();
    baseOffset = state.offset;
    baseTiltXDegrees = state.tiltXDegrees;
    baseTiltYDegrees = state.tiltYDegrees;

    previewPlacement = placementFromState(state);
    previewDirty = true;
    ClippingPlaneManager::instance().setPreviewPlacement(plane, previewPlacement);

    resetDeltaControls();
    viewProvider->setPanelPlaneEditActive(true);
    syncGizmo();

    Q_EMIT editingChanged(true);
    Q_EMIT stateChanged();
    return true;
}

void PlaneGizmoEditor::finish(bool commitPreview)
{
    auto* plane = getPlane();
    const bool hadActiveEdit = isActive();
    bool committedPlacement = false;

    rebaseTimer->stop();

    if (commitPreview && plane && previewDirty) {
        plane->Placement.setValue(localPlacementFromGlobal(*plane, previewPlacement));
        committedPlacement = true;
    }

    clearPreview();

    if (viewer) {
        viewer->resetEditingRoot(false);
        viewer = nullptr;
    }

    gizmoContainer.reset();
    offsetGizmo = nullptr;
    tiltXGizmo = nullptr;
    tiltYGizmo = nullptr;
    resetDeltaControls();

    if (viewProvider) {
        viewProvider->setPanelPlaneEditActive(false);
    }

    if (hadActiveEdit) {
        Q_EMIT editingChanged(false);
    }
    Q_EMIT stateChanged();
    if (committedPlacement) {
        Q_EMIT committed();
    }
}

void PlaneGizmoEditor::setState(const State& state, bool commitPlacement)
{
    auto* plane = getPlane();
    if (!plane) {
        return;
    }

    const Base::Placement placement = placementFromState(state);
    if (commitPlacement) {
        plane->Placement.setValue(localPlacementFromGlobal(*plane, placement));
        clearPreview();
        Q_EMIT stateChanged();
        Q_EMIT committed();
        return;
    }

    applyPreviewPlacement(placement);
    baseOffset = state.offset;
    baseTiltXDegrees = state.tiltXDegrees;
    baseTiltYDegrees = state.tiltYDegrees;
    resetDeltaControls();
    syncGizmo();
    Q_EMIT stateChanged();
}

void PlaneGizmoEditor::setPreset(Preset preset, View3DInventor* view, bool commitPlacement)
{
    Base::Vector3d normal = presetNormal(preset, view);
    normal.Normalize();

    State state;
    state.offset = currentState().offset;
    state.tiltXDegrees = Base::toDegrees<double>(std::asin(std::clamp(normal.y, -1.0, 1.0)));
    state.tiltYDegrees = Base::toDegrees<double>(std::atan2(-normal.x, -normal.z));
    setState(state, commitPlacement);
}

PlaneGizmoEditor::State PlaneGizmoEditor::stateFromPlacement(const Base::Placement& placement)
{
    const Base::Vector3d normal = normalizedSectionNormal(placement);

    State state;
    state.offset = sectionOffsetFromPlacement(placement);
    state.tiltXDegrees = Base::toDegrees<double>(std::asin(std::clamp(normal.y, -1.0, 1.0)));
    state.tiltYDegrees = Base::toDegrees<double>(std::atan2(-normal.x, -normal.z));
    return state;
}

Base::Placement PlaneGizmoEditor::placementFromState(const State& state)
{
    Base::Placement placement;
    placement.setRotation(rotationForTiltAngles(state.tiltXDegrees, state.tiltYDegrees));
    placement.setPosition(normalizedSectionNormal(placement) * state.offset);
    return placement;
}

Base::Vector3d PlaneGizmoEditor::presetNormal(Preset preset, View3DInventor* view)
{
    switch (preset) {
        case Preset::XY:
            return Base::Vector3d(0.0, 0.0, -1.0);
        case Preset::XZ:
            return Base::Vector3d(0.0, -1.0, 0.0);
        case Preset::YZ:
            return Base::Vector3d(-1.0, 0.0, 0.0);
        case Preset::View:
            break;
    }

    if (!view) {
        return Base::Vector3d(0.0, 0.0, -1.0);
    }

    const SbVec3f viewDirection = view->getViewer()->getViewDirection();
    return Base::Vector3d(
        static_cast<double>(viewDirection[0]),
        static_cast<double>(viewDirection[1]),
        static_cast<double>(viewDirection[2])
    );
}

void PlaneGizmoEditor::onDeltaChanged()
{
    if (!gizmoContainer || suppressDeltaUpdates) {
        return;
    }

    State state;
    state.offset = baseOffset + offsetDeltaSpin->rawValue();
    state.tiltXDegrees = baseTiltXDegrees + tiltXDeltaSpin->rawValue();
    state.tiltYDegrees = baseTiltYDegrees + tiltYDeltaSpin->rawValue();

    applyPreviewPlacement(placementFromState(state));
    rebaseTimer->start();
    Q_EMIT stateChanged();
}

void PlaneGizmoEditor::rebaseGizmo()
{
    if (!gizmoContainer) {
        return;
    }

    const State state = currentState();
    baseOffset = state.offset;
    baseTiltXDegrees = state.tiltXDegrees;
    baseTiltYDegrees = state.tiltYDegrees;
    resetDeltaControls();
    syncGizmo();
}

void PlaneGizmoEditor::applyPreviewPlacement(const Base::Placement& placement)
{
    if (auto* plane = getPlane()) {
        previewPlacement = placement;
        previewDirty = true;
        ClippingPlaneManager::instance().setPreviewPlacement(plane, previewPlacement);
    }
}

void PlaneGizmoEditor::clearPreview()
{
    if (auto* plane = getPlane()) {
        ClippingPlaneManager::instance().clearPreviewPlacement(plane);
    }
    previewDirty = false;
    previewPlacement = {};
}

void PlaneGizmoEditor::resetDeltaControls()
{
    suppressDeltaUpdates = true;
    const QSignalBlocker offsetBlocker(offsetDeltaSpin);
    const QSignalBlocker tiltXBlocker(tiltXDeltaSpin);
    const QSignalBlocker tiltYBlocker(tiltYDeltaSpin);
    offsetDeltaSpin->setValue(Base::Quantity(0.0, Base::Unit::Length));
    tiltXDeltaSpin->setValue(Base::Quantity(0.0, Base::Unit::Angle));
    tiltYDeltaSpin->setValue(Base::Quantity(0.0, Base::Unit::Angle));
    suppressDeltaUpdates = false;
}

void PlaneGizmoEditor::syncGizmo()
{
    if (!gizmoContainer || !offsetGizmo || !tiltXGizmo || !tiltYGizmo) {
        return;
    }

    const Base::Placement placement = currentPlacement();
    const Base::Vector3d position = placement.getPosition();
    const Base::Rotation rotation = placement.getRotation();
    const Base::Vector3d normal = normalizedSectionNormal(placement);
    const Base::Vector3d xAxis = rotation.multVec(Base::Vector3d::UnitX);
    const Base::Vector3d yAxis = rotation.multVec(Base::Vector3d::UnitY);

    offsetGizmo->Gizmo::setDraggerPlacement(position, normal);
    tiltXGizmo->Gizmo::setDraggerPlacement(position, xAxis);
    tiltYGizmo->Gizmo::setDraggerPlacement(position, yAxis);
    gizmoContainer->calculateScaleAndOrientation();
}

Base::Placement PlaneGizmoEditor::parentPlacement(const App::ClippingPlane& plane)
{
    return App::GeoFeature::getGlobalPlacement(&plane) * plane.Placement.getValue().inverse();
}

Base::Placement PlaneGizmoEditor::localPlacementFromGlobal(
    const App::ClippingPlane& plane,
    const Base::Placement& globalPlacement
)
{
    return parentPlacement(plane).inverse() * globalPlacement;
}

Base::Vector3d PlaneGizmoEditor::sectionNormalFromPlacement(const Base::Placement& placement)
{
    return placement.getRotation().multVec(Base::Vector3d(0.0, 0.0, -1.0));
}

Base::Vector3d PlaneGizmoEditor::normalizedSectionNormal(const Base::Placement& placement)
{
    Base::Vector3d normal = sectionNormalFromPlacement(placement);
    normal.Normalize();
    return normal;
}

double PlaneGizmoEditor::sectionOffsetFromPlacement(const Base::Placement& placement)
{
    return placement.getPosition() * normalizedSectionNormal(placement);
}

Base::Rotation PlaneGizmoEditor::rotationForTiltAngles(double tiltXDegrees, double tiltYDegrees)
{
    const double tiltXRadians = Base::toRadians<double>(tiltXDegrees);
    const double tiltYRadians = Base::toRadians<double>(tiltYDegrees);

    Base::Vector3d xAxis(std::cos(tiltYRadians), 0.0, -std::sin(tiltYRadians));
    Base::Vector3d yAxis(
        std::sin(tiltYRadians) * std::sin(tiltXRadians),
        std::cos(tiltXRadians),
        std::cos(tiltYRadians) * std::sin(tiltXRadians)
    );
    Base::Vector3d zAxis = -Base::Vector3d(
        -std::sin(tiltYRadians) * std::cos(tiltXRadians),
        std::sin(tiltXRadians),
        -std::cos(tiltYRadians) * std::cos(tiltXRadians)
    );

    xAxis.Normalize();
    yAxis.Normalize();
    zAxis.Normalize();

    return Base::Rotation::makeRotationByAxes(xAxis, yAxis, zAxis, "XYZ");
}

#include "moc_PlaneGizmoEditor.cpp"
