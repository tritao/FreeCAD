#pragma once

#include <QString>

class QMainWindow;
class QWidget;

namespace Gui
{

class DockWindowItems;
class DockWindowManager;

class StandardDockWidgetFactory final
{
public:
    static bool isStandardId(const QString& id);
    static bool isEnabled(const QString& id);

    static QWidget* create(const QString& id, QMainWindow* hostWindow);

    static QWidget* ensureRegistered(
        DockWindowManager* dockManager,
        QMainWindow* hostWindow,
        const QString& id
    );

    static void ensureRegisteredForItems(
        DockWindowManager* dockManager,
        QMainWindow* hostWindow,
        const DockWindowItems& items
    );
};

}  // namespace Gui
