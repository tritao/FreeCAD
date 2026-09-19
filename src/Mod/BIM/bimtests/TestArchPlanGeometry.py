# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for shared BIM plan-footprint geometry and Coin helpers."""

import ArchComponent
import ArchPlanContours
import ArchPlanGeometry
import ArchRepresentation
import FreeCAD
import Part
from bimtests.TestArchBaseGui import TestArchBaseGui
from pivy import coin


class TestArchPlanGeometry(TestArchBaseGui):
    @staticmethod
    def _contour_representation(points, seam=(), joint=None, opening=()):
        representation = ArchRepresentation.BIMRepresentation(source=object())
        representation.add_geometry(
            "projected_geometry", points, "PlanCutOuterBoundary"
        )
        if opening:
            representation.add_geometry(
                "projected_geometry", opening, "PlanCutInnerBoundary"
            )
        if seam:
            representation.add_geometry(
                "projected_geometry",
                seam,
                "WallJointCutLine",
                related_sources=(joint,),
            )
        representation.plan_contours = ArchPlanContours.contours_from_representation(
            representation
        )
        return representation

    def test_joined_plan_contours_remove_seam_and_preserve_mapping(self):
        joint = object()
        first = self._contour_representation(
            (
                FreeCAD.Vector(0, 100),
                FreeCAD.Vector(1900, 100),
                FreeCAD.Vector(2100, -100),
                FreeCAD.Vector(0, -100),
                FreeCAD.Vector(0, 100),
            ),
            (FreeCAD.Vector(2100, -100), FreeCAD.Vector(1900, 100)),
            joint,
        )
        second = self._contour_representation(
            (
                FreeCAD.Vector(2100, -100),
                FreeCAD.Vector(1900, 100),
                FreeCAD.Vector(1900, 1800),
                FreeCAD.Vector(2100, 1800),
                FreeCAD.Vector(2100, -100),
            ),
            (FreeCAD.Vector(1900, 100), FreeCAD.Vector(2100, -100)),
            joint,
        )

        contours = ArchPlanContours.joined_contours((second, first))[0]

        self.assertTrue(contours.valid)
        self.assertEqual(1, len(contours.outer_contours))
        self.assertEqual(1, len(contours.seam_lines))
        self.assertEqual(4, len(contours.source_mappings))
        self.assertTrue(
            contours.outer_contours[0][0].isEqual(
                contours.outer_contours[0][-1], contours.tolerance
            )
        )

    def test_joined_plan_contours_use_tolerance_and_keep_openings(self):
        joint = object()
        opening = (
            FreeCAD.Vector(200, 25),
            FreeCAD.Vector(300, 25),
            FreeCAD.Vector(300, 75),
            FreeCAD.Vector(200, 75),
            FreeCAD.Vector(200, 25),
        )
        first = self._contour_representation(
            (
                FreeCAD.Vector(0, 0),
                FreeCAD.Vector(1000, 0),
                FreeCAD.Vector(1000, 100),
                FreeCAD.Vector(0, 100),
                FreeCAD.Vector(0, 0),
            ),
            (FreeCAD.Vector(1000, 0), FreeCAD.Vector(1000, 100)),
            joint,
            opening,
        )
        epsilon = ArchPlanContours.DEFAULT_TOLERANCE * 0.25
        second = self._contour_representation(
            (
                FreeCAD.Vector(1000 + epsilon, 100),
                FreeCAD.Vector(1000 + epsilon, 0),
                FreeCAD.Vector(1200, 0),
                FreeCAD.Vector(1200, 100),
                FreeCAD.Vector(1000 + epsilon, 100),
            ),
            (FreeCAD.Vector(1000 + epsilon, 100), FreeCAD.Vector(1000 + epsilon, 0)),
            joint,
        )

        contours = ArchPlanContours.joined_contours((first, second))[0]

        self.assertTrue(contours.valid)
        self.assertEqual(1, len(contours.outer_contours))
        self.assertEqual((opening,), contours.opening_contours)

    def test_canonical_contour_owns_coincident_opening_jamb(self):
        representation = self._contour_representation(
            (
                FreeCAD.Vector(0, 0),
                FreeCAD.Vector(1000, 0),
                FreeCAD.Vector(1000, 200),
                FreeCAD.Vector(0, 200),
                FreeCAD.Vector(0, 0),
            )
        )
        contours = representation.plan_contours

        self.assertTrue(
            ArchPlanContours.contour_owns_polyline(
                contours,
                (FreeCAD.Vector(400, 0), FreeCAD.Vector(700, 0)),
            )
        )
        self.assertFalse(
            ArchPlanContours.contour_owns_polyline(
                contours,
                (FreeCAD.Vector(400, 10), FreeCAD.Vector(700, 10)),
            )
        )

    def test_non_manifold_plan_contours_are_reported_without_open_paths(self):
        joint = object()
        first = self._contour_representation(
            (
                FreeCAD.Vector(0, 0),
                FreeCAD.Vector(100, 0),
                FreeCAD.Vector(100, 100),
                FreeCAD.Vector(0, 100),
                FreeCAD.Vector(0, 0),
            ),
            (FreeCAD.Vector(100, 0), FreeCAD.Vector(100, 100)),
            joint,
        )
        second = self._contour_representation(
            (
                FreeCAD.Vector(50, 50),
                FreeCAD.Vector(150, 50),
                FreeCAD.Vector(150, 150),
                FreeCAD.Vector(50, 150),
                FreeCAD.Vector(50, 50),
            ),
            (FreeCAD.Vector(50, 50), FreeCAD.Vector(150, 50)),
            joint,
        )

        contours = ArchPlanContours.joined_contours((first, second))[0]

        self.assertFalse(contours.valid)
        self.assertTrue(
            all(path[0].isEqual(path[-1], contours.tolerance) for path in contours.outer_contours)
        )

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
