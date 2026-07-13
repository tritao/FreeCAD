# SPDX-License-Identifier: LGPL-2.1-or-later

"""Headless architectural contract tests for plan representations."""

import Arch
import ArchPlanRepresentation
import FreeCAD
import Part

from bimtests import TestArchBase


class TestArchPlanRepresentation(TestArchBase.TestArchBase):

    def test_wall_representation_is_headless_and_independent_of_display_mode(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        view_object = wall.ViewObject
        if view_object is not None:
            view_object.Visibility = False

        representation = ArchPlanRepresentation.get_plan_representation(wall)

        self.assertFalse(representation.isEmpty)
        self.assertIs(representation, ArchPlanRepresentation.get_plan_representation(wall))
        self.assertEqual(representation.faces, tuple(wall.Proxy.getFootprint(wall)))
        self.assertGreater(len(representation.edges), 0)
        self.assertIs(
            representation.edges,
            ArchPlanRepresentation.get_plan_representation(wall).edges,
        )

    def test_different_contexts_have_distinct_cached_representations(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        low_context = ArchPlanRepresentation.PlanContext(cut_z=500, target_z=10)
        high_context = ArchPlanRepresentation.PlanContext(cut_z=1500, target_z=42)
        low = ArchPlanRepresentation.get_plan_representation(wall, low_context)
        high = ArchPlanRepresentation.get_plan_representation(wall, high_context)

        self.assertIsNot(low, high)
        self.assertEqual(low.context.signature(), low_context.signature())
        self.assertEqual(high.context.signature(), high_context.signature())
        self.assertAlmostEqual(low.faces[0].BoundBox.ZMin, 10.0, places=6)
        self.assertAlmostEqual(high.faces[0].BoundBox.ZMin, 42.0, places=6)

    def test_invalid_and_unsupported_objects_return_empty_representations(self):
        unsupported = self.document.addObject("Part::Feature", "Unsupported")
        unsupported.Shape = Part.makeBox(10, 10, 10)
        invalid = self.document.addObject("Part::Feature", "Invalid")
        invalid.Shape = Part.Shape()

        unsupported_representation = ArchPlanRepresentation.get_plan_representation(unsupported)
        invalid_representation = ArchPlanRepresentation.get_plan_representation(invalid)

        self.assertTrue(unsupported_representation.isEmpty)
        self.assertTrue(invalid_representation.isEmpty)
        self.assertEqual(unsupported_representation.faces, ())
        self.assertEqual(invalid_representation.edges, ())

    def test_storey_context_change_replaces_neutral_cache(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        storey = Arch.makeFloor(name="PlanRepresentationStorey")
        storey.addObject(wall)
        storey.PlanCutHeight = 500
        self.document.recompute()

        first = ArchPlanRepresentation.get_plan_representation(wall)
        storey.PlanCutHeight = 1800
        self.document.recompute()
        second = ArchPlanRepresentation.get_plan_representation(wall)

        self.assertIsNot(first, second)
        self.assertIs(second, ArchPlanRepresentation.get_plan_representation(wall))
        self.assertIs(second.context.source, storey)
        self.assertAlmostEqual(second.context.cut_z, 1800.0, places=6)

    def test_context_cache_is_bounded(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        for cut_z in (500, 1000, 1500):
            context = ArchPlanRepresentation.PlanContext(cut_z=cut_z, target_z=0)
            ArchPlanRepresentation.get_plan_representation(wall, context)

        self.assertEqual(
            len(wall.Proxy._arch_plan_representation_cache),
            ArchPlanRepresentation.MAX_CACHED_PLAN_REPRESENTATIONS,
        )

    def test_transformed_object_returns_document_coordinates(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Placement = FreeCAD.Placement(FreeCAD.Vector(1200, 3400, 700), FreeCAD.Rotation())
        self.document.recompute()

        context = ArchPlanRepresentation.PlanContext(cut_z=1700, target_z=700)
        representation = ArchPlanRepresentation.get_plan_representation(wall, context)

        self.assertFalse(representation.isEmpty)
        source_box = wall.Shape.BoundBox
        self.assertAlmostEqual(representation.faces[0].BoundBox.XMin, source_box.XMin, places=6)
        self.assertAlmostEqual(representation.faces[0].BoundBox.YMin, source_box.YMin, places=6)
        self.assertAlmostEqual(representation.faces[0].BoundBox.ZMin, 700.0, places=6)
