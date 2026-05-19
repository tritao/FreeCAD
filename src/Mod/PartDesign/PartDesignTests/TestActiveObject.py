# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2024 Werner Mayer <wmayer[at]users.sourceforge.net>     *
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

import unittest
import os
import tempfile

import FreeCAD
import FreeCADGui
from pivy import coin

""" Test active object list """


class TestActiveObject(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("PartDesignTestSketch")
        self.doc.UndoMode = True
        self.temp_files = []

    def _body_mode_signature(self, body):
        sa = coin.SoSearchAction()
        sa.setType(coin.SoSwitch.getClassTypeId())
        sa.setInterest(coin.SoSearchAction.ALL)
        sa.apply(body.ViewObject.RootNode)
        paths = sa.getPaths()

        mode_switch = None
        for index in range(paths.getLength()):
            candidate = paths.get(index).getTail()
            if mode_switch is None or candidate.getNumChildren() > mode_switch.getNumChildren():
                mode_switch = candidate

        self.assertIsNotNone(mode_switch)
        active_child = mode_switch.whichChild.getValue()
        self.assertGreaterEqual(active_child, 0)

        child = mode_switch.getChild(active_child)
        return child.getTypeId().getName().getString(), child.getName().getString()

    def _make_body_with_sketch(self, name="Body"):
        body = self.doc.addObject("PartDesign::Body", name)
        body.newObject("Sketcher::SketchObject", "Sketch")
        self.doc.recompute()
        FreeCADGui.updateGui()
        return body

    def testBodyDisplayModeResyncsOnShow(self):
        FreeCADGui.activateView("Gui::View3DInventor", True)

        body = self._make_body_with_sketch()

        through_signature = self._body_mode_signature(body)
        self.assertNotEqual(body.getSubObjects(1), [])  # GS_SELECT

        body.ViewObject.DisplayModeBody = "Tip"
        FreeCADGui.updateGui()
        tip_signature = self._body_mode_signature(body)
        self.assertNotEqual(through_signature, tip_signature)
        self.assertEqual(body.getSubObjects(1), [])

        body.ViewObject.Visibility = False
        FreeCADGui.updateGui()
        body.ViewObject.Visibility = True
        FreeCADGui.updateGui()
        self.assertEqual(body.ViewObject.DisplayModeBody, "Tip")
        self.assertEqual(self._body_mode_signature(body), tip_signature)
        self.assertEqual(body.getSubObjects(1), [])

        body.ViewObject.DisplayModeBody = "Through"
        FreeCADGui.updateGui()
        self.assertEqual(self._body_mode_signature(body), through_signature)
        self.assertNotEqual(body.getSubObjects(1), [])

        body.ViewObject.Visibility = False
        FreeCADGui.updateGui()
        body.ViewObject.Visibility = True
        FreeCADGui.updateGui()
        self.assertEqual(body.ViewObject.DisplayModeBody, "Through")
        self.assertEqual(self._body_mode_signature(body), through_signature)
        self.assertNotEqual(body.getSubObjects(1), [])

    def testBodyDisplayModeRestoresRuntimeState(self):
        FreeCADGui.activateView("Gui::View3DInventor", True)

        body = self._make_body_with_sketch()

        through_signature = self._body_mode_signature(body)

        body.ViewObject.DisplayModeBody = "Tip"
        FreeCADGui.updateGui()
        tip_signature = self._body_mode_signature(body)
        self.assertEqual(body.getSubObjects(1), [])

        handle, filename = tempfile.mkstemp(suffix=".FCStd")
        os.close(handle)
        self.temp_files.append(filename)

        self.doc.saveAs(filename)
        FreeCAD.closeDocument(self.doc.Name)

        self.doc = FreeCAD.openDocument(filename)
        FreeCADGui.getDocument(self.doc.Name)
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.updateGui()

        body = self.doc.Body
        self.assertEqual(body.ViewObject.DisplayModeBody, "Tip")
        self.assertEqual(self._body_mode_signature(body), tip_signature)
        self.assertEqual(body.getSubObjects(1), [])

        body.ViewObject.DisplayModeBody = "Through"
        FreeCADGui.updateGui()
        self.assertEqual(self._body_mode_signature(body), through_signature)
        self.assertNotEqual(body.getSubObjects(1), [])

        self.doc.save()
        FreeCAD.closeDocument(self.doc.Name)

        self.doc = FreeCAD.openDocument(filename)
        FreeCADGui.getDocument(self.doc.Name)
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.updateGui()
        body = self.doc.Body
        self.assertEqual(body.ViewObject.DisplayModeBody, "Through")
        self.assertEqual(self._body_mode_signature(body), through_signature)
        self.assertNotEqual(body.getSubObjects(1), [])

    def testPartBody(self):
        self.doc.openTransaction("Create part")
        part = self.doc.addObject("App::Part", "Part")
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.activeView().setActiveObject("part", part)
        self.doc.commitTransaction()

        self.doc.openTransaction("Create body")
        body = self.doc.addObject("PartDesign::Body", "Body")
        part.addObject(body)
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.activeView().setActiveObject("pdbody", body)
        self.doc.commitTransaction()

        self.doc.undo()  # undo body creation
        self.doc.undo()  # undo part creation

        FreeCADGui.updateGui()

        self.doc.openTransaction("Create body")
        body = self.doc.addObject("PartDesign::Body", "Body")
        FreeCADGui.activateView("Gui::View3DInventor", True)
        FreeCADGui.activeView().setActiveObject("pdbody", body)
        self.doc.commitTransaction()

        FreeCADGui.updateGui()

    def tearDown(self):
        if self.doc and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)
        for filename in self.temp_files:
            if os.path.exists(filename):
                os.remove(filename)
