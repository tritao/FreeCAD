// SPDX-License-Identifier: LGPL-2.1-or-later
/***************************************************************************
 *   Copyright (c) 2015 Thomas Anderson <blobfish[at]gmx.com>              *
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


#include "DAGModelGraph.h"


using namespace Gui;
using namespace DAG;

VertexProperty::VertexProperty()
    : rectangle(new RectItem())
    , point(new QGraphicsEllipseItem())
    , visibleIcon(new QGraphicsPixmapItem())
    , stateIcon(new QGraphicsPixmapItem())
    , icon(new QGraphicsPixmapItem())
    , text(new QGraphicsTextItem())
{
    // set z values.
    this->rectangle->setZValue(-1000.0);
    this->point->setZValue(1000.0);
    this->visibleIcon->setZValue(0.0);
    this->stateIcon->setZValue(0.0);
    this->icon->setZValue(0.0);
    this->text->setZValue(0.0);
}

EdgeProperty::EdgeProperty() = default;

bool Gui::DAG::hasRecord(const App::DocumentObject* dObjectIn, const GraphLinkContainer& containerIn)
{
    return containerIn.byDObject.find(dObjectIn) != containerIn.byDObject.end();
}

bool Gui::DAG::hasRecord(
    const ViewProviderDocumentObject* VPDObjectIn,
    const GraphLinkContainer& containerIn
)
{
    return containerIn.byVPDObject.find(VPDObjectIn) != containerIn.byVPDObject.end();
}

const GraphLinkRecord& Gui::DAG::findRecord(Vertex vertexIn, const GraphLinkContainer& containerIn)
{
    auto it = containerIn.byVertex.find(vertexIn);
    assert(it != containerIn.byVertex.end());
    return *it->second;
}

const GraphLinkRecord& Gui::DAG::findRecord(
    const App::DocumentObject* dObjectIn,
    const GraphLinkContainer& containerIn
)
{
    auto it = containerIn.byDObject.find(dObjectIn);
    assert(it != containerIn.byDObject.end());
    return *it->second;
}

const GraphLinkRecord& Gui::DAG::findRecord(
    const ViewProviderDocumentObject* VPDObjectIn,
    const GraphLinkContainer& containerIn
)
{
    auto it = containerIn.byVPDObject.find(VPDObjectIn);
    assert(it != containerIn.byVPDObject.end());
    return *it->second;
}

const GraphLinkRecord& Gui::DAG::findRecord(const RectItem* rectIn, const GraphLinkContainer& containerIn)
{
    auto it = containerIn.byRectItem.find(rectIn);
    assert(it != containerIn.byRectItem.end());
    return *it->second;
}

const GraphLinkRecord& Gui::DAG::findRecord(
    const std::string& stringIn,
    const GraphLinkContainer& containerIn
)
{
    auto it = containerIn.byUniqueName.find(stringIn);
    assert(it != containerIn.byUniqueName.end());
    return *it->second;
}

void Gui::DAG::eraseRecord(const ViewProviderDocumentObject* VPDObjectIn, GraphLinkContainer& containerIn)
{
    auto it = containerIn.byVPDObject.find(VPDObjectIn);
    assert(it != containerIn.byVPDObject.end());

    const auto listIt = it->second;

    containerIn.byDObject.erase(listIt->DObject);
    containerIn.byRectItem.erase(listIt->rectItem);
    containerIn.byUniqueName.erase(listIt->uniqueName);
    containerIn.byVertex.erase(listIt->vertex);
    containerIn.byVPDObject.erase(it);
    containerIn.records.erase(listIt);
}
