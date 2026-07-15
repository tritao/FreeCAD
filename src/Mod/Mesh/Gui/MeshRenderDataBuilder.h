// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <Gui/MeshRenderData.h>
#include <Mod/Mesh/App/Mesh.h>
#include <Mod/Mesh/MeshGlobal.h>

class SoState;

namespace MeshGui
{

/**
 * Build the retained triangle stream used by the mesh shapes.
 *
 * Coin state supplies the current material binding and colors, while winding
 * is captured in the generated positions and normals so render consumers do
 * not need to inspect scene-graph state again.
 */
MeshGuiExport Gui::MeshRenderData buildMeshObjectRenderData(
    SoState* state,
    const Mesh::MeshObject* mesh,
    const Gui::MeshRenderRevision& revision,
    bool ccw
);

}  // namespace MeshGui
