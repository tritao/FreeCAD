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

try:
    import FreeCADGui

    GUI_AVAILABLE = FreeCADGui.getMainWindow() is not None
except (ImportError, AttributeError):
    GUI_AVAILABLE = False


class SavedViewGuiTests(unittest.TestCase):
    def setUp(self):
        if not GUI_AVAILABLE:
            self.skipTest("GUI not available")

        self.doc = FreeCAD.newDocument("SavedViewGuiTests")
        self.file_name = os.path.join(tempfile.gettempdir(), "SavedViewGuiTests.FCStd")
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.updateGui()
        self.view = FreeCADGui.getDocument(self.doc.Name).ActiveView
        self.view.setAnimationEnabled(False)
        FreeCADGui.Selection.clearSelection()

    def tearDown(self):
        if GUI_AVAILABLE:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.updateGui()

        if self.doc and self.doc.Name in FreeCAD.listDocuments():
            if self.view and self.view.hasClippingPlane():
                for obj in self.doc.Objects:
                    if obj.TypeId == "App::ClippingPlane":
                        self.select_object(obj)
                        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
                        FreeCADGui.updateGui()
                        break
            FreeCAD.closeDocument(self.doc.Name)
        self.doc = None

        if os.path.exists(self.file_name):
            os.remove(self.file_name)

    def create_clip_plane(self, name="Clip"):
        plane = self.doc.addObject("App::ClippingPlane", name)
        FreeCADGui.updateGui()
        return plane

    def create_saved_view(self):
        FreeCADGui.runCommand("Std_CreateSavedView", 0)
        FreeCADGui.updateGui()
        saved = self.doc.Objects[-1]
        self.assertEqual(saved.TypeId, "App::SavedView")
        return saved

    def select_object(self, obj):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, obj.Name)
        FreeCADGui.updateGui()

    def testCreateCommandCapturesClipPlaneAndCamera(self):
        plane = self.create_clip_plane()
        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        self.view.viewTop()
        FreeCADGui.updateGui()

        saved = self.create_saved_view()

        self.assertEqual(saved.ClipPlane, plane)
        self.assertTrue(saved.CameraState)

    def testApplyCommandRestoresClipPlaneWithoutTouchingDocument(self):
        plane = self.create_clip_plane()
        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        self.view.viewTop()
        FreeCADGui.updateGui()

        saved = self.create_saved_view()
        self.doc.saveAs(self.file_name)
        self.assertFalse(self.doc.isTouched())

        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        self.view.viewBottom()
        FreeCADGui.updateGui()
        self.assertFalse(self.view.hasClippingPlane())

        self.select_object(saved)
        FreeCADGui.runCommand("Std_ApplySavedView", 0)
        FreeCADGui.updateGui()

        self.assertTrue(self.view.hasClippingPlane())
        self.assertEqual(self.view.getCamera(), saved.CameraState)
        self.assertFalse(self.doc.isTouched())

    def testUpdateCommandCapturesCurrentCamera(self):
        saved = self.create_saved_view()
        self.view.viewBottom()
        FreeCADGui.updateGui()

        self.select_object(saved)
        FreeCADGui.runCommand("Std_UpdateSavedView", 0)
        FreeCADGui.updateGui()

        self.assertEqual(self.view.getCamera(), saved.CameraState)
