// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "CoinCameraCodec.h"

#include <Inventor/SbRotation.h>
#include <Inventor/SbVec3f.h>
#include <Inventor/nodes/SoCamera.h>
#include <Inventor/nodes/SoOrthographicCamera.h>
#include <Inventor/nodes/SoPerspectiveCamera.h>

#include "View3DInventor.h"
#include "View3DInventorViewer.h"

using namespace Gui;

namespace
{

Base::Vector3d toVector(const SbVec3f& vector)
{
    return Base::Vector3d(vector[0], vector[1], vector[2]);
}

SbVec3f toCoin(const Base::Vector3d& vector)
{
    return SbVec3f(
        static_cast<float>(vector.x),
        static_cast<float>(vector.y),
        static_cast<float>(vector.z)
    );
}

Base::Rotation toRotation(const SbRotation& rotation)
{
    float q0 {};
    float q1 {};
    float q2 {};
    float q3 {};
    rotation.getValue(q0, q1, q2, q3);
    return Base::Rotation(q0, q1, q2, q3);
}

SbRotation toCoin(const Base::Rotation& rotation)
{
    double q0 {};
    double q1 {};
    double q2 {};
    double q3 {};
    rotation.getValue(q0, q1, q2, q3);
    return SbRotation(
        static_cast<float>(q0),
        static_cast<float>(q1),
        static_cast<float>(q2),
        static_cast<float>(q3)
    );
}

/** Apply a viewer-owned temporary camera and release it afterwards. */
template<typename Node>
bool applyTemporaryCamera(Node* node, View3DInventor& view)
{
    node->ref();
    struct Unref
    {
        Node* node;
        ~Unref()
        {
            node->unref();
        }
    } guard {node};
    return view.getViewer()->applyCameraState(*node);
}

}  // namespace

App::ViewCamera CoinCameraCodec::capture(const View3DInventor& view)
{
    const SoCamera* camera = view.getViewer()->getSoRenderManager()->getCamera();
    if (!camera) {
        return {};
    }

    App::ViewCamera state;
    if (camera->getTypeId() == SoPerspectiveCamera::getClassTypeId()) {
        state.type = App::ViewCameraType::Perspective;
        state.heightAngle = static_cast<const SoPerspectiveCamera*>(camera)->heightAngle.getValue();
    }
    else if (camera->getTypeId() == SoOrthographicCamera::getClassTypeId()) {
        state.type = App::ViewCameraType::Orthographic;
        const auto* orthographic = static_cast<const SoOrthographicCamera*>(camera);
        state.height = orthographic->height.getValue();
        state.aspectRatio = orthographic->aspectRatio.getValue();
    }
    else {
        return {};
    }

    state.position = toVector(camera->position.getValue());
    state.orientation = toRotation(camera->orientation.getValue());
    state.focalDistance = camera->focalDistance.getValue();
    state.nearDistance = camera->nearDistance.getValue();
    state.farDistance = camera->farDistance.getValue();
    return state;
}

bool CoinCameraCodec::apply(const App::ViewCamera& camera, View3DInventor& view)
{
    if (camera.empty()) {
        return true;
    }

    const SbVec3f position = toCoin(camera.position);
    const SbRotation orientation = toCoin(camera.orientation);
    if (camera.type == App::ViewCameraType::Perspective) {
        auto* node = new SoPerspectiveCamera;
        node->position = position;
        node->orientation = orientation;
        node->focalDistance = static_cast<float>(camera.focalDistance);
        node->heightAngle = static_cast<float>(camera.heightAngle);
        node->nearDistance = static_cast<float>(camera.nearDistance);
        node->farDistance = static_cast<float>(camera.farDistance);
        return applyTemporaryCamera(node, view);
    }

    auto* node = new SoOrthographicCamera;
    node->position = position;
    node->orientation = orientation;
    node->focalDistance = static_cast<float>(camera.focalDistance);
    node->height = static_cast<float>(camera.height);
    node->aspectRatio = static_cast<float>(camera.aspectRatio);
    node->nearDistance = static_cast<float>(camera.nearDistance);
    node->farDistance = static_cast<float>(camera.farDistance);
    return applyTemporaryCamera(node, view);
}
