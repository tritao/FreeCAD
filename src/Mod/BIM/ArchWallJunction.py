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

"""Wall-junction relation object for 3+ BIM walls.

A WallJunction stores a cluster of walls around one shared carrier wall and
keeps a set of managed tee joints in sync for the branch walls that terminate
at the common junction point.
"""

import FreeCAD

import ArchWallJoinUtils
import ArchWallJunctionUtils

translate = FreeCAD.Qt.translate
_DELETE_OBSERVERS = []

if FreeCAD.GuiUp:
    from PySide.QtCore import QT_TRANSLATE_NOOP
else:

    def QT_TRANSLATE_NOOP(ctxt, txt):
        return txt


class _WallJunction:
    """Relation object that manages 3+ wall intersections through derived joints."""

    def __init__(self, obj):
        obj.Proxy = self
        self.Type = "WallJunction"
        self._pre_change_walls = []
        self._delete_observer = None
        self.setProperties(obj)

    def setProperties(self, obj):
        if "AutoLabel" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyBool",
                "AutoLabel",
                "Junction",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Automatically updates the label of this wall junction from its linked walls.",
                ),
            )
            obj.AutoLabel = True
        if "Enabled" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyBool",
                "Enabled",
                "Junction",
                QT_TRANSLATE_NOOP("App::Property", "Enables or disables this wall junction."),
            )
            obj.Enabled = True
        if "Walls" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLinkList",
                "Walls",
                "Junction",
                QT_TRANSLATE_NOOP("App::Property", "The walls referenced by this junction."),
            )
        if "CarrierMode" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "CarrierMode",
                "Junction",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Selects whether the junction carrier wall is detected automatically or chosen explicitly.",
                ),
            )
            obj.CarrierMode = ["Auto", "Explicit"]
            obj.CarrierMode = "Auto"
        if "CarrierWall" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLink",
                "CarrierWall",
                "Junction",
                QT_TRANSLATE_NOOP("App::Property", "The explicit carrier wall for this junction."),
            )
        if "Status" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyEnumeration",
                "Status",
                "Junction",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The current solve status of this wall junction."
                ),
            )
            obj.Status = [
                "OK",
                "Disabled",
                "MissingWall",
                "UnsupportedBaseline",
                "NoIntersection",
                "UnsupportedTopology",
                "SolverError",
            ]
            obj.Status = "MissingWall"
            obj.setEditorMode("Status", 1)
        if "StatusMessage" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyString",
                "StatusMessage",
                "Junction",
                QT_TRANSLATE_NOOP("App::Property", "A detailed message about the junction status."),
            )
            obj.setEditorMode("StatusMessage", 1)
        if "Intersection" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyVector",
                "Intersection",
                "Junction",
                QT_TRANSLATE_NOOP("App::Property", "The resolved junction intersection point."),
            )
            obj.setEditorMode("Intersection", 1)
        if "ResolvedCarrierWall" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLink",
                "ResolvedCarrierWall",
                "Junction",
                QT_TRANSLATE_NOOP("App::Property", "The resolved carrier wall of this junction."),
            )
            obj.setEditorMode("ResolvedCarrierWall", 1)
        if "ManagedJoints" not in obj.PropertiesList:
            obj.addProperty(
                "App::PropertyLinkList",
                "ManagedJoints",
                "Junction",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The hidden wall joints derived from this wall junction."
                ),
            )
            obj.setEditorMode("ManagedJoints", 1)
        for prop in (
            "Status",
            "StatusMessage",
            "Intersection",
            "ResolvedCarrierWall",
            "ManagedJoints",
        ):
            if prop in obj.PropertiesList:
                obj.setPropertyStatus(prop, "Output")
                obj.setPropertyStatus(prop, "NoRecompute")
        self._update_editor_modes(obj)

    def dumps(self):
        return self.Type

    def loads(self, _state):
        self.Type = "WallJunction"
        self._pre_change_walls = []
        self._delete_observer = None

    def onDocumentRestored(self, obj):
        self.Type = "WallJunction"
        self._pre_change_walls = []
        self._delete_observer = None
        self.setProperties(obj)
        self._ensure_delete_observer(obj)
        self._sync_managed_joints(obj, create_missing=True)
        self.updatePresentation(obj, force_label=bool(getattr(obj, "AutoLabel", False)))

    def onBeforeChange(self, obj, prop):
        if prop in ("Walls", "CarrierWall"):
            self._pre_change_walls = list(getattr(obj, "Walls", []))

    def onChanged(self, obj, prop):
        if "ManagedJoints" not in getattr(obj, "PropertiesList", []):
            return
        self._ensure_delete_observer(obj)
        if prop in ("Enabled", "Walls", "CarrierMode", "CarrierWall"):
            self._touch_walls(self._pre_change_walls + list(getattr(obj, "Walls", [])))
            self._pre_change_walls = []
            if obj.Document and not getattr(obj.Document, "Recomputing", False):
                self._sync_managed_joints(obj, create_missing=True)
        if prop in ("AutoLabel", "Walls", "CarrierMode", "CarrierWall"):
            self.updatePresentation(obj, force_label=(prop == "AutoLabel"))

    def execute(self, obj):
        self._ensure_delete_observer(obj)
        solution = ArchWallJunctionUtils.solve_wall_junction(obj)
        obj.Status = solution.status
        obj.StatusMessage = solution.status_message
        obj.Intersection = solution.intersection
        obj.ResolvedCarrierWall = solution.carrier_wall
        self._sync_managed_joints(obj, solution=solution, create_missing=False)
        self.updatePresentation(obj)

    def onDelete(self, obj, _args):
        self._disable_managed_joints(obj)
        self._touch_walls(list(getattr(obj, "Walls", [])))
        return True

    @staticmethod
    def _update_editor_modes(obj):
        carrier_mode = getattr(obj, "CarrierMode", "Auto")
        if hasattr(obj, "CarrierWall"):
            obj.setEditorMode("CarrierWall", 0 if carrier_mode == "Explicit" else 2)

    def updatePresentation(self, obj, force_label=False):
        self._update_editor_modes(obj)
        self._update_label(obj, force=force_label)

    def _update_label(self, obj, force=False):
        if not force and not getattr(obj, "AutoLabel", False):
            return
        obj.Label = self._get_auto_label(obj)

    @staticmethod
    def _get_auto_label(obj):
        walls = [wall.Label for wall in getattr(obj, "Walls", []) if wall]
        if walls:
            return "Junction: " + ", ".join(walls)
        return translate("Arch", "Wall Junction")

    def _sync_managed_joints(self, obj, solution=None, create_missing=True):
        solution = solution if solution else ArchWallJunctionUtils.solve_wall_junction(obj)
        doc = getattr(obj, "Document", None)
        managed_joints = []
        for joint in list(getattr(obj, "ManagedJoints", [])):
            if not joint or not ArchWallJoinUtils.is_wall_joint(joint):
                continue
            if doc and not doc.getObject(joint.Name):
                continue
            managed_joints.append(joint)
        desired_joints = []
        if solution.is_ok():
            carrier = solution.carrier_wall
            for branch_wall in solution.branch_walls:
                joint = self._find_managed_joint(managed_joints, obj, branch_wall, carrier)
                if (joint is None) and create_missing:
                    joint = self._create_managed_joint(obj, branch_wall, carrier)
                    if joint:
                        managed_joints.append(joint)
                if not joint:
                    continue
                self._configure_managed_joint(obj, joint, branch_wall, carrier)
                desired_joints.append(joint)

        for joint in managed_joints:
            if joint not in desired_joints:
                if getattr(joint, "Enabled", True):
                    joint.Enabled = False

        if getattr(obj, "ManagedJoints", []) != managed_joints:
            obj.ManagedJoints = managed_joints
        if self._delete_observer:
            self._delete_observer.joint_names = [joint.Name for joint in managed_joints if joint]

    @staticmethod
    def _find_managed_joint(managed_joints, junction, branch_wall, carrier_wall):
        for joint in managed_joints:
            if not ArchWallJoinUtils.is_wall_joint(joint):
                continue
            if {joint.WallA, joint.WallB} == {branch_wall, carrier_wall}:
                return joint
        return None

    @staticmethod
    def _create_managed_joint(junction, branch_wall, carrier_wall):
        import Arch

        if not junction.Document or getattr(junction.Document, "Recomputing", False):
            return None
        joint = Arch.makeWallJoint(branch_wall, carrier_wall, "Tee")
        if not joint:
            return None
        joint.AutoManaged = True
        joint.AutoLabel = False
        joint.Label = f"{junction.Label}: {branch_wall.Label} -> {carrier_wall.Label}"
        if FreeCAD.GuiUp and hasattr(joint, "ViewObject"):
            joint.ViewObject.Visibility = False
        return joint

    @staticmethod
    def _configure_managed_joint(junction, joint, branch_wall, carrier_wall):
        label = f"{junction.Label}: {branch_wall.Label} -> {carrier_wall.Label}"
        updates = {
            "AutoManaged": True,
            "WallA": branch_wall,
            "WallB": carrier_wall,
            "JointType": "Tee",
            "TeeStem": "WallA",
            "EndA": "Auto",
            "EndB": "Auto",
            "ButtTrimmed": "Auto",
            "Enabled": bool(getattr(junction, "Enabled", True)),
            "AutoLabel": False,
            "Label": label,
        }
        for prop, value in updates.items():
            if getattr(joint, prop) != value:
                setattr(joint, prop, value)
        if FreeCAD.GuiUp and hasattr(joint, "ViewObject"):
            joint.ViewObject.Visibility = False

    @staticmethod
    def _disable_managed_joints(obj):
        doc = getattr(obj, "Document", None)
        if not doc:
            return
        for joint in list(getattr(obj, "ManagedJoints", [])):
            if joint and doc.getObject(joint.Name):
                if getattr(joint, "Enabled", True):
                    joint.Enabled = False
                if getattr(joint, "AutoManaged", False):
                    joint.AutoManaged = False

    def _ensure_delete_observer(self, obj):
        doc = getattr(obj, "Document", None)
        if not doc:
            return
        if self._delete_observer and (
            self._delete_observer.doc_name != doc.Name
            or self._delete_observer.junction_name != obj.Name
        ):
            try:
                FreeCAD.removeDocumentObserver(self._delete_observer)
            except Exception:
                pass
            if self._delete_observer in _DELETE_OBSERVERS:
                _DELETE_OBSERVERS.remove(self._delete_observer)
            self._delete_observer = None
        if self._delete_observer:
            return
        observer = _ManagedJointDeleteObserver(
            doc.Name,
            obj.Name,
            [joint.Name for joint in getattr(obj, "ManagedJoints", []) if joint],
        )
        _DELETE_OBSERVERS.append(observer)
        FreeCAD.addDocumentObserver(observer)
        self._delete_observer = observer

    @staticmethod
    def _touch_walls(walls):
        seen = set()
        for wall in walls:
            if not wall or wall.Name in seen:
                continue
            seen.add(wall.Name)
            wall.touch()


class _ViewProviderWallJunction:
    """Minimal view provider for the wall junction relation object."""

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, _vobj):
        return

    def updateData(self, _obj, _prop):
        return

    def onChanged(self, _vobj, _prop):
        return

    def getIcon(self):
        return ":/icons/BIM_Join_Tee.svg"

    def doubleClicked(self, _vobj):
        return False

    def getDisplayModes(self, _obj):
        return []

    def getDefaultDisplayMode(self):
        return "Flat Lines"

    def setDisplayMode(self, mode):
        return mode


class _ManagedJointDeleteObserver:
    """One-shot document observer that removes managed joints after junction deletion."""

    def __init__(self, doc_name, junction_name, joint_names):
        self.doc_name = doc_name
        self.junction_name = junction_name
        self.joint_names = list(joint_names)
        self.armed = False

    def slotDeletedObject(self, obj):
        doc = getattr(obj, "Document", None)
        if not doc or doc.Name != self.doc_name or obj.Name != self.junction_name:
            return
        self.armed = True

    def slotCommitTransaction(self, doc):
        self._flush_pending_deletions(doc)

    def slotRecomputedDocument(self, doc):
        self._flush_pending_deletions(doc)

    def _flush_pending_deletions(self, doc):
        if not self.armed or not doc or doc.Name != self.doc_name:
            return
        self.armed = False
        FreeCAD.removeDocumentObserver(self)
        if self in _DELETE_OBSERVERS:
            _DELETE_OBSERVERS.remove(self)
        for joint_name in self.joint_names:
            managed_joint = doc.getObject(joint_name)
            if managed_joint:
                doc.removeObject(joint_name)
