# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD Project Association
# SPDX-FileCopyrightText: 2025 Furgo
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

import FreeCAD as App
import FreeCADGui as Gui
import Arch
import ArchOpeningConstruction
import ArchSectionPlane
import Draft
from types import SimpleNamespace
from bimtests import TestArchBaseGui
from bimcommands.BimWindow import Arch_Window


class TestArchWindowGui(TestArchBaseGui.TestArchBaseGui):

    def test_interactive_builtin_preset_uses_atomic_construction(self):
        from ArchWindowPresets import WindowPresets

        command = Arch_Window()
        command.doc = self.document
        command.sel = []
        command.Preset = WindowPresets.index("Fixed")
        command.librarypresets = []
        command.Include = False
        command.baseFace = None
        command.SillHeight = 900
        command.wparams = ["Width", "Height", "H1", "H2", "H3", "W1", "W2", "O1", "O2"]
        command.Width = 900
        command.Height = 1200
        command.H1 = command.H2 = command.H3 = 50
        command.W1 = command.W2 = 50
        command.O1 = command.O2 = 0
        command.wp = SimpleNamespace(
            u=App.Vector(1, 0, 0),
            v=App.Vector(0, 1, 0),
            axis=App.Vector(0, 0, 1),
            _restore=lambda: None,
        )
        command.tracker = SimpleNamespace(off=lambda: None, finalize=lambda: None)

        command.getPoint(App.Vector(500, 0, 0))
        opening = next(obj for obj in self.document.Objects if Draft.getType(obj) == "Window")
        self.assertEqual("Window", opening.IfcType)
        self.assertAlmostEqual(900.0, opening.Width.Value)
        self.assertFalse(opening.Shape.isNull())

        opening_name = opening.Name
        self.document.undo()
        self.document.recompute()
        self.assertIsNone(self.document.getObject(opening_name))

    def test_standard_and_hosted_opening_creation_have_semantic_parity(self):
        """Equivalent bases produce equivalent openings through both consumers."""

        first_base = Draft.make_rectangle(900, 1200)
        second_base = Draft.make_rectangle(900, 1200)
        second_base.Placement.Base = App.Vector(1500, 0, 0)
        self.document.recompute()

        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(first_base)
        command = Arch_Window()
        command.Activated()
        standard = next(
            obj
            for obj in self.document.Objects
            if Draft.getType(obj) == "Window" and obj.Base is first_base
        )

        hosted = ArchOpeningConstruction.construct_opening_from_base(
            self.document,
            second_base,
            ArchOpeningConstruction.OpeningConstructionSpec(),
            transaction_name="Create Hosted Opening",
        )

        self.assertEqual(standard.IfcType, hosted.IfcType)
        self.assertEqual(standard.WindowParts, hosted.WindowParts)
        self.assertAlmostEqual(standard.Shape.Volume, hosted.Shape.Volume, delta=1e-6)
        self.assertEqual(len(standard.Shape.Solids), len(hosted.Shape.Solids))

        hosted_name = hosted.Name
        self.document.undo()
        self.document.recompute()
        self.assertIsNone(self.document.getObject(hosted_name))
        self.assertIsNotNone(self.document.getObject(standard.Name))

    def test_opening_construction_rejects_invalid_dimensions_before_mutation(self):
        initial_names = {obj.Name for obj in self.document.Objects}
        with self.assertRaises(ArchOpeningConstruction.OpeningConstructionError):
            ArchOpeningConstruction.construct_opening_from_base(
                self.document,
                None,
                ArchOpeningConstruction.OpeningConstructionSpec(width=0, height=1200),
                transaction_name="Reject Opening",
            )
        self.assertEqual(initial_names, {obj.Name for obj in self.document.Objects})

    def test_window_and_door_presets_use_the_same_atomic_construction(self):
        """Built-in Window and Door presets share validation and transactions."""

        window = ArchOpeningConstruction.construct_preset_opening(
            self.document,
            ArchOpeningConstruction.OpeningPresetSpec(
                "Fixed", 900, 1200, 50, 50, 50, 50, 50, 0, 0
            ),
            placement=App.Placement(App.Vector(0, 0, 0), App.Rotation()),
            transaction_name="Create Window Preset",
        )
        door = ArchOpeningConstruction.construct_preset_opening(
            self.document,
            ArchOpeningConstruction.OpeningPresetSpec(
                "Simple door", 900, 2100, 50, 50, 50, 50, 50, 0, 0
            ),
            placement=App.Placement(App.Vector(1500, 0, 0), App.Rotation()),
            transaction_name="Create Door Preset",
        )

        self.assertEqual("Window", window.IfcType)
        self.assertEqual("Door", door.IfcType)
        self.assertAlmostEqual(900.0, window.Width.Value)
        self.assertAlmostEqual(900.0, door.Width.Value)
        self.assertFalse(window.Shape.isNull())
        self.assertFalse(door.Shape.isNull())

        door_name = door.Name
        self.document.undo()
        self.document.recompute()
        self.assertIsNone(self.document.getObject(door_name))
        self.assertIsNotNone(self.document.getObject(window.Name))

    def test_preset_validation_happens_before_document_mutation(self):
        initial_names = {obj.Name for obj in self.document.Objects}
        with self.assertRaises(ArchOpeningConstruction.OpeningConstructionError):
            ArchOpeningConstruction.construct_preset_opening(
                self.document,
                ArchOpeningConstruction.OpeningPresetSpec(
                    "Simple door", 0, 2100, 50, 50, 50, 50, 50, 0, 0
                ),
                transaction_name="Reject Door Preset",
            )
        self.assertEqual(initial_names, {obj.Name for obj in self.document.Objects})

    def test_change_window_opening(self):
        """Tests if changes to a window opening touches the window's chain of hosts"""

        # Create a wall, a window, a level and a section.
        points = [App.Vector(0.0, 0.0, 0.0), App.Vector(2000.0, 0.0, 0.0)]
        line = Draft.make_wire(points)
        wall = Arch.makeWall(line, height=2000)
        wpl = App.Placement(App.Vector(500, 0, 1500), App.Vector(1, 0, 0), -90)
        win = Arch.makeWindowPreset(
            "Open 1-pane",
            width=1000.0,
            height=1000.0,
            h1=50.0,
            h2=50.0,
            h3=50.0,
            w1=100.0,
            w2=50.0,
            o1=0.0,
            o2=50.0,
            placement=wpl,
        )
        win.Hosts = [wall]
        level = Arch.makeFloor()
        level.addObject(wall)
        section = Arch.makeSectionPlane(level)
        App.ActiveDocument.recompute()

        # Change opening from 0 to 50 (= 45 degrees):
        svg = ArchSectionPlane.getSVG(section)
        win.Opening = 50
        App.ActiveDocument.recompute()
        svg_new = ArchSectionPlane.getSVG(section)
        self.assertNotEqual(svg, svg_new)

        # Invert opening:
        svg = svg_new
        win.ViewObject.Proxy.invertOpening()
        App.ActiveDocument.recompute()
        svg_new = ArchSectionPlane.getSVG(section)
        self.assertNotEqual(svg, svg_new)

        # Invert hinge:
        svg = svg_new
        win.ViewObject.Proxy.invertHinge()
        App.ActiveDocument.recompute()
        svg_new = ArchSectionPlane.getSVG(section)
        self.assertNotEqual(svg, svg_new)
