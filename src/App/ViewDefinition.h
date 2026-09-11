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

    /// Renderer codec identifier for the camera payload (for example, "CoinCamera/1").
    PropertyString CameraCodec;
    /// Version of the camera payload schema.
    PropertyInteger CameraVersion;
    /// Versioned camera payload interpreted by a Gui adapter.
    PropertyString CameraPayload;
    /// Arbitrary reference frame used by contextual consumers.
    PropertyPlacement ReferenceFrame;
    /// Optional consumer-defined purpose tag, kept as a stable string on disk.
    PropertyString Purpose;
    /// Objects explicitly forced visible in this view; absence means inherit.
    PropertyLinkList ForcedVisible;
    /// Objects explicitly forced hidden in this view; absence means inherit.
    PropertyLinkList ForcedHidden;
    /// Optional persistent clipping definitions referenced by this view.
    PropertyLinkList ClippingPlanes;

    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderDocumentObject";
    }
};

}  // namespace App
