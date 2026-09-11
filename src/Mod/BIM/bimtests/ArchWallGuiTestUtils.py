# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
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

"""Shared GUI test helpers for Arch wall and Plan Edit coverage."""

import importlib

import Arch
import FreeCAD
import Part
from bimcommands import BimPlanSession
from bimtests import TestArchBaseGui


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
        del arg

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


class ArchWallGuiTestCase(TestArchBaseGui.TestArchBaseGui):
    def setUp(self):
        """Set up the BIM GUI test environment and wall preferences."""
        super().setUp()
        self.params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        self.original_wall_base = self.params.GetInt("WallBaseline", 1)

    def tearDown(self):
        """Restore wall preferences and stop any active Plan Edit session."""
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
