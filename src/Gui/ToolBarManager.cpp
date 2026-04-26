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


#include <QAction>
#include <QActionGroup>
#include <QApplication>
#include <QByteArray>
#include <QHBoxLayout>
#include <QMap>
#include <QMenuBar>
#include <QMouseEvent>
#include <QPainter>
#include <QPointer>
#include <QSet>
#include <QStatusBar>
#include <QToolBar>
#include <QToolButton>
#include <QStyleOption>


#include <array>
#include <algorithm>
#include <tuple>
#include <boost/algorithm/string/predicate.hpp>

#include <Base/Tools.h>

#include "ToolBarManager.h"
#include "ToolBarAreaWidget.h"
#include "Application.h"
#include "Command.h"
#include "MainWindow.h"
#include "MDIView.h"
#include "OverlayWidgets.h"
#include "PanelToolBarHost.h"
#include "SplitView3DInventor.h"
#include "Tree.h"
#include "ViewToolBarOverlay.h"
#include "View3DInventor.h"
#include "Workbench.h"
#include "WorkbenchManager.h"
#include "WidgetFactory.h"


using namespace Gui;

namespace
{
constexpr auto ToolBarPersistenceKeyProperty = "_fc_toolbar_persistence_key";
constexpr auto ToolBarPublicPersistenceKeyProperty = "PersistenceKey";
constexpr auto ToolBarTierProperty = "_fc_toolbar_tier";
constexpr auto ToolBarPublicTierProperty = "Tier";
constexpr auto ToolBarHostProperty = "_fc_toolbar_host";
constexpr auto ToolBarDefaultHostProperty = "_fc_toolbar_default_host";
constexpr auto ToolBarPublicHostProperty = "Host";
constexpr auto ToolBarPanelRoleProperty = "_fc_toolbar_panel_role";
constexpr auto ToolBarPublicPanelRoleProperty = "PanelRole";
constexpr auto ToolBarViewHostRequirementProperty = "_fc_toolbar_view_host_requirement";
constexpr auto ToolBarViewPresentationProperty = "_fc_toolbar_view_presentation";
constexpr auto ToolBarDefaultViewPresentationProperty = "_fc_toolbar_default_view_presentation";
constexpr auto ToolBarPublicViewPresentationProperty = "ViewPresentation";
constexpr auto ToolBarViewOverlayEdgeProperty = "_fc_toolbar_view_overlay_edge";
constexpr auto ToolBarDefaultViewOverlayEdgeProperty = "_fc_toolbar_default_view_overlay_edge";
constexpr auto ToolBarPublicViewOverlayEdgeProperty = "ViewOverlayEdge";
constexpr auto ToolBarViewOverlayEdgePersistenceProperty
    = "_fc_toolbar_view_overlay_edge_persistence";
constexpr auto ToolBarPublicViewOverlayEdgePersistenceProperty = "ViewOverlayEdgePersistence";
constexpr auto ViewTopLayoutKey = "ViewTop";
constexpr auto ViewLeftLayoutKey = "ViewLeft";
constexpr auto ViewRightLayoutKey = "ViewRight";
constexpr auto ViewBottomLayoutKey = "ViewBottom";
constexpr auto HostedToolbarHostsGroupKey = "HostedToolbarHosts";
constexpr auto ViewToolbarPresentationsGroupKey = "ViewToolbarPresentations";
constexpr auto ViewOverlayEdgesGroupKey = "ViewOverlayEdges";
}  // namespace

namespace
{

QStringList splitLayoutState(const std::string& value)
{
    if (value.empty()) {
        return {};
    }

    return QString::fromUtf8(value.c_str()).split(QLatin1Char(','), Qt::SkipEmptyParts);
}

ToolBarManager::PersistenceId makeToolBarPersistenceId(const QString& persistenceKey)
{
    ToolBarManager::PersistenceId id;
    if (persistenceKey.isEmpty()) {
        return id;
    }

    const auto parts = persistenceKey.split(QLatin1Char(':'), Qt::KeepEmptyParts);
    if (parts.isEmpty()) {
        return id;
    }

    const auto scope = parts.front();
    if (scope == QLatin1String("shared") || scope == QLatin1String("global")) {
        id.scopeId.scope = ToolBarManager::Scope::Shared;
        id.toolbar = parts.back();
        id.sharedPrefix = (scope == QLatin1String("global"))
            ? ToolBarManager::PersistenceId::SharedPrefix::Global
            : ToolBarManager::PersistenceId::SharedPrefix::Shared;
        return id;
    }

    if (scope == QLatin1String("wb") && parts.size() >= 3) {
        id.scopeId.scope = ToolBarManager::Scope::Workbench;
        id.scopeId.workbench = parts.at(1);
        id.toolbar = parts.back();
        return id;
    }

    if (scope == QLatin1String("ctx") && parts.size() >= 4) {
        id.scopeId.scope = ToolBarManager::Scope::Contextual;
        id.scopeId.workbench = parts.at(1);
        id.scopeId.context = parts.mid(2, parts.size() - 3).join(QLatin1Char(':'));
        id.toolbar = parts.back();
        return id;
    }

    id.toolbar = parts.back();
    return id;
}

QString toolBarScopeLabel(ToolBarManager::Scope scope)
{
    switch (scope) {
        case ToolBarManager::Scope::Shared:
            return QApplication::translate("MainWindow", "Shared");
        case ToolBarManager::Scope::Workbench:
            return QApplication::translate("MainWindow", "Workbench");
        case ToolBarManager::Scope::Contextual:
            return QApplication::translate("MainWindow", "Contextual");
        case ToolBarManager::Scope::Legacy:
            return QApplication::translate("MainWindow", "Unscoped");
    }

    return {};
}

QString serializeToolBarPersistenceId(const ToolBarManager::PersistenceId& id)
{
    if (id.toolbar.isEmpty()) {
        return {};
    }

    QStringList segments;
    switch (id.scopeId.scope) {
        case ToolBarManager::Scope::Shared:
            segments.push_back(
                id.sharedPrefix == ToolBarManager::PersistenceId::SharedPrefix::Global
                    ? QStringLiteral("global")
                    : QStringLiteral("shared")
            );
            break;
        case ToolBarManager::Scope::Workbench:
            if (id.scopeId.workbench.isEmpty()) {
                return {};
            }
            segments.push_back(QStringLiteral("wb"));
            segments.push_back(id.scopeId.workbench);
            break;
        case ToolBarManager::Scope::Contextual:
            if (id.scopeId.workbench.isEmpty() || id.scopeId.context.isEmpty()) {
                return {};
            }
            segments.push_back(QStringLiteral("ctx"));
            segments.push_back(id.scopeId.workbench);
            segments.push_back(id.scopeId.context);
            break;
        case ToolBarManager::Scope::Legacy:
            break;
    }

    segments.push_back(id.toolbar);
    return segments.join(QLatin1Char(':'));
}

QString serializeLayoutContextId(const ToolBarManager::ToolbarScopeId& scopeId)
{
    switch (scopeId.scope) {
        case ToolBarManager::Scope::Workbench:
            if (scopeId.workbench.isEmpty() || !scopeId.context.isEmpty()) {
                return {};
            }
            return scopeId.workbench;
        case ToolBarManager::Scope::Contextual:
            if (scopeId.workbench.isEmpty() || scopeId.context.isEmpty()) {
                return {};
            }
            return QStringLiteral("ctx:%1:%2").arg(scopeId.workbench, scopeId.context);
        case ToolBarManager::Scope::Legacy:
        case ToolBarManager::Scope::Shared:
            return {};
    }

    return {};
}
ToolBarItem::Tier defaultToolBarTier(ToolBarItem::DefaultVisibility visibility)
{
    switch (visibility) {
        case ToolBarItem::DefaultVisibility::Visible:
            return ToolBarItem::Tier::Recommended;
        case ToolBarItem::DefaultVisibility::Hidden:
            return ToolBarItem::Tier::Secondary;
        case ToolBarItem::DefaultVisibility::Unavailable:
            return ToolBarItem::Tier::Contextual;
    }

    return ToolBarItem::Tier::Recommended;
}

QString toolBarTierName(ToolBarItem::Tier tier)
{
    switch (tier) {
        case ToolBarItem::Tier::Recommended:
            return QStringLiteral("recommended");
        case ToolBarItem::Tier::Secondary:
            return QStringLiteral("secondary");
        case ToolBarItem::Tier::Advanced:
            return QStringLiteral("advanced");
        case ToolBarItem::Tier::Contextual:
            return QStringLiteral("contextual");
    }

    return {};
}

ToolBarItem::Tier parseToolBarTier(const QString& tierName)
{
    if (tierName == QLatin1String("secondary")) {
        return ToolBarItem::Tier::Secondary;
    }
    if (tierName == QLatin1String("advanced")) {
        return ToolBarItem::Tier::Advanced;
    }
    if (tierName == QLatin1String("contextual")) {
        return ToolBarItem::Tier::Contextual;
    }

    return ToolBarItem::Tier::Recommended;
}

QString toolBarTierLabel(ToolBarItem::Tier tier)
{
    switch (tier) {
        case ToolBarItem::Tier::Recommended:
            return QApplication::translate("MainWindow", "Recommended");
        case ToolBarItem::Tier::Secondary:
            return QApplication::translate("MainWindow", "Secondary");
        case ToolBarItem::Tier::Advanced:
            return QApplication::translate("MainWindow", "Advanced");
        case ToolBarItem::Tier::Contextual:
            return QApplication::translate("MainWindow", "Contextual");
    }

    return {};
}

QString toolBarHostName(ToolBarItem::Host host)
{
    switch (host) {
        case ToolBarItem::Host::MainWindow:
            return QStringLiteral("main-window");
        case ToolBarItem::Host::ActiveView:
            return QStringLiteral("view");
        case ToolBarItem::Host::Panel:
            return QStringLiteral("panel");
    }

    return QStringLiteral("main-window");
}

ToolBarItem::Host parseToolBarHost(const QString& hostName)
{
    if (hostName == QLatin1String("panel")) {
        return ToolBarItem::Host::Panel;
    }
    if (hostName == QLatin1String("view")) {
        return ToolBarItem::Host::ActiveView;
    }

    return ToolBarItem::Host::MainWindow;
}

QString toolBarPanelRoleName(ToolBarItem::PanelRole role)
{
    switch (role) {
        case ToolBarItem::PanelRole::None:
            return QStringLiteral("none");
        case ToolBarItem::PanelRole::ModelTree:
            return QStringLiteral("model-tree");
    }

    return QStringLiteral("none");
}

ToolBarItem::PanelRole parseToolBarPanelRole(const QString& roleName)
{
    if (roleName == QLatin1String("model-tree")) {
        return ToolBarItem::PanelRole::ModelTree;
    }

    return ToolBarItem::PanelRole::None;
}

QString toolBarViewPresentationName(ToolBarItem::ViewPresentation presentation)
{
    switch (presentation) {
        case ToolBarItem::ViewPresentation::Docked:
            return QStringLiteral("docked");
        case ToolBarItem::ViewPresentation::CenteredOverlay:
            return QStringLiteral("centered-overlay");
    }

    return QStringLiteral("docked");
}

ToolBarItem::ViewPresentation parseToolBarViewPresentation(const QString& presentationName)
{
    if (presentationName == QLatin1String("centered-overlay")) {
        return ToolBarItem::ViewPresentation::CenteredOverlay;
    }

    return ToolBarItem::ViewPresentation::Docked;
}

QString toolBarViewOverlayEdgeName(ToolBarItem::ViewOverlayEdge edge)
{
    switch (edge) {
        case ToolBarItem::ViewOverlayEdge::Top:
            return QStringLiteral("top");
        case ToolBarItem::ViewOverlayEdge::Bottom:
            return QStringLiteral("bottom");
        case ToolBarItem::ViewOverlayEdge::Left:
            return QStringLiteral("left");
        case ToolBarItem::ViewOverlayEdge::Right:
            return QStringLiteral("right");
    }

    return QStringLiteral("top");
}

QString toolBarViewOverlayEdgePersistenceName(ToolBarItem::ViewOverlayEdgePersistence persistence)
{
    switch (persistence) {
        case ToolBarItem::ViewOverlayEdgePersistence::ByScope:
            return QStringLiteral("by-scope");
        case ToolBarItem::ViewOverlayEdgePersistence::Shared:
            return QStringLiteral("shared");
        case ToolBarItem::ViewOverlayEdgePersistence::Contextual:
            return QStringLiteral("contextual");
    }

    return QStringLiteral("by-scope");
}

ToolBarItem::ViewOverlayEdge parseToolBarViewOverlayEdge(const QString& edgeName)
{
    if (edgeName == QLatin1String("bottom")) {
        return ToolBarItem::ViewOverlayEdge::Bottom;
    }
    if (edgeName == QLatin1String("left")) {
        return ToolBarItem::ViewOverlayEdge::Left;
    }
    if (edgeName == QLatin1String("right")) {
        return ToolBarItem::ViewOverlayEdge::Right;
    }

    return ToolBarItem::ViewOverlayEdge::Top;
}

ToolBarItem::ViewOverlayEdgePersistence parseToolBarViewOverlayEdgePersistence(
    const QString& persistenceName
)
{
    if (persistenceName == QLatin1String("shared")) {
        return ToolBarItem::ViewOverlayEdgePersistence::Shared;
    }
    if (persistenceName == QLatin1String("contextual")) {
        return ToolBarItem::ViewOverlayEdgePersistence::Contextual;
    }

    return ToolBarItem::ViewOverlayEdgePersistence::ByScope;
}

ToolBarItem::ViewOverlayEdge defaultToolBarViewOverlayEdge(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::ViewOverlayEdge::Top;
    }

    if (const auto property = toolbar->property(ToolBarDefaultViewOverlayEdgeProperty);
        property.isValid()) {
        return static_cast<ToolBarItem::ViewOverlayEdge>(property.toInt());
    }

    return ToolBarManager::toolBarViewOverlayEdge(toolbar);
}

void setDefaultToolBarViewOverlayEdge(QToolBar* toolbar, ToolBarItem::ViewOverlayEdge edge)
{
    if (!toolbar) {
        return;
    }

    toolbar->setProperty(ToolBarDefaultViewOverlayEdgeProperty, static_cast<int>(edge));
}

ToolBarItem::Host defaultToolBarHost(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::Host::MainWindow;
    }

    if (const auto property = toolbar->property(ToolBarDefaultHostProperty); property.isValid()) {
        return static_cast<ToolBarItem::Host>(property.toInt());
    }

    return ToolBarManager::toolBarHost(toolbar);
}

void setDefaultToolBarHost(QToolBar* toolbar, ToolBarItem::Host host)
{
    if (!toolbar) {
        return;
    }

    toolbar->setProperty(ToolBarDefaultHostProperty, static_cast<int>(host));
}

ToolBarItem::ViewPresentation defaultToolBarViewPresentation(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::ViewPresentation::Docked;
    }

    if (const auto property = toolbar->property(ToolBarDefaultViewPresentationProperty);
        property.isValid()) {
        return static_cast<ToolBarItem::ViewPresentation>(property.toInt());
    }

    return ToolBarManager::toolBarViewPresentation(toolbar);
}

void setDefaultToolBarViewPresentation(QToolBar* toolbar, ToolBarItem::ViewPresentation presentation)
{
    if (!toolbar) {
        return;
    }

    toolbar->setProperty(ToolBarDefaultViewPresentationProperty, static_cast<int>(presentation));
}

QString toolBarVisibilityMenuLabel()
{
    return QApplication::translate("MainWindow", "Show");
}

QString toolBarMoveToMenuLabel()
{
    return QApplication::translate("MainWindow", "Move To");
}

QString toolBarPresentationMenuLabel()
{
    return QApplication::translate("MainWindow", "Presentation");
}

QString toolBarHostLabel(ToolBarItem::Host host)
{
    switch (host) {
        case ToolBarItem::Host::MainWindow:
            return QApplication::translate("MainWindow", "Main Window");
        case ToolBarItem::Host::ActiveView:
            return QApplication::translate("MainWindow", "View");
        case ToolBarItem::Host::Panel:
            return QApplication::translate("MainWindow", "Panel");
    }

    return QApplication::translate("MainWindow", "Main Window");
}

QString toolBarPanelRoleLabel(ToolBarItem::PanelRole role)
{
    switch (role) {
        case ToolBarItem::PanelRole::None:
            return QApplication::translate("MainWindow", "Panel");
        case ToolBarItem::PanelRole::ModelTree:
            return QApplication::translate("MainWindow", "Model Tree");
    }

    return QApplication::translate("MainWindow", "Panel");
}

QString toolBarViewPresentationLabel(ToolBarItem::ViewPresentation presentation)
{
    switch (presentation) {
        case ToolBarItem::ViewPresentation::Docked:
            return QApplication::translate("MainWindow", "Docked");
        case ToolBarItem::ViewPresentation::CenteredOverlay:
            return QApplication::translate("MainWindow", "Centered Overlay");
    }

    return QApplication::translate("MainWindow", "Docked");
}

QString toolBarViewOverlayPositionMenuLabel()
{
    return QApplication::translate("MainWindow", "Position");
}

QString toolBarViewOverlayEdgeLabel(ToolBarItem::ViewOverlayEdge edge)
{
    switch (edge) {
        case ToolBarItem::ViewOverlayEdge::Top:
            return QApplication::translate("MainWindow", "Top");
        case ToolBarItem::ViewOverlayEdge::Bottom:
            return QApplication::translate("MainWindow", "Bottom");
        case ToolBarItem::ViewOverlayEdge::Left:
            return QApplication::translate("MainWindow", "Left");
        case ToolBarItem::ViewOverlayEdge::Right:
            return QApplication::translate("MainWindow", "Right");
    }

    return QApplication::translate("MainWindow", "Top");
}

QMainWindow* toolBarHostWindow(const QWidget* widget)
{
    for (auto current = widget; current; current = current->parentWidget()) {
        if (auto hostWindow = qobject_cast<QMainWindow*>(const_cast<QWidget*>(current))) {
            return hostWindow;
        }
    }

    return nullptr;
}

MDIView* activeViewToolBarHostWindow()
{
    if (auto mainWindow = getMainWindow()) {
        if (auto activeWindow = mainWindow->activeWindow()) {
            return activeWindow;
        }
    }

    return qobject_cast<MDIView*>(Application::Instance->activeView());
}

TreePanel* activePanelToolBarHostPanel(ToolBarItem::PanelRole role)
{
    switch (role) {
        case ToolBarItem::PanelRole::ModelTree:
            return TreePanel::instance();
        case ToolBarItem::PanelRole::None:
            break;
    }

    return nullptr;
}

PanelToolBarHost* panelToolBarHost(TreePanel* panel, ToolBarItem::PanelRole role)
{
    if (!panel || role == ToolBarItem::PanelRole::None) {
        return nullptr;
    }

    auto* host = panel->toolBarHostWidget();
    if (host && host->panelRole() == role) {
        return host;
    }

    return nullptr;
}

QWidget* viewToolBarOverlayAnchor(MDIView* view)
{
    if (!view) {
        return nullptr;
    }

    if (auto anchor = view->centralWidget()) {
        return anchor;
    }

    return view;
}

ViewToolBarOverlayHost* viewToolBarOverlayHost(MDIView* view)
{
    auto anchor = viewToolBarOverlayAnchor(view);
    if (!anchor) {
        return nullptr;
    }

    if (auto host = anchor->findChild<QObject*>(
            QString::fromLatin1(ViewToolBarOverlayHost::ObjectName),
            Qt::FindDirectChildrenOnly
        )) {
        return static_cast<ViewToolBarOverlayHost*>(host);
    }

    return new ViewToolBarOverlayHost(anchor);
}

QString decoratedToolBarActionText(const QToolBar* toolbar)
{
    if (!toolbar) {
        return {};
    }

    auto action = toolbar->toggleViewAction();
    if (!action) {
        return {};
    }

    const auto text = action->text();
    const auto tier = ToolBarManager::toolBarTier(toolbar);
    if (tier == ToolBarItem::Tier::Recommended || tier == ToolBarItem::Tier::Contextual) {
        return text;
    }

    const auto tierLabel = ToolBarManager::toolBarTierLabel(tier);
    if (text.isEmpty() || tierLabel.isEmpty()) {
        return text;
    }

    return QApplication::translate("MainWindow", "%1 (%2)").arg(text, tierLabel);
}

QString legacyToolBarKey(const QToolBar* toolbar)
{
    if (!toolbar) {
        return {};
    }

    const auto legacyKey = toolbar->objectName();
    if (legacyKey.isEmpty() || legacyKey == ToolBarManager::toolBarPersistenceKey(toolbar)) {
        return {};
    }

    return legacyKey;
}

QString stringPropertyValue(const QObject* object, const char* propertyName)
{
    if (!object || !propertyName) {
        return {};
    }

    const auto property = object->property(propertyName);
    if (!property.isValid()) {
        return {};
    }

    return property.toString();
}

template<typename T, typename MapGetter>
QMap<QString, T> toLookup(const ParameterGrp::handle& group, MapGetter&& getMap)
{
    QMap<QString, T> values;
    if (!group) {
        return values;
    }

    for (const auto& [key, value] : getMap(group)) {
        values.insert(QString::fromUtf8(key.c_str()), static_cast<T>(value));
    }

    return values;
}

template<typename T>
bool lookupValue(const QMap<QString, T>& values, const QString& key, T* result)
{
    auto it = values.constFind(key);
    if (it == values.cend()) {
        return false;
    }

    if (result) {
        *result = it.value();
    }

    return true;
}

template<typename T>
bool lookupToolBarValue(
    const QMap<QString, T>& primaryValues,
    const QMap<QString, T>& fallbackValues,
    const QToolBar* toolbar,
    T* result
)
{
    if (!toolbar) {
        return false;
    }

    const auto key = ToolBarManager::toolBarPersistenceKey(toolbar);
    if (!key.isEmpty() && lookupValue(primaryValues, key, result)) {
        return true;
    }

    const auto legacyKey = legacyToolBarKey(toolbar);
    if (!legacyKey.isEmpty() && lookupValue(primaryValues, legacyKey, result)) {
        return true;
    }

    if (!key.isEmpty() && lookupValue(fallbackValues, key, result)) {
        return true;
    }

    if (!legacyKey.isEmpty() && lookupValue(fallbackValues, legacyKey, result)) {
        return true;
    }

    return false;
}

QStringList remapLegacyLayoutEntries(const QStringList& layout, const QMap<QString, QString>& aliases)
{
    QStringList normalized;
    for (const auto& entry : layout) {
        if (entry == QStringLiteral("Break")) {
            normalized << entry;
            continue;
        }

        const auto mappedEntry = aliases.value(entry, entry);
        if (!normalized.contains(mappedEntry)) {
            normalized << mappedEntry;
        }
    }

    return normalized;
}

void moveToolBarPreservingVisibility(QMainWindow* hostWindow, QToolBar* toolbar, Qt::ToolBarArea area)
{
    if (!hostWindow || !toolbar) {
        return;
    }

    const bool visible = toolbar->isVisible();
    if (!visible) {
        // QMainWindow does not reliably re-place hidden toolbars when restoring a saved layout.
        toolbar->setVisible(true);
    }

    hostWindow->addToolBar(area, toolbar);
    toolbar->setVisible(visible);
}
}  // namespace

ToolBarItem::ToolBarItem()
    : visibilityPolicy(DefaultVisibility::Visible)
    , _tier(defaultToolBarTier(visibilityPolicy))
{}

ToolBarItem::ToolBarItem(ToolBarItem* item, DefaultVisibility visibilityPolicy)
    : visibilityPolicy(visibilityPolicy)
    , _tier(defaultToolBarTier(visibilityPolicy))
{
    if (item) {
        item->appendItem(this);
    }
}

ToolBarItem::~ToolBarItem()
{
    clear();
}

void ToolBarItem::setCommand(const std::string& name)
{
    _name = name;
}

const std::string& ToolBarItem::command() const
{
    return _name;
}

bool ToolBarItem::hasPersistenceKey() const
{
    return !_persistenceKey.empty();
}

void ToolBarItem::setPersistenceKey(const std::string& key)
{
    _persistenceKey = key;
}

const std::string& ToolBarItem::persistenceKey() const
{
    if (_persistenceKey.empty()) {
        return _name;
    }

    return _persistenceKey;
}

bool ToolBarManager::PersistenceId::isEmpty() const
{
    return toolbar.isEmpty();
}

bool ToolBarManager::ToolbarScopeId::isEmpty() const
{
    return scope == Scope::Legacy && workbench.isEmpty() && context.isEmpty();
}

ToolBarManager::ToolbarScopeId ToolBarManager::PersistenceId::toolbarScopeId() const
{
    return scopeId;
}

void ToolBarItem::setTier(Tier tier)
{
    _tier = tier;
}

ToolBarItem::Tier ToolBarItem::tier() const
{
    return _tier;
}

void ToolBarItem::setHost(Host host)
{
    _host = host;
}

ToolBarItem::Host ToolBarItem::host() const
{
    return _host;
}

void ToolBarItem::setPanelRole(PanelRole role)
{
    _panelRole = role;
}

ToolBarItem::PanelRole ToolBarItem::panelRole() const
{
    return _panelRole;
}

void ToolBarItem::setViewHostRequirement(ViewHostRequirement requirement)
{
    _viewHostRequirement = requirement;
}

ToolBarItem::ViewHostRequirement ToolBarItem::viewHostRequirement() const
{
    return _viewHostRequirement;
}

void ToolBarItem::setViewPresentation(ViewPresentation presentation)
{
    _viewPresentation = presentation;
}

ToolBarItem::ViewPresentation ToolBarItem::viewPresentation() const
{
    return _viewPresentation;
}

void ToolBarItem::setViewOverlayEdge(ViewOverlayEdge edge)
{
    _viewOverlayEdge = edge;
}

ToolBarItem::ViewOverlayEdge ToolBarItem::viewOverlayEdge() const
{
    return _viewOverlayEdge;
}

void ToolBarItem::setViewOverlayEdgePersistence(ViewOverlayEdgePersistence persistence)
{
    _viewOverlayEdgePersistence = persistence;
}

ToolBarItem::ViewOverlayEdgePersistence ToolBarItem::viewOverlayEdgePersistence() const
{
    return _viewOverlayEdgePersistence;
}

bool ToolBarItem::hasItems() const
{
    return !_items.isEmpty();
}

ToolBarItem* ToolBarItem::findItem(const std::string& name)
{
    if (_name == name) {
        return this;
    }

    for (auto it : std::as_const(_items)) {
        if (it->_name == name) {
            return it;
        }
    }

    return nullptr;
}

ToolBarItem* ToolBarItem::copy() const
{
    auto root = new ToolBarItem;
    root->setCommand(command());
    if (!_persistenceKey.empty()) {
        root->setPersistenceKey(_persistenceKey);
    }
    root->setTier(_tier);
    root->setHost(_host);
    root->setPanelRole(_panelRole);
    root->setViewHostRequirement(_viewHostRequirement);
    root->setViewPresentation(_viewPresentation);
    root->setViewOverlayEdge(_viewOverlayEdge);
    root->setViewOverlayEdgePersistence(_viewOverlayEdgePersistence);

    QList<ToolBarItem*> items = getItems();
    for (auto it : items) {
        root->appendItem(it->copy());
    }

    return root;
}

uint ToolBarItem::count() const
{
    return _items.count();
}

void ToolBarItem::appendItem(ToolBarItem* item)
{
    _items.push_back(item);
}

bool ToolBarItem::insertItem(ToolBarItem* before, ToolBarItem* item)
{
    int pos = _items.indexOf(before);
    if (pos != -1) {
        _items.insert(pos, item);
        return true;
    }

    return false;
}

void ToolBarItem::removeItem(ToolBarItem* item)
{
    int pos = _items.indexOf(item);
    if (pos != -1) {
        _items.removeAt(pos);
    }
}

void ToolBarItem::clear()
{
    for (auto it : std::as_const(_items)) {
        delete it;
    }

    _items.clear();
}

ToolBarItem& ToolBarItem::operator<<(ToolBarItem* item)
{
    appendItem(item);
    return *this;
}

ToolBarItem& ToolBarItem::operator<<(const std::string& command)
{
    auto item = new ToolBarItem(this);
    item->setCommand(command);
    return *this;
}

QList<ToolBarItem*> ToolBarItem::getItems() const
{
    return _items;
}

// -----------------------------------------------------------

ToolBar::ToolBar()
    : QToolBar()
{
    setupConnections();
}

ToolBar::ToolBar(QWidget* parent)
    : QToolBar(parent)
{
    setupConnections();
}

void ToolBar::undock()
{
    {
        // We want to block only some signals - topLevelChanged should still be propagated
        QSignalBlocker blocker(this);

        if (auto area = ToolBarManager::getInstance()->toolBarAreaWidget(this)) {
            area->removeWidget(this);
            getMainWindow()->addToolBar(this);
        }

        setWindowFlags(Qt::Tool | Qt::FramelessWindowHint | Qt::X11BypassWindowManagerHint);
        adjustSize();
        setVisible(true);
    }

    Q_EMIT topLevelChanged(true);
}

void ToolBar::updateCustomGripVisibility()
{
    auto area = ToolBarManager::getInstance()->toolBarAreaWidget(this);
    auto grip = findChild<ToolBarGrip*>();

    auto customGripIsRequired = isMovable() && area;

    if (grip && !customGripIsRequired) {
        grip->detach();
        grip->deleteLater();
    }
    else if (!grip && customGripIsRequired) {
        grip = new ToolBarGrip(this);
        grip->attach();
    }
    else {
        // either grip is present and should be present
        // or is not present and should not be - nothing to do
        return;
    }
}

void Gui::ToolBar::setupConnections()
{
    connect(this, &QToolBar::topLevelChanged, this, &ToolBar::updateCustomGripVisibility);
    connect(this, &QToolBar::movableChanged, this, &ToolBar::updateCustomGripVisibility);
}

// -----------------------------------------------------------

ToolBarGrip::ToolBarGrip(QToolBar* parent)
    : QWidget(parent)
{
    updateSize();
}

void ToolBarGrip::attach()
{
    if (isAttached()) {
        return;
    }

    auto parent = qobject_cast<ToolBar*>(parentWidget());

    if (!parent) {
        return;
    }

    auto actions = parent->actions();

    _action = parent->insertWidget(
        // ensure that grip is always placed as the first widget in the toolbar
        actions.isEmpty() ? nullptr : actions[0],
        this
    );

    setCursor(Qt::OpenHandCursor);
    setMouseTracking(true);
    setVisible(true);
}

void ToolBarGrip::detach()
{
    if (!isAttached()) {
        return;
    }

    auto parent = qobject_cast<ToolBar*>(parentWidget());

    if (!parent) {
        return;
    }

    parent->removeAction(_action);
}

bool ToolBarGrip::isAttached() const
{
    return _action != nullptr;
}

void ToolBarGrip::paintEvent(QPaintEvent*)
{
    QPainter painter(this);

    if (auto toolbar = qobject_cast<ToolBar*>(parentWidget())) {
        QStyle* style = toolbar->style();
        QStyleOptionToolBar opt;

        toolbar->initStyleOption(&opt);

        opt.features = QStyleOptionToolBar::Movable;
        opt.rect = rect();

        style->drawPrimitive(QStyle::PE_IndicatorToolBarHandle, &opt, &painter, toolbar);
    }
}

void ToolBarGrip::mouseMoveEvent(QMouseEvent* me)
{
    auto toolbar = qobject_cast<ToolBar*>(parentWidget());
    if (!toolbar) {
        return;
    }

    auto area = ToolBarManager::getInstance()->toolBarAreaWidget(toolbar);
    if (!area) {
        return;
    }

#if QT_VERSION < QT_VERSION_CHECK(6, 0, 0)
    QPoint pos = me->globalPos();
#else
    QPoint pos = me->globalPosition().toPoint();
#endif
    QRect rect(toolbar->mapToGlobal(QPoint(0, 0)), toolbar->size());

    // if mouse did not leave the area of toolbar do not continue with undocking it
    if (rect.contains(pos)) {
        return;
    }

    toolbar->undock();

    // After removing from area, this grip will be deleted. In order to
    // continue toolbar dragging (because the mouse button is still pressed),
    // we fake mouse events and send to toolbar. For some reason,
    // send/postEvent() does not work, only timer works.
    QPointer tb(toolbar);
    QTimer::singleShot(0, [tb] {
        auto modifiers = QApplication::queryKeyboardModifiers();
        auto buttons = QApplication::mouseButtons();
        if (buttons != Qt::LeftButton || QWidget::mouseGrabber() || modifiers != Qt::NoModifier
            || !tb) {
            return;
        }

        QPoint pos(10, 10);
        QPoint globalPos(tb->mapToGlobal(pos));
        QMouseEvent mouseEvent(QEvent::MouseButtonPress, pos, globalPos, Qt::LeftButton, buttons, modifiers);
        QApplication::sendEvent(tb, &mouseEvent);

        // Mouse follow the mouse press event with mouse move with some offset
        // in order to activate toolbar dragging.
        QPoint offset(30, 30);
        QMouseEvent mouseMoveEvent(
            QEvent::MouseMove,
            pos + offset,
            globalPos + offset,
            Qt::LeftButton,
            buttons,
            modifiers
        );
        QApplication::sendEvent(tb, &mouseMoveEvent);
    });
}

void ToolBarGrip::mousePressEvent(QMouseEvent*)
{
    setCursor(Qt::ClosedHandCursor);
}

void ToolBarGrip::mouseReleaseEvent(QMouseEvent*)
{
    setCursor(Qt::OpenHandCursor);
}

void ToolBarGrip::updateSize()
{
    auto parent = qobject_cast<ToolBar*>(parentWidget());

    if (!parent) {
        return;
    }

    QStyle* style = parent->style();
    QStyleOptionToolBar opt;

    parent->initStyleOption(&opt);
    opt.features = QStyleOptionToolBar::Movable;

    setFixedWidth(style->subElementRect(QStyle::SE_ToolBarHandle, &opt, parent).width() + 4);
}

// -----------------------------------------------------------

ToolBarManager* ToolBarManager::_instance = nullptr;  // NOLINT

ToolBarManager* ToolBarManager::getInstance()
{
    if (!_instance) {
        _instance = new ToolBarManager;
    }
    return _instance;
}

QString ToolBarManager::toolBarPersistenceKey(const ToolBarItem* item)
{
    if (!item) {
        return {};
    }

    return QString::fromUtf8(item->persistenceKey().c_str());
}

QString ToolBarManager::toolBarPersistenceKey(const QToolBar* toolbar)
{
    if (!toolbar) {
        return {};
    }

    for (const auto* propertyName :
         {ToolBarPublicPersistenceKeyProperty, ToolBarPersistenceKeyProperty}) {
        const auto key = stringPropertyValue(toolbar, propertyName);
        if (!key.isEmpty()) {
            return key;
        }
    }

    return toolbar->objectName();
}

ToolBarManager::PersistenceId ToolBarManager::toolBarPersistenceId(const QString& persistenceKey)
{
    return makeToolBarPersistenceId(persistenceKey);
}

ToolBarManager::PersistenceId ToolBarManager::toolBarPersistenceId(const ToolBarItem* item)
{
    return toolBarPersistenceId(toolBarPersistenceKey(item));
}

ToolBarManager::PersistenceId ToolBarManager::toolBarPersistenceId(const QToolBar* toolbar)
{
    return toolBarPersistenceId(toolBarPersistenceKey(toolbar));
}

ToolBarManager::ToolbarScopeId ToolBarManager::layoutContextId(const QString& context)
{
    if (context.isEmpty()) {
        return {};
    }

    if (context.startsWith(QStringLiteral("ctx:"))) {
        const auto parts = context.split(QLatin1Char(':'), Qt::KeepEmptyParts);
        if (parts.size() >= 3) {
            return {Scope::Contextual, parts.at(1), parts.mid(2).join(QLatin1Char(':'))};
        }

        return {};
    }

    return {Scope::Workbench, context, {}};
}

QString ToolBarManager::makeToolBarLayoutContext(const ToolbarScopeId& scopeId)
{
    return serializeLayoutContextId(scopeId);
}

QString ToolBarManager::makeToolBarPersistenceKey(const PersistenceId& id)
{
    return serializeToolBarPersistenceId(id);
}

ToolBarManager::ToolbarScopeId ToolBarManager::toolBarScopeId(const QString& persistenceKey)
{
    return toolBarPersistenceId(persistenceKey).toolbarScopeId();
}

ToolBarManager::ToolbarScopeId ToolBarManager::toolBarScopeId(const ToolBarItem* item)
{
    return toolBarScopeId(toolBarPersistenceKey(item));
}

ToolBarManager::ToolbarScopeId ToolBarManager::toolBarScopeId(const QToolBar* toolbar)
{
    return toolBarScopeId(toolBarPersistenceKey(toolbar));
}

QString ToolBarManager::toolBarScopeLabel(const QString& persistenceKey)
{
    return ::toolBarScopeLabel(toolBarScopeId(persistenceKey).scope);
}

QString ToolBarManager::toolBarScopeLabel(const ToolBarItem* item)
{
    return toolBarScopeLabel(toolBarPersistenceKey(item));
}

QString ToolBarManager::toolBarScopeLabel(const QToolBar* toolbar)
{
    return toolBarScopeLabel(toolBarPersistenceKey(toolbar));
}

ToolBarItem::Tier ToolBarManager::toolBarTier(const ToolBarItem* item)
{
    if (!item) {
        return ToolBarItem::Tier::Recommended;
    }

    return item->tier();
}

ToolBarItem::Tier ToolBarManager::toolBarTier(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::Tier::Recommended;
    }

    auto property = toolbar->property(ToolBarTierProperty);
    if (property.isValid()) {
        return static_cast<ToolBarItem::Tier>(property.toInt());
    }

    auto publicProperty = toolbar->property(ToolBarPublicTierProperty);
    if (publicProperty.isValid()) {
        return parseToolBarTier(publicProperty.toString());
    }

    auto scope = toolBarScopeId(toolbar).scope;
    if (scope == Scope::Contextual) {
        return ToolBarItem::Tier::Contextual;
    }

    return ToolBarItem::Tier::Recommended;
}

ToolBarItem::Host ToolBarManager::toolBarHost(const ToolBarItem* item)
{
    if (!item) {
        return ToolBarItem::Host::MainWindow;
    }

    return item->host();
}

ToolBarItem::Host ToolBarManager::toolBarHost(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::Host::MainWindow;
    }

    if (const auto hostName = stringPropertyValue(toolbar, ToolBarPublicHostProperty);
        !hostName.isEmpty()) {
        return parseToolBarHost(hostName);
    }

    if (const auto property = toolbar->property(ToolBarHostProperty); property.isValid()) {
        return static_cast<ToolBarItem::Host>(property.toInt());
    }

    return ToolBarItem::Host::MainWindow;
}

QString ToolBarManager::toolBarPanelRoleName(ToolBarItem::PanelRole role)
{
    return ::toolBarPanelRoleName(role);
}

ToolBarItem::PanelRole ToolBarManager::toolBarPanelRole(const ToolBarItem* item)
{
    if (!item) {
        return ToolBarItem::PanelRole::None;
    }

    return item->panelRole();
}

ToolBarItem::PanelRole ToolBarManager::toolBarPanelRole(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::PanelRole::None;
    }

    if (const auto roleName = stringPropertyValue(toolbar, ToolBarPublicPanelRoleProperty);
        !roleName.isEmpty()) {
        return parseToolBarPanelRole(roleName);
    }

    if (const auto property = toolbar->property(ToolBarPanelRoleProperty); property.isValid()) {
        return static_cast<ToolBarItem::PanelRole>(property.toInt());
    }

    return ToolBarItem::PanelRole::None;
}

ToolBarItem::ViewHostRequirement ToolBarManager::toolBarViewHostRequirement(const ToolBarItem* item)
{
    if (!item) {
        return ToolBarItem::ViewHostRequirement::AnyView;
    }

    return item->viewHostRequirement();
}

ToolBarItem::ViewHostRequirement ToolBarManager::toolBarViewHostRequirement(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::ViewHostRequirement::AnyView;
    }

    if (const auto property = toolbar->property(ToolBarViewHostRequirementProperty);
        property.isValid()) {
        return static_cast<ToolBarItem::ViewHostRequirement>(property.toInt());
    }

    return ToolBarItem::ViewHostRequirement::AnyView;
}

QString ToolBarManager::toolBarViewPresentationName(ToolBarItem::ViewPresentation presentation)
{
    return ::toolBarViewPresentationName(presentation);
}

ToolBarItem::ViewPresentation ToolBarManager::toolBarViewPresentation(const ToolBarItem* item)
{
    if (!item) {
        return ToolBarItem::ViewPresentation::Docked;
    }

    return item->viewPresentation();
}

ToolBarItem::ViewPresentation ToolBarManager::toolBarViewPresentation(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::ViewPresentation::Docked;
    }

    if (const auto presentationName
        = stringPropertyValue(toolbar, ToolBarPublicViewPresentationProperty);
        !presentationName.isEmpty()) {
        return parseToolBarViewPresentation(presentationName);
    }

    if (const auto property = toolbar->property(ToolBarViewPresentationProperty); property.isValid()) {
        return static_cast<ToolBarItem::ViewPresentation>(property.toInt());
    }

    return ToolBarItem::ViewPresentation::Docked;
}

QString ToolBarManager::toolBarViewOverlayEdgeName(ToolBarItem::ViewOverlayEdge edge)
{
    return ::toolBarViewOverlayEdgeName(edge);
}

ToolBarItem::ViewOverlayEdge ToolBarManager::toolBarViewOverlayEdge(const ToolBarItem* item)
{
    if (!item) {
        return ToolBarItem::ViewOverlayEdge::Top;
    }

    return item->viewOverlayEdge();
}

ToolBarItem::ViewOverlayEdge ToolBarManager::toolBarViewOverlayEdge(const QToolBar* toolbar)
{
    if (!toolbar) {
        return ToolBarItem::ViewOverlayEdge::Top;
    }

    if (const auto edgeName = stringPropertyValue(toolbar, ToolBarPublicViewOverlayEdgeProperty);
        !edgeName.isEmpty()) {
        return parseToolBarViewOverlayEdge(edgeName);
    }

    if (const auto property = toolbar->property(ToolBarViewOverlayEdgeProperty); property.isValid()) {
        return static_cast<ToolBarItem::ViewOverlayEdge>(property.toInt());
    }

    return ToolBarItem::ViewOverlayEdge::Top;
}

QString ToolBarManager::toolBarViewOverlayEdgePersistenceName(
    ToolBarItem::ViewOverlayEdgePersistence persistence
)
{
    return ::toolBarViewOverlayEdgePersistenceName(persistence);
}

ToolBarItem::ViewOverlayEdgePersistence ToolBarManager::toolBarViewOverlayEdgePersistence(
    const ToolBarItem* item
)
{
    if (!item) {
        return ToolBarItem::ViewOverlayEdgePersistence::ByScope;
    }

    return item->viewOverlayEdgePersistence();
}

ToolBarItem::ViewOverlayEdgePersistence ToolBarManager::toolBarViewOverlayEdgePersistence(
    const QToolBar* toolbar
)
{
    if (!toolbar) {
        return ToolBarItem::ViewOverlayEdgePersistence::ByScope;
    }

    if (const auto persistenceName
        = stringPropertyValue(toolbar, ToolBarPublicViewOverlayEdgePersistenceProperty);
        !persistenceName.isEmpty()) {
        return parseToolBarViewOverlayEdgePersistence(persistenceName);
    }

    if (const auto property = toolbar->property(ToolBarViewOverlayEdgePersistenceProperty);
        property.isValid()) {
        return static_cast<ToolBarItem::ViewOverlayEdgePersistence>(property.toInt());
    }

    return ToolBarItem::ViewOverlayEdgePersistence::ByScope;
}

ToolBarItem::Tier ToolBarManager::normalizeCustomToolBarTier(ToolBarItem::Tier tier)
{
    switch (tier) {
        case ToolBarItem::Tier::Recommended:
        case ToolBarItem::Tier::Secondary:
        case ToolBarItem::Tier::Advanced:
            return tier;
        case ToolBarItem::Tier::Contextual:
            return ToolBarItem::Tier::Secondary;
    }

    return ToolBarItem::Tier::Secondary;
}

ToolBarItem::Tier ToolBarManager::customToolBarTierFromName(const QString& tierName)
{
    if (tierName.isEmpty()) {
        return ToolBarItem::Tier::Secondary;
    }

    return normalizeCustomToolBarTier(parseToolBarTier(tierName));
}

ToolBarItem::Tier ToolBarManager::toolBarTierFromName(const QString& tierName)
{
    return parseToolBarTier(tierName);
}

QString ToolBarManager::toolBarTierName(ToolBarItem::Tier tier)
{
    return ::toolBarTierName(tier);
}

QString ToolBarManager::toolBarTierLabel(ToolBarItem::Tier tier)
{
    return ::toolBarTierLabel(tier);
}

QString ToolBarManager::toolBarTierLabel(const ToolBarItem* item)
{
    return toolBarTierLabel(toolBarTier(item));
}

QString ToolBarManager::toolBarTierLabel(const QToolBar* toolbar)
{
    return toolBarTierLabel(toolBarTier(toolbar));
}

QString ToolBarManager::toolBarHostName(ToolBarItem::Host host)
{
    return ::toolBarHostName(host);
}

QString ToolBarManager::toolBarPanelRoleLabel(ToolBarItem::PanelRole role)
{
    return ::toolBarPanelRoleLabel(role);
}

void ToolBarManager::setToolBarPersistenceKey(QToolBar* toolbar, const QString& key)
{
    if (!toolbar) {
        return;
    }

    toolbar->setProperty(ToolBarPersistenceKeyProperty, key);
    toolbar->setProperty(ToolBarPublicPersistenceKeyProperty, key);
    toolbar->toggleViewAction()->setProperty(ToolBarPublicPersistenceKeyProperty, key);
}

void ToolBarManager::setToolBarTier(QToolBar* toolbar, ToolBarItem::Tier tier)
{
    if (!toolbar) {
        return;
    }

    toolbar->setProperty(ToolBarTierProperty, static_cast<int>(tier));
    toolbar->setProperty(ToolBarPublicTierProperty, toolBarTierName(tier));
    toolbar->toggleViewAction()->setProperty(ToolBarPublicTierProperty, toolBarTierName(tier));
}

void ToolBarManager::setToolBarHost(QToolBar* toolbar, ToolBarItem::Host host)
{
    if (!toolbar) {
        return;
    }

    const auto hostName = toolBarHostName(host);
    toolbar->setProperty(ToolBarHostProperty, static_cast<int>(host));
    toolbar->setProperty(ToolBarPublicHostProperty, hostName);
    toolbar->toggleViewAction()->setProperty(ToolBarPublicHostProperty, hostName);
}

void ToolBarManager::setToolBarPanelRole(QToolBar* toolbar, ToolBarItem::PanelRole role)
{
    if (!toolbar) {
        return;
    }

    const auto roleName = toolBarPanelRoleName(role);
    toolbar->setProperty(ToolBarPanelRoleProperty, static_cast<int>(role));
    toolbar->setProperty(ToolBarPublicPanelRoleProperty, roleName);
    toolbar->toggleViewAction()->setProperty(ToolBarPublicPanelRoleProperty, roleName);
}

void ToolBarManager::setToolBarViewPresentation(
    QToolBar* toolbar,
    ToolBarItem::ViewPresentation presentation
)
{
    if (!toolbar) {
        return;
    }

    const auto presentationName = toolBarViewPresentationName(presentation);
    toolbar->setProperty(ToolBarViewPresentationProperty, static_cast<int>(presentation));
    toolbar->setProperty(ToolBarPublicViewPresentationProperty, presentationName);
    toolbar->toggleViewAction()->setProperty(ToolBarPublicViewPresentationProperty, presentationName);
}

void ToolBarManager::setToolBarViewOverlayEdge(QToolBar* toolbar, ToolBarItem::ViewOverlayEdge edge)
{
    if (!toolbar) {
        return;
    }

    const auto edgeName = toolBarViewOverlayEdgeName(edge);
    toolbar->setProperty(ToolBarViewOverlayEdgeProperty, static_cast<int>(edge));
    toolbar->setProperty(ToolBarPublicViewOverlayEdgeProperty, edgeName);
    toolbar->toggleViewAction()->setProperty(ToolBarPublicViewOverlayEdgeProperty, edgeName);
}

void ToolBarManager::setToolBarViewOverlayEdgePersistence(
    QToolBar* toolbar,
    ToolBarItem::ViewOverlayEdgePersistence persistence
)
{
    if (!toolbar) {
        return;
    }

    const auto persistenceName = toolBarViewOverlayEdgePersistenceName(persistence);
    toolbar->setProperty(ToolBarViewOverlayEdgePersistenceProperty, static_cast<int>(persistence));
    toolbar->setProperty(ToolBarPublicViewOverlayEdgePersistenceProperty, persistenceName);
    toolbar->toggleViewAction()->setProperty(
        ToolBarPublicViewOverlayEdgePersistenceProperty,
        persistenceName
    );
}

void ToolBarManager::destruct()
{
    delete _instance;
    _instance = nullptr;
}

ToolBarManager::ToolBarManager()
{
    setupParameters();
    setupStatusBar();
    setupMenuBar();

    setupSizeTimer();
    setupResizeTimer();
    setupConnection();
    setupTimer();
    setupMenuBarTimer();

    setupWidgetProducers();
}

ToolBarManager::~ToolBarManager() = default;

void ToolBarManager::setupParameters()
{
    auto& mgr = App::GetApplication().GetUserParameter();
    hGeneral = mgr.GetGroup("BaseApp/Preferences/General");
    hMainWindow = mgr.GetGroup("BaseApp/Preferences/MainWindow");
    hWorkbenchLayouts = mgr.GetGroup("BaseApp/MainWindow/WorkbenchLayouts");
    hGlobalStatusBar = mgr.GetGroup("BaseApp/MainWindow/StatusBar");
    hGlobalMenuBarRight = mgr.GetGroup("BaseApp/MainWindow/MenuBarRight");
    hGlobalMenuBarLeft = mgr.GetGroup("BaseApp/MainWindow/MenuBarLeft");
    hStatusBar = hGlobalStatusBar;
    hMenuBarRight = hGlobalMenuBarRight;
    hMenuBarLeft = hGlobalMenuBarLeft;
    hPref = mgr.GetGroup("BaseApp/MainWindow/Toolbars");
}

void ToolBarManager::setupStatusBar()
{
    if (auto sb = getMainWindow()->statusBar()) {
        sb->installEventFilter(this);
        statusBarAreaWidget = new ToolBarAreaWidget(
            sb,
            ToolBarArea::StatusBarToolBarArea,
            hStatusBar,
            paramHandlers.connection()
        );
        statusBarAreaWidget->setObjectName(QStringLiteral("StatusBarArea"));
        sb->insertPermanentWidget(2, statusBarAreaWidget);
        statusBarAreaWidget->show();
    }
}

void ToolBarManager::setupMenuBar()
{
    if (auto mb = getMainWindow()->menuBar()) {
        mb->installEventFilter(this);
        menuBarLeftAreaWidget = new ToolBarAreaWidget(
            mb,
            ToolBarArea::LeftMenuToolBarArea,
            hMenuBarLeft,
            paramHandlers.connection(),
            &menuBarTimer
        );
        menuBarLeftAreaWidget->setObjectName(QStringLiteral("MenuBarLeftArea"));
        mb->setCornerWidget(menuBarLeftAreaWidget, Qt::TopLeftCorner);
        menuBarLeftAreaWidget->show();
        menuBarRightAreaWidget = new ToolBarAreaWidget(
            mb,
            ToolBarArea::RightMenuToolBarArea,
            hMenuBarRight,
            paramHandlers.connection(),
            &menuBarTimer
        );
        menuBarRightAreaWidget->setObjectName(QStringLiteral("MenuBarRightArea"));
        mb->setCornerWidget(menuBarRightAreaWidget, Qt::TopRightCorner);
        menuBarRightAreaWidget->show();
    }
}

void ToolBarManager::setupConnection()
{
    auto refreshParams = [this](const char* name) {
        bool sizeChanged = false;
        if (!name || boost::equals(name, "ToolbarIconSize")) {
            _toolBarIconSize = hGeneral->GetInt("ToolbarIconSize", 24);
            sizeChanged = true;
        }
        if (!name || boost::equals(name, "StatusBarIconSize")) {
            _statusBarIconSize = hGeneral->GetInt("StatusBarIconSize", 0);
            sizeChanged = true;
        }
        if (!name || boost::equals(name, "MenuBarIconSize")) {
            _menuBarIconSize = hGeneral->GetInt("MenuBarIconSize", 0);
            sizeChanged = true;
        }
        if (sizeChanged) {
            sizeTimer.start(100);
        }
    };

    refreshParams(nullptr);
    paramHandlers.addHandler(hGeneral, "ToolbarIconSize", [refreshParams](const ParamKey* key) {
        refreshParams(key ? key->key : nullptr);
    });
    paramHandlers.addHandler(hGeneral, "StatusBarIconSize", [refreshParams](const ParamKey* key) {
        refreshParams(key ? key->key : nullptr);
    });
    paramHandlers.addHandler(hGeneral, "MenuBarIconSize", [refreshParams](const ParamKey* key) {
        refreshParams(key ? key->key : nullptr);
    });
    paramHandlers.addGroupHandler(hPref, [this](const ParamKey* key) {
        onToolbarParametersChanged(key);
    });
    paramHandlers.addGroupHandler(hStatusBar, [this](const ParamKey* key) {
        onToolbarParametersChanged(key);
    });
    paramHandlers.addGroupHandler(hMenuBarRight, [this](const ParamKey* key) {
        onToolbarParametersChanged(key);
    });
    paramHandlers.addGroupHandler(hMenuBarLeft, [this](const ParamKey* key) {
        onToolbarParametersChanged(key);
    });
    connectActivateView = Application::Instance->signalActivateView.connect([this](const MDIView*) {
        refreshViewHostedToolBars();
    });
}

void ToolBarManager::onToolbarParametersChanged(const ParamKey*)
{
    if (blockRestore) {
        blockRestore = false;
    }
    else {
        timer.start(100);
    }
}

void ToolBarManager::setupTimer()
{
    timer.setSingleShot(true);
    connect(&timer, &QTimer::timeout, [this] { onTimer(); });
}

void ToolBarManager::setupSizeTimer()
{
    sizeTimer.setSingleShot(true);
    connect(&sizeTimer, &QTimer::timeout, [this] { setupToolBarIconSize(); });
}

void ToolBarManager::setupResizeTimer()
{
    resizeTimer.setSingleShot(true);
    connect(&resizeTimer, &QTimer::timeout, [this] {
        for (const auto& [toolbar, guard] : resizingToolbars) {
            if (guard) {
                setToolBarIconSize(toolbar);
            }
        }
        resizingToolbars.clear();
    });
}

void ToolBarManager::setupMenuBarTimer()
{
    menuBarTimer.setSingleShot(true);
    QObject::connect(&menuBarTimer, &QTimer::timeout, [] {
        if (auto menuBar = getMainWindow()->menuBar()) {
            menuBar->adjustSize();
        }
    });
}

void Gui::ToolBarManager::setupWidgetProducers()
{
    new WidgetProducer<Gui::ToolBar>;
}

QString ToolBarManager::activeToolbarLayoutContext() const
{
    auto active = WorkbenchManager::instance()->active();
    if (!active) {
        return {};
    }

    return QString::fromUtf8(active->name().c_str());
}

QString ToolBarManager::effectiveToolbarLayoutContext() const
{
    auto activeContext = activeToolbarLayoutContext();
    if (!toolbarLayoutContextOverride.isEmpty() && !toolbarLayoutContextOverrideWorkbench.isEmpty()
        && toolbarLayoutContextOverrideWorkbench == activeContext) {
        return toolbarLayoutContextOverride;
    }

    return activeContext;
}

ToolBarManager::CurrentLayoutScope ToolBarManager::currentToolbarLayoutScope(
    QString* layoutContext,
    QString* activeContext
) const
{
    const auto currentLayoutContext = effectiveToolbarLayoutContext();
    if (layoutContext) {
        *layoutContext = currentLayoutContext;
    }

    if (currentLayoutContext.isEmpty()) {
        if (activeContext) {
            activeContext->clear();
        }
        return CurrentLayoutScope::None;
    }

    const auto currentLayout = layoutContextId(currentLayoutContext);
    if (currentLayout.isEmpty()) {
        if (activeContext) {
            activeContext->clear();
        }
        return CurrentLayoutScope::None;
    }

    const auto currentActiveContext = activeToolbarLayoutContext();
    if (activeContext) {
        *activeContext = currentActiveContext;
    }

    return currentLayout.scope == Scope::Contextual ? CurrentLayoutScope::Contextual
                                                    : CurrentLayoutScope::Workbench;
}

bool ToolBarManager::rememberToolbarLayoutByWorkbench() const
{
    return hMainWindow->GetBool("RememberToolbarLayoutByWorkbench", false);
}

bool ToolBarManager::hasViewHostedToolBars() const
{
    auto activeView = activeViewToolBarHostWindow();
    for (auto toolbar : toolBars()) {
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::ActiveView
            || !activeViewSupportsToolBarHost(toolbar, activeView)) {
            continue;
        }
        return true;
    }

    return false;
}

bool ToolBarManager::activeViewSupportsToolBarHost(const QToolBar* toolbar, const MDIView* view) const
{
    if (!toolbar || !view) {
        return false;
    }

    switch (toolBarViewHostRequirement(toolbar)) {
        case ToolBarItem::ViewHostRequirement::AnyView:
            return true;
        case ToolBarItem::ViewHostRequirement::View3D:
            return view->isDerivedFrom<View3DInventor>() || view->isDerivedFrom<AbstractSplitView>();
    }

    return false;
}

bool ToolBarManager::activePanelSupportsToolBarHost(const QToolBar* toolbar, const TreePanel* panel) const
{
    if (!toolbar || !panel) {
        return false;
    }

    switch (toolBarPanelRole(toolbar)) {
        case ToolBarItem::PanelRole::ModelTree:
            return panel->toolBarHostWidget() != nullptr;
        case ToolBarItem::PanelRole::None:
            break;
    }

    return false;
}
bool ToolBarManager::hasSavedWorkbenchToolBarLayout(const QString& context) const
{
    auto group = workbenchLayoutGroup(context);
    return group && group->GetBool("Saved", false);
}

bool ToolBarManager::hasSavedViewToolBarLayout(const QString& context) const
{
    const auto hasSavedEntriesForViewToolBars = [this](const ParameterGrp::handle& group) {
        if (!group) {
            return false;
        }

        for (auto toolbar : toolBars()) {
            if (!toolbar) {
                continue;
            }
            if (defaultToolBarHost(toolbar) != ToolBarItem::Host::ActiveView
                && toolBarHost(toolbar) != ToolBarItem::Host::ActiveView) {
                continue;
            }

            const auto key = toolBarPersistenceKey(toolbar);
            if (key.isEmpty()) {
                continue;
            }
            const auto value = QString::fromUtf8(group->GetASCII(key.toUtf8().constData()).c_str());
            if (!value.isEmpty()) {
                return true;
            }
        }

        return false;
    };

    if (hasSavedEntriesForViewToolBars(globalHostedToolBarHostGroup())) {
        return true;
    }
    if (hasSavedEntriesForViewToolBars(globalViewToolBarPresentationGroup())) {
        return true;
    }
    if (hasSavedEntriesForViewToolBars(sharedViewOverlayEdgeGroup())) {
        return true;
    }

    auto group = workbenchLayoutGroup(context);
    if (!group || !group->GetBool("Saved", false)) {
        if (hasSavedEntriesForViewToolBars(hostedToolBarHostGroup(context))) {
            return true;
        }
        if (hasSavedEntriesForViewToolBars(viewToolBarPresentationGroup(context))) {
            return true;
        }
        if (hasSavedEntriesForViewToolBars(viewOverlayEdgeGroup(context))) {
            return true;
        }
        return false;
    }

    return !splitLayoutState(group->GetASCII(ViewTopLayoutKey)).isEmpty()
        || !splitLayoutState(group->GetASCII(ViewLeftLayoutKey)).isEmpty()
        || !splitLayoutState(group->GetASCII(ViewRightLayoutKey)).isEmpty()
        || !splitLayoutState(group->GetASCII(ViewBottomLayoutKey)).isEmpty()
        || hasSavedEntriesForViewToolBars(hostedToolBarHostGroup(context))
        || hasSavedEntriesForViewToolBars(viewToolBarPresentationGroup(context))
        || hasSavedEntriesForViewToolBars(viewOverlayEdgeGroup(context));
}

bool ToolBarManager::toolbarBelongsToLayoutContext(const QToolBar* toolbar, const QString& context) const
{
    if (!toolbar || context.isEmpty()) {
        return false;
    }

    const auto toolbarScope = toolBarScopeId(toolbar);
    const auto layoutScope = layoutContextId(context);
    return toolbarScope.scope == layoutScope.scope && toolbarScope.workbench == layoutScope.workbench
        && toolbarScope.context == layoutScope.context;
}

void ToolBarManager::initializeUnsavedToolbarLayoutContext(const QString& context)
{
    if (!rememberToolbarLayoutByWorkbench() || context.isEmpty()
        || hasSavedWorkbenchToolBarLayout(context)) {
        return;
    }

    Base::ConnectionBlocker block(paramHandlers.connection());
    const QList<ToolBar*> toolbars = toolBars();
    for (const auto& key : toolbarKeys) {
        auto toolbar = findToolBar(toolbars, key);
        if (!toolbar || !toolbarBelongsToLayoutContext(toolbar, context)) {
            continue;
        }

        const auto toolbarKey = toolBarPersistenceKey(toolbar);
        if (toolbarKey.isEmpty()) {
            continue;
        }

        hPref->SetBool(toolbarKey.toUtf8().constData(), recommendedToolBarVisibility(toolbar));
    }
}

ParameterGrp::handle ToolBarManager::workbenchLayoutGroup(const QString& context) const
{
    if (!rememberToolbarLayoutByWorkbench() || context.isEmpty()) {
        return {};
    }

    return hWorkbenchLayouts->GetGroup(context.toUtf8().constData());
}

ParameterGrp::handle ToolBarManager::globalHostedToolBarHostGroup() const
{
    auto& mgr = App::GetApplication().GetUserParameter();
    return mgr.GetGroup("BaseApp/MainWindow/HostedToolbarHosts");
}

ParameterGrp::handle ToolBarManager::hostedToolBarHostGroup(const QString& context) const
{
    auto group = workbenchLayoutGroup(context);
    if (!group) {
        return {};
    }

    return group->GetGroup(HostedToolbarHostsGroupKey);
}

ParameterGrp::handle ToolBarManager::globalViewToolBarPresentationGroup() const
{
    auto& mgr = App::GetApplication().GetUserParameter();
    return mgr.GetGroup("BaseApp/MainWindow/ViewToolbarPresentations");
}

ParameterGrp::handle ToolBarManager::viewToolBarPresentationGroup(const QString& context) const
{
    auto group = workbenchLayoutGroup(context);
    if (!group) {
        return {};
    }

    return group->GetGroup(ViewToolbarPresentationsGroupKey);
}

ParameterGrp::handle ToolBarManager::sharedViewOverlayEdgeGroup() const
{
    auto& mgr = App::GetApplication().GetUserParameter();
    return mgr.GetGroup("BaseApp/MainWindow/ViewOverlayEdges");
}

ParameterGrp::handle ToolBarManager::viewOverlayEdgeGroup(const QString& context) const
{
    auto group = workbenchLayoutGroup(context);
    if (!group) {
        return {};
    }

    return group->GetGroup(ViewOverlayEdgesGroupKey);
}

void ToolBarManager::updateLayoutParameters(const QString& context)
{
    auto workbenchGroup = workbenchLayoutGroup(context);

    if (workbenchGroup) {
        hStatusBar = workbenchGroup->GetGroup("StatusBar");
        hMenuBarLeft = workbenchGroup->GetGroup("MenuBarLeft");
        hMenuBarRight = workbenchGroup->GetGroup("MenuBarRight");
    }
    else {
        hStatusBar = hGlobalStatusBar;
        hMenuBarLeft = hGlobalMenuBarLeft;
        hMenuBarRight = hGlobalMenuBarRight;
    }

    if (statusBarAreaWidget) {
        statusBarAreaWidget->setParameters(hStatusBar);
    }
    if (menuBarLeftAreaWidget) {
        menuBarLeftAreaWidget->setParameters(hMenuBarLeft);
    }
    if (menuBarRightAreaWidget) {
        menuBarRightAreaWidget->setParameters(hMenuBarRight);
    }
}

ParameterGrp::handle ToolBarManager::toolbarAreaRestoreParameters(
    const ParameterGrp::handle& current,
    const ParameterGrp::handle& fallback
) const
{
    if (!rememberToolbarLayoutByWorkbench() || current == fallback) {
        return current;
    }

    if (!current->GetIntMap().empty() || !current->GetBoolMap().empty()) {
        return current;
    }

    return fallback;
}

void ToolBarManager::saveWorkbenchToolBarLayout(const QString& context) const
{
    auto group = workbenchLayoutGroup(context);
    if (!group) {
        return;
    }

    struct ToolBarPosition
    {
        int primary;
        int secondary;
        bool toolbarBreak;
        QString key;
    };

    QList<ToolBarPosition> top;
    QList<ToolBarPosition> left;
    QList<ToolBarPosition> right;
    QList<ToolBarPosition> bottom;
    QList<ToolBarPosition> viewTop;
    QList<ToolBarPosition> viewLeft;
    QList<ToolBarPosition> viewRight;
    QList<ToolBarPosition> viewBottom;
    auto activeView = activeViewToolBarHostWindow();

    for (auto toolbar : toolBars()) {
        auto key = toolBarPersistenceKey(toolbar);
        if (key.isEmpty() || toolbar->isFloating()) {
            continue;
        }

        auto hostWindow = toolBarHostWindow(toolbar);
        if (!hostWindow) {
            continue;
        }

        auto* topLayout = &top;
        auto* leftLayout = &left;
        auto* rightLayout = &right;
        auto* bottomLayout = &bottom;
        if (toolBarHost(toolbar) == ToolBarItem::Host::ActiveView) {
            if (toolBarViewPresentation(toolbar) == ToolBarItem::ViewPresentation::CenteredOverlay) {
                continue;
            }
            if (hostWindow != activeView) {
                continue;
            }

            topLayout = &viewTop;
            leftLayout = &viewLeft;
            rightLayout = &viewRight;
            bottomLayout = &viewBottom;
        }
        else if (hostWindow != getMainWindow()) {
            continue;
        }

        QRect geometry = toolbar->geometry();
        bool toolbarBreak = hostWindow->toolBarBreak(toolbar);
        switch (hostWindow->toolBarArea(toolbar)) {
            case Qt::TopToolBarArea:
                topLayout->push_back({geometry.y(), geometry.x(), toolbarBreak, key});
                break;
            case Qt::LeftToolBarArea:
                leftLayout->push_back({geometry.x(), geometry.y(), toolbarBreak, key});
                break;
            case Qt::RightToolBarArea:
                rightLayout->push_back({-geometry.x(), geometry.y(), toolbarBreak, key});
                break;
            case Qt::BottomToolBarArea:
                bottomLayout->push_back({-geometry.y(), geometry.x(), toolbarBreak, key});
                break;
            default:
                break;
        }
    }

    auto save = [group](const char* key, QList<ToolBarPosition>& positions) {
        std::sort(positions.begin(), positions.end(), [](const auto& lhs, const auto& rhs) {
            return std::tie(lhs.primary, lhs.secondary) < std::tie(rhs.primary, rhs.secondary);
        });

        QStringList layout;
        for (const auto& position : std::as_const(positions)) {
            if (position.toolbarBreak) {
                layout << QStringLiteral("Break");
            }
            layout << position.key;
        }
        group->SetASCII(key, layout.join(QLatin1Char(',')).toUtf8().constData());
    };

    group->SetBool("Saved", true);
    save("Top", top);
    save("Left", left);
    save("Right", right);
    save("Bottom", bottom);
    save(ViewTopLayoutKey, viewTop);
    save(ViewLeftLayoutKey, viewLeft);
    save(ViewRightLayoutKey, viewRight);
    save(ViewBottomLayoutKey, viewBottom);
}

void ToolBarManager::restoreWorkbenchToolBarLayout(const QString& context) const
{
    auto group = workbenchLayoutGroup(context);
    if (!group || !group->GetBool("Saved", false)) {
        return;
    }

    QMap<QString, ToolBar*> mainWindowToolbars;
    QMap<QString, QString> legacyAliases;
    QList<ToolBar*> currentToolbars = toolBars();
    for (auto toolbar : std::as_const(currentToolbars)) {
        auto key = toolBarPersistenceKey(toolbar);
        if (key.isEmpty() || toolbar->isFloating() || toolBarHostWindow(toolbar) != getMainWindow()) {
            continue;
        }

        mainWindowToolbars.insert(key, toolbar);
        if (const auto legacyKey = legacyToolBarKey(toolbar); !legacyKey.isEmpty()) {
            legacyAliases.insert(legacyKey, key);
        }
    }

    if (mainWindowToolbars.isEmpty()) {
        return;
    }

    QStringList top = remapLegacyLayoutEntries(splitLayoutState(group->GetASCII("Top")), legacyAliases);
    QStringList left
        = remapLegacyLayoutEntries(splitLayoutState(group->GetASCII("Left")), legacyAliases);
    QStringList right
        = remapLegacyLayoutEntries(splitLayoutState(group->GetASCII("Right")), legacyAliases);
    QStringList bottom
        = remapLegacyLayoutEntries(splitLayoutState(group->GetASCII("Bottom")), legacyAliases);

    QSet<QString> knownKeys;
    auto rememberKeys = [&knownKeys](const QStringList& layout) {
        for (const auto& key : layout) {
            if (key != QStringLiteral("Break")) {
                knownKeys.insert(key);
            }
        }
    };
    rememberKeys(top);
    rememberKeys(left);
    rememberKeys(right);
    rememberKeys(bottom);

    auto appendMissing =
        [&mainWindowToolbars, &knownKeys, this](QStringList& layout, Qt::ToolBarArea area) {
            for (auto toolbar : toolBars()) {
                auto key = toolBarPersistenceKey(toolbar);
                if (!mainWindowToolbars.contains(key) || knownKeys.contains(key)) {
                    continue;
                }
                if (getMainWindow()->toolBarArea(toolbar) == area) {
                    layout << key;
                    knownKeys.insert(key);
                }
            }
        };
    appendMissing(top, Qt::TopToolBarArea);
    appendMissing(left, Qt::LeftToolBarArea);
    appendMissing(right, Qt::RightToolBarArea);
    appendMissing(bottom, Qt::BottomToolBarArea);

    auto restore = [&mainWindowToolbars, this](const QStringList& layout, Qt::ToolBarArea area) {
        for (const auto& key : layout) {
            if (key == QStringLiteral("Break")) {
                getMainWindow()->addToolBarBreak(area);
                continue;
            }

            auto toolbar = mainWindowToolbars.value(key);
            if (!toolbar) {
                continue;
            }

            moveToolBarPreservingVisibility(getMainWindow(), toolbar, area);
        }
    };

    restore(top, Qt::TopToolBarArea);
    restore(left, Qt::LeftToolBarArea);
    restore(right, Qt::RightToolBarArea);
    restore(bottom, Qt::BottomToolBarArea);
}

void ToolBarManager::resetMainWindowToolBarLayout() const
{
    QList<ToolBar*> toolbars = toolBars();
    for (const auto& key : toolbarKeys) {
        auto toolbar = findToolBar(toolbars, key);
        if (!toolbar) {
            continue;
        }
        if (toolBarHost(toolbar) != ToolBarItem::Host::MainWindow) {
            continue;
        }

        auto parent = toolbar->parentWidget();
        if (parent == statusBarAreaWidget || parent == menuBarLeftAreaWidget
            || parent == menuBarRightAreaWidget) {
            continue;
        }

        bool visible = toolbar->isVisible();
        getMainWindow()->removeToolBarBreak(toolbar);
        getMainWindow()->removeToolBar(toolbar);
        toolbar->setOrientation(Qt::Horizontal);
        getMainWindow()->addToolBar(Qt::TopToolBarArea, toolbar);
        toolbar->setVisible(visible);
    }
}

void ToolBarManager::clearViewToolBarLayout(const QString& context) const
{
    auto group = workbenchLayoutGroup(context);
    if (!group) {
        return;
    }

    group->SetASCII(ViewTopLayoutKey, "");
    group->SetASCII(ViewLeftLayoutKey, "");
    group->SetASCII(ViewRightLayoutKey, "");
    group->SetASCII(ViewBottomLayoutKey, "");

    const auto clearEntriesForViewToolBars = [this](const ParameterGrp::handle& targetGroup) {
        if (!targetGroup) {
            return;
        }

        for (auto toolbar : toolBars()) {
            if (!toolbar) {
                continue;
            }
            if (defaultToolBarHost(toolbar) != ToolBarItem::Host::ActiveView
                && toolBarHost(toolbar) != ToolBarItem::Host::ActiveView) {
                continue;
            }

            const auto key = toolBarPersistenceKey(toolbar);
            if (!key.isEmpty()) {
                targetGroup->RemoveASCII(key.toUtf8().constData());
            }
        }
    };

    clearEntriesForViewToolBars(hostedToolBarHostGroup(context));
    clearEntriesForViewToolBars(viewToolBarPresentationGroup(context));
    clearEntriesForViewToolBars(viewOverlayEdgeGroup(context));
}

void ToolBarManager::resetViewHostedToolBarLayout(QMainWindow* hostWindow) const
{
    if (!hostWindow) {
        return;
    }

    QList<ToolBar*> toolbars = toolBars();
    for (const auto& key : toolbarKeys) {
        auto toolbar = findToolBar(toolbars, key);
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::ActiveView
            || toolBarHostWindow(toolbar) != hostWindow) {
            continue;
        }

        if (toolBarViewPresentation(toolbar) == ToolBarItem::ViewPresentation::CenteredOverlay) {
            setToolBarViewOverlayEdge(toolbar, defaultToolBarViewOverlayEdge(toolbar));
            if (auto overlayHost = viewToolBarOverlayHost(qobject_cast<MDIView*>(hostWindow))) {
                overlayHost->attachToolBar(toolbar, toolBarViewOverlayEdge(toolbar));
            }
            continue;
        }
        if (toolBarViewPresentation(toolbar) != ToolBarItem::ViewPresentation::Docked) {
            continue;
        }

        const bool visible = toolbar->isVisible();
        hostWindow->removeToolBarBreak(toolbar);
        hostWindow->removeToolBar(toolbar);
        toolbar->setOrientation(Qt::Horizontal);
        hostWindow->addToolBar(Qt::TopToolBarArea, toolbar);
        toolbar->setVisible(visible);
    }
}

ToolBarItem::Host ToolBarManager::resolvedHostedToolBarHost(
    const QToolBar* toolbar,
    const QString& context,
    const QString& fallbackContext
) const
{
    if (!toolbar) {
        return ToolBarItem::Host::MainWindow;
    }

    const auto key = toolBarPersistenceKey(toolbar);
    const auto lookup = [&key](const ParameterGrp::handle& group, ToolBarItem::Host* host) {
        if (!group || key.isEmpty()) {
            return false;
        }

        const auto value = QString::fromUtf8(group->GetASCII(key.toUtf8().constData()).c_str());
        if (value.isEmpty()) {
            return false;
        }

        *host = parseToolBarHost(value);
        return true;
    };

    ToolBarItem::Host host;
    if (toolBarScopeId(toolbar).scope == Scope::Shared || context.isEmpty()) {
        if (lookup(globalHostedToolBarHostGroup(), &host)) {
            return host;
        }
        return defaultToolBarHost(toolbar);
    }

    if (lookup(hostedToolBarHostGroup(context), &host)) {
        return host;
    }
    if (!fallbackContext.isEmpty() && lookup(hostedToolBarHostGroup(fallbackContext), &host)) {
        return host;
    }
    if (lookup(globalHostedToolBarHostGroup(), &host)) {
        return host;
    }

    return defaultToolBarHost(toolbar);
}

ToolBarItem::ViewPresentation ToolBarManager::resolvedViewToolBarPresentation(
    const QToolBar* toolbar,
    const QString& context,
    const QString& fallbackContext
) const
{
    if (!toolbar) {
        return ToolBarItem::ViewPresentation::Docked;
    }

    const auto key = toolBarPersistenceKey(toolbar);
    const auto lookup =
        [&key](const ParameterGrp::handle& group, ToolBarItem::ViewPresentation* presentation) {
            if (!group || key.isEmpty()) {
                return false;
            }

            const auto value = QString::fromUtf8(group->GetASCII(key.toUtf8().constData()).c_str());
            if (value.isEmpty()) {
                return false;
            }

            *presentation = parseToolBarViewPresentation(value);
            return true;
        };

    ToolBarItem::ViewPresentation presentation;
    if (toolBarScopeId(toolbar).scope == Scope::Shared || context.isEmpty()) {
        if (lookup(globalViewToolBarPresentationGroup(), &presentation)) {
            return presentation;
        }
        return defaultToolBarViewPresentation(toolbar);
    }

    if (lookup(viewToolBarPresentationGroup(context), &presentation)) {
        return presentation;
    }
    if (!fallbackContext.isEmpty()
        && lookup(viewToolBarPresentationGroup(fallbackContext), &presentation)) {
        return presentation;
    }
    if (lookup(globalViewToolBarPresentationGroup(), &presentation)) {
        return presentation;
    }

    return defaultToolBarViewPresentation(toolbar);
}

void ToolBarManager::persistHostedToolBarHost(
    const QToolBar* toolbar,
    const QString& context,
    ToolBarItem::Host host
) const
{
    const auto key = toolBarPersistenceKey(toolbar);
    if (key.isEmpty()) {
        return;
    }

    ParameterGrp::handle group;
    if (toolBarScopeId(toolbar).scope == Scope::Shared || context.isEmpty()) {
        group = globalHostedToolBarHostGroup();
    }
    else {
        group = hostedToolBarHostGroup(context);
    }
    if (!group) {
        return;
    }

    group->SetASCII(key.toUtf8().constData(), toolBarHostName(host).toUtf8().constData());
}

void ToolBarManager::persistViewToolBarPresentation(
    const QToolBar* toolbar,
    const QString& context,
    ToolBarItem::ViewPresentation presentation
) const
{
    const auto key = toolBarPersistenceKey(toolbar);
    if (key.isEmpty()) {
        return;
    }

    ParameterGrp::handle group;
    if (toolBarScopeId(toolbar).scope == Scope::Shared || context.isEmpty()) {
        group = globalViewToolBarPresentationGroup();
    }
    else {
        group = viewToolBarPresentationGroup(context);
    }
    if (!group) {
        return;
    }

    group->SetASCII(
        key.toUtf8().constData(),
        toolBarViewPresentationName(presentation).toUtf8().constData()
    );
}

ToolBarItem::ViewOverlayEdge ToolBarManager::resolvedViewOverlayEdge(
    const QToolBar* toolbar,
    const QString& context,
    const QString& fallbackContext
) const
{
    if (!toolbar) {
        return ToolBarItem::ViewOverlayEdge::Top;
    }

    const auto key = toolBarPersistenceKey(toolbar);
    const auto lookup =
        [this, &key](const ParameterGrp::handle& group, ToolBarItem::ViewOverlayEdge* edge) {
            if (!group || key.isEmpty()) {
                return false;
            }

            const auto value = QString::fromUtf8(group->GetASCII(key.toUtf8().constData()).c_str());
            if (value.isEmpty()) {
                return false;
            }

            *edge = parseToolBarViewOverlayEdge(value);
            return true;
        };
    const auto lookupContext =
        [this, &lookup, &key](const QString& candidateContext, ToolBarItem::ViewOverlayEdge* edge) {
            if (candidateContext.isEmpty() || key.isEmpty()) {
                return false;
            }

            auto group = viewOverlayEdgeGroup(candidateContext);
            return lookup(group, edge);
        };

    ToolBarItem::ViewOverlayEdge edge;
    switch (toolBarViewOverlayEdgePersistence(toolbar)) {
        case ToolBarItem::ViewOverlayEdgePersistence::Shared:
            if (lookup(sharedViewOverlayEdgeGroup(), &edge)) {
                return edge;
            }
            return defaultToolBarViewOverlayEdge(toolbar);
        case ToolBarItem::ViewOverlayEdgePersistence::Contextual:
            break;
        case ToolBarItem::ViewOverlayEdgePersistence::ByScope:
            if (toolBarScopeId(toolbar).scope == Scope::Shared) {
                if (lookup(sharedViewOverlayEdgeGroup(), &edge)) {
                    return edge;
                }
                return defaultToolBarViewOverlayEdge(toolbar);
            }
            break;
    }

    if (lookupContext(context, &edge)) {
        return edge;
    }
    if (lookupContext(fallbackContext, &edge)) {
        return edge;
    }

    return defaultToolBarViewOverlayEdge(toolbar);
}

void ToolBarManager::persistViewOverlayEdge(
    const QToolBar* toolbar,
    const QString& context,
    ToolBarItem::ViewOverlayEdge edge
) const
{
    const auto key = toolBarPersistenceKey(toolbar);
    if (key.isEmpty()) {
        return;
    }

    ParameterGrp::handle group;
    switch (toolBarViewOverlayEdgePersistence(toolbar)) {
        case ToolBarItem::ViewOverlayEdgePersistence::Shared:
            group = sharedViewOverlayEdgeGroup();
            break;
        case ToolBarItem::ViewOverlayEdgePersistence::Contextual:
            group = viewOverlayEdgeGroup(context);
            break;
        case ToolBarItem::ViewOverlayEdgePersistence::ByScope:
            if (toolBarScopeId(toolbar).scope == Scope::Shared) {
                group = sharedViewOverlayEdgeGroup();
            }
            else {
                group = viewOverlayEdgeGroup(context);
            }
            break;
    }
    if (!group) {
        return;
    }

    group->SetASCII(key.toUtf8().constData(), toolBarViewOverlayEdgeName(edge).toUtf8().constData());
}

bool ToolBarManager::recommendedToolBarVisibility(const QToolBar* toolbar) const
{
    switch (toolBarTier(toolbar)) {
        case ToolBarItem::Tier::Recommended:
        case ToolBarItem::Tier::Contextual:
            return true;
        case ToolBarItem::Tier::Secondary:
        case ToolBarItem::Tier::Advanced:
            return false;
    }

    return true;
}

static bool defaultToolBarVisibility(const QToolBar* toolbar)
{
    if (!toolbar) {
        return false;
    }

    auto* action = toolbar->toggleViewAction();
    const auto property = action ? action->property("DefaultVisibility") : QVariant();
    const auto policy = property.isNull()
        ? ToolBarItem::DefaultVisibility::Visible
        : static_cast<ToolBarItem::DefaultVisibility>(property.toInt());

    switch (policy) {
        case ToolBarItem::DefaultVisibility::Visible:
            return true;
        case ToolBarItem::DefaultVisibility::Hidden:
        case ToolBarItem::DefaultVisibility::Unavailable:
            return false;
    }

    return false;
}

void ToolBarManager::applyRecommendedToolBarPreferences()
{
    Base::ConnectionBlocker block(paramHandlers.connection());
    QList<ToolBar*> toolbars = toolBars();
    for (const auto& key : toolbarKeys) {
        auto toolbar = findToolBar(toolbars, key);
        if (!toolbar) {
            continue;
        }

        const auto toolbarKey = toolBarPersistenceKey(toolbar);
        if (toolbarKey.isEmpty()) {
            continue;
        }

        hPref->SetBool(toolbarKey.toUtf8().constData(), recommendedToolBarVisibility(toolbar));
    }
}

void ToolBarManager::applyRecommendedToolBarVisibility()
{
    QList<ToolBar*> toolbars = toolBars();
    for (const auto& key : toolbarKeys) {
        auto toolbar = findToolBar(toolbars, key);
        if (!toolbar) {
            continue;
        }

        auto action = toolbar->toggleViewAction();
        if ((!action || !action->isVisible()) && !toolbar->isVisible()) {
            continue;
        }

        toolbar->setVisible(recommendedToolBarVisibility(toolbar));
    }
}

void ToolBarManager::applyRecommendedViewToolBarPreferences()
{
    Base::ConnectionBlocker block(paramHandlers.connection());
    QList<ToolBar*> toolbars = toolBars();
    for (const auto& key : toolbarKeys) {
        auto toolbar = findToolBar(toolbars, key);
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::ActiveView) {
            continue;
        }

        const auto toolbarKey = toolBarPersistenceKey(toolbar);
        if (toolbarKey.isEmpty()) {
            continue;
        }

        hPref->SetBool(toolbarKey.toUtf8().constData(), defaultToolBarVisibility(toolbar));
    }
}

void ToolBarManager::applyRecommendedViewToolBarVisibility()
{
    QList<ToolBar*> toolbars = toolBars();
    for (const auto& key : toolbarKeys) {
        auto toolbar = findToolBar(toolbars, key);
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::ActiveView) {
            continue;
        }

        auto action = toolbar->toggleViewAction();
        if ((!action || !action->isVisible()) && !toolbar->isVisible()) {
            continue;
        }

        toolbar->setVisible(defaultToolBarVisibility(toolbar));
    }
}

void ToolBarManager::setHostedToolBarHost(QToolBar* toolbar, ToolBarItem::Host host)
{
    if (!toolbar) {
        return;
    }

    setToolBarHost(toolbar, host);

    const auto context = effectiveToolbarLayoutContext();
    persistHostedToolBarHost(toolbar, context, host);

    if (host == ToolBarItem::Host::ActiveView) {
        refreshViewHostedToolBars();
        return;
    }

    if (host == ToolBarItem::Host::Panel) {
        refreshPanelHostedToolBars();
        return;
    }

    const bool visible = toolbar->isVisible();
    if (auto parentLayout = toolbar->parentWidget() ? toolbar->parentWidget()->layout() : nullptr) {
        parentLayout->removeWidget(toolbar);
    }
    if (auto hostWindow = toolBarHostWindow(toolbar); hostWindow && hostWindow != getMainWindow()) {
        hostWindow->removeToolBarBreak(toolbar);
        hostWindow->removeToolBar(toolbar);
    }

    toolbar->setOrientation(Qt::Horizontal);
    getMainWindow()->addToolBar(Qt::TopToolBarArea, toolbar);
    toolbar->setVisible(visible);

    const auto layoutContext = effectiveToolbarLayoutContext();
    if (!layoutContext.isEmpty() && hasSavedWorkbenchToolBarLayout(layoutContext)) {
        restoreWorkbenchToolBarLayout(layoutContext);
    }
    setToolBarIconSize(toolbar);
}

void ToolBarManager::setViewToolBarPresentation(
    QToolBar* toolbar,
    ToolBarItem::ViewPresentation presentation
)
{
    if (!toolbar) {
        return;
    }

    setToolBarViewPresentation(toolbar, presentation);

    const auto context = effectiveToolbarLayoutContext();
    persistViewToolBarPresentation(toolbar, context, presentation);

    if (toolBarHost(toolbar) == ToolBarItem::Host::ActiveView) {
        refreshViewHostedToolBars();
    }
}

ToolBarArea ToolBarManager::toolBarArea(QWidget* widget) const
{
    if (auto toolBar = qobject_cast<QToolBar*>(widget)) {
        if (toolBar->isFloating()) {
            return ToolBarArea::NoToolBarArea;
        }

        auto hostWindow = qobject_cast<QMainWindow*>(toolBar->parentWidget());
        auto qtToolBarArea = hostWindow ? hostWindow->toolBarArea(toolBar) : Qt::NoToolBarArea;
        switch (qtToolBarArea) {
            case Qt::LeftToolBarArea:
                return ToolBarArea::LeftToolBarArea;
            case Qt::RightToolBarArea:
                return ToolBarArea::RightToolBarArea;
            case Qt::TopToolBarArea:
                return ToolBarArea::TopToolBarArea;
            case Qt::BottomToolBarArea:
                return ToolBarArea::BottomToolBarArea;
            default:
                // no-op
                break;
        }
    }

    if (auto areaWidget = toolBarAreaWidget(widget)) {
        return areaWidget->area();
    }

    return ToolBarArea::NoToolBarArea;
}

ToolBarAreaWidget* ToolBarManager::toolBarAreaWidget(QWidget* widget) const
{
    for (auto& areaWidget : {statusBarAreaWidget, menuBarLeftAreaWidget, menuBarRightAreaWidget}) {
        if (areaWidget->indexOf(widget) >= 0) {
            return areaWidget;
        }
    }

    return nullptr;
}

namespace
{
QPointer<QWidget> createActionWidget()
{
    static QPointer<QWidget> actionWidget;
    if (!actionWidget) {
        actionWidget = new QWidget(getMainWindow());
        actionWidget->setObjectName(QStringLiteral("_fc_action_widget_"));
        /* TODO This is a temporary hack until a longterm solution
        is found, thanks to @realthunder for this pointer.
        Although actionWidget has zero size, it somehow has a
        'phantom' size without any visible content and will block the top
        left tool buttons and menus of the application main window.
        Therefore it is moved out of the way. */
        actionWidget->move(QPoint(-100, -100));
    }
    else {
        auto actions = actionWidget->actions();
        for (auto action : actions) {
            actionWidget->removeAction(action);
        }
    }

    return actionWidget;
}
}  // namespace

int ToolBarManager::toolBarIconSize(QWidget* widget) const
{
    int s = _toolBarIconSize;
    if (widget) {
        if (widget->parentWidget() == statusBarAreaWidget) {
            if (_statusBarIconSize > 0) {
                s = _statusBarIconSize;
            }
            else {
                s *= 0.6;
            }
        }
        else if (
            widget->parentWidget() == menuBarLeftAreaWidget
            || widget->parentWidget() == menuBarRightAreaWidget
        ) {
            if (_menuBarIconSize > 0) {
                s = _menuBarIconSize;
            }
            else {
                s *= 0.6;
            }
        }
    }
    return std::max(s, 5);
}

void ToolBarManager::setupToolBarIconSize()
{
    int s = toolBarIconSize();
    getMainWindow()->setIconSize(QSize(s, s));
    // Most of the toolbar will have explicit icon size, so the above call
    // to QMainWindow::setIconSize() will have no effect. We need to explicitly
    // change the icon size.
    QList<QToolBar*> bars = getMainWindow()->findChildren<QToolBar*>();
    for (auto toolbar : std::as_const(bars)) {
        setToolBarIconSize(toolbar);
    }
}

void ToolBarManager::setToolBarIconSize(QToolBar* toolbar)
{
    int s = toolBarIconSize(toolbar);
    toolbar->setIconSize(QSize(s, s));
    if (toolbar->parentWidget() == menuBarLeftAreaWidget) {
        menuBarLeftAreaWidget->adjustParent();
    }
    else if (toolbar->parentWidget() == menuBarRightAreaWidget) {
        menuBarRightAreaWidget->adjustParent();
    }
}

void ToolBarManager::setup(ToolBarItem* toolBarItems)
{
    if (!toolBarItems) {
        return;  // empty menu bar
    }

    QPointer<QWidget> actionWidget = createActionWidget();

    saveState();
    updateLayoutParameters(effectiveToolbarLayoutContext());
    this->toolbarKeys.clear();

    int max_width = getMainWindow()->width();
    int top_width = 0;

    bool nameAsToolTip = App::GetApplication()
                             .GetUserParameter()
                             .GetGroup("BaseApp")
                             ->GetGroup("Preferences")
                             ->GetGroup("MainWindow")
                             ->GetBool("ToolBarNameAsToolTip", true);

    QList<ToolBarItem*> items = toolBarItems->getItems();
    QList<ToolBar*> toolbars = toolBars();

    for (ToolBarItem* it : items) {
        QString name = QString::fromUtf8(it->command().c_str());
        QString key = toolBarPersistenceKey(it);
        this->toolbarKeys << key;
        ToolBar* toolbar = findToolBar(toolbars, key);
        bool toolbar_added = false;

        if (!toolbar) {
            toolbar = new ToolBar(getMainWindow());
            toolbar->setWindowTitle(QApplication::translate("Workbench", it->command().c_str()));
            toolbar->setObjectName(name);
            setToolBarPersistenceKey(toolbar, key);
            setDefaultToolBarHost(toolbar, toolBarHost(it));
            setToolBarTier(toolbar, toolBarTier(it));
            setToolBarHost(toolbar, toolBarHost(it));
            setToolBarPanelRole(toolbar, toolBarPanelRole(it));
            setDefaultToolBarViewPresentation(toolbar, toolBarViewPresentation(it));
            setToolBarViewPresentation(toolbar, toolBarViewPresentation(it));
            setDefaultToolBarViewOverlayEdge(toolbar, toolBarViewOverlayEdge(it));
            setToolBarViewOverlayEdge(toolbar, toolBarViewOverlayEdge(it));
            setToolBarViewOverlayEdgePersistence(toolbar, toolBarViewOverlayEdgePersistence(it));
            toolbar->setProperty(
                ToolBarViewHostRequirementProperty,
                static_cast<int>(toolBarViewHostRequirement(it))
            );

            getMainWindow()->addToolBar(toolbar);
            setToolBarIconSize(toolbar);

            if (nameAsToolTip) {
                auto tooltip = QChar::fromLatin1('[')
                    + QApplication::translate("Workbench", it->command().c_str())
                    + QChar::fromLatin1(']');
                toolbar->setToolTip(tooltip);
            }
            toolbar_added = true;
        }
        else {
            setToolBarPersistenceKey(toolbar, key);
            setDefaultToolBarHost(toolbar, toolBarHost(it));
            setToolBarTier(toolbar, toolBarTier(it));
            setToolBarHost(toolbar, toolBarHost(it));
            setToolBarPanelRole(toolbar, toolBarPanelRole(it));
            setDefaultToolBarViewPresentation(toolbar, toolBarViewPresentation(it));
            setToolBarViewPresentation(toolbar, toolBarViewPresentation(it));
            setDefaultToolBarViewOverlayEdge(toolbar, toolBarViewOverlayEdge(it));
            setToolBarViewOverlayEdge(toolbar, toolBarViewOverlayEdge(it));
            setToolBarViewOverlayEdgePersistence(toolbar, toolBarViewOverlayEdgePersistence(it));
            toolbar->setProperty(
                ToolBarViewHostRequirementProperty,
                static_cast<int>(toolBarViewHostRequirement(it))
            );
            int index = toolbars.indexOf(toolbar);
            toolbars.removeAt(index);
        }

        bool visible = false;

        // If visibility policy is custom, the toolbar is initialised as not visible, and the
        // toggleViewAction to control its visibility is not visible either.
        //
        // Both are managed under the responsibility of the client code
        if (it->visibilityPolicy != ToolBarItem::DefaultVisibility::Unavailable) {
            bool defaultvisibility = it->visibilityPolicy == ToolBarItem::DefaultVisibility::Visible;

            QByteArray toolbarKey = key.toUtf8();
            visible = hPref->GetBool(toolbarKey.constData(), defaultvisibility);

            // Enable automatic handling of visibility via, for example, (contextual) menu
            toolbar->toggleViewAction()->setVisible(true);
        }
        else {
            // ToolBarItem::DefaultVisibility::Unavailable
            // Prevent that the action to show/hide a toolbar appears on the (contextual) menus.
            // This is also managed by the client code for a toolbar with custom policy
            toolbar->toggleViewAction()->setVisible(false);
        }

        // Initialise toolbar item visibility
        toolbar->setVisible(visible);

        // Store item visibility policy within the action
        QAction* toggle = toolbar->toggleViewAction();
        toggle->setProperty("DefaultVisibility", static_cast<int>(it->visibilityPolicy));

        // setup the toolbar
        setup(it, toolbar);
        toolbar->setVisible(visible);
        auto actions = toolbar->actions();
        for (auto action : actions) {
            actionWidget->addAction(action);
        }

        // try to add some breaks to avoid to have all toolbars in one line
        if (toolbar_added && toolBarHost(toolbar) == ToolBarItem::Host::MainWindow) {
            if (top_width > 0 && getMainWindow()->toolBarBreak(toolbar)) {
                top_width = 0;
            }

            // the width() of a toolbar doesn't return useful results so we estimate
            // its size by the number of buttons and the icon size
            QList<QToolButton*> btns = toolbar->findChildren<QToolButton*>();
            top_width += (btns.size() * toolbar->iconSize().width());
            if (top_width > max_width) {
                top_width = 0;
                getMainWindow()->insertToolBarBreak(toolbar);
            }
        }
    }

    refreshHostedToolBars();

    // hide all unneeded toolbars
    for (QToolBar* it : std::as_const(toolbars)) {
        // make sure that the main window has the focus when hiding the toolbar with
        // the combo box inside
        QWidget* fw = QApplication::focusWidget();
        while (fw && !fw->isWindow()) {
            if (fw == it) {
                getMainWindow()->setFocus();
                break;
            }
            fw = fw->parentWidget();
        }
        // ignore toolbars which do not belong to the previously active workbench
        // QByteArray toolbarName = it->objectName().toUtf8();
        if (!it->toggleViewAction()->isVisible()) {
            continue;
        }
        // hPref->SetBool(toolbarName.constData(), it->isVisible());
        it->hide();
        it->toggleViewAction()->setVisible(false);
    }

    setMovable(!areToolBarsLocked());
}

void ToolBarManager::setup(ToolBarItem* item, QToolBar* toolbar) const
{
    CommandManager& mgr = Application::Instance->commandManager();
    QList<ToolBarItem*> items = item->getItems();
    QList<QAction*> actions = toolbar->actions();
    QList<QAction*> orderedActions;
    orderedActions.reserve(items.size());
    for (ToolBarItem* it : items) {
        // search for the action item
        QAction* action = findAction(actions, QString::fromLatin1(it->command().c_str()));
        if (!action) {
            if (it->command() == "Separator") {
                action = toolbar->addSeparator();
            }
            else {
                // Check if action was added successfully
                if (mgr.addTo(it->command().c_str(), toolbar)) {
                    action = toolbar->actions().constLast();
                }
            }

            // set the tool button user data
            if (action) {
                action->setData(QString::fromLatin1(it->command().c_str()));
            }
        }
        else {
            int index = actions.indexOf(action);
            actions.removeAt(index);
        }

        if (action) {
            orderedActions.push_back(action);
        }
    }

    // remove all tool buttons which we don't need for the moment
    for (QAction* it : std::as_const(actions)) {
        toolbar->removeAction(it);
    }

    if (toolbar->actions() != orderedActions) {
        // Reinsert in one batch so reused toolbars match the workbench definition again.
        toolbar->setUpdatesEnabled(false);
        for (QAction* action : std::as_const(orderedActions)) {
            toolbar->removeAction(action);
        }
        for (QAction* action : std::as_const(orderedActions)) {
            toolbar->addAction(action);
        }
        toolbar->setUpdatesEnabled(true);
    }
}

void ToolBarManager::onTimer()
{
    restoreState();
}

void ToolBarManager::saveState() const
{
    saveWorkbenchToolBarLayout(toolbarLayoutContext);

    auto ignoreSave = [](QAction* action) {
        // Only save state for toolbars whose toggle action is user-visible.
        return !action->isVisible();
    };

    QList<ToolBar*> toolbars = toolBars();
    for (const QString& it : toolbarKeys) {
        ToolBar* toolbar = findToolBar(toolbars, it);

        if (toolbar) {
            if (ignoreSave(toolbar->toggleViewAction())) {
                continue;
            }

            QByteArray toolbarKey = toolBarPersistenceKey(toolbar).toUtf8();
            hPref->SetBool(toolbarKey.constData(), toolbar->isVisible());
        }
    }
}

void ToolBarManager::restoreState()
{
    const QString previousLayoutContext = toolbarLayoutContext;
    const QString layoutContext = effectiveToolbarLayoutContext();
    const QString activeContext = activeToolbarLayoutContext();
    updateLayoutParameters(layoutContext);
    initializeUnsavedToolbarLayoutContext(layoutContext);
    const auto statusBarParams = toolbarAreaRestoreParameters(hStatusBar, hGlobalStatusBar);
    const auto menuBarLeftParams = toolbarAreaRestoreParameters(hMenuBarLeft, hGlobalMenuBarLeft);
    const auto menuBarRightParams = toolbarAreaRestoreParameters(hMenuBarRight, hGlobalMenuBarRight);
    const auto visibilityValues = toLookup<bool>(hPref, [](const auto& group) {
        return group->GetBoolMap();
    });
    const auto statusBarValues = toLookup<int>(hStatusBar, [](const auto& group) {
        return group->GetIntMap();
    });
    const auto statusBarFallbackValues = hStatusBar == hGlobalStatusBar
        ? QMap<QString, int>()
        : toLookup<int>(hGlobalStatusBar, [](const auto& group) { return group->GetIntMap(); });
    const auto menuBarLeftValues = toLookup<int>(hMenuBarLeft, [](const auto& group) {
        return group->GetIntMap();
    });
    const auto menuBarLeftFallbackValues = hMenuBarLeft == hGlobalMenuBarLeft
        ? QMap<QString, int>()
        : toLookup<int>(hGlobalMenuBarLeft, [](const auto& group) { return group->GetIntMap(); });
    const auto menuBarRightValues = toLookup<int>(hMenuBarRight, [](const auto& group) {
        return group->GetIntMap();
    });
    const auto menuBarRightFallbackValues = hMenuBarRight == hGlobalMenuBarRight
        ? QMap<QString, int>()
        : toLookup<int>(hGlobalMenuBarRight, [](const auto& group) { return group->GetIntMap(); });

    std::map<int, QToolBar*> sbToolBars;
    std::map<int, QToolBar*> mbRightToolBars;
    std::map<int, QToolBar*> mbLeftToolBars;
    QList<ToolBar*> toolbars = toolBars();
    const auto fallbackContext = layoutContextId(layoutContext).scope == Scope::Contextual
        ? activeContext
        : QString();
    for (const QString& it : toolbarKeys) {
        QToolBar* toolbar = findToolBar(toolbars, it);
        if (toolbar) {
            setToolBarHost(toolbar, resolvedHostedToolBarHost(toolbar, layoutContext, fallbackContext));
            setToolBarViewPresentation(
                toolbar,
                resolvedViewToolBarPresentation(toolbar, layoutContext, fallbackContext)
            );
            if (getToolbarPolicy(toolbar) != ToolBarItem::DefaultVisibility::Unavailable) {
                bool visible = toolbar->isVisible();
                if (lookupToolBarValue(visibilityValues, {}, toolbar, &visible)) {
                    toolbar->setVisible(visible);
                }
            }

            int idx = -1;
            if (lookupToolBarValue(statusBarValues, statusBarFallbackValues, toolbar, &idx)
                && idx >= 0) {
                sbToolBars[idx] = toolbar;
                continue;
            }
            idx = -1;
            if (lookupToolBarValue(menuBarLeftValues, menuBarLeftFallbackValues, toolbar, &idx)
                && idx >= 0) {
                mbLeftToolBars[idx] = toolbar;
                continue;
            }
            idx = -1;
            if (lookupToolBarValue(menuBarRightValues, menuBarRightFallbackValues, toolbar, &idx)
                && idx >= 0) {
                mbRightToolBars[idx] = toolbar;
                continue;
            }
            if (toolBarHost(toolbar) == ToolBarItem::Host::ActiveView) {
                if (toolBarViewPresentation(toolbar)
                    == ToolBarItem::ViewPresentation::CenteredOverlay) {
                    setToolBarViewOverlayEdge(
                        toolbar,
                        resolvedViewOverlayEdge(toolbar, layoutContext, fallbackContext)
                    );
                }
                continue;
            }
            if (toolBarHost(toolbar) == ToolBarItem::Host::Panel) {
                continue;
            }
            if (toolBarHostWindow(toolbar) != getMainWindow()) {
                getMainWindow()->addToolBar(toolbar);
            }
        }
    }

    setMovable(!areToolBarsLocked());

    restoreWorkbenchToolBarLayout(layoutContext);
    statusBarAreaWidget->restoreState(sbToolBars, statusBarParams);
    menuBarRightAreaWidget->restoreState(mbRightToolBars, menuBarRightParams);
    menuBarLeftAreaWidget->restoreState(mbLeftToolBars, menuBarLeftParams);
    refreshHostedToolBars();

    toolbarLayoutContext = layoutContext;
    if (previousLayoutContext != layoutContext) {
        Q_EMIT toolbarLayoutContextChanged();
    }
    Q_EMIT toolbarLayoutRestored(layoutContext);
}

bool ToolBarManager::addToolBarToArea(QObject* source, QMouseEvent* ev)
{
    auto statusBar = getMainWindow()->statusBar();
    if (!statusBar || !statusBar->isVisible()) {
        statusBar = nullptr;
    }

    auto menuBar = getMainWindow()->menuBar();
    if (!menuBar || !menuBar->isVisible()) {
        if (!statusBar) {
            return false;
        }
        menuBar = nullptr;
    }

    auto tb = qobject_cast<QToolBar*>(source);
    if (!tb || !tb->isFloating()) {
        return false;
    }

    static QPointer<OverlayDragFrame> tbPlaceholder;
    static QPointer<ToolBarAreaWidget> lastArea;
    static int tbIndex = -1;
    if (ev->type() == QEvent::MouseMove) {
        if (tb->orientation() != Qt::Horizontal || ev->buttons() != Qt::LeftButton) {
            if (tbIndex >= 0) {
                if (lastArea) {
                    lastArea->removeWidget(tbPlaceholder);
                    lastArea = nullptr;
                }
                tbPlaceholder->hide();
                tbIndex = -1;
            }
            return false;
        }
    }

    if (ev->type() == QEvent::MouseButtonRelease && ev->button() != Qt::LeftButton) {
        return false;
    }

    QPoint pos = QCursor::pos();
    ToolBarAreaWidget* area = nullptr;
    if (statusBar) {
        QRect rect(statusBar->mapToGlobal(QPoint(0, 0)), statusBar->size());
        if (rect.contains(pos)) {
            area = statusBarAreaWidget;
        }
    }
    if (!area) {
        if (!menuBar) {
            return false;
        }
        QRect rect(menuBar->mapToGlobal(QPoint(0, 0)), menuBar->size());
        if (rect.contains(pos)) {
            if (pos.x() - rect.left() < menuBar->width() / 2) {
                area = menuBarLeftAreaWidget;
            }
            else {
                area = menuBarRightAreaWidget;
            }
        }
        else {
            if (tbPlaceholder) {
                if (lastArea) {
                    lastArea->removeWidget(tbPlaceholder);
                    lastArea = nullptr;
                }
                tbPlaceholder->hide();
                tbIndex = -1;
            }
            return false;
        }
    }

    int idx = 0;
    for (int c = area->count(); idx < c; ++idx) {
        auto widget = area->widgetAt(idx);
        if (!widget || widget->isHidden()) {
            continue;
        }
        int p = widget->mapToGlobal(widget->rect().center()).x();
        if (pos.x() < p) {
            break;
        }
    }
    if (tbIndex >= 0 && tbIndex == idx - 1) {
        idx = tbIndex;
    }
    if (ev->type() == QEvent::MouseMove) {
        if (!tbPlaceholder) {
            tbPlaceholder = new OverlayDragFrame(getMainWindow());
            tbPlaceholder->hide();
            tbIndex = -1;
        }
        if (tbIndex != idx) {
            tbIndex = idx;
            tbPlaceholder->setSizePolicy(tb->sizePolicy());
            tbPlaceholder->setMinimumWidth(tb->minimumWidth());
            tbPlaceholder->resize(tb->size());
            area->insertWidget(idx, tbPlaceholder);
            lastArea = area;
            tbPlaceholder->adjustSize();
            tbPlaceholder->show();
        }
    }
    else {
        tbIndex = idx;
        QTimer::singleShot(10, tb, [tb]() {
            if (!lastArea) {
                return;
            }

            {
                tbPlaceholder->hide();
                QSignalBlocker block(tb);
                lastArea->removeWidget(tbPlaceholder);
                getMainWindow()->removeToolBar(tb);
                tb->setOrientation(Qt::Horizontal);
                lastArea->insertWidget(tbIndex, tb);
                tb->setVisible(true);
                lastArea = nullptr;
            }

            Q_EMIT tb->topLevelChanged(false);
            tbIndex = -1;
        });
    }
    return false;
}

bool ToolBarManager::showContextMenu(QObject* source)
{
    QMenu menu;
    if (auto toolbar = qobject_cast<QToolBar*>(source)) {
        populateSingleToolBarMenu(&menu, toolbar);
        if (toolBarHost(toolbar) == ToolBarItem::Host::ActiveView) {
            addCurrentViewToolbarLayoutActions(&menu);
        }
        else {
            addCurrentToolbarLayoutActions(&menu);
        }
        if (menu.isEmpty()) {
            return false;
        }

        menu.exec(QCursor::pos());
        return true;
    }

    QLayout* layout = nullptr;
    ToolBarAreaWidget* area = nullptr;
    if (getMainWindow()->statusBar() == source) {
        area = statusBarAreaWidget;
        layout = findLayoutOfObject(source, area);
    }
    else if (getMainWindow()->menuBar() == source) {
        area = findToolBarAreaWidget();
        if (!area) {
            return false;
        }
    }
    else {
        return false;
    }

    if (layout) {
        addToMenu(layout, area, &menu);
    }

    QList<QToolBar*> toolbars;
    area->foreachToolBar([&toolbars](QToolBar* toolbar, int, ToolBarAreaWidget*) {
        toolbars.push_back(toolbar);
    });

    if (!toolbars.isEmpty() && !menu.isEmpty()) {
        menu.addSeparator();
    }
    addToolBarActionsByScope(&menu, toolbars);
    addCurrentToolbarLayoutActions(&menu);

    menu.exec(QCursor::pos());
    return true;
}
void ToolBarManager::populateToolBarMenu(QMenu* menu)
{
    if (!menu) {
        return;
    }

    QList<QToolBar*> allToolBars;
    for (auto toolbar : toolBars()) {
        allToolBars.push_back(toolbar);
    }

    addToolBarActionsByScope(menu, allToolBars);
    addCurrentToolbarLayoutActions(menu);
}

bool ToolBarManager::populateViewToolBarMenu(QMenu* menu)
{
    if (!menu) {
        return false;
    }

    QList<QToolBar*> allToolBars;
    for (auto toolbar : toolBars()) {
        allToolBars.push_back(toolbar);
    }

    const auto viewActions = viewToolBarMenuActions(menu, allToolBars);
    for (auto action : viewActions) {
        menu->addAction(action);
    }
    addCurrentViewToolbarLayoutActions(menu);
    return !menu->isEmpty();
}

QLayout* ToolBarManager::findLayoutOfObject(QObject* source, QWidget* area) const
{
    QLayout* layout = nullptr;
    auto layouts = source->findChildren<QHBoxLayout*>();
    for (auto l : std::as_const(layouts)) {
        if (l->indexOf(area) >= 0) {
            layout = l;
            break;
        }
    }
    return layout;
}

ToolBarAreaWidget* ToolBarManager::findToolBarAreaWidget() const
{
    ToolBarAreaWidget* area = nullptr;

    QPoint pos = QCursor::pos();
    QRect rect(menuBarLeftAreaWidget->mapToGlobal(QPoint(0, 0)), menuBarLeftAreaWidget->size());
    if (rect.contains(pos)) {
        area = menuBarLeftAreaWidget;
    }
    else {
        rect = QRect(menuBarRightAreaWidget->mapToGlobal(QPoint(0, 0)), menuBarRightAreaWidget->size());
        if (rect.contains(pos)) {
            area = menuBarRightAreaWidget;
        }
    }

    return area;
}

void ToolBarManager::addToMenu(QLayout* layout, QWidget* area, QMenu* menu)
{
    for (int i = 0, c = layout->count(); i < c; ++i) {
        auto widget = layout->itemAt(i)->widget();
        if (!widget || widget == area || widget->objectName().isEmpty()
            || widget->objectName().startsWith(QStringLiteral("*"))) {
            continue;
        }
        QString name = widget->windowTitle();
        if (name.isEmpty()) {
            name = widget->objectName();
            name.replace(QLatin1Char('_'), QLatin1Char(' '));
            name = name.simplified();
        }

        auto action = new QAction(menu);
        action->setText(name);
        action->setCheckable(true);
        action->setChecked(widget->isVisible());
        menu->addAction(action);

        auto onToggle = [widget, this](bool visible) {
            onToggleStatusBarWidget(widget, visible);
        };
        QObject::connect(action, &QAction::triggered, onToggle);
    }
}

void ToolBarManager::onToggleStatusBarWidget(QWidget* widget, bool visible)
{
    Base::ConnectionBlocker block(paramHandlers.connection());
    widget->setVisible(visible);
    hStatusBar->SetBool(widget->objectName().toUtf8().constData(), widget->isVisible());
}

void ToolBarManager::addToolBarActionsByScope(QMenu* menu, const QList<QToolBar*>& toolbars) const
{
    if (!menu) {
        return;
    }

    const auto viewActions = viewToolBarMenuActions(menu, toolbars);
    const auto panelActions = panelToolBarMenuActions(menu, toolbars);
    QList<QAction*> sharedActions;
    QList<QAction*> workbenchActions;
    QList<QAction*> contextualActions;
    QList<QAction*> legacyActions;

    for (auto toolbar : toolbars) {
        if (!toolbar) {
            continue;
        }

        auto action = toolbar->toggleViewAction();
        if (action->text().isEmpty()) {
            continue;
        }
        if (toolBarHost(toolbar) == ToolBarItem::Host::ActiveView
            || toolBarHost(toolbar) == ToolBarItem::Host::Panel) {
            continue;
        }
        if (!action->isVisible() && !toolbar->isVisible()) {
            continue;
        }

        const auto toggleLabel = QApplication::translate("MainWindow", "Toggles this toolbar");
        const auto tierLabelPrefix = QApplication::translate("MainWindow", "Tier: %1");
        const auto tierLabel = toolBarTierLabel(toolbar);
        const auto toolTip = tierLabel.isEmpty()
            ? toggleLabel
            : QStringLiteral("%1. %2").arg(toggleLabel, tierLabelPrefix.arg(tierLabel));
        auto* menuAction = toolBarMenuAction(menu, toolbar);
        if (!menuAction) {
            continue;
        }
        menuAction->setToolTip(toolTip);
        menuAction->setStatusTip(toolTip);
        menuAction->setWhatsThis(toolTip);

        switch (toolBarScopeId(toolbar).scope) {
            case Scope::Shared:
                sharedActions.push_back(menuAction);
                break;
            case Scope::Workbench:
                workbenchActions.push_back(menuAction);
                break;
            case Scope::Contextual:
                contextualActions.push_back(menuAction);
                break;
            case Scope::Legacy:
                legacyActions.push_back(menuAction);
                break;
        }
    }

    bool hasSection = false;
    auto addToolbarSection = [&](const QString& title, const QList<QAction*>& actions) {
        if (actions.isEmpty()) {
            return;
        }

        if (hasSection) {
            menu->addSeparator();
        }

        menu->addSection(title);
        for (auto action : actions) {
            menu->addAction(action);
        }
        hasSection = true;
    };

    addToolbarSection(QApplication::translate("MainWindow", "View Toolbars"), viewActions);
    addToolbarSection(QApplication::translate("MainWindow", "Panel Toolbars"), panelActions);
    addToolbarSection(QApplication::translate("MainWindow", "Shared Toolbars"), sharedActions);
    addToolbarSection(QApplication::translate("MainWindow", "Workbench Toolbars"), workbenchActions);
    addToolbarSection(QApplication::translate("MainWindow", "Contextual Toolbars"), contextualActions);
    addToolbarSection(QApplication::translate("MainWindow", "Other Toolbars"), legacyActions);
}

QList<QAction*> ToolBarManager::panelToolBarMenuActions(QMenu* menu, const QList<QToolBar*>& toolbars) const
{
    QList<QAction*> panelActions;
    if (!menu) {
        return panelActions;
    }

    const auto toggleLabel = QApplication::translate("MainWindow", "Toggles this toolbar");
    const auto tierLabelPrefix = QApplication::translate("MainWindow", "Tier: %1");

    for (auto toolbar : toolbars) {
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::Panel) {
            continue;
        }

        auto action = toolbar->toggleViewAction();
        const auto role = toolBarPanelRole(toolbar);
        const bool compatible
            = activePanelSupportsToolBarHost(toolbar, activePanelToolBarHostPanel(role));
        if (!action || action->text().isEmpty()) {
            continue;
        }
        if (!compatible && !toolbar->isVisible()) {
            continue;
        }
        if (auto* menuAction = toolBarMenuAction(menu, toolbar)) {
            const auto tierLabel = toolBarTierLabel(toolbar);
            const auto toolTip = tierLabel.isEmpty()
                ? toggleLabel
                : QStringLiteral("%1. %2").arg(toggleLabel, tierLabelPrefix.arg(tierLabel));
            menuAction->setToolTip(toolTip);
            menuAction->setStatusTip(toolTip);
            menuAction->setWhatsThis(toolTip);
            menuAction->setEnabled(compatible);
            panelActions.push_back(menuAction);
        }
    }

    return panelActions;
}

QList<QAction*> ToolBarManager::viewToolBarMenuActions(QMenu* menu, const QList<QToolBar*>& toolbars) const
{
    QList<QAction*> viewActions;
    if (!menu) {
        return viewActions;
    }

    auto activeView = activeViewToolBarHostWindow();
    const auto toggleLabel = QApplication::translate("MainWindow", "Toggles this toolbar");
    const auto tierLabelPrefix = QApplication::translate("MainWindow", "Tier: %1");

    for (auto toolbar : toolbars) {
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::ActiveView) {
            continue;
        }

        auto action = toolbar->toggleViewAction();
        if (!action || action->text().isEmpty()
            || !activeViewSupportsToolBarHost(toolbar, activeView)) {
            continue;
        }
        if (auto* menuAction = toolBarMenuAction(menu, toolbar)) {
            const auto tierLabel = toolBarTierLabel(toolbar);
            const auto toolTip = tierLabel.isEmpty()
                ? toggleLabel
                : QStringLiteral("%1. %2").arg(toggleLabel, tierLabelPrefix.arg(tierLabel));
            menuAction->setToolTip(toolTip);
            menuAction->setStatusTip(toolTip);
            menuAction->setWhatsThis(toolTip);
            viewActions.push_back(menuAction);
        }
    }

    return viewActions;
}

QAction* ToolBarManager::toolBarMenuAction(QMenu* menu, QToolBar* toolbar) const
{
    if (!menu || !toolbar) {
        return nullptr;
    }

    auto* toolbarMenu = new QMenu(decoratedToolBarActionText(toolbar), menu);
    if (auto action = toolbar->toggleViewAction()) {
        toolbarMenu->setIcon(action->icon());
    }
    populateSingleToolBarMenu(toolbarMenu, toolbar);

    return toolbarMenu->menuAction();
}

void ToolBarManager::populateSingleToolBarMenu(QMenu* menu, QToolBar* toolbar) const
{
    if (!menu || !toolbar) {
        return;
    }

    auto* action = toolbar->toggleViewAction();
    if (!action || action->text().isEmpty()) {
        return;
    }

    auto* manager = const_cast<ToolBarManager*>(this);
    auto toggleToolbar = [this, toolbar](bool checked) {
        if (toolBarHost(toolbar) == ToolBarItem::Host::ActiveView) {
            auto hostWindow = activeViewToolBarHostWindow();
            if (!activeViewSupportsToolBarHost(toolbar, hostWindow)) {
                return;
            }

            if (hostWindow) {
                if (toolBarViewPresentation(toolbar)
                    == ToolBarItem::ViewPresentation::CenteredOverlay) {
                    if (auto overlayHost = viewToolBarOverlayHost(hostWindow)) {
                        overlayHost->attachToolBar(toolbar, toolBarViewOverlayEdge(toolbar));
                    }
                }
                else if (toolBarHostWindow(toolbar) != hostWindow) {
                    toolbar->setOrientation(Qt::Horizontal);
                    moveToolBarPreservingVisibility(hostWindow, toolbar, Qt::TopToolBarArea);
                }
            }
        }
        else if (toolBarHost(toolbar) == ToolBarItem::Host::Panel) {
            const auto role = toolBarPanelRole(toolbar);
            auto panel = activePanelToolBarHostPanel(role);
            if (!activePanelSupportsToolBarHost(toolbar, panel)) {
                return;
            }

            if (auto host = panelToolBarHost(panel, role)) {
                host->attachToolBar(toolbar);
            }
        }

        toolbar->setVisible(checked);
        const auto toolbarKey = toolBarPersistenceKey(toolbar);
        if (!toolbarKey.isEmpty()) {
            hPref->SetBool(toolbarKey.toUtf8().constData(), checked);
        }
    };

    auto* showAction = menu->addAction(toolBarVisibilityMenuLabel());
    showAction->setCheckable(true);
    showAction->setChecked(toolbar->isVisible());
    showAction->setEnabled(
        (toolBarHost(toolbar) != ToolBarItem::Host::ActiveView
         || activeViewSupportsToolBarHost(toolbar, activeViewToolBarHostWindow()))
        && (toolBarHost(toolbar) != ToolBarItem::Host::Panel
            || activePanelSupportsToolBarHost(
                toolbar,
                activePanelToolBarHostPanel(toolBarPanelRole(toolbar))
            ))
    );
    QObject::connect(showAction, &QAction::triggered, this, toggleToolbar);

    auto* moveMenu = menu->addMenu(toolBarMoveToMenuLabel());
    auto* moveGroup = new QActionGroup(moveMenu);
    moveGroup->setExclusive(true);

    const auto activeView = activeViewToolBarHostWindow();
    const auto panelRole = toolBarPanelRole(toolbar);
    const auto activePanel = activePanelToolBarHostPanel(panelRole);
    const bool canUseViewHost = activeViewSupportsToolBarHost(toolbar, activeView);
    const bool canUsePanelHost = activePanelSupportsToolBarHost(toolbar, activePanel);
    for (auto host :
         {ToolBarItem::Host::MainWindow, ToolBarItem::Host::ActiveView, ToolBarItem::Host::Panel}) {
        if (host == ToolBarItem::Host::Panel && panelRole == ToolBarItem::PanelRole::None) {
            continue;
        }

        const auto label = host == ToolBarItem::Host::Panel ? toolBarPanelRoleLabel(panelRole)
                                                            : toolBarHostLabel(host);
        auto* hostAction = moveMenu->addAction(label);
        hostAction->setCheckable(true);
        hostAction->setChecked(toolBarHost(toolbar) == host);
        hostAction->setEnabled(
            (host != ToolBarItem::Host::ActiveView || canUseViewHost)
            && (host != ToolBarItem::Host::Panel || canUsePanelHost)
        );
        moveGroup->addAction(hostAction);
        QObject::connect(hostAction, &QAction::triggered, this, [manager, toolbar, host] {
            manager->setHostedToolBarHost(toolbar, host);
        });
    }

    if (toolBarHost(toolbar) == ToolBarItem::Host::ActiveView) {
        auto* presentationMenu = menu->addMenu(toolBarPresentationMenuLabel());
        auto* presentationGroup = new QActionGroup(presentationMenu);
        presentationGroup->setExclusive(true);

        for (auto presentation :
             {ToolBarItem::ViewPresentation::Docked, ToolBarItem::ViewPresentation::CenteredOverlay}) {
            auto* presentationAction = presentationMenu->addAction(
                toolBarViewPresentationLabel(presentation)
            );
            presentationAction->setCheckable(true);
            presentationAction->setChecked(toolBarViewPresentation(toolbar) == presentation);
            presentationGroup->addAction(presentationAction);
            QObject::connect(
                presentationAction,
                &QAction::triggered,
                this,
                [manager, toolbar, presentation] {
                    manager->setViewToolBarPresentation(toolbar, presentation);
                }
            );
        }

        if (toolBarViewPresentation(toolbar) == ToolBarItem::ViewPresentation::CenteredOverlay) {
            auto* positionMenu = menu->addMenu(toolBarViewOverlayPositionMenuLabel());
            auto* positionGroup = new QActionGroup(positionMenu);
            positionGroup->setExclusive(true);

            for (auto edge :
                 {ToolBarItem::ViewOverlayEdge::Top, ToolBarItem::ViewOverlayEdge::Bottom}) {
                auto* edgeAction = positionMenu->addAction(toolBarViewOverlayEdgeLabel(edge));
                edgeAction->setCheckable(true);
                edgeAction->setChecked(toolBarViewOverlayEdge(toolbar) == edge);
                positionGroup->addAction(edgeAction);
                QObject::connect(edgeAction, &QAction::triggered, this, [this, toolbar, edge] {
                    setViewOverlayEdge(toolbar, edge);
                });
            }
        }
    }
}

void ToolBarManager::addCurrentToolbarLayoutActions(QMenu* menu)
{
    if (!menu) {
        return;
    }

    const auto showRecommendedOnlyLabel = currentShowRecommendedOnlyLabel();
    const auto resetLabel = currentToolbarLayoutResetLabel();
    const auto recommendedResetLabel = currentRecommendedToolbarLayoutResetLabel();
    if (showRecommendedOnlyLabel.isEmpty() && resetLabel.isEmpty()
        && recommendedResetLabel.isEmpty() && currentViewToolbarLayoutResetLabel().isEmpty()
        && currentRecommendedViewToolbarLayoutResetLabel().isEmpty()) {
        return;
    }

    if (!menu->isEmpty()) {
        menu->addSeparator();
    }

    if (!showRecommendedOnlyLabel.isEmpty()) {
        auto showRecommendedOnlyAction = menu->addAction(showRecommendedOnlyLabel);
        QObject::connect(showRecommendedOnlyAction, &QAction::triggered, [this] {
            showRecommendedToolBarsOnly();
        });
    }

    if (!resetLabel.isEmpty()) {
        auto resetAction = menu->addAction(resetLabel);
        QObject::connect(resetAction, &QAction::triggered, [this] { resetCurrentToolbarLayout(); });
    }

    addCurrentViewToolbarLayoutActions(menu);

    if (!recommendedResetLabel.isEmpty()) {
        auto recommendedResetAction = menu->addAction(recommendedResetLabel);
        QObject::connect(recommendedResetAction, &QAction::triggered, [this] {
            resetCurrentToolbarLayoutToRecommended();
        });
    }
}

void ToolBarManager::addCurrentViewToolbarLayoutActions(QMenu* menu)
{
    if (!menu) {
        return;
    }

    const auto viewResetLabel = currentViewToolbarLayoutResetLabel();
    const auto recommendedViewResetLabel = currentRecommendedViewToolbarLayoutResetLabel();
    if (viewResetLabel.isEmpty() && recommendedViewResetLabel.isEmpty()) {
        return;
    }

    if (!viewResetLabel.isEmpty()) {
        auto viewResetAction = menu->addAction(viewResetLabel);
        QObject::connect(viewResetAction, &QAction::triggered, [this] {
            resetCurrentViewToolbarLayout();
        });
    }

    if (!recommendedViewResetLabel.isEmpty()) {
        auto recommendedViewResetAction = menu->addAction(recommendedViewResetLabel);
        QObject::connect(recommendedViewResetAction, &QAction::triggered, [this] {
            resetCurrentViewToolbarLayoutToRecommended();
        });
    }
}
bool ToolBarManager::eventFilter(QObject* source, QEvent* ev)
{
    bool res = false;
    switch (ev->type()) {
        case QEvent::Show:
        case QEvent::Hide:
            if (auto toolbar = qobject_cast<QToolBar*>(source)) {
                auto parent = toolbar->parentWidget();
                if (parent == menuBarLeftAreaWidget || parent == menuBarRightAreaWidget) {
                    menuBarTimer.start(10);
                }
                if (toolBarHost(toolbar) != ToolBarItem::Host::MainWindow) {
                    refreshHostedToolBars();
                }
            }
            break;
        case QEvent::MouseButtonRelease: {
            auto mev = static_cast<QMouseEvent*>(ev);
            if (mev->button() == Qt::RightButton) {
                if (showContextMenu(source)) {
                    return true;
                }
            }
        }
        // fall through
        case QEvent::MouseMove:
            res = addToolBarToArea(source, static_cast<QMouseEvent*>(ev));
            break;
        case QEvent::ParentChange:
            if (auto toolbar = qobject_cast<QToolBar*>(source)) {
                resizingToolbars[toolbar] = toolbar;
                resizeTimer.start(100);
                if (toolBarHost(toolbar) != ToolBarItem::Host::MainWindow) {
                    refreshHostedToolBars();
                }
            }
            break;
        default:
            break;
    }
    return res;
}

void ToolBarManager::retranslate() const
{
    QList<ToolBar*> toolbars = toolBars();
    for (ToolBar* it : toolbars) {
        QByteArray toolbarName = it->objectName().toUtf8();
        it->setWindowTitle(QApplication::translate("Workbench", (const char*)toolbarName));
    }
}

QString ToolBarManager::currentToolbarLayoutResetLabel() const
{
    if (!rememberToolbarLayoutByWorkbench()) {
        return {};
    }

    switch (currentToolbarLayoutScope()) {
        case CurrentLayoutScope::Contextual:
            return QApplication::translate("MainWindow", "Reset Current Contextual Layout");
        case CurrentLayoutScope::Workbench:
            return QApplication::translate("MainWindow", "Reset Current Workbench Layout");
        case CurrentLayoutScope::None:
            return {};
    }

    return {};
}

QString ToolBarManager::currentRecommendedToolbarLayoutResetLabel() const
{
    if (!rememberToolbarLayoutByWorkbench()) {
        return {};
    }

    switch (currentToolbarLayoutScope()) {
        case CurrentLayoutScope::Contextual:
            return QApplication::translate("MainWindow", "Reset To Recommended Contextual Layout");
        case CurrentLayoutScope::Workbench:
            return QApplication::translate("MainWindow", "Reset To Recommended Workbench Layout");
        case CurrentLayoutScope::None:
            return {};
    }

    return {};
}

QString ToolBarManager::currentViewToolbarLayoutResetLabel() const
{
    if (!rememberToolbarLayoutByWorkbench()
        || currentToolbarLayoutScope() == CurrentLayoutScope::None || !hasViewHostedToolBars()) {
        return {};
    }

    return QApplication::translate("MainWindow", "Reset Current View Toolbar Layout");
}

QString ToolBarManager::currentRecommendedViewToolbarLayoutResetLabel() const
{
    if (!rememberToolbarLayoutByWorkbench()
        || currentToolbarLayoutScope() == CurrentLayoutScope::None || !hasViewHostedToolBars()) {
        return {};
    }

    return QApplication::translate("MainWindow", "Reset To Recommended View Toolbar Layout");
}

QString ToolBarManager::currentShowRecommendedOnlyLabel() const
{
    if (currentToolbarLayoutScope() == CurrentLayoutScope::None) {
        return {};
    }

    return QApplication::translate("MainWindow", "Show Recommended Only");
}

QString ToolBarManager::currentToolbarLayoutScopeLabel() const
{
    switch (currentToolbarLayoutScope()) {
        case CurrentLayoutScope::Contextual:
            return QApplication::translate("MainWindow", "Layout scope: Current contextual mode");
        case CurrentLayoutScope::Workbench:
            return QApplication::translate("MainWindow", "Layout scope: Current workbench");
        case CurrentLayoutScope::None:
            return {};
    }

    return {};
}

void ToolBarManager::resetCurrentToolbarLayout()
{
    QString layoutContext;
    QString activeContext;
    const auto scope = currentToolbarLayoutScope(&layoutContext, &activeContext);
    if (scope == CurrentLayoutScope::None || !rememberToolbarLayoutByWorkbench()) {
        return;
    }

    if (hWorkbenchLayouts->HasGroup(layoutContext.toUtf8().constData())) {
        hWorkbenchLayouts->RemoveGrp(layoutContext.toUtf8().constData());
    }

    const bool hasWorkbenchFallback = scope == CurrentLayoutScope::Contextual
        && hasSavedWorkbenchToolBarLayout(activeContext);

    if (hasWorkbenchFallback) {
        restoreWorkbenchToolBarLayout(activeContext);
    }
    else {
        resetMainWindowToolBarLayout();
    }

    restoreState();
}

void ToolBarManager::resetCurrentToolbarLayoutToRecommended()
{
    if (currentRecommendedToolbarLayoutResetLabel().isEmpty()) {
        return;
    }

    applyRecommendedToolBarPreferences();
    resetCurrentToolbarLayout();
    applyRecommendedToolBarVisibility();
}

void ToolBarManager::resetCurrentViewToolbarLayout()
{
    QString layoutContext;
    QString activeContext;
    const auto scope = currentToolbarLayoutScope(&layoutContext, &activeContext);
    if (scope == CurrentLayoutScope::None || !rememberToolbarLayoutByWorkbench()
        || currentViewToolbarLayoutResetLabel().isEmpty()) {
        return;
    }

    auto hostWindow = activeViewToolBarHostWindow();
    if (!hostWindow) {
        return;
    }

    clearViewToolBarLayout(layoutContext);

    const bool hasWorkbenchFallback = scope == CurrentLayoutScope::Contextual
        && hasSavedViewToolBarLayout(activeContext);
    if (hasWorkbenchFallback) {
        restoreViewHostedToolBarLayout(hostWindow, activeContext);
    }
    else {
        resetViewHostedToolBarLayout(hostWindow);
    }
}

void ToolBarManager::resetCurrentViewToolbarLayoutToRecommended()
{
    if (currentRecommendedViewToolbarLayoutResetLabel().isEmpty()) {
        return;
    }

    applyRecommendedViewToolBarPreferences();
    resetCurrentViewToolbarLayout();
    applyRecommendedViewToolBarVisibility();
}

void ToolBarManager::showRecommendedToolBarsOnly()
{
    if (currentShowRecommendedOnlyLabel().isEmpty()) {
        return;
    }

    applyRecommendedToolBarPreferences();
    applyRecommendedToolBarVisibility();
}

void ToolBarManager::refreshHostedToolBars()
{
    refreshPanelHostedToolBars();
    refreshViewHostedToolBars();
}

void ToolBarManager::setViewOverlayEdge(QToolBar* toolbar, ToolBarItem::ViewOverlayEdge edge) const
{
    if (!toolbar
        || toolBarViewPresentation(toolbar) != ToolBarItem::ViewPresentation::CenteredOverlay) {
        return;
    }

    setToolBarViewOverlayEdge(toolbar, edge);

    const auto context = effectiveToolbarLayoutContext();
    if (!context.isEmpty()) {
        persistViewOverlayEdge(toolbar, context, edge);
    }

    auto hostWindow = activeViewToolBarHostWindow();
    if (hostWindow && activeViewSupportsToolBarHost(toolbar, hostWindow)) {
        if (auto overlayHost = viewToolBarOverlayHost(hostWindow)) {
            overlayHost->attachToolBar(toolbar, edge);
        }
    }
}

void ToolBarManager::setToolbarLayoutContextOverride(const QString& workbench, const QString& context)
{
    if (toolbarLayoutContextOverrideWorkbench == workbench
        && toolbarLayoutContextOverride == context && effectiveToolbarLayoutContext() == context) {
        return;
    }

    bool affectsCurrentLayout = activeToolbarLayoutContext() == workbench;
    if (affectsCurrentLayout) {
        saveState();
    }

    toolbarLayoutContextOverrideWorkbench = workbench;
    toolbarLayoutContextOverride = context;

    if (affectsCurrentLayout) {
        restoreState();
    }
}

void ToolBarManager::clearToolbarLayoutContextOverride(const QString& workbench)
{
    if (toolbarLayoutContextOverrideWorkbench != workbench) {
        return;
    }

    bool affectsCurrentLayout = activeToolbarLayoutContext() == workbench;
    if (affectsCurrentLayout) {
        saveState();
    }

    toolbarLayoutContextOverrideWorkbench.clear();
    toolbarLayoutContextOverride.clear();

    if (affectsCurrentLayout) {
        restoreState();
    }
}

bool Gui::ToolBarManager::areToolBarsLocked() const
{
    return hGeneral->GetBool("LockToolBars", false);
}

void Gui::ToolBarManager::setToolBarsLocked(bool locked) const
{
    hGeneral->SetBool("LockToolBars", locked);

    setMovable(!locked);
}

void Gui::ToolBarManager::setMovable(bool movable) const
{
    for (auto& tb : toolBars()) {
        const bool overlayToolbar = toolBarHost(tb) == ToolBarItem::Host::ActiveView
            && toolBarViewPresentation(tb) == ToolBarItem::ViewPresentation::CenteredOverlay;
        const bool panelToolbar = toolBarHost(tb) == ToolBarItem::Host::Panel;
        tb->setMovable((overlayToolbar || panelToolbar) ? false : movable);
        tb->updateCustomGripVisibility();
    }
}

ToolBar* ToolBarManager::findToolBar(const QList<ToolBar*>& toolbars, const QString& item) const
{
    for (ToolBar* it : toolbars) {
        if (toolBarPersistenceKey(it) == item || it->objectName() == item) {
            return it;
        }
    }

    return nullptr;  // no item with the user data found
}

QAction* ToolBarManager::findAction(const QList<QAction*>& acts, const QString& item) const
{
    for (QAction* it : acts) {
        if (it->data().toString() == item) {
            return it;
        }
    }

    return nullptr;  // no item with the user data found
}

QList<ToolBar*> ToolBarManager::toolBars() const
{
    auto mw = getMainWindow();

    QList<ToolBar*> tb;
    QList<ToolBar*> bars = getMainWindow()->findChildren<ToolBar*>();

    for (ToolBar* it : bars) {
        for (auto parent = it->parentWidget(); parent; parent = parent->parentWidget()) {
            if (parent == mw || parent == mw->statusBar() || parent == statusBarAreaWidget
                || parent == menuBarLeftAreaWidget || parent == menuBarRightAreaWidget
                || qobject_cast<MDIView*>(parent)) {
                tb.push_back(it);
                it->installEventFilter(const_cast<ToolBarManager*>(this));
                break;
            }
        }
    }

    return tb;
}

QMainWindow* ToolBarManager::toolBarHostWindow(const QToolBar* toolbar) const
{
    if (!toolbar) {
        return nullptr;
    }

    return ::toolBarHostWindow(toolbar);
}

void ToolBarManager::refreshPanelHostedToolBars()
{
    if (refreshingPanelHostedToolBars) {
        return;
    }

    struct RefreshGuard
    {
        bool& refreshing;
        ~RefreshGuard()
        {
            refreshing = false;
        }
    };

    refreshingPanelHostedToolBars = true;
    RefreshGuard refreshGuard {refreshingPanelHostedToolBars};

    for (auto toolbar : toolBars()) {
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::Panel || toolbar->isFloating()) {
            continue;
        }

        auto action = toolbar->toggleViewAction();
        const auto role = toolBarPanelRole(toolbar);
        auto panel = activePanelToolBarHostPanel(role);
        const bool compatible = activePanelSupportsToolBarHost(toolbar, panel);
        if (action) {
            action->setVisible(compatible || toolbar->isVisible());
            action->setEnabled(compatible);
        }
        if (!compatible) {
            continue;
        }

        if (auto host = panelToolBarHost(panel, role)) {
            host->attachToolBar(toolbar);
            setToolBarIconSize(toolbar);
        }
    }
}

void ToolBarManager::restoreViewHostedToolBarLayout(
    QMainWindow* hostWindow,
    const QString& context,
    const QString& fallbackContext
) const
{
    auto group = workbenchLayoutGroup(context);
    const bool hasSavedDockedLayout = group && group->GetBool("Saved", false);
    const bool hasSavedOverlayEdges = viewOverlayEdgeGroup(context)
        && !viewOverlayEdgeGroup(context)->GetASCIIMap().empty();
    if (!hostWindow || !group || (!hasSavedDockedLayout && !hasSavedOverlayEdges)) {
        return;
    }

    auto mdiView = qobject_cast<MDIView*>(hostWindow);
    QMap<QString, ToolBar*> viewToolbars;
    for (auto toolbar : toolBars()) {
        auto key = toolBarPersistenceKey(toolbar);
        if (key.isEmpty() || toolbar->isFloating()
            || toolBarHost(toolbar) != ToolBarItem::Host::ActiveView
            || !activeViewSupportsToolBarHost(toolbar, mdiView)
            || toolBarHostWindow(toolbar) != hostWindow) {
            continue;
        }

        if (toolBarViewPresentation(toolbar) == ToolBarItem::ViewPresentation::CenteredOverlay) {
            setToolBarViewOverlayEdge(
                toolbar,
                resolvedViewOverlayEdge(toolbar, context, fallbackContext)
            );
            if (auto overlayHost = viewToolBarOverlayHost(mdiView)) {
                overlayHost->attachToolBar(toolbar, toolBarViewOverlayEdge(toolbar));
            }
            continue;
        }
        if (toolBarViewPresentation(toolbar) != ToolBarItem::ViewPresentation::Docked) {
            continue;
        }

        viewToolbars.insert(key, toolbar);
    }

    if (viewToolbars.isEmpty()) {
        return;
    }

    QStringList top = splitLayoutState(group->GetASCII(ViewTopLayoutKey));
    QStringList left = splitLayoutState(group->GetASCII(ViewLeftLayoutKey));
    QStringList right = splitLayoutState(group->GetASCII(ViewRightLayoutKey));
    QStringList bottom = splitLayoutState(group->GetASCII(ViewBottomLayoutKey));

    QSet<QString> knownKeys;
    auto rememberKeys = [&knownKeys](const QStringList& layout) {
        for (const auto& key : layout) {
            if (key != QStringLiteral("Break")) {
                knownKeys.insert(key);
            }
        }
    };
    rememberKeys(top);
    rememberKeys(left);
    rememberKeys(right);
    rememberKeys(bottom);

    auto appendMissing =
        [&viewToolbars, &knownKeys, hostWindow](QStringList& layout, Qt::ToolBarArea area) {
            for (auto it = viewToolbars.cbegin(); it != viewToolbars.cend(); ++it) {
                if (knownKeys.contains(it.key()) || hostWindow->toolBarArea(it.value()) != area) {
                    continue;
                }

                layout << it.key();
                knownKeys.insert(it.key());
            }
        };
    appendMissing(top, Qt::TopToolBarArea);
    appendMissing(left, Qt::LeftToolBarArea);
    appendMissing(right, Qt::RightToolBarArea);
    appendMissing(bottom, Qt::BottomToolBarArea);

    auto restore = [&viewToolbars, hostWindow](const QStringList& layout, Qt::ToolBarArea area) {
        for (const auto& key : layout) {
            if (key == QStringLiteral("Break")) {
                hostWindow->addToolBarBreak(area);
                continue;
            }

            auto toolbar = viewToolbars.value(key);
            if (!toolbar) {
                continue;
            }

            moveToolBarPreservingVisibility(hostWindow, toolbar, area);
        }
    };

    restore(top, Qt::TopToolBarArea);
    restore(left, Qt::LeftToolBarArea);
    restore(right, Qt::RightToolBarArea);
    restore(bottom, Qt::BottomToolBarArea);
}

void ToolBarManager::refreshViewHostedToolBars()
{
    if (refreshingViewHostedToolBars) {
        return;
    }

    struct RefreshGuard
    {
        bool& refreshing;
        ~RefreshGuard()
        {
            refreshing = false;
        }
    };

    refreshingViewHostedToolBars = true;
    RefreshGuard refreshGuard {refreshingViewHostedToolBars};

    auto hostWindow = activeViewToolBarHostWindow();
    bool hasCompatibleDockedToolbar = false;

    for (auto toolbar : toolBars()) {
        if (!toolbar || toolBarHost(toolbar) != ToolBarItem::Host::ActiveView
            || toolbar->isFloating()) {
            continue;
        }

        auto action = toolbar->toggleViewAction();
        const bool compatible = activeViewSupportsToolBarHost(toolbar, hostWindow);
        if (action) {
            action->setVisible(compatible);
            action->setEnabled(compatible);
        }
        if (!compatible) {
            continue;
        }

        if (toolBarViewPresentation(toolbar) == ToolBarItem::ViewPresentation::CenteredOverlay) {
            if (auto overlayHost = viewToolBarOverlayHost(hostWindow)) {
                overlayHost->attachToolBar(toolbar, toolBarViewOverlayEdge(toolbar));
            }
            setToolBarIconSize(toolbar);
            continue;
        }

        hasCompatibleDockedToolbar = true;
        if (toolBarHostWindow(toolbar) == hostWindow) {
            continue;
        }

        toolbar->setOrientation(Qt::Horizontal);
        moveToolBarPreservingVisibility(hostWindow, toolbar, Qt::TopToolBarArea);
        setToolBarIconSize(toolbar);
    }

    if (hasCompatibleDockedToolbar) {
        restoreViewHostedToolBarLayout(hostWindow, effectiveToolbarLayoutContext());
    }
}

ToolBarItem::DefaultVisibility ToolBarManager::getToolbarPolicy(const QToolBar* toolbar) const
{
    auto* action = toolbar->toggleViewAction();

    QVariant property = action->property("DefaultVisibility");
    if (property.isNull()) {
        return ToolBarItem::DefaultVisibility::Visible;
    }

    return static_cast<ToolBarItem::DefaultVisibility>(property.toInt());
}

void ToolBarManager::setState(const QList<QString>& names, State state)
{
    for (auto& name : names) {
        setState(name, state);
    }
}

void ToolBarManager::setState(const QString& name, State state)
{
    QToolBar* tb = findToolBar(toolBars(), name);
    const auto visibilityValues = toLookup<bool>(hPref, [](const auto& group) {
        return group->GetBoolMap();
    });
    auto visibility = [this, name, tb, &visibilityValues](bool defaultvalue) {
        bool value = defaultvalue;
        if (tb && lookupToolBarValue(visibilityValues, {}, tb, &value)) {
            return value;
        }

        return hPref->GetBool(name.toStdString().c_str(), defaultvalue);
    };

    auto saveVisibility = [this, visibility, name](bool value, ToolBarItem::DefaultVisibility policy) {
        auto show = visibility(policy == ToolBarItem::DefaultVisibility::Visible);

        if (show != value) {
            blockRestore = true;
            hPref->SetBool(name.toStdString().c_str(), value);
        }
    };

    auto showhide = [visibility](QToolBar* toolbar, ToolBarItem::DefaultVisibility policy) {
        auto show = visibility(policy == ToolBarItem::DefaultVisibility::Visible);

        if (show) {
            toolbar->show();
        }
        else {
            toolbar->hide();
        }
    };

    if (tb) {

        auto policy = getToolbarPolicy(tb);

        if (state == State::RestoreDefault) {
            if (policy == ToolBarItem::DefaultVisibility::Unavailable) {
                tb->hide();
                tb->toggleViewAction()->setVisible(false);
            }
            else {
                tb->toggleViewAction()->setVisible(true);

                showhide(tb, policy);
            }
        }
        else if (state == State::ForceAvailable) {
            tb->toggleViewAction()->setVisible(true);

            // Unavailable policy defaults to Visible when made available.
            auto show = visibility(
                policy == ToolBarItem::DefaultVisibility::Visible
                || policy == ToolBarItem::DefaultVisibility::Unavailable
            );

            if (show) {
                tb->show();
            }
            else {
                tb->hide();
            }
        }
        else if (state == State::ForceHidden) {
            tb->toggleViewAction()->setVisible(false);  // not visible in context menus
            tb->hide();                                 // toolbar not visible
        }
        else if (state == State::SaveState) {
            auto show = tb->isVisible();
            saveVisibility(show, policy);
        }
    }
}

#include "moc_ToolBarManager.cpp"
