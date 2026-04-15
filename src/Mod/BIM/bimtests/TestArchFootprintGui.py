# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD contributors                               *
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

"""GUI regressions for footprint display data."""

import Arch
import FreeCAD
import Part
from bimtests import TestArchBaseGui
from draftutils import params


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

    def _project_v_values(self, polyline, origin, axis_v):
        return [point.sub(origin).dot(axis_v) for point in polyline]

    def _make_hosted_window(self, wall, name, x_start, z_start, width=800.0, height=1200.0):
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
        sketch.Placement.Base = FreeCAD.Vector(x_start, 0, z_start)
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

    def _make_hosted_door(self, wall, name, x_start, z_start, width=900.0, height=2100.0):
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
        sketch.Placement.Base = FreeCAD.Vector(x_start, 0, z_start)
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

    def _make_hosted_legacy_door(self, wall, name, x_start, z_start, width=900.0, height=2100.0):
        door = self._make_hosted_door(wall, name, x_start, z_start, width=width, height=height)
        door.IfcType = "Opening Element"
        self.document.recompute()
        return door

    def _make_hosted_legacy_opening_from_base(
        self, wall, name, x_start, z_start, width=1000.0, height=2100.0
    ):
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
        sketch.Placement.Base = FreeCAD.Vector(x_start, 0, z_start)
        self.document.recompute()

        opening = Arch.makeWindow(sketch, name=name)
        opening.Width = width
        opening.Height = height
        opening.HoleDepth = 0
        opening.IfcType = "Opening Element"
        opening.WindowParts = []
        self.document.recompute()

        Arch.addComponents(opening, wall)
        self.document.recompute()
        return opening

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

    def test_structure_footprint_mode_remains_slab_only(self):
        """Structure footprints should only be exposed while the object is a slab."""

        slab = Arch.makeStructure(length=3000, width=2000, height=250, name="TestSlab")
        self.document.recompute()
        self.pump_gui_events()

        self.assertNotIn("Footprint", slab.ViewObject.listDisplayModes())

        slab.IfcType = "Slab"
        self.document.recompute()
        self.pump_gui_events()

        self.assertIn("Footprint", slab.ViewObject.listDisplayModes())
        slab.ViewObject.DisplayMode = "Footprint"
        self.pump_gui_events()

        slab.IfcType = "Beam"
        self.document.recompute()
        self.pump_gui_events()

        self.assertNotIn("Footprint", slab.ViewObject.listDisplayModes())
        self.assertNotEqual(slab.ViewObject.DisplayMode, "Footprint")

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

    def test_window_footprint_populates_for_cut_opening(self):
        """Hosted windows crossing the cut plane should populate an inset plan symbol."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        window = self._make_hosted_window(
            wall,
            "FootprintWindow",
            x_start=1000,
            z_start=700,
            width=800.0,
            height=1200.0,
        )
        self.pump_gui_events()

        proxy = window.ViewObject.Proxy
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

        polylines = self._get_line_polylines(proxy)
        self.assertEqual(len(polylines), 3)
        self.assertEqual(len(polylines[0]), 2)
        self.assertEqual(len(polylines[1]), 2)
        self.assertEqual(len(polylines[2]), 2)

        cut_z, base_z = proxy._get_footprint_cut_context()
        profile = proxy._get_opening_section_profile(window.Shape, cut_z)
        self.assertIsNotNone(profile)
        host_bounds = proxy._get_host_plan_v_bounds(
            profile["origin"], profile["axis_u"], profile["axis_v"]
        )
        self.assertIsNotNone(host_bounds)
        host_vmin, host_vmax = host_bounds
        expected_inset = min((host_vmax - host_vmin) * 0.25, 30.0)

        for polyline in polylines[:2]:
            start_v = polyline[0].sub(profile["origin"]).dot(profile["axis_v"])
            end_v = polyline[1].sub(profile["origin"]).dot(profile["axis_v"])
            vmin = min(start_v, end_v)
            vmax = max(start_v, end_v)
            self.assertAlmostEqual(vmin - host_vmin, expected_inset, delta=1e-6)
            self.assertAlmostEqual(host_vmax - vmax, expected_inset, delta=1e-6)

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

    def test_late_equipment_plan_symbols_refresh_line_footprint_display_data(self):
        """Assigning plan symbols after creation should refresh cached footprint linework."""

        box = self.document.addObject("Part::Box", "LateEquipmentBox")
        box.Length = 800
        box.Width = 500
        box.Height = 900

        equipment = Arch.makeEquipment(box)
        self.document.recompute()
        self.pump_gui_events()

        plan = self.document.addObject("Part::Feature", "LateEquipmentPlan")
        plan.Shape = Part.makeCompound(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(1000, 0, 0)),
                Part.makeLine(FreeCAD.Vector(1000, 0, 0), FreeCAD.Vector(1000, 700, 0)),
                Part.makeLine(FreeCAD.Vector(1000, 700, 0), FreeCAD.Vector(0, 700, 0)),
                Part.makeLine(FreeCAD.Vector(0, 700, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )

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

    def test_window_footprint_ignores_openings_above_cut_height(self):
        """Openings above the cut plane should not emit committed footprint symbols."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        window = self._make_hosted_window(
            wall,
            "HighFootprintWindow",
            x_start=1000,
            z_start=1800,
            width=800.0,
            height=500.0,
        )
        self.pump_gui_events()

        proxy = window.ViewObject.Proxy
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertEqual(proxy.lcoords.point.getNum(), 0)
        self.assertEqual(proxy.lset.numVertices.getNum(), 0)

    def test_door_footprint_populates_for_cut_opening(self):
        """Hosted doors crossing the cut plane should populate a composed plan symbol."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        door = self._make_hosted_door(
            wall,
            "FootprintDoor",
            x_start=900,
            z_start=0,
            width=900.0,
            height=2100.0,
        )
        self.pump_gui_events()

        proxy = door.ViewObject.Proxy
        self.assertEqual(door.IfcType, "Door")
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

        polylines = self._get_line_polylines(proxy)
        self.assertEqual(len(polylines), 3)
        self.assertEqual(len(polylines[0]), 2, "Closed door leaf should be a single segment.")
        self.assertEqual(len(polylines[1]), 2, "Open door leaf should be a single segment.")
        self.assertGreater(len(polylines[2]), 2, "Door swing arc should be a polyline.")
        self.assertTrue(
            polylines[0][0].isEqual(polylines[1][0], 1e-6),
            "Closed and open leaves should share the same hinge point.",
        )
        closed_leaf_length = polylines[0][0].distanceToPoint(polylines[0][1])
        self.assertAlmostEqual(closed_leaf_length, 900.0, delta=1.0)

        cut_z, base_z = proxy._get_footprint_cut_context()
        profile = proxy._get_hosted_opening_plan_frame(door.Shape, cut_z, base_z)
        self.assertIsNotNone(profile)
        host_bounds = proxy._get_host_plan_v_bounds(
            profile["origin"], profile["axis_u"], profile["axis_v"]
        )
        self.assertIsNotNone(host_bounds)
        host_vmin, host_vmax = host_bounds
        hinge = polylines[0][0]
        hinge_v = hinge.sub(profile["origin"]).dot(profile["axis_v"])
        thickness = host_vmax - host_vmin
        expected_inset = min(thickness * 0.25, 30.0)
        self.assertGreater(hinge_v, host_vmin)
        self.assertLess(hinge_v, host_vmax)
        self.assertAlmostEqual(hinge_v - host_vmin, expected_inset, delta=1e-6)

    def test_legacy_opening_element_door_populates_for_cut_opening(self):
        """Legacy hosted openings with door-like WindowParts should still render as doors."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        door = self._make_hosted_legacy_door(
            wall,
            "LegacyFootprintDoor",
            x_start=900,
            z_start=0,
            width=900.0,
            height=2100.0,
        )
        self.pump_gui_events()

        proxy = door.ViewObject.Proxy
        self.assertEqual(door.IfcType, "Opening Element")
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

    def test_null_shape_opening_element_uses_base_sketch_for_footprint(self):
        """Legacy hosted openings should still render from their base sketch when Shape is null."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        opening = self._make_hosted_legacy_opening_from_base(
            wall,
            "LegacyBaseOpening",
            x_start=900,
            z_start=0,
            width=1000.0,
            height=2100.0,
        )
        self.pump_gui_events()

        proxy = opening.ViewObject.Proxy
        self.assertEqual(opening.IfcType, "Opening Element")
        self.assertTrue(opening.Shape.isNull())
        self.assertEqual(opening.WindowParts, [])
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

    def test_null_shape_opening_footprint_does_not_double_base_placement(self):
        """Legacy opening fallback should not apply the base placement twice."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Placement.Base = FreeCAD.Vector(5000, 4000, 0)
        self.document.recompute()

        opening = self._make_hosted_legacy_opening_from_base(
            wall,
            "LegacyTranslatedOpening",
            x_start=5800,
            z_start=700,
            width=1000.0,
            height=1200.0,
        )
        self.pump_gui_events()

        points = opening.ViewObject.Proxy.lcoords.point
        xs = []
        ys = []
        for idx in range(points.getNum()):
            point = points[idx]
            xs.append(point[0])
            ys.append(point[1])

        self.assertGreater(len(xs), 0)
        self.assertLess(max(xs), 8000.0)
        self.assertGreater(min(xs), 5000.0)
        self.assertLess(max(ys), 4500.0)
        self.assertGreater(min(ys), 3500.0)

    def test_host_shape_changes_refresh_legacy_opening_footprint(self):
        """Hosted legacy opening symbols should refresh when the host shape changes."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        opening = self._make_hosted_legacy_opening_from_base(
            wall,
            "LegacyOpeningWidthRefresh",
            x_start=900,
            z_start=700,
            width=1000.0,
            height=1200.0,
        )
        self.pump_gui_events()

        def _window_symbol_v_span():
            proxy = opening.ViewObject.Proxy
            cut_z, base_z = proxy._get_footprint_cut_context()
            frame = proxy._get_hosted_opening_plan_frame(opening.Shape, cut_z, base_z)
            self.assertIsNotNone(frame)
            host_bounds = proxy._get_host_plan_v_bounds(
                frame["origin"], frame["axis_u"], frame["axis_v"]
            )
            self.assertIsNotNone(host_bounds)
            polylines = self._get_line_polylines(proxy)
            self.assertGreaterEqual(len(polylines), 1)
            v_values = self._project_v_values(polylines[0], frame["origin"], frame["axis_v"])
            return (max(v_values) - min(v_values), host_bounds)

        self.assertGreater(opening.ViewObject.Proxy.lcoords.point.getNum(), 0)
        span, host_bounds = _window_symbol_v_span()
        host_vmin, host_vmax = host_bounds
        expected_inset = min((host_vmax - host_vmin) * 0.25, 30.0)
        self.assertAlmostEqual(span, (host_vmax - host_vmin) - (2.0 * expected_inset), delta=1.0)

        wall.Width = 400
        self.document.recompute()
        self.pump_gui_events()

        span, host_bounds = _window_symbol_v_span()
        host_vmin, host_vmax = host_bounds
        expected_inset = min((host_vmax - host_vmin) * 0.25, 30.0)
        self.assertAlmostEqual(span, (host_vmax - host_vmin) - (2.0 * expected_inset), delta=1.0)

    def test_null_shape_opening_at_floor_uses_door_footprint_symbol(self):
        """Floor-level legacy openings should emit the door-style footprint symbol."""

        previous_cut_height = params.get_param_arch("FootprintCutHeight")
        params.set_param_arch("FootprintCutHeight", 1000.0)
        self.addCleanup(params.set_param_arch, "FootprintCutHeight", previous_cut_height)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        opening = self._make_hosted_legacy_opening_from_base(
            wall,
            "LegacyDoorLikeOpening",
            x_start=900,
            z_start=0,
            width=1000.0,
            height=2100.0,
        )
        self.pump_gui_events()

        proxy = opening.ViewObject.Proxy
        polylines = self._get_line_polylines(proxy)
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertEqual(len(polylines), 3)
        self.assertEqual(len(polylines[0]), 2)
        self.assertEqual(len(polylines[1]), 2)
        self.assertGreater(len(polylines[2]), 2)
        self.assertTrue(polylines[0][0].isEqual(polylines[1][0], 1e-6))
