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

// ----------------------------------------------------------------------------

SO_ENGINE_SOURCE(SoFCMaterialEngine)

SoFCMaterialEngine::SoFCMaterialEngine()
{
    SO_ENGINE_CONSTRUCTOR(SoFCMaterialEngine);

    SO_ENGINE_ADD_INPUT(diffuseColor, (SbColor(0.0, 0.0, 0.0)));
    SO_ENGINE_ADD_OUTPUT(trigger, SoSFBool);
}

SoFCMaterialEngine::~SoFCMaterialEngine() = default;

void SoFCMaterialEngine::initClass()
{
    SO_ENGINE_INIT_CLASS(SoFCMaterialEngine, SoEngine, "Engine");
}

void SoFCMaterialEngine::inputChanged(SoField*)
{
    SO_ENGINE_OUTPUT(trigger, SoSFBool, setValue(true));
}

void SoFCMaterialEngine::evaluate()
{
    // do nothing here
}

// ----------------------------------------------------------------------------

SO_NODE_SOURCE(SoFCIndexedFaceSet)

void SoFCIndexedFaceSet::initClass()
{
    SO_NODE_INIT_CLASS(SoFCIndexedFaceSet, SoIndexedFaceSet, "IndexedFaceSet");
}

SoFCIndexedFaceSet::SoFCIndexedFaceSet()
    : renderTriangleLimit(std::numeric_limits<unsigned>::max())
{
    SO_NODE_CONSTRUCTOR(SoFCIndexedFaceSet);
    SO_NODE_ADD_FIELD(updateGLArray, (false));
    updateGLArray.setFieldType(SoField::EVENTOUT_FIELD);
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
        if (updateGLArray.getValue()) {
            renderRevision.invalidate();
            updateGLArray.setValue(false);
            render.update();
            generateGLArrays(action);
        }
        else if (render.needsUpdate(action, renderRevision)) {
            generateGLArrays(action);
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

    unsigned int num = this->coordIndex.getNum() / 4;
    const Gui::MeshInteractionLodPolicy policy(this->renderTriangleLimit);
    if (!policy.shouldUseReducedGeometry(mode, num)) {
#ifdef RENDER_GLARRAYS
        SoMaterialBindingElement::Binding matbind = SoMaterialBindingElement::get(state);

        SbBool matchCtx = render.canRenderGLArray(action);
        if (matbind == SoMaterialBindingElement::OVERALL && matchCtx) {
            SoMaterialBundle mb(action);
            mb.sendFirst();
            if (updateGLArray.getValue()) {
                renderRevision.invalidate();
                updateGLArray.setValue(false);
                generateGLArrays(action);
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
            tindices
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
    const int32_t* /*texindices*/
)
{
    const SbVec3f* coords3d = nullptr;
    coords3d = vertexlist->getArrayPtr3();

    const Gui::MeshInteractionLodPolicy policy(this->renderTriangleLimit);
    int mod = static_cast<int>(policy.pointStride(numindices, 4));
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
    updateGLArray.setValue(true);
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

    SoMaterialBindingElement::Binding matbind = SoMaterialBindingElement::get(state);
    data.materialBinding = toMeshMaterialBinding(matbind);
    SoGLLazyElement* gl = SoGLLazyElement::getInstance(state);
    if (gl) {
        pcolors = gl->getDiffusePointer();
        numcolors = gl->getNumDiffuse();
        transp = gl->getTransparencyPointer();
        numtransp = gl->getNumTransparencies();
        (void)numtransp;
    }

    std::size_t numTria = numindices / 4;

    if (!mindices && matbind == SoMaterialBindingElement::PER_VERTEX_INDEXED) {
        mindices = cindices;
    }

    SoNormalBindingElement::Binding normbind = SoNormalBindingElement::get(state);

    auto appendVertex =
        [&data, points, normals](int32_t pointIndex, int32_t normalIndex, const float* color) {
            const SbVec3f& normal = normals[normalIndex];
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

    if (normbind == SoNormalBindingElement::PER_VERTEX_INDEXED) {
        const bool hasVertexColors = matbind == SoMaterialBindingElement::PER_FACE
            || matbind == SoMaterialBindingElement::PER_VERTEX_INDEXED;
        data.reserveVertices(3 * numTria, hasVertexColors);
        data.indices.reserve(3 * numTria);

        if (matbind == SoMaterialBindingElement::PER_FACE) {
            if (numcolors != static_cast<int>(numTria)) {
                SoDebugError::postWarning(
                    "SoFCIndexedFaceSet::generateGLArrays",
                    "The number of faces (%d) does not match with the number of colors (%d).",
                    numTria,
                    numcolors
                );
            }

            // the nindices must have the length of numindices
            int index = 0;
            float t = transp ? transp[0] : 0;
            for (std::size_t i = 0; i < numTria; i++) {
                const SbColor& c = pcolors[i];
                const float color[4] {c[0], c[1], c[2], t};
                for (int j = 0; j < 3; j++) {
                    appendVertex(cindices[index], nindices[index], color);
                    index++;
                }
                index++;
            }
        }
        else if (matbind == SoMaterialBindingElement::PER_VERTEX_INDEXED) {
            if (numcolors != coords->getNum()) {
                SoDebugError::postWarning(
                    "SoFCIndexedFaceSet::generateGLArrays",
                    "The number of points (%d) does not match with the number of colors (%d).",
                    coords->getNum(),
                    numcolors
                );
            }

            // the nindices must have the length of numindices
            int index = 0;
            float t = transp ? transp[0] : 0;
            for (std::size_t i = 0; i < numTria; i++) {
                for (int j = 0; j < 3; j++) {
                    const SbColor& c = pcolors[mindices[index]];
                    const float color[4] {c[0], c[1], c[2], t};
                    appendVertex(cindices[index], nindices[index], color);
                    index++;
                }
                index++;
            }
        }
        else {
            // only an overall material
            matbind = SoMaterialBindingElement::OVERALL;
            data.materialBinding = Gui::MeshMaterialBinding::Overall;

            // the nindices must have the length of numindices
            int index = 0;
            for (std::size_t i = 0; i < numTria; i++) {
                for (int j = 0; j < 3; j++) {
                    appendVertex(cindices[index], nindices[index], nullptr);
                    index++;
                }
                index++;
            }
        }
    }
    else if (normbind == SoNormalBindingElement::PER_VERTEX) {
        // only an overall material
        data.materialBinding = Gui::MeshMaterialBinding::Overall;

        std::size_t numPts = coords->getNum();
        data.reserveVertices(numPts, false);
        for (std::size_t i = 0; i < numPts; i++) {
            const SbVec3f& n = normals[i];
            const SbVec3f& p = coords->get3(i);
            const float position[3] {p[0], p[1], p[2]};
            const float normal[3] {n[0], n[1], n[2]};
            data.appendVertex(position, normal);
        }

        int index = 0;
        for (std::size_t i = 0; i < numTria; i++) {
            for (int j = 0; j < 3; j++) {
                data.indices.push_back(static_cast<std::uint32_t>(cindices[index]));
                index++;
            }
            index++;
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

void SoFCIndexedFaceSet::generateGLArrays(SoGLRenderAction* action)
{
    const Gui::MeshRenderData data = buildMeshRenderData(action->getState());
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
