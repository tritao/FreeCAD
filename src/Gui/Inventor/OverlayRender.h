// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 Joao Matos
// SPDX-FileNotice: Part of the FreeCAD project.

#pragma once

#include <cstdint>

#include <Inventor/SbViewportRegion.h>
#include <Inventor/actions/SoGLRenderAction.h>

#include <FCGlobal.h>

class SoNode;

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

/** Render-action settings shared by Inventor overlay passes. */
struct OverlayRenderPolicy
{
    SbViewportRegion viewportRegion;
    SoGLRenderAction::TransparencyType transparencyType {SoGLRenderAction::BLEND};
    uint32_t cacheContext {0};
    bool hasCacheContext {false};
};

/** Applies an overlay scene graph with the requested render-action policy. */
GuiExport void renderOverlay(SoNode* root, const OverlayRenderPolicy& policy);

/** Clears depth only inside an overlay viewport without touching color output. */
GuiExport void clearOverlayDepth(const OverlayViewport& viewport);

}  // namespace Gui
