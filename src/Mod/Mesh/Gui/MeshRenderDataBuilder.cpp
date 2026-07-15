// SPDX-License-Identifier: LGPL-2.1-or-later

#include <algorithm>
#include <array>
#include <cstdint>

#include <Inventor/elements/SoGLLazyElement.h>
#include <Inventor/elements/SoMaterialBindingElement.h>
#include <Inventor/misc/SoState.h>

#include "MeshRenderDataBuilder.h"

namespace MeshGui
{

namespace
{

Gui::MeshMaterialBinding toMeshMaterialBinding(SoMaterialBindingElement::Binding binding)
{
    switch (binding) {
        case SoMaterialBindingElement::PER_FACE:
            return Gui::MeshMaterialBinding::PerFace;
        case SoMaterialBindingElement::PER_FACE_INDEXED:
            return Gui::MeshMaterialBinding::PerFaceIndexed;
        case SoMaterialBindingElement::PER_VERTEX:
            return Gui::MeshMaterialBinding::PerVertex;
        case SoMaterialBindingElement::PER_VERTEX_INDEXED:
            return Gui::MeshMaterialBinding::PerVertexIndexed;
        case SoMaterialBindingElement::PER_PART:
            return Gui::MeshMaterialBinding::PerPart;
        case SoMaterialBindingElement::PER_PART_INDEXED:
            return Gui::MeshMaterialBinding::PerPartIndexed;
        case SoMaterialBindingElement::OVERALL:
        default:
            return Gui::MeshMaterialBinding::Overall;
    }
}

bool isPerFaceBinding(SoMaterialBindingElement::Binding binding)
{
    return binding == SoMaterialBindingElement::PER_FACE
        || binding == SoMaterialBindingElement::PER_FACE_INDEXED
        || binding == SoMaterialBindingElement::PER_PART
        || binding == SoMaterialBindingElement::PER_PART_INDEXED;
}

bool isPerVertexBinding(SoMaterialBindingElement::Binding binding)
{
    return binding == SoMaterialBindingElement::PER_VERTEX
        || binding == SoMaterialBindingElement::PER_VERTEX_INDEXED;
}

}  // namespace

Gui::MeshRenderData buildMeshObjectRenderData(
    SoState* state,
    const Mesh::MeshObject* mesh,
    const Gui::MeshRenderRevision& revision,
    bool ccw
)
{
    Gui::MeshRenderData data;
    data.revision = revision;
    if (!mesh || !state) {
        return data;
    }

    const MeshCore::MeshKernel& kernel = mesh->getKernel();
    const MeshCore::MeshPointArray& points = kernel.GetPoints();
    const MeshCore::MeshFacetArray& facets = kernel.GetFacets();

    const SoMaterialBindingElement::Binding materialBinding = SoMaterialBindingElement::get(state);
    const bool perFace = isPerFaceBinding(materialBinding);
    const bool perVertex = isPerVertexBinding(materialBinding);

    const SoGLLazyElement* lazy = SoGLLazyElement::getInstance(state);
    const SbColor* diffuse = lazy ? lazy->getDiffusePointer() : nullptr;
    const int diffuseCount = lazy ? lazy->getNumDiffuse() : 0;
    const float* transparencies = lazy ? lazy->getTransparencyPointer() : nullptr;
    const int transparencyCount = lazy ? lazy->getNumTransparencies() : 0;

    const bool hasColors = (perFace || perVertex) && diffuse && diffuseCount > 0;
    if (hasColors) {
        data.materialBinding = toMeshMaterialBinding(materialBinding);
    }
    else {
        data.materialBinding = Gui::MeshMaterialBinding::Overall;
    }

    const std::size_t facetCount = facets.size();
    data.reserveVertices(3 * facetCount, hasColors);
    data.indices.reserve(3 * facetCount);

    const auto appendFacet = [&](Mesh::FacetIndex facetIndex) {
        if (facetIndex >= facets.size()) {
            return;
        }

        const MeshCore::MeshFacet& facet = facets[facetIndex];
        const Base::Vector3f facetNormal = kernel.GetFacet(facet).GetNormal();
        const Base::Vector3f normal = ccw
            ? facetNormal
            : Base::Vector3f(-facetNormal.x, -facetNormal.y, -facetNormal.z);
        const std::array<int, 3> order = ccw ? std::array<int, 3> {0, 1, 2}
                                             : std::array<int, 3> {0, 2, 1};

        const auto appendPoint = [&](int pointOrdinal) {
            const Mesh::PointIndex pointIndex = facet._aulPoints[pointOrdinal];
            if (pointIndex >= points.size()) {
                return;
            }

            const MeshCore::MeshPoint& point = points[pointIndex];
            const float position[3] {point.x, point.y, point.z};
            const float normalValue[3] {normal.x, normal.y, normal.z};
            if (hasColors) {
                const std::size_t requestedColorIndex = perVertex
                    ? static_cast<std::size_t>(pointIndex)
                    : static_cast<std::size_t>(facetIndex);
                const std::size_t colorIndex
                    = std::min(requestedColorIndex, static_cast<std::size_t>(diffuseCount - 1));
                const std::size_t transparencyIndex = transparencyCount > 0
                    ? std::min(colorIndex, static_cast<std::size_t>(transparencyCount - 1))
                    : 0;
                const float transparency = transparencies && transparencyCount > 0
                    ? transparencies[transparencyIndex]
                    : 0.0F;
                const SbColor& color = diffuse[colorIndex];
                const float colorValue[4] {
                    color[0],
                    color[1],
                    color[2],
                    1.0F - transparency,
                };
                data.appendColoredVertex(position, normalValue, colorValue);
            }
            else {
                data.appendVertex(position, normalValue);
            }
            data.indices.push_back(static_cast<std::uint32_t>(data.vertexCount() - 1));
        };

        appendPoint(order[0]);
        appendPoint(order[1]);
        appendPoint(order[2]);
    };

    for (std::size_t index = 0; index < facets.size(); ++index) {
        appendFacet(static_cast<Mesh::FacetIndex>(index));
    }

    return data;
}

}  // namespace MeshGui
