# ***************************************************************************
# *   Copyright (c) 2006 Werner Mayer <werner.wm.mayer@gmx.de>              *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************/

# Workbench test module

import FreeCAD, FreeCADGui, os, unittest
import tempfile

from PySide import QtWidgets, QtCore
from PySide.QtWidgets import QApplication


class CallableCheckWarning:
    def __call__(self):
        diag = QApplication.activeModalWidget()
        if diag:
            QtCore.QTimer.singleShot(0, diag, QtCore.SLOT("accept()"))


class WorkbenchTestCase(unittest.TestCase):
    def setUp(self):
        self.Active = FreeCADGui.activeWorkbench()
        FreeCAD.Console.PrintLog(FreeCADGui.activeWorkbench().name())

    def testActivate(self):
        wbs = FreeCADGui.listWorkbenches()
        # this gives workbenches a possibility to detect that we're under test environment
        FreeCAD.TestEnvironment = True
        for i in wbs:
            try:
                print("Activate workbench '{}'".format(i))
                cobj = CallableCheckWarning()
                QtCore.QTimer.singleShot(500, cobj)
                if FreeCADGui.activeWorkbench().name() != i:
                    success = FreeCADGui.activateWorkbench(i)
                else:
                    # Cannot test activation of an already-active workbench
                    success = True
                FreeCAD.Console.PrintLog(
                    "Active: " + FreeCADGui.activeWorkbench().name() + " Expected: " + i + "\n"
                )
                self.assertTrue(success, "Test on activating workbench {0} failed".format(i))
            except Exception as e:
                self.fail("Loading of workbench '{0}' failed: {1}".format(i, e))
        del FreeCAD.TestEnvironment

    def testHandler(self):
        import __main__

        class UnitWorkbench(__main__.Workbench):
            MenuText = "Unittest"
            ToolTip = "Unittest"

            def Initialize(self):
                cmds = ["Test_Test"]
                self.appendToolbar("My Unittest", cmds)

            def GetClassName(self):
                return "Gui::PythonWorkbench"

        FreeCADGui.addWorkbench(UnitWorkbench())
        wbs = FreeCADGui.listWorkbenches()
        self.assertTrue("UnitWorkbench" in wbs, "Test on adding workbench handler failed")
        FreeCADGui.activateWorkbench("UnitWorkbench")
        FreeCADGui.updateGui()
        self.assertTrue(
            FreeCADGui.activeWorkbench().name() == "UnitWorkbench",
            "Test on loading workbench 'Unittest' failed",
        )
        FreeCADGui.removeWorkbench("UnitWorkbench")
        wbs = FreeCADGui.listWorkbenches()
        self.assertTrue(not "UnitWorkbench" in wbs, "Test on removing workbench handler failed")

    def testToolbarOptions(self):
        import __main__

        toolbar_key = "wb:UnitToolbarOptionsWorkbench:PythonToolbar"
        view_toolbar_key = "wb:UnitToolbarOptionsWorkbench:PythonViewToolbar"
        panel_toolbar_key = "wb:UnitToolbarOptionsWorkbench:PythonPanelToolbar"
        doc = FreeCAD.newDocument("ToolbarOptions")
        visibility_group = FreeCAD.ParamGet("User parameter:BaseApp/MainWindow/Toolbars")
        bool_map = {key: visibility_group.GetBool(key) for key in visibility_group.GetBools()}

        class UnitToolbarOptionsWorkbench(__main__.Workbench):
            MenuText = "Toolbar Options"
            ToolTip = "Toolbar Options"

            def Initialize(self):
                cmds = ["Test_Test"]
                self.appendToolbar(
                    "Python Toolbar",
                    cmds,
                    key="PythonToolbar",
                    tier=self.ToolbarTier.Advanced,
                    visibility=self.ToolbarVisibility.Hidden,
                    host=self.ToolbarHost.MainWindow,
                    size=self.ToolbarSize.Slim,
                )
                self.appendToolbar(
                    "Python View Toolbar",
                    cmds,
                    key="PythonViewToolbar",
                    tier=self.ToolbarTier.Secondary,
                    visibility=self.ToolbarVisibility.Hidden,
                    host=self.ToolbarHost.ActiveView,
                    view_host_requirement=self.ToolbarViewHostRequirement.View3D,
                    view_presentation=self.ToolbarViewPresentation.CenteredOverlay,
                    view_overlay_edge=self.ToolbarViewOverlayEdge.Top,
                    view_overlay_edge_persistence=(self.ToolbarViewOverlayEdgePersistence.Shared),
                    size=self.ToolbarSize.Slim,
                )
                self.appendToolbar(
                    "Python Panel Toolbar",
                    cmds,
                    key="PythonPanelToolbar",
                    tier=self.ToolbarTier.Secondary,
                    visibility=self.ToolbarVisibility.Hidden,
                    host=self.ToolbarHost.Panel,
                    panel_role=self.ToolbarPanelRole.ModelTree,
                    size=self.ToolbarSize.Slim,
                )

            def GetClassName(self):
                return "Gui::PythonWorkbench"

        def find_toolbar(key):
            for toolbar in FreeCADGui.getMainWindow().findChildren(QtWidgets.QToolBar):
                if toolbar.property("PersistenceKey") == key:
                    return toolbar
            return None

        try:
            for key in (toolbar_key, view_toolbar_key, panel_toolbar_key):
                visibility_group.RemBool(key)
            FreeCADGui.addWorkbench(UnitToolbarOptionsWorkbench())
            self.assertTrue(FreeCADGui.activateWorkbench("UnitToolbarOptionsWorkbench"))
            FreeCADGui.updateGui()
            QApplication.processEvents()

            toolbar = find_toolbar(toolbar_key)
            self.assertIsNotNone(toolbar)
            self.assertEqual(toolbar.property("Tier"), "advanced")
            self.assertEqual(toolbar.property("Host"), "main-window")
            self.assertEqual(toolbar.property("ToolbarSize"), "slim")
            self.assertFalse(toolbar.isVisible())
            self.assertFalse(toolbar.toggleViewAction().isChecked())
            self.assertTrue(toolbar.toggleViewAction().isVisible())

            view_toolbar = find_toolbar(view_toolbar_key)
            self.assertIsNotNone(view_toolbar)
            self.assertEqual(view_toolbar.property("Tier"), "secondary")
            self.assertEqual(view_toolbar.property("Host"), "view")
            self.assertEqual(view_toolbar.property("ViewPresentation"), "centered-overlay")
            self.assertEqual(view_toolbar.property("ViewOverlayEdge"), "top")
            self.assertEqual(view_toolbar.property("ViewOverlayEdgePersistence"), "shared")
            self.assertEqual(view_toolbar.property("ToolbarSize"), "slim")
            self.assertFalse(view_toolbar.isVisible())
            self.assertFalse(view_toolbar.toggleViewAction().isChecked())
            self.assertTrue(view_toolbar.toggleViewAction().isVisible())
            self.assertTrue(view_toolbar.toggleViewAction().isEnabled())

            panel_toolbar = find_toolbar(panel_toolbar_key)
            self.assertIsNotNone(panel_toolbar)
            self.assertEqual(panel_toolbar.property("Tier"), "secondary")
            self.assertEqual(panel_toolbar.property("Host"), "panel")
            self.assertEqual(panel_toolbar.property("PanelRole"), "model-tree")
            self.assertEqual(panel_toolbar.property("ToolbarSize"), "slim")
            self.assertFalse(panel_toolbar.isVisible())
            self.assertFalse(panel_toolbar.toggleViewAction().isChecked())
            self.assertTrue(panel_toolbar.toggleViewAction().isVisible())
            self.assertTrue(panel_toolbar.toggleViewAction().isEnabled())
        finally:
            for key in (toolbar_key, view_toolbar_key, panel_toolbar_key):
                visibility_group.RemBool(key)
                if key in bool_map:
                    visibility_group.SetBool(key, bool_map[key])
            FreeCADGui.removeWorkbench("UnitToolbarOptionsWorkbench")
            FreeCAD.closeDocument(doc.Name)

    def testConfigureToolbar(self):
        toolbar = FreeCADGui.UiLoader().createWidget("Gui::ToolBar")
        toolbar.setObjectName("Python External Toolbar")
        toolbar.setWindowTitle("Python External Toolbar")
        main_window = FreeCADGui.getMainWindow()
        main_window.addToolBar(toolbar)

        try:
            FreeCADGui.configureToolbar(
                toolbar,
                key="shared:Python External Toolbar",
                tier=FreeCADGui.Workbench.ToolbarTier.Contextual,
                visibility=FreeCADGui.Workbench.ToolbarVisibility.Unavailable,
                host=FreeCADGui.Workbench.ToolbarHost.ActiveView,
                view_host_requirement=FreeCADGui.Workbench.ToolbarViewHostRequirement.View3D,
                view_presentation=FreeCADGui.Workbench.ToolbarViewPresentation.CenteredOverlay,
                view_overlay_edge=FreeCADGui.Workbench.ToolbarViewOverlayEdge.Bottom,
                view_overlay_edge_persistence=(
                    FreeCADGui.Workbench.ToolbarViewOverlayEdgePersistence.Shared
                ),
                size=FreeCADGui.Workbench.ToolbarSize.Slim,
                menu_visible=False,
            )

            self.assertEqual(toolbar.property("PersistenceKey"), "shared:Python External Toolbar")
            self.assertEqual(toolbar.property("Tier"), "contextual")
            self.assertEqual(toolbar.property("Host"), "view")
            self.assertEqual(toolbar.property("ViewPresentation"), "centered-overlay")
            self.assertEqual(toolbar.property("ViewOverlayEdge"), "bottom")
            self.assertEqual(toolbar.property("ViewOverlayEdgePersistence"), "shared")
            self.assertEqual(toolbar.property("ToolbarSize"), "slim")
            self.assertEqual(
                toolbar.toggleViewAction().property("DefaultVisibility"),
                int(FreeCADGui.Workbench.ToolbarVisibility.Unavailable),
            )
            self.assertFalse(toolbar.toggleViewAction().isVisible())
            self.assertEqual(toolbar.toggleViewAction().text(), "")
        finally:
            main_window.removeToolBar(toolbar)
            toolbar.deleteLater()

    def testDraftAndBimToolbarsUseViewOverlayDefaults(self):
        doc = FreeCAD.newDocument("DraftToolbarDefaults")

        def find_toolbar(key):
            for toolbar in FreeCADGui.getMainWindow().findChildren(QtWidgets.QToolBar):
                if toolbar.property("PersistenceKey") == key:
                    return toolbar
            return None

        try:
            self.assertTrue(FreeCADGui.activateWorkbench("DraftWorkbench"))
            FreeCADGui.updateGui()
            QApplication.processEvents()

            draft_snap = find_toolbar("shared:Draft Snap")
            self.assertIsNotNone(draft_snap)
            self.assertEqual(draft_snap.property("Host"), "view")
            self.assertEqual(draft_snap.property("ViewPresentation"), "centered-overlay")
            self.assertEqual(draft_snap.property("ViewOverlayEdge"), "bottom")
            self.assertEqual(draft_snap.property("ViewOverlayEdgePersistence"), "shared")
            self.assertEqual(draft_snap.property("ToolbarSize"), "slim")
            self.assertEqual(
                getattr(draft_snap.parentWidget(), "property", lambda *_: None)("overlayEdge"),
                "bottom",
            )

            draft_tray = getattr(getattr(FreeCADGui, "draftToolBar", None), "tray", None)
            self.assertIsNotNone(draft_tray)
            self.assertEqual(draft_tray.property("PersistenceKey"), "shared:Draft tray")
            self.assertEqual(draft_tray.property("Host"), "view")
            self.assertEqual(draft_tray.property("ViewPresentation"), "centered-overlay")
            self.assertEqual(draft_tray.property("ViewOverlayEdge"), "bottom")
            self.assertEqual(draft_tray.property("ViewOverlayEdgePersistence"), "shared")
            self.assertEqual(draft_tray.property("ToolbarSize"), "slim")
            self.assertFalse(draft_tray.toggleViewAction().isVisible())
            self.assertEqual(draft_tray.toggleViewAction().text(), "")
            draft_tray.show()
            QApplication.processEvents()
            self.assertEqual(
                getattr(draft_tray.parentWidget(), "property", lambda *_: None)("overlayEdge"),
                "bottom",
            )

            self.assertTrue(FreeCADGui.activateWorkbench("BIMWorkbench"))
            FreeCADGui.updateGui()
            QApplication.processEvents()

            bim_snap = find_toolbar("shared:Draft Snap")
            self.assertIsNotNone(bim_snap)
            self.assertEqual(bim_snap.property("Host"), "view")
            self.assertEqual(bim_snap.property("ViewPresentation"), "centered-overlay")
            self.assertEqual(bim_snap.property("ViewOverlayEdge"), "bottom")
            self.assertEqual(bim_snap.property("ViewOverlayEdgePersistence"), "shared")
            self.assertEqual(bim_snap.property("ToolbarSize"), "slim")
            self.assertEqual(
                getattr(bim_snap.parentWidget(), "property", lambda *_: None)("overlayEdge"),
                "bottom",
            )
        finally:
            FreeCAD.closeDocument(doc.Name)

    def testInvalidType(self):
        class MyExtWorkbench(FreeCADGui.Workbench):
            def Initialize(self):
                pass

            def GetClassName(self):
                return "App::Extension"

        FreeCADGui.addWorkbench(MyExtWorkbench())
        with self.assertRaises(TypeError):
            FreeCADGui.activateWorkbench("MyExtWorkbench")
        FreeCADGui.removeWorkbench("MyExtWorkbench")

    def tearDown(self):
        FreeCADGui.activateWorkbench(self.Active.name())
        FreeCAD.Console.PrintLog(self.Active.name())


class CommandTestCase(unittest.TestCase):
    def testPR6889(self):
        # Fixes a crash
        TempPath = tempfile.gettempdir()
        macroName = TempPath + os.sep + "testmacro.py"
        macroFile = open(macroName, "w")
        macroFile.write("print ('Hello, World!')")
        macroFile.close()

        name = FreeCADGui.Command.createCustomCommand(macroName)
        cmd = FreeCADGui.Command.get(name)
        cmd.run()


class TestNavigationStyle(unittest.TestCase):
    def setUp(self):
        self.Doc = FreeCAD.newDocument("CreateTest")

    def testInvalidStyle(self):
        FreeCADGui.getDocument(self.Doc).ActiveView.setNavigationType("App::Extension")
        self.assertNotEqual(
            FreeCADGui.getDocument(self.Doc).ActiveView.getNavigationType(), "App::Extension"
        )

    def tearDown(self):
        FreeCAD.closeDocument("CreateTest")
