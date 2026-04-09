# --- src/Mod/BIM/bimcommands/BimJoin.py ---

# ***************************************************************************
# * (License Header as in other BIM files)                                  *
# ***************************************************************************

"""
BIM join command
This command joins different objects that can be joined, currently only Walls
"""

import Arch
import ArchWallJoinUtils
import FreeCAD
import FreeCADGui

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate


class BIM_Join:
    """
    Base class for the different BIM Join commands. It contains the common
    logic to select objects, find their baselines, and determine the
    intersection point.
    """

    Supported = translate("BIM", "Supported objects: Walls")
    SupportedBaselines = translate(
        "BIM", "The Join command only supports walls with a single straight baseline"
    )
    JointType = "Miter"

    def IsActive(self):
        v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        return v

    def Activated(self):
        """Executes the command's main logic."""
        sel = FreeCADGui.Selection.getSelection()

        if len(sel) != 2:
            FreeCAD.Console.PrintError(
                translate("BIM", "The BIM Join command needs exactly 2 objects selected.") + "\n"
            )
            return

        doc = sel[0].Document
        doc.openTransaction(translate("BIM", "Join objects"))
        joint = ArchWallJoinUtils.find_existing_joint(doc, sel[0], sel[1])
        if not joint:
            joint = Arch.makeWallJoint(sel[0], sel[1], self.JointType)
        if not joint:
            doc.abortTransaction()
            return

        if not self._configure_joint(joint, sel[0], sel[1]):
            doc.abortTransaction()
            return
        doc.commitTransaction()
        doc.recompute()
        self._report_joint_status(joint)

    def _report_unsupported_baseline(self, obj):
        FreeCAD.Console.PrintError(self.SupportedBaselines + f": {obj.Label}\n")

    def _get_join_baseline(self, obj):
        """Returns the baseline edge for a supported wall join."""
        if not (hasattr(obj, "Proxy") and hasattr(obj.Proxy, "get_baseline")):
            FreeCAD.Console.PrintError(
                translate("BIM", "This object is not supported by the Join command")
                + f": {obj.Label}\n"
            )
            return None

        baseline = ArchWallJoinUtils.get_join_baseline(obj)
        if not baseline:
            self._report_unsupported_baseline(obj)
            return None

        return baseline

    def find_best_intersection(self, line1, line2):
        return ArchWallJoinUtils.find_best_intersection(line1, line2)

    def _configure_joint(self, joint, wall1, wall2):
        baseline1 = self._get_join_baseline(wall1)
        baseline2 = self._get_join_baseline(wall2)
        if not baseline1 or not baseline2:
            return False

        intersection, _end_name1, _end_name2 = self.find_best_intersection(baseline1, baseline2)
        if not intersection:
            FreeCAD.Console.PrintError(
                translate("BIM", "The baselines of the selected walls do not intersect.") + "\n"
            )
            return False

        joint.Enabled = True
        joint.JointType = self.JointType
        joint.EndA = "Auto"
        joint.EndB = "Auto"
        joint.ButtTrimmed = "Auto"
        joint.TeeStem = "Auto"
        return self.configure_joint(joint, wall1, wall2, baseline1, baseline2, intersection)

    def configure_joint(self, _joint, _wall1, _wall2, _baseline1, _baseline2, _intersection):
        return True

    @staticmethod
    def _report_joint_status(joint):
        if not joint or getattr(joint, "Status", "OK") == "OK":
            return
        message = joint.StatusMessage or translate("BIM", "The wall joint could not be solved.")
        FreeCAD.Console.PrintError(message + "\n")
        if getattr(joint, "Status", "") == "Conflict":
            FreeCAD.Console.PrintMessage(
                translate(
                    "BIM",
                    "Use Unjoin on the blocking relation, or edit the new joint's end or role properties.",
                )
                + "\n"
            )


class BIM_Join_Miter(BIM_Join):
    """The BIM_Join_Miter command creates a miter joint between two objects."""

    JointType = "Miter"

    def GetResources(self):
        return {
            "Pixmap": "BIM_Join_Miter",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Join_Miter", "Miter joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Join_Miter", "Creates a miter joint between two supported objects."
            ),
        }


class BIM_Join_Tee(BIM_Join):
    """The BIM_Join_Tee command creates a tee joint between two objects."""

    JointType = "Tee"

    def GetResources(self):
        return {
            "Pixmap": "BIM_Join_Tee",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Join_Tee", "Tee joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Join_Tee", "Creates a tee joint between two supported objects."
            ),
        }

    def configure_joint(self, joint, wall1, wall2, baseline1, baseline2, intersection):
        stem_role = ArchWallJoinUtils.get_auto_tee_stem_role(baseline1, baseline2, intersection)
        stem_wall = wall1 if stem_role == "WallA" else wall2
        joint.TeeStem = "WallA" if joint.WallA == stem_wall else "WallB"
        return True


class BIM_Join_Butt(BIM_Join):
    """The BIM_Join_Butt command creates a butt joint between two objects."""

    JointType = "Butt"

    def GetResources(self):
        return {
            "Pixmap": "BIM_Join_Butt",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Join_Butt", "Butt joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Join_Butt", "Creates a butt joint between two supported objects."
            ),
        }

    def configure_joint(self, joint, _wall1, wall2, _baseline1, _baseline2, _intersection):
        joint.ButtTrimmed = "WallA" if joint.WallA == wall2 else "WallB"
        return True


class BIM_Unjoin:
    """The BIM_Unjoin command removes wall-joint relations."""

    def IsActive(self):
        v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        return v

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        joints = self._get_selected_joints(sel)
        if not joints:
            return

        doc = joints[0].Document
        doc.openTransaction(translate("BIM", "Unjoin objects"))
        for joint in joints:
            doc.removeObject(joint.Name)
        doc.commitTransaction()
        doc.recompute()

    @staticmethod
    def _get_selected_joints(sel):
        if sel and all(ArchWallJoinUtils.is_wall_joint(obj) for obj in sel):
            return list(sel)

        if len(sel) == 2:
            joint = ArchWallJoinUtils.find_existing_joint(sel[0].Document, sel[0], sel[1])
            if joint:
                return [joint]
            FreeCAD.Console.PrintError(
                translate("BIM", "The selected objects are not joined by a wall joint.") + "\n"
            )
            return []

        FreeCAD.Console.PrintError(
            translate(
                "BIM",
                "The BIM Unjoin command needs selected wall joint objects or 2 joined walls.",
            )
            + "\n"
        )
        return []

    def GetResources(self):
        return {
            "Pixmap": "Arch_Remove",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Unjoin", "Unjoin"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Unjoin",
                "Removes the selected wall joint, or the wall joint between two selected walls.",
            ),
        }


class BIM_EditWallJoint:
    """The BIM_EditWallJoint command opens a task panel to edit a selected joint."""

    def IsActive(self):
        sel = FreeCADGui.Selection.getSelection()
        v = hasattr(FreeCADGui.getMainWindow().getActiveWindow(), "getSceneGraph")
        return v and len(sel) == 1 and ArchWallJoinUtils.is_wall_joint(sel[0])

    def Activated(self):
        sel = FreeCADGui.Selection.getSelection()
        if len(sel) != 1 or not ArchWallJoinUtils.is_wall_joint(sel[0]):
            FreeCAD.Console.PrintError(
                translate("BIM", "The BIM Edit Wall Joint command needs 1 wall joint selected.")
                + "\n"
            )
            return
        FreeCADGui.ActiveDocument.setEdit(sel[0].Name, 0)

    def GetResources(self):
        return {
            "Pixmap": "BIM_IfcProperties",
            "MenuText": QT_TRANSLATE_NOOP("BIM_EditWallJoint", "Edit wall joint"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_EditWallJoint",
                "Opens a task panel to edit the selected wall joint relation.",
            ),
        }


# Register the commands with FreeCAD's GUI
FreeCADGui.addCommand("BIM_Join_Miter", BIM_Join_Miter())
FreeCADGui.addCommand("BIM_Join_Tee", BIM_Join_Tee())
FreeCADGui.addCommand("BIM_Join_Butt", BIM_Join_Butt())
FreeCADGui.addCommand("BIM_Unjoin", BIM_Unjoin())
FreeCADGui.addCommand("BIM_EditWallJoint", BIM_EditWallJoint())
