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

#include <array>

#include <QColor>
#include <QObject>
#include <QPointer>
#include <QWidget>

#include "ToolBarManager.h"

class QBoxLayout;
class QEvent;
class QRect;
class QString;
class QToolBar;

namespace Gui
{

class ViewToolBarOverlayLane: public QWidget
{
    Q_OBJECT
    Q_PROPERTY(QColor panelColor READ panelColor WRITE setPanelColor)
    Q_PROPERTY(QColor borderColor READ borderColor WRITE setBorderColor)
    Q_PROPERTY(QColor shadowColor READ shadowColor WRITE setShadowColor)
    Q_PROPERTY(int radius READ radius WRITE setRadius)
    Q_PROPERTY(int shadowOffsetY READ shadowOffsetY WRITE setShadowOffsetY)

public:
    static constexpr auto RoleProperty = "overlayRole";
    static constexpr auto EdgeProperty = "overlayEdge";
    static constexpr auto RoleValue = "view-toolbar-lane";
    static constexpr auto TopLaneObjectName = "_fc_view_toolbar_overlay_top_lane";

    explicit ViewToolBarOverlayLane(ToolBarItem::ViewOverlayEdge edge, QWidget* parent);

    QColor panelColor() const;
    void setPanelColor(const QColor& color);

    QColor borderColor() const;
    void setBorderColor(const QColor& color);

    QColor shadowColor() const;
    void setShadowColor(const QColor& color);

    int radius() const;
    void setRadius(int value);

    int shadowOffsetY() const;
    void setShadowOffsetY(int value);

    void applyOverlayStyleSheet();
    void attachToolBar(QToolBar* toolbar);
    void refreshGeometry(const QRect& rect);

protected:
    void paintEvent(QPaintEvent*) override;

private:
    static QString overlayEdgeName(ToolBarItem::ViewOverlayEdge edge);
    bool hasVisibleToolBar() const;

    ToolBarItem::ViewOverlayEdge edge;
    QColor panelColorValue;
    QColor borderColorValue;
    QColor shadowColorValue;
    int radiusValue;
    int shadowOffsetYValue;
    QBoxLayout* layout;
};

class ViewToolBarOverlayHost: public QObject
{
    Q_OBJECT

public:
    static constexpr auto ObjectName = "_fc_view_toolbar_overlay_host";

    explicit ViewToolBarOverlayHost(QWidget* anchor);

    void attachToolBar(QToolBar* toolbar, ToolBarItem::ViewOverlayEdge edge);
    void refreshGeometry();

protected:
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    ViewToolBarOverlayLane* ensureLane(ToolBarItem::ViewOverlayEdge edge);

    QPointer<QWidget> anchor;
    std::array<QPointer<ViewToolBarOverlayLane>, 4> lanes;
};

}  // namespace Gui
