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

"""App-level tests for BIM wall joint relations."""

import Arch
import Draft
import FreeCAD as App

from bimtests import TestArchBase


class TestArchWallJoint(TestArchBase.TestArchBase):
    def _make_baseless_wall_between(self, p1, p2, width=200.0, height=1500.0):
        line_vector = p2.sub(p1)
        wall = Arch.makeWall(length=line_vector.Length, width=width, height=height)
        wall.Placement = App.Placement(
            (p1 + p2) * 0.5,
            App.Rotation(App.Vector(1, 0, 0), line_vector.normalize()),
        )
        self.document.recompute()
        return wall

    @staticmethod
    def _is_identity_placement(placement, tol=1e-9):
        return placement.Base.Length < tol and placement.Rotation.Angle < tol

    def test_make_wall_joint_miter_trims_wall_shapes(self):
        self.printTestMessage("Testing makeWallJoint creates a usable miter relation...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        initial_volume1 = wall1.Shape.Volume
        initial_volume2 = wall2.Shape.Volume

        joint = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()

        self.assertIsNotNone(joint, "makeWallJoint failed to create a relation object.")
        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ResolvedEndA, "End")
        self.assertEqual(joint.ResolvedEndB, "Start")
        self.assertTrue(
            wall1.Shape.isValid(), "First wall became invalid after the miter relation."
        )
        self.assertTrue(
            wall2.Shape.isValid(), "Second wall became invalid after the miter relation."
        )
        self.assertLess(wall1.Shape.Volume, initial_volume1)
        self.assertLess(wall2.Shape.Volume, initial_volume2)
        self.assertTrue(
            self._is_identity_placement(wall1.EndingStart)
            and self._is_identity_placement(wall1.EndingEnd),
            "Manual wall endings should stay untouched when a relation drives the trim.",
        )

    def test_wall_joint_updates_after_wall_move(self):
        self.printTestMessage("Testing wall joint recomputes from wall movement...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(1000, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))

        joint = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()
        initial_intersection = App.Vector(joint.Intersection)

        wall2.Placement.move(App.Vector(200, 0, 0))
        self.document.recompute()

        self.assertNotAlmostEqual(
            joint.Intersection.x,
            initial_intersection.x,
            delta=1e-6,
            msg="The joint intersection should update when a joined wall moves.",
        )
        self.assertAlmostEqual(joint.Intersection.x, 200.0, delta=1e-6)
        self.assertEqual(joint.Status, "OK")

    def test_disabling_wall_joint_restores_original_wall_shapes(self):
        self.printTestMessage("Testing disabling a wall joint restores the walls...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        original_volume1 = wall1.Shape.Volume
        original_volume2 = wall2.Shape.Volume

        joint = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        joint.Enabled = False
        self.document.recompute()

        self.assertEqual(joint.Status, "Disabled")
        self.assertAlmostEqual(wall1.Shape.Volume, original_volume1, delta=1e-6)
        self.assertAlmostEqual(wall2.Shape.Volume, original_volume2, delta=1e-6)

    def test_deleting_wall_joint_restores_original_wall_shapes(self):
        self.printTestMessage("Testing deleting a wall joint restores the walls...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        original_volume1 = wall1.Shape.Volume
        original_volume2 = wall2.Shape.Volume

        joint = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        self.document.removeObject(joint.Name)
        self.document.recompute()

        self.assertAlmostEqual(wall1.Shape.Volume, original_volume1, delta=1e-6)
        self.assertAlmostEqual(wall2.Shape.Volume, original_volume2, delta=1e-6)

    def test_make_wall_joint_reports_unsupported_baselines(self):
        self.printTestMessage("Testing wall joint status on unsupported baselines...")

        wire = Draft.makeWire(
            [App.Vector(0, 0, 0), App.Vector(1000, 0, 0), App.Vector(1000, 1000, 0)]
        )
        self.document.recompute()
        unsupported_wall = Arch.makeWall(wire, width=200, height=1500)
        supported_wall = self._make_baseless_wall_between(
            App.Vector(1000, 0, 0), App.Vector(1000, -1000, 0)
        )

        joint = Arch.makeWallJoint(unsupported_wall, supported_wall, "Miter")
        self.document.recompute()

        self.assertEqual(joint.Status, "UnsupportedBaseline")
        self.assertIn("single straight baseline", joint.StatusMessage)

    def test_make_wall_joint_auto_label_and_custom_name(self):
        self.printTestMessage("Testing wall joint labels...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))

        joint = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()

        self.assertTrue(joint.AutoLabel)
        self.assertEqual(joint.Label, f"Miter: {wall1.Label} <-> {wall2.Label}")

        joint.JointType = "Butt"
        self.document.recompute()
        self.assertEqual(joint.Label, f"Butt: {wall1.Label} <-> {wall2.Label}")

        named_joint = Arch.makeWallJoint(wall1, wall2, "Tee", name="Custom Joint")
        self.document.recompute()

        self.assertFalse(named_joint.AutoLabel)
        self.assertEqual(named_joint.Label, "Custom Joint")

        named_joint.JointType = "Miter"
        self.document.recompute()
        self.assertEqual(named_joint.Label, "Custom Joint")

    def test_wall_joint_conflict_reports_blocking_relation(self):
        self.printTestMessage("Testing wall joint conflict reporting...")

        wall1 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(2000, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        wall3 = self._make_baseless_wall_between(App.Vector(100, 0, 0), App.Vector(100, 1000, 0))

        blocker = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()
        self.assertEqual(blocker.Status, "OK")

        conflicted = Arch.makeWallJoint(wall1, wall3, "Miter")
        self.document.recompute()

        self.assertEqual(conflicted.Status, "Conflict")
        self.assertEqual(conflicted.ResolvedEndA, "Start")
        self.assertEqual(conflicted.ConflictJointLabelA, blocker.Label)
        self.assertEqual(conflicted.ConflictJointLabelB, "")
        self.assertIsNone(conflicted.ConflictJointA)
        self.assertIsNone(conflicted.ConflictJointB)
        self.assertIn("Start", conflicted.ConflictMessageA)
        self.assertIn(blocker.Label, conflicted.ConflictMessageA)
        self.assertEqual(conflicted.ConflictMessageB, "")
        self.assertIn("Conflict:", conflicted.StatusMessage)
        self.assertIn(blocker.Label, conflicted.StatusMessage)

    def test_wall_joint_conflict_resolves_after_blocker_removed(self):
        self.printTestMessage("Testing wall joint conflict clears after blocker removal...")

        wall1 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(2000, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        wall3 = self._make_baseless_wall_between(App.Vector(100, 0, 0), App.Vector(100, 1000, 0))

        blocker = Arch.makeWallJoint(wall1, wall2, "Miter")
        conflicted = Arch.makeWallJoint(wall1, wall3, "Miter")
        self.document.recompute()
        self.assertEqual(conflicted.Status, "Conflict")

        self.document.removeObject(blocker.Name)
        self.document.recompute()

        self.assertEqual(conflicted.Status, "OK")
        self.assertEqual(conflicted.ConflictJointLabelA, "")
        self.assertEqual(conflicted.ConflictJointLabelB, "")
        self.assertIsNone(conflicted.ConflictJointA)
        self.assertIsNone(conflicted.ConflictJointB)
        self.assertEqual(conflicted.ConflictMessageA, "")
        self.assertEqual(conflicted.ConflictMessageB, "")
