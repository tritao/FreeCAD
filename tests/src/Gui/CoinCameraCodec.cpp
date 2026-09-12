// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Gui/CoinCameraCodec.h>

TEST(CoinCameraCodecTest, emptyCameraStateIsSupported)
{
    const Gui::ViewContext::CameraState state;
    EXPECT_TRUE(state.empty());
    EXPECT_TRUE(Gui::CoinCameraCodec::supports(state));
}

TEST(CoinCameraCodecTest, capturedPayloadGetsExplicitCodecAndVersion)
{
    const auto state = Gui::CoinCameraCodec::encode("PerspectiveCamera { position 1 2 3 }");

    EXPECT_EQ(state.codec, Gui::CoinCameraCodec::Identifier);
    EXPECT_EQ(state.version, Gui::CoinCameraCodec::CurrentVersion);
    EXPECT_EQ(state.payload, "PerspectiveCamera { position 1 2 3 }");
    EXPECT_TRUE(Gui::CoinCameraCodec::supports(state));
}

TEST(CoinCameraCodecTest, unsupportedCodecAndVersionAreRejected)
{
    EXPECT_FALSE(Gui::CoinCameraCodec::supports({"OtherCamera", 1, "camera data"}));
    EXPECT_FALSE(Gui::CoinCameraCodec::supports({"CoinCamera", 2, "camera data"}));
    EXPECT_FALSE(Gui::CoinCameraCodec::supports({"CoinCamera", 1, ""}));
}
