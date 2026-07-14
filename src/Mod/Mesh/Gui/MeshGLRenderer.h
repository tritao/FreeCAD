// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2026 FreeCAD developers                                *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public            *
 *   License as published by the Free Software Foundation; either           *
 *   version 2 of the License, or (at your option) any later version.       *
 *                                                                         *
 ***************************************************************************/

#pragma once

#include <Gui/MeshRenderData.h>
#include <Mod/Mesh/MeshGlobal.h>

class SoGLRenderAction;
class SoState;

namespace MeshGui
{

/**
 * Legacy OpenGL backend for the mesh render data stream.
 *
 * This class deliberately contains no Coin mesh semantics. It uploads the
 * backend-neutral data and renders it using the existing OpenGL path.
 */
class MeshGuiExport MeshGLRenderer
{
public:
    MeshGLRenderer();
    ~MeshGLRenderer();

    void generateGLArrays(SoGLRenderAction*, const Gui::MeshRenderData& data);
    void renderFacesGLArray(SoGLRenderAction* action);
    void renderCoordsGLArray(SoGLRenderAction* action);
    bool canRenderGLArray(SoGLRenderAction* action) const;
    bool matchMaterial(SoState*) const;
    void update();
    bool needUpdate(SoGLRenderAction* action) const;

    static bool shouldRenderDirectly(bool);

private:
    class Private;
    Private* p;
};

}  // namespace MeshGui
