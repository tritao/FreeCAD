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

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace Gui
{

/** Header-only mesh render values intentionally have no DLL export annotations. */

/**
 * Monotonic revision token for backend-neutral mesh snapshots.
 *
 * Producers invalidate the token when their source mesh or render inputs
 * change.  Render backends can use the value to distinguish a new snapshot
 * from a new OpenGL context without knowing anything about the scene graph.
 */
class MeshRenderRevision
{
public:
    void invalidate() noexcept
    {
        ++value_;
    }

    bool operator==(const MeshRenderRevision& other) const noexcept
    {
        return value_ == other.value_;
    }

    bool operator!=(const MeshRenderRevision& other) const noexcept
    {
        return !(*this == other);
    }

private:
    std::uint64_t value_ {0};
};

/**
 * The material binding represented by a mesh render stream.
 *
 * This deliberately does not use Coin's binding enum.  The render data is
 * shared between the legacy OpenGL adapter and future render backends.
 */
enum class MeshMaterialBinding
{
    Overall,
    PerFace,
    PerFaceIndexed,
    PerVertex,
    PerVertexIndexed
};

/**
 * Backend-neutral, triangle-oriented mesh data.
 *
 * The arrays contain separate attributes rather than an OpenGL-specific
 * interleaved layout.  A backend may upload them directly or pack them into
 * its preferred representation.
 */
struct MeshRenderData
{
    std::vector<float> positions;
    std::vector<float> normals;
    std::vector<float> colors;
    std::vector<std::uint32_t> indices;
    MeshMaterialBinding materialBinding {MeshMaterialBinding::Overall};
    MeshRenderRevision revision;

    bool empty() const noexcept
    {
        return positions.empty() || indices.empty();
    }

    std::size_t vertexCount() const noexcept
    {
        return positions.size() / 3;
    }

    bool hasVertexColors() const noexcept
    {
        return !colors.empty();
    }

    void reserveVertices(std::size_t count, bool withColors)
    {
        positions.reserve(3 * count);
        normals.reserve(3 * count);
        if (withColors) {
            colors.reserve(4 * count);
        }
    }

    void appendVertex(const float* position, const float* normal)
    {
        assert(colors.empty());
        positions.insert(positions.end(), position, position + 3);
        normals.insert(normals.end(), normal, normal + 3);
    }

    void appendColoredVertex(const float* position, const float* normal, const float* color)
    {
        assert(colors.size() == 4 * vertexCount());
        positions.insert(positions.end(), position, position + 3);
        normals.insert(normals.end(), normal, normal + 3);
        colors.insert(colors.end(), color, color + 4);
    }
};

/**
 * Presentation selected for a mesh during a render pass.
 *
 * The policy is kept separate from the render data so a backend can make the
 * same full-detail versus reduced-detail decision without depending on Coin
 * state or an OpenGL implementation.
 */
struct MeshRenderPresentation
{
    bool reducedGeometry {false};
    std::size_t pointStride {1};
};

/**
 * Renderer-independent policy for reducing mesh detail during interaction.
 */
class MeshInteractionLodPolicy
{
public:
    explicit MeshInteractionLodPolicy(
        unsigned int triangleLimit = std::numeric_limits<unsigned int>::max()
    )
        : triangleLimit(triangleLimit)
    {}

    bool shouldUseReducedGeometry(bool interactive, std::size_t triangleCount) const noexcept
    {
        return interactive && triangleCount > triangleLimit;
    }

    std::size_t pointStride(std::size_t indexCount, std::size_t indicesPerTriangle = 1) const noexcept
    {
        if (indicesPerTriangle == 0 || triangleLimit == 0) {
            return 1;
        }

        return indexCount / (indicesPerTriangle * triangleLimit) + 1;
    }

    MeshRenderPresentation presentation(
        bool interactive,
        std::size_t triangleCount,
        std::size_t indexCount,
        std::size_t indicesPerTriangle = 1
    ) const noexcept
    {
        const bool reduced = shouldUseReducedGeometry(interactive, triangleCount);
        return {reduced, reduced ? pointStride(indexCount, indicesPerTriangle) : 1};
    }

    unsigned int triangleLimit;
};

}  // namespace Gui
