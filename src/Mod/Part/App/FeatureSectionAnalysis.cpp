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
#include <Mod/Part/App/FCBRepAlgoAPI_Section.h>
#include <Standard_Failure.hxx>
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

std::pair<gp_Pnt, gp_Dir> resolveSectionPlane(const App::ClippingPlane& plane)
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
    return {
        gp_Pnt(origin.x, origin.y, origin.z),
        gp_Dir(normal.x, normal.y, normal.z),
    };
}

TopoDS_Compound makeEmptyCompound()
{
    BRep_Builder builder;
    TopoDS_Compound compound;
    builder.MakeCompound(compound);
    return compound;
}

}  // namespace

const char* SectionAnalysis::ResultModeEnums[] = {"Edges", nullptr};

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

        if (ResultMode.getValue() != EdgeResultMode) {
            return new App::DocumentObjectExecReturn("Unsupported section analysis result mode");
        }

        const auto [planeOrigin, planeNormal] = resolveSectionPlane(*planeObject);
        const gp_Pln occPlane(planeOrigin, planeNormal);

        std::vector<TopoShape> sectionResults;
        sectionResults.reserve(sourceObjects.size());
        for (auto* sourceObject : sourceObjects) {
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

            std::unique_ptr<FCBRepAlgoAPI_Section> mkSection(
                new FCBRepAlgoAPI_Section(sourceShape.getShape(), occPlane)
            );
            mkSection->setAutoFuzzy();
            mkSection->Build();
            if (!mkSection->IsDone()) {
                return new App::DocumentObjectExecReturn("Section operation failed");
            }

            const TopoDS_Shape resultShape = mkSection->Shape();
            if (resultShape.IsNull()) {
                continue;
            }

            TopoShape result(0);
            result.makeElementShape(*mkSection, sourceShape, Part::OpCodes::Section);
            if (!result.isNull()) {
                sectionResults.push_back(result);
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
