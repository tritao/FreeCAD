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

"""App-level tests for BIM wall junction relations."""

import Arch
import FreeCAD as App

from bimtests import TestArchBase


class TestArchWallJunction(TestArchBase.TestArchBase):
    def _make_baseless_wall_between(self, p1, p2, width=200.0, height=1500.0):
        line_vector = p2.sub(p1)
        wall = Arch.makeWall(length=line_vector.Length, width=width, height=height)
        wall.Placement = App.Placement(
            (p1 + p2) * 0.5,
            App.Rotation(App.Vector(1, 0, 0), line_vector.normalize()),
        )
        self.document.recompute()
        return wall

    def test_make_wall_junction_creates_managed_branch_joints(self):
        self.printTestMessage("Testing makeWallJunction creates managed branch joints...")

        carrier_wall = self._make_baseless_wall_between(
            App.Vector(-1000, 0, 0), App.Vector(1000, 0, 0)
        )
        branch_up = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        branch_down = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, -1000, 0))
        carrier_volume = carrier_wall.Shape.Volume
        branch_up_volume = branch_up.Shape.Volume
        branch_down_volume = branch_down.Shape.Volume

        junction = Arch.makeWallJunction([carrier_wall, branch_up, branch_down])
        self.document.recompute()

        self.assertIsNotNone(junction)
        self.assertEqual(junction.Status, "OK")
        self.assertEqual(junction.ResolvedCarrierWall, carrier_wall)
        self.assertEqual(len(junction.ManagedJoints), 2)
        self.assertAlmostEqual(junction.Intersection.x, 0.0, delta=1e-6)
        self.assertAlmostEqual(junction.Intersection.y, 0.0, delta=1e-6)
        self.assertAlmostEqual(carrier_wall.Shape.Volume, carrier_volume, delta=1e-6)
        self.assertLess(branch_up.Shape.Volume, branch_up_volume)
        self.assertLess(branch_down.Shape.Volume, branch_down_volume)

        for joint in junction.ManagedJoints:
            self.assertTrue(joint.AutoManaged)
            self.assertEqual(joint.Status, "OK")
            self.assertEqual(joint.JointType, "Tee")
            self.assertEqual(joint.TeeStem, "WallA")
            self.assertEqual(joint.WallB, carrier_wall)

    def test_wall_junction_updates_when_cluster_breaks(self):
        self.printTestMessage(
            "Testing wall junction recomputes when the cluster becomes invalid..."
        )

        carrier_wall = self._make_baseless_wall_between(
            App.Vector(-1000, 0, 0), App.Vector(1000, 0, 0)
        )
        branch_up = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        branch_down = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, -1000, 0))

        junction = Arch.makeWallJunction([carrier_wall, branch_up, branch_down])
        self.document.recompute()
        self.assertEqual(junction.Status, "OK")

        branch_down.Placement.move(App.Vector(200, 0, 0))
        self.document.recompute()

        self.assertNotEqual(junction.Status, "OK")
        self.assertIn(junction.Status, ("NoIntersection", "UnsupportedTopology"))
        self.assertTrue(
            all(not joint.Enabled for joint in junction.ManagedJoints),
            "Managed joints should be disabled when the wall junction no longer solves.",
        )

    def test_wall_junction_rejects_unsupported_cross_topology(self):
        self.printTestMessage("Testing wall junction rejects unsupported cross topology...")

        horizontal = self._make_baseless_wall_between(
            App.Vector(-1000, 0, 0), App.Vector(1000, 0, 0)
        )
        vertical = self._make_baseless_wall_between(App.Vector(0, -1000, 0), App.Vector(0, 1000, 0))
        diagonal = self._make_baseless_wall_between(
            App.Vector(-1000, -1000, 0), App.Vector(1000, 1000, 0)
        )

        junction = Arch.makeWallJunction([horizontal, vertical, diagonal])
        self.document.recompute()

        self.assertEqual(junction.Status, "UnsupportedTopology")
        self.assertFalse(
            any(joint.Enabled for joint in junction.ManagedJoints),
            "Unsupported junction topologies should not keep active managed joints.",
        )

    def test_deleting_wall_junction_removes_managed_joints_and_restores_walls(self):
        self.printTestMessage("Testing deleting a wall junction removes its managed joints...")

        carrier_wall = self._make_baseless_wall_between(
            App.Vector(-1000, 0, 0), App.Vector(1000, 0, 0)
        )
        branch_up = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, 1000, 0))
        branch_down = self._make_baseless_wall_between(App.Vector(0, 0, 0), App.Vector(0, -1000, 0))
        branch_up_volume = branch_up.Shape.Volume
        branch_down_volume = branch_down.Shape.Volume

        junction = Arch.makeWallJunction([carrier_wall, branch_up, branch_down])
        self.document.recompute()
        self.assertEqual(junction.Status, "OK")
        managed_joint_names = [joint.Name for joint in junction.ManagedJoints]

        self.document.removeObject(junction.Name)
        self.document.recompute()

        self.assertAlmostEqual(branch_up.Shape.Volume, branch_up_volume, delta=1e-6)
        self.assertAlmostEqual(branch_down.Shape.Volume, branch_down_volume, delta=1e-6)
        for joint_name in managed_joint_names:
            self.assertIsNone(
                self.document.getObject(joint_name),
                "Deleting the wall junction should also remove its managed wall joints.",
            )
