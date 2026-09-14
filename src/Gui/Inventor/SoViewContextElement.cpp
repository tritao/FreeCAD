// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "SoViewContextElement.h"

#include <Inventor/actions/SoCallbackAction.h>
#include <Inventor/actions/SoGetBoundingBoxAction.h>
#include <Inventor/actions/SoGetMatrixAction.h>
#include <Inventor/actions/SoGetPrimitiveCountAction.h>
#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/actions/SoHandleEventAction.h>
#include <Inventor/actions/SoPickAction.h>
#include <Inventor/actions/SoRayPickAction.h>
#include <Inventor/elements/SoSwitchElement.h>
#include <Inventor/misc/SoChildList.h>

#include "../ViewContext.h"
#include "../ViewProvider.h"
#include "../ViewProviderDocumentObject.h"

using namespace Gui;

SO_ELEMENT_SOURCE(SoViewContextElement)
SO_NODE_SOURCE(SoViewContextSwitch)
SO_NODE_SOURCE(SoViewContextGate)

void SoViewContextElement::initClass()
{
    SO_ELEMENT_INIT_CLASS(SoViewContextElement, inherited);
    SO_ENABLE(SoCallbackAction, SoViewContextElement);
    SO_ENABLE(SoGetBoundingBoxAction, SoViewContextElement);
    SO_ENABLE(SoGetMatrixAction, SoViewContextElement);
    SO_ENABLE(SoGetPrimitiveCountAction, SoViewContextElement);
    SO_ENABLE(SoGLRenderAction, SoViewContextElement);
    SO_ENABLE(SoHandleEventAction, SoViewContextElement);
    SO_ENABLE(SoPickAction, SoViewContextElement);
    SO_ENABLE(SoRayPickAction, SoViewContextElement);
}

void SoViewContextElement::init(SoState* state)
{
    inherited::init(state);
    context = nullptr;
}

SoViewContextElement::~SoViewContextElement() = default;

SbBool SoViewContextElement::matches(const SoElement* element) const
{
    return context == static_cast<const SoViewContextElement*>(element)->context;
}

SoElement* SoViewContextElement::copyMatchInfo() const
{
    auto* copy = static_cast<SoViewContextElement*>(getTypeId().createInstance());
    copy->context = context;
    return copy;
}

void SoViewContextElement::set(SoState* state, const ViewContext* context)
{
    if (!state->isElementEnabled(classStackIndex)) {
        return;
    }
    auto* element = static_cast<SoViewContextElement*>(SoElement::getElement(state, classStackIndex));
    element->context = context;
}

const ViewContext* SoViewContextElement::get(SoState* state)
{
    if (!state->isElementEnabled(classStackIndex)) {
        return nullptr;
    }
    const auto* element = static_cast<const SoViewContextElement*>(
        SoElement::getConstElement(state, classStackIndex)
    );
    return element->context;
}

void SoViewContextSwitch::initClass()
{
    SO_NODE_INIT_CLASS(SoViewContextSwitch, SoSwitch, "Switch");
}

SoViewContextSwitch::SoViewContextSwitch(ViewProvider* provider)
    : provider(provider)
{
    SO_NODE_CONSTRUCTOR(SoViewContextSwitch);
}

SoViewContextSwitch::~SoViewContextSwitch() = default;

bool SoViewContextSwitch::forceVisible(SoAction* action) const
{
    if (whichChild.isIgnored() || whichChild.getValue() != SO_SWITCH_NONE) {
        return false;
    }
    const auto* documentProvider = dynamic_cast<ViewProviderDocumentObject*>(provider);
    const auto* context = SoViewContextElement::get(action->getState());
    return context && documentProvider
        && context->visibility(documentProvider->getObject()) == ViewContext::Visibility::Visible;
}

void SoViewContextSwitch::traverseChild(SoAction* action, int child)
{
    if (child < 0 || child >= getNumChildren()) {
        return;
    }
    SoSwitchElement::set(action->getState(), child);
    int count = 0;
    const int* indices = nullptr;
    const auto pathCode = action->getPathCode(count, indices);
    if (pathCode == SoAction::IN_PATH) {
        for (int index = 0; index < count; ++index) {
            if (indices[index] == child) {
                getChildren()->traverse(action, child);
                break;
            }
        }
    }
    else {
        getChildren()->traverse(action, child);
    }
}

void SoViewContextSwitch::doAction(SoAction* action)
{
    if (forceVisible(action)) {
        traverseChild(action, provider->getDefaultMode());
    }
    else {
        inherited::doAction(action);
    }
}

void SoViewContextSwitch::callback(SoCallbackAction* action)
{
    doAction(action);
}

void SoViewContextSwitch::getBoundingBox(SoGetBoundingBoxAction* action)
{
    doAction(action);
}

void SoViewContextSwitch::getMatrix(SoGetMatrixAction* action)
{
    switch (action->getCurPathCode()) {
        case SoAction::OFF_PATH:
        case SoAction::IN_PATH:
            doAction(action);
            break;
        default:
            break;
    }
}

void SoViewContextSwitch::getPrimitiveCount(SoGetPrimitiveCountAction* action)
{
    doAction(action);
}

void SoViewContextSwitch::GLRender(SoGLRenderAction* action)
{
    doAction(action);
}

void SoViewContextSwitch::handleEvent(SoHandleEventAction* action)
{
    doAction(action);
}

void SoViewContextSwitch::pick(SoPickAction* action)
{
    doAction(action);
}

void SoViewContextGate::initClass()
{
    SO_NODE_INIT_CLASS(SoViewContextGate, SoSeparator, "Separator");
}

SoViewContextGate::SoViewContextGate(ViewProvider* provider, SoNode* child, const ViewContext* context)
    : context(context)
{
    SO_NODE_CONSTRUCTOR(SoViewContextGate);
    if (const auto* documentProvider = dynamic_cast<ViewProviderDocumentObject*>(provider)) {
        object = documentProvider->getObject();
    }
    if (child) {
        addChild(child);
    }
}

SoViewContextGate::~SoViewContextGate() = default;

bool SoViewContextGate::shouldTraverse(SoAction* action) const
{
    if (context) {
        SoViewContextElement::set(action->getState(), context);
    }
    const auto* activeContext = SoViewContextElement::get(action->getState());
    return !activeContext || !object
        || activeContext->visibility(object) != ViewContext::Visibility::Hidden;
}

void SoViewContextGate::callback(SoCallbackAction* action)
{
    if (shouldTraverse(action)) {
        inherited::callback(action);
    }
}

void SoViewContextGate::getBoundingBox(SoGetBoundingBoxAction* action)
{
    if (shouldTraverse(action)) {
        inherited::getBoundingBox(action);
    }
}

void SoViewContextGate::getMatrix(SoGetMatrixAction* action)
{
    if (shouldTraverse(action)) {
        inherited::getMatrix(action);
    }
}

void SoViewContextGate::getPrimitiveCount(SoGetPrimitiveCountAction* action)
{
    if (shouldTraverse(action)) {
        inherited::getPrimitiveCount(action);
    }
}

void SoViewContextGate::GLRenderBelowPath(SoGLRenderAction* action)
{
    if (shouldTraverse(action)) {
        inherited::GLRenderBelowPath(action);
    }
}

void SoViewContextGate::GLRenderInPath(SoGLRenderAction* action)
{
    if (shouldTraverse(action)) {
        inherited::GLRenderInPath(action);
    }
}

void SoViewContextGate::handleEvent(SoHandleEventAction* action)
{
    if (shouldTraverse(action)) {
        inherited::handleEvent(action);
    }
}

void SoViewContextGate::pick(SoPickAction* action)
{
    if (shouldTraverse(action)) {
        inherited::pick(action);
    }
}

void SoViewContextGate::rayPick(SoRayPickAction* action)
{
    if (shouldTraverse(action)) {
        inherited::rayPick(action);
    }
}
