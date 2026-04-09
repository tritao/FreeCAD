# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026                                                    *
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

"""BIM wall joint relation object."""

import FreeCAD

import ArchWallJoinUtils

if FreeCAD.GuiUp:
    from PySide.QtCore import QT_TRANSLATE_NOOP
else:

    def QT_TRANSLATE_NOOP(ctxt, txt):
        return txt


class _WallJoint:
    """Relation object that solves trims between two walls."""

    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "WallJoint"
        self._pre_change_walls = []
        self.setProperties(obj)

    def setProperties(self, obj):
        if "JointType" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "JointType",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The type of wall joint."),
            )
            obj.JointType = ["Miter", "Butt", "Tee"]
            obj.JointType = "Miter"
        if "Enabled" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyBool",
                "Enabled",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "Enables or disables this wall joint."),
            )
            obj.Enabled = True
        if "WallA" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLink",
                "WallA",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The first wall referenced by this joint."),
            )
        if "WallB" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLink",
                "WallB",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The second wall referenced by this joint."),
            )
        if "ButtTrimmed" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "ButtTrimmed",
                "Joint",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Which wall is flush-trimmed when the joint type is Butt."
                ),
            )
            obj.ButtTrimmed = ["Auto", "WallA", "WallB"]
            obj.ButtTrimmed = "Auto"
        if "TeeStem" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "TeeStem",
                "Joint",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Which wall acts as the stem when the joint type is Tee."
                ),
            )
            obj.TeeStem = ["Auto", "WallA", "WallB"]
            obj.TeeStem = "Auto"
        if "EndA" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "EndA",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "Which end of WallA is trimmed by this joint."),
            )
            obj.EndA = ["Auto", "Start", "End", "None"]
            obj.EndA = "Auto"
        if "EndB" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "EndB",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "Which end of WallB is trimmed by this joint."),
            )
            obj.EndB = ["Auto", "Start", "End", "None"]
            obj.EndB = "Auto"
        if "Status" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "Status",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The current solve status of this wall joint."),
            )
            obj.Status = [
                "OK",
                "Disabled",
                "MissingWall",
                "UnsupportedBaseline",
                "NoIntersection",
                "Conflict",
                "SolverError",
            ]
            obj.Status = "MissingWall"
            obj.setEditorMode("Status", 1)
        if "StatusMessage" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyString",
                "StatusMessage",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "A detailed message about the joint status."),
            )
            obj.setEditorMode("StatusMessage", 1)
        if "Intersection" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyVector",
                "Intersection",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The resolved baseline intersection point."),
            )
            obj.setEditorMode("Intersection", 1)
        if "ResolvedEndA" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "ResolvedEndA",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The resolved wall end used on WallA."),
            )
            obj.ResolvedEndA = ["None", "Start", "End"]
            obj.ResolvedEndA = "None"
            obj.setEditorMode("ResolvedEndA", 1)
        if "ResolvedEndB" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "ResolvedEndB",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The resolved wall end used on WallB."),
            )
            obj.ResolvedEndB = ["None", "Start", "End"]
            obj.ResolvedEndB = "None"
            obj.setEditorMode("ResolvedEndB", 1)
        if "ResolvedPlaneA" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyPlacement",
                "ResolvedPlaneA",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The resolved global cutting plane for WallA."),
            )
            obj.setEditorMode("ResolvedPlaneA", 1)
        if "ResolvedPlaneB" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyPlacement",
                "ResolvedPlaneB",
                "Joint",
                QT_TRANSLATE_NOOP("App::Property", "The resolved global cutting plane for WallB."),
            )
            obj.setEditorMode("ResolvedPlaneB", 1)

    def dumps(self):
        return self.Type

    def loads(self, _state):
        self.Type = "WallJoint"
        self._pre_change_walls = []

    def onDocumentRestored(self, obj):
        self.Type = "WallJoint"
        self._pre_change_walls = []
        self.setProperties(obj)

    def onBeforeChange(self, obj, prop):
        if prop in ("WallA", "WallB"):
            self._pre_change_walls = [getattr(obj, "WallA", None), getattr(obj, "WallB", None)]

    def onChanged(self, obj, prop):
        if prop in (
            "JointType",
            "Enabled",
            "WallA",
            "WallB",
            "ButtTrimmed",
            "TeeStem",
            "EndA",
            "EndB",
        ):
            self._touch_walls(
                self._pre_change_walls + [getattr(obj, "WallA", None), getattr(obj, "WallB", None)]
            )
            self._pre_change_walls = []

    def execute(self, obj):
        solution = ArchWallJoinUtils.solve_wall_joint(obj)
        obj.Status = solution["status"]
        obj.StatusMessage = solution["status_message"]
        obj.Intersection = solution["intersection"]
        obj.ResolvedEndA = solution["resolved_end_a"] if solution["resolved_end_a"] else "None"
        obj.ResolvedEndB = solution["resolved_end_b"] if solution["resolved_end_b"] else "None"
        obj.ResolvedPlaneA = solution["plane_a"] if solution["plane_a"] else FreeCAD.Placement()
        obj.ResolvedPlaneB = solution["plane_b"] if solution["plane_b"] else FreeCAD.Placement()

    def onDelete(self, obj, _args):
        self._touch_walls([obj.WallA, obj.WallB])
        return True

    @staticmethod
    def _touch_walls(walls):
        seen = set()
        for wall in walls:
            if not wall or wall.Name in seen:
                continue
            seen.add(wall.Name)
            wall.touch()


class _ViewProviderWallJoint:
    """Minimal view provider for the wall joint relation object."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object

    def updateData(self, _obj, _prop):
        return

    def onChanged(self, _vobj, _prop):
        return

    def getIcon(self):
        joint_type = getattr(self.Object, "JointType", "Miter")
        return f":/icons/BIM_Join_{joint_type}.svg"
