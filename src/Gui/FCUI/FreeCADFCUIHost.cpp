#include "FreeCADFCUIHost.h"

#include <QLabel>
#include <QSizePolicy>

#include "Application.h"
#include "Command.h"
#include "Selection.h"
#include "View3DInventorViewer.h"

using namespace Gui::FCUI;

FreeCADFCUIHost::FreeCADFCUIHost(QObject* parent)
    : FCUIQtHost(parent)
{
    // Selection changes (fastsignals) -> host path update.
    selectionConn_ = fastsignals::scoped_connection(
        Gui::Selection().signalSelectionChanged.connect([this](const Gui::SelectionChanges&) {
        emitSelectionCount();
        })
    );

    // Active document changes -> update viewers created through this host.
    if (Gui::Application::Instance) {
        activeDocConn_ = fastsignals::scoped_connection(
            Gui::Application::Instance->signalActiveDocument.connect([this](const Gui::Document&) {
                syncViewerDocuments();
            })
        );
    }

    emitSelectionCount();
}

FreeCADFCUIHost::~FreeCADFCUIHost() = default;

void FreeCADFCUIHost::emitSelectionCount()
{
    Q_EMIT pathChanged(QStringLiteral("selection.count"), static_cast<int>(Gui::Selection().size()));
}

void FreeCADFCUIHost::syncViewerDocuments()
{
    Gui::Document* doc = Gui::Application::Instance ? Gui::Application::Instance->activeDocument() : nullptr;

    for (auto it = viewers_.begin(); it != viewers_.end();) {
        if (!(*it)) {
            it = viewers_.erase(it);
            continue;
        }
        (*it)->setDocument(doc);
        ++it;
    }
}

QVariant FreeCADFCUIHost::readPath(const QString& path) const
{
    if (path == QLatin1String("selection.count")) {
        return static_cast<int>(Gui::Selection().size());
    }
    return {};
}

QWidget* FreeCADFCUIHost::createNativeWidget(const QString& kind, const QVariantMap& props, QWidget* parent)
{
    Q_UNUSED(props);

    if (kind == QLatin1String("View3D") || kind == QLatin1String("View3DInventorViewer")) {
        auto* viewer = new Gui::View3DInventorViewer(parent);
        if (Gui::Application::Instance) {
            viewer->setDocument(Gui::Application::Instance->activeDocument());
        }
        viewer->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
        viewers_.push_back(QPointer<Gui::View3DInventorViewer>(viewer));
        return viewer;
    }

    return new QLabel(QStringLiteral("Unsupported native widget: %1").arg(kind), parent);
}

void FreeCADFCUIHost::invokeCommand(const QString& name, const QVariantList& args)
{
    Q_UNUSED(args);
    if (!Gui::Application::Instance) {
        return;
    }
    Gui::Application::Instance->commandManager().runCommandByName(name.toUtf8().constData());
}
