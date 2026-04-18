// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2026 FreeCAD contributors                               *
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

#include <BRepLib.hxx>
#include <HLRAlgo_Projector.hxx>
#include <HLRBRep_Algo.hxx>
#include <HLRBRep_HLRToShape.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>

#include "ProjectionAlgos.h"


namespace Part
{
namespace
{

TopoDS_Shape build3dCurves(TopoDS_Shape shape)
{
    for (TopExp_Explorer it(shape, TopAbs_EDGE); it.More(); it.Next()) {
        BRepLib::BuildCurve3d(TopoDS::Edge(it.Current()));
    }
    return shape;
}

}  // namespace

ProjectionAlgos::ProjectionAlgos(const TopoDS_Shape& input, const Base::Vector3d& dir)
    : Input(input)
    , Direction(dir)
{
    execute();
}

ProjectionAlgos::~ProjectionAlgos() = default;

void ProjectionAlgos::execute()
{
    Handle(HLRBRep_Algo) brep_hlr = new HLRBRep_Algo;
    brep_hlr->Add(Input);

    gp_Ax2 transform(gp_Pnt(0, 0, 0), gp_Dir(Direction.x, Direction.y, Direction.z));
    HLRAlgo_Projector projector(transform);
    brep_hlr->Projector(projector);
    brep_hlr->Update();
    brep_hlr->Hide();

    HLRBRep_HLRToShape shapes(brep_hlr);

    V = build3dCurves(shapes.VCompound());
    V1 = build3dCurves(shapes.Rg1LineVCompound());
    VN = build3dCurves(shapes.RgNLineVCompound());
    VO = build3dCurves(shapes.OutLineVCompound());
    VI = build3dCurves(shapes.IsoLineVCompound());
    H = build3dCurves(shapes.HCompound());
    H1 = build3dCurves(shapes.Rg1LineHCompound());
    HN = build3dCurves(shapes.RgNLineHCompound());
    HO = build3dCurves(shapes.OutLineHCompound());
    HI = build3dCurves(shapes.IsoLineHCompound());
}

}  // namespace Part
