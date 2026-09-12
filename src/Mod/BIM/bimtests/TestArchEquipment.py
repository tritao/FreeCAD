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

import Arch
import FreeCAD as App
import Part
from bimtests import TestArchBase


class TestArchEquipment(TestArchBase.TestArchBase):

    def test_makeEquipment(self):
        """Test the makeEquipment function."""

        obj = Arch.makeEquipment()
        self.assertIsNotNone(obj, "makeEquipment failed to create an object")
        self.assertEqual(obj.Label, "Equipment", "Incorrect default label for Equipment")

    def testEquipment(self):
        box = App.ActiveDocument.addObject("Part::Box", "Box")
        box.Length = 500
        box.Width = 2000
        box.Height = 600
        equip = Arch.makeEquipment(box)
        self.assertTrue(equip, "Arch Equipment failed")

    def test_equipment_get_footprint_uses_plan_slice_and_flattens_to_base(self):
        box = self.document.addObject("Part::Box", "Box")
        box.Length = 500
        box.Width = 2000
        box.Height = 1200

        equip = Arch.makeEquipment(box)
        self.document.recompute()

        faces = equip.Proxy.getFootprint(equip)
        self.assertEqual(1, len(faces))
        self.assertAlmostEqual(500 * 2000, faces[0].Area, delta=0.1)
        self.assertAlmostEqual(
            equip.Shape.BoundBox.ZMin,
            faces[0].BoundBox.ZMin,
            delta=0.001,
        )
        self.assertAlmostEqual(
            equip.Shape.BoundBox.ZMin,
            faces[0].BoundBox.ZMax,
            delta=0.001,
        )

    def test_equipment_get_footprint_prefers_authored_plan_symbols(self):
        box = self.document.addObject("Part::Box", "Box")
        box.Length = 500
        box.Width = 2000
        box.Height = 1200

        plan = self.document.addObject("Part::Feature", "PlanSymbol")
        plan.Shape = Part.makePlane(900, 450, App.Vector(0, 0, 0))

        equip = Arch.makeEquipment(box)
        equip.PlanSymbols = [plan]
        self.document.recompute()

        faces = equip.Proxy.getFootprint(equip)
        self.assertEqual(1, len(faces))
        self.assertAlmostEqual(900 * 450, faces[0].Area, delta=0.1)
        self.assertAlmostEqual(equip.Shape.BoundBox.ZMin, faces[0].BoundBox.ZMin, delta=0.001)

    def test_equipment_get_footprint_builds_faces_from_closed_plan_symbol_wires(self):
        box = self.document.addObject("Part::Box", "Box")
        box.Length = 500
        box.Width = 2000
        box.Height = 1200

        plan = self.document.addObject("Part::Feature", "PlanWireSymbol")
        plan.Shape = Part.Wire(
            [
                Part.makeLine(App.Vector(0, 0, 0), App.Vector(900, 0, 0)),
                Part.makeLine(App.Vector(900, 0, 0), App.Vector(900, 450, 0)),
                Part.makeLine(App.Vector(900, 450, 0), App.Vector(0, 450, 0)),
                Part.makeLine(App.Vector(0, 450, 0), App.Vector(0, 0, 0)),
            ],
        )

        equip = Arch.makeEquipment(box)
        equip.PlanSymbols = [plan]
        self.document.recompute()

        faces = equip.Proxy.getFootprint(equip)
        self.assertEqual(1, len(faces))
        self.assertAlmostEqual(900 * 450, faces[0].Area, delta=0.1)
        self.assertAlmostEqual(equip.Shape.BoundBox.ZMin, faces[0].BoundBox.ZMin, delta=0.001)
