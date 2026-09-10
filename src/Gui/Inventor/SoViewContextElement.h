// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <Inventor/elements/SoElement.h>
#include <Inventor/elements/SoSubElement.h>
#include <Inventor/nodes/SoSubNode.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoSwitch.h>

#include <FCGlobal.h>

namespace App
{
class DocumentObject;
}

namespace Gui
{

class ViewContext;
class ViewProvider;

/** Carries a viewer-local ViewContext through a Coin action traversal. */
class GuiExport SoViewContextElement: public SoElement
{
    using inherited = SoElement;

    SO_ELEMENT_HEADER(SoViewContextElement);

public:
    static void initClass();
    void init(SoState* state) override;
    SbBool matches(const SoElement* element) const override;
    SoElement* copyMatchInfo() const override;

    static void set(SoState* state, const ViewContext* context);
    static const ViewContext* get(SoState* state);

protected:
    ~SoViewContextElement() override;

private:
    const ViewContext* context = nullptr;
};

/** A display-mode switch that can be enabled by the current viewer without changing its field. */
class GuiExport SoViewContextSwitch: public SoSwitch
{
    using inherited = SoSwitch;

    SO_NODE_HEADER(SoViewContextSwitch);

public:
    static void initClass();
    explicit SoViewContextSwitch(ViewProvider* provider = nullptr);

    void callback(SoCallbackAction* action) override;
    void doAction(SoAction* action) override;
    void getBoundingBox(SoGetBoundingBoxAction* action) override;
    void getMatrix(SoGetMatrixAction* action) override;
    void getPrimitiveCount(SoGetPrimitiveCountAction* action) override;
    void GLRender(SoGLRenderAction* action) override;
    void handleEvent(SoHandleEventAction* action) override;
    void pick(SoPickAction* action) override;

protected:
    ~SoViewContextSwitch() override;

private:
    bool forceVisible(SoAction* action) const;
    void traverseChild(SoAction* action, int child);

    ViewProvider* provider = nullptr;
};

/** Object-aware separator used for auxiliary foreground/background provider roots. */
class GuiExport SoViewContextGate: public SoSeparator
{
    using inherited = SoSeparator;

    SO_NODE_HEADER(SoViewContextGate);

public:
    static void initClass();
    SoViewContextGate(
        ViewProvider* provider = nullptr,
        SoNode* child = nullptr,
        const ViewContext* context = nullptr
    );

    void callback(SoCallbackAction* action) override;
    void getBoundingBox(SoGetBoundingBoxAction* action) override;
    void getMatrix(SoGetMatrixAction* action) override;
    void getPrimitiveCount(SoGetPrimitiveCountAction* action) override;
    void GLRenderBelowPath(SoGLRenderAction* action) override;
    void GLRenderInPath(SoGLRenderAction* action) override;
    void handleEvent(SoHandleEventAction* action) override;
    void pick(SoPickAction* action) override;
    void rayPick(SoRayPickAction* action) override;

protected:
    ~SoViewContextGate() override;

private:
    bool shouldTraverse(SoAction* action) const;

    const App::DocumentObject* object = nullptr;
    const ViewContext* context = nullptr;
};

}  // namespace Gui
