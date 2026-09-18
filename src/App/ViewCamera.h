// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <Base/Rotation.h>
#include <Base/Vector3D.h>
#include <FCGlobal.h>

namespace App
{

/** Projection model of a saved camera. */
enum class ViewCameraType
{
    Orthographic,
    Perspective
};

/** Renderer-neutral state of a saved camera.
 *
 * The values describe a physical camera: a pose, a projection model and the
 * matching projection parameters.  Renderer adapters translate this state to
 * and from their own camera representation.
 */
struct AppExport ViewCamera
{
    ViewCameraType type {ViewCameraType::Orthographic};
    Base::Vector3d position {0.0, 0.0, 0.0};
    Base::Rotation orientation {};

    /// Distance from the camera position to the focal point.
    double focalDistance {0.0};
    /// Vertical field of view of a perspective camera, in radians.
    double heightAngle {0.0};
    /// Vertical extent of an orthographic camera.
    double height {0.0};
    /// Stored aspect ratio of an orthographic camera.
    double aspectRatio {0.0};
    double nearDistance {0.0};
    double farDistance {0.0};

    /** True when no camera has been captured yet.
     *
     * A captured camera always carries a projection size, so an all-zero
     * projection marks a saved view that was created without a capture.
     */
    bool empty() const
    {
        return focalDistance == 0.0 && height == 0.0 && heightAngle == 0.0;
    }

    bool operator==(const ViewCamera& other) const
    {
        return type == other.type
            && position == other.position
            && orientation == other.orientation
            && focalDistance == other.focalDistance
            && heightAngle == other.heightAngle
            && height == other.height
            && aspectRatio == other.aspectRatio
            && nearDistance == other.nearDistance
            && farDistance == other.farDistance;
    }

    bool operator!=(const ViewCamera& other) const
    {
        return !(*this == other);
    }
};

}  // namespace App
