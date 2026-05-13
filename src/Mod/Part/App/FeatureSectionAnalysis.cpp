// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileNotice: Part of the FreeCAD project.
/******************************************************************************
 *                                                                            *
 *   © 2026 FreeCAD contributors                                              *
 *                                                                            *
 *   FreeCAD is free software: you can redistribute it and/or modify          *
 *   it under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1            *
 *   of the License, or (at your option) any later version.                   *
 *                                                                            *
 *   FreeCAD is distributed in the hope that it will be useful,               *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty              *
 *   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                  *
 *   See the GNU Lesser General Public License for more details.              *
 *                                                                            *
 *   You should have received a copy of the GNU Lesser General Public         *
 *   License along with FreeCAD. If not, see https://www.gnu.org/licenses     *
 *                                                                            *
 ******************************************************************************/

#include "PreCompiled.h"

#include <memory>
#include <numbers>
#include <vector>

#include <App/ClippingPlane.h>
#include <App/GeoFeature.h>
#include <Base/Placement.h>
#include <Base/Rotation.h>
#include <Base/Tools.h>
#include <Base/Unit.h>
#include <BRep_Builder.hxx>
#include <BRep_Tool.hxx>
#include <Mod/Part/App/CrossSection.h>
#include <Mod/Part/App/FCBRepAlgoAPI_Section.h>
#include <Standard_Failure.hxx>
#include <TopAbs_ShapeEnum.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS_Compound.hxx>
#include <TopoDS_Vertex.hxx>
#include <gp_Dir.hxx>
#include <gp_Ax1.hxx>
#include <gp_Pln.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>

#include "FeatureSectionAnalysis.h"
#include "TopoShapeOpCode.h"

using namespace Part;

PROPERTY_SOURCE(Part::SectionAnalysis, Part::Feature)

namespace
{

constexpr long EdgeResultMode = 0;
constexpr long FaceResultMode = 1;
constexpr long BothResultMode = 2;
constexpr int MaxHatchPlanes = 512;

struct SectionPlaneData
{
    gp_Pnt origin;
    gp_Dir normal;
    gp_Pln plane;
    double a;
    double b;
    double c;
    double d;
};

struct HatchFrame
{
    gp_Dir lineDirection;
    gp_Dir offsetDirection;
};

SectionPlaneData resolveSectionPlane(const App::ClippingPlane& plane)
{
    Base::Placement placement = App::GeoFeature::getGlobalPlacement(&plane);
    if (plane.Reverse.getValue()) {
        placement.setRotation(
            placement.getRotation()
            * Base::Rotation(Base::Vector3d(1.0, 0.0, 0.0), std::numbers::pi_v<double>)
        );
    }

    const Base::Vector3d origin = placement.getPosition();
    const Base::Vector3d normal = placement.getRotation().multVec(Base::Vector3d(0.0, 0.0, -1.0));
    const double d = (origin * normal);
    return {
        gp_Pnt(origin.x, origin.y, origin.z),
        gp_Dir(normal.x, normal.y, normal.z),
        gp_Pln(gp_Pnt(origin.x, origin.y, origin.z), gp_Dir(normal.x, normal.y, normal.z)),
        normal.x,
        normal.y,
        normal.z,
        d,
    };
}

HatchFrame resolveHatchFrame(const SectionPlaneData& planeData, double angleDegrees)
{
    gp_Dir reference(0.0, 0.0, 1.0);
    if (planeData.normal.IsParallel(reference, Precision::Angular())) {
        reference = gp_Dir(1.0, 0.0, 0.0);
    }

    gp_Vec u = gp_Vec(reference) ^ gp_Vec(planeData.normal);
    u.Normalize();
    gp_Vec v = gp_Vec(planeData.normal) ^ u;
    v.Normalize();

    const double angleRadians = Base::toRadians<double>(angleDegrees);
    gp_Vec lineDirection = std::cos(angleRadians) * u + std::sin(angleRadians) * v;
    if (lineDirection.Magnitude() <= Precision::Confusion()) {
        lineDirection = u;
    }
    lineDirection.Normalize();

    gp_Vec offsetDirection = gp_Vec(planeData.normal) ^ lineDirection;
    offsetDirection.Normalize();

    return {gp_Dir(lineDirection), gp_Dir(offsetDirection)};
}

bool getProjectedRange(
    const TopoShape& shape,
    const gp_Pnt& origin,
    const gp_Dir& direction,
    double& minimum,
    double& maximum
)
{
    bool found = false;
    minimum = 0.0;
    maximum = 0.0;

    for (auto face : shape.getSubTopoShapes(TopAbs_FACE)) {
        for (TopExp_Explorer explorer(face.getShape(), TopAbs_VERTEX); explorer.More();
             explorer.Next()) {
            const gp_Pnt point = BRep_Tool::Pnt(TopoDS::Vertex(explorer.Current()));
            const double projection = gp_Vec(origin, point).Dot(gp_Vec(direction));
            if (!found) {
                minimum = projection;
                maximum = projection;
                found = true;
            }
            else {
                minimum = std::min(minimum, projection);
                maximum = std::max(maximum, projection);
            }
        }
    }

    return found;
}

TopoDS_Compound makeEmptyCompound()
{
    BRep_Builder builder;
    TopoDS_Compound compound;
    builder.MakeCompound(compound);
    return compound;
}

TopoShape makeSectionEdges(const TopoShape& sourceShape, const gp_Pln& plane)
{
    std::unique_ptr<FCBRepAlgoAPI_Section> mkSection(
        new FCBRepAlgoAPI_Section(sourceShape.getShape(), plane)
    );
    mkSection->setAutoFuzzy();
    mkSection->Build();
    if (!mkSection->IsDone()) {
        FC_THROWM(Base::CADKernelError, "Section operation failed");
    }

    if (mkSection->Shape().IsNull()) {
        return TopoShape();
    }

    TopoShape result(0);
    result.makeElementShape(*mkSection, sourceShape, Part::OpCodes::Section);
    return result;
}

TopoShape makeSectionFaces(const TopoShape& sourceShape, const SectionPlaneData& planeData, int index)
{
    TopoCrossSection
        crossSection(planeData.a, planeData.b, planeData.c, sourceShape, Part::OpCodes::Section);
    TopoShape wires = crossSection.slice(index, planeData.d);
    if (wires.isNull() || wires.countSubShapes(TopAbs_WIRE) == 0) {
        return TopoShape();
    }

    TopoShape result(0);
    result.makeElementFace(wires, Part::OpCodes::Section, nullptr, &planeData.plane);
    return result;
}

std::vector<TopoShape> makeSectionHatchEdges(
    const TopoShape& faceShape,
    const SectionPlaneData& planeData,
    double spacing,
    double angleDegrees
)
{
    std::vector<TopoShape> hatchEdges;
    if (faceShape.isNull() || spacing <= Precision::Confusion()) {
        return hatchEdges;
    }

    double minimum = 0.0;
    double maximum = 0.0;
    const HatchFrame hatchFrame = resolveHatchFrame(planeData, angleDegrees);
    if (!getProjectedRange(faceShape, planeData.origin, hatchFrame.offsetDirection, minimum, maximum)) {
        return hatchEdges;
    }

    const double range = std::max(0.0, maximum - minimum);
    const double effectiveSpacing = range > 0.0
        ? std::max(spacing, range / static_cast<double>(MaxHatchPlanes))
        : spacing;
    const double start = minimum + (effectiveSpacing * 0.5);

    for (double offset = start; offset < (maximum - Precision::Confusion());
         offset += effectiveSpacing) {
        gp_Pnt point = planeData.origin.Translated(gp_Vec(hatchFrame.offsetDirection) * offset);
        gp_Pln hatchPlane(point, gp_Dir(gp_Vec(hatchFrame.lineDirection) ^ gp_Vec(planeData.normal)));
        FCBRepAlgoAPI_Section section(faceShape.getShape(), hatchPlane);
        section.setAutoFuzzy();
        section.Build();
        if (!section.IsDone() || section.Shape().IsNull()) {
            continue;
        }

        TopoShape hatch(0);
        hatch.setShape(section.Shape());
        for (auto edge : hatch.getSubTopoShapes(TopAbs_EDGE)) {
            if (!edge.isNull()) {
                hatchEdges.push_back(edge);
            }
        }
    }

    return hatchEdges;
}

}  // namespace

const char* SectionAnalysis::ResultModeEnums[] = {"Edges", "Faces", "Both", nullptr};

SectionAnalysis::SectionAnalysis()
{
    ADD_PROPERTY(Sources, (nullptr));
    Sources.setSize(0);
    ADD_PROPERTY_TYPE(
        ClippingPlane,
        (nullptr),
        "SectionAnalysis",
        App::Prop_None,
        "Clipping plane used to compute the section result"
    );
    ADD_PROPERTY_TYPE(
        ResultMode,
        (static_cast<long>(BothResultMode)),
        "SectionAnalysis",
        App::Prop_None,
        "Type of section result to generate"
    );
    ResultMode.setEnums(ResultModeEnums);
    ADD_PROPERTY_TYPE(
        ShowHatching,
        (false),
        "SectionAnalysis",
        App::Prop_None,
        "Generate hatch geometry on section faces"
    );
    ADD_PROPERTY_TYPE(
        HatchSpacing,
        (2.0),
        "SectionAnalysis",
        App::Prop_None,
        "Spacing between generated hatch lines"
    );
    HatchSpacing.setUnit(Base::Unit::Length);
    ADD_PROPERTY_TYPE(
        HatchAngle,
        (45.0),
        "SectionAnalysis",
        App::Prop_None,
        "Angle used for generated hatch lines"
    );
}

short SectionAnalysis::mustExecute() const
{
    if (Sources.isTouched() || ClippingPlane.isTouched() || ResultMode.isTouched()
        || ShowHatching.isTouched() || HatchSpacing.isTouched() || HatchAngle.isTouched()) {
        return 1;
    }
    return Part::Feature::mustExecute();
}

App::DocumentObjectExecReturn* SectionAnalysis::execute()
{
    try {
        auto* planeObject = dynamic_cast<App::ClippingPlane*>(ClippingPlane.getValue());
        if (!planeObject) {
            return new App::DocumentObjectExecReturn("No clipping plane linked");
        }

        const auto sourceObjects = Sources.getValues();
        if (sourceObjects.empty()) {
            return new App::DocumentObjectExecReturn("No source objects linked");
        }

        const long resultMode = ResultMode.getValue();
        if (resultMode != EdgeResultMode && resultMode != FaceResultMode
            && resultMode != BothResultMode) {
            return new App::DocumentObjectExecReturn("Unsupported section analysis result mode");
        }

        const SectionPlaneData planeData = resolveSectionPlane(*planeObject);
        const bool includeFaces = resultMode == FaceResultMode || resultMode == BothResultMode;
        const bool includeEdges = resultMode == EdgeResultMode || resultMode == BothResultMode;
        const bool includeHatching = includeFaces && ShowHatching.getValue();

        std::vector<TopoShape> sectionResults;
        sectionResults.reserve(sourceObjects.size() * (includeHatching ? 3 : 2));
        for (std::size_t i = 0; i < sourceObjects.size(); ++i) {
            auto* sourceObject = sourceObjects[i];
            if (!sourceObject) {
                return new App::DocumentObjectExecReturn("Linked source object is null");
            }

            TopoShape sourceShape = Feature::getTopoShape(
                sourceObject,
                ShapeOption::ResolveLink | ShapeOption::Transform
            );
            if (sourceShape.isNull()) {
                return new App::DocumentObjectExecReturn("Linked source shape is null");
            }

            if (includeEdges) {
                TopoShape edges = makeSectionEdges(sourceShape, planeData.plane);
                if (!edges.isNull()) {
                    sectionResults.push_back(edges);
                }
            }

            if (includeFaces) {
                TopoShape faces = makeSectionFaces(sourceShape, planeData, static_cast<int>(i + 1));
                if (!faces.isNull()) {
                    sectionResults.push_back(faces);
                    if (includeHatching) {
                        std::vector<TopoShape> hatchEdges = makeSectionHatchEdges(
                            faces,
                            planeData,
                            HatchSpacing.getValue(),
                            HatchAngle.getValue()
                        );
                        sectionResults
                            .insert(sectionResults.end(), hatchEdges.begin(), hatchEdges.end());
                    }
                }
            }
        }

        if (sectionResults.empty()) {
            Shape.setValue(makeEmptyCompound());
        }
        else {
            Shape.setValue(TopoShape().makeElementCompound(sectionResults));
            copyMaterial(sourceObjects.front());
        }

        return Part::Feature::execute();
    }
    catch (const Base::Exception& e) {
        return new App::DocumentObjectExecReturn(e.what());
    }
    catch (Standard_Failure& e) {
        return new App::DocumentObjectExecReturn(e.GetMessageString());
    }
    catch (...) {
        return new App::DocumentObjectExecReturn(
            "A fatal error occurred while computing section analysis"
        );
    }
}
