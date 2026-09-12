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
import Part
from bimtests import TestArchBaseGui


class TestArchFootprintGui(TestArchBaseGui.TestArchBaseGui):

    def _get_line_polylines(self, proxy):
        polylines = []
        points = proxy.lcoords.point
        counts = proxy.lset.numVertices
        point_index = 0
        for set_index in range(counts.getNum()):
            count = counts[set_index]
            polyline = []
            for _ in range(count):
                point = points[point_index]
                polyline.append(FreeCAD.Vector(point[0], point[1], point[2]))
                point_index += 1
            polylines.append(polyline)
        return polylines

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

    def test_symbolic_equipment_populates_line_footprint_display_data(self):
        """Edge-only equipment should populate line footprint data in plan mode."""

        base = self.document.addObject("Part::Feature", "EquipmentSymbol")
        base.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(600, 0, 0)),
                Part.makeLine(FreeCAD.Vector(600, 0, 0), FreeCAD.Vector(600, 400, 0)),
                Part.makeLine(FreeCAD.Vector(600, 400, 0), FreeCAD.Vector(0, 400, 0)),
                Part.makeLine(FreeCAD.Vector(0, 400, 0), FreeCAD.Vector(0, 0, 0)),
                Part.makeLine(FreeCAD.Vector(300, 0, 0), FreeCAD.Vector(300, 400, 0)),
            ]
        )

        equipment = Arch.makeEquipment(base)
        self.document.recompute()
        self.pump_gui_events()

        proxy = equipment.ViewObject.Proxy
        self.assertIn("Footprint", equipment.ViewObject.listDisplayModes())
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

    def test_equipment_plan_symbols_drive_line_footprint_display_data(self):
        """Authored 2D plan symbols should override generated equipment line footprints."""

        box = self.document.addObject("Part::Box", "EquipmentBox")
        box.Length = 800
        box.Width = 500
        box.Height = 900

        plan = self.document.addObject("Part::Feature", "EquipmentPlan")
        plan.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0)),
                Part.makeLine(FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 700, 0)),
                Part.makeLine(FreeCAD.Vector(1000, 700, 0), FreeCAD.Vector(0, 700, 0)),
                Part.makeLine(FreeCAD.Vector(0, 700, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )

        equipment = Arch.makeEquipment(box)
        equipment.PlanSymbols = [plan]
        self.document.recompute()
        self.pump_gui_events()

        proxy = equipment.ViewObject.Proxy
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

        polylines = self._get_line_polylines(proxy)
        points = [point for polyline in polylines for point in polyline]
        xs = [point.x for point in points]
        ys = [point.y for point in points]
        self.assertAlmostEqual(0.0, min(xs), delta=1e-6)
        self.assertAlmostEqual(1000.0, max(xs), delta=1e-6)
        self.assertAlmostEqual(0.0, min(ys), delta=1e-6)
        self.assertAlmostEqual(700.0, max(ys), delta=1e-6)
