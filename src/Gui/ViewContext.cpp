// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ViewContext.h"

#include <set>
#include <utility>
#include <vector>

#include <App/DocumentObject.h>
#include <App/Document.h>
#include <App/ViewDefinition.h>

#include "Application.h"
#include "ViewProviderDocumentObject.h"

using namespace Gui;

ViewContext::ViewContext(ChangedCallback changed)
    : changed(std::move(changed))
{}

ViewContext::LayerId ViewContext::pushLayer()
{
    const auto id = nextLayerId++;
    layers.emplace(id, VisibilityMap {});
    return id;
}

bool ViewContext::removeLayer(LayerId layer)
{
    const auto pos = layers.find(layer);
    if (pos == layers.end()) {
        return false;
    }

    std::set<const App::DocumentObject*> affected;
    for (const auto& [object, visibility] : pos->second) {
        (void)visibility;
        affected.insert(object);
    }
    layers.erase(pos);
    for (const auto* object : affected) {
        notify(object);
    }
    return true;
}

bool ViewContext::setVisibility(LayerId layer, const App::DocumentObject* object, Visibility value)
{
    const auto pos = layers.find(layer);
    if (pos == layers.end() || !object) {
        return false;
    }

    if (value == Visibility::Inherit) {
        if (pos->second.erase(object) == 0) {
            return false;
        }
    }
    else {
        const auto current = pos->second.find(object);
        if (current != pos->second.end() && current->second == value) {
            return false;
        }
        pos->second[object] = value;
    }
    notify(object);
    return true;
}

ViewContext::Visibility ViewContext::visibility(const App::DocumentObject* object) const
{
    for (auto layer = layers.rbegin(); layer != layers.rend(); ++layer) {
        const auto pos = layer->second.find(object);
        if (pos != layer->second.end()) {
            return pos->second;
        }
    }
    return Visibility::Inherit;
}

bool ViewContext::effectiveVisibility(const ViewProviderDocumentObject* provider) const
{
    if (!provider) {
        return false;
    }
    switch (visibility(provider->getObject())) {
        case Visibility::Visible:
            return true;
        case Visibility::Hidden:
            return false;
        case Visibility::Inherit:
            return provider->Visibility.getValue();
    }
    return provider->Visibility.getValue();
}

bool ViewContext::applyDefinition(const App::ViewDefinition* definition)
{
    if (!definition || !definition->getDocument()) {
        return false;
    }
    clear();
    activeCameraState = {
        definition->CameraCodec.getValue(),
        definition->CameraVersion.getValue(),
        definition->CameraPayload.getValue()
    };
    activeReferenceFrame = definition->ReferenceFrame.getValue();
    const auto layer = pushLayer();
    for (auto* object : definition->ForcedVisible.getValues()) {
        setVisibility(layer, object, Visibility::Visible);
    }
    for (auto* object : definition->ForcedHidden.getValues()) {
        setVisibility(layer, object, Visibility::Hidden);
    }
    return true;
}

bool ViewContext::captureDefinition(App::ViewDefinition* definition) const
{
    if (!definition) {
        return false;
    }
    std::vector<App::DocumentObject*> forcedVisible;
    std::vector<App::DocumentObject*> forcedHidden;
    std::set<const App::DocumentObject*> captured;

    // Persist only the effective state.  Walking layers from newest to oldest
    // ensures that a later override is not accidentally overwritten by an
    // older one when the two link lists are restored.
    for (auto layer = layers.rbegin(); layer != layers.rend(); ++layer) {
        for (const auto& [object, visibility] : layer->second) {
            if (!object || !captured.insert(object).second) {
                continue;
            }
            switch (visibility) {
                case Visibility::Visible:
                    forcedVisible.push_back(const_cast<App::DocumentObject*>(object));
                    break;
                case Visibility::Hidden:
                    forcedHidden.push_back(const_cast<App::DocumentObject*>(object));
                    break;
                case Visibility::Inherit:
                    break;
            }
        }
    }
    definition->ForcedVisible.setValues(std::move(forcedVisible));
    definition->ForcedHidden.setValues(std::move(forcedHidden));
    definition->CameraPayload.setValue(activeCameraState.payload);
    definition->CameraCodec.setValue(activeCameraState.codec);
    definition->CameraVersion.setValue(activeCameraState.version);
    definition->ReferenceFrame.setValue(activeReferenceFrame);
    return true;
}

void ViewContext::setCameraState(CameraState state)
{
    activeCameraState = std::move(state);
}

const ViewContext::CameraState& ViewContext::cameraState() const
{
    return activeCameraState;
}

void ViewContext::setReferenceFrame(const Base::Placement& frame)
{
    activeReferenceFrame = frame;
}

const Base::Placement& ViewContext::referenceFrame() const
{
    return activeReferenceFrame;
}

void ViewContext::removeObject(const App::DocumentObject* object)
{
    for (auto& [id, values] : layers) {
        (void)id;
        values.erase(object);
    }
}

void ViewContext::clear()
{
    std::set<const App::DocumentObject*> affected;
    for (const auto& [id, values] : layers) {
        (void)id;
        for (const auto& [object, visibility] : values) {
            (void)visibility;
            affected.insert(object);
        }
    }
    layers.clear();
    for (const auto* object : affected) {
        notify(object);
    }
}

void ViewContext::notify(const App::DocumentObject* object) const
{
    if (!changed || !object || !Application::Instance) {
        return;
    }
    auto* provider = dynamic_cast<ViewProviderDocumentObject*>(
        Application::Instance->getViewProvider(const_cast<App::DocumentObject*>(object))
    );
    if (provider) {
        changed(provider);
    }
}
