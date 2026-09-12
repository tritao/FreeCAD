// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ViewDefinition.h"

using namespace App;

PROPERTY_SOURCE(App::ViewDefinition, App::DocumentObject)

ViewDefinition::ViewDefinition()
{
    ADD_PROPERTY_TYPE(
        CameraCodec,
        (""),
        "View",
        Prop_None,
        "Renderer camera codec identifier"
    );
    ADD_PROPERTY_TYPE(
        CameraVersion,
        (1),
        "View",
        Prop_None,
        "Version of the camera payload schema"
    );
    ADD_PROPERTY_TYPE(
        CameraPayload,
        (""),
        "View",
        Prop_None,
        "Versioned renderer camera payload"
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
}
