# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest

import Arch
import FreeCAD
import Part
import Arch
import Draft

from ArchRepresentation import (
    BIMEditHandle,
    BIMEditOperation,
    BIMEditTransaction,
    BIMRepresentation,
    RepresentationUnavailable,
    RepresentationContext,
    RepresentationPurpose,
    query_representation_pick,
    query_representation_snap,
    query_representation_snap_candidates,
    representation_for,
)
from bimplan.contextual_editing import BIMContextualHandleEditor, ContextualEditController
from bimplan.editable_points import get_contextual_edit_points


class TestArchRepresentation(unittest.TestCase):
    def test_context_accepts_enum_or_serialized_purpose(self):
        plan = RepresentationContext(purpose=RepresentationPurpose.PLAN)
        section = RepresentationContext(purpose="Section")
        self.assertIs(plan.purpose, RepresentationPurpose.PLAN)
        self.assertIs(section.purpose, RepresentationPurpose.SECTION)
        self.assertIsNone(section.reference_frame)

    def test_context_keeps_arbitrary_frame_and_ranges(self):
        frame = object()
        context = RepresentationContext(
            purpose="Elevation",
            reference_frame=frame,
            cut_range=(0.0, 2.1),
            projection_range=(-1.0, 8.0),
            profile="Architectural",
            cut_offset=1.2,
            target_offset=0.0,
        )
        self.assertIs(context.reference_frame, frame)
        self.assertEqual(context.cut_range, (0.0, 2.1))
        self.assertEqual(context.projection_range, (-1.0, 8.0))
        self.assertEqual(context.cut_offset, 1.2)
        self.assertEqual(context.target_offset, 0.0)

    def test_context_supports_plan_offsets(self):
        context = RepresentationContext(
            purpose=RepresentationPurpose.PLAN,
            cut_offset=1.0,
            target_offset=0.0,
        )
        self.assertIs(context.purpose, RepresentationPurpose.PLAN)
        self.assertEqual(context.cut_offset, 1.0)
        self.assertEqual(context.target_offset, 0.0)

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

    def test_wall_provider_exposes_semantic_cut_boundary(self):
        document = FreeCAD.newDocument("SemanticWallBoundary")
        try:
            wall = Arch.makeWall(length=3000, width=200, height=3000)
            document.recompute()
            representation = wall.Proxy.getRepresentation(
                wall,
                RepresentationContext(
                    purpose=RepresentationPurpose.PLAN,
                    cut_offset=1000,
                    target_offset=0,
                ),
            )
            boundaries = [
                mapping
                for mapping in representation.source_mappings
                if mapping.role == "PlanCutOuterBoundary"
            ]
            self.assertEqual(len(boundaries), 1)
            self.assertIn(boundaries[0].geometry, representation.projected_geometry)
            self.assertEqual(boundaries[0].subelement, "PlanFace1.OuterWire")
            self.assertGreaterEqual(len(boundaries[0].geometry), 2)
            self.assertTrue(boundaries[0].geometry[0].isEqual(boundaries[0].geometry[-1], 1e-7))
        finally:
            FreeCAD.closeDocument(document.Name)

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

    def test_contextual_editor_projects_previews_and_commits(self):
        source = {"width": 100.0}
        operation = BIMEditOperation(
            "set-width",
            "Set width",
            lambda value: value["width"],
            lambda value, width: value.__setitem__("width", width),
            minimum=10.0,
            manages_transaction=True,
        )
        handle = BIMEditHandle(
            source,
            "width",
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(1, 0, 0),
            operation,
        )
        refreshed = []
        editor = BIMContextualHandleEditor(RepresentationContext(purpose="Plan"), refreshed.append)

        editor.begin(handle)
        preview = editor.preview(FreeCAD.Vector(25, 50, 10))
        self.assertEqual(125.0, preview.value)
        self.assertEqual(FreeCAD.Vector(25, 0, 0), preview.point)
        result = editor.commit(FreeCAD.Vector(25, 50, 10))

        self.assertTrue(result.success)
        self.assertEqual(125.0, source["width"])
        self.assertEqual([source], refreshed)
        self.assertIsNone(editor.handle)

    def test_contextual_edit_controller_uses_injected_view_render_and_input(self):
        class Renderer:
            def __init__(self):
                self.events = []

            def set_handle_state(self, handle, state):
                self.events.append(("state", handle, state))

            def preview_handle(self, handle, point):
                self.events.append(("point", handle, FreeCAD.Vector(point)))

            def clear_preview(self, source):
                self.events.append(("clear", source))

        class InputAdapter:
            def start_point_pick(self, point, callback, move_callback, title):
                self.point = point
                self.callback = callback
                self.move_callback = move_callback
                self.title = title

            def defer(self, _key, callback):
                callback()
                return True

            def clear(self):
                self.cleared = True

        source = {"width": 100.0}
        operation = BIMEditOperation(
            "set-width",
            "Set width",
            lambda value: value["width"],
            lambda value, width: value.__setitem__("width", width),
            minimum=1.0,
            manages_transaction=True,
        )
        handle = BIMEditHandle(
            source,
            "width",
            FreeCAD.Vector(),
            FreeCAD.Vector(1, 0, 0),
            operation,
        )
        renderer = Renderer()
        input_adapter = InputAdapter()
        refreshed = []
        view = object()
        controller = ContextualEditController(
            view,
            RepresentationContext(purpose="Plan"),
            renderer,
            input_adapter,
            refresh_callback=refreshed.append,
        )

        self.assertTrue(controller.activate(handle))
        self.assertIs(controller.view, view)
        self.assertIs(controller.active_edit, handle)
        self.assertEqual("Edit width", input_adapter.title)
        input_adapter.move_callback(FreeCAD.Vector(25, 10, 0))
        input_adapter.callback(FreeCAD.Vector(25, 10, 0), None)

        self.assertEqual(125.0, source["width"])
        self.assertEqual([source], refreshed)
        self.assertIsNone(controller.active_edit)
        self.assertTrue(input_adapter.cleared)
        self.assertIn(("clear", source), renderer.events)

    def test_object_owned_contextual_points_preserve_global_coordinates(self):
        class Owner:
            Points = [FreeCAD.Vector(1, 2, 3), FreeCAD.Vector(4, 5, 6)]

            class ProxyType:
                def getContextualEditPoints(self, owner, context):
                    del context
                    return tuple(owner.Points)

                def setContextualEditPoint(self, owner, index, point):
                    owner.Points[index] = FreeCAD.Vector(point)

            Proxy = ProxyType()

            @staticmethod
            def getGlobalPlacement():
                return FreeCAD.Placement()

        owner = Owner()
        points = get_contextual_edit_points(owner, RepresentationContext(purpose="Plan"))

        self.assertEqual(2, len(points))
        self.assertEqual("Vertex2", points[1].subelement)
        points[1].apply_value(FreeCAD.Vector(7, 8, 9))
        self.assertEqual(FreeCAD.Vector(7, 8, 9), points[1].get_value())

    def test_planar_contextual_handle_moves_a_point_value(self):
        source = {"point": FreeCAD.Vector(1, 2, 0)}
        operation = BIMEditOperation(
            "move-point",
            "Move point",
            lambda value: value["point"],
            lambda value, point: value.__setitem__("point", point),
            value_kind="Point",
            manages_transaction=True,
        )
        handle = BIMEditHandle(
            source,
            "path-point",
            source["point"],
            FreeCAD.Vector(),
            operation,
            interaction="Planar",
        )
        editor = BIMContextualHandleEditor(RepresentationContext(purpose="Plan"))

        editor.begin(handle)
        result = editor.commit(FreeCAD.Vector(6, 8, 20))

        self.assertTrue(result.success)
        self.assertEqual(FreeCAD.Vector(6, 8, 20), source["point"])

    def test_native_wall_path_exposes_semantic_endpoint_handles(self):
        document = FreeCAD.newDocument("ContextualPathRepresentationTest")
        self.addCleanup(FreeCAD.closeDocument, document.Name)
        wall = Arch.makeWall(length=4000, width=200, height=3000)
        document.recompute()

        representation = wall.Proxy.getRepresentation(
            wall,
            RepresentationContext(
                purpose="Plan",
                cut_offset=1000,
                target_offset=0,
            ),
        )

        handles = {handle.subelement: handle for handle in representation.edit_handles}
        self.assertTrue({"Path.Start", "Path.End"}.issubset(handles))
        self.assertEqual("Square", handles["Path.Start"].glyph)
        self.assertEqual("Square", handles["Path.End"].glyph)
        self.assertEqual("Point", handles["Path.End"].operation.value_kind)
        self.assertEqual("WallStretchStart", handles["Path.Start"].operation.interaction_intent)
        move_handle = next(
            handle for handle in representation.edit_handles if handle.role == "WallMove"
        )
        self.assertEqual("Circle", move_handle.glyph)
        self.assertEqual("WallMove", move_handle.operation.interaction_intent)
        endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertTrue(move_handle.point.isEqual((endpoints[0] + endpoints[1]) * 0.5, 1e-7))

    def test_joint_handle_anchors_to_offset_miter_seam(self):
        document = FreeCAD.newDocument("OffsetMiterHandleTest")
        self.addCleanup(FreeCAD.closeDocument, document.Name)
        horizontal = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        horizontal.Placement.Base = FreeCAD.Vector(1500, 0, 0)
        vertical = Arch.makeWall(length=2000, width=200, height=2500, align="Right")
        vertical.Placement = FreeCAD.Placement(
            FreeCAD.Vector(3000, -1000, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), -90),
        )
        document.recompute()
        joint = Arch.makeWallJoint(horizontal, vertical, "Miter")
        document.recompute()
        self.assertEqual("OK", joint.Status, joint.StatusMessage)

        context = RepresentationContext(purpose="Plan", cut_offset=1000, target_offset=0)
        representation = horizontal.Proxy.getRepresentation(horizontal, context)
        handle = next(item for item in representation.edit_handles if item.role == "WallJointMove")
        semantic_point = handle.operation.get_value(handle.source)

        self.assertTrue(semantic_point.isEqual(FreeCAD.Vector(3000, 0, 0), 1e-7))
        self.assertTrue(handle.point.isEqual(FreeCAD.Vector(3100, 0, 0), 1e-7))
        editor = BIMContextualHandleEditor(context)
        editor.begin(handle)
        preview = editor.preview(handle.point + FreeCAD.Vector(200, 150, 0))
        self.assertTrue(preview.value.isEqual(semantic_point + FreeCAD.Vector(200, 150, 0), 1e-7))

        vertical_representation = vertical.Proxy.getRepresentation(vertical, context)
        joint_targets = tuple(
            target
            for target in representation.iter_snap_targets()
            if joint in target.related_sources
        )
        self.assertTrue(joint_targets)
        self.assertIn("WallJointBoundary", {target.role for target in joint_targets})
        self.assertIn("WallJointCutPoint", {target.role for target in joint_targets})
        corner = next(target for target in joint_targets if target.role == "WallJointCutPoint")
        result = query_representation_snap(
            (representation, vertical_representation), corner.geometry.Point, 1.0
        )
        self.assertIn(joint, result.sources)
        self.assertIn(horizontal, result.sources)
        self.assertIn(vertical, result.sources)

    def test_wall_width_face_handles_preserve_the_opposite_face(self):
        document = FreeCAD.newDocument("ContextualWallWidthTest")
        self.addCleanup(FreeCAD.closeDocument, document.Name)
        context = RepresentationContext(purpose="Plan", cut_offset=1000, target_offset=0)
        for align in ("Center", "Left", "Right"):
            for side in ("Negative", "Positive"):
                with self.subTest(align=align, side=side):
                    wall = Arch.makeWall(
                        length=3000,
                        width=200,
                        height=3000,
                        align=align,
                        name="{}{}WidthWall".format(align, side),
                    )
                    wall.Offset = 25
                    document.recompute()
                    before = wall.Proxy.get_resolved_section(wall)
                    representation = wall.Proxy.getRepresentation(wall, context)
                    handles = {
                        item.subelement: item
                        for item in representation.edit_handles
                        if item.role == "WallWidth"
                    }
                    self.assertEqual({"Width.NegativeFace", "Width.PositiveFace"}, set(handles))
                    handle = handles["Width.{}Face".format(side)]
                    self.assertEqual("Plus", handle.glyph)
                    self.assertEqual(1.0, handle.operation.sensitivity)

                    editor = BIMContextualHandleEditor(context)
                    editor.begin(handle)
                    result = editor.commit(handle.point + handle.direction * 50)
                    document.recompute()

                    self.assertTrue(result.success)
                    self.assertAlmostEqual(250.0, wall.Width.Value)
                    after = wall.Proxy.get_resolved_section(wall)
                    if side == "Negative":
                        self.assertAlmostEqual(before.y_max, after.y_max)
                        self.assertAlmostEqual(before.y_min - 50, after.y_min)
                    else:
                        self.assertAlmostEqual(before.y_min, after.y_min)
                        self.assertAlmostEqual(before.y_max + 50, after.y_max)

    def test_hosted_opening_exposes_semantic_plan_geometry_and_handles(self):
        document = FreeCAD.newDocument("ContextualOpeningRepresentationTest")
        self.addCleanup(FreeCAD.closeDocument, document.Name)
        wall = Arch.makeWall(length=3000, width=200, height=3000)
        base = Draft.make_rectangle(900, 2100)
        base.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90)
        opening = Arch.makeWindow(baseobj=base, name="ContextualOpening")
        opening.Width = 900
        opening.Height = 2100
        Arch.addComponents(opening, wall)
        document.recompute()

        representation = opening.Proxy.getRepresentation(
            opening,
            RepresentationContext(purpose="Plan", cut_offset=1000, target_offset=0),
        )

        self.assertIs(representation.source, opening)
        self.assertTrue(representation.projected_geometry)
        self.assertTrue(representation.snap_geometry)
        self.assertTrue(representation.edit_handles)
        mappings_by_role = {}
        for mapping in representation.source_mappings:
            mappings_by_role.setdefault(mapping.role, []).append(mapping)
        self.assertEqual(2, len(mappings_by_role["OpeningJambLine"]))
        self.assertEqual(4, len(mappings_by_role["OpeningJambPoint"]))
        self.assertIn("OpeningPosition", {handle.role for handle in representation.edit_handles})
        self.assertTrue(
            all(
                target.source is opening and target.role == "OpeningJambPoint"
                for target in representation.iter_snap_targets()
                if target.role == "OpeningJambPoint"
            )
        )
        self.assertTrue(
            all(mapping.source is opening for mapping in representation.source_mappings)
        )
        position = next(
            handle for handle in representation.edit_handles if handle.role == "OpeningPosition"
        )
        before = FreeCAD.Placement(base.Placement)
        preview = position.operation.get_preview_representation(
            opening,
            position.operation.get_value(opening) + 100.0,
            representation.context,
        )
        self.assertTrue(preview.cut_geometry)
        self.assertEqual(
            {"OpeningJambLine", "OpeningSymbol", "OpeningGuide"},
            {mapping.role for mapping in preview.source_mappings} - {"OpeningPreviewCut"},
        )
        self.assertEqual(before, base.Placement)

    def test_wall_representation_supports_a_rotated_section_frame(self):
        document = FreeCAD.newDocument("ArbitraryWallRepresentationTest")
        self.addCleanup(FreeCAD.closeDocument, document.Name)
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        document.recompute()
        frame = FreeCAD.Placement(
            FreeCAD.Vector(1500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        context = RepresentationContext(
            purpose="Section",
            reference_frame=frame,
            cut_offset=0,
            target_offset=0,
        )

        representation = wall.Proxy.getRepresentation(wall, context)

        self.assertTrue(representation.cut_geometry)
        self.assertTrue(representation.snap_geometry)
        roles = {handle.role for handle in representation.edit_handles}
        self.assertIn("WallHeight", roles)
        self.assertTrue(all(mapping.source is wall for mapping in representation.source_mappings))

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

    def test_representation_for_delegates_to_object_provider(self):
        context = RepresentationContext(purpose="Plan")

        class Provider:
            def getRepresentation(self, obj, requested_context):
                self.args = (obj, requested_context)
                return BIMRepresentation(source=obj, context=requested_context)

        class BIMObject:
            pass

        obj = BIMObject()
        obj.Proxy = Provider()
        result = representation_for(obj, context)
        self.assertIs(result.source, obj)
        self.assertIs(result.context, context)
        self.assertEqual(obj.Proxy.args, (obj, context))

    def test_representation_for_does_not_dispatch_on_type_name(self):
        class BIMObject:
            pass

        obj = BIMObject()
        obj.Proxy = object()
        with self.assertRaises(RepresentationUnavailable):
            representation_for(obj, RepresentationContext())


if __name__ == "__main__":
    unittest.main()
