// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "CoinCameraCodec.h"

#include <utility>

#include "View3DInventor.h"

using namespace Gui;

ViewContext::CameraState CoinCameraCodec::capture(const View3DInventor& view)
{
    return encode(view.getCamera());
}

ViewContext::CameraState CoinCameraCodec::encode(std::string payload)
{
    if (payload.empty()) {
        return {};
    }
    return {std::string(Identifier), CurrentVersion, std::move(payload)};
}

bool CoinCameraCodec::supports(const ViewContext::CameraState& state) noexcept
{
    return state.empty()
        || (state.codec == Identifier && state.version == CurrentVersion && !state.payload.empty());
}

bool CoinCameraCodec::apply(const ViewContext::CameraState& state, View3DInventor& view)
{
    if (!supports(state)) {
        return false;
    }
    return state.empty() || view.setCamera(state.payload.c_str());
}
