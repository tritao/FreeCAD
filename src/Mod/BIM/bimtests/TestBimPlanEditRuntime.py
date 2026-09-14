# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest
from types import SimpleNamespace

import FreeCAD

import ArchComponent
from ArchRepresentation import RepresentationPurpose, RepresentationRequest
from bimplan.representation_request import (
    PlanRepresentationRequestAPI,
    representation_request_from_source,
    representation_request_from_storey,
)
from bimplan.runtime.session import PlanEditSession


class TestBimPlanEditRuntime(unittest.TestCase):
    def make_storey(self):
        return SimpleNamespace(
            IfcType="Building Storey",
            Placement=FreeCAD.Placement(
                FreeCAD.Vector(0, 0, 3200), FreeCAD.Rotation()
            ),
            LevelOffset=SimpleNamespace(Value=150.0),
            PlanCutHeight=SimpleNamespace(Value=1200.0),
        )

    def test_storey_request_contains_plan_cut_and_target_offsets(self):
        storey = self.make_storey()

        request = representation_request_from_storey(storey)

        self.assertEqual(RepresentationPurpose.PLAN, request.purpose)
        self.assertEqual(3350.0, request.target_offset)
        self.assertEqual(4550.0, request.cut_offset)
        self.assertIs(request.source, storey)

    def test_storey_request_uses_default_cut_height(self):
        storey = self.make_storey()
        storey.PlanCutHeight = 0.0

        request = representation_request_from_storey(storey)

        self.assertEqual(3350.0, request.target_offset)
        self.assertEqual(
            3350.0 + ArchComponent.DEFAULT_PLAN_CUT_HEIGHT,
            request.cut_offset,
        )

    def test_object_request_provider_precedes_storey_fallback(self):
        request = RepresentationRequest(purpose=RepresentationPurpose.SECTION)

        class Proxy:
            def getRepresentationRequest(self, _source):
                return request

        source = SimpleNamespace(IfcType="Wall", Proxy=Proxy())

        self.assertIs(representation_request_from_source(source), request)
        self.assertIsNone(representation_request_from_source(SimpleNamespace()))

    def test_request_api_tracks_source_and_projects_in_reference_frame(self):
        frame = FreeCAD.Placement(
            FreeCAD.Vector(10, 20, 30),
            FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90),
        )
        request = RepresentationRequest(
            purpose=RepresentationPurpose.PLAN,
            reference_frame=frame,
            target_offset=4.0,
        )
        target = object()

        class Proxy:
            def getRepresentationRequest(self, _source):
                return request

        source = SimpleNamespace(Proxy=Proxy(), Objects=(target,))
        session = PlanEditSession()
        api = PlanRepresentationRequestAPI(session)

        self.assertIs(api.set_source(source, refresh=False), request)
        global_point = frame.multVec(FreeCAD.Vector(5, 6, 8))
        local_point = api.to_local(global_point)
        self.assertTrue(local_point.isEqual(FreeCAD.Vector(5, 6, 8), 1e-7))
        self.assertTrue(api.to_global(local_point).isEqual(global_point, 1e-7))
        projected = api.project_to_plane(global_point)
        expected = frame.multVec(FreeCAD.Vector(5, 6, 4))
        self.assertTrue(projected.isEqual(expected, 1e-7))
        self.assertTrue(api.includes_object(target))
        self.assertFalse(api.includes_object(object()))

    def test_plan_session_starts_from_explicit_storey_request(self):
        storey = self.make_storey()

        session = PlanEditSession(active_storey=storey)

        self.assertIs(session.active_storey, storey)
        self.assertIs(session.request.source, storey)
        self.assertEqual(RepresentationPurpose.PLAN, session.request.purpose)
        self.assertEqual(4550.0, session.request.cut_offset)


if __name__ == "__main__":
    unittest.main()
