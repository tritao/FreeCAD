// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ViewDefinition.h"

using namespace App;

PROPERTY_SOURCE(App::ViewDefinition, App::DocumentObject)

namespace
{

const char* CameraTypeEnums[] = {"Orthographic", "Perspective", nullptr};

}  // namespace

ViewDefinition::ViewDefinition()
{
    CameraType.setEnums(CameraTypeEnums);
    ADD_PROPERTY_TYPE(
        CameraType,
        ("Orthographic"),
        "Camera",
        Prop_None,
        "Projection model of the saved camera"
    );
    ADD_PROPERTY_TYPE(
        CameraPlacement,
        (Base::Placement()),
        "Camera",
        Prop_None,
        "Pose of the saved camera"
    );
    ADD_PROPERTY_TYPE(
        CameraFocalDistance,
        (0.0),
        "Camera",
        Prop_None,
        "Distance from the camera position to the focal point"
    );
    ADD_PROPERTY_TYPE(
        CameraHeightAngle,
        (0.0),
        "Camera",
        Prop_None,
        "Vertical field of view of a perspective camera"
    );
    ADD_PROPERTY_TYPE(
        CameraHeight,
        (0.0),
        "Camera",
        Prop_None,
        "Vertical extent of an orthographic camera"
    );
    ADD_PROPERTY_TYPE(
        CameraAspectRatio,
        (1.0),
        "Camera",
        Prop_None,
        "Stored aspect ratio of an orthographic camera"
    );
    ADD_PROPERTY_TYPE(
        CameraNearDistance,
        (0.0),
        "Camera",
        Prop_None,
        "Near clipping distance of the saved camera"
    );
    ADD_PROPERTY_TYPE(
        CameraFarDistance,
        (0.0),
        "Camera",
        Prop_None,
        "Far clipping distance of the saved camera"
    );
    ADD_PROPERTY_TYPE(
        ReferenceFrame,
        (Base::Placement()),
        "View",
        Prop_None,
        "Reference frame for contextual representations"
    );
    ADD_PROPERTY_TYPE(Purpose, (""), "View", Prop_None, "Purpose of this saved view");
    ADD_PROPERTY_TYPE(
        ForcedVisible,
        (),
        "View",
        Prop_None,
        "Objects forced visible by this view"
    );
    ADD_PROPERTY_TYPE(
        ForcedHidden,
        (),
        "View",
        Prop_None,
        "Objects forced hidden by this view"
    );
    ADD_PROPERTY_TYPE(
        ClippingPlanes,
        (),
        "View",
        Prop_None,
        "Persistent clipping definitions referenced by this view"
    );
}

ViewCamera ViewDefinition::camera() const
{
    ViewCamera state;
    state.type = std::string(CameraType.getValueAsString()) == "Perspective"
        ? ViewCameraType::Perspective
        : ViewCameraType::Orthographic;
    const Base::Placement& placement = CameraPlacement.getValue();
    state.position = placement.getPosition();
    state.orientation = placement.getRotation();
    state.focalDistance = CameraFocalDistance.getValue();
    state.heightAngle = CameraHeightAngle.getValue();
    state.height = CameraHeight.getValue();
    state.aspectRatio = CameraAspectRatio.getValue();
    state.nearDistance = CameraNearDistance.getValue();
    state.farDistance = CameraFarDistance.getValue();
    return state;
}

void ViewDefinition::setCamera(const ViewCamera& state)
{
    CameraType.setValue(state.type == ViewCameraType::Perspective ? "Perspective" : "Orthographic");
    CameraPlacement.setValue(Base::Placement(state.position, state.orientation));
    CameraFocalDistance.setValue(state.focalDistance);
    CameraHeightAngle.setValue(state.heightAngle);
    CameraHeight.setValue(state.height);
    CameraAspectRatio.setValue(state.aspectRatio);
    CameraNearDistance.setValue(state.nearDistance);
    CameraFarDistance.setValue(state.farDistance);
}
