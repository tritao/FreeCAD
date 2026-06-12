// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 Joao Matos
// SPDX-FileNotice: Part of the FreeCAD project.

#include <FCConfig.h>

#ifdef FC_OS_WIN32
# include <windows.h>
#endif

#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/system/gl.h>

#include "OverlayRender.h"

namespace
{

/** Restores the OpenGL state touched while clearing overlay depth. */
class ScopedDepthClearState
{
public:
    ScopedDepthClearState()
    {
        glGetBooleanv(GL_SCISSOR_TEST, &scissorEnabled);
        glGetIntegerv(GL_SCISSOR_BOX, scissorBox);
        glGetBooleanv(GL_DEPTH_WRITEMASK, &depthMask);
        glGetDoublev(GL_DEPTH_CLEAR_VALUE, &clearDepth);
    }

    ScopedDepthClearState(const ScopedDepthClearState&) = delete;
    ScopedDepthClearState& operator=(const ScopedDepthClearState&) = delete;

    ~ScopedDepthClearState()
    {
        if (scissorEnabled) {
            glEnable(GL_SCISSOR_TEST);
        }
        else {
            glDisable(GL_SCISSOR_TEST);
        }
        glScissor(scissorBox[0], scissorBox[1], scissorBox[2], scissorBox[3]);
        glDepthMask(depthMask);
        glClearDepth(clearDepth);
    }

private:
    GLboolean scissorEnabled {GL_FALSE};
    GLint scissorBox[4] {0, 0, 0, 0};
    GLboolean depthMask {GL_FALSE};
    GLdouble clearDepth {1.0};
};

}  // namespace

void Gui::renderOverlay(SoNode* root, const OverlayRenderPolicy& policy)
{
    if (!root) {
        return;
    }

    SoGLRenderAction action(policy.viewportRegion);
    if (policy.hasCacheContext) {
        action.setCacheContext(policy.cacheContext);
    }
    action.setTransparencyType(policy.transparencyType);
    action.apply(root);
}

void Gui::clearOverlayDepth(const OverlayViewport& viewport)
{
    if (!viewport.isValid()) {
        return;
    }

    const ScopedDepthClearState state;
    glEnable(GL_SCISSOR_TEST);
    glScissor(viewport.x, viewport.y, viewport.width, viewport.height);
    glDepthMask(GL_TRUE);
    glClearDepth(1.0);
    glClear(GL_DEPTH_BUFFER_BIT);
}
