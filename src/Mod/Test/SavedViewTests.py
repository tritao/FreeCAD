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


class SavedViewTests(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("SavedViewTests")
        self.file_name = os.path.join(tempfile.gettempdir(), "SavedViewTests.FCStd")

    def tearDown(self):
        if self.doc and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)
        self.doc = None
        if os.path.exists(self.file_name):
            os.remove(self.file_name)

    def testCreateSavedView(self):
        obj = self.doc.addObject("App::SavedView", "Saved")
        self.assertEqual(obj.TypeId, "App::SavedView")
        self.assertTrue(obj.RestoreCamera)
        self.assertTrue(obj.RestoreVisibility)
        self.assertTrue(obj.RestoreClipping)
        self.assertIsNone(obj.ClipPlane)

    def testSaveRestoreSavedView(self):
        plane = self.doc.addObject("App::ClippingPlane", "Clip")
        saved = self.doc.addObject("App::SavedView", "Saved")
        saved.CameraState = "OrthographicCamera { position 1 2 3 }"
        saved.VisibilityState = {"Clip": "False", "Other": "True"}
        saved.RestoreCamera = False
        saved.RestoreVisibility = True
        saved.RestoreClipping = False
        saved.ClipPlane = plane

        self.doc.saveAs(self.file_name)
        FreeCAD.closeDocument(self.doc.Name)
        self.doc = FreeCAD.open(self.file_name)

        restored = self.doc.getObject("Saved")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.CameraState, "OrthographicCamera { position 1 2 3 }")
        self.assertEqual(restored.VisibilityState["Clip"], "False")
        self.assertEqual(restored.VisibilityState["Other"], "True")
        self.assertFalse(restored.RestoreCamera)
        self.assertTrue(restored.RestoreVisibility)
        self.assertFalse(restored.RestoreClipping)
        self.assertIsNotNone(restored.ClipPlane)
        self.assertEqual(restored.ClipPlane.Name, "Clip")
