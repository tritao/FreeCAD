// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Gui/ViewContext.h>

TEST(ViewContextTest, latestLayerWinsAndRemovalRestoresPreviousLayer)
{
    const auto* object = reinterpret_cast<const App::DocumentObject*>(0x1);
    Gui::ViewContext context;

    const auto lower = context.pushLayer();
    const auto upper = context.pushLayer();
    EXPECT_TRUE(context.setVisibility(lower, object, Gui::ViewContext::Visibility::Hidden));
    EXPECT_EQ(context.visibility(object), Gui::ViewContext::Visibility::Hidden);

    EXPECT_TRUE(context.setVisibility(upper, object, Gui::ViewContext::Visibility::Visible));
    EXPECT_EQ(context.visibility(object), Gui::ViewContext::Visibility::Visible);

    EXPECT_TRUE(context.removeLayer(upper));
    EXPECT_EQ(context.visibility(object), Gui::ViewContext::Visibility::Hidden);
}

TEST(ViewContextTest, inheritRemovesOnlyTheOwningLayerOverride)
{
    const auto* object = reinterpret_cast<const App::DocumentObject*>(0x1);
    Gui::ViewContext context;
    const auto layer = context.pushLayer();

    EXPECT_TRUE(context.setVisibility(layer, object, Gui::ViewContext::Visibility::Hidden));
    EXPECT_TRUE(context.setVisibility(layer, object, Gui::ViewContext::Visibility::Inherit));
    EXPECT_EQ(context.visibility(object), Gui::ViewContext::Visibility::Inherit);
    EXPECT_FALSE(context.setVisibility(layer, object, Gui::ViewContext::Visibility::Inherit));
}

TEST(ViewContextTest, rejectsUnknownLayersAndDropsRemovedObjects)
{
    const auto* object = reinterpret_cast<const App::DocumentObject*>(0x1);
    Gui::ViewContext context;
    const auto layer = context.pushLayer();

    EXPECT_FALSE(context.setVisibility(layer + 1, object, Gui::ViewContext::Visibility::Hidden));
    EXPECT_TRUE(context.setVisibility(layer, object, Gui::ViewContext::Visibility::Hidden));
    context.removeObject(object);
    EXPECT_EQ(context.visibility(object), Gui::ViewContext::Visibility::Inherit);
    EXPECT_FALSE(context.removeLayer(layer + 1));
}

TEST(ViewContextTest, clippingChangesNotifyViewerAndClearStaleDefinitions)
{
    const auto* plane = reinterpret_cast<const App::ClippingPlane*>(0x2);
    std::vector<std::vector<const App::ClippingPlane*>> events;
    Gui::ViewContext context(
        Gui::ViewContext::ChangedCallback {},
        [&](const std::vector<const App::ClippingPlane*>& planes) { events.push_back(planes); }
    );

    context.setClippingPlanes({plane});
    ASSERT_EQ(events.size(), 1U);
    ASSERT_EQ(events.back().size(), 1U);
    EXPECT_EQ(events.back().front(), plane);

    context.setClippingPlanes({plane});
    EXPECT_EQ(events.size(), 1U);

    context.removeObject(reinterpret_cast<const App::DocumentObject*>(plane));
    ASSERT_EQ(events.size(), 2U);
    EXPECT_TRUE(events.back().empty());
}
