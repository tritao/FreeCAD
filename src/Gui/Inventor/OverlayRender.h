// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 Joao Matos
// SPDX-FileNotice: Part of the FreeCAD project.

#pragma once

#include <FCGlobal.h>

namespace Gui
{

/** Pixel viewport used by Inventor overlay passes.
 *
 * Coordinates are OpenGL framebuffer coordinates with the origin at the bottom
 * left of the render target.
 */
struct OverlayViewport
{
    int x {0};
    int y {0};
    int width {0};
    int height {0};

    [[nodiscard]] bool isValid() const
    {
        return width > 0 && height > 0;
    }
};

/** Clears depth only inside an overlay viewport without touching color output. */
GuiExport void clearOverlayDepth(const OverlayViewport& viewport);

}  // namespace Gui
