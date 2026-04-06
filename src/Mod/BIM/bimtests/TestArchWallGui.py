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

"""GUI tests for the ArchWall module."""

import FreeCAD
import FreeCADGui
import Draft
import Arch
import Part
import WorkingPlane
import importlib
from bimtests import TestArchBaseGui
from bimcommands import BimPlanSession
from unittest.mock import patch


class MockTracker:
    """A dummy tracker to absorb GUI calls during logic tests."""

    def __init__(self):
        self.last_points = None
        self._width = None
        self._height = None

    def off(self):
        pass

    def on(self):
        pass

    def finalize(self):
        pass

    def update(self, points):
        self.last_points = points

    def setorigin(self, arg):
        pass

    def width(self, value=None):
        if value is not None:
            self._width = value
        return self._width

    def height(self, value=None):
        if value is not None:
            self._height = value
        return self._height


def current_arch_wall_class():
    return importlib.import_module("bimcommands.BimWall").Arch_Wall


class TestArchWallGui(TestArchBaseGui.TestArchBaseGui):

    def setUp(self):
        """Set up the test environment by activating the BIM workbench and setting preferences."""
        super().setUp()
        self.params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        self.original_wall_base = self.params.GetInt("WallBaseline", 1)  # Default to 1 (line)

    def tearDown(self):
        """Restore original preferences after the test."""
        session = BimPlanSession.get_active_session()
        if session:
            session.shutdown(close_dialog=False, teardown=True)
        self.params.SetInt("WallBaseline", self.original_wall_base)
        super().tearDown()

    def assertPlaneIsSaneTop(self, plane):
        self.assertIsNotNone(plane, "Expected an interaction plane.")
        self.assertAlmostEqual(plane.u.x, 1.0, delta=1e-9)
        self.assertAlmostEqual(plane.u.y, 0.0, delta=1e-9)
        self.assertAlmostEqual(plane.u.z, 0.0, delta=1e-9)
        self.assertAlmostEqual(plane.v.x, 0.0, delta=1e-9)
        self.assertAlmostEqual(plane.v.y, 1.0, delta=1e-9)
        self.assertAlmostEqual(plane.v.z, 0.0, delta=1e-9)
        self.assertAlmostEqual(plane.axis.x, 0.0, delta=1e-9)
        self.assertAlmostEqual(plane.axis.y, 0.0, delta=1e-9)
        self.assertAlmostEqual(plane.axis.z, 1.0, delta=1e-9)

    def _make_hosted_door(self, wall, name="TestDoor", width=900.0, height=2100.0):
        sketch = self.document.addObject("Sketcher::SketchObject", name + "Sketch")
        sketch.addGeometry(
            [
                Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(width, 0, 0)),
                Part.LineSegment(FreeCAD.Vector(width, 0, 0), FreeCAD.Vector(width, height, 0)),
                Part.LineSegment(FreeCAD.Vector(width, height, 0), FreeCAD.Vector(0, height, 0)),
                Part.LineSegment(FreeCAD.Vector(0, height, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )
        sketch.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90)
        self.document.recompute()

        door = Arch.makeWindow(sketch, name=name)
        door.Width = width
        door.Height = height
        door.HoleDepth = 0
        door.IfcType = "Door"
        door.WindowParts = ["DoorLeaf", "Solid panel", "Wire0,Edge1,Mode1", "40", "0"]
        self.document.recompute()

        Arch.addComponents(door, wall)
        self.document.recompute()
        return door

    def test_plan_edit_embedded_wall_uses_sane_top_plane(self):
        """Embedded wall creation in Plan Edit should start from a clean top plane."""

        self.params.SetInt("WallBaseline", 0)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session.activate_wall_tool()
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Wall")
        self.assertIsNotNone(session._embedded_tool, "Wall tool should be embedded in Plan Edit.")
        self.assertIsInstance(session._embedded_tool, current_arch_wall_class())

        self.assertPlaneIsSaneTop(session.get_interaction_plane())
        self.assertPlaneIsSaneTop(session._embedded_tool._plane)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_embedded_wall_first_update_stays_sane(self):
        """The first embedded wall preview update in Plan Edit should stay bounded."""

        self.params.SetInt("WallBaseline", 0)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session.activate_wall_tool()
        self.pump_gui_events()

        cmd = session._embedded_tool
        self.assertIsInstance(cmd, current_arch_wall_class())

        cmd.tracker = MockTracker()
        first = FreeCAD.Vector(1000, 1000, 0)
        second = FreeCAD.Vector(3000, 1000, 0)

        cmd.getPoint(first)
        self.assertEqual(len(cmd.points), 1)

        self.assertTrue(
            FreeCADGui.Control.activeDialog(),
            "Embedded wall point picking should open a live Draft dialog.",
        )
        cmd.update(second, None)

        self.assertPlaneIsSaneTop(cmd._plane)
        self.assertIsNotNone(cmd.tracker.last_points, "Expected a preview update on the tracker.")
        self.assertEqual(len(cmd.tracker.last_points), 2)
        for point in cmd.tracker.last_points:
            self.assertLess(abs(point.x), 1e6)
            self.assertLess(abs(point.y), 1e6)
            self.assertLess(abs(point.z), 1e6)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_rect_wall_tool_creates_four_walls(self):
        """Plan Edit should create a rectangular run as four baseless walls."""

        level = Arch.makeFloor(name="Level 0")
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}
        session.activate_rect_wall_tool()
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Rect Wall")

        session._handle_rect_wall_point(FreeCAD.Vector(0, 0, 0))
        session._handle_rect_wall_point(FreeCAD.Vector(3000, 2000, 0))
        self.pump_gui_events()

        created = [obj for obj in self.document.Objects if obj.Name not in before]
        walls = [obj for obj in created if Draft.getType(obj) == "Wall"]
        self.assertEqual(len(walls), 4, "Expected exactly four walls from a rectangular run.")
        for wall in walls:
            self.assertIn(level, wall.InListRecursive)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_rect_wall_tool_autojoins_closed_run(self):
        """Rectangular wall runs should autojoin as one closed addition host when enabled."""

        arch_params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Arch")
        original_autojoin = arch_params.GetBool("autoJoinWalls", False)

        try:
            arch_params.SetBool("autoJoinWalls", True)
            level = Arch.makeFloor(name="Level 0")
            self.document.recompute()

            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(level)

            session = BimPlanSession.start_session()
            self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
            self.pump_gui_events()

            before = {obj.Name for obj in self.document.Objects}
            session.activate_rect_wall_tool()
            self.pump_gui_events()

            session._handle_rect_wall_point(FreeCAD.Vector(0, 0, 0))
            session._handle_rect_wall_point(FreeCAD.Vector(3000, 2000, 0))
            self.pump_gui_events()

            created = [obj for obj in self.document.Objects if obj.Name not in before]
            walls = [obj for obj in created if Draft.getType(obj) == "Wall"]
            self.assertEqual(len(walls), 4)
            self.assertEqual(sum(len(wall.Additions) for wall in walls), 3)

            session.shutdown(close_dialog=False)
            self.pump_gui_events()
        finally:
            arch_params.SetBool("autoJoinWalls", original_autojoin)

    def test_plan_edit_hides_joined_wall_additions(self):
        """Joined child walls should stay hidden so their footprints do not overdraw the host."""

        host = Arch.makeWall(length=3000, width=200, height=2500)
        child = Arch.makeWall(length=3000, width=200, height=2500)
        Arch.addComponents(child, host)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(host.ViewObject.Visibility)
        self.assertFalse(
            child.ViewObject.Visibility,
            "Joined child walls should stay hidden in Plan Edit to avoid double rendering.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_slabs_visible_but_not_selectable(self):
        """Active-storey slabs should not block wall picking in Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)

        rect = Draft.makeRectangle(6000, 6000)
        slab = Arch.makeStructure(rect, height=200, name="TestSlab")
        slab.IfcType = "Slab"

        level.addObject(wall)
        level.addObject(slab)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(wall.ViewObject.Selectable)
        self.assertTrue(slab.ViewObject.Visibility)
        self.assertFalse(
            slab.ViewObject.Selectable,
            "Slabs should stay visible as background context but not intercept selection.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_global_mode_keeps_slabs_not_selectable(self):
        """Global plan mode should still treat slabs as non-selectable background."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)

        rect = Draft.makeRectangle(6000, 6000)
        slab = Arch.makeStructure(rect, height=200, name="TestSlab")
        slab.IfcType = "Slab"

        self.document.recompute()

        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertIsNone(session.active_storey)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertTrue(slab.ViewObject.Visibility)
        self.assertFalse(
            slab.ViewObject.Selectable,
            "Slabs should stay unselectable even when Plan Edit is in Global XY mode.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_global_mode_hides_unsupported_objects(self):
        """Global plan mode should hide unsupported objects instead of restoring them as-is."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        box = self.document.addObject("Part::Box", "TestBox")
        box.Length = 600
        box.Width = 600
        box.Height = 600

        self.document.recompute()

        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertIsNone(session.active_storey)
        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertFalse(box.ViewObject.Visibility)
        self.assertFalse(box.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hides_unsupported_active_storey_objects(self):
        """Unsupported active-storey objects should not clutter Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        box = self.document.addObject("Part::Box", "TestBox")
        box.Length = 600
        box.Width = 600
        box.Height = 600

        level.addObject(wall)
        level.addObject(box)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertFalse(
            box.ViewObject.Visibility,
            "Unsupported active-storey objects should be hidden in Plan Edit.",
        )
        self.assertFalse(box.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hides_unsupported_objects_outside_active_storey(self):
        """Unsupported objects with no storey ancestry should also be hidden."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        box = self.document.addObject("Part::Box", "TestBox")
        box.Length = 600
        box.Width = 600
        box.Height = 600

        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)
        self.assertFalse(
            box.ViewObject.Visibility,
            "Unsupported objects outside the active storey should be hidden in Plan Edit.",
        )
        self.assertFalse(box.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_building_visible_but_not_selectable(self):
        """Building containers should stay visible as context, but not intercept selection."""

        building = Arch.makeBuilding(name="TestBuilding")
        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)

        building.addObject(level)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(building.ViewObject.Visibility)
        self.assertFalse(building.ViewObject.Selectable)
        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_keeps_plain_groups_visible_but_not_selectable(self):
        """Generic group containers should stay visible as context in Plan Edit."""

        group = self.document.addObject("App::DocumentObjectGroup", "TestGroup")
        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)

        group.addObject(level)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(group.ViewObject.Visibility)
        self.assertFalse(group.ViewObject.Selectable)
        self.assertTrue(wall.ViewObject.Visibility)
        self.assertTrue(wall.ViewObject.Selectable)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_forces_hosted_doors_visible(self):
        """Hosted doors should become visible in Plan Edit even if the regular 3D view keeps them hidden."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall)
        self.assertFalse(
            door.ViewObject.Visibility,
            "Hosted doors should start hidden in the normal Arch workflow for this regression.",
        )

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Visibility)
        self.assertTrue(door.ViewObject.Selectable)
        self.assertTrue(hasattr(door.ViewObject.Proxy, "lcoords"))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hosted_door_populates_footprint_lines(self):
        """Hosted doors should have committed footprint line data while Plan Edit is active."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="PlanDoor")
        self.assertFalse(door.ViewObject.Visibility)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = door.ViewObject.Proxy
        self.assertTrue(door.ViewObject.Visibility)
        self.assertTrue(door.ViewObject.Selectable)
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

    def test_plan_edit_selecting_hosted_door_does_not_enable_wall_grips(self):
        """Hosted opening selection should not re-enter wall endpoint edit mode."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="SelectableDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Selectable)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        self.assertIs(session.selected_opening, door)
        self.assertIsNone(session.selected_wall)
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

    def test_plan_edit_can_flip_selected_door_hinge(self):
        """Selected door handles should expose hinge flipping in Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="FlipDoor")
        original_parts = list(door.WindowParts)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        session._activate_opening_handle(door, 1)
        self.pump_gui_events()

        self.assertNotEqual(original_parts, list(door.WindowParts))

    def test_plan_edit_shows_grips_for_straight_base_wall(self):
        """Straight base-driven walls should get the same grip overlays as baseless walls."""

        base = Draft.make_line(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(3000, 0, 0))
        wall = Arch.makeWall(base, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        self.assertTrue(session.is_selected_wall_endpoint_editable())
        self.assertEqual(len(session._grip_trackers), 3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clears_selected_wall_when_host_shape_changes(self):
        """Selected wall grips should be cleared if a hosted opening changes the wall shape."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        self.pump_gui_events()
        self.assertIs(session.selected_wall, wall)
        self.assertGreater(len(session._grip_trackers), 0)

        self._make_hosted_door(wall, name="ResetDoor")
        self.pump_gui_events()

        self.assertIsNone(session.selected_wall)
        self.assertEqual(len(session._grip_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_create_baseless_wall_interactive_mode(self):
        """
        Tests the interactive creation of a baseless wall by simulating the
        Arch_Wall command's internal logic.
        """
        from draftguitools import gui_trackers  # Import the tracker module

        self.printTestMessage("Testing interactive creation of a baseless wall...")

        # 1. Arrange: Set preference to "No baseline" mode
        self.params.SetInt("WallBaseline", 0)

        # 2. Arrange: Simulate the state of the command after two clicks
        cmd = current_arch_wall_class()()
        cmd.doc = self.document
        cmd.wp = WorkingPlane.get_working_plane()
        cmd.points = [FreeCAD.Vector(1000, 1000, 0), FreeCAD.Vector(3000, 1000, 0)]
        cmd.Align = "Center"
        cmd.Width = 200.0
        cmd.Height = 2500.0
        cmd.MultiMat = None
        cmd.existing = []
        cmd.tracker = gui_trackers.boxTracker()

        initial_object_count = len(self.document.Objects)

        # 3. Act: Call the internal method that processes the points
        cmd.create_wall()

        # 4. Assert
        self.assertEqual(
            len(self.document.Objects),
            initial_object_count + 1,
            "Exactly one new object should have been created.",
        )

        wall = self.document.Objects[-1]
        self.assertEqual(Draft.get_type(wall), "Wall", "The created object is not a wall.")

        self.assertIsNone(wall.Base, "A baseless wall should have its Base property set to None.")

        self.assertAlmostEqual(
            wall.Length.Value, 2000.0, delta=1e-6, msg="Wall length is incorrect."
        )

        # Verify the placement is correct
        expected_center = FreeCAD.Vector(2000, 1000, 0)
        self.assertTrue(
            wall.Placement.Base.isEqual(expected_center, 1e-6),
            f"Wall center {wall.Placement.Base} does not match expected {expected_center}",
        )

        # Verify the rotation is correct (aligned with global X-axis, so no rotation)
        self.assertAlmostEqual(
            wall.Placement.Rotation.Angle,
            0.0,
            delta=1e-6,
            msg="Wall rotation should be zero for a horizontal line.",
        )

    def test_create_draft_line_baseline_wall_interactive(self):
        """Tests the interactive creation of a wall with a Draft.Line baseline."""
        from draftguitools import gui_trackers

        self.printTestMessage("Testing interactive creation of a Draft.Line based wall...")

        # 1. Arrange: Set preference to "Draft line" mode
        self.params.SetInt("WallBaseline", 1)  # Corresponds to WallBaselineMode.DRAFT_LINE

        cmd = current_arch_wall_class()()
        cmd.doc = self.document
        cmd.wp = WorkingPlane.get_working_plane()
        cmd.points = [FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(2000, 0, 0)]
        cmd.Align = "Center"
        cmd.Width = 200.0
        cmd.Height = 2500.0
        cmd.MultiMat = None
        cmd.existing = []
        cmd.tracker = gui_trackers.boxTracker()

        initial_object_count = len(self.document.Objects)

        # 2. Act
        cmd.create_wall()

        # 3. Assert
        self.assertEqual(
            len(self.document.Objects),
            initial_object_count + 2,
            "Should have created a Wall and a Draft Line.",
        )

        # The wall is created after the base, so it's the last object
        wall = self.document.Objects[-1]
        base = self.document.Objects[-2]

        self.assertEqual(Draft.get_type(wall), "Wall")
        self.assertEqual(Draft.get_type(base), "Wire")
        self.assertEqual(wall.Base, base, "The wall's Base should be the newly created line.")

    def test_create_sketch_baseline_wall_interactive(self):
        """Tests the interactive creation of a wall with a Sketch baseline."""
        from draftguitools import gui_trackers

        self.printTestMessage("Testing interactive creation of a Sketch based wall...")

        # 1. Arrange: Set preference to "Sketch" mode
        self.params.SetInt("WallBaseline", 2)  # Corresponds to WallBaselineMode.SKETCH

        cmd = current_arch_wall_class()()
        cmd.doc = self.document
        cmd.wp = WorkingPlane.get_working_plane()
        cmd.points = [FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(2000, 0, 0)]
        cmd.Align = "Center"
        cmd.Width = 200.0
        cmd.Height = 2500.0
        cmd.MultiMat = None
        cmd.existing = []
        cmd.tracker = gui_trackers.boxTracker()

        initial_object_count = len(self.document.Objects)

        # 2. Act
        cmd.create_wall()

        # 3. Assert
        self.assertEqual(
            len(self.document.Objects),
            initial_object_count + 2,
            "Should have created a Wall and a Sketch.",
        )

        wall = self.document.Objects[-1]
        base = self.document.Objects[-2]

        self.assertEqual(Draft.get_type(wall), "Wall")
        self.assertEqual(base.TypeId, "Sketcher::SketchObject")
        self.assertEqual(wall.Base, base, "The wall's Base should be the newly created sketch.")

    def test_stretch_rotated_baseless_wall(self):
        """Tests that the Draft_Stretch tool correctly handles a rotated baseless wall."""
        self.printTestMessage("Testing stretch on a rotated baseless wall...")

        from draftguitools.gui_stretch import Stretch

        # 1. Arrange: Create a rotated baseless wall
        wall = Arch.makeWall(length=2000, width=200, height=1500)

        rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 45)
        placement = FreeCAD.Placement(FreeCAD.Vector(1000, 1000, 0), rotation)
        wall.Placement = placement
        self.document.recompute()

        # Ensure the view is scaled to the object so selection logic works correctly
        FreeCADGui.ActiveDocument.ActiveView.fitAll()

        # Get initial state for assertion later
        initial_endpoints = wall.Proxy.calc_endpoints(wall)
        p_start_initial = initial_endpoints[0]
        p_end_initial = initial_endpoints[1]

        # 2. Act: Simulate the Stretch command
        cmd = Stretch()
        cmd.doc = self.document
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)

        # Activate the command. It will detect the existing selection and
        # call proceed() internally after performing necessary setup.
        cmd.Activated()

        # Simulate user clicks:
        # Define a selection rectangle that encloses only the end point
        cmd.addPoint(FreeCAD.Vector(p_end_initial.x - 1, p_end_initial.y - 1, 0))
        cmd.addPoint(FreeCAD.Vector(p_end_initial.x + 1, p_end_initial.y + 1, 0))

        # Manually inject the selection state to bypass the view-dependent tracker,
        # which acts inconsistently in a headless test environment.
        # [False, True] selects the end point while keeping the start point anchored.
        cmd.ops = [[wall, [False, True]]]

        # Define the displacement vector
        displacement_vector = FreeCAD.Vector(500, -500, 0)
        cmd.addPoint(FreeCAD.Vector(0, 0, 0))  # Start of displacement
        cmd.addPoint(displacement_vector)  # End of displacement

        # Allow the GUI command's macro to be processed
        self.pump_gui_events()

        # 3. Assert: Verify the new position of the endpoints
        final_endpoints = wall.Proxy.calc_endpoints(wall)
        p_start_final = final_endpoints[0]
        p_end_final = final_endpoints[1]

        # Calculate the error vector for diagnosis
        diff = p_start_final.sub(p_start_initial)

        error_message = (
            f"\nThe unselected start point moved!\n"
            f"Initial:  {p_start_initial}\n"
            f"Final:    {p_start_final}\n"
            f"Diff Vec: {diff}\n"
            f"Error Mag: {diff.Length:.12f}"
        )

        # The start point should not have moved
        self.assertTrue(p_start_final.isEqual(p_start_initial, 1e-6), error_message)

        # The end point should have moved by the global displacement vector
        expected_end_point = p_end_initial.add(displacement_vector)
        self.assertTrue(
            p_end_final.isEqual(expected_end_point, 1e-6),
            f"Stretched endpoint {p_end_final} does not match expected {expected_end_point}",
        )

    def test_create_baseless_wall_on_rotated_working_plane(self):
        """Tests that a baseless wall respects the current working plane."""
        import Part

        self.printTestMessage("Testing baseless wall creation on a rotated working plane...")

        # Arrange: Create a non-standard working plane (rotated and elevated)
        wp = WorkingPlane.get_working_plane()
        placement = FreeCAD.Placement(
            FreeCAD.Vector(0, 0, 1000), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 45)
        )

        # Apply the placement to the working plane, ensuring translation is included
        wp.align_to_placement(placement)

        # Define points in the local coordinate system of the working plane
        p1_local = FreeCAD.Vector(0, 0, 0)
        p2_local = FreeCAD.Vector(2000, 0, 0)

        # Convert local points to the global coordinates the command will receive
        p1_global = wp.get_global_coords(p1_local)
        p2_global = wp.get_global_coords(p2_local)

        self.params.SetInt("WallBaseline", 0)

        cmd = current_arch_wall_class()()
        cmd.doc = self.document
        cmd.wp = wp
        cmd.points = [p1_global, p2_global]
        cmd.Align = "Center"
        cmd.Width = 200.0
        cmd.Height = 1500.0
        cmd.MultiMat = None

        # Use a mock tracker to isolate logic tests from the 3D view environment
        cmd.tracker = MockTracker()
        cmd.existing = []

        # Act
        cmd.create_wall()

        # Assert
        wall = self.document.ActiveObject
        self.assertEqual(Draft.get_type(wall), "Wall")

        # Calculate the expected global placement
        midpoint_local = (p1_local + p2_local) * 0.5
        direction_local = (p2_local - p1_local).normalize()
        rotation_local = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), direction_local)
        placement_local = FreeCAD.Placement(midpoint_local, rotation_local)

        # The wall's final placement must be the local placement transformed by the WP
        expected_placement = wp.get_placement().multiply(placement_local)

        # Compare Position (Vector)
        self.assertTrue(
            wall.Placement.Base.isEqual(expected_placement.Base, Part.Precision.confusion()),
            f"Wall position {wall.Placement.Base} does not match expected {expected_placement.Base}",
        )

        # Compare Orientation (Rotation)
        self.assertTrue(
            wall.Placement.Rotation.isSame(expected_placement.Rotation, Part.Precision.confusion()),
            f"Wall rotation {wall.Placement.Rotation.Q} does not match expected {expected_placement.Rotation.Q}",
        )

    def test_create_multiple_sketch_based_walls(self):
        """Tests that creating multiple sketch-based walls uses separate sketches."""
        self.printTestMessage("Testing creation of multiple sketch-based walls...")

        self.params.SetInt("WallBaseline", 2)

        cmd = current_arch_wall_class()()
        cmd.doc = self.document
        cmd.wp = WorkingPlane.get_working_plane()
        cmd.Align = "Left"
        cmd.Width = 200.0
        cmd.Height = 1500.0
        cmd.MultiMat = None
        cmd.tracker = MockTracker()
        cmd.existing = []

        initial_object_count = len(self.document.Objects)

        # Act: Create the first wall
        cmd.points = [FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0)]
        cmd.create_wall()
        base1 = self.document.getObject("Wall").Base

        # Act again: Create the second wall
        cmd.points = [FreeCAD.Vector(0, 1000, 0), FreeCAD.Vector(1000, 1000, 0)]
        cmd.create_wall()

        # Retrieve the last object to ensure we get the newest wall
        wall2 = self.document.ActiveObject
        base2 = wall2.Base

        # Assert
        self.assertEqual(
            len(self.document.Objects),
            initial_object_count + 4,
            "Should have created two Walls and two Sketches.",
        )
        self.assertIsNotNone(base1, "First wall should have a base sketch.")
        self.assertIsNotNone(base2, "Second wall should have a base sketch.")

        self.assertNotEqual(
            base1, base2, "Each sketch-based wall should have its own unique sketch object."
        )

    def _get_mock_side_effect(self, **kwargs):
        """
        Creates a side_effect function for mocking params.get_param.
        This reads the actual system parameter dictionary (draftutils.params.PARAM_DICT)
        to populate defaults, ensuring all parameters expected by Draft/BIM tools are present.
        It then overrides specific values as needed for the test.
        """

        from draftutils import params

        def side_effect(name, path=None, ret_default=False, silent=False):
            # Start with a comprehensive dictionary built from the real parameter definitions
            defaults = {}
            # Flatten PARAM_DICT: iterate over all groups ('Mod/Draft', 'View', etc.)
            for group_name, group_params in params.PARAM_DICT.items():
                for param_name, param_data in group_params.items():
                    # param_data is (type, value)
                    defaults[param_name] = param_data[1]

            # Add or Override with test-specific values and missing parameters
            # Some parameters might be dynamic or not yet in PARAM_DICT in the environment
            overrides = {
                # Arch Wall specific overrides for tests
                "joinWallSketches": False,
                "autoJoinWalls": False,
                "WallBaseline": 0,
            }
            defaults.update(overrides)

            # Apply any kwargs passed specifically to this side_effect call (from tests)
            if name in kwargs:
                return kwargs[name]

            val = defaults.get(name)

            return val

        return side_effect

    def _simulate_interactive_wall_creation(self, p1, p2, existing_wall, wall_width=200.0):
        """
        Simulates the core logic of the Arch_Wall command's interactive mode.
        """
        try:
            cmd = current_arch_wall_class()()

            # This calls the real Activated() method, but the mock intercepts the
            # calls to params.get_param, allowing us to control the outcome.
            FreeCADGui.Selection.clearSelection()
            cmd.Activated()

            # Override interactive parts of the command instance
            cmd.doc = self.document
            cmd.wp = WorkingPlane.get_working_plane()
            cmd.points = [p1, p2]
            cmd.Width = wall_width
            cmd.existing = [existing_wall] if existing_wall else []
            cmd.tracker = MockTracker()

            # This is the core action being tested
            cmd.create_wall()
            return self.document.Objects[-1]  # Return the newly created wall
        finally:
            # Clean up the global command state to ensure test isolation
            # We put this here to ensure cleanup even if the wall creation fails
            if FreeCAD.activeDraftCommand is cmd:
                FreeCAD.activeDraftCommand = None

    # Section 1: Baseless wall joining

    @patch("draftutils.params.get_param")
    def test_baseless_wall_autojoins_as_addition(self, mock_get_param):
        """Verify baseless wall becomes an 'Addition' when AUTOJOIN is on."""
        mock_get_param.side_effect = self._get_mock_side_effect(autoJoinWalls=True, WallBaseline=0)
        self.printTestMessage("Testing baseless wall with AUTOJOIN=True...")

        wall1 = Arch.makeWall(length=1000)
        self.document.recompute()
        initial_object_count = len(self.document.Objects)

        wall2 = self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1
        )

        self.assertEqual(len(self.document.Objects), initial_object_count + 1)
        self.assertIn(wall2, wall1.Additions, "New baseless wall should be in wall1's Additions.")

    @patch("draftutils.params.get_param")
    def test_baseless_wall_does_not_join_when_autojoin_is_off(self, mock_get_param):
        """Verify no relationship is created for baseless wall when AUTOJOIN is off."""
        mock_get_param.side_effect = self._get_mock_side_effect(autoJoinWalls=False, WallBaseline=0)
        self.printTestMessage("Testing baseless wall with AUTOJOIN=False...")

        wall1 = Arch.makeWall(length=1000)
        self.document.recompute()

        self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1
        )

        self.assertEqual(len(wall1.Additions), 0, "No join action should have occurred.")

    # Section 2: Draft-Line-based wall joining

    @patch("draftutils.params.get_param")
    def test_line_based_wall_merges_with_joinWallSketches(self, mock_get_param):
        """Verify line-based wall performs a destructive merge."""
        mock_get_param.side_effect = self._get_mock_side_effect(
            joinWallSketches=True, WallBaseline=1
        )
        self.printTestMessage("Testing line-based wall with JOIN_SKETCHES=True...")

        line1 = Draft.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0))
        wall1 = Arch.makeWall(line1)
        self.document.recompute()
        base1_initial_edges = len(wall1.Base.Shape.Edges)

        self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1
        )

        self.assertEqual(
            len(self.document.Objects),
            3,  # In theory objects should be 2, but wall merging does not delete the original baseline
            "The new wall and its line should have been deleted.",
        )
        self.assertEqual(
            wall1.Base.TypeId,
            "Sketcher::SketchObject",
            "The base of wall1 should have been converted to a Sketch.",
        )
        self.assertGreater(
            len(wall1.Base.Shape.Edges),
            base1_initial_edges,
            "The base sketch should have more edges after the merge.",
        )

    @patch("draftutils.params.get_param")
    def test_line_based_wall_uses_autojoin_when_joinWallSketches_is_off(self, mock_get_param):
        """Verify line-based wall uses AUTOJOIN when sketch joining is off."""
        mock_get_param.side_effect = self._get_mock_side_effect(
            joinWallSketches=False, autoJoinWalls=True, WallBaseline=1
        )
        self.printTestMessage("Testing line-based wall with JOIN_SKETCHES=False, AUTOJOIN=True...")

        line1 = Draft.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0))
        wall1 = Arch.makeWall(line1)
        self.document.recompute()
        initial_object_count = len(self.document.Objects)

        wall2 = self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1
        )

        self.assertEqual(
            len(self.document.Objects),
            initial_object_count + 2,
            "A new wall and its baseline should have been created.",
        )
        self.assertIn(wall2, wall1.Additions, "The new wall should be an Addition to the first.")

    @patch("draftutils.params.get_param")
    def test_line_based_wall_falls_back_to_autojoin_on_incompatible_walls(self, mock_get_param):
        """Verify fallback to AUTOJOIN for incompatible line-based walls."""
        mock_get_param.side_effect = self._get_mock_side_effect(
            joinWallSketches=True, autoJoinWalls=True, WallBaseline=1
        )
        self.printTestMessage("Testing line-based wall fallback to AUTOJOIN...")

        line1 = Draft.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0))
        wall1 = Arch.makeWall(line1, width=200)  # Incompatible width
        self.document.recompute()

        wall2 = self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1, wall_width=300
        )

        self.assertIn(wall2, wall1.Additions, "Fallback failed; wall should be an Addition.")

    # Section 3: Sketch-based wall joining

    @patch("draftutils.params.get_param")
    def test_sketch_based_wall_merges_with_joinWallSketches(self, mock_get_param):
        """Verify sketch-based wall performs a destructive merge."""
        mock_get_param.side_effect = self._get_mock_side_effect(
            joinWallSketches=True, WallBaseline=2
        )
        self.printTestMessage("Testing sketch-based wall with JOIN_SKETCHES=True...")

        sketch1 = self.document.addObject("Sketcher::SketchObject", "Sketch1")
        sketch1.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0)))
        wall1 = Arch.makeWall(sketch1)
        self.document.recompute()
        base1_initial_edges = len(wall1.Base.Shape.Edges)

        self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1
        )

        self.assertEqual(
            len(self.document.Objects),
            2,
            "The new wall and its sketch should have been deleted.",
        )
        self.assertGreater(
            len(wall1.Base.Shape.Edges),
            base1_initial_edges,
            "The base sketch should have more edges after the merge.",
        )

    @patch("draftutils.params.get_param")
    def test_sketch_based_wall_uses_autojoin_when_joinWallSketches_is_off(self, mock_get_param):
        """Verify sketch-based wall uses AUTOJOIN when sketch joining is off."""
        mock_get_param.side_effect = self._get_mock_side_effect(
            joinWallSketches=False, autoJoinWalls=True, WallBaseline=2
        )
        self.printTestMessage(
            "Testing sketch-based wall with JOIN_SKETCHES=False, AUTOJOIN=True..."
        )

        sketch1 = self.document.addObject("Sketcher::SketchObject", "Sketch1")
        sketch1.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0)))
        wall1 = Arch.makeWall(sketch1)
        self.document.recompute()

        wall2 = self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1
        )

        self.assertIn(wall2, wall1.Additions, "The new wall should be an Addition to the first.")

    @patch("draftutils.params.get_param")
    def test_sketch_based_wall_falls_back_to_autojoin_on_incompatible_walls(self, mock_get_param):
        """Verify fallback to AUTOJOIN for incompatible sketch-based walls."""
        mock_get_param.side_effect = self._get_mock_side_effect(
            joinWallSketches=True, autoJoinWalls=True, WallBaseline=2
        )
        self.printTestMessage("Testing sketch-based wall fallback to AUTOJOIN...")

        sketch1 = self.document.addObject("Sketcher::SketchObject", "Sketch1")
        sketch1.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0)))
        wall1 = Arch.makeWall(sketch1, width=200)  # Incompatible width
        self.document.recompute()

        wall2 = self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1, wall_width=300
        )

        self.assertIn(wall2, wall1.Additions, "Fallback failed; wall should be an Addition.")

    @patch("draftutils.params.get_param")
    def test_no_join_action_when_prefs_are_off(self, mock_get_param):
        """Verify no join action occurs when both preferences are off."""
        mock_get_param.side_effect = self._get_mock_side_effect(
            joinWallSketches=False, autoJoinWalls=False, WallBaseline=1
        )
        self.printTestMessage("Testing no join action when preferences are off...")

        # Test with a based wall
        line1 = Draft.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0))
        wall1 = Arch.makeWall(line1)
        self.document.recompute()
        initial_object_count = len(self.document.Objects)

        self._simulate_interactive_wall_creation(
            FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 1000, 0), wall1
        )

        self.assertEqual(len(self.document.Objects), initial_object_count + 2)
        self.assertEqual(
            len(wall1.Additions), 0, "No join action should have occurred for based wall."
        )
