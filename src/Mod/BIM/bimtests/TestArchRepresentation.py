# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest

import FreeCAD
import Part
import Arch
import Draft

from ArchRepresentation import (
    BIMEditHandle,
    BIMEditOperation,
    BIMRepresentation,
    RepresentationUnavailable,
    RepresentationContext,
    RepresentationPurpose,
    query_representation_pick,
    query_representation_snap,
    representation_for,
)
from bimplan.contextual_editing import BIMContextualHandleEditor
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
        editor = BIMContextualHandleEditor(
            RepresentationContext(purpose="Plan"), refreshed.append
        )

        editor.begin(handle)
        preview = editor.preview(FreeCAD.Vector(25, 50, 10))
        self.assertEqual(125.0, preview.value)
        self.assertEqual(FreeCAD.Vector(25, 0, 0), preview.point)
        result = editor.commit(FreeCAD.Vector(25, 50, 10))

        self.assertTrue(result.success)
        self.assertEqual(125.0, source["width"])
        self.assertEqual([source], refreshed)
        self.assertIsNone(editor.handle)

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

        handles = {
            handle.subelement: handle for handle in representation.edit_handles
        }
        self.assertTrue({"Path.Start", "Path.End"}.issubset(handles))
        self.assertEqual("Point", handles["Path.End"].operation.value_kind)

    def test_wall_width_handle_uses_alignment_sensitivity(self):
        document = FreeCAD.newDocument("ContextualWallWidthTest")
        self.addCleanup(FreeCAD.closeDocument, document.Name)
        wall = Arch.makeWall(length=3000, width=200, height=3000, align="Center")
        document.recompute()
        context = RepresentationContext(
            purpose="Plan", cut_offset=1000, target_offset=0
        )
        representation = wall.Proxy.getRepresentation(wall, context)
        handle = next(item for item in representation.edit_handles if item.role == "WallWidth")

        self.assertEqual(2.0, handle.operation.sensitivity)
        editor = BIMContextualHandleEditor(context)
        editor.begin(handle)
        result = editor.commit(handle.point + handle.direction * 50)

        self.assertTrue(result.success)
        self.assertAlmostEqual(300.0, wall.Width.Value)

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
            RepresentationContext(
                purpose="Plan", cut_offset=1000, target_offset=0
            ),
        )

        self.assertIs(representation.source, opening)
        self.assertTrue(representation.projected_geometry)
        self.assertTrue(representation.snap_geometry)
        self.assertTrue(representation.edit_handles)
        self.assertTrue(
            all(mapping.source is opening for mapping in representation.source_mappings)
        )

    def test_snap_query_preserves_semantic_identity(self):
        source = object()
        edge = Part.makeLine(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, 0, 0))
        representation = BIMRepresentation(source=source)
        representation.add_geometry("snap_geometry", edge, "axis", "Edge1")

        result = query_representation_snap(
            (representation,), FreeCAD.Vector(4, 0.5, 0), 1.0
        )

        self.assertIs(result.source, source)
        self.assertEqual("Edge1", result.subelement)
        self.assertEqual("axis", result.role)
        self.assertAlmostEqual(0.5, result.distance)

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
