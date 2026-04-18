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

#pragma once

#include <TopoDS_Shape.hxx>

#include <Base/Vector3D.h>
#include <Mod/Part/PartGlobal.h>


namespace Part
{

class PartExport ProjectionAlgos
{
public:
    ProjectionAlgos(const TopoDS_Shape& input, const Base::Vector3d& dir);
    virtual ~ProjectionAlgos();

    void execute();

    TopoDS_Shape Input;
    Base::Vector3d Direction;

    TopoDS_Shape V;   // visible hard
    TopoDS_Shape V1;  // visible smooth
    TopoDS_Shape VN;  // visible seam
    TopoDS_Shape VO;  // visible outline
    TopoDS_Shape VI;  // visible iso
    TopoDS_Shape H;   // hidden hard
    TopoDS_Shape H1;  // hidden smooth
    TopoDS_Shape HN;  // hidden seam
    TopoDS_Shape HO;  // hidden outline
    TopoDS_Shape HI;  // hidden iso
};

}  // namespace Part
