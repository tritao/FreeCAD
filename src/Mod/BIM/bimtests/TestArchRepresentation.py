# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest

import FreeCAD
import Part

from ArchRepresentation import (
    AxisConstraint,
    BIMEditCapabilities,
    BIMEditHandle,
    BIMEditOperation,
    BIMEditRay,
    BIMEditTransaction,
    BIMRepresentation,
    PlaneConstraint,
    RepresentationUnavailable,
    WorkingPlaneConstraint,
    is_property_expression_driven,
    project_direction_to_representation_plane,
    project_to_representation_plane,
    query_representation_pick,
    query_representation_snap,
    query_representation_snap_candidates,
    RepresentationPurpose,
    RepresentationRequest,
    edit_capabilities_for,
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




    def test_representation_projection_respects_reference_frame(self):
        frame = FreeCAD.Placement(
            FreeCAD.Vector(10, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        request = RepresentationRequest(reference_frame=frame, target_offset=2.0)
        projected = project_to_representation_plane(FreeCAD.Vector(10, 5, 9), request)
        self.assertTrue(projected.isEqual(FreeCAD.Vector(10, 5, 2), 1e-7))

        tilted = FreeCAD.Placement(
            FreeCAD.Vector(1, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90)
        )
        working_plane = WorkingPlaneConstraint(tilted)
        working_ray = BIMEditRay(FreeCAD.Vector(10, 2, 3), FreeCAD.Vector(-1, 0, 0))
        self.assertTrue(
            working_plane.project(working_ray).isEqual(FreeCAD.Vector(1, 2, 3), 1e-7)
        )

        direction = project_direction_to_representation_plane(
            FreeCAD.Vector(0, 0, 1), RepresentationRequest()
        )
        self.assertIsNone(direction)




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


    def test_edit_operation_uses_semantic_candidate_validation(self):
        operation = BIMEditOperation(
            "Semantic",
            "Semantic edit",
            lambda _source: FreeCAD.Vector(),
            lambda _source, _value: None,
            value_kind="Point",
            validator=lambda _source, _value: type(
                "Evaluation", (), {"allowed": False, "reason": "Relation failed."}
            )(),
        )
        validation = operation.validate(object(), FreeCAD.Vector(1, 0, 0))
        self.assertFalse(validation.allowed)
        self.assertEqual("Relation failed.", validation.reason)

    def test_edit_operation_validates_before_mutating_semantic_source(self):
        source = {"width": 100.0}
        operation = BIMEditOperation(
            "set-width",
            "Set width",
            lambda value: value["width"],
            lambda value, width: value.__setitem__("width", width),
            minimum=10.0,
            maximum=500.0,
        )
        handle = BIMEditHandle(
            source,
            "width",
            FreeCAD.Vector(),
            FreeCAD.Vector(1, 0, 0),
            operation,
        )

        self.assertEqual(100.0, operation.get_value(source))
        self.assertFalse(operation.validate(source, 5.0).allowed)
        with self.assertRaises(ValueError):
            operation.apply(source, 5.0)
        operation.apply(source, 250.0)
        self.assertEqual(250.0, source["width"])
        self.assertIs(handle.operation, operation)

    def test_bim_edit_transaction_commits_and_aborts(self):
        class Document:
            def __init__(self):
                self.events = []

            def openTransaction(self, label):
                self.events.append(("open", label))

            def commitTransaction(self):
                self.events.append(("commit",))

            def abortTransaction(self):
                self.events.append(("abort",))

        document = Document()
        with BIMEditTransaction(document, "Edit wall"):
            document.events.append(("apply",))
        self.assertEqual([("open", "Edit wall"), ("apply",), ("commit",)], document.events)

        document.events.clear()
        with self.assertRaisesRegex(RuntimeError, "failed"):
            with BIMEditTransaction(document, "Edit wall"):
                raise RuntimeError("failed")
        self.assertEqual([("open", "Edit wall"), ("abort",)], document.events)

    def test_axis_constraint_resolves_pointer_ray_for_scalar_edit(self):
        source = {"height": 20.0}
        operation = BIMEditOperation(
            "set-height",
            "Set height",
            lambda value: value["height"],
            lambda value, height: value.__setitem__("height", height),
            minimum=1.0,
            manages_transaction=True,
        )
        axis = AxisConstraint(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1))
        handle = BIMEditHandle(
            source,
            "height",
            FreeCAD.Vector(0, 0, 10),
            FreeCAD.Vector(),
            operation,
            constraint=axis,
        )
        editor = BIMContextualHandleEditor(RepresentationRequest(purpose="Model"))
        ray = BIMEditRay(FreeCAD.Vector(10, 0, 5), FreeCAD.Vector(-1, 0, 0))

        editor.begin(handle)
        preview = editor.preview(ray)
        self.assertAlmostEqual(15.0, preview.value)
        self.assertTrue(preview.point.isEqual(FreeCAD.Vector(0, 0, 5), 1e-7))
        self.assertTrue(editor.commit(ray).success)
        self.assertAlmostEqual(15.0, source["height"])

    def test_plane_constraint_resolves_ray_and_working_plane_uses_frame(self):
        source = {"point": FreeCAD.Vector(1, 2, 0)}
        operation = BIMEditOperation(
            "move-point",
            "Move point",
            lambda value: value["point"],
            lambda value, point: value.__setitem__("point", point),
            value_kind="Point",
            manages_transaction=True,
        )
        plane = PlaneConstraint(FreeCAD.Vector(), FreeCAD.Vector(0, 0, 1))
        handle = BIMEditHandle(
            source,
            "point",
            source["point"],
            FreeCAD.Vector(),
            operation,
            constraint=plane,
        )
        editor = BIMContextualHandleEditor(RepresentationRequest(purpose="Model"))
        ray = BIMEditRay(FreeCAD.Vector(10, 20, 10), FreeCAD.Vector(-1, -2, -1))

        editor.begin(handle)
        preview = editor.preview(ray)
        self.assertTrue(preview.point.isEqual(FreeCAD.Vector(), 1e-7))
        self.assertTrue(preview.value.isEqual(FreeCAD.Vector(), 1e-7))
        self.assertTrue(editor.commit(ray).success)
        self.assertTrue(source["point"].isEqual(FreeCAD.Vector(), 1e-7))

        frame = FreeCAD.Placement(
            FreeCAD.Vector(1, 2, 3),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        working_plane = WorkingPlaneConstraint(frame)
        projected = working_plane.project(FreeCAD.Vector(8, 6, 5))
        self.assertTrue(projected.isEqual(FreeCAD.Vector(1, 6, 5), 1e-7))

    def test_constraints_report_ambiguous_parallel_pointer_rays(self):
        axis = AxisConstraint(FreeCAD.Vector(), FreeCAD.Vector(0, 0, 1))
        plane = PlaneConstraint(FreeCAD.Vector(), FreeCAD.Vector(0, 0, 1))
        axis_ray = BIMEditRay(FreeCAD.Vector(0, 0, 10), FreeCAD.Vector(0, 0, -1))
        plane_ray = BIMEditRay(FreeCAD.Vector(0, 0, 10), FreeCAD.Vector(1, 0, 0))
        self.assertIsNone(axis.project(axis_ray))
        self.assertIsNone(plane.project(plane_ray))

    def test_edit_capabilities_have_no_representation_geometry(self):
        request = RepresentationRequest(purpose=RepresentationPurpose.MODEL)

        class Provider:
            def getEditCapabilities(self, obj, requested_request):
                self.args = (obj, requested_request)
                return BIMEditCapabilities(source=obj, request=requested_request)

        class BIMObject:
            pass

        obj = BIMObject()
        obj.Proxy = Provider()
        result = edit_capabilities_for(obj, request)
        self.assertIs(result.source, obj)
        self.assertIs(result.request, request)
        self.assertEqual((obj, request), obj.Proxy.args)
        self.assertFalse(hasattr(result, "cut_geometry"))
        self.assertFalse(hasattr(result, "projected_geometry"))
        self.assertFalse(hasattr(result, "snap_geometry"))


    def test_preview_entries_describe_spatial_boundary_effects(self):
        source = object()
        representation = BIMRepresentation(source=source)
        state = BIMPreviewState(source)
        state.add_representation(
            representation,
            replace_committed=True,
            affects_spatial_boundary=False,
        )

        entry = state.entry_for(source)
        self.assertIs(entry.representation, representation)
        self.assertTrue(entry.replace_committed)
        self.assertFalse(entry.affects_spatial_boundary)
        self.assertIs(entry.style, BIMPreviewStyle.AVAILABLE)

        state.add_representation(representation, style="Emphasized")
        self.assertIs(state.entries[-1].style, BIMPreviewStyle.EMPHASIZED)
