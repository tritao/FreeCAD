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
import tempfile
import unittest

import FreeCAD


class ClipPlaneTests(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("ClipPlaneTests")
        self.file_name = os.path.join(tempfile.gettempdir(), "ClipPlaneTests.FCStd")

    def tearDown(self):
        if self.doc and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)
        self.doc = None
        if os.path.exists(self.file_name):
            os.remove(self.file_name)

    def testCreateClipPlane(self):
        obj = self.doc.addObject("App::ClippingPlane", "Clip")
        self.assertEqual(obj.TypeId, "App::ClippingPlane")
        self.assertFalse(obj.Reverse)
        self.assertEqual(obj.ScopeMode, "WholeDocument")
        self.assertEqual(list(obj.Targets), [])
        self.assertTrue(hasattr(obj, "Placement"))

    def testSaveRestoreClipPlane(self):
        obj = self.doc.addObject("App::ClippingPlane", "Clip")
        target = self.doc.addObject("App::ClippingPlane", "Target")
        obj.Reverse = True
        obj.ScopeMode = "Exclude"
        obj.Targets = [target]
        obj.Placement.Base = FreeCAD.Vector(1, 2, 3)

        self.doc.saveAs(self.file_name)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = FreeCAD.open(self.file_name)

        restored = self.doc.getObject("Clip")
        self.assertIsNotNone(restored)
        self.assertTrue(restored.Reverse)
        self.assertEqual(restored.ScopeMode, "Exclude")
        self.assertEqual([target.Name for target in restored.Targets], ["Target"])
        self.assertAlmostEqual(restored.Placement.Base.x, 1.0)
        self.assertAlmostEqual(restored.Placement.Base.y, 2.0)
        self.assertAlmostEqual(restored.Placement.Base.z, 3.0)
