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

try:
    from pivy import coin

    COIN_AVAILABLE = True
except ImportError:
    COIN_AVAILABLE = False


class ClipPlaneGuiTests(unittest.TestCase):
    def setUp(self):
        if not GUI_AVAILABLE:
            self.skipTest("GUI not available")

        self.doc = FreeCAD.newDocument("ClipPlaneGuiTests")
        self.file_name = os.path.join(tempfile.gettempdir(), "ClipPlaneGuiTests.FCStd")
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.updateGui()
        self.view = FreeCADGui.getDocument(self.doc.Name).ActiveView
        self.active_planes = []
        FreeCADGui.Selection.clearSelection()

    def tearDown(self):
        if GUI_AVAILABLE:
            for plane in reversed(self.active_planes):
                if plane and plane.Name in [obj.Name for obj in self.doc.Objects]:
                    self.select_object(plane)
                    FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
                    FreeCADGui.updateGui()
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.updateGui()

        if self.doc and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)
        self.doc = None

        if os.path.exists(self.file_name):
            os.remove(self.file_name)

    def create_clip_plane(self, name="Clip"):
        plane = self.doc.addObject("App::ClippingPlane", name)
        FreeCADGui.updateGui()
        return plane

    def select_object(self, obj):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, obj.Name)
        FreeCADGui.updateGui()

    def create_scoped_clip_plane(self, target, name="Scoped"):
        plane = self.create_clip_plane(name)
        plane.ScopeMode = "IncludeOnly"
        plane.Targets = [target]
        FreeCADGui.updateGui()
        return plane

    def create_excluded_clip_plane(self, target, name="Excluded"):
        plane = self.create_clip_plane(name)
        plane.ScopeMode = "Exclude"
        plane.Targets = [target]
        FreeCADGui.updateGui()
        return plane

    def find_named_node(self, name):
        if not COIN_AVAILABLE:
            self.skipTest("pivy.coin not available")

        search = coin.SoSearchAction()
        search.setName(name)
        search.setInterest(coin.SoSearchAction.FIRST)
        search.apply(self.view.getSceneGraph())
        path = search.getPath()
        return path.getTail() if path else None

    def count_named_nodes(self, name):
        if not COIN_AVAILABLE:
            self.skipTest("pivy.coin not available")

        search = coin.SoSearchAction()
        search.setName(name)
        search.setInterest(coin.SoSearchAction.ALL)
        search.apply(self.view.getSceneGraph())
        return search.getPaths().getLength()

    def parent_name_for_root(self, obj):
        if not COIN_AVAILABLE:
            self.skipTest("pivy.coin not available")

        search = coin.SoSearchAction()
        search.setNode(obj.ViewObject.RootNode)
        search.setInterest(coin.SoSearchAction.FIRST)
        search.apply(self.view.getSceneGraph())
        path = search.getPath()
        self.assertIsNotNone(path)
        self.assertGreaterEqual(path.getLength(), 2)
        parent = path.getNodeFromTail(1)
        return parent.getName().getString()

    def testCreateCommandCreatesAndActivatesClipPlane(self):
        self.assertFalse(self.view.hasClippingPlane())

        FreeCADGui.runCommand("Std_CreateClippingPlane", 0)
        FreeCADGui.updateGui()

        self.assertEqual(len(self.doc.Objects), 1)
        plane = self.doc.Objects[0]
        self.active_planes = [plane]
        self.assertEqual(plane.TypeId, "App::ClippingPlane")
        self.assertTrue(self.view.hasClippingPlane())

        selection = FreeCADGui.Selection.getSelection(self.doc.Name)
        self.assertEqual(selection, [plane])

    def testToggleCommandDoesNotTouchDocument(self):
        plane = self.create_clip_plane()
        self.doc.saveAs(self.file_name)
        self.assertFalse(self.doc.isTouched())

        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [plane]
        self.assertTrue(self.view.hasClippingPlane())
        self.assertFalse(self.doc.isTouched())

        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = []
        self.assertFalse(self.view.hasClippingPlane())
        self.assertFalse(self.doc.isTouched())

    def testReverseRefreshKeepsClipActive(self):
        plane = self.create_clip_plane()
        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [plane]
        self.assertTrue(self.view.hasClippingPlane())

        plane.Reverse = True
        FreeCADGui.updateGui()
        self.assertTrue(self.view.hasClippingPlane())

        plane.Reverse = False
        FreeCADGui.updateGui()
        self.assertTrue(self.view.hasClippingPlane())

    def testDeletingActivePlaneClearsClip(self):
        plane = self.create_clip_plane()
        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [plane]
        self.assertTrue(self.view.hasClippingPlane())

        self.doc.removeObject(plane.Name)
        FreeCADGui.updateGui()
        self.active_planes = []
        self.assertFalse(self.view.hasClippingPlane())

    def testScopedClipUsesRuntimeNode(self):
        target = self.create_clip_plane("Target")
        other = self.create_clip_plane("Other")
        plane = self.create_scoped_clip_plane(target)

        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [plane]

        self.assertTrue(self.view.hasClippingPlane())

        runtime = self.find_named_node("FCScopedClipPlaneRuntime")
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.getNumChildren(), 2)
        self.assertEqual(runtime.getChild(0).getName().getString(), "FCScopedClipPlane")
        self.assertEqual(self.parent_name_for_root(target), "FCScopedClipPlaneRuntime")
        self.assertNotEqual(self.parent_name_for_root(other), "FCScopedClipPlaneRuntime")

    def testDeletingScopedTargetRefreshesRuntimeNode(self):
        target = self.create_clip_plane("Target")
        plane = self.create_scoped_clip_plane(target)

        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [plane]

        self.doc.removeObject(target.Name)
        FreeCADGui.updateGui()

        self.assertIsNone(self.find_named_node("FCScopedClipPlaneRuntime"))
        self.assertFalse(self.view.hasClippingPlane())

    def testExcludedScopeUsesRuntimeNode(self):
        target = self.create_clip_plane("Target")
        other = self.create_clip_plane("Other")
        plane = self.create_excluded_clip_plane(target)

        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [plane]

        self.assertTrue(self.view.hasClippingPlane())

        runtime = self.find_named_node("FCScopedClipPlaneRuntime")
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.getNumChildren(), 2)
        self.assertNotEqual(self.parent_name_for_root(target), "FCScopedClipPlaneRuntime")
        self.assertEqual(self.parent_name_for_root(other), "FCScopedClipPlaneRuntime")

    def testDeletingExcludedTargetFallsBackToWholeDocumentClip(self):
        target = self.create_clip_plane("Target")
        plane = self.create_excluded_clip_plane(target)

        self.select_object(plane)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [plane]

        self.doc.removeObject(target.Name)
        FreeCADGui.updateGui()

        self.assertIsNone(self.find_named_node("FCScopedClipPlaneRuntime"))
        self.assertTrue(self.view.hasClippingPlane())

    def testMultipleWholeDocumentPlanesStayActive(self):
        first = self.create_clip_plane("First")
        second = self.create_clip_plane("Second")

        self.select_object(first)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()

        self.select_object(second)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [first, second]

        self.assertTrue(self.view.hasClippingPlane())
        self.assertEqual(self.count_named_nodes("FCWholeClipPlaneRuntime"), 2)

        self.select_object(second)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [first]

        self.assertTrue(self.view.hasClippingPlane())
        self.assertEqual(self.count_named_nodes("FCWholeClipPlaneRuntime"), 1)

    def testOverlappingScopedPlanesShareOneWrapper(self):
        target = self.create_clip_plane("Target")
        first = self.create_scoped_clip_plane(target, "First")
        second = self.create_scoped_clip_plane(target, "Second")

        self.select_object(first)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.select_object(second)
        FreeCADGui.runCommand("Std_ActivateClippingPlane", 0)
        FreeCADGui.updateGui()
        self.active_planes = [first, second]

        runtime = self.find_named_node("FCScopedClipPlaneRuntime")
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.getNumChildren(), 3)
        self.assertEqual(runtime.getChild(0).getName().getString(), "FCScopedClipPlane")
        self.assertEqual(runtime.getChild(1).getName().getString(), "FCScopedClipPlane")
        self.assertEqual(self.parent_name_for_root(target), "FCScopedClipPlaneRuntime")
