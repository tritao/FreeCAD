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
import ArchWallPath
import Draft
import FreeCAD as App
import Part

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

    def _make_sketch_based_wall_between(self, p1, p2, width=200.0, height=1500.0):
        sketch = self.document.addObject("Sketcher::SketchObject", "WallSketch")
        sketch.addGeometry(Part.LineSegment(p1, p2))
        wall = Arch.makeWall(sketch, width=width, height=height)
        self.document.recompute()
        return wall

    @staticmethod
    def _is_identity_placement(placement, tol=1e-9):
        return placement.Base.Length < tol and placement.Rotation.Angle < tol

    def _assert_wall_trimmed(self, wall, initial_volume, msg):
        self.assertTrue(wall.Shape.isValid(), f"{wall.Label} became invalid after the joint.")
        self.assertLess(wall.Shape.Volume, initial_volume, msg)

    def _assert_wall_unchanged(self, wall, initial_volume, msg):
        self.assertTrue(wall.Shape.isValid(), f"{wall.Label} became invalid after the joint.")
        self.assertAlmostEqual(wall.Shape.Volume, initial_volume, delta=1e-6, msg=msg)

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

    def test_make_wall_joint_butt_trims_wall_shapes(self):
        self.printTestMessage("Testing makeWallJoint creates a usable butt relation...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))

        joint = Arch.makeWallJoint(wall1, wall2, "Butt")
        joint.ButtTrimmed = "WallB"
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ButtTrimmed, "WallB")
        self.assertEqual(joint.ResolvedEndA, "End")
        self.assertEqual(joint.ResolvedEndB, "Start")
        self.assertFalse(
            self._is_identity_placement(joint.ResolvedPlaneA),
            "The butt relation should solve a cutting plane for the first wall.",
        )
        self.assertFalse(
            self._is_identity_placement(joint.ResolvedPlaneB),
            "The butt relation should solve a cutting plane for the second wall.",
        )
        self.assertTrue(wall1.Shape.isValid(), "First wall became invalid after the butt relation.")
        self.assertTrue(
            wall2.Shape.isValid(), "Second wall became invalid after the butt relation."
        )

    def test_make_wall_joint_miter_on_sketch_based_walls(self):
        self.printTestMessage("Testing miter joints on one-edge sketch-based walls...")

        wall1 = self._make_sketch_based_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_sketch_based_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        initial_volume1 = wall1.Shape.Volume
        initial_volume2 = wall2.Shape.Volume

        joint = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ResolvedEndA, "End")
        self.assertEqual(joint.ResolvedEndB, "Start")
        self._assert_wall_trimmed(
            wall1,
            initial_volume1,
            "Sketch-based miter joints should trim the first wall.",
        )
        self._assert_wall_trimmed(
            wall2,
            initial_volume2,
            "Sketch-based miter joints should trim the second wall.",
        )

    def test_make_wall_joint_butt_on_sketch_based_walls(self):
        self.printTestMessage("Testing butt joints on one-edge sketch-based walls...")

        wall1 = self._make_sketch_based_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_sketch_based_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))

        joint = Arch.makeWallJoint(wall1, wall2, "Butt")
        joint.ButtTrimmed = "WallB"
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ResolvedEndA, "End")
        self.assertEqual(joint.ResolvedEndB, "Start")
        self.assertFalse(
            self._is_identity_placement(joint.ResolvedPlaneA),
            "Sketch-based butt joints should solve a cutting plane for the first wall.",
        )
        self.assertFalse(
            self._is_identity_placement(joint.ResolvedPlaneB),
            "Sketch-based butt joints should solve a cutting plane for the second wall.",
        )
        self.assertTrue(
            wall1.Shape.isValid(), "First sketch-based wall became invalid after the butt relation."
        )
        self.assertTrue(
            wall2.Shape.isValid(),
            "Second sketch-based wall became invalid after the butt relation.",
        )

    def test_get_wall_path_uses_global_endpoints_for_based_walls(self):
        self.printTestMessage("Testing wall path normalization for based walls...")

        wall = self._make_sketch_based_wall_between(App.Vector(0, 0, 0), App.Vector(1000, 0, 0))
        wall.Placement = App.Placement(
            App.Vector(250, 125, 0),
            App.Rotation(App.Vector(0, 0, 1), 35),
        )
        self.document.recompute()

        path = ArchWallPath.get_wall_path(wall)
        endpoints = wall.Proxy.calc_endpoints(wall)

        self.assertIsNotNone(path, "A one-edge based wall should produce a join path.")
        self.assertTrue(
            path.start_point.isEqual(endpoints[0], 1e-6),
            "The path start point should match the wall's global start endpoint.",
        )
        self.assertTrue(
            path.end_point.isEqual(endpoints[1], 1e-6),
            "The path end point should match the wall's global end endpoint.",
        )

    def test_get_wall_path_rejects_unsupported_based_walls(self):
        self.printTestMessage("Testing wall path rejection for unsupported based walls...")

        wire = Draft.makeWire(
            [App.Vector(0, 0, 0), App.Vector(1000, 0, 0), App.Vector(1000, 1000, 0)]
        )
        self.document.recompute()
        wall = Arch.makeWall(wire, width=200, height=1500)
        self.document.recompute()

        self.assertIsNone(
            ArchWallPath.get_wall_path(wall),
            "Multi-edge based walls should be rejected by the join path adapter.",
        )

    def test_make_wall_joint_tee_on_sketch_based_walls(self):
        self.printTestMessage("Testing tee joints on one-edge sketch-based walls...")

        stem_wall = self._make_sketch_based_wall_between(
            App.Vector(0, 0, 0), App.Vector(0, 1000, 0)
        )
        top_wall = self._make_sketch_based_wall_between(
            App.Vector(-1000, 0, 0), App.Vector(1000, 0, 0)
        )
        initial_stem_volume = stem_wall.Shape.Volume
        initial_top_volume = top_wall.Shape.Volume

        joint = Arch.makeWallJoint(stem_wall, top_wall, "Tee")
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ResolvedEndA, "Start")
        self.assertEqual(joint.ResolvedEndB, "None")
        self._assert_wall_trimmed(
            stem_wall,
            initial_stem_volume,
            "Sketch-based tee joints should trim the stem wall.",
        )
        self._assert_wall_unchanged(
            top_wall,
            initial_top_volume,
            "Sketch-based tee joints should leave the top wall volume unchanged.",
        )

    def test_make_wall_joint_miter_handles_oblique_walls(self):
        self.printTestMessage("Testing miter joints on oblique straight walls...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(800, 600, 0))
        initial_volume1 = wall1.Shape.Volume
        initial_volume2 = wall2.Shape.Volume

        joint = Arch.makeWallJoint(wall1, wall2, "Miter")
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ResolvedEndA, "End")
        self.assertEqual(joint.ResolvedEndB, "Start")
        self._assert_wall_trimmed(
            wall1,
            initial_volume1,
            "Oblique miter joints should trim the first wall.",
        )
        self._assert_wall_trimmed(
            wall2,
            initial_volume2,
            "Oblique miter joints should trim the second wall.",
        )

    def test_make_wall_joint_butt_handles_oblique_walls(self):
        self.printTestMessage("Testing butt joints on oblique straight walls...")

        wall1 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(0, 0, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(800, 600, 0))
        initial_volume1 = wall1.Shape.Volume
        initial_volume2 = wall2.Shape.Volume

        joint = Arch.makeWallJoint(wall1, wall2, "Butt")
        joint.ButtTrimmed = "WallB"
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ResolvedEndA, "End")
        self.assertEqual(joint.ResolvedEndB, "Start")
        self._assert_wall_trimmed(
            wall1,
            initial_volume1,
            "Oblique butt joints should trim the supporting wall.",
        )
        self._assert_wall_trimmed(
            wall2,
            initial_volume2,
            "Oblique butt joints should trim the selected butt wall.",
        )

    def test_make_wall_joint_tee_handles_oblique_walls(self):
        self.printTestMessage("Testing tee joints on oblique straight walls...")

        stem_wall = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(400, 400, 0))
        top_wall = self._make_baseless_wall_between(
            App.Vector(-800, 400, 0), App.Vector(1200, 400, 0)
        )
        initial_stem_volume = stem_wall.Shape.Volume
        initial_top_volume = top_wall.Shape.Volume

        joint = Arch.makeWallJoint(stem_wall, top_wall, "Tee")
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.TeeStem, "Auto")
        self.assertEqual(joint.ResolvedEndA, "End")
        self.assertEqual(joint.ResolvedEndB, "None")
        self._assert_wall_trimmed(
            stem_wall,
            initial_stem_volume,
            "Oblique tee joints should trim the stem wall.",
        )
        self._assert_wall_unchanged(
            top_wall,
            initial_top_volume,
            "Oblique tee joints should leave the top wall volume unchanged.",
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

    def test_wall_joint_tee_stem_edit_updates_trimmed_wall_geometry(self):
        self.printTestMessage("Testing tee stem edits update the trimmed wall geometry...")

        wall1 = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        wall2 = self._make_baseless_wall_between(App.Vector(-1000, 0, 0), App.Vector(1000, 0, 0))
        original_volume1 = wall1.Shape.Volume
        original_volume2 = wall2.Shape.Volume

        joint = Arch.makeWallJoint(wall1, wall2, "Tee")
        joint.TeeStem = "WallA"
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self._assert_wall_trimmed(
            wall1,
            original_volume1,
            "The initial tee stem wall should be trimmed.",
        )
        self._assert_wall_unchanged(
            wall2,
            original_volume2,
            "The top wall should remain untrimmed before flipping the tee stem.",
        )

        joint.TeeStem = "WallB"
        self.document.recompute()

        self.assertEqual(joint.Status, "OK")
        self.assertEqual(joint.ResolvedEndA, "None")
        self.assertNotEqual(joint.ResolvedEndB, "None")
        self._assert_wall_unchanged(
            wall1,
            original_volume1,
            "Changing TeeStem should restore the original wall when it stops being the stem.",
        )
        self._assert_wall_trimmed(
            wall2,
            original_volume2,
            "Changing TeeStem should trim the newly selected stem wall.",
        )
