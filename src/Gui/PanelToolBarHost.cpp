/***************************************************************************
 *   Copyright (c) 2026                                                    *
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

#include "PanelToolBarHost.h"

#include <QEvent>
#include <QHBoxLayout>
#include <QMainWindow>
#include <QToolBar>

using namespace Gui;

namespace
{

QMainWindow* toolBarHostWindow(const QWidget* widget)
{
    for (auto current = widget; current; current = current->parentWidget()) {
        if (auto hostWindow = qobject_cast<QMainWindow*>(const_cast<QWidget*>(current))) {
            return hostWindow;
        }
    }

    return nullptr;
}

QString panelRoleName(ToolBarItem::PanelRole role)
{
    return ToolBarManager::toolBarPanelRoleName(role);
}

}  // namespace

PanelToolBarHost::PanelToolBarHost(ToolBarItem::PanelRole role, QWidget* parent)
    : QWidget(parent)
    , roleValue(role)
    , layout(new QHBoxLayout(this))
{
    setContentsMargins(0, 0, 0, 0);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);
    setProperty(RoleProperty, panelRoleName(role));
    if (role == ToolBarItem::PanelRole::ModelTree) {
        setObjectName(QString::fromLatin1(ModelTreeObjectName));
    }
    hide();
}

ToolBarItem::PanelRole PanelToolBarHost::panelRole() const
{
    return roleValue;
}

void PanelToolBarHost::attachToolBar(QToolBar* toolbar)
{
    if (!toolbar) {
        return;
    }

    const bool visible = toolbar->isVisible();
    if (auto hostWindow = toolBarHostWindow(toolbar)) {
        if (hostWindow->toolBarArea(toolbar) != Qt::NoToolBarArea) {
            hostWindow->removeToolBarBreak(toolbar);
            hostWindow->removeToolBar(toolbar);
        }
    }

    if (toolbar->parentWidget() == this) {
        if (layout->indexOf(toolbar) < 0) {
            layout->addWidget(toolbar);
        }
    }
    else {
        if (auto parentLayout = toolbar->parentWidget() ? toolbar->parentWidget()->layout()
                                                        : nullptr) {
            parentLayout->removeWidget(toolbar);
        }
        toolbar->setParent(this);
        layout->addWidget(toolbar);
    }

    toolbar->setOrientation(Qt::Horizontal);
    toolbar->installEventFilter(this);
    toolbar->setVisible(visible);
    refreshVisibility();
}

bool PanelToolBarHost::eventFilter(QObject* watched, QEvent* event)
{
    if (qobject_cast<QToolBar*>(watched)) {
        switch (event->type()) {
            case QEvent::Show:
            case QEvent::Hide:
            case QEvent::LayoutRequest:
            case QEvent::ParentChange:
                refreshVisibility();
                break;
            default:
                break;
        }
    }

    return QWidget::eventFilter(watched, event);
}

void PanelToolBarHost::refreshVisibility()
{
    bool anyVisible = false;
    for (auto* toolbar : findChildren<QToolBar*>(QString(), Qt::FindDirectChildrenOnly)) {
        if (!toolbar->isHidden()) {
            anyVisible = true;
            break;
        }
    }

    setVisible(anyVisible);
}
