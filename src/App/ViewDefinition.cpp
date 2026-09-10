// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ViewDefinition.h"

using namespace App;

PROPERTY_SOURCE(App::ViewDefinition, App::DocumentObject)

ViewDefinition::ViewDefinition()
{
    ADD_PROPERTY_TYPE(
        CameraState,
        (""),
        "View",
        Prop_None,
        "Renderer-neutral serialized camera state"
    );
    ADD_PROPERTY_TYPE(
        ReferenceFrame,
        (Base::Placement()),
        "View",
        Prop_None,
        "Reference frame for contextual representations"
    );
    ADD_PROPERTY_TYPE(Purpose, ("Model"), "View", Prop_None, "Purpose of this saved view");
    ADD_PROPERTY_TYPE(
        VisibilityOverrides,
        (),
        "View",
        Prop_None,
        "Persistent object visibility overrides"
    );
    ADD_PROPERTY_TYPE(
        ClippingPlanes,
        (),
        "View",
        Prop_None,
        "Persistent clipping definitions referenced by this view"
    );

    Purpose.setEnums({"Model", "Plan", "Section", "Elevation"});
    Purpose.setValue("Model");
}
