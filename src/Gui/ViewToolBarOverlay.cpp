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

#include "ViewToolBarOverlay.h"

#include <QBoxLayout>
#include <QPainter>
#include <QStyle>
#include <QToolBar>

#include <algorithm>
#include <vector>

#include <Base/Parameter.h>

#include "Application.h"
#include "MainWindow.h"
#include "OverlayManager.h"

using namespace Gui;

namespace
{
constexpr int ViewToolBarOverlayMargin = 12;
constexpr int ViewToolBarOverlaySpacing = 6;
constexpr int ViewToolBarOverlayPaddingX = 8;
constexpr int ViewToolBarOverlayPaddingY = 4;
constexpr int ViewToolBarOverlayRadius = 6;
constexpr int ViewToolBarOverlayShadowOffsetY = 2;

QMainWindow* toolBarHostWindow(const QWidget* widget)
{
    for (auto current = widget; current; current = current->parentWidget()) {
        if (auto hostWindow = qobject_cast<QMainWindow*>(const_cast<QWidget*>(current))) {
            return hostWindow;
        }
    }

    return nullptr;
}

class ViewToolBarOverlayStyleObserver: public ParameterGrp::ObserverType
{
public:
    ViewToolBarOverlayStyleObserver()
    {
        mainWindowHandle = App::GetApplication().GetParameterGroupByPath(
            "User parameter:BaseApp/Preferences/MainWindow"
        );
        themesHandle = App::GetApplication().GetParameterGroupByPath(
            "User parameter:BaseApp/Preferences/Themes"
        );
        mainWindowHandle->Attach(this);
        themesHandle->Attach(this);
    }

    static ViewToolBarOverlayStyleObserver* instance()
    {
        static ViewToolBarOverlayStyleObserver observer;
        return &observer;
    }

    void registerLane(ViewToolBarOverlayLane* lane)
    {
        if (!lane) {
            return;
        }

        for (const auto& existing : lanes) {
            if (existing == lane) {
                return;
            }
        }

        lanes.push_back(lane);
    }

    void OnChange(Base::Subject<const char*>&, const char* reason)
    {
        if (!reason) {
            return;
        }

        if (strcmp(reason, "StyleSheet") != 0 && strcmp(reason, "OverlayActiveStyleSheet") != 0
            && strcmp(reason, "Theme") != 0 && strcmp(reason, "ThemeStyleParametersFile") != 0
            && strcmp(reason, "ThemeStyleParametersFiles") != 0
            && strcmp(reason, "ThemeAccentColor1") != 0 && strcmp(reason, "ThemeAccentColor2") != 0) {
            return;
        }

        OverlayManager::instance()->refresh(nullptr, true);
        lanes.erase(
            std::remove_if(
                lanes.begin(),
                lanes.end(),
                [](const auto& lane) {
                    if (!lane) {
                        return true;
                    }
                    lane->applyOverlayStyleSheet();
                    return false;
                }
            ),
            lanes.end()
        );
    }

private:
    ParameterGrp::handle mainWindowHandle;
    ParameterGrp::handle themesHandle;
    std::vector<QPointer<ViewToolBarOverlayLane>> lanes;
};

}  // namespace

ViewToolBarOverlayLane::ViewToolBarOverlayLane(ToolBarItem::ViewOverlayEdge edge, QWidget* parent)
    : QWidget(parent)
    , edge(edge)
    , panelColorValue(QColor::fromRgb(25, 25, 25, 220))
    , borderColorValue(QColor::fromRgb(110, 110, 110, 160))
    , shadowColorValue(QColor::fromRgb(0, 0, 0, 45))
    , radiusValue(ViewToolBarOverlayRadius)
    , shadowOffsetYValue(ViewToolBarOverlayShadowOffsetY)
    , layout(new QBoxLayout(
          edge == ToolBarItem::ViewOverlayEdge::Left || edge == ToolBarItem::ViewOverlayEdge::Right
              ? QBoxLayout::TopToBottom
              : QBoxLayout::LeftToRight,
          this
      ))
{
    setAttribute(Qt::WA_NoSystemBackground);
    setAttribute(Qt::WA_TranslucentBackground);
    setContentsMargins(0, 0, 0, 0);
    setProperty(RoleProperty, QLatin1String(RoleValue));
    setProperty(EdgeProperty, overlayEdgeName(edge));
    layout->setContentsMargins(
        ViewToolBarOverlayPaddingX,
        ViewToolBarOverlayPaddingY,
        ViewToolBarOverlayPaddingX,
        ViewToolBarOverlayPaddingY
    );
    layout->setSpacing(ViewToolBarOverlaySpacing);
    layout->setSizeConstraint(QLayout::SetFixedSize);
    applyOverlayStyleSheet();
    hide();
}

QColor ViewToolBarOverlayLane::panelColor() const
{
    return panelColorValue;
}

void ViewToolBarOverlayLane::setPanelColor(const QColor& color)
{
    if (panelColorValue == color) {
        return;
    }
    panelColorValue = color;
    update();
}

QColor ViewToolBarOverlayLane::borderColor() const
{
    return borderColorValue;
}

void ViewToolBarOverlayLane::setBorderColor(const QColor& color)
{
    if (borderColorValue == color) {
        return;
    }
    borderColorValue = color;
    update();
}

QColor ViewToolBarOverlayLane::shadowColor() const
{
    return shadowColorValue;
}

void ViewToolBarOverlayLane::setShadowColor(const QColor& color)
{
    if (shadowColorValue == color) {
        return;
    }
    shadowColorValue = color;
    update();
}

int ViewToolBarOverlayLane::radius() const
{
    return radiusValue;
}

void ViewToolBarOverlayLane::setRadius(int value)
{
    if (radiusValue == value) {
        return;
    }
    radiusValue = value;
    update();
}

int ViewToolBarOverlayLane::shadowOffsetY() const
{
    return shadowOffsetYValue;
}

void ViewToolBarOverlayLane::setShadowOffsetY(int value)
{
    if (shadowOffsetYValue == value) {
        return;
    }
    shadowOffsetYValue = value;
    update();
}

void ViewToolBarOverlayLane::applyOverlayStyleSheet()
{
    const QString stylesheet = OverlayManager::instance()->getStyleSheet();
    if (styleSheet() != stylesheet) {
        setStyleSheet(stylesheet);
    }
    style()->unpolish(this);
    style()->polish(this);
    update();
}

void ViewToolBarOverlayLane::attachToolBar(QToolBar* toolbar)
{
    if (!toolbar) {
        return;
    }

    auto* previousLane = dynamic_cast<ViewToolBarOverlayLane*>(toolbar->parentWidget());
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

    if (previousLane && previousLane != this && previousLane->parentWidget()) {
        previousLane->refreshGeometry(previousLane->parentWidget()->rect());
    }

    toolbar->setOrientation(
        edge == ToolBarItem::ViewOverlayEdge::Left || edge == ToolBarItem::ViewOverlayEdge::Right
            ? Qt::Vertical
            : Qt::Horizontal
    );
    toolbar->setVisible(visible);
    toolbar->raise();
}

void ViewToolBarOverlayLane::refreshGeometry(const QRect& rect)
{
    if (!hasVisibleToolBar()) {
        hide();
        return;
    }

    adjustSize();
    const auto size = sizeHint();
    QPoint topLeft;
    switch (edge) {
        case ToolBarItem::ViewOverlayEdge::Top:
            topLeft = {
                rect.x() + (rect.width() - size.width()) / 2,
                rect.y() + ViewToolBarOverlayMargin,
            };
            break;
        case ToolBarItem::ViewOverlayEdge::Bottom:
            topLeft = {
                rect.x() + (rect.width() - size.width()) / 2,
                rect.y() + rect.height() - size.height() - ViewToolBarOverlayMargin,
            };
            break;
        case ToolBarItem::ViewOverlayEdge::Left:
            topLeft = {
                rect.x() + ViewToolBarOverlayMargin,
                rect.y() + (rect.height() - size.height()) / 2,
            };
            break;
        case ToolBarItem::ViewOverlayEdge::Right:
            topLeft = {
                rect.x() + rect.width() - size.width() - ViewToolBarOverlayMargin,
                rect.y() + (rect.height() - size.height()) / 2,
            };
            break;
    }

    setGeometry(QRect(topLeft, size));
    raise();
    show();
}

void ViewToolBarOverlayLane::paintEvent(QPaintEvent*)
{
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing, true);

    painter.setPen(Qt::NoPen);
    painter.setBrush(shadowColorValue);
    painter.drawRoundedRect(rect().adjusted(1, shadowOffsetYValue, -1, -1), radiusValue, radiusValue);

    painter.setPen(QPen(borderColorValue, 1));
    painter.setBrush(panelColorValue);
    painter.drawRoundedRect(rect().adjusted(0, 0, -1, -shadowOffsetYValue), radiusValue, radiusValue);
}

QString ViewToolBarOverlayLane::overlayEdgeName(ToolBarItem::ViewOverlayEdge edge)
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

bool ViewToolBarOverlayLane::hasVisibleToolBar() const
{
    for (auto toolbar : findChildren<QToolBar*>(QString(), Qt::FindDirectChildrenOnly)) {
        if (!toolbar->isHidden()) {
            return true;
        }
    }

    return false;
}

ViewToolBarOverlayHost::ViewToolBarOverlayHost(QWidget* anchor)
    : QObject(anchor)
    , anchor(anchor)
{
    setObjectName(QString::fromLatin1(ObjectName));
    if (anchor) {
        anchor->installEventFilter(this);
    }
}

void ViewToolBarOverlayHost::attachToolBar(QToolBar* toolbar, ToolBarItem::ViewOverlayEdge edge)
{
    if (!anchor || !toolbar) {
        return;
    }

    auto lane = ensureLane(edge);
    lane->attachToolBar(toolbar);
    toolbar->installEventFilter(this);
    refreshGeometry();
}

void ViewToolBarOverlayHost::refreshGeometry()
{
    if (!anchor) {
        return;
    }

    for (auto lane : lanes) {
        if (lane) {
            lane->refreshGeometry(anchor->rect());
        }
    }
}

bool ViewToolBarOverlayHost::eventFilter(QObject* watched, QEvent* event)
{
    if (watched == anchor) {
        switch (event->type()) {
            case QEvent::Resize:
            case QEvent::Show:
            case QEvent::LayoutRequest:
                refreshGeometry();
                break;
            default:
                break;
        }
    }
    else if (qobject_cast<QToolBar*>(watched)) {
        switch (event->type()) {
            case QEvent::Show:
            case QEvent::Hide:
            case QEvent::LayoutRequest:
            case QEvent::ParentChange:
                refreshGeometry();
                break;
            default:
                break;
        }
    }

    return QObject::eventFilter(watched, event);
}

ViewToolBarOverlayLane* ViewToolBarOverlayHost::ensureLane(ToolBarItem::ViewOverlayEdge edge)
{
    auto& lane = lanes[static_cast<int>(edge)];
    if (!lane) {
        lane = new ViewToolBarOverlayLane(edge, anchor);
        ViewToolBarOverlayStyleObserver::instance()->registerLane(lane);
        if (edge == ToolBarItem::ViewOverlayEdge::Top) {
            lane->setObjectName(QString::fromLatin1(ViewToolBarOverlayLane::TopLaneObjectName));
        }
    }

    return lane;
}
