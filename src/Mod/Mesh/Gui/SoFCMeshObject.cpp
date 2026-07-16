// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2006 Werner Mayer <wmayer[at]users.sourceforge.net>     *
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

#include <algorithm>
#include <limits>
#include <utility>
#include <vector>
#ifdef FC_OS_WIN32
# include <windows.h>
#endif
#ifdef FC_OS_MACOSX
# include <OpenGL/gl.h>
# include <OpenGL/glu.h>
#else
# include <GL/gl.h>
# include <GL/glu.h>
#endif
#include <Inventor/SbLine.h>
#include <Inventor/SoPickedPoint.h>
#include <Inventor/SoPrimitiveVertex.h>
#include <Inventor/actions/SoCallbackAction.h>
#include <Inventor/actions/SoGetBoundingBoxAction.h>
#include <Inventor/actions/SoGetPrimitiveCountAction.h>
#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/actions/SoPickAction.h>
#include <Inventor/actions/SoSearchAction.h>
#include <Inventor/bundles/SoMaterialBundle.h>
#include <Inventor/details/SoFaceDetail.h>
#include <Inventor/misc/SoState.h>

#include <Base/Console.h>
#include <Base/Exception.h>
#include <Gui/MeshRenderData.h>
#include <Gui/SoFCInteractiveElement.h>
#include <Gui/Selection/SoFCSelectionAction.h>
#include <Mod/Mesh/App/Core/Algorithm.h>
#include <Mod/Mesh/App/Core/Elements.h>
#include <Mod/Mesh/App/Core/Grid.h>
#include <Mod/Mesh/App/Core/MeshKernel.h>

#include "MeshRenderDataBuilder.h"
#include "SoFCMeshObject.h"


using namespace MeshGui;

class SoOutputStreambuf: public std::streambuf
{
public:
    explicit SoOutputStreambuf(SoOutput* o)
        : out(o)
    {}

protected:
    int overflow(int c = EOF) override
    {
        if (c != EOF) {
            char z = static_cast<char>(c);
            out->write(z);
        }
        return c;
    }
    std::streamsize xsputn(const char* s, std::streamsize num) override
    {
        out->write(s);
        return num;
    }

private:
    SoOutput* out;
};

class SoOutputStream: public std::ostream
{
public:
    explicit SoOutputStream(SoOutput* o)
        : std::ostream(nullptr)
        , buf(o)
    {
        this->rdbuf(&buf);
    }

private:
    SoOutputStreambuf buf;
};

class SoInputStreambuf: public std::streambuf
{
public:
    explicit SoInputStreambuf(SoInput* o)
        : inp(o)
    {
        setg(buffer + pbSize, buffer + pbSize, buffer + pbSize);
    }

protected:
    int underflow() override
    {
        if (gptr() < egptr()) {
            return *gptr();
        }

        int numPutback {};
        numPutback = gptr() - eback();
        if (numPutback > pbSize) {
            numPutback = pbSize;
        }

        memcpy(buffer + (pbSize - numPutback), gptr() - numPutback, numPutback);

        int num = 0;
        for (int i = 0; i < bufSize; i++) {
            char c {};
            SbBool ok = inp->get(c);
            if (ok) {
                num++;
                buffer[pbSize + i] = c;
                if (c == '\n') {
                    break;
                }
            }
            else if (num == 0) {
                return EOF;
            }
        }

        setg(buffer + (pbSize - numPutback), buffer + pbSize, buffer + pbSize + num);

        return *gptr();
    }

private:
    static const int pbSize = 4;
    static const int bufSize = 1024;
    char buffer[bufSize + pbSize] {};
    SoInput* inp;
};

class SoInputStream: public std::istream
{
public:
    explicit SoInputStream(SoInput* o)
        : std::istream(nullptr)
        , buf(o)
    {
        this->rdbuf(&buf);
    }
    ~SoInputStream() override = default;
    SoInputStream(const SoInputStream&) = delete;
    SoInputStream(SoInputStream&&) = delete;
    SoInputStream& operator=(const SoInputStream&) = delete;
    SoInputStream& operator=(SoInputStream&&) = delete;

private:
    SoInputStreambuf buf;
};

// Defines all required member variables and functions for a
// single-value field
SO_SFIELD_SOURCE(
    SoSFMeshObject,
    Base::Reference<const Mesh::MeshObject>,
    Base::Reference<const Mesh::MeshObject>
)


void SoSFMeshObject::initClass()
{
    // This macro takes the name of the class and the name of the
    // parent class
    SO_SFIELD_INIT_CLASS(SoSFMeshObject, SoSField);
}

// This reads the value of a field from a file. It returns false if the value could not be read
// successfully.
SbBool SoSFMeshObject::readValue(SoInput* in)
{
    if (!in->isBinary()) {
        SoInputStream str(in);
        MeshCore::MeshKernel kernel;
        MeshCore::MeshInput(kernel).LoadMeshNode(str);
        value = new Mesh::MeshObject(kernel);

        // We need to trigger the notification chain here, as this function
        // can be used on a node in a scene graph in any state -- not only
        // during initial scene graph import.
        this->valueChanged();

        return true;
    }

    int32_t countPt {};
    in->read(countPt);
    std::vector<float> verts(countPt);
    in->readBinaryArray(verts.data(), countPt);

    MeshCore::MeshPointArray rPoints;
    rPoints.reserve(countPt / 3);
    for (auto it = verts.begin(); it != verts.end();) {
        Base::Vector3f p;
        p.x = *it;
        ++it;
        p.y = *it;
        ++it;
        p.z = *it;
        ++it;
        rPoints.push_back(p);
    }

    int32_t countFt {};
    in->read(countFt);
    std::vector<int32_t> faces(countFt);
    in->readBinaryArray(faces.data(), countFt);

    MeshCore::MeshFacetArray rFacets;
    rFacets.reserve(countFt / 3);
    for (auto it = faces.begin(); it != faces.end();) {
        MeshCore::MeshFacet f;
        f._aulPoints[0] = *it;
        ++it;
        f._aulPoints[1] = *it;
        ++it;
        f._aulPoints[2] = *it;
        ++it;
        rFacets.push_back(f);
    }

    MeshCore::MeshKernel kernel;
    kernel.Adopt(rPoints, rFacets, true);
    value = new Mesh::MeshObject(kernel);

    // We need to trigger the notification chain here, as this function
    // can be used on a node in a scene graph in any state -- not only
    // during initial scene graph import.
    this->valueChanged();

    return true;
}

// This writes the value of a field to a file.
void SoSFMeshObject::writeValue(SoOutput* out) const
{
    if (!value) {
        int32_t count = 0;
        out->write(count);
        out->write(count);
        return;
    }

    if (!out->isBinary()) {
        SoOutputStream str(out);
        MeshCore::MeshOutput(value->getKernel()).SaveMeshNode(str);
        return;
    }

    const MeshCore::MeshPointArray& rPoints = value->getKernel().GetPoints();
    std::vector<float> verts;
    verts.reserve(3 * rPoints.size());
    for (const auto& rPoint : rPoints) {
        verts.push_back(rPoint.x);
        verts.push_back(rPoint.y);
        verts.push_back(rPoint.z);
    }

    int32_t countPt = (int32_t)verts.size();
    out->write(countPt);
    out->writeBinaryArray(verts.data(), countPt);

    const MeshCore::MeshFacetArray& rFacets = value->getKernel().GetFacets();
    std::vector<uint32_t> faces;
    faces.reserve(3 * rFacets.size());
    for (const auto& rFacet : rFacets) {
        faces.push_back((int32_t)rFacet._aulPoints[0]);
        faces.push_back((int32_t)rFacet._aulPoints[1]);
        faces.push_back((int32_t)rFacet._aulPoints[2]);
    }

    int32_t countFt = (int32_t)faces.size();
    out->write(countFt);
    out->writeBinaryArray((const int32_t*)faces.data(), countFt);
}

// -------------------------------------------------------

SO_ELEMENT_SOURCE(SoFCMeshObjectElement)

void SoFCMeshObjectElement::initClass()
{
    SO_ELEMENT_INIT_CLASS(SoFCMeshObjectElement, inherited);
}

void SoFCMeshObjectElement::init(SoState* state)
{
    inherited::init(state);
    this->mesh = nullptr;
}

SoFCMeshObjectElement::~SoFCMeshObjectElement() = default;

void SoFCMeshObjectElement::set(SoState* const state, SoNode* const node, const Mesh::MeshObject* const mesh)
{
    SoFCMeshObjectElement* elem = static_cast<SoFCMeshObjectElement*>(
        SoReplacedElement::getElement(state, classStackIndex, node)
    );
    if (elem) {
        elem->mesh = mesh;
        elem->nodeId = node->getNodeId();
    }
}

const Mesh::MeshObject* SoFCMeshObjectElement::get(SoState* const state)
{
    return SoFCMeshObjectElement::getInstance(state)->mesh;
}

const SoFCMeshObjectElement* SoFCMeshObjectElement::getInstance(SoState* state)
{
    return static_cast<const SoFCMeshObjectElement*>(
        SoElement::getConstElement(state, classStackIndex)
    );
}

void SoFCMeshObjectElement::print(FILE* /* file */) const
{}

// -------------------------------------------------------

SO_NODE_SOURCE(SoFCMeshPickNode)

/*!
  Constructor.
*/
SoFCMeshPickNode::SoFCMeshPickNode()
{
    SO_NODE_CONSTRUCTOR(SoFCMeshPickNode);

    SO_NODE_ADD_FIELD(mesh, (nullptr));
}

/*!
  Destructor.
*/
SoFCMeshPickNode::~SoFCMeshPickNode()
{
    delete meshGrid;
}

// Doc from superclass.
void SoFCMeshPickNode::initClass()
{
    SO_NODE_INIT_CLASS(SoFCMeshPickNode, SoNode, "Node");
}

void SoFCMeshPickNode::notify(SoNotList* list)
{
    SoField* f = list->getLastField();
    if (f == &mesh) {
        const Mesh::MeshObject* meshObject = mesh.getValue();
        if (meshObject) {
            MeshCore::MeshAlgorithm alg(meshObject->getKernel());
            float fAvgLen = alg.GetAverageEdgeLength();
            delete meshGrid;
            meshGrid = new MeshCore::MeshFacetGrid(meshObject->getKernel(), 5.0F * fAvgLen);
        }
    }
}

// Doc from superclass.
void SoFCMeshPickNode::rayPick(SoRayPickAction* /*action*/)
{}

// Doc from superclass.
void SoFCMeshPickNode::pick(SoPickAction* action)
{
    SoRayPickAction* raypick = static_cast<SoRayPickAction*>(action);
    raypick->setObjectSpace();

    const Mesh::MeshObject* meshObject = mesh.getValue();
    MeshCore::MeshAlgorithm alg(meshObject->getKernel());

    const SbLine& line = raypick->getLine();
    const SbVec3f& pos = line.getPosition();
    const SbVec3f& dir = line.getDirection();
    Base::Vector3f pt(pos[0], pos[1], pos[2]);
    Base::Vector3f dr(dir[0], dir[1], dir[2]);
    Mesh::FacetIndex index {};
    if (alg.NearestFacetOnRay(pt, dr, *meshGrid, pt, index)) {
        SoPickedPoint* pp = raypick->addIntersection(SbVec3f(pt.x, pt.y, pt.z));
        if (pp) {
            SoFaceDetail* det = new SoFaceDetail();
            det->setFaceIndex(index);
            pp->setDetail(det, this);
        }
    }
}

// -------------------------------------------------------

SO_NODE_SOURCE(SoFCMeshObjectNode)

/*!
  Constructor.
*/
SoFCMeshObjectNode::SoFCMeshObjectNode()
{
    SO_NODE_CONSTRUCTOR(SoFCMeshObjectNode);

    SO_NODE_ADD_FIELD(mesh, (nullptr));
}

/*!
  Destructor.
*/
SoFCMeshObjectNode::~SoFCMeshObjectNode() = default;

// Doc from superclass.
void SoFCMeshObjectNode::initClass()
{
    SO_NODE_INIT_CLASS(SoFCMeshObjectNode, SoNode, "Node");

    SO_ENABLE(SoGetBoundingBoxAction, SoFCMeshObjectElement);
    SO_ENABLE(SoGLRenderAction, SoFCMeshObjectElement);
    SO_ENABLE(SoPickAction, SoFCMeshObjectElement);
    SO_ENABLE(SoCallbackAction, SoFCMeshObjectElement);
    SO_ENABLE(SoGetPrimitiveCountAction, SoFCMeshObjectElement);
}

// Doc from superclass.
void SoFCMeshObjectNode::doAction(SoAction* action)
{
    SoFCMeshObjectElement::set(action->getState(), this, mesh.getValue());
}

// Doc from superclass.
void SoFCMeshObjectNode::GLRender(SoGLRenderAction* action)
{
    SoFCMeshObjectNode::doAction(action);
}

// Doc from superclass.
void SoFCMeshObjectNode::callback(SoCallbackAction* action)
{
    SoFCMeshObjectNode::doAction(action);
}

// Doc from superclass.
void SoFCMeshObjectNode::pick(SoPickAction* action)
{
    SoFCMeshObjectNode::doAction(action);
}

// Doc from superclass.
void SoFCMeshObjectNode::getBoundingBox(SoGetBoundingBoxAction* action)
{
    SoFCMeshObjectNode::doAction(action);
}

// Doc from superclass.
void SoFCMeshObjectNode::getPrimitiveCount(SoGetPrimitiveCountAction* action)
{
    SoFCMeshObjectNode::doAction(action);
}

// Helper functions: draw vertices
inline void glVertex(const MeshCore::MeshPoint& _v)
{
    float v[3];
    v[0] = _v.x;
    v[1] = _v.y;
    v[2] = _v.z;
    glVertex3fv(v);
}

// Helper functions: draw normal
inline void glNormal(const Base::Vector3f& _n)
{
    float n[3];
    n[0] = _n.x;
    n[1] = _n.y;
    n[2] = _n.z;
    glNormal3fv(n);
}

// Helper functions: draw normal
inline void glNormal(float* n)
{
    glNormal3fv(n);
}

// Helper function: convert Vec to SbVec3f
inline SbVec3f sbvec3f(const Base::Vector3f& _v)
{
    return {_v.x, _v.y, _v.z};
}

SO_NODE_SOURCE(SoFCMeshObjectShape)

void SoFCMeshObjectShape::initClass()
{
    SO_NODE_INIT_CLASS(SoFCMeshObjectShape, SoShape, "Shape");
}

SoFCMeshObjectShape::SoFCMeshObjectShape()
    : renderTriangleLimit(std::numeric_limits<unsigned>::max())
{
    SO_NODE_CONSTRUCTOR(SoFCMeshObjectShape);
    setName(SoFCMeshObjectShape::getClassTypeId().getName());
}

SoFCMeshObjectShape::~SoFCMeshObjectShape() = default;

void SoFCMeshObjectShape::notify(SoNotList* node)
{
    inherited::notify(node);
    renderRevision.invalidate();
    renderCcwValid = false;
}

#define RENDER_GLARRAYS

/**
 * Either renders the complete mesh or only a subset of the points.
 */
void SoFCMeshObjectShape::GLRender(SoGLRenderAction* action)
{
    if (shouldGLRender(action)) {
        SoState* state = action->getState();

        // Here we must save the model and projection matrices because
        // we need them later for picking
        glGetFloatv(GL_MODELVIEW_MATRIX, this->modelview);
        glGetFloatv(GL_PROJECTION_MATRIX, this->projection);

        SbBool mode = Gui::SoFCInteractiveElement::get(state);
        const Mesh::MeshObject* mesh = SoFCMeshObjectElement::get(state);
        if (!mesh || mesh->countPoints() == 0) {
            return;
        }

        Binding mbind = this->findMaterialBinding(state);

        SoMaterialBundle mb(action);
        // SoTextureCoordinateBundle tb(action, true, false);

        SbBool needNormals = !mb.isColorOnly() /* || tb.isFunction()*/;
        mb.sendFirst();  // make sure we have the correct material

        SbBool ccw = true;
        if (SoShapeHintsElement::getVertexOrdering(state) == SoShapeHintsElement::CLOCKWISE) {
            ccw = false;
        }

        if (!renderCcwValid || renderCcw != bool(ccw)) {
            renderRevision.invalidate();
            renderCcw = ccw;
            renderCcwValid = true;
        }

        const Gui::MeshInteractionLodPolicy policy(this->renderTriangleLimit);
        const Gui::MeshRenderPresentation presentation
            = policy.presentation(mode, mesh->countFacets(), mesh->countFacets());
        if (!presentation.reducedGeometry) {
#ifdef RENDER_GLARRAYS
            if (render.canRenderGLArray(action)) {
                if (render.needsUpdate(action, renderRevision) || !render.matchMaterial(state)) {
                    render.update();
                    const Gui::MeshRenderData data
                        = buildMeshObjectRenderData(state, mesh, renderRevision, ccw);
                    render.generateGLArrays(action, data);
                }
                if (render.matchMaterial(state)) {
                    render.renderFacesGLArray(action);
                }
                else {
                    drawFaces(mesh, &mb, mbind, needNormals, ccw);
                }
            }
            else {
                drawFaces(mesh, &mb, mbind, needNormals, ccw);
            }
#else
            drawFaces(mesh, &mb, mbind, needNormals, ccw);
#endif
        }
        else {
            drawPoints(mesh, needNormals, ccw, presentation.pointStride);
        }
    }
}

/**
 * Translates current material binding into the internal Binding enum.
 */
SoFCMeshObjectShape::Binding SoFCMeshObjectShape::findMaterialBinding(SoState* const state) const
{
    Binding binding = OVERALL;
    SoMaterialBindingElement::Binding matbind = SoMaterialBindingElement::get(state);

    switch (matbind) {
        case SoMaterialBindingElement::OVERALL:
            binding = OVERALL;
            break;
        case SoMaterialBindingElement::PER_VERTEX:
            binding = PER_VERTEX_INDEXED;
            break;
        case SoMaterialBindingElement::PER_VERTEX_INDEXED:
            binding = PER_VERTEX_INDEXED;
            break;
        case SoMaterialBindingElement::PER_PART:
        case SoMaterialBindingElement::PER_FACE:
            binding = PER_FACE_INDEXED;
            break;
        case SoMaterialBindingElement::PER_PART_INDEXED:
        case SoMaterialBindingElement::PER_FACE_INDEXED:
            binding = PER_FACE_INDEXED;
            break;
        default:
            break;
    }
    return binding;
}

/**
 * Renders the triangles of the complete mesh.
 * FIXME: Do it the same way as Coin did to have only one implementation which is controlled by
 * defines
 * FIXME: Implement using different values of transparency for each vertex or face
 */
void SoFCMeshObjectShape::drawFaces(
    const Mesh::MeshObject* mesh,
    SoMaterialBundle* mb,
    Binding bind,
    SbBool needNormals,
    SbBool ccw
) const
{
    const MeshCore::MeshPointArray& rPoints = mesh->getKernel().GetPoints();
    const MeshCore::MeshFacetArray& rFacets = mesh->getKernel().GetFacets();
    bool perVertex = (mb && bind == PER_VERTEX_INDEXED);
    bool perFace = (mb && bind == PER_FACE_INDEXED);

    if (needNormals) {
        glBegin(GL_TRIANGLES);
        if (ccw) {
            // counterclockwise ordering
            for (auto it = rFacets.begin(); it != rFacets.end(); ++it) {
                const MeshCore::MeshPoint& v0 = rPoints[it->_aulPoints[0]];
                const MeshCore::MeshPoint& v1 = rPoints[it->_aulPoints[1]];
                const MeshCore::MeshPoint& v2 = rPoints[it->_aulPoints[2]];

                // Calculate the normal n = (v1-v0)x(v2-v0)
                float n[3];
                n[0] = (v1.y - v0.y) * (v2.z - v0.z) - (v1.z - v0.z) * (v2.y - v0.y);
                n[1] = (v1.z - v0.z) * (v2.x - v0.x) - (v1.x - v0.x) * (v2.z - v0.z);
                n[2] = (v1.x - v0.x) * (v2.y - v0.y) - (v1.y - v0.y) * (v2.x - v0.x);

                if (perFace) {
                    mb->send(it - rFacets.begin(), true);
                }
                glNormal(n);
                if (perVertex) {
                    mb->send(it->_aulPoints[0], true);
                }
                glVertex(v0);
                if (perVertex) {
                    mb->send(it->_aulPoints[1], true);
                }
                glVertex(v1);
                if (perVertex) {
                    mb->send(it->_aulPoints[2], true);
                }
                glVertex(v2);
            }
        }
        else {
            // clockwise ordering
            for (const auto& rFacet : rFacets) {
                const MeshCore::MeshPoint& v0 = rPoints[rFacet._aulPoints[0]];
                const MeshCore::MeshPoint& v1 = rPoints[rFacet._aulPoints[1]];
                const MeshCore::MeshPoint& v2 = rPoints[rFacet._aulPoints[2]];

                // Calculate the normal n = -(v1-v0)x(v2-v0)
                float n[3];
                n[0] = -((v1.y - v0.y) * (v2.z - v0.z) - (v1.z - v0.z) * (v2.y - v0.y));
                n[1] = -((v1.z - v0.z) * (v2.x - v0.x) - (v1.x - v0.x) * (v2.z - v0.z));
                n[2] = -((v1.x - v0.x) * (v2.y - v0.y) - (v1.y - v0.y) * (v2.x - v0.x));

                glNormal(n);
                glVertex(v0);
                glVertex(v1);
                glVertex(v2);
            }
        }
        glEnd();
    }
    else {
        glBegin(GL_TRIANGLES);
        for (const auto& rFacet : rFacets) {
            glVertex(rPoints[rFacet._aulPoints[0]]);
            glVertex(rPoints[rFacet._aulPoints[1]]);
            glVertex(rPoints[rFacet._aulPoints[2]]);
        }
        glEnd();
    }
}

/**
 * Renders the gravity points of a subset of triangles.
 */
void SoFCMeshObjectShape::drawPoints(
    const Mesh::MeshObject* mesh,
    SbBool needNormals,
    SbBool ccw,
    std::size_t pointStride
) const
{
    const MeshCore::MeshPointArray& rPoints = mesh->getKernel().GetPoints();
    const MeshCore::MeshFacetArray& rFacets = mesh->getKernel().GetFacets();
    const int mod = static_cast<int>(pointStride);

    float size = std::min<float>((float)mod, 3.0F);
    glPointSize(size);

    if (needNormals) {
        glBegin(GL_POINTS);
        int ct = 0;
        if (ccw) {
            for (auto it = rFacets.begin(); it != rFacets.end(); ++it, ct++) {
                if (ct % mod == 0) {
                    const MeshCore::MeshPoint& v0 = rPoints[it->_aulPoints[0]];
                    const MeshCore::MeshPoint& v1 = rPoints[it->_aulPoints[1]];
                    const MeshCore::MeshPoint& v2 = rPoints[it->_aulPoints[2]];

                    // Calculate the normal n = (v1-v0)x(v2-v0)
                    float n[3];
                    n[0] = (v1.y - v0.y) * (v2.z - v0.z) - (v1.z - v0.z) * (v2.y - v0.y);
                    n[1] = (v1.z - v0.z) * (v2.x - v0.x) - (v1.x - v0.x) * (v2.z - v0.z);
                    n[2] = (v1.x - v0.x) * (v2.y - v0.y) - (v1.y - v0.y) * (v2.x - v0.x);

                    // Calculate the center point p=(v0+v1+v2)/3
                    float p[3];
                    p[0] = (v0.x + v1.x + v2.x) / 3.0F;
                    p[1] = (v0.y + v1.y + v2.y) / 3.0F;
                    p[2] = (v0.z + v1.z + v2.z) / 3.0F;
                    glNormal3fv(n);
                    glVertex3fv(p);
                }
            }
        }
        else {
            for (auto it = rFacets.begin(); it != rFacets.end(); ++it, ct++) {
                if (ct % mod == 0) {
                    const MeshCore::MeshPoint& v0 = rPoints[it->_aulPoints[0]];
                    const MeshCore::MeshPoint& v1 = rPoints[it->_aulPoints[1]];
                    const MeshCore::MeshPoint& v2 = rPoints[it->_aulPoints[2]];

                    // Calculate the normal n = -(v1-v0)x(v2-v0)
                    float n[3];
                    n[0] = -((v1.y - v0.y) * (v2.z - v0.z) - (v1.z - v0.z) * (v2.y - v0.y));
                    n[1] = -((v1.z - v0.z) * (v2.x - v0.x) - (v1.x - v0.x) * (v2.z - v0.z));
                    n[2] = -((v1.x - v0.x) * (v2.y - v0.y) - (v1.y - v0.y) * (v2.x - v0.x));

                    // Calculate the center point p=(v0+v1+v2)/3
                    float p[3];
                    p[0] = (v0.x + v1.x + v2.x) / 3.0F;
                    p[1] = (v0.y + v1.y + v2.y) / 3.0F;
                    p[2] = (v0.z + v1.z + v2.z) / 3.0F;
                    glNormal3fv(n);
                    glVertex3fv(p);
                }
            }
        }
        glEnd();
    }
    else {
        glBegin(GL_POINTS);
        int ct = 0;
        for (auto it = rFacets.begin(); it != rFacets.end(); ++it, ct++) {
            if (ct % mod == 0) {
                const MeshCore::MeshPoint& v0 = rPoints[it->_aulPoints[0]];
                const MeshCore::MeshPoint& v1 = rPoints[it->_aulPoints[1]];
                const MeshCore::MeshPoint& v2 = rPoints[it->_aulPoints[2]];
                // Calculate the center point p=(v0+v1+v2)/3
                float p[3];
                p[0] = (v0.x + v1.x + v2.x) / 3.0F;
                p[1] = (v0.y + v1.y + v2.y) / 3.0F;
                p[2] = (v0.z + v1.z + v2.z) / 3.0F;
                glVertex3fv(p);
            }
        }
        glEnd();
    }
}

void SoFCMeshObjectShape::doAction(SoAction* action)
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
        sa.setType(SoFCMeshObjectNode::getClassTypeId(), 1);
        sa.apply(node);
        SoPath* path = sa.getPath();
        if (!path) {
            return;
        }

        // make sure we got the node we wanted
        SoNode* coords = path->getNodeFromTail(0);
        if (!(coords && coords->getTypeId().isDerivedFrom(SoFCMeshObjectNode::getClassTypeId()))) {
            return;
        }
        const Mesh::MeshObject* mesh = static_cast<SoFCMeshObjectNode*>(coords)->mesh.getValue();
        startSelection(action, mesh);
        renderSelectionGeometry(mesh);
        stopSelection(action, mesh);
    }

    inherited::doAction(action);
}

void SoFCMeshObjectShape::startSelection(SoAction* action, const Mesh::MeshObject* mesh)
{
    Gui::SoGLSelectAction* doaction = static_cast<Gui::SoGLSelectAction*>(action);
    const SbViewportRegion& vp = doaction->getViewportRegion();
    int x = vp.getViewportOriginPixels()[0];
    int y = vp.getViewportOriginPixels()[1];
    int w = vp.getViewportSizePixels()[0];
    int h = vp.getViewportSizePixels()[1];

    unsigned int bufSize = 5 * mesh->countFacets();  // make the buffer big enough
    this->selectBuf = new GLuint[bufSize];

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
    glMultMatrixf(/*mp*/ this->projection);
    glMatrixMode(GL_MODELVIEW);
    glPushMatrix();
    glLoadMatrixf(this->modelview);
}

void SoFCMeshObjectShape::stopSelection(SoAction* action, const Mesh::MeshObject* mesh)
{
    // restoring the original projection matrix
    glPopMatrix();
    glMatrixMode(GL_PROJECTION);
    glPopMatrix();
    glMatrixMode(GL_MODELVIEW);
    glFlush();

    // returning to normal rendering mode
    GLint hits = glRenderMode(GL_RENDER);

    unsigned int bufSize = 5 * mesh->countFacets();
    std::vector<std::pair<double, unsigned int>> hit;
    GLuint index = 0;
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

void SoFCMeshObjectShape::renderSelectionGeometry(const Mesh::MeshObject* mesh)
{
    int fcnt = 0;
    const MeshCore::MeshPointArray& rPoints = mesh->getKernel().GetPoints();
    const MeshCore::MeshFacetArray& rFacets = mesh->getKernel().GetFacets();
    MeshCore::MeshFacetArray::_TConstIterator it_end = rFacets.end();
    for (MeshCore::MeshFacetArray::_TConstIterator it = rFacets.begin(); it != it_end; ++it) {
        const MeshCore::MeshPoint& v0 = rPoints[it->_aulPoints[0]];
        const MeshCore::MeshPoint& v1 = rPoints[it->_aulPoints[1]];
        const MeshCore::MeshPoint& v2 = rPoints[it->_aulPoints[2]];
        glLoadName(fcnt);
        glBegin(GL_TRIANGLES);
        glVertex(v0);
        glVertex(v1);
        glVertex(v2);
        glEnd();
        fcnt++;
    }
}


/**
 * Calculates picked point based on primitives generated by subclasses.
 */
void SoFCMeshObjectShape::rayPick(SoRayPickAction* action)
{
    inherited::rayPick(action);
}

/** Sets the point indices, the geometric points and the normal for each triangle.
 * If the number of triangles exceeds \a renderTriangleLimit then only a triangulation of
 * a rough model is filled in instead. This is due to performance issues.
 * \see createTriangleDetail().
 */
void SoFCMeshObjectShape::generatePrimitives(SoAction* action)
{
    SoState* state = action->getState();
    const Mesh::MeshObject* mesh = SoFCMeshObjectElement::get(state);
    if (!mesh) {
        return;
    }
    const MeshCore::MeshPointArray& rPoints = mesh->getKernel().GetPoints();
    const MeshCore::MeshFacetArray& rFacets = mesh->getKernel().GetFacets();
    if (rPoints.size() < 3) {
        return;
    }
    if (rFacets.empty()) {
        return;
    }

    // get material binding
    Binding mbind = this->findMaterialBinding(state);

    // Create the information when moving over or picking into the scene
    SoPrimitiveVertex vertex;
    SoPointDetail pointDetail;
    SoFaceDetail faceDetail;

    vertex.setDetail(&pointDetail);

    beginShape(action, TRIANGLES, &faceDetail);
    try {
        for (const auto& rFacet : rFacets) {
            const MeshCore::MeshPoint& v0 = rPoints[rFacet._aulPoints[0]];
            const MeshCore::MeshPoint& v1 = rPoints[rFacet._aulPoints[1]];
            const MeshCore::MeshPoint& v2 = rPoints[rFacet._aulPoints[2]];

            // Calculate the normal n = (v1-v0)x(v2-v0)
            SbVec3f n;
            n[0] = (v1.y - v0.y) * (v2.z - v0.z) - (v1.z - v0.z) * (v2.y - v0.y);
            n[1] = (v1.z - v0.z) * (v2.x - v0.x) - (v1.x - v0.x) * (v2.z - v0.z);
            n[2] = (v1.x - v0.x) * (v2.y - v0.y) - (v1.y - v0.y) * (v2.x - v0.x);

            // Set the normal
            vertex.setNormal(n);

            // Vertex 0
            if (mbind == PER_VERTEX_INDEXED || mbind == PER_FACE_INDEXED) {
                pointDetail.setMaterialIndex(rFacet._aulPoints[0]);
                vertex.setMaterialIndex(rFacet._aulPoints[0]);
            }
            pointDetail.setCoordinateIndex(rFacet._aulPoints[0]);
            vertex.setPoint(sbvec3f(v0));
            shapeVertex(&vertex);

            // Vertex 1
            if (mbind == PER_VERTEX_INDEXED || mbind == PER_FACE_INDEXED) {
                pointDetail.setMaterialIndex(rFacet._aulPoints[1]);
                vertex.setMaterialIndex(rFacet._aulPoints[1]);
            }
            pointDetail.setCoordinateIndex(rFacet._aulPoints[1]);
            vertex.setPoint(sbvec3f(v1));
            shapeVertex(&vertex);

            // Vertex 2
            if (mbind == PER_VERTEX_INDEXED || mbind == PER_FACE_INDEXED) {
                pointDetail.setMaterialIndex(rFacet._aulPoints[2]);
                vertex.setMaterialIndex(rFacet._aulPoints[2]);
            }
            pointDetail.setCoordinateIndex(rFacet._aulPoints[2]);
            vertex.setPoint(sbvec3f(v2));
            shapeVertex(&vertex);

            // Increment for the next face
            faceDetail.incFaceIndex();
        }
    }
    catch (const Base::MemoryException&) {
        Base::Console().log("Not enough memory to generate primitives\n");
    }

    endShape();
}

/**
 * If the number of triangles exceeds \a renderTriangleLimit 0 is returned.
 * This means that the client programmer needs to implement itself to get the
 * index of the picked triangle. If the number of triangles doesn't exceed
 * \a renderTriangleLimit SoShape::createTriangleDetail() gets called.
 * Against the default OpenInventor implementation which returns 0 as well
 * Coin3d fills in the point and face indices.
 */
SoDetail* SoFCMeshObjectShape::createTriangleDetail(
    SoRayPickAction* action,
    const SoPrimitiveVertex* v1,
    const SoPrimitiveVertex* v2,
    const SoPrimitiveVertex* v3,
    SoPickedPoint* pp
)
{
    SoDetail* detail = inherited::createTriangleDetail(action, v1, v2, v3, pp);
    return detail;
}

/**
 * Sets the bounding box of the mesh to \a box and its center to \a center.
 */
void SoFCMeshObjectShape::computeBBox(SoAction* action, SbBox3f& box, SbVec3f& center)
{
    SoState* state = action->getState();
    const Mesh::MeshObject* mesh = SoFCMeshObjectElement::get(state);
    if (mesh && mesh->countPoints() > 0) {
        Base::BoundBox3f cBox = mesh->getKernel().GetBoundBox();
        box.setBounds(
            SbVec3f(cBox.MinX, cBox.MinY, cBox.MinZ),
            SbVec3f(cBox.MaxX, cBox.MaxY, cBox.MaxZ)
        );
        Base::Vector3f mid = cBox.GetCenter();
        center.setValue(mid.x, mid.y, mid.z);
    }
    else {
        box.setBounds(SbVec3f(0, 0, 0), SbVec3f(0, 0, 0));
        center.setValue(0.0F, 0.0F, 0.0F);
    }
}

/**
 * Adds the number of the triangles to the \a SoGetPrimitiveCountAction.
 */
void SoFCMeshObjectShape::getPrimitiveCount(SoGetPrimitiveCountAction* action)
{
    if (!this->shouldPrimitiveCount(action)) {
        return;
    }
    SoState* state = action->getState();
    const Mesh::MeshObject* mesh = SoFCMeshObjectElement::get(state);
    action->addNumTriangles(mesh->countFacets());
    action->addNumPoints(mesh->countPoints());
}

/**
 * Counts the number of triangles. If a mesh is not set yet it returns 0.
 */
unsigned int SoFCMeshObjectShape::countTriangles(SoAction* action) const
{
    SoState* state = action->getState();
    const Mesh::MeshObject* mesh = SoFCMeshObjectElement::get(state);
    return (unsigned int)mesh->countFacets();
}

// -------------------------------------------------------
