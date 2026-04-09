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

"""GUI workflow matrix tests for BIM wall join relations."""

import Arch
import ArchWallJoint
import Draft
import FreeCAD
import FreeCADGui
import Part

from bimtests import TestArchBaseGui
from bimcommands.BimJoin import (
    BIM_EditWallJoint,
    BIM_Join_Butt,
    BIM_Join_Miter,
    BIM_Join_Tee,
    BIM_Unjoin,
)


class TestArchWallJoinWorkflowGui(TestArchBaseGui.TestArchBaseGui):
    def _make_baseless_wall_between(self, p1, p2, width=200.0, height=1500.0):
        line_vector = p2.sub(p1)
        wall = Arch.makeWall(length=line_vector.Length, width=width, height=height)
        wall.Placement = FreeCAD.Placement(
            (p1 + p2) * 0.5,
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), line_vector.normalize()),
        )
        self.document.recompute()
        return wall

    def _make_line_based_wall_between(self, p1, p2, width=200.0, height=1500.0):
        line = Draft.makeLine(p1, p2)
        self.document.recompute()
        wall = Arch.makeWall(line, width=width, height=height)
        self.document.recompute()
        return wall

    def _make_sketch_based_wall_between(self, p1, p2, width=200.0, height=1500.0):
        sketch = self.document.addObject("Sketcher::SketchObject", "WallSketch")
        sketch.addGeometry(Part.LineSegment(p1, p2))
        wall = Arch.makeWall(sketch, width=width, height=height)
        self.document.recompute()
        return wall

    def _make_wall_between(self, baseline_kind, p1, p2, width=200.0, height=1500.0):
        if baseline_kind == "baseless":
            return self._make_baseless_wall_between(p1, p2, width=width, height=height)
        if baseline_kind == "line":
            return self._make_line_based_wall_between(p1, p2, width=width, height=height)
        if baseline_kind == "sketch":
            return self._make_sketch_based_wall_between(p1, p2, width=width, height=height)
        self.fail(f"Unsupported baseline kind in GUI workflow matrix: {baseline_kind}")

    def _make_join_pair(self, baseline_kind, joint_type):
        if joint_type == "Tee":
            wall_a = self._make_wall_between(
                baseline_kind,
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(0, 1000, 0),
            )
            wall_b = self._make_wall_between(
                baseline_kind,
                FreeCAD.Vector(-1000, 0, 0),
                FreeCAD.Vector(1000, 0, 0),
            )
            return wall_a, wall_b
        wall_a = self._make_wall_between(
            baseline_kind,
            FreeCAD.Vector(-1000, 0, 0),
            FreeCAD.Vector(0, 0, 0),
        )
        wall_b = self._make_wall_between(
            baseline_kind,
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(0, 1000, 0),
        )
        return wall_a, wall_b

    def _activate_command(self, command, *objects):
        FreeCADGui.Selection.clearSelection()
        for obj in objects:
            FreeCADGui.Selection.addSelection(self.document.Name, obj.Name)
        command.Activated()
        self.pump_gui_events()
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

    @staticmethod
    def _is_identity_placement(placement, tol=1e-9):
        return placement.Base.Length < tol and placement.Rotation.Angle < tol

    def _assert_manual_endings_clear(self, *walls):
        for wall in walls:
            self.assertTrue(
                self._is_identity_placement(wall.EndingStart)
                and self._is_identity_placement(wall.EndingEnd),
                f"Manual endings should stay untouched for {wall.Label} in the GUI workflow matrix.",
            )

    def _get_wall_joints(self):
        return [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]

    def _remove_created_objects(self, existing_names):
        if FreeCADGui.ActiveDocument.getInEdit():
            FreeCADGui.ActiveDocument.resetEdit()
            self.pump_gui_events()
        for obj in reversed(list(self.document.Objects)):
            if obj.Name not in existing_names:
                self.document.removeObject(obj.Name)
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

    def test_join_command_matrix_supported_baselines(self):
        self.printTestMessage("Testing GUI workflow matrix for join commands...")

        command_map = {
            "Miter": BIM_Join_Miter,
            "Butt": BIM_Join_Butt,
            "Tee": BIM_Join_Tee,
        }
        for baseline_kind in ("baseless", "line", "sketch"):
            for joint_type, command_cls in command_map.items():
                with self.subTest(baseline=baseline_kind, joint_type=joint_type):
                    existing_names = {obj.Name for obj in self.document.Objects}
                    wall_a, wall_b = self._make_join_pair(baseline_kind, joint_type)

                    self._activate_command(command_cls(), wall_a, wall_b)

                    joints = self._get_wall_joints()
                    self.assertEqual(len(joints), 1)
                    joint = joints[0]
                    self.assertEqual(joint.JointType, joint_type)
                    self.assertEqual(joint.Status, "OK")
                    if joint_type == "Butt":
                        self.assertEqual(joint.ButtTrimmed, "WallB")
                    elif joint_type == "Tee":
                        self.assertEqual(joint.TeeStem, "WallA")
                    self._assert_manual_endings_clear(wall_a, wall_b)
                    self._remove_created_objects(existing_names)

    def test_join_workflow_matrix_reuse_edit_and_unjoin(self):
        self.printTestMessage("Testing GUI workflow matrix for reuse, edit, and unjoin...")

        for baseline_kind in ("baseless", "line", "sketch"):
            with self.subTest(baseline=baseline_kind):
                existing_names = {obj.Name for obj in self.document.Objects}
                wall_a, wall_b = self._make_join_pair(baseline_kind, "Miter")

                self._activate_command(BIM_Join_Miter(), wall_a, wall_b)
                joints = self._get_wall_joints()
                self.assertEqual(len(joints), 1)
                joint = joints[0]
                original_name = joint.Name

                self._activate_command(BIM_Join_Miter(), wall_b, wall_a)
                joints = self._get_wall_joints()
                self.assertEqual(len(joints), 1)
                joint = joints[0]
                self.assertEqual(joint.Name, original_name)

                self._activate_command(BIM_EditWallJoint(), joint)
                in_edit = FreeCADGui.ActiveDocument.getInEdit()
                self.assertIsNotNone(in_edit)
                self.assertEqual(getattr(in_edit, "Object", None), joint)
                FreeCADGui.ActiveDocument.resetEdit()
                self.pump_gui_events()

                panel = ArchWallJoint.WallJointTaskPanel(joint)
                panel._set_combo_value(panel.joint_type_combo, "JointType", "Butt")
                panel._set_combo_value(panel.butt_trimmed_combo, "ButtTrimmed", "WallA")
                panel.accept()
                self.pump_gui_events()

                self.assertEqual(joint.JointType, "Butt")
                self.assertEqual(joint.ButtTrimmed, "WallA")
                self.assertEqual(joint.Status, "OK")

                self._activate_command(BIM_Unjoin(), joint)
                self.assertEqual(len(self._get_wall_joints()), 0)
                self._remove_created_objects(existing_names)

    def test_join_workflow_matrix_tee_edit_supported_baselines(self):
        self.printTestMessage("Testing GUI workflow matrix for tee stem edits...")

        for baseline_kind in ("baseless", "line", "sketch"):
            with self.subTest(baseline=baseline_kind):
                existing_names = {obj.Name for obj in self.document.Objects}
                wall_a, wall_b = self._make_join_pair(baseline_kind, "Tee")

                self._activate_command(BIM_Join_Tee(), wall_a, wall_b)
                joints = self._get_wall_joints()
                self.assertEqual(len(joints), 1)
                joint = joints[0]
                self.assertEqual(joint.TeeStem, "WallA")

                panel = ArchWallJoint.WallJointTaskPanel(joint)
                panel._set_combo_value(panel.tee_stem_combo, "TeeStem", "WallB")
                panel.accept()
                self.pump_gui_events()

                self.assertEqual(joint.JointType, "Tee")
                self.assertEqual(joint.TeeStem, "WallB")
                self.assertEqual(joint.Status, "OK")
                self._assert_manual_endings_clear(wall_a, wall_b)
                self._remove_created_objects(existing_names)
