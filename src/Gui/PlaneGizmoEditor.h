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

#include <QObject>
#include <FCGlobal.h>

#include <Base/Placement.h>

class QTimer;

namespace App
{
class ClippingPlane;
}

namespace Gui
{

class GizmoContainer;
class LinearGizmo;
class QuantitySpinBox;
class RotationGizmo;
class View3DInventor;
class View3DInventorViewer;
class ViewProviderClippingPlane;

class GuiExport PlaneGizmoEditor: public QObject
{
    Q_OBJECT

public:
    struct State
    {
        double offset {0.0};
        double tiltXDegrees {0.0};
        double tiltYDegrees {0.0};
    };

    enum class Preset
    {
        XY = 0,
        XZ,
        YZ,
        View,
    };

    explicit PlaneGizmoEditor(ViewProviderClippingPlane* viewProvider, QObject* parent = nullptr);
    ~PlaneGizmoEditor() override;

    ViewProviderClippingPlane* getViewProvider() const;
    App::ClippingPlane* getPlane() const;

    bool isActive() const;
    Base::Placement currentPlacement() const;
    State currentState() const;

    bool start(View3DInventorViewer* viewer);
    void finish(bool commitPreview);

    void setState(const State& state, bool commitPlacement);
    void setPreset(Preset preset, View3DInventor* view, bool commitPlacement);

    static State stateFromPlacement(const Base::Placement& placement);
    static Base::Placement placementFromState(const State& state);
    static Base::Vector3d presetNormal(Preset preset, View3DInventor* view);

Q_SIGNALS:
    void stateChanged();
    void editingChanged(bool active);
    void committed();

private Q_SLOTS:
    void onDeltaChanged();
    void rebaseGizmo();

private:
    void applyPreviewPlacement(const Base::Placement& placement);
    void clearPreview();
    void resetDeltaControls();
    void syncGizmo();

    static Base::Placement parentPlacement(const App::ClippingPlane& plane);
    static Base::Placement localPlacementFromGlobal(
        const App::ClippingPlane& plane,
        const Base::Placement& globalPlacement
    );
    static Base::Vector3d sectionNormalFromPlacement(const Base::Placement& placement);
    static Base::Vector3d normalizedSectionNormal(const Base::Placement& placement);
    static double sectionOffsetFromPlacement(const Base::Placement& placement);
    static Base::Rotation rotationForTiltAngles(double tiltXDegrees, double tiltYDegrees);

    ViewProviderClippingPlane* viewProvider {nullptr};
    std::unique_ptr<GizmoContainer> gizmoContainer;
    LinearGizmo* offsetGizmo {nullptr};
    RotationGizmo* tiltXGizmo {nullptr};
    RotationGizmo* tiltYGizmo {nullptr};
    QuantitySpinBox* offsetDeltaSpin {nullptr};
    QuantitySpinBox* tiltXDeltaSpin {nullptr};
    QuantitySpinBox* tiltYDeltaSpin {nullptr};
    QTimer* rebaseTimer {nullptr};
    View3DInventorViewer* viewer {nullptr};
    Base::Placement previewPlacement {};
    double baseOffset {0.0};
    double baseTiltXDegrees {0.0};
    double baseTiltYDegrees {0.0};
    bool previewDirty {false};
    bool suppressDeltaUpdates {false};
};

}  // namespace Gui
