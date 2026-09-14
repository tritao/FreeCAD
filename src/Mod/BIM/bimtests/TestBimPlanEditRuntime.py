# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
    def make_storey(self, name="Level1", elevation=3200):
        return SimpleNamespace(
            IfcType="Building Storey",
            Name=name,
            Placement=FreeCAD.Placement(
                FreeCAD.Vector(0, 0, elevation), FreeCAD.Rotation()
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

    def test_visibility_scopes_objects_to_the_active_storey(self):
        active_storey = self.make_storey()
        other_storey = self.make_storey("Level2", elevation=5000)

        class Item:
            def __init__(self, name, storey):
                self.Name = name
                self.InListRecursive = (storey,)

        active_object = Item("Wall1", active_storey)
        other_object = Item("Wall2", other_storey)

        class View:
            def __init__(self):
                self.visibility = []

            def setViewVisibility(self, layer, obj, state):
                self.visibility.append((layer, obj, state))
                return True

        view = View()
        session = PlanEditSession(
            active_storey,
            doc=SimpleNamespace(Objects=(active_object, other_object)),
            view=view,
        )
        layer = object()
        session.contextual_rendering.renderer = SimpleNamespace(layer=layer)

        self.assertTrue(session.visibility.object_belongs_to_active_storey(active_object))
        self.assertFalse(session.visibility.object_belongs_to_active_storey(other_object))
        session.visibility.apply_storey_visibility()

        self.assertEqual([(layer, other_object, "Hidden")], view.visibility)

    def test_plan_renderer_uses_shared_representations_and_viewer_local_visibility(self):
        storey = self.make_storey()

        class Item:
            def __init__(self, name, parent):
                self.Name = name
                self.InListRecursive = (parent,)

        active_object = Item("Wall1", storey)
        other_storey = self.make_storey("Level2", elevation=5000)
        other_object = Item("Wall2", other_storey)
        document = SimpleNamespace(Objects=(active_object, other_object))

        class View:
            def __init__(self):
                self.visibility = []

            def setViewVisibility(self, layer, obj, state):
                self.visibility.append((layer, obj, state))
                return True

        class Renderer:
            def __init__(self, _view):
                self.layer = object()
                self.representations = {}
                self.closed = False

            def set_representation(self, representation):
                self.representations[representation.source] = representation

            def remove_representation(self, source):
                self.representations.pop(source, None)

            def close(self):
                self.closed = True

        view = View()
        session = PlanEditSession(storey, doc=document, view=view)
        representation = SimpleNamespace(source=active_object)

        with (
            patch(
                "bimplan.contextual_rendering.BimContextualRendering."
                "ContextualRepresentationRenderer",
                Renderer,
            ),
            patch(
                "bimplan.contextual_rendering.ArchRepresentation.representation_for",
                side_effect=lambda obj, _request: (
                    representation if obj is active_object else None
                ),
            ),
        ):
            renderer = session.contextual_rendering.start()

        self.assertEqual({active_object}, set(renderer.representations))
        self.assertEqual(
            [(renderer.layer, other_object, "Hidden")], view.visibility
        )
        session.contextual_rendering.close()
        self.assertTrue(renderer.closed)


if __name__ == "__main__":
    unittest.main()
