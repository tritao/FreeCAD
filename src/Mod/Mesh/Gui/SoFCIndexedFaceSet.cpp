// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2009 Werner Mayer <wmayer[at]users.sourceforge.net>     *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
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

#include <algorithm>
#include <limits>
#ifdef FC_OS_MACOSX
# include <OpenGL/gl.h>
# include <OpenGL/glext.h>
# include <OpenGL/glu.h>
#else
# include <GL/gl.h>
# include <GL/glext.h>
# include <GL/glu.h>
#endif
#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/actions/SoSearchAction.h>
#include <Inventor/bundles/SoMaterialBundle.h>
#include <Inventor/bundles/SoTextureCoordinateBundle.h>
#include <Inventor/elements/SoCoordinateElement.h>
#include <Inventor/elements/SoGLCacheContextElement.h>
#include <Inventor/elements/SoGLCoordinateElement.h>
#include <Inventor/elements/SoGLLazyElement.h>
#include <Inventor/elements/SoMaterialBindingElement.h>
#include <Inventor/elements/SoNormalBindingElement.h>
#include <Inventor/elements/SoNormalElement.h>
#include <Inventor/elements/SoProjectionMatrixElement.h>
#include <Inventor/elements/SoViewingMatrixElement.h>
#include <Inventor/errors/SoDebugError.h>
#include <Inventor/nodes/SoCoordinate3.h>

#include <Gui/SoFCInteractiveElement.h>
#include <Gui/Selection/SoFCSelectionAction.h>

#include "SoFCIndexedFaceSet.h"


#define RENDER_GL_VAO

using namespace MeshGui;

namespace
{

Gui::MeshMaterialBinding toMeshMaterialBinding(SoMaterialBindingElement::Binding binding)
{
    switch (binding) {
        case SoMaterialBindingElement::PER_FACE:
            return Gui::MeshMaterialBinding::PerFace;
        case SoMaterialBindingElement::PER_FACE_INDEXED:
            return Gui::MeshMaterialBinding::PerFaceIndexed;
        case SoMaterialBindingElement::PER_PART:
            return Gui::MeshMaterialBinding::PerPart;
        case SoMaterialBindingElement::PER_PART_INDEXED:
            return Gui::MeshMaterialBinding::PerPartIndexed;
        case SoMaterialBindingElement::PER_VERTEX:
            return Gui::MeshMaterialBinding::PerVertex;
        case SoMaterialBindingElement::PER_VERTEX_INDEXED:
            return Gui::MeshMaterialBinding::PerVertexIndexed;
        case SoMaterialBindingElement::OVERALL:
        default:
            return Gui::MeshMaterialBinding::Overall;
    }
}

}  // namespace

SO_NODE_SOURCE(SoFCIndexedFaceSet)

void SoFCIndexedFaceSet::initClass()
{
    SO_NODE_INIT_CLASS(SoFCIndexedFaceSet, SoIndexedFaceSet, "IndexedFaceSet");
}

SoFCIndexedFaceSet::SoFCIndexedFaceSet()
    : renderTriangleLimit(std::numeric_limits<unsigned>::max())
{
    SO_NODE_CONSTRUCTOR(SoFCIndexedFaceSet);
    setName(SoFCIndexedFaceSet::getClassTypeId().getName());
}

/**
 * Either renders the complete mesh or only a subset of the points.
 */
void SoFCIndexedFaceSet::GLRender(SoGLRenderAction* action)
{
    if (this->coordIndex.getNum() < 3) {
        return;
    }

    if (!this->shouldGLRender(action)) {
        // Transparency is handled inside 'shouldGLRender' but the base class
        // somehow misses to reset the blending mode. This causes SoGLLazyElement
        // not to switch on and off GL_BLEND mode and thus transparency doesn't
        // work as expected. Calling SoMaterialBundle::sendFirst seems to fix the
        // problem.
        SoMaterialBundle mb(action);
        mb.sendFirst();
        return;
    }

#if defined(RENDER_GL_VAO)
    SoState* state = action->getState();

    // get the VBO status of the viewer
    SbBool useVBO = true;
    Gui::SoGLVBOActivatedElement::get(state, useVBO);

    // Check for a matching OpenGL context
    if (!render.canRenderGLArray(action)) {
        useVBO = false;
    }

    // use VBO for fast rendering if possible
    if (useVBO) {
        if (render.needsUpdate(action, renderRevision) || !render.matchMaterial(state)) {
            render.update();
            const Gui::MeshRenderData data = buildMeshRenderData(state);
            generateGLArrays(action, data);
        }

        if (render.matchMaterial(state)) {
            SoMaterialBundle mb(action);
            mb.sendFirst();
            render.renderFacesGLArray(action);
        }
        else {
            drawFaces(action);
        }
    }
    else {
        drawFaces(action);
    }
#else
    drawFaces(action);
#endif
}

void SoFCIndexedFaceSet::drawFaces(SoGLRenderAction* action)
{
    SoState* state = action->getState();
    SbBool mode = Gui::SoFCInteractiveElement::get(state);

    const std::size_t numTriangles = this->coordIndex.getNum() / 4;
    const Gui::MeshInteractionLodPolicy policy(this->renderTriangleLimit);
    const Gui::MeshRenderPresentation presentation
        = policy.presentation(mode, numTriangles, this->coordIndex.getNum(), 4);
    if (!presentation.reducedGeometry) {
#ifdef RENDER_GLARRAYS
        SoMaterialBindingElement::Binding matbind = SoMaterialBindingElement::get(state);

        SbBool matchCtx = render.canRenderGLArray(action);
        if (matbind == SoMaterialBindingElement::OVERALL && matchCtx) {
            SoMaterialBundle mb(action);
            mb.sendFirst();
            if (render.needsUpdate(action, renderRevision)) {
                const Gui::MeshRenderData data = buildMeshRenderData(state);
                generateGLArrays(action, data);
            }
            render.renderFacesGLArray(action);
        }
        else {
            inherited::GLRender(action);
        }
#else
        inherited::GLRender(action);
#endif
    }
    else {
#if 0 && defined(RENDER_GLARRAYS)
        SoMaterialBundle mb(action);
        mb.sendFirst();
        render.renderCoordsGLArray(action);
#else
        SoMaterialBindingElement::Binding matbind = SoMaterialBindingElement::get(state);
        int32_t binding = (int32_t)(matbind);

        const SoCoordinateElement* coords = nullptr;
        const SbVec3f* normals = nullptr;
        const int32_t* cindices = nullptr;
        int numindices = 0;
        const int32_t* nindices = nullptr;
        const int32_t* tindices = nullptr;
        const int32_t* mindices = nullptr;
        SbBool normalCacheUsed {};

        SoMaterialBundle mb(action);

        SoTextureCoordinateBundle tb(action, true, false);
        SbBool sendNormals = !mb.isColorOnly() || tb.isFunction();

        this->getVertexData(
            state,
            coords,
            normals,
            cindices,
            nindices,
            tindices,
            mindices,
            numindices,
            sendNormals,
            normalCacheUsed
        );

        mb.sendFirst();  // make sure we have the correct material

        drawCoords(
            static_cast<const SoGLCoordinateElement*>(coords),
            cindices,
            numindices,
            normals,
            nindices,
            &mb,
            mindices,
            binding,
            &tb,
            tindices,
            presentation.pointStride
        );

        // getVertexData() internally calls readLockNormalCache() that read locks
        // the normal cache. When the cache is not needed any more we must call
        // readUnlockNormalCache()
        if (normalCacheUsed) {
            this->readUnlockNormalCache();
        }

        // Disable caching for this node
        SoGLCacheContextElement::shouldAutoCache(state, SoGLCacheContextElement::DONT_AUTO_CACHE);
#endif
    }
}

void SoFCIndexedFaceSet::drawCoords(
    const SoGLCoordinateElement* const vertexlist,
    const int32_t* vertexindices,
    int numindices,
    const SbVec3f* normals,
    const int32_t* normalindices,
    SoMaterialBundle* materials,
    const int32_t* /*matindices*/,
    const int32_t binding,
    const SoTextureCoordinateBundle* const /*texcoords*/,
    const int32_t* /*texindices*/,
    std::size_t pointStride
)
{
    const SbVec3f* coords3d = nullptr;
    coords3d = vertexlist->getArrayPtr3();

    const int mod = static_cast<int>(pointStride);
    float size = std::min<float>((float)mod, 3.0F);
    glPointSize(size);

    SbBool per_face = false;
    SbBool per_vert = false;
    switch (binding) {
        case SoMaterialBindingElement::PER_FACE:
            per_face = true;
            break;
        case SoMaterialBindingElement::PER_VERTEX:
            per_vert = true;
            break;
        default:
            break;
    }

    int ct = 0;
    const int32_t* viptr = vertexindices;
    int32_t v1 {}, v2 {}, v3 {};
    SbVec3f dummynormal(0, 0, 1);
    const SbVec3f* currnormal = &dummynormal;
    if (normals) {
        currnormal = normals;
    }

    glBegin(GL_POINTS);
    for (int index = 0; index < numindices; ct++) {
        if (ct % mod == 0) {
            if (per_face) {
                materials->send(ct, true);
            }
            v1 = *viptr++;
            index++;
            if (per_vert) {
                materials->send(v1, true);
            }
            if (normals) {
                currnormal = &normals[*normalindices++];
            }
            glNormal3fv((const GLfloat*)currnormal);
            glVertex3fv((const GLfloat*)(coords3d + v1));

            v2 = *viptr++;
            index++;
            if (per_vert) {
                materials->send(v2, true);
            }
            if (normals) {
                currnormal = &normals[*normalindices++];
            }
            glNormal3fv((const GLfloat*)currnormal);
            glVertex3fv((const GLfloat*)(coords3d + v2));

            v3 = *viptr++;
            index++;
            if (per_vert) {
                materials->send(v3, true);
            }
            if (normals) {
                currnormal = &normals[*normalindices++];
            }
            glNormal3fv((const GLfloat*)currnormal);
            glVertex3fv((const GLfloat*)(coords3d + v3));
        }
        else {
            viptr++;
            index++;
            normalindices++;
            viptr++;
            index++;
            normalindices++;
            viptr++;
            index++;
            normalindices++;
        }

        viptr++;
        index++;
        normalindices++;
    }
    glEnd();
}

void SoFCIndexedFaceSet::invalidate()
{
    renderRevision.invalidate();
}

Gui::MeshRenderData SoFCIndexedFaceSet::buildMeshRenderData(SoState* state)
{
    Gui::MeshRenderData data;
    data.revision = renderRevision;

    if (!state) {
        return data;
    }

    const SoCoordinateElement* coords = nullptr;
    const SbVec3f* normals = nullptr;
    const int32_t* cindices = nullptr;
    const SbColor* pcolors = nullptr;
    const float* transp = nullptr;
    int numindices = 0, numcolors = 0, numtransp = 0;
    const int32_t* nindices = nullptr;
    const int32_t* tindices = nullptr;
    const int32_t* mindices = nullptr;
    SbBool normalCacheUsed {};

    SbBool sendNormals = true;

    const SbBool vertexDataAvailable = this->getVertexData(
        state,
        coords,
        normals,
        cindices,
        nindices,
        tindices,
        mindices,
        numindices,
        sendNormals,
        normalCacheUsed
    );
    if (!vertexDataAvailable) {
        if (normalCacheUsed) {
            this->readUnlockNormalCache();
        }
        return data;
    }

    const SbVec3f* points = coords->getArrayPtr3();
    if (!points || !normals || !cindices || numindices <= 0) {
        if (normalCacheUsed) {
            this->readUnlockNormalCache();
        }
        return data;
    }

    const SoMaterialBindingElement::Binding matbind = SoMaterialBindingElement::get(state);
    data.materialBinding = toMeshMaterialBinding(matbind);
    SoGLLazyElement* gl = SoGLLazyElement::getInstance(state);
    if (gl) {
        pcolors = gl->getDiffusePointer();
        numcolors = gl->getNumDiffuse();
        transp = gl->getTransparencyPointer();
        numtransp = gl->getNumTransparencies();
    }

    const std::size_t numTria = static_cast<std::size_t>(numindices / 4);
    const bool perFaceMaterial = matbind == SoMaterialBindingElement::PER_FACE
        || matbind == SoMaterialBindingElement::PER_FACE_INDEXED
        || matbind == SoMaterialBindingElement::PER_PART
        || matbind == SoMaterialBindingElement::PER_PART_INDEXED;
    const bool perVertexMaterial = matbind == SoMaterialBindingElement::PER_VERTEX
        || matbind == SoMaterialBindingElement::PER_VERTEX_INDEXED;
    const bool hasColors = pcolors && numcolors > 0 && (perFaceMaterial || perVertexMaterial);
    if (!hasColors) {
        data.materialBinding = Gui::MeshMaterialBinding::Overall;
    }

    const SoNormalBindingElement::Binding normalBinding = [&] {
        SoNormalBindingElement::Binding binding = SoNormalBindingElement::get(state);
        if (normalCacheUsed && binding == SoNormalBindingElement::PER_VERTEX) {
            binding = SoNormalBindingElement::PER_VERTEX_INDEXED;
        }
        if (normalCacheUsed && binding == SoNormalBindingElement::PER_FACE_INDEXED) {
            binding = SoNormalBindingElement::PER_FACE;
        }
        return binding;
    }();

    const int normalCount = SoNormalElement::getInstance(state)->getNum();
    const auto safeIndex = [](int32_t index) -> std::size_t {
        return index < 0 ? 0U : static_cast<std::size_t>(index);
    };
    const auto clampColorIndex = [&](std::size_t index) {
        return std::min(index, static_cast<std::size_t>(numcolors - 1));
    };
    const auto opacityFor = [&](std::size_t index) {
        if (!transp || numtransp <= 0) {
            return 1.0F;
        }
        const std::size_t transparencyIndex = std::min(index, static_cast<std::size_t>(numtransp - 1));
        return 1.0F - transp[transparencyIndex];
    };
    const auto materialIndexFor = [&](std::size_t faceIndex, std::size_t vertexIndex) {
        switch (matbind) {
            case SoMaterialBindingElement::PER_VERTEX:
                return vertexIndex;
            case SoMaterialBindingElement::PER_VERTEX_INDEXED:
                return safeIndex(mindices ? mindices[vertexIndex] : cindices[vertexIndex]);
            case SoMaterialBindingElement::PER_FACE_INDEXED:
            case SoMaterialBindingElement::PER_PART_INDEXED:
                return safeIndex(mindices ? mindices[faceIndex] : cindices[faceIndex * 4]);
            case SoMaterialBindingElement::PER_FACE:
            case SoMaterialBindingElement::PER_PART:
                return faceIndex;
            default:
                return std::size_t {0};
        }
    };
    const auto normalIndexFor = [&](std::size_t faceIndex, std::size_t vertexIndex) {
        switch (normalBinding) {
            case SoNormalBindingElement::PER_VERTEX:
                return static_cast<int32_t>(vertexIndex);
            case SoNormalBindingElement::PER_VERTEX_INDEXED:
                return nindices ? nindices[vertexIndex] : cindices[vertexIndex];
            case SoNormalBindingElement::PER_FACE_INDEXED:
            case SoNormalBindingElement::PER_PART_INDEXED:
                return nindices ? nindices[faceIndex] : cindices[faceIndex * 4];
            case SoNormalBindingElement::PER_FACE:
            case SoNormalBindingElement::PER_PART:
                return static_cast<int32_t>(faceIndex);
            default:
                return 0;
        }
    };

    auto appendVertex = [&data,
                         points,
                         normals,
                         normalCount](int32_t pointIndex, int32_t normalIndex, const float* color) {
        const int32_t safeNormalIndex = normalCount > 0 ? std::clamp(normalIndex, 0, normalCount - 1)
                                                        : std::max(normalIndex, 0);
        const SbVec3f& normal = normals[safeNormalIndex];
        const SbVec3f& point = points[pointIndex];
        const float position[3] {point[0], point[1], point[2]};
        const float normalValue[3] {normal[0], normal[1], normal[2]};
        if (color) {
            data.appendColoredVertex(position, normalValue, color);
        }
        else {
            data.appendVertex(position, normalValue);
        }
        data.indices.push_back(static_cast<std::uint32_t>(data.vertexCount() - 1));
    };

    data.reserveVertices(3 * numTria, hasColors);
    data.indices.reserve(3 * numTria);
    for (std::size_t faceIndex = 0; faceIndex < numTria; ++faceIndex) {
        const std::size_t baseIndex = faceIndex * 4;
        bool validFace = true;
        for (std::size_t corner = 0; corner < 3; ++corner) {
            const int32_t pointIndex = cindices[baseIndex + corner];
            if (pointIndex < 0 || pointIndex >= coords->getNum()) {
                validFace = false;
                break;
            }
        }
        if (!validFace) {
            continue;
        }

        for (std::size_t corner = 0; corner < 3; ++corner) {
            const std::size_t vertexIndex = baseIndex + corner;
            const int32_t pointIndex = cindices[vertexIndex];

            const std::size_t materialIndex = materialIndexFor(faceIndex, vertexIndex);
            if (hasColors) {
                const SbColor& color = pcolors[clampColorIndex(materialIndex)];
                const float colorValue[4] {
                    color[0],
                    color[1],
                    color[2],
                    opacityFor(materialIndex),
                };
                appendVertex(pointIndex, normalIndexFor(faceIndex, vertexIndex), colorValue);
            }
            else {
                appendVertex(pointIndex, normalIndexFor(faceIndex, vertexIndex), nullptr);
            }
        }
    }

    // getVertexData() internally calls readLockNormalCache() that read locks
    // the normal cache. When the cache is not needed any more we must call
    // readUnlockNormalCache()
    if (normalCacheUsed) {
        this->readUnlockNormalCache();
    }

    return data;
}

void SoFCIndexedFaceSet::generateGLArrays(SoGLRenderAction* action, const Gui::MeshRenderData& data)
{
    render.generateGLArrays(action, data);
}

void SoFCIndexedFaceSet::doAction(SoAction* action)
{
    if (action->getTypeId() == Gui::SoGLSelectAction::getClassTypeId()) {
        SoNode* node = action->getNodeAppliedTo();
        if (!node) {  // on no node applied
            return;
        }

        // The node we have is the parent of this node and the coordinate node
        // thus we search there for it.
        SoSearchAction sa;
        sa.setInterest(SoSearchAction::FIRST);
        sa.setSearchingAll(false);
        sa.setType(SoCoordinate3::getClassTypeId(), 1);
        sa.apply(node);
        SoPath* path = sa.getPath();
        if (!path) {
            return;
        }

        // make sure we got the node we wanted
        SoNode* coords = path->getNodeFromTail(0);
        if (!(coords && coords->getTypeId().isDerivedFrom(SoCoordinate3::getClassTypeId()))) {
            return;
        }
        startSelection(action);
        renderSelectionGeometry(static_cast<SoCoordinate3*>(coords)->point.getValues(0));
        stopSelection(action);
    }
    else if (action->getTypeId() == Gui::SoVisibleFaceAction::getClassTypeId()) {
        SoNode* node = action->getNodeAppliedTo();
        if (!node) {  // on no node applied
            return;
        }

        // The node we have is the parent of this node and the coordinate node
        // thus we search there for it.
        SoSearchAction sa;
        sa.setInterest(SoSearchAction::FIRST);
        sa.setSearchingAll(false);
        sa.setType(SoCoordinate3::getClassTypeId(), 1);
        sa.apply(node);
        SoPath* path = sa.getPath();
        if (!path) {
            return;
        }

        // make sure we got the node we wanted
        SoNode* coords = path->getNodeFromTail(0);
        if (!(coords && coords->getTypeId().isDerivedFrom(SoCoordinate3::getClassTypeId()))) {
            return;
        }
        startVisibility(action);
        renderVisibleFaces(static_cast<SoCoordinate3*>(coords)->point.getValues(0));
        stopVisibility(action);
    }

    inherited::doAction(action);
}

void SoFCIndexedFaceSet::startSelection(SoAction* action)
{
    Gui::SoGLSelectAction* doaction = static_cast<Gui::SoGLSelectAction*>(action);
    const SbViewportRegion& vp = doaction->getViewportRegion();
    int x = vp.getViewportOriginPixels()[0];
    int y = vp.getViewportOriginPixels()[1];
    int w = vp.getViewportSizePixels()[0];
    int h = vp.getViewportSizePixels()[1];

    int bufSize = 5 * (this->coordIndex.getNum() / 4);  // make the buffer big enough
    this->selectBuf = new GLuint[bufSize];

    SbMatrix view = SoViewingMatrixElement::get(action->getState());  // clazy:exclude=rule-of-two-soft
    SbMatrix proj = SoProjectionMatrixElement::get(action->getState());  // clazy:exclude=rule-of-two-soft

    glSelectBuffer(bufSize, selectBuf);
    glRenderMode(GL_SELECT);

    glInitNames();
    glPushName(-1);

    GLint viewport[4];
    glGetIntegerv(GL_VIEWPORT, viewport);
    glMatrixMode(GL_PROJECTION);

    glPushMatrix();
    glLoadIdentity();

    if (w > 0 && h > 0) {
        glTranslatef(
            (viewport[2] - 2 * (x - viewport[0])) / w,
            (viewport[3] - 2 * (y - viewport[1])) / h,
            0
        );
        glScalef(viewport[2] / w, viewport[3] / h, 1.0);
    }
    glMultMatrixf(/*mp*/ (float*)proj);
    glMatrixMode(GL_MODELVIEW);
    glPushMatrix();
    glLoadMatrixf((float*)view);
}

void SoFCIndexedFaceSet::stopSelection(SoAction* action)
{
    // restoring the original projection matrix
    glPopMatrix();
    glMatrixMode(GL_PROJECTION);
    glPopMatrix();
    glMatrixMode(GL_MODELVIEW);
    glFlush();

    // returning to normal rendering mode
    GLint hits = glRenderMode(GL_RENDER);

    int bufSize = 5 * (this->coordIndex.getNum() / 4);
    std::vector<std::pair<double, unsigned int>> hit;
    GLint index = 0;
    for (GLint ii = 0; ii < hits && index < bufSize; ii++) {
        GLint ct = (GLint)selectBuf[index];
        hit.emplace_back(selectBuf[index + 1] / 4294967295.0, selectBuf[index + 3]);
        index = index + ct + 3;
    }

    delete[] selectBuf;
    selectBuf = nullptr;
    std::sort(hit.begin(), hit.end());

    Gui::SoGLSelectAction* doaction = static_cast<Gui::SoGLSelectAction*>(action);
    doaction->indices.reserve(hit.size());
    for (GLint ii = 0; ii < hits; ii++) {
        doaction->indices.push_back(hit[ii].second);
    }
}

void SoFCIndexedFaceSet::renderSelectionGeometry(const SbVec3f* coords3d)
{
    int numfaces = this->coordIndex.getNum() / 4;
    const int32_t* cindices = this->coordIndex.getValues(0);

    int fcnt = 0;
    int32_t v1 {}, v2 {}, v3 {};
    for (int index = 0; index < numfaces; index++, cindices++) {
        glLoadName(fcnt);
        glBegin(GL_TRIANGLES);
        v1 = *cindices++;
        glVertex3fv((const GLfloat*)(coords3d + v1));
        v2 = *cindices++;
        glVertex3fv((const GLfloat*)(coords3d + v2));
        v3 = *cindices++;
        glVertex3fv((const GLfloat*)(coords3d + v3));
        glEnd();
        fcnt++;
    }
}

void SoFCIndexedFaceSet::startVisibility(SoAction* action)
{
    SbMatrix view = SoViewingMatrixElement::get(action->getState());  // clazy:exclude=rule-of-two-soft
    SbMatrix proj = SoProjectionMatrixElement::get(action->getState());  // clazy:exclude=rule-of-two-soft

    glMatrixMode(GL_PROJECTION);
    glPushMatrix();
    glLoadIdentity();
    glMultMatrixf((float*)proj);
    glMatrixMode(GL_MODELVIEW);
    glPushMatrix();
    glLoadMatrixf((float*)view);
}

void SoFCIndexedFaceSet::stopVisibility(SoAction* /*action*/)
{
    // restoring the original projection matrix
    glPopMatrix();
    glMatrixMode(GL_PROJECTION);
    glPopMatrix();
    glMatrixMode(GL_MODELVIEW);
    glFlush();
}

void SoFCIndexedFaceSet::renderVisibleFaces(const SbVec3f* coords3d)
{
    glDisable(GL_BLEND);
    glDisable(GL_DITHER);
    glDisable(GL_FOG);
    glDisable(GL_LIGHTING);
    glDisable(GL_TEXTURE_1D);
    glDisable(GL_TEXTURE_2D);
    glShadeModel(GL_FLAT);

    uint32_t numfaces = this->coordIndex.getNum() / 4;
    const int32_t* cindices = this->coordIndex.getValues(0);

    int32_t v1 {}, v2 {}, v3 {};
    for (uint32_t index = 0; index < numfaces; index++, cindices++) {
        glBegin(GL_TRIANGLES);
        float t {};
        SbColor c;
        c.setPackedValue(index << 8, t);
        glColor3f(c[0], c[1], c[2]);
        v1 = *cindices++;
        glVertex3fv((const GLfloat*)(coords3d + v1));
        v2 = *cindices++;
        glVertex3fv((const GLfloat*)(coords3d + v2));
        v3 = *cindices++;
        glVertex3fv((const GLfloat*)(coords3d + v3));
        glEnd();
    }
}
