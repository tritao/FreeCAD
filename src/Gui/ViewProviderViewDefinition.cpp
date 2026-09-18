// SPDX-License-Identifier: LGPL-2.1-or-later

#include "PreCompiled.h"

#include "ViewProviderViewDefinition.h"

#include <App/Application.h>
#include <App/Document.h>
#include <App/ViewDefinition.h>

#include "Application.h"
#include "BitmapFactory.h"
#include "Document.h"
#include "MainWindow.h"
#include "View3DInventor.h"
#include "View3DInventorViewer.h"
#include "ViewContext.h"

using namespace Gui;

PROPERTY_SOURCE(Gui::ViewProviderViewDefinition, Gui::ViewProviderDocumentObject)

namespace
{

/** True for the definition properties that describe what a view shows. */
bool isViewStateProperty(const App::ViewDefinition& definition, const App::Property* prop)
{
    return prop == &definition.CameraType
        || prop == &definition.CameraPlacement
        || prop == &definition.CameraFocalDistance
        || prop == &definition.CameraHeightAngle
        || prop == &definition.CameraHeight
        || prop == &definition.CameraAspectRatio
        || prop == &definition.CameraNearDistance
        || prop == &definition.CameraFarDistance
        || prop == &definition.ReferenceFrame
        || prop == &definition.ForcedVisible
        || prop == &definition.ForcedHidden
        || prop == &definition.ClippingPlanes;
}

}  // namespace

ViewProviderViewDefinition::ViewProviderViewDefinition() = default;

QIcon ViewProviderViewDefinition::getIcon() const
{
    return QIcon(BitmapFactory().pixmap("view-axonometric"));
}

bool ViewProviderViewDefinition::doubleClicked()
{
    auto* definition = getObject<App::ViewDefinition>();
    auto* guiDocument = getDocument();
    if (!definition || !guiDocument) {
        return false;
    }

    auto* view = dynamic_cast<View3DInventor*>(guiDocument->getActiveView());
    if (!view) {
        const auto views = guiDocument->getMDIViewsOfType(View3DInventor::getClassTypeId());
        if (!views.empty()) {
            view = static_cast<View3DInventor*>(views.front());
        }
    }
    if (!view) {
        return false;
    }

    getMainWindow()->setActiveWindow(view);
    return view->applyViewDefinition(*definition);
}

void ViewProviderViewDefinition::updateData(const App::Property* prop)
{
    auto* definition = getObject<App::ViewDefinition>();
    if (definition && prop && !App::GetApplication().isRestoring()
        && isViewStateProperty(*definition, prop)) {
        applyToViewsShowingDefinition();
    }
    ViewProviderDocumentObject::updateData(prop);
}

void ViewProviderViewDefinition::applyToViewsShowingDefinition()
{
    auto* definition = getObject<App::ViewDefinition>();
    auto* guiDocument = getDocument();
    if (!definition || !guiDocument) {
        return;
    }

    const auto views = guiDocument->getMDIViewsOfType(View3DInventor::getClassTypeId());
    for (auto* mdiView : views) {
        auto* view = static_cast<View3DInventor*>(mdiView);
        if (view->getViewer()->getViewContext().appliedDefinition() != definition) {
            continue;
        }
        view->applyViewDefinition(*definition);
    }
}
