// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <string>
#include <string_view>

#include <FCGlobal.h>

#include "ViewContext.h"

namespace Gui
{

class View3DInventor;

/** Adapts a versioned saved camera state to FreeCAD's Coin camera payload. */
class GuiExport CoinCameraCodec
{
public:
    static constexpr std::string_view Identifier = "CoinCamera";
    static constexpr long CurrentVersion = 1;

    static ViewContext::CameraState capture(const View3DInventor& view);
    static ViewContext::CameraState encode(std::string payload);
    static bool supports(const ViewContext::CameraState& state) noexcept;
    static bool apply(const ViewContext::CameraState& state, View3DInventor& view);
};

}  // namespace Gui
