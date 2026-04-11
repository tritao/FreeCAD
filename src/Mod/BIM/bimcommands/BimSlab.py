# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2017 Yorik van Havre <yorik@uncreated.net>              *
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

"""The BIM Slab command"""

import FreeCAD
import FreeCADGui
from bimcommands import BimArchUtils

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate


class BIM_Slab:

    def __init__(self):
        self.callback = None
        self.view = None

    def GetResources(self):
        return {
            "Pixmap": "BIM_Slab",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Slab", "Slab"),
            "ToolTip": QT_TRANSLATE_NOOP("BIM_Slab", "Creates a slab from a planar shape"),
            "Accel": "S,B",
        }

    def IsActive(self):
        v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        return v

    def Activated(self):
        from draftguitools import gui_tool_utils

        self.removeCallback()
        gui_tool_utils.finish_active_draft_command()
        self.doc = FreeCAD.ActiveDocument
        if self.doc is None:
            return
        sel = BimArchUtils.selectionOf(self.doc)
        if sel:
            self.proceed()
        else:
            if hasattr(FreeCADGui, "draftToolBar"):
                FreeCADGui.draftToolBar.selectUi()
            FreeCAD.Console.PrintMessage(translate("BIM", "Select a planar object") + "\n")
            FreeCAD.activeDraftCommand = self
            self.view = BimArchUtils.activeViewOf(self.doc)
            if self.view is not None:
                self.callback = self.view.addEventCallback("SoEvent", self._selectObject)

    def proceed(self):
        self.removeCallback()
        sel = BimArchUtils.selectionOf(self.doc)
        if len(sel) == 1:

            def create_slab(document):
                FreeCADGui.addModule("Arch")
                document.openTransaction("Create Slab")
                FreeCADGui.doCommand(
                    "s = Arch.makeStructure(FreeCAD.ActiveDocument."
                    + sel[0].Name
                    + ",height=200)"
                )
                FreeCADGui.doCommand("s.Label = " + repr(translate("BIM", "Slab")))
                FreeCADGui.doCommand('s.IfcType = "Slab"')
                FreeCADGui.doCommand("s.Normal = FreeCAD.Vector(0,0,-1)")
                document.commitTransaction()
                document.recompute()

            BimArchUtils.runInDocument(self.doc, create_slab)
        self.finish()

    def _selectObject(self, arg):
        if arg["Type"] == "SoKeyboardEvent":
            if arg["Key"] == "ESCAPE":
                self.finish()
        elif not arg["CtrlDown"] and FreeCADGui.Selection.hasSelection(self.doc.Name):
            self.proceed()

    def removeCallback(self):
        if self.callback:
            try:
                self.view.removeEventCallback("SoEvent", self.callback)
            except RuntimeError:
                pass
            self.callback = None

    def finish(self, cont=False):
        if FreeCAD.activeDraftCommand is self:
            FreeCAD.activeDraftCommand = None
        self.removeCallback()
        if hasattr(FreeCADGui, "draftToolBar"):
            FreeCADGui.draftToolBar.offUi()


FreeCADGui.addCommand("BIM_Slab", BIM_Slab())
