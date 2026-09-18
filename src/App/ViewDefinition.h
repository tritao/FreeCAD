// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "DocumentObject.h"
#include "PropertyLinks.h"
#include "PropertyStandard.h"
#include "PropertyUnits.h"
#include "ViewCamera.h"

namespace App
{

/** Persistent, renderer-neutral definition of a saved view. */
class AppExport ViewDefinition: public App::DocumentObject
{
    PROPERTY_HEADER_WITH_OVERRIDE(App::ViewDefinition);

public:
    ViewDefinition();
    ~ViewDefinition() override = default;

    /// Projection model of the saved camera.
    PropertyEnumeration CameraType;
    /// Pose of the saved camera.
    PropertyPlacement CameraPlacement;
    /// Distance from the camera position to the focal point.
    PropertyLength CameraFocalDistance;
    /// Vertical field of view of a perspective camera.
    PropertyAngle CameraHeightAngle;
    /// Vertical extent of an orthographic camera.
    PropertyLength CameraHeight;
    /// Stored aspect ratio of an orthographic camera.
    PropertyFloat CameraAspectRatio;
    PropertyLength CameraNearDistance;
    PropertyLength CameraFarDistance;
    /// Arbitrary reference frame used by contextual consumers.
    PropertyPlacement ReferenceFrame;
    /// Optional consumer-defined purpose tag, kept as a stable string on disk.
    PropertyString Purpose;
    /// Objects explicitly forced visible in this view; absence means inherit.
    PropertyLinkList ForcedVisible;
    /// Objects explicitly forced hidden in this view; absence means inherit.
    PropertyLinkList ForcedHidden;
    /// Persistent clipping definitions referenced by this view.
    PropertyLinkList ClippingPlanes;

    /// Read the persisted camera state.
    ViewCamera camera() const;
    /// Persist a camera state.
    void setCamera(const ViewCamera& camera);

    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderDocumentObject";
    }
};

}  // namespace App
