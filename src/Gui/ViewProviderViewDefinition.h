// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <QIcon>

#include "ViewProviderDocumentObject.h"

namespace App
{
class ViewDefinition;
}

namespace Gui
{

/** Tree representation of an ``App::ViewDefinition``.
 *
 * Editing a saved view's state in the property editor is realized in every 3D
 * view that currently shows the definition, and double clicking applies it to
 * the document's active 3D view.  Both paths use the same core realization as
 * the ``View3DInventor.applyViewDefinition`` Python API, so the provider needs
 * no vocabulary from the workbench that created the saved view.
 */
class GuiExport ViewProviderViewDefinition: public ViewProviderDocumentObject
{
    PROPERTY_HEADER_WITH_OVERRIDE(Gui::ViewProviderViewDefinition);

public:
    ViewProviderViewDefinition();
    ~ViewProviderViewDefinition() override = default;

    bool doubleClicked() override;
    QIcon getIcon() const override;
    void updateData(const App::Property* prop) override;

private:
    void applyToViewsShowingDefinition();
};

}  // namespace Gui
