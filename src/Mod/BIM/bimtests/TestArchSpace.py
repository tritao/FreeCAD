# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2013 Yorik van Havre <yorik@uncreated.net>              *
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

# Unit tests for the Arch space module

import os
from unittest.mock import patch
import Arch
import ArchSpace
import Draft
import Part
import FreeCAD as App
from FreeCAD import Units
from bimtests import TestArchBase
import WorkingPlane


def like(a, b):
    return abs(a - b) < 0.001


def checkBB(a, b):
    return (
        like(a.XMin, b.XMin)
        and like(a.YMin, b.YMin)
        and like(a.ZMin, b.ZMin)
        and like(a.XMax, b.XMax)
        and like(a.YMax, b.YMax)
        and like(a.ZMax, b.ZMax)
    )


class TestArchSpace(TestArchBase.TestArchBase):

    def testSpace(self):
        operation = "Checking Arch Space..."
        self.printTestMessage(operation)

        sb = Part.makeBox(1, 1, 1)
        b = App.ActiveDocument.addObject("Part::Feature", "Box")
        b.Shape = sb
        s = Arch.makeSpace([b])
        self.assertTrue(s, "Arch Space failed")

    def test_space_footprint_returns_face_list(self):
        operation = "Checking Arch Space footprint contract..."
        self.printTestMessage(operation)

        base = App.ActiveDocument.addObject("Part::Feature", "SpaceBox")
        base.Shape = Part.makeBox(1000, 500, 2000)
        space = Arch.makeSpace([base])
        App.ActiveDocument.recompute()

        faces = space.Proxy.getFootprint(space)

        self.assertIsInstance(faces, list)
        self.assertEqual(len(faces), 1)
        self.assertGreater(faces[0].Area, 0)
        self.assertAlmostEqual(space.Proxy.getArea(space), faces[0].Area)

    def test_space_area_falls_back_to_footprint_when_projection_area_is_zero(self):
        """Space Area should fall back to the footprint when XY projection data is unavailable."""
        operation = "Checking Arch Space area fallback"
        self.printTestMessage(operation)

        base = App.ActiveDocument.addObject("Part::Feature", "FallbackSpaceBox")
        base.Shape = Part.makeBox(4000, 3000, 2500)

        def fake_compute_areas(_self, obj):
            obj.VerticalArea = 0
            obj.HorizontalArea = 0
            obj.PerimeterLength = 0

        with patch("ArchComponent.Component.computeAreas", autospec=True) as compute_areas:
            compute_areas.side_effect = fake_compute_areas
            space = Arch.makeSpace(base)
            App.ActiveDocument.recompute()

        self.assertEqual(space.HorizontalArea.getValueAs("m^2").Value, 0)
        self.assertAlmostEqual(space.Area.getValueAs("m^2").Value, 12.0, places=3)
        self.assertAlmostEqual(space.PerimeterLength.getValueAs("m").Value, 14.0, places=3)

    def testSpaceBBox(self):
        operation = "Checking Arch Space bound box..."
        self.printTestMessage(operation)

        shape = Part.Shape()
        shape.importBrepFromString(brepArchiCAD)
        bborig = shape.BoundBox
        App.Console.PrintLog("Original BB: " + str(bborig))
        baseobj = App.ActiveDocument.addObject("Part::Feature", "brepArchiCAD_body")
        baseobj.Shape = shape
        space = Arch.makeSpace(baseobj)
        space.recompute()
        bbnew = space.Shape.BoundBox
        App.Console.PrintLog("New BB: " + str(bbnew))
        self.assertTrue(checkBB(bborig, bbnew), "Arch Space has wrong Placement")

    def test_addSpaceBoundaries(self):
        """Test the Arch.addSpaceBoundaries method.
        Create a space and a wall that intersects it. Add the wall as a boundary to the space,
        and check if the resulting space area is as expected.
        """
        operation = "Add a wall face as a boundary to a space"
        self.printTestMessage(operation)

        # Create the space
        pl = App.Placement()
        pl.Rotation.Q = (0.0, 0.0, 0.0, 1.0)
        pl.Base = App.Vector(-2000.0, -2000.0, 0.0)
        rectangleBase = Draft.make_rectangle(
            length=4000.0, height=4000.0, placement=pl, face=True, support=None
        )
        App.ActiveDocument.recompute()
        extr = rectangleBase.Shape.extrude(App.Vector(0, 0, 2000))
        Part.show(extr, "Extrusion")
        space = Arch.makeSpace(App.activeDocument().getObject("Extrusion"))
        App.ActiveDocument.recompute()  # To calculate area

        # Create the wall
        trace = Part.LineSegment(App.Vector(3000.0, 1000.0, 0.0), App.Vector(-3000.0, 1000.0, 0.0))
        wp = WorkingPlane.get_working_plane()
        base = App.ActiveDocument.addObject("Sketcher::SketchObject", "WallTrace")
        base.Placement = wp.get_placement()
        base.addGeometry(trace)
        wall = Arch.makeWall(base, width=200.0, height=3000.0, align="Left")
        wall.Normal = wp.axis

        # Add the boundary
        wallBoundary = [(wall, ["Face1"])]
        Arch.addSpaceBoundaries(App.ActiveDocument.Space, wallBoundary)
        App.ActiveDocument.recompute()  # To recalculate area

        # Assert if area is as expected
        expectedArea = Units.parseQuantity("12 m^2")
        actualArea = Units.parseQuantity(str(space.Area))

        self.assertAlmostEqual(
            expectedArea.Value,
            actualArea.Value,
            msg=(
                f"Invalid area value. "
                + f"Expected: {expectedArea.UserString}, actual: {actualArea.UserString}"
            ),
        )

    def test_SpaceFromSingleWall(self):
        """Create a space from boundaries of a single wall."""
        operation = "Arch Space from single wall"
        self.printTestMessage(operation)

        # Create a wall
        wallInnerLength = 4000.0
        wallHeight = 3000.0
        wallInnerFaceArea = wallInnerLength * wallHeight
        pl = App.Placement()
        pl.Rotation.Q = (0.0, 0.0, 0.0, 1.0)
        pl.Base = App.Vector(0.0, 0.0, 0.0)
        rectangleBase = Draft.make_rectangle(
            length=wallInnerLength, height=wallInnerLength, placement=pl, face=True, support=None
        )
        App.ActiveDocument.recompute()  # To calculate rectangle area
        rectangleArea = rectangleBase.Area
        App.ActiveDocument.getObject(rectangleBase.Name).MakeFace = False
        wall = Arch.makeWall(baseobj=rectangleBase, height=wallHeight, align="Left")
        App.ActiveDocument.recompute()  # To calculate face areas

        # Create a space from the wall's inner faces
        boundaries = [
            f"Face{ind+1}"
            for ind, face in enumerate(wall.Shape.Faces)
            if round(face.Area) == round(wallInnerFaceArea)
        ]

        if App.GuiUp:
            import FreeCADGui

            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(wall, boundaries)

            space = Arch.makeSpace(FreeCADGui.Selection.getSelectionEx())
            # Alternative, but test takes longer to run (~10x)
            # FreeCADGui.activateWorkbench("BIMWorkbench")
            # FreeCADGui.runCommand('Arch_Space', 0)
            # space = App.ActiveDocument.Space
        else:
            # Also tests the alternative way of specifying the boundaries
            # [ (<Part::Feature>, ["Face1", ...]), ... ]
            space = Arch.makeSpace([(wall, boundaries)])

        App.ActiveDocument.recompute()  # To calculate space area

        # Assert if area is as expected
        expectedArea = Units.parseQuantity(str(rectangleArea))
        actualArea = Units.parseQuantity(str(space.Area))

        self.assertAlmostEqual(
            expectedArea.Value,
            actualArea.Value,
            msg=f"Invalid area value. Expected: {expectedArea.UserString}, actual: {actualArea.UserString}",
        )

    def test_space_boundaries_support_inner_void_loop(self):
        """Boundary-derived spaces should support a single inner void."""
        operation = "Arch Space from boundary loops with an inner void"
        self.printTestMessage(operation)

        height = 2500.0
        expected_area = 6000.0 * 4000.0 - 2000.0 * 1500.0

        def make_boundary_face(name, points):
            face_object = App.ActiveDocument.addObject("Part::Feature", name)
            face_object.Shape = Part.Face(Part.makePolygon(points + [points[0]]))
            return face_object

        boundaries = [
            (
                make_boundary_face(
                    "OuterSouth",
                    [
                        App.Vector(0.0, 0.0, 0.0),
                        App.Vector(6000.0, 0.0, 0.0),
                        App.Vector(6000.0, 0.0, height),
                        App.Vector(0.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterEast",
                    [
                        App.Vector(6000.0, 0.0, 0.0),
                        App.Vector(6000.0, 4000.0, 0.0),
                        App.Vector(6000.0, 4000.0, height),
                        App.Vector(6000.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterNorth",
                    [
                        App.Vector(6000.0, 4000.0, 0.0),
                        App.Vector(0.0, 4000.0, 0.0),
                        App.Vector(0.0, 4000.0, height),
                        App.Vector(6000.0, 4000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OuterWest",
                    [
                        App.Vector(0.0, 4000.0, 0.0),
                        App.Vector(0.0, 0.0, 0.0),
                        App.Vector(0.0, 0.0, height),
                        App.Vector(0.0, 4000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "InnerSouth",
                    [
                        App.Vector(1000.0, 1000.0, 0.0),
                        App.Vector(3000.0, 1000.0, 0.0),
                        App.Vector(3000.0, 1000.0, height),
                        App.Vector(1000.0, 1000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "InnerEast",
                    [
                        App.Vector(3000.0, 1000.0, 0.0),
                        App.Vector(3000.0, 2500.0, 0.0),
                        App.Vector(3000.0, 2500.0, height),
                        App.Vector(3000.0, 1000.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "InnerNorth",
                    [
                        App.Vector(3000.0, 2500.0, 0.0),
                        App.Vector(1000.0, 2500.0, 0.0),
                        App.Vector(1000.0, 2500.0, height),
                        App.Vector(3000.0, 2500.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "InnerWest",
                    [
                        App.Vector(1000.0, 2500.0, 0.0),
                        App.Vector(1000.0, 1000.0, 0.0),
                        App.Vector(1000.0, 1000.0, height),
                        App.Vector(1000.0, 2500.0, height),
                    ],
                ),
                ["Face1"],
            ),
        ]

        preflight = ArchSpace.analyzeBoundaryLinks(boundaries, label="Inner Void Preview")
        self.assertTrue(preflight["valid"])
        self.assertEqual(preflight["code"], "valid")
        self.assertEqual(preflight["region_count"], 1)
        self.assertEqual(preflight["inner_void_count"], 1)

        space = Arch.makeSpace(boundaries)
        App.ActiveDocument.recompute()

        footprint = space.Proxy.getFootprint(space)

        self.assertEqual(len(space.Shape.Solids), 1)
        self.assertEqual(len(footprint), 1)
        self.assertEqual(len(footprint[0].Wires), 2)
        self.assertAlmostEqual(space.Proxy.getArea(space), expected_area)
        self.assertAlmostEqual(footprint[0].Area, expected_area)
        self.assertAlmostEqual(space.Area.getValueAs("m^2").Value, 21.0, places=3)
        self.assertAlmostEqual(space.PerimeterLength.getValueAs("m").Value, 27.0, places=3)

    def test_space_boundary_failure_describes_open_loop(self):
        """Open boundary selections should keep a useful failure reason."""
        operation = "Arch Space reports open boundary loops"
        self.printTestMessage(operation)

        height = 2500.0

        def make_boundary_face(name, points):
            face_object = App.ActiveDocument.addObject("Part::Feature", name)
            face_object.Shape = Part.Face(Part.makePolygon(points + [points[0]]))
            return face_object

        boundaries = [
            (
                make_boundary_face(
                    "OpenSouth",
                    [
                        App.Vector(0.0, 0.0, 0.0),
                        App.Vector(4000.0, 0.0, 0.0),
                        App.Vector(4000.0, 0.0, height),
                        App.Vector(0.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OpenEast",
                    [
                        App.Vector(4000.0, 0.0, 0.0),
                        App.Vector(4000.0, 3000.0, 0.0),
                        App.Vector(4000.0, 3000.0, height),
                        App.Vector(4000.0, 0.0, height),
                    ],
                ),
                ["Face1"],
            ),
            (
                make_boundary_face(
                    "OpenWest",
                    [
                        App.Vector(0.0, 3000.0, 0.0),
                        App.Vector(0.0, 0.0, 0.0),
                        App.Vector(0.0, 0.0, height),
                        App.Vector(0.0, 3000.0, height),
                    ],
                ),
                ["Face1"],
            ),
        ]

        with patch("FreeCAD.Console.PrintError") as print_error:
            space = Arch.makeSpace(boundaries)
            App.ActiveDocument.recompute()

        preflight = ArchSpace.analyzeBoundaryLinks(boundaries, label="Open Loop Preview")
        self.assertFalse(preflight["valid"])
        self.assertEqual(preflight["code"], "open_loop")
        self.assertIn("closed room loop", preflight["message"])
        self.assertEqual(len(space.Shape.Solids), 0)
        self.assertIn("closed room loop", space.Proxy.getLastBoundaryError())
        console_output = "".join(call.args[0] for call in print_error.call_args_list)
        self.assertIn("closed room loop", console_output)

    def test_space_base_supports_connected_l_shaped_volume(self):
        """Connected non-rectangular base solids should keep a polygonal footprint."""
        operation = "Arch Space from connected L-shaped base"
        self.printTestMessage(operation)

        points = [
            App.Vector(0.0, 0.0, 0.0),
            App.Vector(4000.0, 0.0, 0.0),
            App.Vector(4000.0, 1000.0, 0.0),
            App.Vector(1000.0, 1000.0, 0.0),
            App.Vector(1000.0, 3000.0, 0.0),
            App.Vector(0.0, 3000.0, 0.0),
            App.Vector(0.0, 0.0, 0.0),
        ]
        l_face = Part.Face(Part.makePolygon(points))
        base = App.ActiveDocument.addObject("Part::Feature", "ConnectedLShape")
        base.Shape = l_face.extrude(App.Vector(0.0, 0.0, 2500.0))

        space = Arch.makeSpace(base)
        App.ActiveDocument.recompute()

        faces = space.Proxy.getFootprint(space)
        actual_area = Units.parseQuantity(str(space.Area)).Value

        self.assertEqual(len(space.Shape.Solids), 1)
        self.assertEqual(len(faces), 1)
        self.assertGreater(len(faces[0].OuterWire.Vertexes), 4)
        self.assertAlmostEqual(actual_area, l_face.Area)
        self.assertAlmostEqual(faces[0].Area, l_face.Area)

    def test_space_base_multi_solid_keeps_only_first_connected_region(self):
        """Current Arch Space base-shape flow only keeps the first solid of a disconnected base."""
        operation = "Arch Space from disconnected multi-solid base"
        self.printTestMessage(operation)

        box_a = Part.makeBox(2000.0, 1500.0, 2500.0, App.Vector(0.0, 0.0, 0.0))
        box_b = Part.makeBox(1200.0, 1200.0, 2500.0, App.Vector(4000.0, 0.0, 0.0))
        disconnected = Part.makeCompound([box_a, box_b])
        base = App.ActiveDocument.addObject("Part::Feature", "DisconnectedSpaceBase")
        base.Shape = disconnected

        space = Arch.makeSpace(base)
        App.ActiveDocument.recompute()

        footprint = space.Proxy.getFootprint(space)
        actual_area = Units.parseQuantity(str(space.Area)).Value
        total_disconnected_area = 2000.0 * 1500.0 + 1200.0 * 1200.0
        first_region_area = 2000.0 * 1500.0

        self.assertEqual(len(base.Shape.Solids), 2)
        self.assertEqual(len(space.Shape.Solids), 1)
        self.assertEqual(len(footprint), 1)
        self.assertAlmostEqual(actual_area, first_region_area)
        self.assertLess(actual_area, total_disconnected_area)


brepArchiCAD = """
DBRep_DrawableShape

CASCADE Topology V1, (c) Matra-Datavision
Locations 3
1
              1               0               0               0
              0               1               0               0
              0               0               1               0
1
              0               1               0               0
             -1               0               0               0
              0               0               1               0
2  2 -1 0
Curve2ds 0
Curves 12
1 0 0 0 1 0 0
1 3000 0 0 0 0 1
1 3000 0 3000 -1 0 0
1 0 0 3000 0 0 -1
1 0 0 0 0 1 0
1 0 5000 0 1 0 0
1 3000 5000 0 0 -1 0
1 3000 5000 0 0 0 1
1 3000 5000 3000 0 -1 0
1 3000 5000 3000 -1 0 0
1 0 5000 3000 0 -1 0
1 0 5000 3000 0 0 -1
Polygon3D 0
PolygonOnTriangulations 24
2 1 2
p 18.3333333333333 1 0 3000
2 1 4
p 18.3333333333333 1 0 3000
2 2 3
p 18.3333333333333 1 0 3000
2 2 4
p 18.3333333333333 1 0 3000
2 3 4
p 18.3333333333333 1 0 3000
2 1 2
p 18.3333333333333 1 0 3000
2 4 1
p 18.3333333333333 1 0 3000
2 3 1
p 18.3333333333333 1 0 3000
2 1 2
p 18.3333333333333 1 0 5000
2 1 2
p 18.3333333333333 1 0 5000
2 2 3
p 18.3333333333333 1 0 3000
2 1 2
p 18.3333333333333 1 0 3000
2 3 4
p 18.3333333333333 1 0 5000
2 1 2
p 18.3333333333333 1 0 5000
2 1 3
p 18.3333333333333 1 0 3000
2 2 4
p 18.3333333333333 1 0 3000
2 3 4
p 18.3333333333333 1 0 5000
2 3 1
p 18.3333333333333 1 0 5000
2 3 4
p 18.3333333333333 1 0 3000
2 4 3
p 18.3333333333333 1 0 3000
2 4 2
p 18.3333333333333 1 0 5000
2 4 3
p 18.3333333333333 1 0 5000
2 4 2
p 18.3333333333333 1 0 3000
2 3 1
p 18.3333333333333 1 0 3000
Surfaces 6
1 1500 0 1500 -0 -1 -0 0 0 -1 1 0 0
1 1500 2500 0 -0 -0 -1 -1 0 0 0 1 0
1 3000 2500 1500 1 0 0 0 0 1 0 -1 0
1 1500 2500 3000 0 0 1 1 0 0 0 1 0
1 0 2500 1500 -1 -0 -0 0 0 -1 0 -1 0
1 1500 5000 1500 0 1 0 0 0 1 1 0 0
Triangulations 6
4 2 1 18.3333333333333
0 0 0 3000 0 0 3000 0 3000 0 0 3000 1500 -1500 1500 1500 -1500 1500 -1500 -1500 3 4 1 2 3 1
4 2 1 18.3333333333333
0 0 0 0 5000 0 3000 5000 0 3000 0 0 1500 -2500 1500 2500 -1500 2500 -1500 -2500 2 3 4 2 4 1
4 2 1 18.3333333333333
3000 5000 0 3000 0 0 3000 5000 3000 3000 0 3000 -1500 -2500 -1500 2500 1500 -2500 1500 2500 4 2 1 4 1 3
4 2 1 18.3333333333333
3000 0 3000 0 0 3000 3000 5000 3000 0 5000 3000 1500 -2500 -1500 -2500 1500 2500 -1500 2500 3 2 1 3 4 2
4 2 1 18.3333333333333
0 0 0 0 5000 0 0 0 3000 0 5000 3000 1500 2500 1500 -2500 -1500 2500 -1500 -2500 1 3 4 1 4 2
4 2 1 18.3333333333333
0 5000 0 3000 5000 0 0 5000 3000 3000 5000 3000 -1500 -1500 -1500 1500 1500 -1500 1500 1500 3 2 1 4 2 3

TShapes 35
Ve
0.1
0 0 0
0 0

0101101
*
Ve
0.1
0 -3000 0
0 0

0101101
*
Ed
 0.0001 1 1 0
1  1 0 0 3000
6  1 1 0
6  2 2 0
0

0101000
+35 3 -34 3 *
Ve
0.1
0 -3000 3000
0 0

0101101
*
Ed
 0.0001 1 1 0
1  2 0 0 3000
6  3 1 0
6  4 3 0
0

0101000
+34 3 -32 3 *
Ve
0.1
0 0 3000
0 0

0101101
*
Ed
 0.0001 1 1 0
1  3 0 0 3000
6  5 1 0
6  6 4 0
0

0101000
+32 3 -30 3 *
Ed
 0.0001 1 1 0
1  4 0 0 3000
6  7 1 0
6  8 5 0
0

0101000
+30 3 -35 3 *
Wi

0101100
+33 0 +31 0 +29 0 +28 0 *
Fa
0  0.1 1 0
2  1
0111000
+27 0 *
Ve
0.1
5000 0 0
0 0

0101101
*
Ed
 0.0001 1 1 0
1  5 0 0 5000
6  9 2 0
6  10 5 0
0

0101000
+35 3 -25 3 *
Ve
0.1
5000 -3000 0
0 0

0101101
*
Ed
 0.0001 1 1 0
1  6 0 0 3000
6  11 2 0
6  12 6 0
0

0101000
+25 3 -23 3 *
Ed
 0.0001 1 1 0
1  7 0 0 5000
6  13 2 0
6  14 3 0
0

0101000
+23 3 -34 3 *
Wi

0101100
+24 0 +22 0 +21 0 -33 0 *
Fa
0  0.1 2 0
2  2
0111000
+20 0 *
Ve
0.1
5000 -3000 3000
0 0

0101101
*
Ed
 0.0001 1 1 0
1  8 0 0 3000
6  15 3 0
6  16 6 0
0

0101000
+23 3 -18 3 *
Ed
 0.0001 1 1 0
1  9 0 0 5000
6  17 3 0
6  18 4 0
0

0101000
+18 3 -32 3 *
Wi

0101100
-21 0 +17 0 +16 0 -31 0 *
Fa
0  0.1 3 0
2  3
0111000
+15 0 *
Ve
0.1
5000 0 3000
0 0

0101101
*
Ed
 0.0001 1 1 0
1  10 0 0 3000
6  19 4 0
6  20 6 0
0

0101000
+18 3 -13 3 *
Ed
 0.0001 1 1 0
1  11 0 0 5000
6  21 4 0
6  22 5 0
0

0101000
+13 3 -30 3 *
Wi

0101100
-29 0 -16 0 +12 0 +11 0 *
Fa
0  0.1 4 0
2  4
0111000
+10 0 *
Ed
 0.0001 1 1 0
1  12 0 0 3000
6  23 5 0
6  24 6 0
0

0101000
+13 3 -25 3 *
Wi

0101100
-24 0 -28 0 -11 0 +8 0 *
Fa
0  0.1 5 0
2  5
0111000
+7 0 *
Wi

0101100
-22 0 -8 0 -12 0 -17 0 *
Fa
0  0.1 6 0
2  6
0111000
+5 0 *
Sh

0101100
+26 0 +19 0 +14 0 +9 0 +6 0 +4 0 *
So

0100000
+3 0 *
Co

1100000
+2 2 *

+1 1
"""
