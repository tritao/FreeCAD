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

#pragma once

#include <QPointer>
#include <QWidget>

#include "ToolBarManager.h"

class QEvent;
class QHBoxLayout;
class QToolBar;

namespace Gui
{

class PanelToolBarHost: public QWidget
{
    Q_OBJECT

public:
    static constexpr auto RoleProperty = "panelRole";
    static constexpr auto ModelTreeObjectName = "_fc_panel_toolbar_host_model_tree";

    explicit PanelToolBarHost(ToolBarItem::PanelRole role, QWidget* parent = nullptr);

    ToolBarItem::PanelRole panelRole() const;
    void attachToolBar(QToolBar* toolbar);

protected:
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    void refreshVisibility();

    ToolBarItem::PanelRole roleValue;
    QHBoxLayout* layout;
};

}  // namespace Gui
