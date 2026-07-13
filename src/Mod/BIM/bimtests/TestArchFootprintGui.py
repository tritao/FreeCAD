# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD contributors
# SPDX-FileNotice: Part of the FreeCAD project.
################################################################################
#                                                                              #
#   FreeCAD is free software: you can redistribute it and/or modify            #
#   it under the terms of the GNU Lesser General Public License as             #
#   published by the Free Software Foundation, either version 2.1              #
#   of the License, or (at your option) any later version.                     #
#                                                                              #
#   FreeCAD is distributed in the hope that it will be useful,                 #
#   but WITHOUT ANY WARRANTY; without even the implied warranty                #
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                    #
#   See the GNU Lesser General Public License for more details.                #
#                                                                              #
#   You should have received a copy of the GNU Lesser General Public           #
#   License along with FreeCAD. If not, see https://www.gnu.org/licenses       #
#                                                                              #
################################################################################

"""GUI regressions for footprint display data."""

import Arch
import FreeCAD
import FreeCADGui
import Part
from bimtests import TestArchBaseGui
from draftguitools.gui_snapper import Snapper


class TestArchFootprintGui(TestArchBaseGui.TestArchBaseGui):

    def test_new_wall_populates_footprint_display_data(self):
        """New walls should populate their footprint nodes on shape update."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        self.pump_gui_events()

        proxy = wall.ViewObject.Proxy
        self.assertIn("Footprint", wall.ViewObject.listDisplayModes())
        self.assertTrue(hasattr(proxy, "fcoords"))
        self.assertTrue(hasattr(proxy, "fset"))
        self.assertGreater(proxy.fcoords.point.getNum(), 0)
        self.assertGreater(proxy.fset.coordIndex.getNum(), 0)

    def test_wall_footprint_display_data_is_local_to_placement(self):
        """Footprint display data should be stored in object-local coordinates."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Placement.Base = FreeCAD.Vector(1234, 5678, 0)
        self.document.recompute()
        self.pump_gui_events()

        points = wall.ViewObject.Proxy.fcoords.point
        xs = []
        ys = []
        for idx in range(points.getNum()):
            point = points[idx]
            xs.append(point[0])
            ys.append(point[1])

        self.assertLess(min(xs), -1000)
        self.assertGreater(max(xs), 1000)
        self.assertLess(min(ys), 0)
        self.assertGreater(max(ys), 0)
        self.assertLess(max(abs(value) for value in xs), 5000)
        self.assertLess(max(abs(value) for value in ys), 500)

    def test_wall_footprint_mode_populates_snap_outline_data(self):
        """Footprint mode should expose outline edges for snapping."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        wall.ViewObject.DisplayMode = "Footprint"
        self.pump_gui_events()

        proxy = wall.ViewObject.Proxy
        self.assertTrue(hasattr(proxy, "flcoords"))
        self.assertTrue(hasattr(proxy, "flines"))
        self.assertGreater(proxy.flcoords.point.getNum(), 0)
        self.assertGreater(proxy.flines.coordIndex.getNum(), 0)

        derived_edge = proxy.getFootprintSnapEdges()[0]
        midpoint_parameter = (derived_edge.FirstParameter + derived_edge.LastParameter) / 2.0
        picked_edge = proxy.getFootprintSnapEdge(derived_edge.Curve.value(midpoint_parameter))
        self.assertIsNotNone(picked_edge)
        self.assertEqual(picked_edge.hashCode(), derived_edge.hashCode())

        self.assertIsNotNone(proxy.getFootprintSnapEdge(derived_edge.Vertexes[0].Point))

    def test_footprint_outline_tracks_line_color(self):
        """Changing LineColor should immediately update the outline node."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        proxy = wall.ViewObject.Proxy
        wall.ViewObject.LineColor = (0.2, 0.4, 0.6, 1.0)
        self.pump_gui_events()

        try:
            color = proxy.flinecolor.rgb.getValue()
        except AttributeError:
            color = proxy.flinecolor.rgb.getValues(0)[0]
        self.assertAlmostEqual(color[0], 0.2, places=6)
        self.assertAlmostEqual(color[1], 0.4, places=6)
        self.assertAlmostEqual(color[2], 0.6, places=6)

    def test_footprint_refreshes_when_storey_cut_changes(self):
        """Changing the containing storey's cut should refresh derived edges."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        wall.Shape = Part.makeCompound(
            [
                Part.makeBox(3000, 2000, 1000),
                Part.makeBox(2000, 2000, 1500, FreeCAD.Vector(500, 0, 1000)),
            ]
        )
        storey = Arch.makeFloor(name="FootprintRefreshStorey")
        storey.addObject(wall)
        storey.PlanCutHeight = 500
        wall.ViewObject.DisplayMode = "Footprint"
        self.pump_gui_events()
        low_representation = wall.ViewObject.Proxy.getFootprintRepresentation()
        self.assertIs(low_representation, wall.ViewObject.Proxy.getFootprintRepresentation())
        low_width = max(
            edge.BoundBox.XLength for edge in wall.ViewObject.Proxy.getFootprintSnapEdges()
        )

        storey.PlanCutHeight = 2000
        self.pump_gui_events()
        high_representation = wall.ViewObject.Proxy.getFootprintRepresentation()
        self.assertIsNot(low_representation, high_representation)
        high_width = max(
            edge.BoundBox.XLength for edge in wall.ViewObject.Proxy.getFootprintSnapEdges()
        )

        self.assertGreater(low_width, high_width)

    def test_footprint_edge_snapping_uses_coin_pick_and_draft_snapper(self):
        """Coin picks on the outline should reach Draft endpoint/midpoint/near snaps."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        wall.ViewObject.DisplayMode = "Footprint"
        self.pump_gui_events()

        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewTop()
        view.fitAll()
        self.pump_gui_events()

        edge = max(wall.ViewObject.Proxy.getFootprintSnapEdges(), key=lambda item: item.Length)
        start = edge.Vertexes[0].Point
        end = edge.Vertexes[-1].Point
        midpoint = start.add(end).multiply(0.5)

        def object_info(point):
            """Return the derived outline pick at a projected world point."""

            screen = view.getPointOnScreen(point)
            info = view.getObjectInfo(screen, 8)
            if not info:
                height = view.getSize()[1]
                screen = (screen[0], height - screen[1] - 1)
                info = view.getObjectInfo(screen, 8)
            if info and info.get("Object") == wall.Name and info.get("Component", "") == "":
                return info
            # A filled Footprint face can win the first Coin hit at a shared
            # boundary. getObjectsInfo still exposes the outline path, which
            # exercises the same ViewProvider.getElementPicked() callback.
            infos = view.getObjectsInfo(screen, 8) or []
            for candidate in infos:
                if candidate.get("Object") == wall.Name and candidate.get("Component", "") == "":
                    return candidate
            return None

        midpoint_info = object_info(midpoint)
        self.assertIsNotNone(midpoint_info)
        self.assertEqual(midpoint_info["Object"], wall.Name)
        self.assertEqual(midpoint_info.get("Component", ""), "")

        def snap(info, mode):
            snapper = Snapper()
            snapper.active_snaps = ["Lock", mode]
            snapper.snapInfo = info
            return snapper.snapToObject(
                None,
                True,
                False,
                None,
                FreeCAD.Vector(info["x"], info["y"], info["z"]),
            )

        endpoint = snap(midpoint_info, "Endpoint")
        midpoint_snap = snap(midpoint_info, "Midpoint")
        near = snap(midpoint_info, "Near")

        self.assertIsNotNone(endpoint)
        self.assertIsNotNone(midpoint_snap)
        self.assertIsNotNone(near)
        self.assertTrue(endpoint.isEqual(start, 0.001) or endpoint.isEqual(end, 0.001))
        self.assertTrue(midpoint_snap.isEqual(midpoint, 0.001))
        picked_midpoint = FreeCAD.Vector(midpoint_info["x"], midpoint_info["y"], midpoint_info["z"])
        self.assertTrue(near.isEqual(picked_midpoint, 0.001))
