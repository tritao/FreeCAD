// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "DocumentObject.h"
#include "PropertyLinks.h"
#include "PropertyStandard.h"

namespace App
{

/** Persistent, renderer-neutral definition of a saved view. */
class AppExport ViewDefinition: public App::DocumentObject
{
    PROPERTY_HEADER_WITH_OVERRIDE(App::ViewDefinition);

public:
    ViewDefinition();
    ~ViewDefinition() override = default;

    /// Serialized camera state owned by the active viewer adapter.
    PropertyString CameraState;
    /// Arbitrary reference frame used by contextual consumers.
    PropertyPlacement ReferenceFrame;
    /// Architectural or generic purpose, kept as a stable string on disk.
    PropertyEnumeration Purpose;
    /// Object-name to Inherit/Visible/Hidden overrides.
    PropertyMap VisibilityOverrides;
    /// Optional persistent clipping definitions referenced by this view.
    PropertyLinkList ClippingPlanes;

    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderDocumentObject";
    }
};

}  // namespace App
