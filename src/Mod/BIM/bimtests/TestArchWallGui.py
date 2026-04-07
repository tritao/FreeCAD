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

    class _FakeKeyEvent:
        def __init__(self, key):
            self._key = key

        def getKey(self):
            return self._key

    class _FakeEventCallback:
        def __init__(self, event):
            self._event = event
            self._handled = False

        def getEvent(self):
            return self._event

        def setHandled(self):
            self._handled = True

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

    def test_plan_edit_hovered_hosted_door_shows_preselection_overlay(self):
        """Hosted openings should get a hover overlay independent of global preselection."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="HoverDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.view,
            "getObjectsInfo",
            return_value=[{"Document": self.document.Name, "Object": door.Name, "Component": ""}],
        ):
            session._update_hovered_opening((100, 100))

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session._opening_hover_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 0)

    def test_plan_edit_clicking_hovered_hosted_door_selects_it(self):
        """Clicking a hovered hosted opening should promote it to selected opening state."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClickHoverDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_opening_target_at_position",
            return_value=door,
        ):
            activated = session._activate_opening_target((100, 100))

        self.assertTrue(activated)
        self.assertIs(session.selected_opening, door)
        self.assertIsNone(session.selected_wall)
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

    def test_plan_edit_opening_move_uses_reduced_snap_profile(self):
        """Opening move should use a constrained snap profile while point-picking."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="MoveDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        handle = session._get_selected_opening_edit_handles(door)[0]
        captured = {}
        pushed_modes = []
        popped = []

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ), patch.object(
            FreeCADGui.Snapper,
            "push_snap_modes",
            side_effect=lambda modes: pushed_modes.append(set(modes)),
        ), patch.object(
            FreeCADGui.Snapper, "pop_snap_modes", side_effect=lambda: popped.append(True)
        ):
            session._start_opening_handle_point_pick(door, 0, handle)

            self.assertEqual(pushed_modes, [set(BimPlanSession._OPENING_MOVE_SNAP_SET)])
            self.assertEqual(session.current_tool, "Move Opening")
            self.assertIn("callback", captured)
            self.assertIn("movecallback", captured)
            self.assertIn("last", captured)

            captured["callback"](handle.point, None)

        self.assertEqual(len(popped), 1)
        self.assertEqual(session.current_tool, "Select")

    def test_plan_edit_opening_move_clamps_to_host_span(self):
        """Opening move projection should stay within the valid host wall span."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClampedDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        origin = context["origin"]
        axis_u = context["axis_u"]
        far_before = origin.add(FreeCAD.Vector(axis_u).multiply(-100000))
        far_after = origin.add(FreeCAD.Vector(axis_u).multiply(100000))

        projected_before = proxy.project_point_to_host_axis(far_before)
        projected_after = proxy.project_point_to_host_axis(far_after)

        before_u = projected_before.sub(origin).dot(axis_u)
        after_u = projected_after.sub(origin).dot(axis_u)

        self.assertAlmostEqual(before_u, context["move_u_min"], delta=1e-6)
        self.assertAlmostEqual(after_u, context["move_u_max"], delta=1e-6)

    def test_plan_edit_opening_move_anchor_offsets_center_from_edge_alignment(self):
        """Opening move anchors should offset the center from left/right jamb picks."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="AnchoredDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        origin = context["origin"]
        axis_u = context["axis_u"]
        center_u = (context["move_u_min"] + context["move_u_max"]) * 0.5
        half_width = context["opening_half_width_u"]

        left_edge_point = origin.add(FreeCAD.Vector(axis_u).multiply(center_u - half_width))
        right_edge_point = origin.add(FreeCAD.Vector(axis_u).multiply(center_u + half_width))

        projected_left = proxy.project_point_to_host_axis(left_edge_point, anchor="left")
        projected_right = proxy.project_point_to_host_axis(right_edge_point, anchor="right")

        projected_left_u = projected_left.sub(origin).dot(axis_u)
        projected_right_u = projected_right.sub(origin).dot(axis_u)

        self.assertAlmostEqual(projected_left_u, center_u, delta=1e-6)
        self.assertAlmostEqual(projected_right_u, center_u, delta=1e-6)

    def test_plan_edit_opening_overlay_stays_within_wall_span_at_limit(self):
        """Hosted opening overlay should stay inside the host wall span at the move limit."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="BoundedSymbolDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        left_limit = context["origin"].add(
            FreeCAD.Vector(context["axis_u"]).multiply(context["move_u_min"])
        )
        left_limit.z = context["base_z"]
        proxy.move_along_host(left_limit)
        self.document.recompute()

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_end = FreeCAD.Vector(wall_end)
        wall_axis_u = wall_end.sub(wall_start)
        wall_length = wall_axis_u.Length
        self.assertGreater(wall_length, 0.0)
        wall_axis_u.normalize()

        overlay_us = []
        for polyline in proxy.get_plan_overlay_polylines():
            for point in polyline:
                overlay_us.append(FreeCAD.Vector(point).sub(wall_start).dot(wall_axis_u))

        self.assertTrue(overlay_us)
        self.assertGreaterEqual(min(overlay_us), -1e-6)
        self.assertLessEqual(max(overlay_us), wall_length + 1e-6)

    def test_plan_edit_opening_move_tab_cycles_anchor(self):
        """Tab should cycle opening move anchors while the point-pick is active."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="TabDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        handle = session._get_selected_opening_edit_handles(door)[0]

        with patch.object(FreeCADGui.Snapper, "getPoint", return_value=None), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ), patch.object(
            session, "_refresh_opening_move_preview_from_raw_point", return_value=None
        ) as refresh_preview:
            session._start_opening_handle_point_pick(door, 0, handle)

            from pivy import coin

            session._on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.TAB))
            )
            self.assertEqual(session._edit_opening_move_anchor, "left")

            session._on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.TAB))
            )
            self.assertEqual(session._edit_opening_move_anchor, "right")

            session._on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.TAB))
            )
            self.assertEqual(session._edit_opening_move_anchor, "center")

            self.assertEqual(refresh_preview.call_count, 3)

            session._cancel_opening_handle_point_pick()

    def test_plan_edit_opening_move_updates_input_hints(self):
        """Active opening move should publish placement/cancel/anchor hints."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="HintDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        handle = session._get_selected_opening_edit_handles(door)[0]

        with patch.object(FreeCADGui.Snapper, "getPoint", return_value=None), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ), patch.object(FreeCADGui.HintManager, "show") as show_hints:
            session._start_opening_handle_point_pick(door, 0, handle)

        self.assertTrue(show_hints.called)
        hints = show_hints.call_args.args
        self.assertEqual(len(hints), 3)
        self.assertEqual(hints[0].message, "place opening")
        self.assertEqual(hints[1].message, "cycle move anchor")
        self.assertEqual(hints[2].message, "cancel")

    def test_plan_edit_hovered_wall_shows_preselection_overlay(self):
        """Walls should get a lightweight hover overlay before actual selection."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.view,
            "getObjectsInfo",
            return_value=[{"Document": self.document.Name, "Object": wall.Name, "Component": ""}],
        ):
            session._update_hovered_plan_target((100, 100))

        self.assertIs(session.hovered_wall, wall)
        self.assertIsNone(session.hovered_opening)
        self.assertGreater(len(session._wall_hover_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 0)

    def test_plan_edit_clicking_hovered_wall_selects_it(self):
        """Clicking a hovered wall should promote it to selected wall state."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "_get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session._activate_wall_target((100, 100))

        self.assertTrue(activated)
        self.assertIs(session.selected_wall, wall)
        self.assertIsNone(session.selected_opening)
        self.assertEqual(len(session._wall_hover_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_wall_grip_move_uses_point_pick_commit(self):
        """Wall grips should use click-move-click editing instead of hold-drag."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            session._start_wall_grip_edit(2)

        self.assertEqual(session.current_tool, "Move Wall")
        self.assertIs(session.selected_wall, wall)
        self.assertIn("callback", captured)
        self.assertIn("movecallback", captured)
        self.assertIn("last", captured)

        new_midpoint = captured["last"].add(FreeCAD.Vector(1000, 0, 0))
        captured["movecallback"](new_midpoint, None)
        self.assertIsNotNone(session._preview_points)
        self.assertNotEqual(session._preview_points, list(original_endpoints))

        captured["callback"](new_midpoint, None)
        self.pump_gui_events()

        moved_endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(
            moved_endpoints[0].x - original_endpoints[0].x,
            1000.0,
            delta=1e-6,
        )
        self.assertAlmostEqual(
            moved_endpoints[1].x - original_endpoints[1].x,
            1000.0,
            delta=1e-6,
        )
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_wall, wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_wall_grip_move_escape_cancels_and_keeps_selection(self):
        """Esc should cancel an active wall point-pick edit and restore wall grips."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            session._start_wall_grip_edit(2)

        new_midpoint = captured["last"].add(FreeCAD.Vector(1000, 0, 0))
        captured["movecallback"](new_midpoint, None)

        from pivy import coin

        session._on_key_pressed(
            self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.ESCAPE))
        )
        self.pump_gui_events()

        canceled_endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(canceled_endpoints[0].x, original_endpoints[0].x, delta=1e-6)
        self.assertAlmostEqual(canceled_endpoints[1].x, original_endpoints[1].x, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_wall, wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_wall_grip_activation_is_deferred(self):
        """Wall grip activation should defer point-pick start until after the click event unwinds."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        calls = []

        def fake_single_shot(delay, callback):
            calls.append((delay, callback))

        with patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot):
            session._activate_wall_grip(2)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 0)
        self.assertEqual(session.current_tool, "Select")

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            calls[0][1]()

        self.assertEqual(session.current_tool, "Move Wall")
        self.assertIs(session.selected_wall, wall)

    def test_plan_edit_wall_move_preview_shows_delta_readouts(self):
        """Moving a wall should show horizontal and vertical temporary readouts."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = original_endpoints

        moved_points = [
            original_endpoints[0].add(FreeCAD.Vector(500, 250, 0)),
            original_endpoints[1].add(FreeCAD.Vector(500, 250, 0)),
        ]

        session._sync_wall_edit_preview(moved_points)

        self.assertEqual(len(session._wall_edit_readout_trackers), 2)
        self.assertTrue(
            all(hasattr(tracker, "dimnode") for tracker in session._wall_edit_readout_trackers)
        )
        self.assertEqual(
            sorted(
                int(tracker.dimnode.datumtype.getValue())
                for tracker in session._wall_edit_readout_trackers
            ),
            [2, 3],
        )

    def test_plan_edit_wall_stretch_preview_shows_length_readout(self):
        """Stretching a wall endpoint should show one aligned temporary length readout."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"

        stretched_points = [
            original_endpoints[0],
            original_endpoints[1].add(FreeCAD.Vector(800, 0, 0)),
        ]

        session._sync_wall_edit_preview(stretched_points)

        self.assertEqual(len(session._wall_edit_readout_trackers), 1)
        tracker = session._wall_edit_readout_trackers[0]
        self.assertTrue(hasattr(tracker, "label"))
        self.assertTrue(hasattr(tracker, "startEdit"))
        self.assertEqual(tracker.mode, 1)

    def test_plan_edit_wall_stretch_enter_starts_length_edit(self):
        """Enter should activate in-view length editing for a wall stretch preview."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            session._start_wall_grip_edit(1)

        from pivy import coin

        callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.RETURN))
        session._on_key_pressed(callback)

        self.assertTrue(callback._handled)
        self.assertIsNotNone(session._wall_edit_active_readout_tracker)
        self.assertTrue(session._wall_edit_active_readout_tracker.isInEdit())

    def test_plan_edit_wall_stretch_length_edit_updates_preview(self):
        """Numeric wall stretch edits should drive the preview without rebuilding the label."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"
        session._sync_wall_edit_preview(list(original_endpoints))

        tracker = session._wall_edit_active_readout_tracker
        self.assertIsNotNone(tracker)

        session._on_wall_stretch_length_changed(4200.0)

        self.assertIs(session._wall_edit_active_readout_tracker, tracker)
        self.assertAlmostEqual(session._preview_points[0].x, original_endpoints[0].x, delta=1e-6)
        self.assertAlmostEqual(
            session._preview_points[1].x, original_endpoints[0].x + 4200.0, delta=1e-6
        )

    def test_plan_edit_wall_stretch_length_edit_commits_wall(self):
        """Accepting a typed wall stretch length should commit the resized wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            session._start_wall_grip_edit(1)

        session._on_wall_stretch_length_finished(4200.0)
        self.pump_gui_events()

        endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(endpoints[1].sub(endpoints[0]).Length, 4200.0, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selected_wall, wall)

    def test_plan_edit_wall_edit_refreshes_hosted_opening_footprints(self):
        """Wall edits should refresh footprints for openings hosted by that wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="WallEditDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ), patch.object(session, "_refresh_opening_footprint_display") as refresh_opening:
            session._start_wall_grip_edit(2)
            new_midpoint = captured["last"].add(FreeCAD.Vector(400, 0, 0))
            captured["callback"](new_midpoint, None)

        refresh_opening.assert_any_call(door)

    def test_plan_edit_wall_stretch_clamps_hosted_opening_inside_wall(self):
        """Shortening a wall should move hosted openings back inside the valid span."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="ClampAfterStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        door_proxy.move_along_host(rightmost)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_end = original_endpoints[0].add(axis.multiply(1600.0))

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            session._start_wall_grip_edit(1)
            captured["callback"](shortened_end, None)

        updated_context = door_proxy.get_plan_move_context()
        current_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(current_center)
        current_center_u = (
            FreeCAD.Vector(current_center)
            .sub(updated_context["origin"])
            .dot(updated_context["axis_u"])
        )
        self.assertAlmostEqual(current_center_u, updated_context["move_u_max"], delta=1e-6)
        self.assertIn("callback", captured)
        self.assertIn("movecallback", captured)

    def test_plan_edit_wall_stretch_preserves_opening_edge_clearance(self):
        """Stretching a wall endpoint should preserve existing opening edge clearance when possible."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="PreserveEdgeClearanceDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        target_center_u = 750.0
        target_point = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(target_center_u)
        )
        target_point.z = move_context["base_z"]
        self.assertTrue(door_proxy.move_along_host(target_point))
        self.document.recompute()

        initial_context = door_proxy.get_plan_move_context()
        initial_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(initial_center)
        initial_center_u = (
            FreeCAD.Vector(initial_center)
            .sub(initial_context["origin"])
            .dot(initial_context["axis_u"])
        )
        initial_left_clearance = initial_center_u - initial_context["opening_half_width_u"]
        self.assertAlmostEqual(initial_left_clearance, 300.0, delta=1e-6)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        new_start = FreeCAD.Vector(original_endpoints[0]).add(FreeCAD.Vector(200.0, 0.0, 0.0))

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            session._start_wall_grip_edit(0)
            captured["callback"](new_start, None)

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_axis_u = FreeCAD.Vector(wall_end).sub(wall_start)
        self.assertGreater(wall_axis_u.Length, 0.0)
        wall_axis_u.normalize()

        updated_context = door_proxy.get_plan_move_context()
        updated_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(updated_center)
        updated_center_u = FreeCAD.Vector(updated_center).sub(wall_start).dot(wall_axis_u)
        updated_left_clearance = updated_center_u - updated_context["opening_half_width_u"]
        self.assertAlmostEqual(updated_left_clearance, initial_left_clearance, delta=1e-6)

    def test_plan_edit_wall_stretch_keeps_opening_symbol_centered_on_slot(self):
        """Hosted opening symbols should stay centered on the actual slot after wall resize."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="CenteredAfterStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        door_proxy.move_along_host(rightmost)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_end = original_endpoints[0].add(axis.multiply(1600.0))

        with patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point), patch.object(
            FreeCADGui.Snapper, "setSelectMode", return_value=None
        ):
            session._start_wall_grip_edit(1)
            captured["callback"](shortened_end, None)

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_end = FreeCAD.Vector(wall_end)
        wall_axis_u = wall_end.sub(wall_start)
        self.assertGreater(wall_axis_u.Length, 0.0)
        wall_axis_u.normalize()

        actual_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(actual_center)
        actual_center_u = FreeCAD.Vector(actual_center).sub(wall_start).dot(wall_axis_u)

        overlay_polylines = door_proxy.get_plan_overlay_polylines()
        self.assertTrue(overlay_polylines)
        centerline = overlay_polylines[-1]
        self.assertEqual(len(centerline), 2)
        symbol_center = FreeCAD.Vector(centerline[0]).add(centerline[1]).multiply(0.5)
        symbol_center_u = symbol_center.sub(wall_start).dot(wall_axis_u)

        self.assertAlmostEqual(symbol_center_u, actual_center_u, delta=1e-6)

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

    def test_plan_edit_invalidates_selected_opening_overlay_when_base_changes(self):
        """Selected opening overlays should be invalidated when the opening base changes."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="UndoDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        with patch.object(session, "_queue_plan_overlay_visual_refresh") as queue_refresh:
            session.slotChangedObject(door.Base, "Placement")

        queue_refresh.assert_called_once_with(
            BimPlanSession._PLAN_VISUAL_SELECTED_OPENING,
            BimPlanSession._PLAN_VISUAL_HOVERED_OPENING,
        )

    def test_plan_edit_invalidates_selected_opening_overlay_on_undo_document(self):
        """Selected opening overlays should be invalidated on document-level undo notifications."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="UndoNotifyDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session._refresh_selected_wall()

        with patch.object(session, "_queue_plan_overlay_visual_refresh") as queue_refresh:
            session.slotUndoDocument(self.document)

        queue_refresh.assert_called_once_with(
            BimPlanSession._PLAN_VISUAL_SELECTED_OPENING,
            BimPlanSession._PLAN_VISUAL_HOVERED_OPENING,
            BimPlanSession._PLAN_VISUAL_HOVERED_WALL,
            BimPlanSession._PLAN_VISUAL_WALL_GRIPS,
        )

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
