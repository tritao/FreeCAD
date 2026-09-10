# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2025 Furgo                                              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

# Unit tests for the ArchComponent module

import Arch
import ArchComponent
import BimContextualRendering
from bimplan import contextual_rendering as plan_contextual_rendering
from bimplan import contextual_editing as plan_contextual_editing
from bimplan import representation_context as plan_representation_context
import Draft
import Part
import FreeCAD as App
from bimtests import TestArchBase
from draftutils.messages import _msg

from math import pi, cos, sin, radians
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestArchComponent(TestArchBase.TestArchBase):

    def test_bim_edit_operation_reports_constraints_and_ranges(self):
        obj = self.document.addObject("Part::Feature", "ConstrainedEdit")
        obj.addProperty("App::PropertyLength", "Height")
        obj.Height = 1000
        operation = ArchComponent.BIMEditOperation(
            "Height",
            "Edit Height",
            lambda source: source.Height.Value,
            lambda source, value: setattr(source, "Height", value),
            minimum=100.0,
            maximum=5000.0,
        )

        self.assertTrue(operation.validate(obj, 1000).allowed)
        too_small = operation.validate(obj, 50)
        self.assertFalse(too_small.allowed)
        self.assertEqual(too_small.minimum, 100.0)
        self.assertIn("at least", too_small.reason)
        with self.assertRaisesRegex(ValueError, "at least"):
            operation.apply(obj, 50)

    def test_contextual_handle_projects_drag_and_commits_transaction(self):
        """A Section handle should ignore motion normal to its active plane."""

        obj = self.document.addObject("Part::Feature", "SemanticHeight")
        self.document.UndoMode = 1
        obj.addProperty("App::PropertyLength", "Height")
        obj.Height = 3000.0
        frame = App.Placement(
            App.Vector(250, 100, 50),
            App.Rotation(App.Vector(0, 1, 0), 90),
        )
        context = ArchComponent.RepresentationContext(
            purpose=ArchComponent.RepresentationPurpose.SECTION,
            reference_frame=frame,
            target_offset=0.0,
        )
        direction = ArchComponent.representation_vertical_direction(context)
        point = ArchComponent.project_to_representation_plane(App.Vector(0, 0, 3000), context)
        operation = ArchComponent.BIMEditOperation(
            "WallHeight",
            "Edit Wall Height",
            lambda source: source.Height.Value,
            lambda source, value: setattr(source, "Height", value),
            property_name="Height",
        )
        handle = ArchComponent.BIMEditHandle(
            obj, "WallHeight", point, direction, operation, subelement="Height"
        )
        editor = plan_contextual_editing.BIMContextualHandleEditor(context)

        editor.begin(handle)
        normal = frame.Rotation.multVec(App.Vector(0, 0, 1))
        preview = editor.preview(point + direction * 500 + normal * 1700)
        self.assertAlmostEqual(preview.value, 3500.0)
        editor.commit(point + direction * 500 + normal * 1700)

        self.assertAlmostEqual(obj.Height.Value, 3500.0)
        self.document.undo()
        self.assertAlmostEqual(obj.Height.Value, 3000.0)
        self.document.redo()
        self.assertAlmostEqual(obj.Height.Value, 3500.0)

    def test_plan_contextual_rendering_refreshes_dependencies_and_closes(self):
        """Plan Edit should incrementally render walls and their hosted openings."""

        wall = object()
        opening = object()
        wall_representation = SimpleNamespace(source=wall)
        opening_representation = SimpleNamespace(source=opening)
        renderer = MagicMock()
        get_contextual_representation = MagicMock(
            side_effect=lambda obj: wall_representation if obj is wall else opening_representation
        )
        session = SimpleNamespace(
            view=object(),
            doc=SimpleNamespace(Objects=(wall, opening)),
            active_storey=None,
            viewport=SimpleNamespace(request_view_redraw=MagicMock()),
            visibility=SimpleNamespace(get_plan_semantic_object=lambda obj: obj),
            selection=SimpleNamespace(
                targets=SimpleNamespace(is_plan_selectable_wall=lambda obj: obj is wall)
            ),
            openings=SimpleNamespace(
                is_hosted_opening_object=lambda obj: obj is opening,
                get_plan_opening_instances=lambda: (opening,),
                get_wall_hosted_openings=lambda obj: (opening,) if obj is wall else (),
                is_opening_visual_dependency=lambda candidate, obj: (
                    candidate is opening and obj is wall
                ),
            ),
            overlays=SimpleNamespace(
                geometry=SimpleNamespace(
                    get_wall_representation=lambda obj: wall_representation,
                    get_opening_representation=lambda obj: opening_representation,
                    get_contextual_representation=get_contextual_representation,
                )
            ),
            representation_context=SimpleNamespace(includes_object=lambda _obj: True),
        )
        api = plan_contextual_rendering.PlanContextualRenderingAPI(session)

        with patch(
            "bimplan.contextual_rendering."
            "BimContextualRendering.ContextualRepresentationRenderer",
            return_value=renderer,
        ):
            api.start()
            renderer.reset_mock()
            api.refresh_object(wall)
            api.close()

        renderer.set_representation.assert_any_call(wall_representation)
        renderer.set_representation.assert_any_call(opening_representation)
        get_contextual_representation.assert_any_call(wall)
        get_contextual_representation.assert_any_call(opening)
        renderer.close.assert_called_once_with()

    def test_section_plane_provides_arbitrary_representation_context(self):
        """SectionPlane should configure the same BIM representation pipeline as plans."""

        section = Arch.makeSectionPlane(name="ContextSection")
        section.Placement = App.Placement(
            App.Vector(25, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90)
        )
        section.Depth = 750

        context = section.Proxy.getRepresentationContext(section)

        self.assertEqual(context.purpose, ArchComponent.RepresentationPurpose.SECTION)
        self.assertEqual(context.reference_frame, section.Placement)
        self.assertEqual(context.cut_offset, 0.0)
        self.assertEqual(context.target_offset, 0.0)
        self.assertEqual(context.projection_range, 750.0)
        self.assertIs(context.source, section)

    def test_representation_context_accepts_saved_view_provider_protocol(self):
        """BIM Views should be able to provide profiles without Plan Edit knowing their type."""

        expected = ArchComponent.RepresentationContext(
            purpose=ArchComponent.RepresentationPurpose.ELEVATION,
            reference_frame=App.Placement(),
            profile="Architectural",
        )
        source = SimpleNamespace()
        source.Proxy = SimpleNamespace(getRepresentationContext=lambda obj: expected)

        context = plan_representation_context.context_from_source(source)

        self.assertIs(context, expected)

    def test_representation_context_transforms_and_projects_arbitrary_points(self):
        """Context-local editing math should not assume global XY or Z."""

        frame = App.Placement(App.Vector(10, 20, 30), App.Rotation(App.Vector(1, 0, 0), 90))
        context = ArchComponent.RepresentationContext(
            purpose=ArchComponent.RepresentationPurpose.SECTION,
            reference_frame=frame,
            target_offset=5.0,
        )
        api = plan_representation_context.PlanRepresentationContextAPI(SimpleNamespace())
        api.context = context
        local = App.Vector(4, 6, 12)

        global_point = api.to_global(local)
        roundtrip = api.to_local(global_point)
        projected = api.to_local(api.project_to_plane(global_point))

        self.assertLess(roundtrip.distanceToPoint(local), 1e-9)
        self.assertAlmostEqual(projected.x, local.x)
        self.assertAlmostEqual(projected.y, local.y)
        self.assertAlmostEqual(projected.z, 5.0)
        self.assertFalse(api.supports("wall_join"))
        self.assertTrue(api.supports("semantic_snap"))

    def test_contextual_renderer_keeps_same_object_viewer_local(self):
        """Two viewers should own independent representations of one BIM object."""

        class FakeView:
            def __init__(self, layer):
                self.scene = BimContextualRendering.coin.SoSeparator()
                self.layer = layer
                self.visibility_calls = []

            def pushViewContextLayer(self):
                return self.layer

            def removeViewContextLayer(self, layer):
                self.removed_layer = layer

            def setViewVisibility(self, layer, source, state):
                self.visibility_calls.append((layer, source, state))

            def getSceneGraph(self):
                return self.scene

        source = self.document.addObject("Part::Feature", "ContextualSource")
        plan = ArchComponent.BIMRepresentation(source, ArchComponent.PlanContext(1000, 0))
        line = (App.Vector(0, 0, 0), App.Vector(100, 0, 0))
        plan.add_geometry("projected_geometry", line, "Projection", "Projection1")
        section = ArchComponent.BIMRepresentation(source, object())
        face = Part.makePlane(100, 50)
        section.add_geometry("cut_geometry", face, "CutFace", "Face1")
        handle = section.add_edit_handle(
            ArchComponent.BIMEditHandle(
                source,
                ArchComponent.BIMEditOperation(
                    "Height",
                    "Edit Height",
                    lambda obj: obj.Height.Value,
                    lambda obj, value: setattr(obj, "Height", value),
                    property_name="Height",
                ),
                App.Vector(50, 50, 0),
                App.Vector(0, 1, 0),
                "Height",
            )
        )
        first_view = FakeView(11)
        second_view = FakeView(22)

        first = BimContextualRendering.ContextualRepresentationRenderer(first_view)
        second = BimContextualRendering.ContextualRepresentationRenderer(second_view)
        first_node = first.set_representation(plan)
        second_node = second.set_representation(section)

        self.assertIsNot(first.root, second.root)
        self.assertIsNot(first_node, second_node)
        self.assertIs(first.set_representation(plan), first_node)
        self.assertEqual(first_view.visibility_calls[-1], (11, source, "Hidden"))
        self.assertEqual(second_view.visibility_calls[-1], (22, source, "Hidden"))
        self.assertEqual(second.edit_handles_for(source), (handle,))
        self.assertTrue(second.preview_handle(handle, App.Vector(50, 75, 0)))
        self.assertTrue(second.set_handle_state(handle, "invalid"))
        first.close()
        self.assertEqual(first_view.removed_layer, 11)
        self.assertEqual(second_view.scene.getNumChildren(), 1)
        second.close()

    def test_query_representation_snap_preserves_semantic_identity(self):
        """Semantic snap queries should prefer vertices and retain their source mapping."""

        source = self.document.addObject("Part::Feature", "SnapSource")
        edge = Part.makeLine(App.Vector(0, 0, 0), App.Vector(100, 0, 0))
        vertex = edge.Vertexes[0]
        context = ArchComponent.PlanContext(cut_z=1000.0, target_z=0.0)
        representation = ArchComponent.BIMRepresentation(source=source, context=context)
        representation.add_geometry("snap_geometry", edge, "CutEdge", "Face1.Edge1")
        representation.add_geometry("snap_geometry", vertex, "CutVertex", "Face1.Vertex1")

        result = ArchComponent.query_representation_snap(
            [representation], App.Vector(0, 0, 500), 1.0, context=context
        )

        self.assertIsNotNone(result)
        self.assertIs(result.source, source)
        self.assertEqual(result.role, "CutVertex")
        self.assertEqual(result.subelement, "Face1.Vertex1")
        self.assertAlmostEqual(result.point.z, 0.0)

    def test_query_representation_pick_accepts_cut_face_interior(self):
        """A filled contextual cut face should remain pickable away from its boundary."""

        source = self.document.addObject("Part::Feature", "FacePickSource")
        face = Part.makePlane(100, 50)
        representation = ArchComponent.BIMRepresentation(source, object())
        representation.add_geometry("cut_geometry", face, "CutFace", "Face1")

        result = ArchComponent.query_representation_pick(
            (representation,),
            (50, 25),
            lambda point: (point.x, point.y),
            1.0,
        )

        self.assertIsNotNone(result)
        self.assertIs(result.source, source)
        self.assertEqual(result.subelement, "Face1")

    def test_query_representation_snap_uses_arbitrary_context_plane(self):
        """Snap distance should be measured after projecting onto the active frame."""

        source = self.document.addObject("Part::Feature", "SectionSnapSource")
        vertex = Part.Vertex(App.Vector(25, 10, 0))
        frame = App.Placement(App.Vector(), App.Rotation(App.Vector(0, 1, 0), 90))
        context = ArchComponent.RepresentationContext(
            purpose=ArchComponent.RepresentationPurpose.SECTION,
            reference_frame=frame,
            target_offset=25.0,
        )
        representation = ArchComponent.BIMRepresentation(source=source, context=context)
        representation.add_geometry("snap_geometry", vertex, "CutVertex", "Vertex1")

        result = ArchComponent.query_representation_snap(
            [representation], App.Vector(900, 10, 0), 0.1, context=context
        )

        self.assertIsNotNone(result)
        self.assertIs(result.source, source)
        self.assertEqual(result.subelement, "Vertex1")

    def test_query_representation_pick_preserves_mapping_and_input_priority(self):
        """Screen picks should resolve semantic subelements and break ties by input order."""

        wall = self.document.addObject("Part::Feature", "PickWall")
        opening = self.document.addObject("Part::Feature", "PickOpening")
        context = ArchComponent.PlanContext(cut_z=1000.0, target_z=0.0)
        wall_representation = ArchComponent.BIMRepresentation(wall, context)
        opening_representation = ArchComponent.BIMRepresentation(opening, context)
        wall_line = (App.Vector(0, 0, 0), App.Vector(100, 0, 0))
        opening_line = (App.Vector(40, 0, 0), App.Vector(60, 0, 0))
        wall_representation.add_geometry(
            "projected_geometry", wall_line, "WallProjection", "WallEdge1"
        )
        opening_representation.add_geometry(
            "projected_geometry", opening_line, "OpeningSymbol", "OpeningSymbol1"
        )

        result = ArchComponent.query_representation_pick(
            [opening_representation, wall_representation],
            (50, 0),
            lambda point: (point.x, point.y),
            2.0,
        )

        self.assertIsNotNone(result)
        self.assertIs(result.source, opening)
        self.assertEqual(result.role, "OpeningSymbol")
        self.assertEqual(result.subelement, "OpeningSymbol1")

    def testAdd(self):
        App.Console.PrintLog("Checking Arch Add...\n")
        l = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(2, 0, 0))
        w = Arch.makeWall(l, width=0.2, height=2)
        sb = Part.makeBox(1, 1, 1)
        b = App.ActiveDocument.addObject("Part::Feature", "Box")
        b.Shape = sb
        App.ActiveDocument.recompute()
        Arch.addComponents(b, w)
        App.ActiveDocument.recompute()
        r = w.Shape.Volume > 1.5
        self.assertTrue(r, "Arch Add failed")

    def testMakeProjectedHorizontalAreaFace(self):
        """Projected horizontal analysis face should preserve union semantics."""

        face_a = Part.makeFace(
            [
                Part.makePolygon(
                    [
                        App.Vector(0, 0, 0),
                        App.Vector(2, 0, 0),
                        App.Vector(2, 1, 0),
                        App.Vector(0, 1, 0),
                        App.Vector(0, 0, 0),
                    ]
                )
            ],
            "Part::FaceMakerCheese",
        )
        face_b = Part.makeFace(
            [
                Part.makePolygon(
                    [
                        App.Vector(1, 0, 0),
                        App.Vector(3, 0, 0),
                        App.Vector(3, 1, 0),
                        App.Vector(1, 1, 0),
                        App.Vector(1, 0, 0),
                    ]
                )
            ],
            "Part::FaceMakerCheese",
        )
        face_c = Part.makeFace(
            [
                Part.makePolygon(
                    [
                        App.Vector(0, 1, 0),
                        App.Vector(3, 1, 0),
                        App.Vector(3, 2, 0),
                        App.Vector(0, 2, 0),
                        App.Vector(0, 1, 0),
                    ]
                )
            ],
            "Part::FaceMakerCheese",
        )

        # Seed element maps so the test verifies the transient fuse drops
        # naming metadata, not just that the projected faces union geometrically.
        face_a.ElementMap = {"FaceA": "FaceA"}
        face_b.ElementMap = {"FaceB": "FaceB"}
        face_c.ElementMap = {"FaceC": "FaceC"}
        self.assertGreater(face_a.ElementMapSize, 0)
        self.assertGreater(face_b.ElementMapSize, 0)
        self.assertGreater(face_c.ElementMapSize, 0)

        single = ArchComponent._make_projected_horizontal_area_face([face_a])
        overlapping_union = ArchComponent._make_projected_horizontal_area_face([face_a, face_b])
        fused = ArchComponent._make_projected_horizontal_area_face([face_a, face_b, face_c])

        self.assertIsNotNone(single)
        self.assertEqual(0, single.ElementMapSize)
        self.assertAlmostEqual(2.0, single.Area, places=7)
        self.assertIsNotNone(overlapping_union)
        self.assertEqual(0, overlapping_union.ElementMapSize)
        self.assertAlmostEqual(3.0, overlapping_union.Area, places=7)
        self.assertEqual(1, len(overlapping_union.Faces))
        self.assertAlmostEqual(8.0, overlapping_union.Faces[0].OuterWire.Length, places=7)
        self.assertIsNotNone(fused)
        self.assertEqual(0, fused.ElementMapSize)
        self.assertAlmostEqual(6.0, fused.Area, places=7)

    def testRemove(self):
        App.Console.PrintLog("Checking Arch Remove...\n")
        l = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(2, 0, 0))
        w = Arch.makeWall(l, width=0.2, height=2, align="Right")
        sb = Part.makeBox(1, 1, 1)
        b = App.ActiveDocument.addObject("Part::Feature", "Box")
        b.Shape = sb
        App.ActiveDocument.recompute()
        Arch.removeComponents(b, w)
        App.ActiveDocument.recompute()
        r = w.Shape.Volume < 0.75
        self.assertTrue(r, "Arch Remove failed")

    def testBsplineSlabAreas(self):
        """Test the HorizontalArea and VerticalArea properties of a Bspline-based slab.

        See https://github.com/FreeCAD/FreeCAD/issues/20989.
        """

        operation = "Checking Bspline slab area calculation..."
        self.printTestMessage(operation)

        doc = App.ActiveDocument

        # Parameters
        radius = 10000  # 10 meters in mm
        extrusionLength = 100  # 10 cm in mm
        numPoints = 50  # Number of points for B-spline
        startAngle = 0  # Start at 0 degrees (right)
        endAngle = 180  # End at 180 degrees (left)

        # Create points for semicircle
        points = []
        angleStep = (endAngle - startAngle) / (numPoints - 1)
        for i in range(numPoints):
            angleDeg = startAngle + i * angleStep
            angleRad = radians(angleDeg)
            x = radius * cos(angleRad)
            y = radius * sin(angleRad)
            points.append(App.Vector(x, y, 0))

        # Create Draft objects
        bspline = Draft.makeBSpline(points, closed=False)
        closingLine = Draft.makeLine(points[-1], points[0])
        doc.recompute()

        # Create sketch
        # We do this because Draft.make_wires does not support B-splines
        # and we need a closed wire for the slab
        sketch = Draft.makeSketch([bspline, closingLine], autoconstraints=True, delete=True)
        if sketch is None:
            self.fail("Sketch creation failed")
        sketch.recompute()

        # Create slab
        slab = Arch.makeStructure(sketch, length=extrusionLength, name="Slab")
        slab.recompute()

        # Calculate theoretical areas
        radiusMeters = radius / 1000
        heightMeters = extrusionLength / 1000
        theoreticalHorizontalArea = (pi * radiusMeters**2) / 2
        theoreticalVerticalArea = (pi * radiusMeters + 2 * radiusMeters) * heightMeters

        # Get actual areas
        actualHorizontalArea = slab.HorizontalArea.getValueAs("m^2").Value
        actualVerticalArea = slab.VerticalArea.getValueAs("m^2").Value

        # Optimally wrapped assertions
        self.assertAlmostEqual(
            actualHorizontalArea,
            theoreticalHorizontalArea,
            places=3,
            msg=(
                "Horizontal area > 0.1% tolerance | "
                f"Exp: {theoreticalHorizontalArea:.3f} m² | "
                f"Got: {actualHorizontalArea:.3f} m²"
            ),
        )

        self.assertAlmostEqual(
            actualVerticalArea,
            theoreticalVerticalArea,
            places=3,
            msg=(
                "Vertical area > 0.1% tolerance | "
                f"Exp: {theoreticalVerticalArea:.3f} m² | "
                f"Got: {actualVerticalArea:.3f} m²"
            ),
        )

    def testHouseSpaceAreas(self):
        """Test the HorizontalArea and VerticalArea properties of a house-like space.

        See https://github.com/FreeCAD/FreeCAD/issues/14687.
        """

        operation = "Checking house space area calculation..."
        self.printTestMessage(operation)

        doc = App.ActiveDocument

        # Dimensional parameters (all in mm)
        baseLength = 5000  # 5m along X-axis
        baseWidth = 5000  # 5m along Y-axis (extrusion depth)
        rectangleHeight = 2500  # 2.5m lower rectangular portion
        triangleHeight = 2500  # 2.5m upper triangular portion
        totalHeight = rectangleHeight + triangleHeight  # 5m total height

        # Create envelope profile points (XZ plane)
        points = [
            App.Vector(0, 0, 0),
            App.Vector(baseLength, 0, 0),
            App.Vector(baseLength, 0, rectangleHeight),
            App.Vector(baseLength / 2, 0, totalHeight),
            App.Vector(0, 0, rectangleHeight),
        ]

        # Create wire with automatic face creation
        wire = Draft.makeWire(points, closed=True, face=True)
        if not wire:
            self.fail(f"Wire creation failed with points: {points}\n")
        doc.recompute()

        # Extrude the wire
        extrudedObj = Draft.extrude(wire, App.Vector(0, baseWidth, 0), solid=True)
        if not extrudedObj:
            self.fail("Extrusion failed - no object created\n")
        extrudedObj.Label = "Extruded house"
        doc.recompute()

        # Create Arch Space from the extrusion
        space = Arch.makeSpace(extrudedObj)
        space.Label = "House space"
        doc.recompute()

        # Calculate theoretical areas
        # Horizontal area (only bottom face on XY plane)
        theoreticalHorizontalArea = (baseLength * baseWidth) / 1e6  # 25 m²

        # Vertical areas
        # Side faces (YZ plane) - two rectangles
        sideFaceArea = (rectangleHeight * baseWidth) / 1e6  # 12.5 m² each
        totalSides = sideFaceArea * 2  # 25 m²

        # Front/back faces (XZ plane)
        rectangularPart = (baseLength * rectangleHeight) / 1e6  # 12.5 m²
        triangularPart = (baseLength * triangleHeight / 2) / 1e6  # 6.25 m²
        totalFrontBack = (rectangularPart + triangularPart) * 2  # 37.5 m²

        theoreticalVerticalArea = totalSides + totalFrontBack  # 62.5 m²

        # Get actual areas from space
        actualHorizontalArea = space.HorizontalArea.getValueAs("m^2").Value
        actualVerticalArea = space.VerticalArea.getValueAs("m^2").Value

        self.assertAlmostEqual(
            actualHorizontalArea,
            theoreticalHorizontalArea,
            places=3,
            msg=f"Horizontal area > 0.1% | Exp: {theoreticalHorizontalArea:.3f} | "
            f"Got: {actualHorizontalArea:.3f}",
        )

        self.assertAlmostEqual(
            actualVerticalArea,
            theoreticalVerticalArea,
            places=3,
            msg=f"Vertical area > 0.1% | Exp: {theoreticalVerticalArea:.3f} | "
            f"Got: {actualVerticalArea:.3f}",
        )

    def test_plan_region_area_falls_back_to_project_ex_when_project_missing(self):
        """Plan-region areas should still compute when TechDraw.project is unavailable."""

        import TechDraw

        points = [
            App.Vector(0, 0, 0),
            App.Vector(3000, 0, 0),
            App.Vector(3000, 2000, 0),
            App.Vector(0, 2000, 0),
        ]
        region = Arch.makePlanRegion(points=points, name="Fallback Region")
        self.document.recompute()

        region.HorizontalArea = 0
        region.PerimeterLength = 0

        with patch.object(
            TechDraw,
            "project",
            side_effect=AttributeError("module 'TechDraw' has no attribute 'project'"),
        ):
            region.Proxy.computeAreas(region)

        self.assertAlmostEqual(region.HorizontalArea.getValueAs("m^2").Value, 6.0, places=3)
        self.assertAlmostEqual(region.PerimeterLength.getValueAs("m").Value, 10.0, places=3)

    def test_remove_single_window_from_wall_host_is_none(self):
        """
        Tests that a window is removed from its wall's host list when
        Arch.removeComponents is called with host=None (single window selection scenario).

        See https://github.com/FreeCAD/FreeCAD/issues/21551
        """

        # Create a basic wall
        wall_base = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0))
        wall = Arch.makeWall(wall_base, width=200, height=2500)

        # Create a window to be added to the wall
        window_width = 1000.0
        window_height = 1200.0

        # Create a Draft Rectangle for the window's Base. Arch.makeWindow can work with
        # either a Wire or a Face.
        window_base = Draft.makeRectangle(length=window_width, height=window_height)

        window = Arch.makeWindow(baseobj=window_base)
        window.Width = window_width  # Manually set as makeWindow(base) doesn't
        window.Height = window_height  # Manually set

        self.document.recompute()

        # Add the window to the wall.
        Arch.addComponents(window, wall)
        self.document.recompute()

        # Pre-condition check: ensure the wall is indeed a host for the window.
        self.assertIn(wall, window.Hosts, "Wall should be in window.Hosts before removal.")
        self.assertEqual(len(window.Hosts), 1, "Window should have 1 host before removal.")

        # Simulate the Arch_Remove command with the scenario where only the window
        # is selected and "Remove" is used.
        Arch.removeComponents([window], host=None)
        self.document.recompute()  # Important for Arch objects to update their state.

        # Assert: the wall should no longer be in the window's Hosts list.
        self.assertNotIn(wall, window.Hosts, "Wall should not be in window.Hosts after removal.")
        self.assertEqual(len(window.Hosts), 0, "Window.Hosts list should be empty after removal.")

    def test_rehost_object_updates_single_host_link_and_preserves_placement(self):
        wall_a = Arch.makeWall(Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0)))
        wall_b = Arch.makeWall(Draft.makeLine(App.Vector(0, 2000, 0), App.Vector(3000, 2000, 0)))
        hosted = self.document.addObject("Part::Box", "HostedSingle")
        hosted.addProperty("App::PropertyLink", "Host", "Component")
        hosted.Placement.Base = App.Vector(400, 500, 600)
        hosted.Host = wall_a
        self.document.recompute()

        original_base = hosted.Placement.Base

        self.assertTrue(Arch.canRehostObject(hosted, wall_b))
        self.assertTrue(
            Arch.rehostObject(hosted, wall_b, preserve_world_position=True, raise_on_error=True)
        )
        self.document.recompute()

        self.assertIs(wall_b, hosted.Host)
        self.assertTrue(hosted.Placement.Base.isEqual(original_base, 1e-6))

    def test_rehost_object_replaces_hosts_link_list_and_supports_clear(self):
        wall_a = Arch.makeWall(Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0)))
        wall_b = Arch.makeWall(Draft.makeLine(App.Vector(0, 2000, 0), App.Vector(3000, 2000, 0)))
        hosted = self.document.addObject("Part::Box", "HostedMulti")
        hosted.addProperty("App::PropertyLinkList", "Hosts", "Component")
        hosted.Placement.Base = App.Vector(700, 800, 900)
        hosted.Hosts = [wall_a]
        self.document.recompute()

        self.assertTrue(Arch.canRehostObject(hosted, wall_b))
        self.assertTrue(Arch.rehostObject(hosted, wall_b, raise_on_error=True))
        self.assertEqual([wall_b], list(hosted.Hosts))

        self.assertTrue(Arch.canRehostObject(hosted, None))
        self.assertTrue(Arch.rehostObject(hosted, None, raise_on_error=True))
        self.assertEqual([], list(hosted.Hosts))

    def test_can_rehost_object_rejects_invalid_targets(self):
        wall = Arch.makeWall(Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0)))
        plain = self.document.addObject("Part::Box", "PlainBox")
        hosted = self.document.addObject("Part::Box", "Hosted")
        hosted.addProperty("App::PropertyLinkList", "Hosts", "Component")
        self.document.recompute()

        self.assertFalse(Arch.canRehostObject(plain, wall))
        self.assertFalse(Arch.canRehostObject(hosted, hosted))

    def test_if_face_vertical(self):
        """
        Test the ArchComponent.AreaCalculator.isFaceVertical method directly.

        Verifies classification of standard walls, periodic surfaces (cylinders),
        extruded surfaces (B-Splines), and sloped faces (tapered wedge) using
        white-box testing on the internal calculator.
        """
        import math

        tolerance = Part.Precision.confusion()

        def get_normal_z(face):
            return abs(face.normalAt(0, 0).z)

        def is_vertical(normal_z):
            return math.isclose(normal_z, 0.0, abs_tol=tolerance)

        def is_horizontal(normal_z):
            return math.isclose(normal_z, 1.0, abs_tol=tolerance)

        def is_sloped(normal_z):
            return not (is_vertical(normal_z) or is_horizontal(normal_z))

        with self.subTest(case="Standard Wall"):
            line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(10, 0, 0))
            wall = Arch.makeWall(line, width=2, height=10)
            self.document.recompute()

            calc = ArchComponent.AreaCalculator(wall)
            vertical_count = 0

            for face in wall.Shape.Faces:
                is_vert = calc.isFaceVertical(face)
                normal_z = get_normal_z(face)

                if is_vertical(normal_z):
                    self.assertTrue(is_vert, "Side face should be vertical")
                    vertical_count += 1
                elif is_horizontal(normal_z):
                    self.assertFalse(is_vert, "Top/Bottom face should not be vertical")

            self.assertEqual(
                vertical_count, 4, f"Expected 4 vertical sides on wall, found {vertical_count}"
            )

        with self.subTest(case="Closed Extrusion"):
            points = [App.Vector(0, 0, 0), App.Vector(10, 0, 0), App.Vector(5, 5, 0)]
            bspline = Draft.makeBSpline(points, closed=True)
            structure = Arch.makeStructure(bspline, height=10)
            self.document.recompute()

            calc_bspline = ArchComponent.AreaCalculator(structure)
            extrusion_vert_count = 0

            for face in structure.Shape.Faces:
                is_vert = calc_bspline.isFaceVertical(face)

                if "SurfaceOfExtrusion" in face.Surface.TypeId:
                    self.assertTrue(is_vert, "Extruded B-Spline surface should be vertical")
                    extrusion_vert_count += 1

            self.assertGreater(
                extrusion_vert_count,
                0,
                f"Expected at least one vertical extruded face, found {extrusion_vert_count}",
            )

        with self.subTest(case="Cylinder"):
            circle = Draft.makeCircle(radius=5)
            struct = Arch.makeStructure(circle, height=20)
            self.document.recompute()

            calc_struct = ArchComponent.AreaCalculator(struct)
            cyl_vertical_count = 0

            for face in struct.Shape.Faces:
                is_vert = calc_struct.isFaceVertical(face)

                if "Cylinder" in face.Surface.TypeId:
                    self.assertTrue(is_vert, "Cylindrical face should be vertical")
                    cyl_vertical_count += 1
                else:
                    self.assertFalse(is_vert, "Caps of cylinder should not be vertical")

            self.assertEqual(
                cyl_vertical_count,
                1,
                f"Expected exactly 1 vertical face on cylinder, found {cyl_vertical_count}",
            )

        with self.subTest(case="Generic Vertical Surface"):
            # Create two B-spline curves, vertically aligned
            points1 = [App.Vector(0, 0, 0), App.Vector(5, 5, 0), App.Vector(10, 0, 0)]
            bspline1 = Draft.makeBSpline(points1, closed=False)

            points2 = [App.Vector(0, 0, 20), App.Vector(5, 5, 20), App.Vector(10, 0, 20)]
            bspline2 = Draft.makeBSpline(points2, closed=False)

            # Create a ruled surface (Loft)
            loft = self.document.addObject("Part::Loft", "GenericVerticalLoft")
            loft.Sections = [bspline1, bspline2]
            loft.Solid = False
            loft.Ruled = True
            self.document.recompute()

            comp = Arch.makeComponent(loft)
            calc_loft = ArchComponent.AreaCalculator(comp)

            generic_vertical_count = 0
            for face in comp.Shape.Faces:
                if calc_loft.isFaceVertical(face):
                    generic_vertical_count += 1

            self.assertEqual(
                generic_vertical_count,
                1,
                f"Expected generic vertical surface to be detected as vertical, found {generic_vertical_count}",
            )

        with self.subTest(case="Tapered Wedge"):
            wedge = self.document.addObject("Part::Wedge", "Wedge")
            wedge.Ymin = 0
            wedge.Zmin = 0
            wedge.Xmin = 0
            wedge.Ymax = 10
            wedge.Zmax = 10
            wedge.Xmax = 10
            # Taper top to create slopes
            wedge.X2min = 2
            wedge.X2max = 8
            wedge.Z2min = 2
            wedge.Z2max = 8
            self.document.recompute()

            comp = Arch.makeComponent(wedge)
            calc_wedge = ArchComponent.AreaCalculator(comp)

            tapered_vertical_count = 0
            for face in comp.Shape.Faces:
                normal_z = get_normal_z(face)

                if is_vertical(normal_z):
                    self.assertTrue(
                        calc_wedge.isFaceVertical(face), "X-Tapered face should be vertical"
                    )
                    tapered_vertical_count += 1
                elif is_sloped(normal_z):
                    self.assertFalse(
                        calc_wedge.isFaceVertical(face), "Sloped face must not be vertical"
                    )

            self.assertGreater(
                tapered_vertical_count,
                0,
                f"Expected at least one vertical face on tapered wedge, found {tapered_vertical_count}",
            )

    def test_vertical_area_update_to_zero(self):
        """
        Verify that VerticalArea property updates correctly even when the result is zero.
        """

        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(10, 0, 0))
        wall = Arch.makeWall(line, width=2, height=10)
        self.document.recompute()

        initial_area = wall.VerticalArea.Value
        self.assertGreater(
            initial_area, 0, f"Setup error: Wall should have vertical area, found {initial_area}"
        )

        # Get the footprint to simulate a flat wall (valid shape, but 0 height)
        footprint_faces = wall.Proxy.getFootprint(wall)

        # Exactly one face is expected for this particular footprint (straight wall)
        self.assertEqual(len(footprint_faces), 1, "Setup error: Expected exactly 1 footprint face")

        # Manually assign the single footprint face as the wall shape. We do this as an alternative
        # to setting height=0, because ArchWall.applyShape protects against null shapes (which
        # height=0 produces), preventing area updates
        wall.Shape = footprint_faces[0]

        wall.Proxy.computeAreas(wall)

        final_area = wall.VerticalArea.Value
        self.assertEqual(final_area, 0.0, f"VerticalArea must update to zero, found {final_area}")

    def test_complex_composite_area(self):
        """
        Integration test: verify that AreaCalculator correctly sums areas from
        mixed geometry types (planar, cylindrical, and generic) within a single object,
        while correctly ignoring horizontal faces.
        """

        # Create planar geometry (Box)
        # 10x10x10 box.
        # 4 Vertical faces = 10 * 10 * 4 = 400.
        # 2 Horizontal faces (Top/Bottom) should be ignored.
        box = Part.makeBox(10, 10, 10)
        box.translate(App.Vector(0, 0, 0))
        expected_box_v_area = 400.0

        # Create cylindrical geometry (Cylinder)
        # Radius 5, Height 10.
        # 1 Vertical Face = 2 * pi * r * h = 100 * pi.
        # 2 Horizontal faces (caps) should be ignored.
        cyl = Part.makeCylinder(5, 10)
        cyl.translate(App.Vector(20, 0, 0))
        expected_cyl_v_area = 100 * pi

        # Create generic geometry (Ruled Surface / Loft)
        # Reuse the B-Spline logic that triggers the fallback projection path
        points1 = [App.Vector(40, 0, 0), App.Vector(45, 5, 0), App.Vector(50, 0, 0)]
        bspline1 = Draft.makeBSpline(points1, closed=False)
        points2 = [App.Vector(40, 0, 10), App.Vector(45, 5, 10), App.Vector(50, 0, 10)]
        bspline2 = Draft.makeBSpline(points2, closed=False)

        loft = self.document.addObject("Part::Loft", "IntegrationLoft")
        loft.Sections = [bspline1, bspline2]
        loft.Solid = False
        loft.Ruled = True
        self.document.recompute()

        # The entire loft is a vertical surface, so we take its total area.
        expected_loft_v_area = loft.Shape.Area

        # Combine into an Arch Component using a compound to simulate a complex single object
        compound_shape = Part.makeCompound([box, cyl, loft.Shape])

        complex_obj = Arch.makeComponent(compound_shape, name="ComplexStructure")

        # Execute calculation
        complex_obj.Proxy.computeAreas(complex_obj)

        # Verify
        total_expected = expected_box_v_area + expected_cyl_v_area + expected_loft_v_area

        self.assertAlmostEqual(
            complex_obj.VerticalArea.Value,
            total_expected,
            places=3,
            msg=f"Failed to aggregate vertical areas of mixed types. Expected {total_expected}, got {complex_obj.VerticalArea.Value}",
        )

    def test_horizontal_area_tilted_cylinders(self):
        """
        Verify that the HorizontalArea of tilted cylinders is correct.
        The cylinders are rotated around the X-axis and the Y-axis.
        """

        # The created cylinders are very tall to also check for potential
        # 'crazy edge' issues related to the use of TechDraw code. Edges
        # longer than ca. 10m are considered 'crazy'.
        angle = 30  # in degrees
        radius = 100  # in mm
        height = 50000  # in mm

        # To calculate the horizontal area, the shape to be projected can be
        # reduced to a rectangular face through the center of the cylinder
        # and two semi-circular faces for the top and bottom.
        area_rect = 2 * radius * height * cos(radians(90 - angle))
        area_circ = pi * radius**2 * cos(radians(angle))
        area_expected = (area_rect + area_circ) / 1e6  # in m^2

        for rot_vec in (App.Vector(1, 0, 0), App.Vector(0, 1, 0)):
            cyl = Part.show(Part.makeCylinder(radius, height))
            cyl.Placement.Rotation = App.Rotation(rot_vec, 30)
            obj = Arch.makeStructure(cyl)
            obj.recompute()
            area_actual = obj.HorizontalArea.getValueAs("m^2").Value

            self.assertAlmostEqual(
                area_expected,
                area_actual,
                places=3,
                msg=(
                    "Horizontal area > 0.1% tolerance | "
                    f"Exp: {area_expected:.3f} m² | "
                    f"Got: {area_actual:.3f} m²"
                ),
            )

    def test_rotated_component_area(self):
        """Verify AreaCalculator respects Placement for generic ArchComponents."""
        self.printTestMessage("ArchComponent rotated area calculation...")

        # Create a horizontal slab (1 m x 1 m x 0.01 m)
        # Area of one large face = 1.0 m2
        box = self.document.addObject("Part::Box", "HorizontalSlab")
        box.Length = 1000.0
        box.Width = 1000.0
        box.Height = 10.0
        self.document.recompute()

        # Wrap in a generic Component and rotate 90 degrees around the X axis to turn it into a
        # vertical panel.
        comp = Arch.makeComponent(box)
        comp.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)
        self.document.recompute()

        # Check the VerticalArea property.
        # FreeCAD sums all vertical faces (front + back + vertical side edges).
        # Expected: (1.0 * 1.0)*2 + (1.0 * 0.01)*2 = 2.02 m2
        expected_v_area = 2.02
        actual_v_area = comp.VerticalArea.getValueAs("m^2").Value

        self.assertAlmostEqual(
            actual_v_area,
            expected_v_area,
            places=2,
            msg=f"Vertical area calculation failed for rotated component. Got {actual_v_area}",
        )

    def test_moved_component_subtraction(self):
        """Verify subtractions align correctly for moved/rotated components."""
        self.printTestMessage("moved component boolean subtraction...")

        # Create a base component and move it 5 meters away
        base_box = self.document.addObject("Part::Box", "BaseBox")
        base_box.Length = base_box.Width = base_box.Height = 100.0
        comp = Arch.makeComponent(base_box)
        comp.Placement.Base = App.Vector(5000.0, 0, 0)
        self.document.recompute()

        initial_volume = comp.Shape.Volume  # Should be 1,000,000 mm^3

        # Create a "Cutter" box at the same global 5-meter position
        cutter = self.document.addObject("Part::Box", "CutterBox")
        cutter.Length = cutter.Width = cutter.Height = 100.0
        cutter.Placement.Base = App.Vector(5000.0, 0, 0)
        self.document.recompute()

        # Add the cutter to subtractions.
        # processSubShapes must inverse-transform the cutter into the component's local space.
        comp.Subtractions = [cutter]
        self.document.recompute()

        # Assert: If the fix works, the volumes overlap perfectly and result is 0.
        # If the fix fails, the cutter is ignored because it looks for the box at the origin.
        final_volume = comp.Shape.Volume
        self.assertLess(
            final_volume,
            initial_volume,
            "Subtraction failed. The global cutter did not intersect the moved local shape.",
        )
        self.assertAlmostEqual(final_volume, 0.0, places=5)

    def test_apply_shape_spread(self):
        """Ensure generic components handle spreading (automatic arraying) via the Axis property."""
        self.printTestMessage("applyShape spread logic (generic component)...")

        # Create base geometry at identity (0,0,0)
        box = self.document.addObject("Part::Box", "SpreadBase")
        box.Length = box.Width = box.Height = 100.0
        self.document.recompute()

        # Create a generic Arch Component
        comp = Arch.makeComponent(box)

        # Create an Axis system with 2 points (at 0 and 2000mm)
        axis = Arch.makeAxis(num=2, size=2000)
        self.document.recompute()

        # Link the axis to the component
        comp.Axis = axis
        self.document.recompute()

        # Verify that the resulting shape contains 2 instances (solids)
        # This confirms that the execute() loop correctly processes the Axis property.
        self.assertEqual(
            len(comp.Shape.Solids),
            2,
            "Generic Arch Component failed to spread geometry to Axis points.",
        )

    def test_component_double_transformation(self):
        """Test that Arch Components do not suffer from double-transformation."""
        self.printTestMessage("ArchComponent placement and coordinate integrity...")

        # Scenario 1: translation and vertex check
        with self.subTest(case="Translation Only"):
            base_box = self.document.addObject("Part::Box", "BaseBoxTrans")
            base_box.Length = base_box.Width = base_box.Height = 1000.0

            # Move the box 10 meters away. Raw vertices are at 0, Shape.Placement is at 10 m.
            base_box.Placement.Base = App.Vector(10000, 0, 0)
            self.document.recompute()

            comp = Arch.makeComponent(base_box, name="TestTrans")
            self.document.recompute()

            # The component object should match the base object's placement
            self.assertEqual(comp.Placement.Base.x, 10000.0)

            # Verification of localization:
            # Visual Center = Object.Placement (10000) + Shape.Center (500) = 10500.
            # If the bug were present (double transform), it would be 20500.
            actual_center_x = comp.Shape.BoundBox.Center.x
            self.assertAlmostEqual(
                actual_center_x,
                10500.0,
                places=3,
                msg="Double transformation detected! Object is offset twice.",
            )

        # Scenario 2: CSG alignment (Additions)
        with self.subTest(case="CSG Alignment"):
            # Base box (1m cube) moved to 5m
            base_box_csg = self.document.addObject("Part::Box", "BaseBoxCSG")
            base_box_csg.Length = base_box_csg.Width = base_box_csg.Height = 1000.0
            base_box_csg.Placement.Base = App.Vector(5000, 0, 0)

            comp_csg = Arch.makeComponent(base_box_csg, name="TestCSG")
            self.document.recompute()

            # Addition box (identical 1m cube) at exactly the same global location (5m)
            # They should overlap perfectly.
            add_box = self.document.addObject("Part::Box", "AdditionBox")
            add_box.Length = add_box.Width = add_box.Height = 1000.0
            add_box.Placement.Base = App.Vector(5000, 0, 0)
            if App.GuiUp:
                add_box.ViewObject.hide()

            comp_csg.Additions = [add_box]
            self.document.recompute()

            # If sanitized, they overlap perfectly: Total Volume = 1,000,000,000 mm3
            # If not sanitized, they would be 5m apart: Volume = 2,000,000,000 mm3
            self.assertAlmostEqual(
                comp_csg.Shape.Volume,
                1000000000.0,
                delta=100.0,
                msg="CSG pieces did not align. Base shape likely retained the offset.",
            )

    def test_component_without_base(self):
        """Test that a component without a base retains its shape."""
        self.printTestMessage("ArchComponent without Base test...")

        box1 = self.document.addObject("Part::Box", "TestBox1")
        box2 = self.document.addObject("Part::Box", "TestBox2")
        self.document.recompute()
        volume_box1 = box1.Shape.Volume
        volume_box2 = box2.Shape.Volume  # Box2 will be deleted.

        comp1 = Arch.makeComponent(box1)
        comp2 = Arch.makeComponent(box2, delete=True)
        self.document.recompute()

        comp1.Base = None
        self.document.recompute()

        self.assertAlmostEqual(
            volume_box1,
            comp1.Shape.Volume,
            places=6,
            msg="Wrong shape for baseless component!",
        )

        self.assertAlmostEqual(
            volume_box2,
            comp2.Shape.Volume,
            places=6,
            msg="Wrong shape for baseless component!",
        )

    def test_add_window_link_standard(self):
        """Test adding a Window Link to a Wall using standard lifecycle (recompute before add).
        This verifies the 'appLinkExecute' hook mechanism.
        """
        operation = "Arch Link addition (Standard Lifecycle)"
        self.printTestMessage(operation)

        # Create the host wall
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(4000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=3000, align="Center")
        self.document.recompute()
        initial_volume = wall.Shape.Volume

        # Create a prototype window
        rect = Draft.makeRectangle(length=1000, height=1500)
        rect.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)
        rect.Placement.Base = App.Vector(0, 0, 0)
        self.document.recompute()

        win_proto = Arch.makeWindow(baseobj=rect, name="Window_Prototype")
        win_proto.Width = 1000
        win_proto.Height = 1500
        win_proto.Frame = 100
        self.document.recompute()

        # Create a link to the prototype window and recompute
        # This is the standard lifecycle
        link1 = self.document.addObject("App::Link", "Link_Standard")
        link1.LinkedObject = win_proto
        link1.Placement.Base = App.Vector(1000, 0, 500)
        self.document.recompute()  # Trigger appLinkExecute -> shadow_link_properties

        # Add the window link to the wall
        Arch.addComponents(link1, wall)
        self.document.recompute()

        # Assert
        self.assertIn(wall, link1.Hosts, "Link should host the wall")
        self.assertNotIn(wall, win_proto.Hosts, "Prototype should not host the wall")
        self.assertLess(wall.Shape.Volume, initial_volume, "Wall volume should decrease (hole cut)")

    def test_add_window_link_immediate(self):
        """Test adding a Window Link to a Wall immediately without recomputing.
        This verifies the 'ensure_link_overrides' safeguard mechanism.
        """
        operation = "Arch Link addition (Immediate Lifecycle)"
        self.printTestMessage(operation)

        # Create the host wall
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(4000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=3000, align="Center")
        self.document.recompute()
        initial_volume = wall.Shape.Volume

        # Create a prototype window
        rect = Draft.makeRectangle(length=1000, height=1500)
        rect.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)
        rect.Placement.Base = App.Vector(0, 0, 0)
        self.document.recompute()

        win_proto = Arch.makeWindow(baseobj=rect, name="Window_Prototype")
        win_proto.Width = 1000
        win_proto.Height = 1500
        win_proto.Frame = 100
        self.document.recompute()

        # Create a link to the prototype window without recomputing
        link2 = self.document.addObject("App::Link", "Link_Immediate")
        link2.LinkedObject = win_proto
        link2.Placement.Base = App.Vector(3000, 0, 500)

        # Add the window link to the wall immediately
        # This triggers ensure_link_overrides -> shadow_link_properties
        Arch.addComponents(link2, wall)
        self.document.recompute()

        # Assert
        self.assertIn(wall, link2.Hosts, "Link should host the wall")
        self.assertNotIn(wall, win_proto.Hosts, "Prototype should NOT host the wall")
        self.assertLess(wall.Shape.Volume, initial_volume, "Wall volume should decrease (hole cut)")

    def test_remove_window_link(self):
        """Test removing a Window Link from a Wall."""
        operation = "Arch Link removal"
        self.printTestMessage(operation)

        # Create the host wall
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(4000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=3000, align="Center")
        self.document.recompute()
        initial_volume = wall.Shape.Volume

        # Create a prototype window
        rect = Draft.makeRectangle(length=1000, height=1500)
        rect.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)
        rect.Placement.Base = App.Vector(0, 0, 0)
        self.document.recompute()

        win_proto = Arch.makeWindow(baseobj=rect)
        win_proto.Width = 1000
        win_proto.Height = 1500
        win_proto.Frame = 100
        self.document.recompute()

        # Create a link to the prototype window
        link = self.document.addObject("App::Link", "Link_Remove")
        link.LinkedObject = win_proto
        link.Placement.Base = App.Vector(2000, 0, 500)
        self.document.recompute()

        # Add the window link to the wall, ensure it cuts the hole
        Arch.addComponents(link, wall)
        self.document.recompute()
        cut_volume = wall.Shape.Volume
        self.assertLess(cut_volume, initial_volume, "Setup failed: Wall not cut")

        # Remove the window link from the wall
        Arch.removeComponents([link])
        self.document.recompute()

        # Assert
        self.assertNotIn(wall, link.Hosts, "Link should no longer host the wall")
        self.assertAlmostEqual(
            wall.Shape.Volume, initial_volume, 3, "Wall volume should be restored"
        )
