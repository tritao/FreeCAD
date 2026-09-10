# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest
import sys
import types
from pathlib import Path

from ArchRepresentation import (
    BIMRepresentation,
    PlanContext,
    RepresentationContext,
    RepresentationPurpose,
    representation_for,
)


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

    def test_plan_context_preserves_horizontal_compatibility(self):
        context = PlanContext(cut_z=1.0, target_z=0.0)

        self.assertIs(context.purpose, RepresentationPurpose.PLAN)
        self.assertEqual(context.cut_z, 1.0)
        self.assertEqual(context.target_z, 0.0)
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
        with self.assertRaises(TypeError):
            representation_for(obj, RepresentationContext())

    def test_techdraw_projects_the_shared_representation_contract(self):
        techdraw_path = str(Path(__file__).resolve().parents[2] / "TechDraw")
        sys.path.insert(0, techdraw_path)
        try:
            import TechDrawBIM
        finally:
            sys.path.pop(0)

        shape = object()
        representation = BIMRepresentation()
        representation.add_geometry("projected_geometry", shape, "projected")

        calls = []
        fake_techdraw = types.SimpleNamespace(
            projectToSVG=lambda projected, direction, **styles: calls.append(
                (projected, direction, styles)
            )
            or "<svg />"
        )
        previous = sys.modules.get("TechDraw")
        sys.modules["TechDraw"] = fake_techdraw
        try:
            result = TechDrawBIM.project_representation_to_svg(
                representation,
                (0, 0, 1),
                stroke="#000000",
            )
        finally:
            if previous is None:
                del sys.modules["TechDraw"]
            else:
                sys.modules["TechDraw"] = previous

        self.assertEqual(result, "<svg />")
        self.assertEqual(calls, [(shape, (0, 0, 1), {"stroke": "#000000"})])


if __name__ == "__main__":
    unittest.main()
