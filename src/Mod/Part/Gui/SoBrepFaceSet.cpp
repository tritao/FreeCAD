// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2011 Werner Mayer <wmayer[at]users.sourceforge.net>     *
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

#include <algorithm>
#include <limits>
#include <set>
#include <vector>

#include <Inventor/SoPickedPoint.h>
#include <Inventor/SoPrimitiveVertex.h>
#include <Inventor/actions/SoGetBoundingBoxAction.h>
#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/actions/SoRayPickAction.h>
#include <Inventor/bundles/SoMaterialBundle.h>
#include <Inventor/details/SoFaceDetail.h>
#include <Inventor/elements/SoCoordinateElement.h>
#include <Inventor/elements/SoDepthBufferElement.h>
#include <Inventor/elements/SoLazyElement.h>
#include <Inventor/elements/SoMaterialBindingElement.h>
#include <Inventor/elements/SoNormalBindingElement.h>
#include <Inventor/elements/SoOverrideElement.h>
#include <Inventor/elements/SoShapeStyleElement.h>
#include <Inventor/elements/SoTextureEnabledElement.h>
#include <Inventor/errors/SoDebugError.h>
#include <Inventor/misc/SoState.h>

#include <Base/Profiler.h>

#include <Gui/SoFCInteractiveElement.h>
#include <Gui/Selection/Selection.h>
#include <Gui/Selection/SoFCSelectionAction.h>
#include <Gui/Selection/SoFCUnifiedSelection.h>
#include <Gui/Inventor/So3DAnnotation.h>

#include "SoBrepFaceSet.h"
#include "ViewProviderExt.h"

using namespace PartGui;

SO_NODE_SOURCE(SoBrepFaceSet)

namespace
{

static void buildOverlayCoordIndex(
    std::vector<int32_t>& out,
    const int32_t* coordIndex,
    int coordIndexCount,
    const int32_t* partTriCounts,
    int partCount,
    const std::set<int>& parts,
    bool selectAll
)
{
    out.clear();
    if (!coordIndex || coordIndexCount <= 0) {
        return;
    }
    if (selectAll) {
        out.insert(out.end(), coordIndex, coordIndex + coordIndexCount);
        return;
    }
    if (!partTriCounts || partCount <= 0 || parts.empty()) {
        return;
    }

    std::vector<int32_t> face;
    face.reserve(8);

    int pos = 0;
    for (int part = 0; part < partCount && pos < coordIndexCount; ++part) {
        const bool include = (parts.find(part) != parts.end());
        const int tris = partTriCounts[part];
        for (int t = 0; t < tris && pos < coordIndexCount; ++t) {
            // Skip any stray delimiters.
            while (pos < coordIndexCount && coordIndex[pos] < 0) {
                pos++;
            }
            face.clear();
            while (pos < coordIndexCount && coordIndex[pos] >= 0) {
                face.push_back(coordIndex[pos]);
                pos++;
            }
            if (pos < coordIndexCount && coordIndex[pos] < 0) {
                // Consume one delimiter.
                pos++;
            }
            if (include && face.size() >= 3) {
                out.insert(out.end(), face.begin(), face.end());
                out.push_back(-1);
            }
        }
    }
}

static void renderOverlayFaces(
    SoGLRenderAction* action,
    SoIndexedFaceSet* faceSet,
    const std::vector<int32_t>& coordIndex,
    const SbColor& color,
    bool onTop
)
{
    if (!action || !faceSet || coordIndex.empty()) {
        return;
    }

    auto state = action->getState();
    state->push();

    SoLazyElement::setLightModel(state, SoLazyElement::BASE_COLOR);
    SoTextureEnabledElement::set(state, faceSet, false);
    SoMaterialBindingElement::set(state, SoMaterialBindingElement::OVERALL);
    SoOverrideElement::setMaterialBindingOverride(state, faceSet, true);

    if (onTop) {
        SoDepthBufferElement::set(
            state,
            FALSE,
            FALSE,
            SoDepthBufferElement::ALWAYS,
            SbVec2f(0.0f, 1.0f)
        );
        SoShapeStyleElement::setTransparencyType(state, SoGLRenderAction::BLEND);
        SoLazyElement::setTransparencyType(state, SoGLRenderAction::BLEND);
    }
    else {
        SoDepthBufferElement::set(
            state,
            TRUE,
            FALSE,
            SoDepthBufferElement::LEQUAL,
            SbVec2f(0.0f, 1.0f)
        );
    }

    SoLazyElement::setEmissive(state, &color);
    const uint32_t packed = color.getPackedValue(0.0f);
    SoLazyElement::setPacked(state, faceSet, 1, &packed, false);

    faceSet->coordIndex.setValues(0, static_cast<int32_t>(coordIndex.size()), coordIndex.data());
    faceSet->GLRender(action);

    state->pop();
}

}  // namespace

void SoBrepFaceSet::initClass()
{
    SO_NODE_INIT_CLASS(SoBrepFaceSet, SoIndexedFaceSet, "IndexedFaceSet");
}

SoBrepFaceSet::SoBrepFaceSet()
{
    SO_NODE_CONSTRUCTOR(SoBrepFaceSet);
    SO_NODE_ADD_FIELD(partIndex, (-1));
    SO_NODE_ADD_FIELD(highlightPartIndex, (-1));
    SO_NODE_ADD_FIELD(selectionPartIndex, (0));
    SO_NODE_ADD_FIELD(highlightColor, (SbColor(1.0f, 0.0f, 0.0f)));
    SO_NODE_ADD_FIELD(selectionColor, (SbColor(0.0f, 0.6f, 0.0f)));

    selectionPartIndex.setNum(0);

    selContext = std::make_shared<SelContext>();
    selContext2 = std::make_shared<SelContext>();
    packedColor = 0;

    overlayFaceSet = new SoIndexedFaceSet;
    overlayFaceSet->ref();
}

SoBrepFaceSet::~SoBrepFaceSet()
{
    if (overlayFaceSet) {
        overlayFaceSet->unref();
        overlayFaceSet = nullptr;
    }
}

void SoBrepFaceSet::doAction(SoAction* action)
{
    if (action->getTypeId() == Gui::SoHighlightElementAction::getClassTypeId()) {
        auto* hlaction = static_cast<Gui::SoHighlightElementAction*>(action);
        selCounter.checkAction(hlaction);
        if (!hlaction->isHighlighted()) {
            SelContextPtr ctx = Gui::SoFCSelectionRoot::getActionContext(action, this, selContext, false);
            if (ctx) {
                ctx->highlightIndex = -1;
                touch();
            }
            if (viewProvider) {
                viewProvider->setFaceHighlightActive(false);
            }
            return;
        }

        const SoDetail* detail = hlaction->getElement();
        if (!detail) {
            SelContextPtr ctx = Gui::SoFCSelectionRoot::getActionContext(action, this, selContext);
            ctx->highlightIndex = std::numeric_limits<int>::max();
            ctx->highlightColor = hlaction->getColor();
            touch();
        }
        else {
            if (!detail->isOfType(SoFaceDetail::getClassTypeId())) {
                SelContextPtr ctx = Gui::SoFCSelectionRoot::getActionContext(action, this, selContext, false);
                if (ctx) {
                    ctx->highlightIndex = -1;
                    touch();
                }
                if (viewProvider) {
                    viewProvider->setFaceHighlightActive(false);
                }
            }
            else {
                int index = static_cast<const SoFaceDetail*>(detail)->getPartIndex();
                SelContextPtr ctx = Gui::SoFCSelectionRoot::getActionContext(action, this, selContext);
                ctx->highlightIndex = index;
                ctx->highlightColor = hlaction->getColor();
                touch();
            }
        }
        return;
    }
    else if (action->getTypeId() == Gui::SoSelectionElementAction::getClassTypeId()) {
        auto* selaction = static_cast<Gui::SoSelectionElementAction*>(action);
        switch (selaction->getType()) {
            case Gui::SoSelectionElementAction::All: {
                SelContextPtr ctx
                    = Gui::SoFCSelectionRoot::getActionContext<SelContext>(action, this, selContext);
                selCounter.checkAction(selaction, ctx);
                ctx->selectionIndex.clear();
                ctx->selectionIndex.insert(-1);
                ctx->selectionColor = selaction->getColor();
                touch();
                break;
            }
            case Gui::SoSelectionElementAction::None: {
                SelContextPtr ctx = Gui::SoFCSelectionRoot::getActionContext(action, this, selContext, false);
                if (ctx && (!ctx->selectionIndex.empty())) {
                    ctx->selectionIndex.clear();
                    touch();
                }
                break;
            }
            case Gui::SoSelectionElementAction::Append:
            case Gui::SoSelectionElementAction::Remove: {
                const SoDetail* detail = selaction->getElement();
                if (!detail || !detail->isOfType(SoFaceDetail::getClassTypeId())) {
                    if (selaction->isSecondary()) {
                        auto ctx = Gui::SoFCSelectionRoot::getActionContext<SelContext>(action, this);
                        selCounter.checkAction(selaction, ctx);
                        touch();
                    }
                    return;
                }
                int index = static_cast<const SoFaceDetail*>(detail)->getPartIndex();
                if (selaction->getType() == Gui::SoSelectionElementAction::Append) {
                    auto ctx = Gui::SoFCSelectionRoot::getActionContext(action, this, selContext);
                    selCounter.checkAction(selaction, ctx);
                    ctx->selectionColor = selaction->getColor();
                    if (ctx->isSelectAll()) {
                        ctx->selectionIndex.clear();
                    }
                    if (ctx->selectionIndex.insert(index).second) {
                        touch();
                    }
                }
                else {
                    auto ctx = Gui::SoFCSelectionRoot::getActionContext(action, this, selContext, false);
                    if (ctx && ctx->removeIndex(index)) {
                        touch();
                    }
                }
                break;
            }
            default:
                break;
        }
        return;
    }
    else if (action->getTypeId() == Gui::SoVRMLAction::getClassTypeId()) {
        // Keep materialIndex in sync when using PER_PART binding with one color per part.
        SoState* state = action->getState();
        Binding mbind = this->findMaterialBinding(state);
        if (mbind == PER_PART) {
            const SoLazyElement* mat = SoLazyElement::getInstance(state);
            const int numParts = partIndex.getNum();
            if (mat && mat->getNumDiffuse() == numParts) {
                int count = 0;
                const int32_t* indices = this->partIndex.getValues(0);
                for (int i = 0; i < numParts; i++) {
                    count += indices[i];
                }
                this->materialIndex.setNum(count);
                int32_t* matind = this->materialIndex.startEditing();
                int32_t k = 0;
                for (int i = 0; i < numParts; i++) {
                    for (int j = 0; j < indices[i]; j++) {
                        matind[k++] = i;
                    }
                }
                this->materialIndex.finishEditing();
            }
        }
    }

    inherited::doAction(action);
}

void SoBrepFaceSet::renderHighlight(SoGLRenderAction* action, SelContextPtr ctx)
{
    if (!ctx || ctx->highlightIndex < 0) {
        return;
    }

    const int32_t* partCounts = this->partIndex.getValues(0);
    const int partCount = this->partIndex.getNum();
    const int32_t* ci = this->coordIndex.getValues(0);
    const int ciCount = this->coordIndex.getNum();

    const int id = ctx->highlightIndex;
    if (id != std::numeric_limits<int>::max() && (id < 0 || id >= partCount)) {
        SoDebugError::postWarning("SoBrepFaceSet::renderHighlight", "highlightIndex out of range");
        return;
    }

    std::set<int> parts;
    const bool selectAll = (id == std::numeric_limits<int>::max());
    if (!selectAll) {
        parts.insert(id);
    }
    buildOverlayCoordIndex(overlayCoordIndex, ci, ciCount, partCounts, partCount, parts, selectAll);

    const bool onTop = Gui::Selection().isClarifySelectionActive()
        && Gui::SoDelayedAnnotationsElement::isProcessingDelayedPaths;

    renderOverlayFaces(action, overlayFaceSet, overlayCoordIndex, ctx->highlightColor, onTop);
}

void SoBrepFaceSet::renderSelection(SoGLRenderAction* action, SelContextPtr ctx, bool /*push*/)
{
    if (!ctx || ctx->selectionIndex.empty()) {
        return;
    }

    const int32_t* partCounts = this->partIndex.getValues(0);
    const int partCount = this->partIndex.getNum();
    const int32_t* ci = this->coordIndex.getValues(0);
    const int ciCount = this->coordIndex.getNum();

    if (ctx->isSelectAll()) {
        std::set<int> dummy;
        buildOverlayCoordIndex(overlayCoordIndex, ci, ciCount, partCounts, partCount, dummy, true);
        renderOverlayFaces(action, overlayFaceSet, overlayCoordIndex, ctx->selectionColor, false);
        return;
    }

    std::set<int> parts;
    for (int idx : ctx->selectionIndex) {
        if (idx >= 0 && idx < partCount) {
            parts.insert(idx);
        }
    }
    if (parts.empty()) {
        SoDebugError::postWarning("SoBrepFaceSet::renderSelection", "selectionIndex out of range");
        return;
    }

    buildOverlayCoordIndex(overlayCoordIndex, ci, ciCount, partCounts, partCount, parts, false);
    renderOverlayFaces(action, overlayFaceSet, overlayCoordIndex, ctx->selectionColor, false);
}

bool SoBrepFaceSet::overrideMaterialBinding(SoGLRenderAction* /*action*/, SelContextPtr /*ctx*/, SelContextPtr /*ctx2*/)
{
    // The legacy implementation relied on raw OpenGL state; the current rendering path uses
    // explicit overlay passes (renderSelection/renderHighlight) instead.
    return false;
}

void SoBrepFaceSet::GLRender(SoGLRenderAction* action)
{
    ZoneScoped;

    if (this->coordIndex.getNum() < 3) {
        return;
    }

    SelContextPtr ctx2;
    SelContextPtr ctx = Gui::SoFCSelectionRoot::getRenderContext(this, selContext, ctx2);
    const bool hasOverlayFields = (highlightPartIndex.getValue() >= 0) || (selectionPartIndex.getNum() > 0);
    if (!hasOverlayFields && ctx2 && ctx2->selectionIndex.empty()) {
        return;
    }
    if (selContext2->checkGlobal(ctx)) {
        ctx = selContext2;
    }
    if (ctx && (ctx->selectionIndex.empty() && ctx->highlightIndex < 0)) {
        ctx.reset();
    }

    auto state = action->getState();
    selCounter.checkRenderCache(state);

    const bool hasContextHighlight = ctx && ctx->isHighlighted() && !ctx->isHighlightAll()
        && ctx->highlightIndex >= 0 && ctx->highlightIndex < partIndex.getNum();

    // Clarify selection: render highlight as delayed annotation on top.
    if (Gui::Selection().isClarifySelectionActive() && hasContextHighlight) {
        if (!Gui::SoDelayedAnnotationsElement::isProcessingDelayedPaths) {
            if (viewProvider) {
                viewProvider->setFaceHighlightActive(true);
            }
            const SoPath* currentPath = action->getCurPath();
            Gui::SoDelayedAnnotationsElement::addDelayedPath(state, currentPath->copy(), 100);
            return;
        }
        inherited::GLRender(action);
        renderHighlight(action, ctx);
        return;
    }

    SoMaterialBundle mb(action);
    mb.sendFirst();
    if (!this->shouldGLRender(action)) {
        return;
    }

    inherited::GLRender(action);

    // Selection first, highlight on top.
    if (ctx2 && !ctx2->selectionIndex.empty()) {
        renderSelection(action, ctx2, false);
    }
    if (ctx && !ctx->selectionIndex.empty()) {
        renderSelection(action, ctx);
    }
    renderHighlight(action, ctx);

    // Optional overlay rendering for deterministic tests (and programmatic usage).
    const int selNum = selectionPartIndex.getNum();
    if (selNum > 0) {
        SelContextPtr octx = std::make_shared<SelContext>();
        octx->selectionColor = selectionColor.getValue();
        const int32_t* vals = selectionPartIndex.getValues(0);
        for (int i = 0; i < selNum; i++) {
            octx->selectionIndex.insert(vals[i]);
        }
        renderSelection(action, octx);
    }
    const int hl = highlightPartIndex.getValue();
    if (hl >= 0) {
        SelContextPtr octx = std::make_shared<SelContext>();
        octx->highlightIndex = hl;
        octx->highlightColor = highlightColor.getValue();
        renderHighlight(action, octx);
    }
}

void SoBrepFaceSet::GLRenderBelowPath(SoGLRenderAction* action)
{
    inherited::GLRenderBelowPath(action);
}

void SoBrepFaceSet::generatePrimitives(SoAction* action)
{
    inherited::generatePrimitives(action);
}

void SoBrepFaceSet::getBoundingBox(SoGetBoundingBoxAction* action)
{
    inherited::getBoundingBox(action);
}

SoDetail* SoBrepFaceSet::createTriangleDetail(
    SoRayPickAction* action,
    const SoPrimitiveVertex* v1,
    const SoPrimitiveVertex* v2,
    const SoPrimitiveVertex* v3,
    SoPickedPoint* pp
)
{
    SoDetail* detail = inherited::createTriangleDetail(action, v1, v2, v3, pp);
    const int32_t* indices = this->partIndex.getValues(0);
    const int num = this->partIndex.getNum();
    if (indices) {
        auto* face_detail = static_cast<SoFaceDetail*>(detail);
        const int index = face_detail->getFaceIndex();
        int count = 0;
        for (int i = 0; i < num; i++) {
            count += indices[i];
            if (index < count) {
                face_detail->setPartIndex(i);
                break;
            }
        }
    }
    return detail;
}

SoBrepFaceSet::Binding SoBrepFaceSet::findMaterialBinding(SoState* const state) const
{
    Binding binding = OVERALL;
    const auto matbind = SoMaterialBindingElement::get(state);

    switch (matbind) {
        case SoMaterialBindingElement::OVERALL:
            binding = OVERALL;
            break;
        case SoMaterialBindingElement::PER_VERTEX:
            binding = PER_VERTEX;
            break;
        case SoMaterialBindingElement::PER_VERTEX_INDEXED:
            binding = PER_VERTEX_INDEXED;
            break;
        case SoMaterialBindingElement::PER_PART:
            binding = PER_PART;
            break;
        case SoMaterialBindingElement::PER_FACE:
            binding = PER_FACE;
            break;
        case SoMaterialBindingElement::PER_PART_INDEXED:
            binding = PER_PART_INDEXED;
            break;
        case SoMaterialBindingElement::PER_FACE_INDEXED:
            binding = PER_FACE_INDEXED;
            break;
        default:
            break;
    }
    return binding;
}

SoBrepFaceSet::Binding SoBrepFaceSet::findNormalBinding(SoState* const state) const
{
    Binding binding = PER_VERTEX_INDEXED;
    const auto normbind = static_cast<SoNormalBindingElement::Binding>(SoNormalBindingElement::get(state));

    switch (normbind) {
        case SoNormalBindingElement::OVERALL:
            binding = OVERALL;
            break;
        case SoNormalBindingElement::PER_VERTEX:
            binding = PER_VERTEX;
            break;
        case SoNormalBindingElement::PER_VERTEX_INDEXED:
            binding = PER_VERTEX_INDEXED;
            break;
        case SoNormalBindingElement::PER_PART:
            binding = PER_PART;
            break;
        case SoNormalBindingElement::PER_FACE:
            binding = PER_FACE;
            break;
        case SoNormalBindingElement::PER_PART_INDEXED:
            binding = PER_PART_INDEXED;
            break;
        case SoNormalBindingElement::PER_FACE_INDEXED:
            binding = PER_FACE_INDEXED;
            break;
        default:
            break;
    }
    return binding;
}
