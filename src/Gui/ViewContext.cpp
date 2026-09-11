// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ViewContext.h"

#include <algorithm>
#include <set>

#include <App/DocumentObject.h>
#include <App/Document.h>
#include <App/ClippingPlane.h>
#include <App/ViewDefinition.h>

#include "Application.h"
#include "ViewProviderDocumentObject.h"

using namespace Gui;

ViewContext::ViewContext(ChangedCallback changed, ClippingChangedCallback clippingChanged)
    : changed(std::move(changed))
    , clippingChanged(std::move(clippingChanged))
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
    activeCameraState = definition->CameraState.getValue();
    activeReferenceFrame = definition->ReferenceFrame.getValue();
    const auto layer = pushLayer();
    for (const auto& [name, state] : definition->VisibilityOverrides.getValue()) {
        auto* object = definition->getDocument()->getObject(name.c_str());
        if (!object) {
            continue;
        }
        Visibility visibility;
        if (state == "Visible") {
            visibility = Visibility::Visible;
        }
        else if (state == "Hidden") {
            visibility = Visibility::Hidden;
        }
        else {
            continue;
        }
        setVisibility(layer, object, visibility);
    }
    std::vector<const App::ClippingPlane*> planes;
    for (auto* object : definition->ClippingPlanes.getValues()) {
        if (auto* plane = dynamic_cast<const App::ClippingPlane*>(object)) {
            planes.push_back(plane);
        }
    }
    setClippingPlanes(planes);
    return true;
}

bool ViewContext::captureDefinition(App::ViewDefinition* definition) const
{
    if (!definition) {
        return false;
    }
    std::map<std::string, std::string> overrides;
    for (const auto& [id, values] : layers) {
        (void)id;
        for (const auto& [object, visibility] : values) {
            if (!object) {
                continue;
            }
            const char* state = nullptr;
            switch (visibility) {
                case Visibility::Visible:
                    state = "Visible";
                    break;
                case Visibility::Hidden:
                    state = "Hidden";
                    break;
                case Visibility::Inherit:
                    break;
            }
            if (state) {
                overrides[object->getNameInDocument()] = state;
            }
        }
    }
    definition->VisibilityOverrides.setValue(std::move(overrides));
    definition->CameraState.setValue(activeCameraState);
    definition->ReferenceFrame.setValue(activeReferenceFrame);
    std::vector<App::DocumentObject*> planes;
    planes.reserve(activeClippingPlanes.size());
    for (const auto* plane : activeClippingPlanes) {
        planes.push_back(const_cast<App::ClippingPlane*>(plane));
    }
    definition->ClippingPlanes.setValues(planes);
    return true;
}

void ViewContext::setCameraState(std::string state)
{
    activeCameraState = std::move(state);
}

const std::string& ViewContext::cameraState() const
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

void ViewContext::setClippingPlanes(const std::vector<const App::ClippingPlane*>& planes)
{
    if (activeClippingPlanes == planes) {
        return;
    }
    activeClippingPlanes = planes;
    if (clippingChanged) {
        clippingChanged(activeClippingPlanes);
    }
}

const std::vector<const App::ClippingPlane*>& ViewContext::clippingPlanes() const
{
    return activeClippingPlanes;
}

void ViewContext::setClippingChangedCallback(ClippingChangedCallback callback)
{
    clippingChanged = std::move(callback);
    if (clippingChanged) {
        clippingChanged(activeClippingPlanes);
    }
}

void ViewContext::removeObject(const App::DocumentObject* object)
{
    for (auto& [id, values] : layers) {
        (void)id;
        values.erase(object);
    }
    const auto oldSize = activeClippingPlanes.size();
    activeClippingPlanes.erase(
        std::remove(activeClippingPlanes.begin(), activeClippingPlanes.end(), object),
        activeClippingPlanes.end()
    );
    if (oldSize != activeClippingPlanes.size() && clippingChanged) {
        clippingChanged(activeClippingPlanes);
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
    const bool hadClippingPlanes = !activeClippingPlanes.empty();
    activeClippingPlanes.clear();
    for (const auto* object : affected) {
        notify(object);
    }
    if (hadClippingPlanes && clippingChanged) {
        clippingChanged(activeClippingPlanes);
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
