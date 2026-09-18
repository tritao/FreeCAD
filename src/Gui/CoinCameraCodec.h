// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <FCGlobal.h>
#include <App/ViewCamera.h>

namespace Gui
{

class View3DInventor;

/** Adapts a saved camera state to FreeCAD's Coin camera nodes. */
class GuiExport CoinCameraCodec
{
public:
    /// Read the viewer's live camera into renderer-neutral state.
    static App::ViewCamera capture(const View3DInventor& view);
    /// Realize renderer-neutral state in the viewer.
    static bool apply(const App::ViewCamera& camera, View3DInventor& view);
};

}  // namespace Gui
