// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include "DocumentObject.h"
#include "PropertyStandard.h"
#include "PropertyUnits.h"

namespace App
{

/** Persistent, renderer-neutral clipping plane definition. */
class AppExport ClippingPlane: public App::DocumentObject
{
    PROPERTY_HEADER_WITH_OVERRIDE(App::ClippingPlane);

public:
    ClippingPlane();
    ~ClippingPlane() override = default;

    PropertyVector Normal;
    PropertyLength Offset;
    PropertyBool Enabled;

    const char* getViewProviderName() const override
    {
        return "Gui::ViewProviderDocumentObject";
    }
};

}  // namespace App
