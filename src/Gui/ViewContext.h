// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <cstdint>
#include <functional>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

#include <FCGlobal.h>
#include <Base/Placement.h>

namespace App
{
class DocumentObject;
class ViewDefinition;
class ClippingPlane;
}

namespace Gui
{

class ViewProviderDocumentObject;

class GuiExport ViewContext
{
public:
    struct CameraState
    {
        std::string codec;
        long version = 1;
        std::string payload;

        bool empty() const noexcept
        {
            return codec.empty() && payload.empty();
        }
    };

    enum class Visibility
    {
        Inherit,
        Visible,
        Hidden
    };

    using LayerId = std::uint64_t;
    using ChangedCallback = std::function<void(const ViewProviderDocumentObject*)>;
    using ClippingChangedCallback = std::function<void(const std::vector<const App::ClippingPlane*>&)>;

    explicit ViewContext(ChangedCallback changed = {}, ClippingChangedCallback clippingChanged = {});

    LayerId pushLayer();
    bool removeLayer(LayerId layer);
    bool setVisibility(LayerId layer, const App::DocumentObject* object, Visibility visibility);
    Visibility visibility(const App::DocumentObject* object) const;
    bool effectiveVisibility(const ViewProviderDocumentObject* provider) const;
    bool applyDefinition(const App::ViewDefinition* definition);
    bool captureDefinition(App::ViewDefinition* definition) const;
    void setCameraState(CameraState state);
    const CameraState& cameraState() const;
    void setReferenceFrame(const Base::Placement& frame);
    const Base::Placement& referenceFrame() const;
    void setClippingPlanes(const std::vector<const App::ClippingPlane*>& planes);
    const std::vector<const App::ClippingPlane*>& clippingPlanes() const;
    void removeObject(const App::DocumentObject* object);
    void clear();

private:
    using VisibilityMap = std::unordered_map<const App::DocumentObject*, Visibility>;

    void notify(const App::DocumentObject* object) const;

    std::map<LayerId, VisibilityMap> layers;
    LayerId nextLayerId = 1;
    ChangedCallback changed;
    ClippingChangedCallback clippingChanged;
    std::vector<const App::ClippingPlane*> activeClippingPlanes;
    CameraState activeCameraState;
    Base::Placement activeReferenceFrame;
};

}  // namespace Gui
