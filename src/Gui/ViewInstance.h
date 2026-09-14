// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <FCGlobal.h>

class SoNode;
class SoSeparator;

namespace Gui
{

class SoViewContextGate;
class ViewContext;
class ViewProvider;

/**
 * Viewer-local Coin realization of a contextual representation.
 *
 * The instance owns its transient Coin roots and the representation nodes
 * attached to them. It does not own the semantic ViewProvider or ViewContext.
 */
class GuiExport ViewInstance
{
public:
    ViewInstance(ViewProvider* provider, const ViewContext* context);
    ~ViewInstance();

    ViewInstance(const ViewInstance&) = delete;
    ViewInstance& operator=(const ViewInstance&) = delete;

    SoSeparator* getRoot() const;
    SoSeparator* getRepresentationRoot() const;
    void setRepresentation(SoNode* representation);
    void clearRepresentation();
    bool hasRepresentation() const;

private:
    SoViewContextGate* root = nullptr;
    SoSeparator* representationRoot = nullptr;
};

}  // namespace Gui
