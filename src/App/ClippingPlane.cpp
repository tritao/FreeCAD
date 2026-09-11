// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ClippingPlane.h"

using namespace App;

PROPERTY_SOURCE(App::ClippingPlane, App::DocumentObject)

ClippingPlane::ClippingPlane()
{
    ADD_PROPERTY_TYPE(Normal, (Base::Vector3d(0.0, 0.0, 1.0)), "Clipping", Prop_None, "Plane normal");
    ADD_PROPERTY_TYPE(Offset, (0.0), "Clipping", Prop_None, "Signed distance from the origin");
    ADD_PROPERTY_TYPE(Enabled, (true), "Clipping", Prop_None, "Whether this plane is active");
}

