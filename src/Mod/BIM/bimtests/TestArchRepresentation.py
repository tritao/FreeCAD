# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest

import FreeCAD
import Part

from ArchRepresentation import (
    BIMRepresentation,
    RepresentationUnavailable,
    query_representation_pick,
    query_representation_snap,
    query_representation_snap_candidates,
    RepresentationPurpose,
    RepresentationRequest,
    representation_for,
)


class TestArchRepresentation(unittest.TestCase):
    def test_request_accepts_enum_or_serialized_purpose(self):
        plan = RepresentationRequest(purpose=RepresentationPurpose.PLAN)
        section = RepresentationRequest(purpose="Section")
        self.assertIs(plan.purpose, RepresentationPurpose.PLAN)
        self.assertIs(section.purpose, RepresentationPurpose.SECTION)
        self.assertIsNone(section.reference_frame)

    def test_request_keeps_arbitrary_frame_and_ranges(self):
        frame = object()
        request = RepresentationRequest(
            purpose="Elevation",
            reference_frame=frame,
            cut_range=(0.0, 2.1),
            projection_range=(-1.0, 8.0),
            cut_offset=1.2,
            target_offset=0.0,
        )
        self.assertIs(request.reference_frame, frame)
        self.assertEqual(request.cut_range, (0.0, 2.1))
        self.assertEqual(request.projection_range, (-1.0, 8.0))
        self.assertEqual(request.cut_offset, 1.2)
        self.assertEqual(request.target_offset, 0.0)

    def test_representation_records_roles_and_subelements(self):
        source = object()
        edge = object()
        representation = BIMRepresentation(source=source)
        representation.add_geometry("cut_geometry", edge, "cut", subelement="Edge3")
        mapping = representation.mapping_for(edge)
        self.assertIs(mapping.geometry, edge)
        self.assertIs(mapping.source, source)
        self.assertEqual(mapping.role, "cut")
        self.assertEqual(mapping.subelement, "Edge3")

    def test_representation_rejects_unknown_collection(self):
        with self.assertRaises(ValueError):
            BIMRepresentation().add_geometry("display", object(), "display")

    def test_representation_for_delegates_to_object_provider(self):
        request = RepresentationRequest(purpose="Plan")

        class Provider:
            def getRepresentation(self, obj, requested_request):
                self.args = (obj, requested_request)
                return BIMRepresentation(source=obj, request=requested_request)

        class BIMObject:
            pass

        obj = BIMObject()
        obj.Proxy = Provider()
        result = representation_for(obj, request)
        self.assertIs(result.source, obj)
        self.assertIs(result.request, request)
        self.assertEqual(obj.Proxy.args, (obj, request))


    def test_snap_query_preserves_semantic_identity(self):
        source = object()
        edge = Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, 0, 0))
        representation = BIMRepresentation(source=source)
        representation.add_geometry("snap_geometry", edge, "axis", "Edge1")

        result = query_representation_snap((representation,), FreeCAD.Vector(4, 0.5, 0), 1.0)

        self.assertIs(result.source, source)
        self.assertEqual("Edge1", result.subelement)
        self.assertEqual("axis", result.role)
        self.assertAlmostEqual(0.5, result.distance)

    def test_snap_query_deduplicates_coincident_semantic_targets(self):
        first_source = object()
        second_source = object()
        relation = object()
        point = FreeCAD.Vector(4, 2, 0)
        first = BIMRepresentation(source=first_source)
        second = BIMRepresentation(source=second_source)
        first.add_geometry(
            "snap_geometry",
            Part.Vertex(point),
            "WallCorner",
            related_sources=(relation,),
        )
        second.add_geometry(
            "snap_geometry",
            Part.Vertex(point),
            "WallCorner",
            related_sources=(relation,),
        )

        candidates = query_representation_snap_candidates((first, second), point, 1.0)

        self.assertEqual(1, len(candidates))
        self.assertEqual({first_source, second_source, relation}, set(candidates[0].sources))

    def test_pick_query_preserves_cut_geometry_mapping(self):
        source = object()
        edge = Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, 0, 0))
        representation = BIMRepresentation(source=source)
        representation.add_geometry("cut_geometry", edge, "cut", "Edge2")

        result = query_representation_pick(
            (representation,),
            (5.0, 0.25),
            lambda point: (point.x, point.y),
            1.0,
        )

        self.assertIs(result.source, source)
        self.assertEqual("Edge2", result.subelement)
        self.assertEqual("cut", result.role)


if __name__ == "__main__":
    unittest.main()


    def test_request_supports_plan_offsets(self):
        request = RepresentationRequest(
            purpose=RepresentationPurpose.PLAN,
            cut_offset=1.0,
            target_offset=0.0,
        )
        self.assertIs(request.purpose, RepresentationPurpose.PLAN)
        self.assertEqual(request.cut_offset, 1.0)
        self.assertEqual(request.target_offset, 0.0)


    def test_wall_representation_supports_a_rotated_section_frame(self):
        document = FreeCAD.newDocument("ArbitraryWallRepresentationTest")
        self.addCleanup(FreeCAD.closeDocument, document.Name)
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        document.recompute()
        frame = FreeCAD.Placement(
            FreeCAD.Vector(1500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        request = RepresentationRequest(
            purpose="Section",
            reference_frame=frame,
            cut_offset=0,
            target_offset=0,
        )

        representation = wall.Proxy.getRepresentation(wall, request)

        self.assertTrue(representation.cut_geometry)
        self.assertTrue(representation.snap_geometry)
        roles = {handle.role for handle in representation.edit_handles}
        self.assertIn("WallHeight", roles)
        height_handle = next(
            handle for handle in representation.edit_handles if handle.role == "WallHeight"
        )
        self.assertIsInstance(height_handle.constraint, AxisConstraint)
        self.assertTrue(all(mapping.source is wall for mapping in representation.source_mappings))

    def test_representation_for_does_not_dispatch_on_type_name(self):
        class BIMObject:
            pass

        obj = BIMObject()
        obj.Proxy = object()
        with self.assertRaises(RepresentationUnavailable):
            representation_for(obj, RepresentationRequest())
