# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest

import FreeCAD
import Part
import TechDraw


class ProjectionApiTest(unittest.TestCase):
    def setUp(self):
        self.document = FreeCAD.newDocument("TechDrawProjectionApiTest")

    def tearDown(self):
        FreeCAD.closeDocument(self.document.Name)

    def test_part_projection_matches_techdraw_projection(self):
        box = Part.makeBox(10, 10, 10)
        direction = FreeCAD.Vector(0, 1, 0)

        projected = Part.project(box, direction)
        projected_ex = Part.projectEx(box, direction)

        legacy_projected = TechDraw.project(box, direction)
        legacy_projected_ex = TechDraw.projectEx(box, direction)

        self.assertEqual(len(projected), 4)
        self.assertEqual(len(projected_ex), 10)
        self.assertEqual(
            [len(group.Edges) for group in projected],
            [len(group.Edges) for group in legacy_projected],
        )
        self.assertEqual(
            [len(group.Edges) for group in projected_ex],
            [len(group.Edges) for group in legacy_projected_ex],
        )
