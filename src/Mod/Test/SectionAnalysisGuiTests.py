# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileNotice: Part of the FreeCAD project.
################################################################################
#                                                                              #
#   © 2026 FreeCAD contributors                                                #
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

import os
import unittest

import FreeCAD

try:
    import FreeCADGui

    GUI_AVAILABLE = FreeCADGui.getMainWindow() is not None
except (ImportError, AttributeError):
    GUI_AVAILABLE = False

HEADLESS_OFFSCREEN = os.environ.get("QT_QPA_PLATFORM") == "offscreen"


@unittest.skipIf(
    HEADLESS_OFFSCREEN,
    "SectionAnalysis GUI smoke test is unstable in offscreen Qt mode",
)
class SectionAnalysisGuiTests(unittest.TestCase):
    def setUp(self):
        if not GUI_AVAILABLE:
            self.skipTest("GUI not available")

        self.active_workbench = FreeCADGui.activeWorkbench()
        self.doc = FreeCAD.newDocument("SectionAnalysisGuiTests")
        FreeCADGui.activateWorkbench("PartWorkbench")
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.updateGui()
        FreeCADGui.Selection.clearSelection()

    def tearDown(self):
        if GUI_AVAILABLE:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.updateGui()
            if self.active_workbench:
                FreeCADGui.activateWorkbench(self.active_workbench.name())

        if self.doc and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)
        self.doc = None

    def select_object(self, obj):
        FreeCADGui.Selection.addSelection(self.doc.Name, obj.Name)
        FreeCADGui.updateGui()

    def testCreateCommandBuildsSectionAnalysis(self):
        plane = self.doc.addObject("App::ClippingPlane", "Clip")
        plane.Placement.Base = FreeCAD.Vector(0, 0, 5)
        box = self.doc.addObject("Part::Box", "Box")
        box.Length = 10
        box.Width = 10
        box.Height = 10
        self.doc.recompute()

        self.select_object(plane)
        self.select_object(box)
        self.assertIn("Part_SectionAnalysis", FreeCADGui.listCommands())
        FreeCADGui.runCommand("Part_SectionAnalysis", 0)
        FreeCADGui.updateGui()
        self.doc.recompute()

        analysis = self.doc.Objects[-1]
        self.assertEqual(analysis.TypeId, "Part::SectionAnalysis")
        self.assertEqual(analysis.ClippingPlane.Name, "Clip")
        self.assertEqual([obj.Name for obj in analysis.Sources], ["Box"])
        self.assertFalse(analysis.Shape.isNull())
        self.assertGreater(len(analysis.Shape.Edges), 0)
