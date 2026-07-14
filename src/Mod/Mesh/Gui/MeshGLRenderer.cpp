// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2026 FreeCAD developers                                *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.       *
 *                                                                         *
 ***************************************************************************/

#include <FCConfig.h>

#ifndef FC_OS_WIN32
# ifndef GL_GLEXT_PROTOTYPES
#  define GL_GLEXT_PROTOTYPES 1
# endif
#else
# include <windows.h>
#endif

#ifdef FC_OS_MACOSX
# include <OpenGL/gl.h>
# include <OpenGL/glext.h>
#else
# include <GL/gl.h>
# include <GL/glext.h>
#endif

#include <cstddef>
#include <cstdint>
#include <vector>

#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/elements/SoGLLazyElement.h>
#include <Inventor/elements/SoMaterialBindingElement.h>
#include <Inventor/errors/SoDebugError.h>

#include <Gui/GLBuffer.h>

#include "MeshGLRenderer.h"


#define RENDER_GL_VAO

using namespace MeshGui;

namespace
{

SoMaterialBindingElement::Binding toCoinMaterialBinding(Gui::MeshMaterialBinding binding)
{
    switch (binding) {
        case Gui::MeshMaterialBinding::PerFace:
            return SoMaterialBindingElement::PER_FACE;
        case Gui::MeshMaterialBinding::PerFaceIndexed:
            return SoMaterialBindingElement::PER_FACE_INDEXED;
        case Gui::MeshMaterialBinding::PerVertex:
            return SoMaterialBindingElement::PER_VERTEX;
        case Gui::MeshMaterialBinding::PerVertexIndexed:
            return SoMaterialBindingElement::PER_VERTEX_INDEXED;
        case Gui::MeshMaterialBinding::Overall:
        default:
            return SoMaterialBindingElement::OVERALL;
    }
}

std::vector<float> interleaveMeshRenderData(const Gui::MeshRenderData& data)
{
    const std::size_t vertexCount = data.vertexCount();
    const bool hasColors = data.hasVertexColors();
    const std::size_t stride = hasColors ? 10 : 6;
    std::vector<float> result;
    result.reserve(vertexCount * stride);

    for (std::size_t i = 0; i < vertexCount; ++i) {
        if (hasColors) {
            result.insert(
                result.end(),
                data.colors.begin() + static_cast<std::ptrdiff_t>(i * 4),
                data.colors.begin() + static_cast<std::ptrdiff_t>(i * 4 + 4)
            );
        }
        result.insert(
            result.end(),
            data.normals.begin() + static_cast<std::ptrdiff_t>(i * 3),
            data.normals.begin() + static_cast<std::ptrdiff_t>(i * 3 + 3)
        );
        result.insert(
            result.end(),
            data.positions.begin() + static_cast<std::ptrdiff_t>(i * 3),
            data.positions.begin() + static_cast<std::ptrdiff_t>(i * 3 + 3)
        );
    }

    return result;
}

}  // namespace

#if defined RENDER_GL_VAO

class MeshGLRenderer::Private
{
public:
    Gui::OpenGLMultiBuffer vertices;
    Gui::OpenGLMultiBuffer indices;
    const SbColor* pcolors {nullptr};
    SoMaterialBindingElement::Binding matbinding {SoMaterialBindingElement::OVERALL};
    bool initialized {false};
    Gui::MeshRenderRevision revision;

    Private();
    bool canRenderGLArray(SoGLRenderAction*) const;
    void generateGLArrays(SoGLRenderAction* action, const Gui::MeshRenderData& data);
    void renderFacesGLArray(SoGLRenderAction*);
    void renderCoordsGLArray(SoGLRenderAction*);
    void update();
    bool needsUpdate(SoGLRenderAction*, const Gui::MeshRenderRevision& revision) const;

private:
    void renderGLArray(SoGLRenderAction*, GLenum);
};

MeshGLRenderer::Private::Private()
    : vertices(GL_ARRAY_BUFFER)
    , indices(GL_ELEMENT_ARRAY_BUFFER)
{}

bool MeshGLRenderer::Private::canRenderGLArray(SoGLRenderAction* action) const
{
    static bool init = false;
    static bool vboAvailable = false;
    if (!init) {
        vboAvailable = Gui::OpenGLBuffer::isVBOSupported(action->getCacheContext());
        if (!vboAvailable) {
            SoDebugError::postInfo(
                "MeshGLRenderer",
                "GL_ARB_vertex_buffer_object extension not supported"
            );
        }
        init = true;
    }

    return vboAvailable;
}

void MeshGLRenderer::Private::generateGLArrays(SoGLRenderAction* action, const Gui::MeshRenderData& data)
{
    if (data.empty()) {
        return;
    }

    // A revision change invalidates buffers in every context.  Keep this
    // invariant inside the adapter so callers cannot accidentally leave an
    // older context resident while uploading the new snapshot.
    if (data.revision != this->revision) {
        update();
    }

    std::vector<float> vertex = interleaveMeshRenderData(data);

    vertices.setCurrentContext(action->getCacheContext());
    indices.setCurrentContext(action->getCacheContext());

    initialized = true;
    vertices.create();
    indices.create();

    vertices.bind();
    vertices.allocate(vertex.data(), vertex.size() * sizeof(float));
    vertices.release();

    indices.bind();
    indices.allocate(data.indices.data(), data.indices.size() * sizeof(std::uint32_t));
    indices.release();
    this->matbinding = toCoinMaterialBinding(data.materialBinding);
    this->revision = data.revision;
}

void MeshGLRenderer::Private::renderGLArray(SoGLRenderAction* action, GLenum mode)
{
    if (!initialized) {
        SoDebugError::postWarning("MeshGLRenderer", "not initialized");
        return;
    }

    vertices.setCurrentContext(action->getCacheContext());
    indices.setCurrentContext(action->getCacheContext());

    glEnableClientState(GL_VERTEX_ARRAY);
    glEnableClientState(GL_NORMAL_ARRAY);
    glEnableClientState(GL_COLOR_ARRAY);

    vertices.bind();
    indices.bind();

    if (matbinding != SoMaterialBindingElement::OVERALL) {
        glInterleavedArrays(GL_C4F_N3F_V3F, 0, nullptr);
    }
    else {
        glInterleavedArrays(GL_N3F_V3F, 0, nullptr);
    }

    glDrawElements(mode, indices.size() / sizeof(uint32_t), GL_UNSIGNED_INT, nullptr);

    vertices.release();
    indices.release();

    glDisableClientState(GL_COLOR_ARRAY);
    glDisableClientState(GL_NORMAL_ARRAY);
    glDisableClientState(GL_VERTEX_ARRAY);
}

void MeshGLRenderer::Private::renderFacesGLArray(SoGLRenderAction* action)
{
    renderGLArray(action, GL_TRIANGLES);
}

void MeshGLRenderer::Private::renderCoordsGLArray(SoGLRenderAction* action)
{
    renderGLArray(action, GL_POINTS);
}

void MeshGLRenderer::Private::update()
{
    vertices.destroy();
    indices.destroy();
}

bool MeshGLRenderer::Private::needsUpdate(
    SoGLRenderAction* action,
    const Gui::MeshRenderRevision& revision
) const
{
    return revision != this->revision || !vertices.isCreated(action->getCacheContext())
        || !indices.isCreated(action->getCacheContext());
}
#elif defined RENDER_GLARRAYS
class MeshGLRenderer::Private
{
public:
    std::vector<std::uint32_t> index_array;
    std::vector<float> vertex_array;
    const SbColor* pcolors;
    SoMaterialBindingElement::Binding matbinding;

    Private()
        : pcolors(0)
        , matbinding(SoMaterialBindingElement::OVERALL)
    {}

    bool canRenderGLArray(SoGLRenderAction*) const;
    void generateGLArrays(SoGLRenderAction* action, const Gui::MeshRenderData& data);
    void renderFacesGLArray(SoGLRenderAction* action);
    void renderCoordsGLArray(SoGLRenderAction* action);
    void update()
    {}
    bool needsUpdate(SoGLRenderAction*, const Gui::MeshRenderRevision& revision) const
    {
        return revision != this->revision;
    }

    Gui::MeshRenderRevision revision;
};

bool MeshGLRenderer::Private::canRenderGLArray(SoGLRenderAction*) const
{
    return true;
}

void MeshGLRenderer::Private::generateGLArrays(SoGLRenderAction*, const Gui::MeshRenderData& data)
{
    if (data.empty()) {
        return;
    }

    this->index_array = data.indices;
    this->vertex_array = interleaveMeshRenderData(data);
    this->matbinding = toCoinMaterialBinding(data.materialBinding);
    this->revision = data.revision;
}

void MeshGLRenderer::Private::renderFacesGLArray(SoGLRenderAction* action)
{
    (void)action;
    int cnt = index_array.size();

    glEnableClientState(GL_NORMAL_ARRAY);
    glEnableClientState(GL_VERTEX_ARRAY);

    if (matbinding != SoMaterialBindingElement::OVERALL) {
        glInterleavedArrays(GL_C4F_N3F_V3F, 0, &(vertex_array[0]));
    }
    else {
        glInterleavedArrays(GL_N3F_V3F, 0, &(vertex_array[0]));
    }
    glDrawElements(GL_TRIANGLES, cnt, GL_UNSIGNED_INT, &(index_array[0]));

    glDisableClientState(GL_VERTEX_ARRAY);
    glDisableClientState(GL_NORMAL_ARRAY);
}

void MeshGLRenderer::Private::renderCoordsGLArray(SoGLRenderAction*)
{
    int cnt = index_array.size();

    glEnableClientState(GL_NORMAL_ARRAY);
    glEnableClientState(GL_VERTEX_ARRAY);

    if (matbinding != SoMaterialBindingElement::OVERALL) {
        glInterleavedArrays(GL_C4F_N3F_V3F, 0, &(vertex_array[0]));
    }
    else {
        glInterleavedArrays(GL_N3F_V3F, 0, &(vertex_array[0]));
    }
    glDrawElements(GL_POINTS, cnt, GL_UNSIGNED_INT, &(index_array[0]));

    glDisableClientState(GL_VERTEX_ARRAY);
    glDisableClientState(GL_NORMAL_ARRAY);
}
#else
class MeshGLRenderer::Private
{
public:
    const SbColor* pcolors;
    SoMaterialBindingElement::Binding matbinding;

    Private()
        : pcolors(0)
        , matbinding(SoMaterialBindingElement::OVERALL)
    {}

    bool canRenderGLArray(SoGLRenderAction*) const
    {
        return false;
    }
    void generateGLArrays(SoGLRenderAction*, const Gui::MeshRenderData&)
    {}
    void renderFacesGLArray(SoGLRenderAction*)
    {}
    void renderCoordsGLArray(SoGLRenderAction*)
    {}
    void update()
    {}
    bool needsUpdate(SoGLRenderAction*, const Gui::MeshRenderRevision&) const
    {
        return false;
    }
};
#endif

MeshGLRenderer::MeshGLRenderer()
    : p(new Private)
{}

MeshGLRenderer::~MeshGLRenderer()
{
    delete p;
}

void MeshGLRenderer::update()
{
    p->update();
}

bool MeshGLRenderer::needsUpdate(SoGLRenderAction* action, const Gui::MeshRenderRevision& revision) const
{
    return p->needsUpdate(action, revision);
}

void MeshGLRenderer::generateGLArrays(SoGLRenderAction* action, const Gui::MeshRenderData& data)
{
    SoGLLazyElement* gl = SoGLLazyElement::getInstance(action->getState());
    if (gl) {
        p->pcolors = gl->getDiffusePointer();
    }
    p->generateGLArrays(action, data);
}

void MeshGLRenderer::renderCoordsGLArray(SoGLRenderAction* action)
{
    p->renderCoordsGLArray(action);
}

void MeshGLRenderer::renderFacesGLArray(SoGLRenderAction* action)
{
    p->renderFacesGLArray(action);
}

bool MeshGLRenderer::canRenderGLArray(SoGLRenderAction* action) const
{
    return p->canRenderGLArray(action);
}

bool MeshGLRenderer::matchMaterial(SoState* state) const
{
    SoMaterialBindingElement::Binding matbind = SoMaterialBindingElement::get(state);
    if (p->matbinding != matbind) {
        return false;
    }
    if (matbind == SoMaterialBindingElement::OVERALL) {
        return true;
    }
    const SbColor* pcolors = nullptr;
    SoGLLazyElement* gl = SoGLLazyElement::getInstance(state);
    if (gl) {
        pcolors = gl->getDiffusePointer();
    }
    return p->pcolors == pcolors;
}

bool MeshGLRenderer::shouldRenderDirectly([[maybe_unused]] bool direct)
{
#ifdef RENDER_GL_VAO
    return false;
#else
    return direct;
#endif
}
