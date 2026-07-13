// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Gui/MeshRenderData.h>

namespace
{

TEST(MeshInteractionLodPolicyTest, SelectsReducedPresentationOnlyAboveLimit)
{
    const Gui::MeshInteractionLodPolicy policy(100);

    const Gui::MeshRenderPresentation full = policy.presentation(false, 101, 404, 4);
    EXPECT_FALSE(full.reducedGeometry);
    EXPECT_EQ(full.pointStride, 1U);

    const Gui::MeshRenderPresentation atLimit = policy.presentation(true, 100, 400, 4);
    EXPECT_FALSE(atLimit.reducedGeometry);
    EXPECT_EQ(atLimit.pointStride, 1U);

    const Gui::MeshRenderPresentation reduced = policy.presentation(true, 101, 404, 4);
    EXPECT_TRUE(reduced.reducedGeometry);
    EXPECT_EQ(reduced.pointStride, 2U);
}

TEST(MeshInteractionLodPolicyTest, HandlesZeroLimitWithoutDivisionByZero)
{
    const Gui::MeshInteractionLodPolicy policy(0);
    const Gui::MeshRenderPresentation presentation = policy.presentation(true, 1, 4, 4);

    EXPECT_TRUE(presentation.reducedGeometry);
    EXPECT_EQ(presentation.pointStride, 1U);
}

TEST(MeshRenderDataTest, ColoredVerticesKeepAttributeStreamsAligned)
{
    Gui::MeshRenderData data;
    data.reserveVertices(2, true);

    const float firstPosition[3] {0.0F, 0.0F, 0.0F};
    const float secondPosition[3] {1.0F, 0.0F, 0.0F};
    const float normal[3] {0.0F, 0.0F, 1.0F};
    const float firstColor[4] {1.0F, 0.0F, 0.0F, 0.5F};
    const float secondColor[4] {0.0F, 1.0F, 0.0F, 0.25F};

    data.appendColoredVertex(firstPosition, normal, firstColor);
    data.appendColoredVertex(secondPosition, normal, secondColor);

    EXPECT_EQ(data.vertexCount(), 2U);
    EXPECT_EQ(data.positions.size(), 6U);
    EXPECT_EQ(data.normals.size(), 6U);
    EXPECT_EQ(data.colors.size(), 8U);
    EXPECT_TRUE(data.hasVertexColors());
}

}  // namespace
