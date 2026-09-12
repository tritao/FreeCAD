// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ViewInstance.h"

#include <Inventor/nodes/SoSeparator.h>

#include "Inventor/SoViewContextElement.h"

using namespace Gui;

ViewInstance::ViewInstance(ViewProvider* provider, const ViewContext* context)
{
    representationRoot = new SoSeparator;
    representationRoot->ref();
    root = new SoViewContextGate(provider, representationRoot, context);
    root->ref();
}

ViewInstance::~ViewInstance()
{
    root->removeAllChildren();
    root->unref();
    representationRoot->removeAllChildren();
    representationRoot->unref();
}

SoSeparator* ViewInstance::getRoot() const
{
    return root;
}

SoSeparator* ViewInstance::getRepresentationRoot() const
{
    return representationRoot;
}

void ViewInstance::setRepresentation(SoNode* representation)
{
    clearRepresentation();
    if (representation) {
        representationRoot->addChild(representation);
    }
}

void ViewInstance::clearRepresentation()
{
    representationRoot->removeAllChildren();
}

bool ViewInstance::hasRepresentation() const
{
    return representationRoot->getNumChildren() > 0;
}
