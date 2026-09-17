# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for the UI-independent Draft/BIM planar grid engine."""

import unittest

import FreeCAD as App

from draftutils.grid import GridLattice, adaptive_grid_interval


class DraftGridLattice(unittest.TestCase):
    def test_nearest_node_uses_origin_and_directed_axes(self):
        lattice = GridLattice(
            App.Vector(100, 200, 300),
            App.Vector(0, 1, 0),
            App.Vector(-1, 0, 0),
            spacing=100,
        )

        point = App.Vector(176, 251, 300)

        self.assertEqual(App.Vector(200, 300, 300), lattice.nearest_node(point))

    def test_lines_are_aligned_and_mark_major_intervals(self):
        lattice = GridLattice(spacing=100, major_every=2)

        lines = lattice.lines((-200, 200, -100, 100), display_spacing=100)

        self.assertEqual(8, len(lines))
        self.assertEqual(App.Vector(-200, -100, 0), lines[0].start)
        self.assertTrue(lines[2].major)
        self.assertFalse(lines[1].major)
        self.assertEqual(App.Vector(1, 0, 0), lattice.u_axis)
        self.assertEqual(App.Vector(0, 1, 0), lattice.v_axis)

    def test_adaptive_interval_uses_engineering_series(self):
        self.assertEqual(100.0, adaptive_grid_interval(0.8, target_pixels=100))
        self.assertEqual(200.0, adaptive_grid_interval(1.1, target_pixels=100))
        self.assertEqual(500.0, adaptive_grid_interval(3.0, target_pixels=100))
        self.assertEqual(1000.0, adaptive_grid_interval(8.0, target_pixels=100))
