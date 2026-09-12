# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for shared BIM plan-footprint geometry and Coin helpers."""

import ArchComponent
import ArchPlanGeometry
import FreeCAD
import Part
from bimtests.TestArchBaseGui import TestArchBaseGui
from pivy import coin


class TestArchPlanGeometry(TestArchBaseGui):
    def test_face_wire_polylines_are_ordered_and_closed(self):
        wire = Part.Wire(
            [
                Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, 0, 0)),
                Part.makeLine(FreeCAD.Vector(10, 0, 0), FreeCAD.Vector(10, 5, 0)),
                Part.makeLine(FreeCAD.Vector(10, 5, 0), FreeCAD.Vector(0, 5, 0)),
                Part.makeLine(FreeCAD.Vector(0, 5, 0), FreeCAD.Vector(0, 0, 0)),
            ]
        )

        polylines = ArchPlanGeometry.get_face_wire_polylines([Part.Face(wire)])

        self.assertEqual(1, len(polylines))
        self.assertEqual(5, len(polylines[0]))
        self.assertTrue(polylines[0][0].isEqual(polylines[0][-1], 0.001))

    def test_line_node_updates_clear_before_replacing_and_reject_bad_counts(self):
        coordinates = coin.SoCoordinate3()
        line_set = coin.SoLineSet()
        update = ArchComponent.ViewProviderComponent._update_footprint_line_nodes

        self.assertTrue(
            update(
                None,
                coordinates,
                line_set,
                [[0, 0, 0], [5, 0, 0], [5, 5, 0]],
                [3],
            )
        )
        self.assertEqual(3, coordinates.point.getNum())
        self.assertEqual(1, line_set.numVertices.getNum())

        self.assertFalse(update(None, coordinates, line_set, [[0, 0, 0]], [2]))
        self.assertEqual(0, coordinates.point.getNum())
        self.assertEqual(0, line_set.numVertices.getNum())

    def test_footprint_fill_subtree_is_unlit(self):
        coordinates = coin.SoCoordinate3()
        faces = coin.SoIndexedFaceSet()
        subtree = ArchComponent.ViewProviderComponent.buildFootprintFillSeparator(
            None, (0.7, 0.7, 0.7), 0.5, coordinates, faces
        )

        self.assertIsInstance(subtree, coin.SoSeparator)
        self.assertEqual(5, subtree.getNumChildren())
        self.assertIsInstance(subtree.getChild(1), coin.SoLightModel)
