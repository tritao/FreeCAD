# SPDX-License-Identifier: LGPL-2.1-or-later

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import FreeCAD

import ArchComponent
from ArchRepresentation import (
    BIMEditHandle,
    BIMEditOperation,
    RepresentationPurpose,
    RepresentationRequest,
)
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

    def test_plan_picking_selection_and_snap_use_canonical_semantic_handles(self):
        source = object()
        operation = BIMEditOperation(
            "move", "Move", lambda _source: FreeCAD.Vector(), lambda *_args: None,
            value_kind="Point",
        )
        handle = BIMEditHandle(
            source,
            "endpoint",
            FreeCAD.Vector(1, 2, 3),
            FreeCAD.Vector(1, 0, 0),
            operation,
            subelement="Vertex1",
        )

        class View:
            def getPointOnScreen(self, point):
                return point.x, point.y

        class Renderer:
            def __init__(self):
                self.visible_sources = ()
                self.snap_request = None

            def pick_edit_handle(self, _position, _project, radius_px=8):
                return handle

            def edit_handles_for(self, candidate):
                return (handle,) if candidate is source else ()

            def set_visible_handle_sources(self, sources):
                self.visible_sources = tuple(sources)
                return True

            def query_snap(self, point, tolerance, request=None):
                self.snap_request = (point, tolerance, request)
                return "semantic-snap"

        session = PlanEditSession(view=View())
        renderer = Renderer()
        session.contextual_rendering.renderer = renderer

        picked = session.picking.pick_edit_handle((12, 24))
        self.assertIs(picked, handle)
        self.assertIsInstance(picked, BIMEditHandle)
        self.assertTrue(session.selection.select_handle(picked))
        self.assertIs(session.selection.selected_handle, handle)
        self.assertIs(session.selection.selected_source, source)
        self.assertEqual((source,), renderer.visible_sources)

        point = FreeCAD.Vector(4, 5, 6)
        self.assertEqual(
            "semantic-snap",
            session.snap._query_semantic_snap(point, 0.5),
        )
        self.assertEqual((point, 0.5, session.request), renderer.snap_request)

        session.selection.clear()
        self.assertEqual((), renderer.visible_sources)

    def test_plan_selection_activates_only_rendered_domain_handles(self):
        sources = tuple(
            SimpleNamespace(IfcType=kind) for kind in ("Wall", "Window", "Space")
        )
        handles = tuple(
            BIMEditHandle(
                source,
                "semantic-edit",
                FreeCAD.Vector(),
                FreeCAD.Vector(1, 0, 0),
                BIMEditOperation(
                    "semantic-edit", "Edit", lambda _source: 0.0, lambda *_args: None
                ),
            )
            for source in sources
        )

        class Renderer:
            def __init__(self):
                self.visible_sources = ()

            def edit_handles_for(self, source):
                return tuple(handle for handle in handles if handle.source is source)

            def set_visible_handle_sources(self, sources):
                self.visible_sources = tuple(sources)
                return True

        activated = []
        session = PlanEditSession()
        renderer = Renderer()
        session.contextual_rendering.renderer = renderer
        session.contextual_editing = SimpleNamespace(
            activate=lambda handle: activated.append(handle) or True
        )

        for source, handle in zip(sources, handles):
            self.assertTrue(session.selection.activate_handle(handle))
            self.assertIs(session.selection.selected_source, source)

        unknown = BIMEditHandle(
            object(), "unknown", FreeCAD.Vector(), FreeCAD.Vector(), handles[0].operation
        )
        self.assertFalse(session.selection.activate_handle(unknown))
        self.assertEqual(list(handles), activated)
        self.assertEqual((sources[-1],), renderer.visible_sources)

    def test_plan_space_adapter_delegates_evaluation_and_boundary_mutation(self):
        from bimplan.tools import space_editing

        space = object()
        document = object()
        refreshed = []
        session = SimpleNamespace(
            doc=document,
            contextual_rendering=SimpleNamespace(refresh_object=refreshed.append),
        )
        boundaries = ((object(), ("Face1",)),)
        evaluation = object()

        with (
            patch("ArchSpaceSemantic.evaluate_boundaries", return_value=evaluation) as evaluate,
            patch("ArchSpaceSemantic.set_boundaries", return_value=space) as set_boundaries,
        ):
            self.assertIs(
                evaluation,
                space_editing.evaluate_space_boundaries(
                    boundaries, label="Office", seed_space=space, candidates=True
                ),
            )
            self.assertTrue(space_editing.set_space_boundaries(session, space, boundaries))

        evaluate.assert_called_once_with(
            boundaries, label="Office", seed_space=space, candidates=True
        )
        set_boundaries.assert_called_once_with(
            document,
            space,
            boundaries,
            transaction_name="Edit Space Boundaries",
        )
        self.assertEqual([space], refreshed)

        with patch(
            "ArchSpaceSemantic.set_boundaries", side_effect=ValueError("invalid boundary")
        ):
            self.assertFalse(space_editing.set_space_boundaries(session, space, boundaries))
        self.assertEqual([space], refreshed)

    def test_plan_wall_and_opening_creation_delegate_to_domain_services(self):
        from contextlib import nullcontext

        import ArchOpeningConstruction
        from bimplan.tools import wall_create, window_create

        document = object()
        wall = object()
        point = FreeCAD.Vector(100, 200, 0)
        created_walls = (object(), object())
        session = SimpleNamespace(
            doc=document,
            creation_preview_state=SimpleNamespace(
                rect_wall_params={
                    "width": 200.0,
                    "height": 3000.0,
                    "align": "Center",
                    "offset": 0.0,
                },
                opening_kind="Door",
            ),
            visibility=SimpleNamespace(
                register_plan_object=lambda _obj: None,
                add_object_to_active_storey=lambda _obj: None,
            ),
            document_visuals=SimpleNamespace(defer_document_visual_updates=nullcontext),
            openings=SimpleNamespace(is_hosted_opening_object=lambda _obj: True),
        )

        with patch(
            "bimplan.tools.wall_create.wall_construction.construct_wall_run",
            return_value=created_walls,
        ) as construct_wall:
            result = wall_create.create_rect_wall_run(
                session,
                (
                    FreeCAD.Vector(0, 0, 0),
                    FreeCAD.Vector(1000, 0, 0),
                    FreeCAD.Vector(1000, 1000, 0),
                    FreeCAD.Vector(0, 1000, 0),
                ),
            )

        self.assertEqual(list(created_walls), result)
        wall_spec = construct_wall.call_args.args[2]
        self.assertEqual(200.0, wall_spec.width)
        self.assertEqual(3000.0, wall_spec.height)
        self.assertTrue(construct_wall.call_args.kwargs["closed"])
        self.assertIs(
            construct_wall.call_args.kwargs["on_created"],
            session.visibility.register_plan_object,
        )

        opening = object()
        with (
            patch(
                "bimplan.tools.window_create.project_window_point_to_host",
                return_value=point,
            ),
            patch(
                "ArchOpeningConstruction.construct_hosted_opening",
                return_value=opening,
            ) as construct_opening,
        ):
            self.assertIs(window_create.create_hosted_opening(session, wall, point), opening)

        opening_spec = construct_opening.call_args.args[3]
        self.assertEqual("Door", opening_spec.kind)
        self.assertIs(construct_opening.call_args.args[0], document)
        self.assertIs(construct_opening.call_args.args[1], wall)
        self.assertTrue(construct_opening.call_args.args[2].isEqual(point, 1e-7))
        self.assertTrue(session.openings.is_hosted_opening_object(opening))

    def test_contextual_edit_activation_uses_controller_and_cleans_prior_input(self):
        from bimplan.contextual_editing import PlanContextualEditingAPI

        class Snap:
            def __init__(self):
                self.clears = 0

            def clear_active_draft_command(self):
                self.clears += 1

        class Renderer:
            def refresh_object(self, _source):
                pass

        class Host:
            def __init__(self):
                self.inputs = []
                self.clears = 0

            def set_value_input(self, **kwargs):
                self.inputs.append(kwargs)

            def clear_value_input(self):
                self.clears += 1

        outcomes = iter((True, False))

        class Controller:
            def __init__(self, *_args, **_kwargs):
                self.editor = None
                self.activations = []
                self.begins = []
                self.cancellations = 0
                self.value_commits = []

            def activate(self, handle):
                self.activations.append(handle)
                if next(outcomes):
                    self.editor = SimpleNamespace(handle=handle)
                    return True
                return False

            def begin(self, handle):
                self.begins.append(handle)

            def cancel(self, **_kwargs):
                self.cancellations += 1

            def commit_value(self, value):
                self.value_commits.append(value)
                return SimpleNamespace(success=True)

        source = {"height": 2400.0}
        operation = BIMEditOperation(
            "height",
            "Set height",
            lambda obj: obj["height"],
            lambda obj, value: obj.__setitem__("height", value),
            value_kind="Scalar",
        )
        handle = BIMEditHandle(
            source,
            "height",
            FreeCAD.Vector(),
            FreeCAD.Vector(1, 0, 0),
            operation,
        )
        session = PlanEditSession(view=object())
        session.snap = Snap()
        session.contextual_rendering = Renderer()
        editing = PlanContextualEditingAPI(session)
        host = Host()
        editing.input_adapter.host = host

        with patch(
            "bimplan.contextual_editing.ContextualEditController", Controller
        ):
            self.assertTrue(editing.activate(handle))
            first_controller = editing.controller
            self.assertEqual([handle], first_controller.activations)
            self.assertEqual([], first_controller.begins)
            self.assertEqual("Set height", host.inputs[0]["label"])
            self.assertEqual("Length", host.inputs[0]["unit"])
            self.assertEqual(2400.0, host.inputs[0]["value"])
            self.assertTrue(host.inputs[0]["callback"](2600.0))
            self.assertEqual([2600.0], first_controller.value_commits)

            self.assertFalse(editing.activate(handle))

        self.assertEqual(1, first_controller.cancellations)
        self.assertEqual(3, host.clears)
        self.assertEqual(2, session.snap.clears)
        self.assertEqual([], editing.controller.begins)
        self.assertEqual(1, len(host.inputs))

    def test_contextual_edit_cancel_clears_point_and_value_input(self):
        from bimplan.contextual_editing import PlanContextualEditingAPI

        class Snap:
            def __init__(self):
                self.clears = 0

            def clear_active_draft_command(self):
                self.clears += 1

        class Renderer:
            def refresh_object(self, _source):
                pass

        class Controller:
            def __init__(self, *_args, **_kwargs):
                self.editor = None
                self.cancellations = []

            def cancel(self, **kwargs):
                self.cancellations.append(kwargs)

        class Host:
            def __init__(self):
                self.clears = 0

            def clear_value_input(self):
                self.clears += 1

        session = PlanEditSession(view=object())
        session.snap = Snap()
        session.contextual_rendering = Renderer()
        editing = PlanContextualEditingAPI(session)
        controller = Controller()
        host = Host()
        editing.controller = controller
        editing.input_adapter.host = host

        editing.cancel(refresh=False)

        self.assertEqual([{"refresh": False}], controller.cancellations)
        self.assertEqual(1, session.snap.clears)
        self.assertEqual(1, host.clears)

    def test_plan_overlay_refreshes_coalesce_and_close_discards_pending_work(self):
        from bimplan.overlays.manager import PlanOverlayManagerService
        from bimplan.runtime.session_state import PlanOverlayRefreshState

        scheduled = []
        refreshed = []
        session = SimpleNamespace(overlay_refresh_state=PlanOverlayRefreshState())
        manager = PlanOverlayManagerService(
            session,
            scheduler=scheduled.append,
            refresh_callback=refreshed.append,
        )

        self.assertTrue(manager.queue_plan_overlay_visual_refresh(("hovered",)))
        self.assertTrue(manager.queue_plan_overlay_visual_refresh(("selected",)))
        self.assertEqual(1, len(scheduled))
        self.assertEqual({"hovered", "selected"}, session.overlay_refresh_state.dirty_plan_visuals)

        scheduled.pop()()

        self.assertEqual([{"hovered", "selected"}], refreshed)
        self.assertFalse(session.overlay_refresh_state.overlay_refresh_queued)
        self.assertEqual(set(), session.overlay_refresh_state.dirty_plan_visuals)

        self.assertTrue(manager.queue_plan_overlay_visual_refresh(("hovered",)))
        pending = scheduled.pop()
        manager.close()
        pending()
        self.assertEqual([{"hovered", "selected"}], refreshed)
        self.assertFalse(manager.queue_plan_overlay_visual_refresh(("selected",)))

    def test_plan_status_feedback_is_invalidated_when_semantic_context_changes(self):
        from bimplan.ui.status_text import PlanStatusTextAPI

        session = SimpleNamespace(
            current_tool="Select",
            representation_request=SimpleNamespace(
                request=SimpleNamespace(source=object())
            ),
            selection=SimpleNamespace(selected_handle=object()),
        )
        status = PlanStatusTextAPI(session)

        self.assertEqual(
            "Wall has no editable endpoint.",
            status.set_integration_feedback_message(" Wall has no editable endpoint. "),
        )
        self.assertEqual("Wall has no editable endpoint.", status.get_integration_feedback_message())

        session.selection.selected_handle = object()

        self.assertEqual("", status.get_integration_feedback_message())


if __name__ == "__main__":
    unittest.main()
