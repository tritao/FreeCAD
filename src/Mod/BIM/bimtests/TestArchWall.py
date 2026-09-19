# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2013 Yorik van Havre <yorik@uncreated.net>              *
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

# Unit tests for the Arch wall module

import math
import os
import tempfile
from unittest.mock import patch

import Arch
import ArchComponent
import ArchPlanAnalytic
import ArchRepresentation
import ArchWall
import ArchWallConstruction
import ArchWallExact
import ArchWallEndCondition
import Draft
import Part
import FreeCAD as App
from bimtests import TestArchBase


class TestArchWall(TestArchBase.TestArchBase):

    def test_resolved_wall_defaults_preserve_instance_property_behavior(self):
        """The future type boundary initially mirrors existing wall values."""

        material = Arch.makeMultiMaterial()
        wall = Arch.makeWall(length=2400, width=275, height=3150, align="Right", offset=35)
        wall.Material = material

        defaults = ArchWall.get_resolved_wall_defaults(wall)

        self.assertEqual(275.0, defaults.width)
        self.assertEqual(3150.0, defaults.height)
        self.assertEqual("Right", defaults.align)
        self.assertEqual(35.0, defaults.offset)
        self.assertIs(material, defaults.material)

        section = wall.Proxy.get_resolved_section(wall)
        self.assertEqual(35.0, section.y_min)
        self.assertEqual(310.0, section.y_max)

    def test_wall_type_supplies_inherited_geometry_defaults(self):
        wall_type = Arch.makeWallType("Exterior 300")
        wall_type.Function = "Exterior"
        wall_type.Width = 300
        wall_type.DefaultHeight = 2800
        wall_type.Align = "Center"

        wall = Arch.makeWall(length=2400, wall_type=wall_type)
        self.document.recompute()

        defaults = ArchWall.get_resolved_wall_defaults(wall)
        self.assertEqual(300.0, defaults.width)
        self.assertEqual(2800.0, defaults.height)
        self.assertEqual([], list(wall.TypeOverrides))
        self.assertAlmostEqual(300.0, wall.Shape.BoundBox.YLength)
        self.assertAlmostEqual(2800.0, wall.Shape.BoundBox.ZLength)

        wall_type.Width = 360
        self.document.recompute()
        self.assertAlmostEqual(360.0, wall.Shape.BoundBox.YLength)

    def test_wall_construction_assigns_type_without_occurrence_overrides(self):
        wall_type = Arch.makeWallType("Typed Construction")
        wall_type.Width = 325
        wall_type.DefaultHeight = 2750
        wall_type.Align = "Left"
        spec = ArchWallConstruction.WallConstructionSpec(
            width=325,
            height=2750,
            align="Left",
            wall_type=wall_type,
        )

        wall = ArchWallConstruction.create_wall_segment(
            App.Vector(),
            App.Vector(2000, 0, 0),
            spec,
            auto_group=False,
        )
        self.document.recompute()

        self.assertIs(wall.WallType, wall_type)
        self.assertEqual([], list(wall.TypeOverrides))
        defaults = ArchWall.get_resolved_wall_defaults(wall)
        self.assertEqual((325.0, 2750.0, "Left"), (defaults.width, defaults.height, defaults.align))

    def test_assigning_wall_type_preserves_differing_instance_values(self):
        wall = Arch.makeWall(length=2000, width=225, height=2600, align="Left")
        wall_type = Arch.makeWallType("Generic")
        wall_type.Width = 300
        wall_type.DefaultHeight = 3000
        wall_type.Align = "Center"

        ArchWall.assign_wall_type(wall, wall_type, preserve_instance_values=True)
        defaults = ArchWall.get_resolved_wall_defaults(wall)

        self.assertEqual({"Width", "Height", "Align"}, set(wall.TypeOverrides))
        self.assertEqual(225.0, defaults.width)
        self.assertEqual(2600.0, defaults.height)
        self.assertEqual("Left", defaults.align)

    def test_wall_type_instance_override_can_be_reset_to_type(self):
        wall_type = Arch.makeWallType("Partition")
        wall_type.Width = 125
        wall = Arch.makeWall(length=2000, wall_type=wall_type)

        wall.Width = 175
        self.assertIn("Width", wall.TypeOverrides)
        self.assertEqual(175.0, ArchWall.get_resolved_wall_defaults(wall).width)

        ArchWall.set_wall_type_override(wall, "Width", False)
        self.document.recompute()
        self.assertNotIn("Width", wall.TypeOverrides)
        self.assertEqual(125.0, ArchWall.get_resolved_wall_defaults(wall).width)
        self.assertAlmostEqual(125.0, wall.Shape.BoundBox.YLength)

    def _wall_plan_representation(self, wall):
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            cut_offset=1000.0,
            target_offset=0.0,
        )
        return ArchRepresentation.representation_for(wall, request)

    @staticmethod
    def _plan_hatch_mappings(representation):
        return tuple(
            mapping
            for mapping in representation.source_mappings
            if mapping.role == "PlanHatch"
        )

    def test_wall_type_plan_hatch_is_clipped_to_cut_faces(self):
        wall_type = Arch.makeWallType("Exterior Hatched")
        wall_type.Function = "Exterior"
        wall_type.PlanHatch = "Diagonal"
        wall_type.PlanHatchSpacing = 100
        wall_type.PlanHatchAngle = 45
        wall = Arch.makeWall(length=2000, wall_type=wall_type)
        self._make_hosted_window(wall, "HatchWindow", 700, 0, width=600, height=2000)
        self.document.recompute()

        representation = self._wall_plan_representation(wall)
        hatches = self._plan_hatch_mappings(representation)

        self.assertGreater(len(hatches), 0)
        for mapping in hatches:
            self.assertIs(mapping.source, wall)
            start, end = mapping.geometry[0], mapping.geometry[-1]
            midpoint = start.add(end).multiply(0.5)
            self.assertTrue(
                any(face.isInside(midpoint, 0.001, True) for face in representation.cut_geometry)
            )

    def test_wall_type_plan_hatch_respects_angle_and_spacing(self):
        wall_type = Arch.makeWallType("Exterior Hatched")
        wall_type.PlanHatch = "Diagonal"
        wall_type.PlanHatchSpacing = 100
        wall_type.PlanHatchAngle = 30
        wall = Arch.makeWall(length=2000, width=400, wall_type=wall_type)
        self.document.recompute()

        coarse = self._plan_hatch_mappings(self._wall_plan_representation(wall))
        directions = set()
        for mapping in coarse:
            vector = mapping.geometry[-1].sub(mapping.geometry[0])
            directions.add(round(math.degrees(math.atan2(vector.y, vector.x)) % 180.0, 3))
        self.assertEqual({30.0}, directions)

        wall_type.PlanHatchSpacing = 50
        self.document.recompute()
        fine = self._plan_hatch_mappings(self._wall_plan_representation(wall))
        self.assertGreater(len(fine), len(coarse))

    def test_cross_plan_hatch_adds_two_directions(self):
        wall_type = Arch.makeWallType("Cross Hatched")
        wall_type.PlanHatch = "Cross"
        wall_type.PlanHatchSpacing = 100
        wall_type.PlanHatchAngle = 45
        wall = Arch.makeWall(length=1000, width=400, wall_type=wall_type)
        self.document.recompute()

        directions = set()
        for mapping in self._plan_hatch_mappings(self._wall_plan_representation(wall)):
            vector = mapping.geometry[-1].sub(mapping.geometry[0])
            directions.add(round(math.degrees(math.atan2(vector.y, vector.x)) % 180.0, 3))
        self.assertEqual({45.0, 135.0}, directions)

    def test_wall_type_plan_hatch_change_invalidates_cached_wall_representation(self):
        from bimviews import representation_cache

        wall_type = Arch.makeWallType("Cached Hatch")
        wall_type.PlanHatch = "Diagonal"
        wall = Arch.makeWall(length=1000, wall_type=wall_type)
        self.document.recompute()
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            cut_offset=1000.0,
            target_offset=0.0,
        )
        representation = self._wall_plan_representation(wall)
        representation_cache.cache_representation(wall, request, representation)

        wall_type.PlanHatchSpacing = 50
        self.document.recompute()

        self.assertIsNone(representation_cache.get_cached_representation(wall, request))

    def _make_hosted_window(self, wall, name, x_start, z_start, width=800.0, height=1200.0):
        sketch = self.document.addObject("Sketcher::SketchObject", name + "Sketch")
        sketch.addGeometry(
            [
                Part.LineSegment(App.Vector(0, 0, 0), App.Vector(width, 0, 0)),
                Part.LineSegment(App.Vector(width, 0, 0), App.Vector(width, height, 0)),
                Part.LineSegment(App.Vector(width, height, 0), App.Vector(0, height, 0)),
                Part.LineSegment(App.Vector(0, height, 0), App.Vector(0, 0, 0)),
            ]
        )
        sketch.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)
        sketch.Placement.Base = App.Vector(x_start, 0, z_start)
        self.document.recompute()

        window = Arch.makeWindow(sketch, name=name)
        window.Width = width
        window.Height = height
        window.HoleDepth = 0
        window.WindowParts = ["DefaultFrame", "Frame", "Wire0", "60", "0"]
        self.document.recompute()

        Arch.addComponents(window, wall)
        self.document.recompute()
        return window

    def testWall(self):
        operation = "Checking Arch Wall..."
        self.printTestMessage(operation)

        l = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(-2, 0, 0))
        w = Arch.makeWall(l)
        self.assertTrue(w, "Arch Wall failed")

    def testWallMultiMatAlign(self):
        operation = "Checking Arch Wall with MultiMaterial and 3 alignments..."
        self.printTestMessage(operation)

        matA = Arch.makeMaterial()
        matB = Arch.makeMaterial()
        matMulti = Arch.makeMultiMaterial()
        matMulti.Materials = [matA, matB]
        matMulti.Thicknesses = [100, 200]  # total width different from default 200
        pts = [
            App.Vector(0, 0, 0),
            App.Vector(1000, 0, 0),
            App.Vector(1000, 1000, 0),
            App.Vector(2000, 1000, 0),
        ]
        # wall based on wire:
        wire = Draft.makeWire(pts)
        wallWire = Arch.makeWall(wire)
        wallWire.Material = matMulti
        # wall based on sketch:
        sketch = App.activeDocument().addObject("Sketcher::SketchObject", "Sketch")
        sketch.addGeometry(
            [
                Part.LineSegment(pts[0], pts[1]),
                Part.LineSegment(pts[1], pts[2]),
                Part.LineSegment(pts[2], pts[3]),
            ]
        )
        wallSketch = Arch.makeWall(sketch)
        wallSketch.Material = matMulti

        alignLst = ["Left", "Center", "Right"]
        checkLst = [
            [App.Vector(0, -300, 0), App.Vector(2000, 1000, 0)],
            [App.Vector(0, -150, 0), App.Vector(2000, 1150, 0)],
            [App.Vector(0, 0, 0), App.Vector(2000, 1300, 0)],
        ]
        for i in range(3):
            wallWire.Align = alignLst[i]
            wallSketch.Align = alignLst[i]
            App.ActiveDocument.recompute()
            for box in [wallWire.Shape.BoundBox, wallSketch.Shape.BoundBox]:
                ptMin = App.Vector(box.XMin, box.YMin, 0)
                self.assertTrue(
                    ptMin.isEqual(checkLst[i][0], 1e-8),
                    "Arch Wall with MultiMaterial and 3 alignments failed",
                )
                ptMax = App.Vector(box.XMax, box.YMax, 0)
                self.assertTrue(
                    ptMax.isEqual(checkLst[i][1], 1e-8),
                    "Arch Wall with MultiMaterial and 3 alignments failed",
                )

    def test_wall_from_issue_29701_left_align(self):
        """Regression test for a sketch-based left-aligned wall that previously truncated."""
        operation = "Checking Arch Wall left-align regression from issue 29701..."
        self.printTestMessage(operation)

        point_data = [
            (0.0, 0.0),
            (9842.5, 0.0),
            (9842.5, -393.7),
            (9740.9, -393.7),
            (9740.9, -3657.6),
            (13004.8, -3657.6),
            (13004.8, -393.7),
            (12903.2, -393.7),
            (12903.2, 0.0),
            (17278.35, 0.0),
            (17278.35, 3873.5),
            (17179.925, 3873.5),
            (17179.925, 4267.2),
            (17278.35, 4267.2),
            (17278.35, 7737.475),
            (10369.55, 7737.475),
            (10369.55, 6924.675),
            (10077.45, 6924.675),
            (10077.45, 7318.375),
            (10175.875, 7318.375),
            (10175.875, 11191.875),
            (5908.675, 11191.875),
            (5908.675, 11801.475),
            (4079.875, 11801.475),
            (4079.875, 10556.875),
            (3787.775, 10556.875),
            (3787.775, 10950.575),
            (3886.2, 10950.575),
            (3886.2, 14030.637),
            (3095.937, 14820.9),
            (787.4, 14820.9),
            (0.0, 14033.5),
            (0.0, 10972.8),
            (98.425, 10972.8),
            (98.425, 10579.1),
            (0.0, 10579.1),
            (0.0, 8515.35),
            (98.425, 8515.35),
            (98.425, 8121.65),
            (0.0, 8121.65),
            (0.0, 5683.25),
            (98.425, 5683.25),
            (98.425, 5289.55),
            (0.0, 5289.55),
        ]
        points = [App.Vector(x, y, 0) for x, y in point_data]
        sketch = self.document.addObject("Sketcher::SketchObject", "Issue29701Sketch")
        sketch.addGeometry(
            [Part.LineSegment(start, end) for start, end in zip(points, points[1:] + points[:1])]
        )
        self.document.recompute()

        wall = Arch.makeWall(sketch, width=193.675, height=2641.6, align="Left")
        self.document.recompute()

        self.assertTrue(wall.Shape.isValid(), "The wall shape should be valid.")
        self.assertEqual(len(wall.Shape.Solids), 1, "The wall should produce one solid.")
        self.assertGreater(
            wall.Shape.BoundBox.XLength,
            17000.0,
            "The left-aligned wall should span the full sketch width.",
        )
        self.assertGreater(
            wall.Shape.BoundBox.YLength,
            18000.0,
            "The left-aligned wall should span the full sketch height.",
        )
        self.assertGreater(
            wall.Shape.Volume,
            3.8e10,
            "The left-aligned wall volume should not collapse after binding the segments.",
        )

    def test_makeWall(self):
        """Test the makeWall function."""
        operation = "Testing makeWall function"
        self.printTestMessage(operation)

        wall = Arch.makeWall(length=5000, width=200, height=3000)
        self.assertIsNotNone(wall, "makeWall failed to create a wall object.")
        self.assertEqual(wall.Label, "Wall", "Wall label is incorrect.")

    def test_wall_footprint_shows_hosted_opening_gap(self):
        """Hosted windows should split the wall footprint at the plan cut height."""
        self.printTestMessage("Checking wall footprint with hosted opening...")

        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=3000)
        self.document.recompute()

        initial_faces = wall.Proxy.getFootprint(wall)
        self.assertEqual(
            len(initial_faces), 1, "Straight wall footprint should start as a single face."
        )

        window_width = 800.0
        self._make_hosted_window(
            wall,
            "FootprintWindow",
            x_start=1100,
            z_start=800,
            width=window_width,
            height=1200.0,
        )

        footprint_faces = wall.Proxy.getFootprint(wall)
        self.assertEqual(
            len(footprint_faces),
            2,
            "Hosted opening should split a straight wall footprint into two faces.",
        )
        footprint_area = sum(face.Area for face in footprint_faces)
        expected_area = (wall.Length.Value - window_width) * wall.Width.Value
        self.assertAlmostEqual(
            footprint_area,
            expected_area,
            places=3,
            msg="Wall footprint area should reflect the hosted opening gap at plan cut height.",
        )

    def test_wall_plan_representation_preserves_semantic_source(self):
        """Generated plan geometry should map back to its source wall."""

        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=2500)
        self.document.recompute()

        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            cut_offset=1000.0,
            target_offset=0.0,
        )
        representation = ArchRepresentation.representation_for(wall, request)

        self.assertIs(representation.source, wall)
        self.assertGreater(len(representation.cut_geometry), 0)
        mapping = representation.mapping_for(representation.cut_geometry[0])
        self.assertIsNotNone(mapping)
        self.assertIs(mapping.source, wall)
        self.assertEqual(mapping.role, "PlanCutFace")
        self.assertEqual(mapping.subelement, "PlanFace1")

    def test_straight_wall_plan_representation_uses_analytic_model(self):
        """A simple Plan wall must not section its final OCCT solid."""

        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=2500)
        self.document.recompute()
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            cut_offset=1000.0,
            target_offset=0.0,
        )

        with patch.object(wall.Proxy, "_getCutRepresentation") as section_shape:
            representation = wall.Proxy.getRepresentation(wall, request)

        section_shape.assert_not_called()
        self.assertIsNotNone(representation.analytic_model)
        self.assertEqual(1, len(representation.cut_geometry))
        self.assertAlmostEqual(600000.0, representation.cut_geometry[0].Area)

    def test_multilayer_plan_faces_preserve_layer_material_ownership(self):
        first_material = Arch.makeMaterial(name="FirstLayerMaterial")
        second_material = Arch.makeMaterial(name="SecondLayerMaterial")
        first_material.Material = {
            "Hatch Pattern": "*Diagonal\n45,0,0,0,4",
            "Hatch Scale": "1",
        }
        second_material.Material = {
            "Hatch Pattern": "*Cross\n0,0,0,0,4\n90,0,0,0,4",
            "Hatch Scale": "1",
        }
        material = Arch.makeMultiMaterial(name="LayeredWallMaterial")
        material.Materials = [first_material, second_material]
        material.Thicknesses = [100, 200]
        wall = Arch.makeWall(length=3000, width=300, height=2500)
        wall.Material = material
        self.document.recompute()
        request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            cut_offset=1000.0,
            target_offset=0.0,
        )

        representation = wall.Proxy.getRepresentation(wall, request)

        self.assertEqual(2, len(representation.cut_geometry))
        self.assertEqual(
            [first_material, second_material],
            [
                representation.mapping_for(face).related_sources[0]
                for face in representation.cut_geometry
            ],
        )
        self.assertEqual(
            [300000.0, 600000.0],
            sorted(round(face.Area, 6) for face in representation.cut_geometry),
        )
        fallback = ArchRepresentation.CutSurfaceStyle(
            ArchRepresentation.CutFillMode.MATERIAL
        )
        self.assertEqual(
            ["PAT", "PAT"],
            [
                ArchRepresentation.cut_surface_style_for(
                    representation.mapping_for(face), fallback
                ).pattern_kind
                for face in representation.cut_geometry
            ],
        )

        self._make_hosted_window(wall, "LayeredWallOpening", 800, 500)
        from bimviews import representation_cache

        representation_cache.invalidate_document(self.document)
        opened = wall.Proxy.getRepresentation(wall, request)
        self.assertEqual(2, len(opened.cut_geometry))
        self.assertLess(sum(face.Area for face in opened.cut_geometry), 900000.0)
        self.assertEqual(
            {first_material, second_material},
            {
                opened.mapping_for(face).related_sources[0]
                for face in opened.cut_geometry
            },
        )

    def test_joined_wall_analytic_outputs_match_exact_shape(self):
        """Joined-wall meshes and directly compiled solids match legacy geometry."""

        with patch.object(ArchWallExact, "compile_straight_wall", return_value=None):
            support = Arch.makeWall(length=2000, width=200, height=1000)
            trimmed = Arch.makeWall(length=1000, width=200, height=1000)
            trimmed.Placement = App.Placement(
                App.Vector(1000, 500, 0),
                App.Rotation(App.Vector(1, 0, 0), App.Vector(0, 1, 0)),
            )
            self.document.recompute()
            joint = Arch.makeWallJoint(support, trimmed, "Butt")
            joint.ButtTrimmed = "WallB"
            self.document.recompute()
            legacy_shapes = {wall.Name: wall.Shape.copy() for wall in (support, trimmed)}

        for wall in (support, trimmed):
            recipe = ArchPlanAnalytic.straight_wall_geometry_recipe(wall, wall.Proxy)
            self.assertIsNotNone(recipe)
            mesh = recipe.viewport_mesh()
            self.assertIsNotNone(mesh)
            self.assertTrue(mesh.is_closed)
            compilation = ArchWallExact.compile_wall_recipe(recipe)
            self.assertIsNotNone(compilation)
            self.assertTrue(compilation.shape.isValid())
            legacy_shape = legacy_shapes[wall.Name]
            bounds = legacy_shape.BoundBox
            expected_bounds = (
                bounds.XMin,
                bounds.YMin,
                bounds.ZMin,
                bounds.XMax,
                bounds.YMax,
                bounds.ZMax,
            )
            for actual, expected in zip(mesh.bounds, expected_bounds):
                self.assertAlmostEqual(actual, expected, delta=1e-5)
            self.assertAlmostEqual(mesh.volume, legacy_shape.Volume, delta=1e-3)
            compiled_bounds = compilation.shape.BoundBox
            for actual, expected in zip(
                (
                    compiled_bounds.XMin,
                    compiled_bounds.YMin,
                    compiled_bounds.ZMin,
                    compiled_bounds.XMax,
                    compiled_bounds.YMax,
                    compiled_bounds.ZMax,
                ),
                expected_bounds,
            ):
                self.assertAlmostEqual(actual, expected, delta=1e-5)
            self.assertAlmostEqual(
                compilation.shape.Volume, legacy_shape.Volume, delta=1e-3
            )

        for wall in (support, trimmed):
            wall.touch()
        with patch.object(
            support.Proxy, "processSubShapes", wraps=support.Proxy.processSubShapes
        ) as legacy_subtractions:
            self.document.recompute()
        legacy_subtractions.assert_not_called()
        for wall in (support, trimmed):
            runtime_bounds = wall.Shape.BoundBox
            legacy_bounds = legacy_shapes[wall.Name].BoundBox
            for actual, expected in zip(
                (
                    runtime_bounds.XMin,
                    runtime_bounds.YMin,
                    runtime_bounds.ZMin,
                    runtime_bounds.XMax,
                    runtime_bounds.YMax,
                    runtime_bounds.ZMax,
                ),
                (
                    legacy_bounds.XMin,
                    legacy_bounds.YMin,
                    legacy_bounds.ZMin,
                    legacy_bounds.XMax,
                    legacy_bounds.YMax,
                    legacy_bounds.ZMax,
                ),
            ):
                self.assertAlmostEqual(actual, expected, delta=1e-5)
            self.assertAlmostEqual(
                wall.Shape.Volume, legacy_shapes[wall.Name].Volume, delta=1e-3
            )

    def test_wall_model_provider_selects_viewport_mesh_and_exact_fallback(self):
        """Model requests opt into meshes and retain exact fallback behavior."""

        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(3000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=2500)
        self.document.recompute()
        exact_request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL
        )
        viewport_request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL,
            representation_mode=ArchRepresentation.RepresentationMode.VIEWPORT,
        )

        exact = ArchRepresentation.representation_for(wall, exact_request)
        viewport = ArchRepresentation.representation_for(wall, viewport_request)

        self.assertIsInstance(exact, ArchRepresentation.PartShapeRepresentation)
        self.assertIsInstance(viewport, ArchRepresentation.ViewportRepresentation)
        self.assertTrue(viewport.cut_geometry)
        self.assertTrue(all(viewport.face_mesh_for(item) for item in viewport.cut_geometry))
        picked = ArchRepresentation.query_representation_pick(
            (viewport,),
            (1500, 0),
            lambda point: (point.x, point.y),
            1,
        )
        self.assertIsNotNone(picked)
        self.assertIs(picked.source, wall)
        self.assertEqual("WallViewportTop", picked.role)

        self._make_hosted_window(wall, "ModelFallbackWindow", 800, 500)
        fallback = ArchRepresentation.representation_for(wall, viewport_request)
        self.assertIsInstance(fallback, ArchRepresentation.PartShapeRepresentation)
        self.assertTrue(fallback.cut_geometry)

    def test_wall_model_representation_cache_separates_modes_and_invalidates(self):
        """Viewport and exact model results have distinct invalidatable keys."""

        from bimviews import representation_cache

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        exact_request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL
        )
        viewport_request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.MODEL,
            representation_mode=ArchRepresentation.RepresentationMode.VIEWPORT,
        )
        exact = ArchRepresentation.representation_for(wall, exact_request)
        viewport = ArchRepresentation.representation_for(wall, viewport_request)
        representation_cache.cache_representation(wall, exact_request, exact)
        representation_cache.cache_representation(wall, viewport_request, viewport)

        self.assertIs(exact, representation_cache.get_cached_representation(wall, exact_request))
        self.assertIs(
            viewport,
            representation_cache.get_cached_representation(wall, viewport_request),
        )
        representation_cache.invalidate_for_object_change(wall, "Width")
        self.assertIsNone(representation_cache.get_cached_representation(wall, exact_request))
        self.assertIsNone(representation_cache.get_cached_representation(wall, viewport_request))

    def test_wall_footprint_ignores_openings_above_cut_height(self):
        """Only openings intersecting the plan cut height should affect the wall footprint."""
        self.printTestMessage("Checking wall footprint ignores openings above cut height...")

        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(4000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=3000)
        self.document.recompute()

        low_window_width = 700.0
        low_window = self._make_hosted_window(
            wall,
            "LowFootprintWindow",
            x_start=700,
            z_start=700,
            width=low_window_width,
            height=1200.0,
        )
        high_window_width = 500.0
        high_window = self._make_hosted_window(
            wall,
            "HighFootprintWindow",
            x_start=2400,
            z_start=1800,
            width=high_window_width,
            height=700.0,
        )

        with patch.object(
            low_window.Proxy,
            "get_plan_overlay_geometry",
            side_effect=AssertionError("wall recipes must not consume Plan overlay geometry"),
        ), patch.object(
            high_window.Proxy,
            "get_plan_overlay_geometry",
            side_effect=AssertionError("wall recipes must not consume Plan overlay geometry"),
        ):
            footprint_faces = wall.Proxy.getFootprint(wall)
        self.assertEqual(
            len(footprint_faces),
            2,
            "Only the opening crossing the cut height should split the wall footprint.",
        )
        footprint_area = sum(face.Area for face in footprint_faces)
        expected_area = (wall.Length.Value - low_window_width) * wall.Width.Value
        self.assertAlmostEqual(
            footprint_area,
            expected_area,
            places=3,
            msg="Openings above the cut height must not remove area from the wall footprint.",
        )
        high_cut_request = ArchRepresentation.RepresentationRequest(
            purpose=ArchRepresentation.RepresentationPurpose.PLAN,
            cut_offset=2200.0,
            target_offset=wall.Shape.BoundBox.ZMin,
        )
        high_cut_faces = wall.Proxy.getPlanRepresentation(wall, high_cut_request)
        high_cut_area = sum(face.Area for face in high_cut_faces)
        expected_high_cut_area = (wall.Length.Value - high_window_width) * wall.Width.Value
        self.assertAlmostEqual(
            high_cut_area,
            expected_high_cut_area,
            places=3,
            msg="Explicit plan requests should drive wall plan representation height.",
        )

    def test_wall_batches_multiple_hosted_opening_subtractions(self):
        """Several hosted openings retain the expected exact wall solid."""

        wall_length = 5000.0
        wall_width = 200.0
        wall_height = 3000.0
        opening_width = 600.0
        opening_height = 1200.0
        line = Draft.makeLine(App.Vector(), App.Vector(wall_length, 0, 0))
        wall = Arch.makeWall(line, width=wall_width, height=wall_height)
        self.document.recompute()
        cut_tool_counts = []
        cut_tools = ArchComponent.Component._cut_subtraction_tools

        def record_cut_tools(base, tools):
            cut_tool_counts.append(len(tools))
            return cut_tools(base, tools)

        with patch.object(
            ArchComponent.Component,
            "_cut_subtraction_tools",
            side_effect=record_cut_tools,
        ), patch.object(ArchWallExact, "compile_straight_wall", return_value=None):
            for index, x_start in enumerate((500.0, 1800.0, 3100.0), start=1):
                self._make_hosted_window(
                    wall,
                    f"BatchOpening{index}",
                    x_start=x_start,
                    z_start=700.0,
                    width=opening_width,
                    height=opening_height,
                )
            wall.touch()
            self.document.recompute()

        self.assertIn(3, cut_tool_counts)
        self.assertTrue(wall.Shape.isValid())
        self.assertEqual(1, len(wall.Shape.Solids))
        expected_volume = wall_length * wall_width * wall_height - (
            3 * opening_width * wall_width * opening_height
        )
        self.assertAlmostEqual(expected_volume, wall.Shape.Volume, delta=1e-3)

    def test_exact_wall_compiler_matches_legacy_opening_shape(self):
        """Compiled window and floor-touching door openings match legacy geometry."""

        with patch.object(ArchWallExact, "compile_straight_wall", return_value=None):
            line = Draft.makeLine(App.Vector(), App.Vector(5000, 0, 0))
            wall = Arch.makeWall(line, width=200, height=3000)
            self.document.recompute()
            openings = (
                ("Window1", 700.0, 700.0, 1200.0),
                ("Window2", 2600.0, 700.0, 1200.0),
                ("Door", 4000.0, 0.0, 2100.0),
            )
            for name, x_start, z_start, height in openings:
                self._make_hosted_window(
                    wall,
                    f"ExactCompiler{name}",
                    x_start=x_start,
                    z_start=z_start,
                    width=600.0 if name == "Door" else 700.0,
                    height=height,
                )
            legacy_shape = wall.Shape.copy()

        compilation = ArchWallExact.compile_straight_wall(wall, wall.Proxy)
        self.assertIsNotNone(compilation)
        self.assertTrue(compilation.shape.isValid())
        self.assertAlmostEqual(legacy_shape.Volume, compilation.shape.Volume, delta=1e-3)
        legacy_bounds = legacy_shape.BoundBox
        compiled_bounds = compilation.shape.BoundBox
        for legacy, compiled in zip(
            (
                legacy_bounds.XMin,
                legacy_bounds.YMin,
                legacy_bounds.ZMin,
                legacy_bounds.XMax,
                legacy_bounds.YMax,
                legacy_bounds.ZMax,
            ),
            (
                compiled_bounds.XMin,
                compiled_bounds.YMin,
                compiled_bounds.ZMin,
                compiled_bounds.XMax,
                compiled_bounds.YMax,
                compiled_bounds.ZMax,
            ),
        ):
            self.assertAlmostEqual(legacy, compiled, delta=1e-6)
        legacy_section = ArchComponent.get_horizontal_slice_faces(legacy_shape, 1000)
        compiled_section = ArchComponent.get_horizontal_slice_faces(
            compilation.shape, 1000
        )
        self.assertAlmostEqual(
            sum(face.Area for face in legacy_section),
            sum(face.Area for face in compiled_section),
            delta=1e-3,
        )
        wall.touch()
        with patch.object(
            wall.Proxy, "processSubShapes", wraps=wall.Proxy.processSubShapes
        ) as legacy_subtractions:
            self.document.recompute()
        legacy_subtractions.assert_not_called()
        self.assertAlmostEqual(wall.Shape.Volume, legacy_shape.Volume, delta=1e-3)

    def test_wall_footprint_uses_parent_storey_plan_cut_height(self):
        """Parent storeys should define the absolute plan cut for contained walls."""
        self.printTestMessage("Checking wall footprint uses parent storey plan cut height...")

        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(4000, 0, 0))
        wall = Arch.makeWall(line, width=200, height=3000)
        storey = Arch.makeFloor(name="FootprintLevel")
        storey.LevelOffset = 1200
        storey.PlanCutHeight = 1500
        storey.addObject(wall)
        self.document.recompute()

        low_window_width = 500.0
        self._make_hosted_window(
            wall,
            "LowStoreyWindow",
            x_start=700,
            z_start=700,
            width=low_window_width,
            height=900.0,
        )
        high_window_width = 900.0
        self._make_hosted_window(
            wall,
            "HighStoreyWindow",
            x_start=2200,
            z_start=2200,
            width=high_window_width,
            height=700.0,
        )

        request = wall.Proxy.getDefaultPlanRequest(wall)
        self.assertAlmostEqual(
            request.cut_offset,
            2700.0,
            places=6,
            msg="Contained walls should derive their plan cut from the parent storey level.",
        )
        self.assertIs(
            request.source,
            storey,
            "The default wall plan context should record the parent storey source.",
        )
        footprint_faces = wall.Proxy.getFootprint(wall)
        self.assertEqual(
            len(footprint_faces),
            2,
            "Only the opening crossing the parent storey cut height should split the wall.",
        )
        footprint_area = sum(face.Area for face in footprint_faces)
        expected_area = (wall.Length.Value - high_window_width) * wall.Width.Value
        self.assertAlmostEqual(
            footprint_area,
            expected_area,
            places=3,
            msg="Parent storey plan cut height should override the default wall-base cut.",
        )

    def test_joinWalls(self):
        """Test the joinWalls function."""
        operation = "Testing joinWalls function"
        self.printTestMessage(operation)

        base_line1 = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(5000, 0, 0))
        base_line2 = Draft.makeLine(App.Vector(5000, 0, 0), App.Vector(5000, 3000, 0))
        wall1 = Arch.makeWall(base_line1, width=200, height=3000)
        wall2 = Arch.makeWall(base_line2, width=200, height=3000)
        joined_wall = Arch.joinWalls([wall1, wall2])
        self.assertIsNotNone(joined_wall, "joinWalls failed to join walls.")

    def test_remove_base_from_wall_without_host(self):
        """
        Tests that removing a debasable wall's base using removeComponents
        successfully unlinks the base.
        """
        self.printTestMessage("Testing removal of a wall's base component...")

        # 1. Arrange: Create a wall with a base
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(2000, 0, 0))
        # Ensure the base object's shape is computed, making the wall debasable.
        line.recompute()
        wall = Arch.makeWall(line)
        self.document.recompute()  # Ensure wall is fully formed
        self.assertIsNotNone(wall.Base, "Pre-condition failed: Wall should have a base.")
        self.assertTrue(
            Arch.is_debasable(wall), "Pre-condition failed: The test wall is not debasable."
        )

        # 2. Act: Call removeComponents on the base.
        # This will trigger the is_debasable -> True -> debaseWall() path.
        Arch.removeComponents([wall.Base])
        self.document.recompute()

        # 3. Assert: The base should now be None because debaseWall was successful.
        self.assertIsNone(wall.Base, "The wall's Base property was not cleared after removal.")

    def test_is_debasable_with_valid_line_base(self):
        """Tests that a wall based on a single Draft.Line is debasable."""
        self.printTestMessage("Checking is_debasable with Draft.Line...")
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(1000, 0, 0))
        line.recompute()
        wall = Arch.makeWall(line)
        self.document.recompute()
        self.assertTrue(Arch.is_debasable(wall), "Wall on Draft.Line should be debasable.")

    def test_is_debasable_with_valid_sketch_base(self):
        """Tests that a wall based on a Sketch with a single line is debasable."""
        self.printTestMessage("Checking is_debasable with single-line Sketch...")
        sketch = self.document.addObject("Sketcher::SketchObject", "SingleLineSketch")
        sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(1000, 0, 0)))
        self.document.recompute()
        wall = Arch.makeWall(sketch)
        self.assertTrue(Arch.is_debasable(wall), "Wall on single-line Sketch should be debasable.")

    def test_is_debasable_with_multi_edge_base(self):
        """Tests that a wall based on a multi-segment wire is not debasable."""
        self.printTestMessage("Checking is_debasable with multi-segment Wire...")
        wire = Draft.makeWire(
            [App.Vector(0, 0, 0), App.Vector(1000, 0, 0), App.Vector(1000, 1000, 0)]
        )
        wall = Arch.makeWall(wire)
        self.assertFalse(
            Arch.is_debasable(wall), "Wall on multi-segment wire should not be debasable."
        )

    def test_is_debasable_with_curved_base(self):
        """Tests that a wall based on an arc is not debasable."""
        self.printTestMessage("Checking is_debasable with curved base...")
        arc = Draft.make_circle(radius=500, startangle=0, endangle=90)
        self.document.recompute()
        wall = Arch.makeWall(arc)
        self.document.recompute()
        self.assertFalse(Arch.is_debasable(wall), "Wall on curved base should not be debasable.")

    def test_is_debasable_with_no_base(self):
        """Tests that a baseless wall is not debasable."""
        self.printTestMessage("Checking is_debasable with no base...")
        wall = Arch.makeWall(length=1000)
        self.assertFalse(Arch.is_debasable(wall), "Baseless wall should not be debasable.")

    def test_debase_wall_preserves_global_position(self):
        """
        Tests that debaseWall correctly transfers the base's placement to the
        wall, preserving its global position and dimensions.
        """
        self.printTestMessage("Checking debaseWall preserves global position...")

        # 1. Arrange: Create a rotated and translated line, and a wall from it.
        pl = App.Placement(App.Vector(1000, 500, 200), App.Rotation(App.Vector(0, 0, 1), 45))
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(2000, 0, 0))
        line.Placement = pl
        line.recompute()  # Use object-level recompute

        wall = Arch.makeWall(line, width=200, height=1500, align="Left")
        self.document.recompute()

        # Store the wall's original state
        original_bb = wall.Shape.BoundBox
        original_volume = wall.Shape.Volume
        original_length = wall.Length.Value

        # 2. Act: Debase the wall
        success = Arch.debaseWall(wall)
        self.document.recompute()

        # 3. Assert
        self.assertTrue(success, "debaseWall should return True for a valid wall.")
        self.assertIsNone(wall.Base, "Wall's Base should be None after debasing.")

        # Core assertions for preserving geometry and placement
        self.assertAlmostEqual(
            original_volume,
            wall.Shape.Volume,
            delta=1e-6,
            msg="Wall volume should not change after debasing.",
        )

        # Compare individual properties of the BoundBox with a tolerance
        final_bb = wall.Shape.BoundBox
        self.assertAlmostEqual(
            original_bb.XMin, final_bb.XMin, delta=1e-6, msg="Bounding box XMin does not match."
        )
        self.assertAlmostEqual(
            original_bb.XMax, final_bb.XMax, delta=1e-6, msg="Bounding box XMax does not match."
        )
        self.assertAlmostEqual(
            original_bb.YMin, final_bb.YMin, delta=1e-6, msg="Bounding box YMin does not match."
        )
        self.assertAlmostEqual(
            original_bb.YMax, final_bb.YMax, delta=1e-6, msg="Bounding box YMax does not match."
        )
        self.assertAlmostEqual(
            original_bb.ZMin, final_bb.ZMin, delta=1e-6, msg="Bounding box ZMin does not match."
        )
        self.assertAlmostEqual(
            original_bb.ZMax, final_bb.ZMax, delta=1e-6, msg="Bounding box ZMax does not match."
        )

        # Check parametric integrity
        self.assertAlmostEqual(
            wall.Length.Value,
            original_length,
            delta=1e-6,
            msg="Wall's Length property should be preserved.",
        )

        # Verify it remains parametric by changing a property
        wall.Height = 2000
        self.document.recompute()
        self.assertNotAlmostEqual(
            original_volume,
            wall.Shape.Volume,
            delta=1e-6,
            msg="Wall should remain parametric and its volume should change with height.",
        )

    def test_makeWall_baseless_alignment(self):
        """
        Tests that Arch.makeWall correctly creates a baseless wall with the
        specified alignment.
        """
        self.printTestMessage("Checking baseless wall alignment from makeWall...")

        # Define the test cases: (Alignment Mode, Expected final Y-center)
        test_cases = [
            ("Center", 0.0),
            ("Left", -100.0),
            ("Right", 100.0),
        ]

        for align_mode, expected_y_center in test_cases:
            with self.subTest(alignment=align_mode):
                # 1. Arrange & Act: Create a baseless wall using the API call.
                wall = Arch.makeWall(length=2000, width=200, height=1500, align=align_mode)
                self.document.recompute()

                # 2. Assert Geometry: Verify the shape is valid.
                self.assertFalse(
                    wall.Shape.isNull(), msg=f"[{align_mode}] Shape should not be null."
                )
                expected_volume = 2000 * 200 * 1500
                self.assertAlmostEqual(
                    wall.Shape.Volume,
                    expected_volume,
                    delta=1e-6,
                    msg=f"[{align_mode}] Wall volume is incorrect.",
                )

                # 3. Assert Placement and Alignment.
                # The wall's Placement should be at the origin.
                self.assertTrue(
                    wall.Placement.Base.isEqual(App.Vector(0, 0, 0), 1e-6),
                    msg=f"[{align_mode}] Default placement Base should be at the origin.",
                )
                self.assertAlmostEqual(
                    wall.Placement.Rotation.Angle,
                    0.0,
                    delta=1e-6,
                    msg=f"[{align_mode}] Default placement Rotation should be zero.",
                )

                # The shape's center should be offset according to the alignment.
                shape_center = wall.Shape.BoundBox.Center
                expected_center = App.Vector(0, expected_y_center, 750)

                self.assertTrue(
                    shape_center.isEqual(expected_center, 1e-5),
                    msg=f"For '{align_mode}' align, wall center {shape_center} does not match expected {expected_center}",
                )

    def test_baseless_wall_stretch_api(self):
        """
        Tests the proxy methods for graphically editing baseless walls:
        calc_endpoints() and set_from_endpoints().
        """
        self.printTestMessage("Checking baseless wall stretch API...")

        # 1. Arrange: Create a baseless wall and then set its placement.
        initial_placement = App.Placement(
            App.Vector(1000, 1000, 0), App.Rotation(App.Vector(0, 0, 1), 45)
        )
        # Create wall first, then set its placement.
        wall = Arch.makeWall(length=2000)
        wall.Placement = initial_placement
        self.document.recompute()

        # 2. Test calc_endpoints()
        endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertEqual(len(endpoints), 2, "calc_endpoints should return two points.")

        # Verify the calculated endpoints against manual calculation
        half_len_vec_x = App.Vector(1000, 0, 0)
        rotated_half_vec = initial_placement.Rotation.multVec(half_len_vec_x)
        expected_p1 = initial_placement.Base - rotated_half_vec
        expected_p2 = initial_placement.Base + rotated_half_vec

        self.assertTrue(endpoints[0].isEqual(expected_p1, 1e-6), "Start point is incorrect.")
        self.assertTrue(endpoints[1].isEqual(expected_p2, 1e-6), "End point is incorrect.")

        # 3. Test set_from_endpoints()
        new_p1 = App.Vector(0, 0, 0)
        new_p2 = App.Vector(4000, 0, 0)
        wall.Proxy.set_from_endpoints(wall, [new_p1, new_p2])
        self.document.recompute()

        # Assert that the wall's properties have been updated correctly
        self.assertAlmostEqual(
            wall.Length.Value, 4000.0, delta=1e-6, msg="Length was not updated correctly."
        )

        expected_center = App.Vector(2000, 0, 0)
        self.assertTrue(
            wall.Placement.Base.isEqual(expected_center, 1e-6),
            "Placement.Base (center) was not updated correctly.",
        )

        # Check rotation (should now be zero as the new points are on the X-axis)
        self.assertAlmostEqual(
            wall.Placement.Rotation.Angle,
            0.0,
            delta=1e-6,
            msg="Placement.Rotation was not updated correctly.",
        )

    def test_based_wall_stretch_api_debases_straight_wall(self):
        """Straight line base walls should join the endpoint-editing API."""
        self.printTestMessage("Checking based wall stretch API on straight base...")

        base = Draft.makeLine(App.Vector(100, 200, 0), App.Vector(2100, 200, 0))
        wall = Arch.makeWall(base, width=200, height=1500)
        self.document.recompute()

        wall.Proxy.set_from_endpoints(wall, [App.Vector(0, 0, 0), App.Vector(4000, 0, 0)])
        self.document.recompute()

        self.assertIsNone(wall.Base, "Straight base wall should debase on first endpoint edit.")
        self.assertAlmostEqual(wall.Length.Value, 4000.0, delta=1e-6)
        self.assertTrue(wall.Placement.Base.isEqual(App.Vector(2000, 0, 0), 1e-6))

    def test_based_wall_stretch_rejects_coincident_endpoints_without_mutation(self):
        """Invalid endpoint edits must not debase or otherwise change a wall."""
        base = Draft.makeLine(App.Vector(100, 200, 0), App.Vector(2100, 200, 0))
        wall = Arch.makeWall(base, width=200, height=1500)
        self.document.recompute()
        original_base = wall.Base
        original_length = wall.Length.Value
        original_placement = wall.Placement.copy()

        with self.assertRaises(ValueError):
            wall.Proxy.set_from_endpoints(wall, [App.Vector(0, 0, 0), App.Vector(0, 0, 0)])

        self.assertIs(wall.Base, original_base)
        self.assertAlmostEqual(wall.Length.Value, original_length, delta=1e-6)
        self.assertTrue(wall.Placement.Base.isEqual(original_placement.Base, 1e-6))

    def test_get_global_baseline_for_based_wall(self):
        """Tests that get_global_baseline returns based-wall geometry."""
        self.printTestMessage("Checking get_global_baseline for based walls...")

        line = Draft.makeLine(App.Vector(100, 200, 0), App.Vector(2100, 200, 0))
        self.document.recompute()
        wall = Arch.makeWall(line, width=200, height=1500)
        self.document.recompute()

        baseline = wall.Proxy.get_global_baseline(wall)
        self.assertIsNotNone(baseline, "Based wall baseline should not be None.")
        self.assertTrue(baseline.normal.isEqual(App.Vector(0, 0, 1), 1e-6))

        expected_start = line.Start
        expected_end = line.End
        self.assertTrue(
            baseline.start_point.isEqual(expected_start, 1e-6),
            "Baseline start point does not match the base shape.",
        )
        self.assertTrue(
            baseline.end_point.isEqual(expected_end, 1e-6),
            "Baseline end point does not match the base shape.",
        )

    def test_get_global_baseline_preserves_provider_orientation(self):
        """Draft lines and sketches define stable Start/End semantics."""
        line = Draft.makeLine(App.Vector(1000, 0, 0), App.Vector(0, 0, 0))
        wall_from_line = Arch.makeWall(line, width=200, height=1500)

        sketch = self.document.addObject("Sketcher::SketchObject", "ReversedWallSketch")
        sketch.addGeometry(Part.LineSegment(App.Vector(1000, 200, 0), App.Vector(0, 200, 0)))
        wall_from_sketch = Arch.makeWall(sketch, width=200, height=1500)
        self.document.recompute()

        line_baseline = wall_from_line.Proxy.get_global_baseline(wall_from_line)
        sketch_baseline = wall_from_sketch.Proxy.get_global_baseline(wall_from_sketch)
        self.assertTrue(line_baseline.start_point.isEqual(line.Start, 1e-6))
        self.assertTrue(line_baseline.end_point.isEqual(line.End, 1e-6))
        self.assertTrue(sketch_baseline.start_point.isEqual(App.Vector(1000, 200, 0), 1e-6))
        self.assertTrue(sketch_baseline.end_point.isEqual(App.Vector(0, 200, 0), 1e-6))

    def test_get_global_baseline_matches_transformed_wall_geometry(self):
        """Baseline coordinates include base, wall, and explicit normal transforms."""
        base_placement = App.Placement(
            App.Vector(100, 500, 20), App.Rotation(App.Vector(0, 0, 1), 45)
        )
        wall_placement = App.Placement(
            App.Vector(300, -200, 40), App.Rotation(App.Vector(0, 0, 1), 30)
        )
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(2000, 0, 0))
        line.Placement = base_placement
        wall = Arch.makeWall(line, width=200, height=1500)
        wall.Placement = wall_placement
        wall.Normal = App.Vector(0, 1, 1)
        self.document.recompute()

        baseline = wall.Proxy.get_global_baseline(wall)
        expected_start = wall_placement.multVec(line.Start)
        expected_end = wall_placement.multVec(line.End)
        expected_normal = wall_placement.Rotation.multVec(wall.Normal)
        expected_normal.normalize()
        self.assertTrue(baseline.start_point.isEqual(expected_start, 1e-6))
        self.assertTrue(baseline.end_point.isEqual(expected_end, 1e-6))
        self.assertTrue(baseline.normal.isEqual(expected_normal, 1e-6))
        expected_edge = Part.makeLine(expected_start, expected_end)
        self.assertAlmostEqual(wall.Shape.distToShape(expected_edge)[0], 0.0, delta=1e-6)
        self.assertTrue(wall.Shape.BoundBox.isValid())

    def test_get_global_baseline_preserves_orientation_after_round_trip(self):
        """Provider endpoint orientation survives document serialization."""
        line = Draft.makeLine(App.Vector(1000, 0, 0), App.Vector(0, 0, 0))
        wall = Arch.makeWall(line, width=200, height=1500)
        self.document.recompute()
        wall_name = wall.Name

        fd, path = tempfile.mkstemp(suffix=".FCStd")
        os.close(fd)
        try:
            document_name = self.document.Name
            self.document.saveAs(path)
            App.closeDocument(document_name)
            self.document = App.openDocument(path)
            self.document.recompute()
            restored_wall = self.document.getObject(wall_name)
            baseline = restored_wall.Proxy.get_global_baseline(restored_wall)
            self.assertTrue(baseline.start_point.isEqual(App.Vector(1000, 0, 0), 1e-6))
            self.assertTrue(baseline.end_point.isEqual(App.Vector(0, 0, 0), 1e-6))
        finally:
            if self.document:
                App.closeDocument(self.document.Name)
                self.document = None
            if os.path.exists(path):
                os.unlink(path)

    def test_get_global_baseline_rejects_unsupported_based_walls(self):
        """Multi-edge and curved wall bases are not join baselines."""
        wire = Draft.makeWire(
            [App.Vector(0, 0, 0), App.Vector(1000, 0, 0), App.Vector(1000, 1000, 0)]
        )
        self.document.recompute()
        wire_wall = Arch.makeWall(wire, width=200, height=1500)
        self.document.recompute()
        self.assertIsNone(wire_wall.Proxy.get_global_baseline(wire_wall))

        arc = Draft.make_circle(radius=500, startangle=0, endangle=90)
        self.document.recompute()
        curved_wall = Arch.makeWall(arc, width=200, height=1500)
        self.document.recompute()
        self.assertIsNone(curved_wall.Proxy.get_global_baseline(curved_wall))

    def test_resolved_section_matches_visible_shape_bounds(self):
        """Invisible material layers move the cursor but never become faces."""
        material_a = Arch.makeMaterial()
        material_b = Arch.makeMaterial()
        material = Arch.makeMultiMaterial()
        material.Materials = [material_a, material_b]
        material.Thicknesses = [100, -50]

        wall = Arch.makeWall(length=2000, width=150, height=1000, align="Center")
        wall.Material = material
        self.document.recompute()

        section = wall.Proxy.get_resolved_section(wall)
        self.assertEqual([layer.raw_thickness for layer in section.layers], [100, -50])
        self.assertAlmostEqual(wall.Shape.BoundBox.YMin, section.y_min, delta=1e-6)
        self.assertAlmostEqual(wall.Shape.BoundBox.YMax, section.y_max, delta=1e-6)

    def test_resolved_section_applies_wall_overrides_and_defaults(self):
        """Short overrides resolve each segment against the wall defaults."""
        wire = Draft.makeWire(
            [App.Vector(0, 0, 0), App.Vector(1000, 0, 0), App.Vector(1000, 1000, 0)]
        )
        wall = Arch.makeWall(wire, width=100, height=1000, align="Center", offset=10)
        wall.OverrideWidth = [300]
        wall.OverrideAlign = ["Left"]
        wall.OverrideOffset = [25]

        first = wall.Proxy.get_resolved_section(wall, segment_index=0)
        second = wall.Proxy.get_resolved_section(wall, segment_index=1)

        self.assertEqual([layer.raw_thickness for layer in first.layers], [300])
        self.assertEqual([layer.raw_thickness for layer in second.layers], [100])
        self.assertEqual(wall.Proxy.get_width(wall, widths=False), 100.0)
        self.assertEqual(wall.Proxy.get_width(wall), (100.0, [300]))

        self.document.recompute()
        section = wall.Proxy.get_resolved_section(wall)
        self.assertAlmostEqual(section.y_min, -325.0)
        self.assertAlmostEqual(section.y_max, -25.0)

        first_segment = wall.Shape.common(Part.makeBox(2, 2000, 1000, App.Vector(499, -1000, 0)))
        self.assertAlmostEqual(first_segment.BoundBox.YMin, section.y_min, delta=1e-6)
        self.assertAlmostEqual(first_segment.BoundBox.YMax, section.y_max, delta=1e-6)

        second_section = wall.Proxy.get_resolved_section(wall, segment_index=1)
        second_segment = wall.Shape.common(Part.makeBox(2000, 2, 1000, App.Vector(-500, 499, 0)))
        self.assertAlmostEqual(
            second_segment.BoundBox.XMin, 1000 + second_section.y_min, delta=1e-6
        )
        self.assertAlmostEqual(
            second_segment.BoundBox.XMax, 1000 + second_section.y_max, delta=1e-6
        )

    def test_resolved_material_layers_use_wall_width_for_all_segments(self):
        """Variable material layers use the wall width, not segment overrides."""
        wire = Draft.makeWire(
            [App.Vector(0, 0, 0), App.Vector(1000, 0, 0), App.Vector(1000, 1000, 0)]
        )
        material = Arch.makeMultiMaterial()
        material.Materials = [Arch.makeMaterial(), Arch.makeMaterial()]
        material.Thicknesses = [50, 0]
        wall = Arch.makeWall(wire, width=100, height=1000, align="Center")
        wall.Material = material
        wall.OverrideWidth = [300, 100]
        self.document.recompute()

        first = wall.Proxy.get_resolved_section(wall, segment_index=0)
        second = wall.Proxy.get_resolved_section(wall, segment_index=1)
        self.assertEqual([layer.raw_thickness for layer in first.layers], [50, 50])
        self.assertEqual([layer.raw_thickness for layer in second.layers], [50, 50])

        second_segment = wall.Shape.common(Part.makeBox(2000, 2, 1000, App.Vector(-500, 499, 0)))
        self.assertAlmostEqual(second_segment.BoundBox.XMin, 1000 + second.y_min, delta=1e-6)
        self.assertAlmostEqual(second_segment.BoundBox.XMax, 1000 + second.y_max, delta=1e-6)

    def test_resolved_section_rejects_invalid_alignment_values(self):
        """Invalid alignment sources fall back to wall.Align."""
        wall = Arch.makeWall(length=2000, width=100, height=1000, align="Center")
        wall.OverrideAlign = ["Bogus"]
        section = wall.Proxy.get_resolved_section(wall)
        self.assertAlmostEqual(section.y_min, -50.0)
        self.assertAlmostEqual(section.y_max, 50.0)

        class InvalidArchSketchProvider:
            Type = "ArchSketch"

            @staticmethod
            def getWidths(_obj, **_kwargs):
                return [100]

            @staticmethod
            def getAligns(_obj, **_kwargs):
                return ["Bogus"]

            @staticmethod
            def getOffsets(_obj, **_kwargs):
                return [0]

        base = self.document.addObject("Part::FeaturePython", "InvalidArchSketchBase")
        base.Proxy = InvalidArchSketchProvider()
        provider_wall = Arch.makeWall(length=2000, width=100, height=1000, align="Center")
        provider_wall.Base = base
        provider_wall.ArchSketchData = True
        provider_section = provider_wall.Proxy.get_resolved_section(provider_wall)
        self.assertAlmostEqual(provider_section.y_min, -50.0)
        self.assertAlmostEqual(provider_section.y_max, 50.0)

    def test_wall_ending_properties_trim_wall(self):
        """Tests that EndingStart/EndingEnd placements trim and restore a wall shape."""
        self.printTestMessage("Checking wall ending properties...")

        wall = Arch.makeWall(length=2000, width=200, height=1000)
        self.document.recompute()
        initial_volume = wall.Shape.Volume
        self.assertGreater(initial_volume, 0)

        wall.EndingEnd = App.Placement(
            App.Vector(1000, 0, 0),
            App.Rotation(App.Vector(0, 0, 1), 45) * App.Rotation(App.Vector(0, 1, 0), 90),
        )
        self.document.recompute()

        self.assertTrue(wall.Shape.isValid(), "Wall shape became invalid after trimming.")
        self.assertLess(wall.Shape.Volume, initial_volume)
        self.assertLess(wall.Shape.BoundBox.XMax, 1000.01)

        wall.EndingEnd = App.Placement()
        self.document.recompute()
        self.assertAlmostEqual(wall.Shape.Volume, initial_volume, delta=1e-6)

    def test_wall_end_condition_selector_orders_sources(self):
        """Tests that end-condition selection follows the configured order."""
        manual = ArchWallEndCondition.WallEndCondition(
            source="Manual",
            placement=App.Placement(App.Vector(100, 0, 0), App.Rotation()),
        )
        relation = ArchWallEndCondition.WallEndCondition(
            source="Relation",
            placement=App.Placement(App.Vector(200, 0, 0), App.Rotation()),
            is_global=True,
            extension=12.5,
        )

        order = ["Manual", "Relation", "Manual", "Bogus"]
        active = ArchWallEndCondition.select_end_condition([relation, manual], order)
        self.assertEqual(
            ArchWallEndCondition.normalize_end_condition_order(order), ["Manual", "Relation"]
        )
        self.assertEqual(active.source, "Manual")

        active = ArchWallEndCondition.select_end_condition(
            [relation, manual], ["Relation", "Manual"]
        )
        self.assertEqual(active.source, "Relation")
        self.assertTrue(active.is_global)
        self.assertAlmostEqual(active.extension, 12.5)

        inactive_relation = ArchWallEndCondition.WallEndCondition(source="Relation", extension=25.0)
        self.assertIs(
            ArchWallEndCondition.select_end_condition(
                [inactive_relation, manual], ["Relation", "Manual"]
            ),
            manual,
        )

    def test_wall_end_conditions_require_brep_export(self):
        """Walls with processed end planes must not use untrimmed IFC extrusions."""
        self.printTestMessage("Checking IFC representation selection for wall endings...")

        wall = Arch.makeWall(length=2000, width=200, height=1000)
        self.document.recompute()
        self.assertFalse(wall.Proxy.requires_brep_export(wall))
        self.assertTrue(wall.Proxy.isStandardCase(wall))

        wall.EndingEnd = App.Placement(
            App.Vector(1000, 0, 0),
            App.Rotation(App.Vector(0, 0, 1), 45) * App.Rotation(App.Vector(0, 1, 0), 90),
        )
        self.document.recompute()

        self.assertTrue(
            wall.Proxy.requires_brep_export(wall),
            "A wall with an active end condition must export its processed shape.",
        )
        self.assertFalse(
            wall.Proxy.isStandardCase(wall),
            "A BREP-exported wall must not be classified as IfcWallStandardCase.",
        )

        wall.EndingEnd = App.Placement()
        self.document.recompute()
        self.assertFalse(wall.Proxy.requires_brep_export(wall))
        self.assertTrue(wall.Proxy.isStandardCase(wall))

    def test_wall_end_condition_order_changes_active_trim(self):
        """Tests that the configured order changes which trim drives the wall end."""
        support_wall = Arch.makeWall(length=2000, width=200, height=1000)
        trimmed_wall = Arch.makeWall(length=1000, width=200, height=1000)
        trimmed_wall.Placement = App.Placement(
            App.Vector(1000, 500, 0),
            App.Rotation(App.Vector(1, 0, 0), App.Vector(0, 1, 0)),
        )
        self.document.recompute()

        joint = Arch.makeWallJoint(support_wall, trimmed_wall, "Butt")
        joint.ButtTrimmed = "WallB"
        support_wall.EndingEnd = App.Placement(
            App.Vector(600, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90)
        )
        self.document.recompute()
        joint_first_xmax = support_wall.Shape.BoundBox.XMax
        self.assertGreater(joint_first_xmax, 800.0)

        support_wall.EndConditionOrderEnd = ["Manual", "Relation"]
        self.document.recompute()
        self.assertAlmostEqual(support_wall.Shape.BoundBox.XMax, 600.0, delta=1e-4)

    def test_wall_makeblocks(self):
        """Test the 'MakeBlocks' feature for both based and baseless Arch Walls.
        This is a regression test for https://github.com/FreeCAD/FreeCAD/issues/26982,
        a unit test for https://github.com/FreeCAD/FreeCAD/issues/27817, and a basic, functional test for the
        MakeBlocks code path.
        """
        operation = "Checking Arch Wall MakeBlocks functional correctness..."
        self.printTestMessage(operation)

        # Block parameters
        L, H, W = 1000.0, 600.0, 200.0
        BL, BH = 400.0, 200.0  # Block Length and Height
        O1, O2 = 0.0, 200.0  # Row offsets

        def calc_row(row_start):
            """
            Simulates the 1D block-segmentation logic for a single horizontal course.

            This helper replicates the "sawing" algorithm found in _Wall._make_blocks:
            1. It places the first vertical joint at 'row_start'.
            2. It advances the cutting position by 'BlockLength' (BL).
            3. It measures the resulting segments between joints.
            4. It classifies segments equal to 'BL' as 'Entire' and any
               remainder (at the start or end of the row) as 'Broken'.

            Args:
                row_start (float): The distance from the start of the wall to the first vertical
                                   joint.

            Returns:
                tuple (int, int): A pair of integers (entire_count, broken_count)
                                  predicted for this specific row.
            """
            row_entire, row_broken = 0, 0
            current_pos = row_start
            last_pos = 0.0

            # Mimic the logic in ArchWall:
            # while offset < (Length - Joint): create cut at offset
            # Perform the cuts and record the resulting segments
            segments = []
            while current_pos < L:
                if current_pos > 0:
                    segments.append(current_pos - last_pos)
                    last_pos = current_pos
                current_pos += BL
            if last_pos < L:
                segments.append(L - last_pos)

            # Classify segments
            for seg_len in segments:
                if abs(seg_len - BL) < 0.1:  # Threshold for "Entire"
                    row_entire += 1
                else:
                    row_broken += 1
            return row_entire, row_broken

        # Calculate expectations based on total courses (rows)
        num_rows = int(H // BH)
        expected_entire = 0
        expected_broken = 0

        # Effectively "lay the bricks" in a running bond pattern: alternate offsets per even/odd row
        for r in range(num_rows):
            ent, brk = calc_row(O1 if r % 2 == 0 else O2)
            expected_entire += ent
            expected_broken += brk

        expected_vol = L * W * H

        # Create both wall variants: one with a base line, one baseless
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(L, 0, 0))
        self.document.recompute()
        based_wall = Arch.makeWall(line, width=W, height=H)
        baseless_wall = Arch.makeWall(None, length=L, width=W, height=H)

        walls = {"based": based_wall, "baseless": baseless_wall}
        for wall in walls.values():
            wall.BlockLength = BL
            wall.BlockHeight = BH
            wall.Joint = 0  # For test and volume calculation simplicity
            wall.OffsetFirst = O1
            wall.OffsetSecond = O2
            wall.MakeBlocks = True
        self.document.recompute()

        for label, wall in walls.items():
            with self.subTest(wall=label):
                # Regression check
                self.assertFalse(wall.Shape.isNull(), "Wall shape should not be null")

                # Functional check: block counts and volume correctness
                self.assertEqual(
                    wall.CountEntire,
                    expected_entire,
                    f"Mismatch in Entire blocks. Expected {expected_entire}, got {wall.CountEntire}",
                )
                self.assertEqual(
                    wall.CountBroken,
                    expected_broken,
                    f"Mismatch in Broken blocks. Expected {expected_broken}, got {wall.CountBroken}",
                )

                # Integrity check: volume correctness
                self.assertAlmostEqual(wall.Shape.Volume, expected_vol, places=3)

    def test_debase_wall_stationary_children(self):
        """Test that debasing a wall does not shift its children in world space."""
        self.printTestMessage("Arch.debaseWall stationary children...")

        # Create a base line offset by 5 meters for a clear distinction between local (0,0,0) and
        # global coordinates.
        # Line start/end: (5000,0,0) / (7000,0,0). Midpoint/new placement: (6000,0,0).
        line = Draft.makeLine(App.Vector(0, 0, 0), App.Vector(2000, 0, 0))
        line.Placement.Base = App.Vector(5000, 0, 0)
        self.document.recompute()

        # Create the wall. Initially, wall.Placement is (0,0,0).
        wall = Arch.makeWall(line, width=200, height=3000)
        self.document.recompute()

        # Create a set of different types of children, with different properties

        # Child A: a standard Part::Box primitive. Lacks MoveWithHost property. It should be handled
        # by the default move logic.
        box = self.document.addObject("Part::Box", "ChildBox")
        box.Placement.Base = App.Vector(5250, -150, 500)

        # Child B: an ArchComponent with MoveWithHost=True. This should be explicitly included in
        # the move logic.
        comp_true_base = self.document.addObject("Part::Box", "CompTrueBase")
        comp_true = Arch.makeComponent(comp_true_base, name="CompWithMove")
        comp_true.MoveWithHost = True
        comp_true.Placement.Base = App.Vector(5750, -150, 500)

        # Child C: an ArchComponent with MoveWithHost=False. This should be ignored by the move
        # logic.
        comp_false_base = self.document.addObject("Part::Box", "CompFalseBase")
        comp_false = Arch.makeComponent(comp_false_base, name="CompNoMove")
        comp_false.MoveWithHost = False
        comp_false.Placement.Base = App.Vector(6250, -150, 500)

        # Child D: a hosted Arch.Window. This is not an Addition but is found via InList by
        # getMovableChildren.
        win_base = Draft.makeRectangle(length=500, height=800)
        win_base.Placement.Rotation = App.Rotation(App.Vector(1, 0, 0), 90)  # Orient vertically
        win_base.Placement.Base = App.Vector(6500, 100, 1000)  # Position in wall center
        self.document.recompute()
        window = Arch.makeWindow(win_base)

        # Add all children/guests to the wall
        wall.Additions = [box, comp_true, comp_false]
        window.Hosts = [wall]
        self.document.recompute()

        # Record initial global placements for all children/hosts before debasing.
        initial_placements = {
            "Box": box.Placement.copy(),
            "CompTrue": comp_true.Placement.copy(),
            "CompFalse": comp_false.Placement.copy(),
            "Window": window.Placement.copy(),
        }

        # Perform the debase operation. This will reset wall.Placement from (0,0,0) to (6000,0,0)
        # and trigger the onChanged -> getMovableChildren -> move logic.
        Arch.debaseWall(wall)
        self.document.recompute()

        # All children must remain at their original global coordinates. Use subtests to get a clear
        # report for each child type.
        with self.subTest(child_type="Part Primitive (Box)"):
            self.assertTrue(
                box.Placement.Base.isEqual(initial_placements["Box"].Base, 1e-6),
                f"Part Primitive Box position shifted! Expected {initial_placements['Box'].Base}, got {box.Placement.Base}",
            )

        with self.subTest(child_type="ArchComponent (MoveWithHost=True)"):
            self.assertTrue(
                comp_true.Placement.Base.isEqual(initial_placements["CompTrue"].Base, 1e-6),
                f"Component with MoveWithHost=True position shifted! Expected {initial_placements['CompTrue'].Base}, got {comp_true.Placement.Base}",
            )

        with self.subTest(child_type="ArchComponent (MoveWithHost=False)"):
            self.assertTrue(
                comp_false.Placement.Base.isEqual(initial_placements["CompFalse"].Base, 1e-6),
                f"Component with MoveWithHost=False position shifted! Expected {initial_placements['CompFalse'].Base}, got {comp_false.Placement.Base}",
            )

        with self.subTest(child_type="Hosted Window"):
            self.assertTrue(
                window.Placement.Base.isEqual(initial_placements["Window"].Base, 1e-6),
                f"Hosted Window position shifted! Expected {initial_placements['Window'].Base}, got {window.Placement.Base}",
            )

        # Final verification that the wall itself was correctly debased
        self.assertIsNone(wall.Base, "Wall was not successfully debased (Base still exists).")
        self.assertAlmostEqual(wall.Placement.Base.x, 6000.0, places=3)

    def test_baseless_wall_offset(self):
        """Test that the Offset property shifts the geometry of a baseless wall.

        Regression test for https://github.com/FreeCAD/FreeCAD/issues/29256.
        """
        self.printTestMessage("Checking baseless wall Offset property...")

        length, width, height, offset = 2000.0, 200.0, 3000.0, 1000.0

        # Left alignment: wall body is in -Y direction. Offset shifts it further in -Y.
        wall_left = Arch.makeWall(
            length=length, width=width, height=height, align="Left", offset=offset
        )
        self.assertIsNone(wall_left.Base, "Left: wall should be baseless")
        self.document.recompute()
        bb = wall_left.Shape.BoundBox
        self.assertAlmostEqual(bb.YMax, -offset, delta=1e-6, msg="Left: YMax should be -offset")
        self.assertAlmostEqual(
            bb.YMin, -width - offset, delta=1e-6, msg="Left: YMin should be -(width+offset)"
        )

        # Right alignment: wall body is in +Y direction. Offset shifts it further in +Y.
        wall_right = Arch.makeWall(
            length=length, width=width, height=height, align="Right", offset=offset
        )
        self.assertIsNone(wall_right.Base, "Right: wall should be baseless")
        self.document.recompute()
        bb = wall_right.Shape.BoundBox
        self.assertAlmostEqual(bb.YMin, offset, delta=1e-6, msg="Right: YMin should be offset")
        self.assertAlmostEqual(
            bb.YMax, width + offset, delta=1e-6, msg="Right: YMax should be width+offset"
        )
