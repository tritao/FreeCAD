// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <App/ViewCamera.h>

TEST(ViewCameraTest, defaultStateHasNotBeenCaptured)
{
    const App::ViewCamera camera;
    EXPECT_TRUE(camera.empty());
    EXPECT_EQ(camera.type, App::ViewCameraType::Orthographic);
}

TEST(ViewCameraTest, projectionSizeMarksStateAsCaptured)
{
    App::ViewCamera camera;
    camera.focalDistance = 250.0;
    EXPECT_FALSE(camera.empty());

    camera = App::ViewCamera {};
    camera.height = 1000.0;
    EXPECT_FALSE(camera.empty());

    camera = App::ViewCamera {};
    camera.heightAngle = 0.75;
    EXPECT_FALSE(camera.empty());
}

TEST(ViewCameraTest, equalityComparesPoseAndProjection)
{
    App::ViewCamera camera;
    camera.type = App::ViewCameraType::Perspective;
    camera.position = Base::Vector3d(1.0, 2.0, 3.0);
    camera.orientation = Base::Rotation(Base::Vector3d(0.0, 0.0, 1.0), 1.5);
    camera.heightAngle = 0.75;

    const App::ViewCamera same = camera;
    EXPECT_EQ(same, camera);

    App::ViewCamera other = camera;
    other.heightAngle = 0.5;
    EXPECT_NE(other, camera);
}
