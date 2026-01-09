#pragma once

#include "FCUIQtHost.h"

#include <QList>
#include <QPointer>
#include <fastsignals/connection.h>

namespace Gui
{
class Document;
class View3DInventorViewer;
}

namespace Gui::FCUI
{

class FreeCADFCUIHost final : public FCUIQtHost
{
    Q_OBJECT

public:
    explicit FreeCADFCUIHost(QObject* parent = nullptr);
    ~FreeCADFCUIHost() override;

    QVariant readPath(const QString& path) const override;
    QWidget* createNativeWidget(const QString& kind, const QVariantMap& props, QWidget* parent) override;

public Q_SLOTS:
    void invokeCommand(const QString& name, const QVariantList& args) override;

private:
    void emitSelectionCount();
    void syncViewerDocuments();

    fastsignals::scoped_connection selectionConn_;
    fastsignals::scoped_connection activeDocConn_;
    QList<QPointer<Gui::View3DInventorViewer>> viewers_;
};

}  // namespace Gui::FCUI
