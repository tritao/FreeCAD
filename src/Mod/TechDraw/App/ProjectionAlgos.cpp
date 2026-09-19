// SPDX-License-Identifier: LGPL-2.1-or-later

/***************************************************************************
 *   Copyright (c) 2002 Jürgen Riegel <juergen.riegel@web.de>              *
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
//this file originally part of TechDraw workbench
//migrated to TechDraw workbench 2022-01-26 by Wandererfan


# include <cmath>
# include <iomanip>
# include <sstream>
# include <utility>
# include <vector>
# include <BRepAdaptor_Curve.hxx>
# include <BRepLib.hxx>
# include <BRepMesh_IncrementalMesh.hxx>
# include <HLRAlgo_Projector.hxx>
# include <HLRBRep_Algo.hxx>
# include <HLRBRep_HLRToShape.hxx>
# include <gp_Ax2.hxx>
# include <gp_Dir.hxx>
# include <gp_Pnt.hxx>
# include <TopExp_Explorer.hxx>
# include <TopoDS.hxx>
# include <TopoDS_Shape.hxx>


#include "ProjectionAlgos.h"
#include "TechDrawExport.h"


using namespace TechDraw;
using namespace std;

//===========================================================================
// ProjectionAlgos
//===========================================================================

namespace TechDraw {
  //added by tanderson. aka blobfish.
  //projection algorithms build a 2d curve(pcurve) but no 3d curve.
  //this causes problems with meshing algorithms after save and load.
  const TopoDS_Shape& build3dCurves(const TopoDS_Shape &shape)
  {
    TopExp_Explorer it;
    for (it.Init(shape, TopAbs_EDGE); it.More(); it.Next())
      BRepLib::BuildCurve3d(TopoDS::Edge(it.Current()));
    return shape;
  }
}

ProjectionAlgos::ProjectionAlgos(const TopoDS_Shape &Input, const Base::Vector3d &Dir)
  : Input(Input), Direction(Dir)
{
    execute();
}

ProjectionAlgos::~ProjectionAlgos()
{
}

namespace {

struct ProjectedPoint {
    double x;
    double y;
};

struct LinearSegment {
    ProjectedPoint start;
    ProjectedPoint end;
};

bool samePoint(const ProjectedPoint &first, const ProjectedPoint &second)
{
    constexpr double tolerance = 1.0e-7;
    return std::abs(first.x - second.x) <= tolerance
        && std::abs(first.y - second.y) <= tolerance;
}

ProjectedPoint projectPoint(const gp_Pnt &point,
                            const gp_Dir &xAxis,
                            const gp_Dir &yAxis)
{
    return {
        point.X() * xAxis.X() + point.Y() * xAxis.Y() + point.Z() * xAxis.Z(),
        point.X() * yAxis.X() + point.Y() * yAxis.Y() + point.Z() * yAxis.Z(),
    };
}

} // namespace

std::string ProjectionAlgos::getSVGPath(const TopoDS_Shape &shape,
                                        const Base::Vector3d &direction,
                                        XmlAttributes style)
{
    gp_Ax2 projection(gp_Pnt(0, 0, 0),
                      gp_Dir(direction.x, direction.y, direction.z));
    const gp_Dir xAxis = projection.XDirection();
    const gp_Dir yAxis = projection.YDirection();

    std::vector<LinearSegment> segments;
    for (TopExp_Explorer edges(shape, TopAbs_EDGE); edges.More(); edges.Next()) {
        const TopoDS_Edge &edge = TopoDS::Edge(edges.Current());
        BRepAdaptor_Curve curve(edge);
        if (curve.GetType() != GeomAbs_Line) {
            // The caller can fall back to the generic HLR exporter for
            // curves. Never silently approximate them as straight edges.
            return {};
        }

        const gp_Pnt start = curve.Value(curve.FirstParameter());
        const gp_Pnt end = curve.Value(curve.LastParameter());
        LinearSegment segment{
            projectPoint(start, xAxis, yAxis),
            projectPoint(end, xAxis, yAxis),
        };
        if (!samePoint(segment.start, segment.end)) {
            segments.push_back(segment);
        }
    }
    if (segments.empty()) {
        return {};
    }

    std::vector<bool> used(segments.size(), false);
    std::vector<std::vector<ProjectedPoint>> chains;
    for (std::size_t first = 0; first < segments.size(); ++first) {
        if (used[first]) {
            continue;
        }

        std::vector<ProjectedPoint> chain{
            segments[first].start,
            segments[first].end,
        };
        used[first] = true;

        while (!samePoint(chain.front(), chain.back())) {
            bool extended = false;
            for (std::size_t candidate = 0; candidate < segments.size(); ++candidate) {
                if (used[candidate]) {
                    continue;
                }

                const LinearSegment &segment = segments[candidate];
                if (samePoint(chain.back(), segment.start)) {
                    chain.push_back(segment.end);
                }
                else if (samePoint(chain.back(), segment.end)) {
                    chain.push_back(segment.start);
                }
                else if (samePoint(chain.front(), segment.end)) {
                    chain.insert(chain.begin(), segment.start);
                }
                else if (samePoint(chain.front(), segment.start)) {
                    chain.insert(chain.begin(), segment.end);
                }
                else {
                    continue;
                }

                used[candidate] = true;
                extended = true;
                break;
            }
            if (!extended) {
                break;
            }
        }
        chains.push_back(std::move(chain));
    }

    style.insert({"stroke", "rgb(0, 0, 0)"});
    style.insert({"stroke-width", "1.0"});
    style.insert({"stroke-linecap", "butt"});
    style.insert({"stroke-linejoin", "miter"});
    style.insert({"fill", "none"});
    style.insert({"transform", "scale(1, -1)"});

    std::ostringstream result;
    result << "<g";
    for (const auto &attribute : style) {
        result << "   " << attribute.first << "=\""
               << attribute.second << "\"\n";
    }
    result << "  >\n";
    result << std::setprecision(15);
    for (const auto &chain : chains) {
        if (chain.size() < 2) {
            continue;
        }
        const bool closed = chain.size() > 2
            && samePoint(chain.front(), chain.back());
        const std::size_t pointCount = closed ? chain.size() - 1 : chain.size();
        result << "<path d=\"M " << chain.front().x << " " << chain.front().y;
        for (std::size_t point = 1; point < pointCount; ++point) {
            result << " L " << chain[point].x << " " << chain[point].y;
        }
        if (closed) {
            result << " Z";
        }
        result << "\" />\n";
    }
    result << "</g>\n";
    return result.str();
}


void ProjectionAlgos::execute()
{
    Handle( HLRBRep_Algo ) brep_hlr = new HLRBRep_Algo;
    brep_hlr->Add(Input);

    gp_Ax2 transform(gp_Pnt(0, 0, 0), gp_Dir(Direction.x, Direction.y, Direction.z));
    HLRAlgo_Projector projector( transform );
    brep_hlr->Projector(projector);
    brep_hlr->Update();
    brep_hlr->Hide();

    // extracting the result sets:
    HLRBRep_HLRToShape shapes( brep_hlr );

    V  = build3dCurves(shapes.VCompound       ());// hard edge visibly
    V1 = build3dCurves(shapes.Rg1LineVCompound());// Smoth edges visibly
    VN = build3dCurves(shapes.RgNLineVCompound());// contour edges visibly
    VO = build3dCurves(shapes.OutLineVCompound());// contours apparents visibly
    VI = build3dCurves(shapes.IsoLineVCompound());// isoparamtriques   visibly
    H  = build3dCurves(shapes.HCompound       ());// hard edge       invisibly
    H1 = build3dCurves(shapes.Rg1LineHCompound());// Smoth edges  invisibly
    HN = build3dCurves(shapes.RgNLineHCompound());// contour edges invisibly
    HO = build3dCurves(shapes.OutLineHCompound());// contours apparents invisibly
    HI = build3dCurves(shapes.IsoLineHCompound());// isoparamtriques   invisibly
}

string ProjectionAlgos::getSVG(ExtractionType type,
                               double tolerance,
                               XmlAttributes V_style,
                               XmlAttributes V0_style,
                               XmlAttributes V1_style,
                               XmlAttributes H_style,
                               XmlAttributes H0_style,
                               XmlAttributes H1_style)
{
    stringstream result;
    SVGOutput output;

    if (!H.IsNull() && (type & WithHidden)) {
        H_style.insert({"stroke", "rgb(0, 0, 0)"});
        H_style.insert({"stroke-width", "0.15"});
        H_style.insert({"stroke-linecap", "butt"});
        H_style.insert({"stroke-linejoin", "miter"});
        H_style.insert({"stroke-dasharray", "0.2, 0.1)"});
        H_style.insert({"fill", "none"});
        H_style.insert({"transform", "scale(1, -1)"});
        BRepMesh_IncrementalMesh(H, tolerance);
        result  << "<g";
        for (const auto& attribute : H_style)
            result << "   " << attribute.first << "=\""
                   << attribute.second << "\"\n";
        result << "  >" << endl
               << output.exportEdges(H)
               << "</g>" << endl;
    }
    if (!HO.IsNull() && (type & WithHidden)) {
        H0_style.insert({"stroke", "rgb(0, 0, 0)"});
        H0_style.insert({"stroke-width", "0.15"});
        H0_style.insert({"stroke-linecap", "butt"});
        H0_style.insert({"stroke-linejoin", "miter"});
        H0_style.insert({"stroke-dasharray", "0.02, 0.1)"});
        H0_style.insert({"fill", "none"});
        H0_style.insert({"transform", "scale(1, -1)"});
        BRepMesh_IncrementalMesh(HO, tolerance);
        result  << "<g";
        for (const auto& attribute : H0_style)
            result << "   " << attribute.first << "=\""
                   << attribute.second << "\"\n";
        result << "  >" << endl
               << output.exportEdges(HO)
               << "</g>" << endl;
    }
    if (!VO.IsNull()) {
        V0_style.insert({"stroke", "rgb(0, 0, 0)"});
        V0_style.insert({"stroke-width", "1.0"});
        V0_style.insert({"stroke-linecap", "butt"});
        V0_style.insert({"stroke-linejoin", "miter"});
        V0_style.insert({"fill", "none"});
        V0_style.insert({"transform", "scale(1, -1)"});
        BRepMesh_IncrementalMesh(VO, tolerance);
        result  << "<g";
        for (const auto& attribute : V0_style)
            result << "   " << attribute.first << "=\""
                   << attribute.second << "\"\n";
        result << "  >" << endl
               << output.exportEdges(VO)
               << "</g>" << endl;
    }
    if (!V.IsNull()) {
        V_style.insert({"stroke", "rgb(0, 0, 0)"});
        V_style.insert({"stroke-width", "1.0"});
        V_style.insert({"stroke-linecap", "butt"});
        V_style.insert({"stroke-linejoin", "miter"});
        V_style.insert({"fill", "none"});
        V_style.insert({"transform", "scale(1, -1)"});
        BRepMesh_IncrementalMesh(V, tolerance);
        result  << "<g";
        for (const auto& attribute : V_style)
            result << "   " << attribute.first << "=\""
                   << attribute.second << "\"\n";
        result << "  >" << endl
               << output.exportEdges(V)
               << "</g>" << endl;
    }
    if (!V1.IsNull() && (type & WithSmooth)) {
        V1_style.insert({"stroke", "rgb(0, 0, 0)"});
        V1_style.insert({"stroke-width", "1.0"});
        V1_style.insert({"stroke-linecap", "butt"});
        V1_style.insert({"stroke-linejoin", "miter"});
        V1_style.insert({"fill", "none"});
        V1_style.insert({"transform", "scale(1, -1)"});
        BRepMesh_IncrementalMesh(V1, tolerance);
        result  << "<g";
        for (const auto& attribute : V1_style)
            result << "   " << attribute.first << "=\""
                   << attribute.second << "\"\n";
        result << "  >" << endl
               << output.exportEdges(V1)
               << "</g>" << endl;
    }
    if (!H1.IsNull() && (type & WithSmooth) && (type & WithHidden)) {
        H1_style.insert({"stroke", "rgb(0, 0, 0)"});
        H1_style.insert({"stroke-width", "0.15"});
        H1_style.insert({"stroke-linecap", "butt"});
        H1_style.insert({"stroke-linejoin", "miter"});
        H1_style.insert({"stroke-dasharray", "0.09, 0.05)"});
        H1_style.insert({"fill", "none"});
        H1_style.insert({"transform", "scale(1, -1)"});
        BRepMesh_IncrementalMesh(H1, tolerance);
        result  << "<g";
        for (const auto& attribute : H1_style)
            result << "   " << attribute.first << "=\""
                   << attribute.second << "\"\n";
        result << "  >" << endl
               << output.exportEdges(H1)
               << "</g>" << endl;
    }
    return result.str();
}

/* dxf output section - Dan Falck 2011/09/25  */

string ProjectionAlgos::getDXF(ExtractionType type, double /*scale*/, double tolerance)
{
    stringstream result;
    DXFOutput output;

    if (!H.IsNull() && (type & WithHidden)) {
        //float width = 0.15f/scale;
        BRepMesh_IncrementalMesh(H, tolerance);
        result  << output.exportEdges(H);
    }
    if (!HO.IsNull() && (type & WithHidden)) {
        //float width = 0.15f/scale;
        BRepMesh_IncrementalMesh(HO, tolerance);
        result  << output.exportEdges(HO);
    }
    if (!VO.IsNull()) {
        //float width = 0.35f/scale;
        BRepMesh_IncrementalMesh(VO, tolerance);
        result  << output.exportEdges(VO);
    }
    if (!V.IsNull()) {
        //float width = 0.35f/scale;
        BRepMesh_IncrementalMesh(V, tolerance);
        result  << output.exportEdges(V);
    }
    if (!V1.IsNull() && (type & WithSmooth)) {
        //float width = 0.35f/scale;
        BRepMesh_IncrementalMesh(V1, tolerance);
        result  << output.exportEdges(V1);
    }
    if (!H1.IsNull() && (type & WithSmooth) && (type & WithHidden)) {
        //float width = 0.15f/scale;
        BRepMesh_IncrementalMesh(H1, tolerance);
        result  << output.exportEdges(H1);
    }

    return result.str();
}
