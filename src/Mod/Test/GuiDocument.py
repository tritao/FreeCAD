# SPDX-License-Identifier: LGPL-2.1-or-later
"""**************************************************************************
*                                                                          *
*   Copyright (c) 2024 Ondsel <development@ondsel.com>                     *
*                                                                          *
*   This file is part of FreeCAD.                                          *
*                                                                          *
*   FreeCAD is free software: you can redistribute it and/or modify it     *
*   under the terms of the GNU Lesser General Public License as            *
*   published by the Free Software Foundation, either version 2.1 of the   *
*   License, or (at your option) any later version.                        *
*                                                                          *
*   FreeCAD is distributed in the hope that it will be useful, but         *
*   WITHOUT ANY WARRANTY; without even the implied warranty of             *
*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU       *
*   Lesser General Public License for more details.                        *
*                                                                          *
*   You should have received a copy of the GNU Lesser General Public       *
*   License along with FreeCAD. If not, see                                *
*   <https://www.gnu.org/licenses/>.                                       *
*                                                                          *
***************************************************************************/"""

import FreeCAD, FreeCADGui, unittest
from PySide import QtCore, QtGui

# ---------------------------------------------------------------------------
# define the functions to test the FreeCAD Gui Document code
# ---------------------------------------------------------------------------


class TestGuiDocument(unittest.TestCase):
    def setUp(self):
        # Create a new document
        self.doc = FreeCAD.newDocument("TestDoc")

    def tearDown(self):
        self.close_task_dialog("TestDoc")
        # Close the document
        FreeCAD.closeDocument("TestDoc")

    def pump_gui_events(self, timeout_ms=50):
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(int(timeout_ms), loop.quit)
        loop.exec_()

    def close_task_dialog(self, doc_name):
        if doc_name not in FreeCAD.listDocuments():
            return

        gui_doc = FreeCADGui.getDocument(doc_name)
        if gui_doc:
            FreeCADGui.Control.closeDialog(gui_doc)
            self.pump_gui_events()

    def testGetTreeRootObject(self):
        # Create objects at the root level
        group1 = self.doc.addObject("App::DocumentObjectGroup", "Group1")
        group2 = self.doc.addObject("App::DocumentObjectGroup", "Group2")
        obj1 = self.doc.addObject("App::FeaturePython", "RootObject1")
        part1 = self.doc.addObject("App::Part", "Part1")

        # Create App::Parts and groups with objects in them
        part1_obj = part1.newObject("App::FeaturePython", "Part1_Object")
        group3 = group2.newObject("App::DocumentObjectGroup", "Group1")
        group1_obj = group3.newObject("App::FeaturePython", "Group1_Object")

        # Fetch the root objects using getTreeRootObjects
        root_objects = FreeCADGui.getDocument("TestDoc").TreeRootObjects

        # Check if the new function returns the correct root objects
        expected_root_objects = [group1, group2, obj1, part1]
        self.assertEqual(set(root_objects), set(expected_root_objects))

    def testCloseDocumentTaskDialogDoesNotSwitchActiveDocument(self):
        class DummyTaskPanel:
            def __init__(self, title):
                self.form = QtGui.QWidget()
                self.form.setWindowTitle(title)

        second_doc = FreeCAD.newDocument("TestDoc2")
        self.addCleanup(lambda: self.close_task_dialog("TestDoc2"))
        self.addCleanup(
            lambda: FreeCAD.closeDocument("TestDoc2")
            if "TestDoc2" in FreeCAD.listDocuments()
            else None
        )

        gui_doc_1 = FreeCADGui.getDocument(self.doc.Name)
        first_panel = DummyTaskPanel("Doc 1 Task")
        FreeCADGui.Control.showDialog(first_panel, gui_doc_1)
        self.pump_gui_events()

        gui_doc_2 = FreeCADGui.getDocument(second_doc.Name)
        second_panel = DummyTaskPanel("Doc 2 Task")
        FreeCADGui.Control.showDialog(second_panel, gui_doc_2)
        self.pump_gui_events()

        FreeCAD.setActiveDocument(self.doc.Name)
        self.pump_gui_events()

        self.assertEqual(FreeCAD.ActiveDocument.Name, self.doc.Name)
        self.assertEqual(FreeCADGui.ActiveDocument.Document.Name, self.doc.Name)
        self.assertTrue(FreeCADGui.Control.activeDialog(gui_doc_1))
        self.assertTrue(FreeCADGui.Control.activeDialog(gui_doc_2))
        self.assertTrue(FreeCADGui.Control.activeDialog(FreeCADGui.ActiveDocument))

        FreeCADGui.Control.closeDialog(gui_doc_1)
        self.pump_gui_events()

        self.assertEqual(FreeCAD.ActiveDocument.Name, self.doc.Name)
        self.assertEqual(FreeCADGui.ActiveDocument.Document.Name, self.doc.Name)
        self.assertFalse(FreeCADGui.Control.activeDialog(gui_doc_1))
        self.assertTrue(FreeCADGui.Control.activeDialog(gui_doc_2))
        self.assertFalse(FreeCADGui.Control.activeDialog(FreeCADGui.ActiveDocument))

        self.close_task_dialog("TestDoc2")
