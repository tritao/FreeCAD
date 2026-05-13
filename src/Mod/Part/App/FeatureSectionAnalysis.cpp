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

#include <App/ClippingPlane.h>
#include <App/GeoFeature.h>
#include <Base/Placement.h>
#include <Base/Rotation.h>
#include <BRep_Builder.hxx>
#include <Mod/Part/App/CrossSection.h>
#include <Mod/Part/App/FCBRepAlgoAPI_Section.h>
#include <Standard_Failure.hxx>
#include <TopAbs_ShapeEnum.hxx>
#include <TopoDS_Compound.hxx>
#include <gp_Dir.hxx>
#include <gp_Pln.hxx>
#include <gp_Pnt.hxx>

#include "FeatureSectionAnalysis.h"
#include "TopoShapeOpCode.h"

using namespace Part;

PROPERTY_SOURCE(Part::SectionAnalysis, Part::Feature)

namespace
{

constexpr long EdgeResultMode = 0;
constexpr long FaceResultMode = 1;
constexpr long BothResultMode = 2;

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
        (static_cast<long>(EdgeResultMode)),
        "SectionAnalysis",
        App::Prop_None,
        "Type of section result to generate"
    );
    ResultMode.setEnums(ResultModeEnums);
}

short SectionAnalysis::mustExecute() const
{
    if (Sources.isTouched() || ClippingPlane.isTouched() || ResultMode.isTouched()) {
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

        std::vector<TopoShape> sectionResults;
        sectionResults.reserve(sourceObjects.size() * (resultMode == BothResultMode ? 2 : 1));
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

            if (resultMode == EdgeResultMode || resultMode == BothResultMode) {
                TopoShape edges = makeSectionEdges(sourceShape, planeData.plane);
                if (!edges.isNull()) {
                    sectionResults.push_back(edges);
                }
            }

            if (resultMode == FaceResultMode || resultMode == BothResultMode) {
                TopoShape faces = makeSectionFaces(sourceShape, planeData, static_cast<int>(i + 1));
                if (!faces.isNull()) {
                    sectionResults.push_back(faces);
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
