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
 * Viewer-local realization of a contextual representation.
 *
 * The instance owns only transient Coin nodes.  It does not change a
 * document object's ViewProvider or visibility fields, and it does not own
 * the semantic ViewProvider.  Add getRoot() to a viewer scene graph and use
 * setRepresentation() whenever the active context changes.
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
