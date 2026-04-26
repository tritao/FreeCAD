/***************************************************************************
 *   Copyright (c) 2005 Werner Mayer <wmayer[at]users.sourceforge.net>     *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/


#pragma once

#include <string>
#include <utility>
#include <fastsignals/signal.h>

#include <QStringList>
#include <QPointer>
#include <QTimer>
#include <QToolBar>
#include <QPointer>

#include <FCGlobal.h>
#include <Base/Parameter.h>

#include "ParamHandler.h"

class QAction;
class QLayout;
class QMenu;
class QMouseEvent;
class QMainWindow;

namespace Gui
{

class ToolBarAreaWidget;
enum class ToolBarArea;
class MDIView;
class TreePanel;

class GuiExport ToolBarItem
{
public:
    /** Manages the default visibility status of a toolbar item, as well as the default status
     * of the toggleViewAction usable by the contextual menu to enable and disable its visibility
     */
    enum class DefaultVisibility
    {
        Visible,      // toolbar is hidden by default, visibility toggle action is enabled
        Hidden,       // toolbar hidden by default, visibility toggle action is enabled
        Unavailable,  // toolbar visibility is managed independently by client code and defaults to
                      // hidden, visibility toggle action is disabled by default (it is unavailable
                      // to the UI). Upon being forced to be available, these toolbars default to
                      // visible.
    };

    enum class Tier
    {
        Recommended,
        Secondary,
        Advanced,
        Contextual,
    };

    enum class Host
    {
        MainWindow,
        ActiveView,
        Panel,
    };

    enum class PanelRole
    {
        None,
        ModelTree,
    };

    enum class ViewHostRequirement
    {
        AnyView,
        View3D,
    };

    enum class ViewPresentation
    {
        Docked,
        CenteredOverlay,
    };

    enum class ViewOverlayEdge
    {
        Top,
        Bottom,
        Left,
        Right,
    };

    enum class ViewOverlayEdgePersistence
    {
        ByScope,
        Shared,
        Contextual,
    };

    ToolBarItem();
    explicit ToolBarItem(
        ToolBarItem* item,
        DefaultVisibility visibilityPolicy = DefaultVisibility::Visible
    );
    ~ToolBarItem();

    void setCommand(const std::string&);
    const std::string& command() const;
    bool hasPersistenceKey() const;
    void setPersistenceKey(const std::string&);
    const std::string& persistenceKey() const;
    void setTier(Tier tier);
    Tier tier() const;
    void setHost(Host host);
    Host host() const;
    void setPanelRole(PanelRole role);
    PanelRole panelRole() const;
    void setViewHostRequirement(ViewHostRequirement requirement);
    ViewHostRequirement viewHostRequirement() const;
    void setViewPresentation(ViewPresentation presentation);
    ViewPresentation viewPresentation() const;
    void setViewOverlayEdge(ViewOverlayEdge edge);
    ViewOverlayEdge viewOverlayEdge() const;
    void setViewOverlayEdgePersistence(ViewOverlayEdgePersistence persistence);
    ViewOverlayEdgePersistence viewOverlayEdgePersistence() const;

    bool hasItems() const;
    ToolBarItem* findItem(const std::string&);
    ToolBarItem* copy() const;
    uint count() const;

    void appendItem(ToolBarItem* item);
    bool insertItem(ToolBarItem*, ToolBarItem* item);
    void removeItem(ToolBarItem* item);
    void clear();

    ToolBarItem& operator<<(ToolBarItem* item);
    ToolBarItem& operator<<(const std::string& command);
    QList<ToolBarItem*> getItems() const;

    DefaultVisibility visibilityPolicy;

private:
    std::string _name;
    std::string _persistenceKey;
    Tier _tier = Tier::Recommended;
    Host _host = Host::MainWindow;
    PanelRole _panelRole = PanelRole::None;
    ViewHostRequirement _viewHostRequirement = ViewHostRequirement::AnyView;
    ViewPresentation _viewPresentation = ViewPresentation::Docked;
    ViewOverlayEdge _viewOverlayEdge = ViewOverlayEdge::Top;
    ViewOverlayEdgePersistence _viewOverlayEdgePersistence = ViewOverlayEdgePersistence::ByScope;
    QList<ToolBarItem*> _items;
};

class ToolBarGrip: public QWidget
{
    Q_OBJECT

public:
    explicit ToolBarGrip(QToolBar*);

    void attach();
    void detach();

    bool isAttached() const;

protected:
    void paintEvent(QPaintEvent*);
    void mouseMoveEvent(QMouseEvent*);
    void mousePressEvent(QMouseEvent*);
    void mouseReleaseEvent(QMouseEvent*);

    void updateSize();

private:
    QPointer<QAction> _action = nullptr;
};

/**
 * QToolBar from Qt lacks few abilities like ability to float toolbar from code.
 * This class allows us to provide custom behaviors for toolbars if needed.
 */
class GuiExport ToolBar: public QToolBar
{
    Q_OBJECT

    friend class ToolBarGrip;

public:
    ToolBar();
    explicit ToolBar(QWidget* parent);

    virtual ~ToolBar() = default;

    void undock();
    void updateCustomGripVisibility();

protected:
    void setupConnections();
};

/**
 * The ToolBarManager class is responsible for the creation of toolbars and appending them
 * to the main window.
 * @see ToolBoxManager
 * @see MenuManager
 * @author Werner Mayer
 */
class GuiExport ToolBarManager: public QObject
{
    Q_OBJECT
public:
    enum class Scope
    {
        Legacy,
        Shared,
        Workbench,
        Contextual,
    };

    struct ToolbarScopeId
    {
        Scope scope = Scope::Legacy;
        QString workbench;
        QString context;

        bool isEmpty() const;
    };

    struct PersistenceId
    {
        enum class SharedPrefix
        {
            Shared,
            Global,
        };

        PersistenceId() = default;
        PersistenceId(
            ToolbarScopeId scopeId,
            QString toolbar,
            SharedPrefix sharedPrefix = SharedPrefix::Shared
        )
            : scopeId(std::move(scopeId))
            , toolbar(std::move(toolbar))
            , sharedPrefix(sharedPrefix)
        {}
        PersistenceId(
            Scope scope,
            QString toolbar,
            QString workbench = {},
            QString context = {},
            SharedPrefix sharedPrefix = SharedPrefix::Shared
        )
            : PersistenceId(
                  ToolbarScopeId {scope, std::move(workbench), std::move(context)},
                  std::move(toolbar),
                  sharedPrefix
              )
        {}

        ToolbarScopeId scopeId;
        QString toolbar;
        SharedPrefix sharedPrefix = SharedPrefix::Shared;

        bool isEmpty() const;
        ToolbarScopeId toolbarScopeId() const;
    };

    enum class State
    {
        ForceHidden,     // Forces a toolbar to hide and hides the toggle action
        ForceAvailable,  // Forces a toolbar toggle action to show, visibility depends on user config
        RestoreDefault,  // Restores a toolbar toggle action default, visibility as user config
        SaveState,       // Saves the state of the toolbars
    };

    /// The one and only instance.
    static ToolBarManager* getInstance();
    static void destruct();
    static QString toolBarPersistenceKey(const ToolBarItem*);
    static QString toolBarPersistenceKey(const QToolBar*);
    static PersistenceId toolBarPersistenceId(const QString& persistenceKey);
    static PersistenceId toolBarPersistenceId(const ToolBarItem*);
    static PersistenceId toolBarPersistenceId(const QToolBar*);
    static ToolbarScopeId layoutContextId(const QString& context);
    static QString makeToolBarLayoutContext(const ToolbarScopeId& scopeId);
    static QString makeToolBarPersistenceKey(const PersistenceId&);
    static ToolbarScopeId toolBarScopeId(const QString& persistenceKey);
    static ToolbarScopeId toolBarScopeId(const ToolBarItem*);
    static ToolbarScopeId toolBarScopeId(const QToolBar*);
    static QString toolBarScopeLabel(const QString& persistenceKey);
    static QString toolBarScopeLabel(const ToolBarItem*);
    static QString toolBarScopeLabel(const QToolBar*);
    static ToolBarItem::Tier toolBarTier(const ToolBarItem*);
    static ToolBarItem::Tier toolBarTier(const QToolBar*);
    static ToolBarItem::Host toolBarHost(const ToolBarItem*);
    static ToolBarItem::Host toolBarHost(const QToolBar*);
    static QString toolBarPanelRoleName(ToolBarItem::PanelRole);
    static ToolBarItem::PanelRole toolBarPanelRole(const ToolBarItem*);
    static ToolBarItem::PanelRole toolBarPanelRole(const QToolBar*);
    static ToolBarItem::Tier normalizeCustomToolBarTier(ToolBarItem::Tier);
    static ToolBarItem::Tier customToolBarTierFromName(const QString&);
    static ToolBarItem::Tier toolBarTierFromName(const QString&);
    static QString toolBarTierName(ToolBarItem::Tier);
    static QString toolBarTierLabel(ToolBarItem::Tier);
    static QString toolBarTierLabel(const ToolBarItem*);
    static QString toolBarTierLabel(const QToolBar*);
    static QString toolBarHostName(ToolBarItem::Host);
    static QString toolBarPanelRoleLabel(ToolBarItem::PanelRole);
    static ToolBarItem::ViewHostRequirement toolBarViewHostRequirement(const ToolBarItem*);
    static ToolBarItem::ViewHostRequirement toolBarViewHostRequirement(const QToolBar*);
    static QString toolBarViewPresentationName(ToolBarItem::ViewPresentation);
    static ToolBarItem::ViewPresentation toolBarViewPresentation(const ToolBarItem*);
    static ToolBarItem::ViewPresentation toolBarViewPresentation(const QToolBar*);
    static QString toolBarViewOverlayEdgeName(ToolBarItem::ViewOverlayEdge);
    static ToolBarItem::ViewOverlayEdge toolBarViewOverlayEdge(const ToolBarItem*);
    static ToolBarItem::ViewOverlayEdge toolBarViewOverlayEdge(const QToolBar*);
    static QString toolBarViewOverlayEdgePersistenceName(ToolBarItem::ViewOverlayEdgePersistence);
    static ToolBarItem::ViewOverlayEdgePersistence toolBarViewOverlayEdgePersistence(
        const ToolBarItem*
    );
    static ToolBarItem::ViewOverlayEdgePersistence toolBarViewOverlayEdgePersistence(const QToolBar*);
    static void setToolBarPersistenceKey(QToolBar*, const QString&);
    static void setToolBarTier(QToolBar*, ToolBarItem::Tier);
    static void setToolBarHost(QToolBar*, ToolBarItem::Host);
    static void setToolBarPanelRole(QToolBar*, ToolBarItem::PanelRole);
    static void setToolBarViewPresentation(QToolBar*, ToolBarItem::ViewPresentation);
    static void setToolBarViewOverlayEdge(QToolBar*, ToolBarItem::ViewOverlayEdge);
    static void setToolBarViewOverlayEdgePersistence(QToolBar*, ToolBarItem::ViewOverlayEdgePersistence);

    /** Sets up the toolbars of a given workbench. */
    void setup(ToolBarItem*);
    void saveState() const;
    void restoreState();
    void retranslate() const;
    void populateToolBarMenu(QMenu* menu);
    bool populateViewToolBarMenu(QMenu* menu);
    void setToolbarLayoutContextOverride(const QString& workbench, const QString& context);
    void clearToolbarLayoutContextOverride(const QString& workbench);
    QString currentToolbarLayoutScopeLabel() const;
    QString currentToolbarLayoutResetLabel() const;
    QString currentRecommendedToolbarLayoutResetLabel() const;
    QString currentViewToolbarLayoutResetLabel() const;
    QString currentRecommendedViewToolbarLayoutResetLabel() const;
    QString currentShowRecommendedOnlyLabel() const;
    void resetCurrentToolbarLayout();
    void resetCurrentToolbarLayoutToRecommended();
    void resetCurrentViewToolbarLayout();
    void resetCurrentViewToolbarLayoutToRecommended();
    void showRecommendedToolBarsOnly();
    void refreshHostedToolBars();

    bool areToolBarsLocked() const;
    void setToolBarsLocked(bool locked) const;

    void setState(const QList<QString>& names, State state);
    void setState(const QString& name, State state);

    int toolBarIconSize(QWidget* widget = nullptr) const;
    void setupToolBarIconSize();

    ToolBarArea toolBarArea(QWidget* toolBar) const;
    ToolBarAreaWidget* toolBarAreaWidget(QWidget* toolBar) const;

Q_SIGNALS:
    void toolbarLayoutContextChanged();
    void toolbarLayoutRestored(const QString& context);

protected:
    void setup(ToolBarItem*, QToolBar*) const;

    void setMovable(bool movable) const;

    ToolBarItem::DefaultVisibility getToolbarPolicy(const QToolBar*) const;

    bool addToolBarToArea(QObject* source, QMouseEvent* ev);
    bool showContextMenu(QObject* source);
    void onToggleStatusBarWidget(QWidget* widget, bool visible);
    void setToolBarIconSize(QToolBar* toolbar);
    void onTimer();

    bool eventFilter(QObject* source, QEvent* ev) override;

    /** Returns a list of all currently existing toolbars. */
    QList<ToolBar*> toolBars() const;
    ToolBar* findToolBar(const QList<ToolBar*>&, const QString&) const;
    QAction* findAction(const QList<QAction*>&, const QString&) const;
    ToolBarManager();
    ~ToolBarManager() override;

private:
    enum class CurrentLayoutScope
    {
        None,
        Workbench,
        Contextual,
    };

    void setupParameters();
    void setupStatusBar();
    void setupMenuBar();
    void setupConnection();
    void setupTimer();
    void setupSizeTimer();
    void setupResizeTimer();
    void setupMenuBarTimer();
    void setupWidgetProducers();
    void onToolbarParametersChanged(const ParamKey*);
    QList<QAction*> panelToolBarMenuActions(QMenu* menu, const QList<QToolBar*>& toolbars) const;
    QList<QAction*> viewToolBarMenuActions(QMenu* menu, const QList<QToolBar*>& toolbars) const;
    void populateSingleToolBarMenu(QMenu* menu, QToolBar* toolbar) const;
    QAction* toolBarMenuAction(QMenu* menu, QToolBar* toolbar) const;
    void addToolBarActionsByScope(QMenu* menu, const QList<QToolBar*>& toolbars) const;
    void addCurrentToolbarLayoutActions(QMenu* menu);
    void addCurrentViewToolbarLayoutActions(QMenu* menu);
    QString activeToolbarLayoutContext() const;
    QString effectiveToolbarLayoutContext() const;
    CurrentLayoutScope currentToolbarLayoutScope(
        QString* layoutContext = nullptr,
        QString* activeContext = nullptr
    ) const;
    bool hasViewHostedToolBars() const;
    bool rememberToolbarLayoutByWorkbench() const;
    bool hasSavedWorkbenchToolBarLayout(const QString& context) const;
    bool hasSavedViewToolBarLayout(const QString& context) const;
    bool toolbarBelongsToLayoutContext(const QToolBar* toolbar, const QString& context) const;
    void initializeUnsavedToolbarLayoutContext(const QString& context);
    void updateLayoutParameters(const QString& context);
    ParameterGrp::handle workbenchLayoutGroup(const QString& context) const;
    ParameterGrp::handle globalHostedToolBarHostGroup() const;
    ParameterGrp::handle hostedToolBarHostGroup(const QString& context) const;
    ParameterGrp::handle globalViewToolBarPresentationGroup() const;
    ParameterGrp::handle viewToolBarPresentationGroup(const QString& context) const;
    ParameterGrp::handle sharedViewOverlayEdgeGroup() const;
    ParameterGrp::handle viewOverlayEdgeGroup(const QString& context) const;
    ParameterGrp::handle toolbarAreaRestoreParameters(
        const ParameterGrp::handle& current,
        const ParameterGrp::handle& fallback
    ) const;
    ToolBarItem::Host resolvedHostedToolBarHost(
        const QToolBar* toolbar,
        const QString& context,
        const QString& fallbackContext = {}
    ) const;
    ToolBarItem::ViewPresentation resolvedViewToolBarPresentation(
        const QToolBar* toolbar,
        const QString& context,
        const QString& fallbackContext = {}
    ) const;
    ToolBarItem::ViewOverlayEdge resolvedViewOverlayEdge(
        const QToolBar* toolbar,
        const QString& context,
        const QString& fallbackContext = {}
    ) const;
    void persistHostedToolBarHost(
        const QToolBar* toolbar,
        const QString& context,
        ToolBarItem::Host host
    ) const;
    void persistViewToolBarPresentation(
        const QToolBar* toolbar,
        const QString& context,
        ToolBarItem::ViewPresentation presentation
    ) const;
    void persistViewOverlayEdge(
        const QToolBar* toolbar,
        const QString& context,
        ToolBarItem::ViewOverlayEdge edge
    ) const;
    void saveWorkbenchToolBarLayout(const QString& context) const;
    void restoreWorkbenchToolBarLayout(const QString& context) const;
    void resetMainWindowToolBarLayout() const;
    void clearViewToolBarLayout(const QString& context) const;
    void resetViewHostedToolBarLayout(QMainWindow* hostWindow) const;
    void restoreViewHostedToolBarLayout(
        QMainWindow* hostWindow,
        const QString& context,
        const QString& fallbackContext = {}
    ) const;
    bool recommendedToolBarVisibility(const QToolBar* toolbar) const;
    void applyRecommendedToolBarPreferences();
    void applyRecommendedToolBarVisibility();
    void applyRecommendedViewToolBarPreferences();
    void applyRecommendedViewToolBarVisibility();
    void refreshPanelHostedToolBars();
    void refreshViewHostedToolBars();
    void setHostedToolBarHost(QToolBar* toolbar, ToolBarItem::Host host);
    void setViewToolBarPresentation(QToolBar* toolbar, ToolBarItem::ViewPresentation presentation);
    void setViewOverlayEdge(QToolBar* toolbar, ToolBarItem::ViewOverlayEdge edge) const;
    QMainWindow* toolBarHostWindow(const QToolBar* toolbar) const;
    bool activeViewSupportsToolBarHost(const QToolBar* toolbar, const MDIView* view) const;
    bool activePanelSupportsToolBarHost(const QToolBar* toolbar, const TreePanel* panel) const;

    void addToMenu(QLayout* layout, QWidget* area, QMenu* menu);
    QLayout* findLayoutOfObject(QObject* source, QWidget* area) const;
    ToolBarAreaWidget* findToolBarAreaWidget() const;

private:
    QStringList toolbarKeys;
    QString toolbarLayoutContext;
    QString toolbarLayoutContextOverrideWorkbench;
    QString toolbarLayoutContextOverride;
    static ToolBarManager* _instance;

    QTimer timer;
    QTimer menuBarTimer;
    QTimer sizeTimer;
    QTimer resizeTimer;
    fastsignals::connection connectActivateView;
    ParamHandlers paramHandlers;
    ToolBarAreaWidget* statusBarAreaWidget = nullptr;
    ToolBarAreaWidget* menuBarLeftAreaWidget = nullptr;
    ToolBarAreaWidget* menuBarRightAreaWidget = nullptr;
    ParameterGrp::handle hGeneral;
    ParameterGrp::handle hMainWindow;
    ParameterGrp::handle hPref;
    ParameterGrp::handle hWorkbenchLayouts;
    ParameterGrp::handle hGlobalStatusBar;
    ParameterGrp::handle hGlobalMenuBarLeft;
    ParameterGrp::handle hGlobalMenuBarRight;
    ParameterGrp::handle hStatusBar;
    ParameterGrp::handle hMenuBarLeft;
    ParameterGrp::handle hMenuBarRight;
    std::map<QToolBar*, QPointer<QToolBar>> resizingToolbars;
    int _toolBarIconSize = 0;
    int _statusBarIconSize = 0;
    int _menuBarIconSize = 0;
    bool blockRestore = false;
    bool refreshingPanelHostedToolBars = false;
    bool refreshingViewHostedToolBars = false;
};

}  // namespace Gui
