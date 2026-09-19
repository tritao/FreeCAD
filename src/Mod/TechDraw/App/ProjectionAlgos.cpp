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
# include <BRepTools_WireExplorer.hxx>
# include <HLRAlgo_Projector.hxx>
# include <HLRBRep_Algo.hxx>
# include <HLRBRep_HLRToShape.hxx>
# include <gp_Ax2.hxx>
# include <gp_Dir.hxx>
# include <gp_Pnt.hxx>
# include <TopExp_Explorer.hxx>
# include <TopoDS.hxx>
# include <TopoDS_Shape.hxx>
# include <TopoDS_Wire.hxx>


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

struct LinearPath {
    std::vector<ProjectedPoint> points;
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

    std::vector<LinearPath> paths;
    auto appendEdge = [&](const TopoDS_Edge &edge, LinearPath &path) {
        BRepAdaptor_Curve curve(edge);
        if (curve.GetType() != GeomAbs_Line) {
            // The caller can fall back to the generic HLR exporter for
            // curves. Never silently approximate them as straight edges.
            return false;
        }

        const ProjectedPoint start = projectPoint(
            curve.Value(curve.FirstParameter()), xAxis, yAxis);
        const ProjectedPoint end = projectPoint(
            curve.Value(curve.LastParameter()), xAxis, yAxis);
        if (samePoint(start, end)) {
            return true;
        }
        if (path.points.empty()) {
            path.points = {start, end};
        }
        else if (samePoint(path.points.back(), start)) {
            path.points.push_back(end);
        }
        else if (samePoint(path.points.back(), end)) {
            path.points.push_back(start);
        }
        else {
            return false;
        }
        return true;
    };

    std::vector<TopoDS_Wire> wires;
    if (shape.ShapeType() == TopAbs_WIRE) {
        wires.push_back(TopoDS::Wire(shape));
    }
    else {
        for (TopExp_Explorer wireExplorer(shape, TopAbs_WIRE);
             wireExplorer.More(); wireExplorer.Next()) {
            wires.push_back(TopoDS::Wire(wireExplorer.Current()));
        }
    }

    for (const TopoDS_Wire &wire : wires) {
        LinearPath path;
        for (BRepTools_WireExplorer edgeExplorer(wire);
             edgeExplorer.More(); edgeExplorer.Next()) {
            if (!appendEdge(TopoDS::Edge(edgeExplorer.Current()), path)) {
                return {};
            }
        }
        if (path.points.size() >= 2) {
            paths.push_back(std::move(path));
        }
    }

    // A compound made only from loose edges has no wires to preserve. Keep
    // those edges as open paths so the endpoint join below can still connect
    // semantic line fragments from separate representations.
    if (wires.empty()) {
        for (TopExp_Explorer edges(shape, TopAbs_EDGE); edges.More(); edges.Next()) {
            LinearPath path;
            if (!appendEdge(TopoDS::Edge(edges.Current()), path)) {
                return {};
            }
            if (path.points.size() >= 2) {
                paths.push_back(std::move(path));
            }
        }
    }
    if (paths.empty()) {
        return {};
    }

    auto isClosed = [](const LinearPath &path) {
        return path.points.size() > 2
            && samePoint(path.points.front(), path.points.back());
    };

    auto samePath = [](const LinearPath &first, const LinearPath &second) {
        if (first.points.size() != second.points.size()) {
            return false;
        }
        bool forward = true;
        bool reverse = true;
        for (std::size_t point = 0; point < first.points.size(); ++point) {
            forward = forward
                && samePoint(first.points[point], second.points[point]);
            reverse = reverse
                && samePoint(first.points[point],
                             second.points[second.points.size() - point - 1]);
        }
        return forward || reverse;
    };

    // Multiple semantic sources can expose the same projected boundary. A
    // duplicate path would otherwise make that edge heavier than its style.
    for (std::size_t first = 0; first < paths.size(); ++first) {
        for (std::size_t second = first + 1; second < paths.size();) {
            if (samePath(paths[first], paths[second])) {
                paths.erase(paths.begin() + second);
            }
            else {
                ++second;
            }
        }
    }

    // Only join open paths at an endpoint with exactly two incident open
    // paths. Closed face boundaries remain independent, preventing branches
    // and overlapping wall faces from becoming self-intersecting SVG paths.
    std::vector<ProjectedPoint> joinPoints;
    std::vector<int> joinCounts;
    for (const auto &path : paths) {
        if (isClosed(path)) {
            continue;
        }
        for (const auto &point : {path.points.front(), path.points.back()}) {
            std::size_t index = 0;
            while (index < joinPoints.size() && !samePoint(joinPoints[index], point)) {
                ++index;
            }
            if (index == joinPoints.size()) {
                joinPoints.push_back(point);
                joinCounts.push_back(0);
            }
            ++joinCounts[index];
        }
    }
    auto endpointDegree = [&](const ProjectedPoint &point) {
        for (std::size_t index = 0; index < joinPoints.size(); ++index) {
            if (samePoint(joinPoints[index], point)) {
                return joinCounts[index];
            }
        }
        return 0;
    };
    auto joinAt = [](const LinearPath &first, const LinearPath &second) {
        LinearPath joined = first;
        if (samePoint(first.points.back(), second.points.front())) {
            joined.points.insert(joined.points.end(),
                                 second.points.begin() + 1, second.points.end());
        }
        else if (samePoint(first.points.back(), second.points.back())) {
            joined.points.insert(joined.points.end(),
                                 second.points.rbegin() + 1, second.points.rend());
        }
        else if (samePoint(first.points.front(), second.points.back())) {
            joined.points.insert(joined.points.begin(),
                                 second.points.begin(), second.points.end() - 1);
        }
        else if (samePoint(first.points.front(), second.points.front())) {
            joined.points.insert(joined.points.begin(),
                                 second.points.rbegin(), second.points.rend() - 1);
        }
        else {
            return first;
        }
        return joined;
    };

    bool changed = true;
    while (changed) {
        changed = false;
        for (std::size_t first = 0; first < paths.size() && !changed; ++first) {
            if (isClosed(paths[first])) {
                continue;
            }
            for (std::size_t second = first + 1; second < paths.size(); ++second) {
                if (isClosed(paths[second])) {
                    continue;
                }
                const bool joinsAtDegreeTwoEndpoint =
                    (samePoint(paths[first].points.front(), paths[second].points.front())
                     && endpointDegree(paths[first].points.front()) == 2
                     && endpointDegree(paths[second].points.front()) == 2)
                    || (samePoint(paths[first].points.front(), paths[second].points.back())
                        && endpointDegree(paths[first].points.front()) == 2
                        && endpointDegree(paths[second].points.back()) == 2)
                    || (samePoint(paths[first].points.back(), paths[second].points.front())
                        && endpointDegree(paths[first].points.back()) == 2
                        && endpointDegree(paths[second].points.front()) == 2)
                    || (samePoint(paths[first].points.back(), paths[second].points.back())
                        && endpointDegree(paths[first].points.back()) == 2
                        && endpointDegree(paths[second].points.back()) == 2);
                if (!joinsAtDegreeTwoEndpoint) {
                    continue;
                }
                paths[first] = joinAt(paths[first], paths[second]);
                paths.erase(paths.begin() + second);
                changed = true;
                break;
            }
        }
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
    for (const auto &path : paths) {
        if (path.points.size() < 2) {
            continue;
        }
        const bool closed = isClosed(path);
        const std::size_t pointCount = closed ? path.points.size() - 1 : path.points.size();
        result << "<path d=\"M " << path.points.front().x << " " << path.points.front().y;
        for (std::size_t point = 1; point < pointCount; ++point) {
            result << " L " << path.points[point].x << " " << path.points[point].y;
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
