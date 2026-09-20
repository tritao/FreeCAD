# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI tests for the viewer-local BIM Plan Edit session."""

from unittest.mock import patch
from types import SimpleNamespace

import Arch
from ArchContextualCreation import architectural_contextual_providers
import ArchWall
import ArchWallRelation
import FreeCAD
import FreeCADGui
import Part
from pivy import coin
from ArchRepresentation import (
    BIMEditRay,
    RepresentationRequest,
    RepresentationPurpose,
    preview_state_from_representation,
)
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimplan.runtime.session import PlanEditSession, activate_representation_request
from bimplan import document_visuals as plan_document_visuals
from bimplan import snap as plan_snap
from bimcontextual.session import ContextualSession
from bimcontextual.interaction import ContextualInteractionHost
from bimcontextual import context_policy
from bimcontextual.actions import ContextualProvider, ContextualToolSpec
from ArchWallSemantic import apply_wall_candidate
from bimplan.storeys import collect_storeys, find_initial_storey, get_storey_elevation
from bimplan.providers import PlanEditProvider, PlanEditRegistry
from BimContextualRendering import (
    ContextualInteractionRenderer,
    ContextualNodeMapping,
    ContextualRepresentationRenderer,
    ray_from_view,
)


class _TestProvider(PlanEditProvider):
    def __init__(self, provider_id):
        self.provider_id = provider_id

    def get_provider_id(self):
        return self.provider_id


class _ContextualToolProvider(ContextualProvider):
    provider_id = "test-contextual-tools"

    def __init__(self):
        self.executed = []

    def get_tools(self, context):
        del context
        return (ContextualToolSpec("inspect", "Inspect", provider_id=self.provider_id),)

    def execute_tool(self, tool_key, context, commands=None, payload=None):
        del context, commands, payload
        self.executed.append(tool_key)
        return True


class _HostedOpeningProxy:
    """Minimal semantic opening used to exercise host-relative wall movement."""

    def __init__(self, obj):
        self.Object = obj

    def get_hosted_opening_move_context(self):
        return {"opening_half_width_u": 50.0}

    def get_hosted_opening_center_point(self):
        return FreeCAD.Vector(self.Object.Placement.Base)

    def project_hosted_opening_move_point(self, point, anchor="center"):
        del anchor
        return FreeCAD.Vector(point)


class TestBimPlanEditSessionGui(TestArchBaseGui):
    def test_session_prepare_defers_semantic_rendering_until_populate(self):
        session = PlanEditSession()
        self.assertTrue(session.prepare())
        try:
            self.assertTrue(session._prepared)
            self.assertFalse(session._populated)
            self.assertIsNone(session.contextual_rendering.renderer)
            self.assertFalse(session.contextual_rendering.is_ready)

            self.assertTrue(session.populate(attach_task_panel=False))
            self.assertTrue(session._populated)
            self.assertIsNotNone(session.contextual_rendering.renderer)
            self.assertTrue(session.contextual_rendering.is_ready)
        finally:
            session.shutdown(close_dialog=False)

    def test_session_enter_keeps_synchronous_compatibility_contract(self):
        session = PlanEditSession()
        self.assertTrue(session.enter(attach_task_panel=False))
        try:
            self.assertTrue(session._prepared)
            self.assertTrue(session._populated)
            self.assertIsNotNone(session.contextual_rendering.renderer)
            self.assertTrue(session.contextual_rendering.is_ready)
        finally:
            session.shutdown(close_dialog=False)

    def test_freecadgui_adopt_qobject_survives_parent_teardown(self):
        """An adopted Python widget tree may be destroyed by its C++ parent."""

        from PySide import QtWidgets
        from shiboken6 import Shiboken
        import FreeCADGui

        host = QtWidgets.QWidget()
        child = QtWidgets.QWidget(host)
        grandchild = QtWidgets.QLabel(child)
        destroyed = []
        child.destroyed.connect(lambda: destroyed.append(True))

        FreeCADGui.adoptQObject(child)
        del grandchild, child
        Shiboken.delete(host)

        QtWidgets.QApplication.processEvents()
        self.assertTrue(destroyed)

    def test_freecadgui_delete_later_pins_deferred_widget_trees(self):
        """Deferred deletion must keep every wrapped Qt child alive."""

        from PySide import QtCore, QtWidgets
        import FreeCADGui
        destroyed = []
        callbacks = []
        parent = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(parent)
        child = QtWidgets.QLabel(parent)
        layout.addWidget(child)
        parent.destroyed.connect(lambda: destroyed.append(True))

        FreeCADGui.deleteLater(parent)
        FreeCADGui.invokeLater(lambda: callbacks.append(True))
        del child, layout, parent

        loop = QtCore.QEventLoop()
        FreeCADGui.invokeLater(loop.quit)
        loop.exec_()
        for _ in range(3):
            QtCore.QCoreApplication.sendPostedEvents(
                None, QtCore.QEvent.DeferredDelete
            )
            QtWidgets.QApplication.processEvents()

        self.assertTrue(destroyed)
        self.assertTrue(callbacks)

    def test_freecadgui_invoke_later_releases_callback_when_it_raises(self):
        """A callback failure must not leave its retained timer behind."""

        import sys
        from unittest.mock import patch

        from PySide import QtCore, QtWidgets
        import FreeCADGui
        callback_calls = []

        def fail():
            callback_calls.append(True)
            raise RuntimeError("expected timer callback failure")

        loop = QtCore.QEventLoop()
        with patch.object(sys, "excepthook") as excepthook:
            FreeCADGui.invokeLater(fail)
            FreeCADGui.invokeLater(loop.quit)
            loop.exec_()
            for _ in range(3):
                QtCore.QCoreApplication.sendPostedEvents(
                    None, QtCore.QEvent.DeferredDelete
                )
                QtWidgets.QApplication.processEvents()

        self.assertTrue(callback_calls)
        excepthook.assert_called_once()

    def test_hover_throttle_resolves_latest_pointer_position(self):
        """A stopped pointer must not leave the last throttled hover unresolved."""

        from bimplan.picking import hover as plan_hover
        from bimplan.runtime.session_state import PlanHoverPickState

        callbacks = []
        session = SimpleNamespace(
            hover_pick_state=PlanHoverPickState(last_time=10.0),
            lifecycle_state=SimpleNamespace(tearing_down=False),
            performance=SimpleNamespace(plan_perf_count=lambda *args, **kwargs: None),
        )
        with (
            patch.object(plan_hover.time, "monotonic", side_effect=(10.01, 10.02)),
            patch.object(
                FreeCADGui,
                "invokeLater",
                side_effect=lambda callback, _delay=0: callbacks.append(callback),
            ),
        ):
            self.assertTrue(plan_hover.should_skip_hover_pick(session, (10, 20)))
            self.assertTrue(plan_hover.should_skip_hover_pick(session, (30, 40)))

        self.assertEqual(1, len(callbacks))
        with patch.object(plan_hover, "update_hovered_plan_target") as update_hover:
            callbacks[0]()
        update_hover.assert_called_once_with(session, (30.0, 40.0), force=True)

    def test_plan_snap_api_configures_only_the_session_view_context(self):
        """Plan Edit's modes and plane stay local to its originating view."""

        plane = SimpleNamespace(
            position=FreeCAD.Vector(0, 0, 0),
            u=FreeCAD.Vector(1, 0, 0),
            v=FreeCAD.Vector(0, 1, 0),
        )
        context = SimpleNamespace(interaction_plane=None)
        view = object()
        session = SimpleNamespace(
            view=view,
            viewport=SimpleNamespace(get_interaction_plane=lambda: plane),
        )

        class _Snapper:
            def context_for(self, candidate):
                self.context_view = candidate
                return context

            def configure_view(self, candidate, **kwargs):
                self.configured_view = candidate
                if "interaction_plane" in kwargs:
                    context.interaction_plane = kwargs["interaction_plane"]
                if "modes" in kwargs:
                    self.configured_modes = tuple(kwargs["modes"])

            def get_snap_modes(self, view=None):
                del view
                return getattr(self, "configured_modes", ("Lock", "Grid"))

            def push_snap_modes(self, modes, view=None):
                self.pushed_modes = tuple(modes)
                self.pushed_view = view

            def pop_snap_modes(self, view=None):
                self.popped_view = view

        snapper = _Snapper()
        with patch.object(FreeCADGui, "Snapper", snapper, create=True):
            api = plan_snap.PlanSnapAPI(session, ("Lock", "Grid"))
            api.apply_plan_snap_profile()
            self.assertIs(view, snapper.context_view)
            self.assertIs(view, snapper.configured_view)
            self.assertIs(view, snapper.pushed_view)
            self.assertIs(plane, context.interaction_plane)
            self.assertTrue(api.is_grid_snap_enabled())

            self.assertTrue(api.set_grid_snap_enabled(False))
            self.assertNotIn("Grid", snapper.configured_modes)
            self.assertFalse(api.is_grid_snap_enabled())
            self.assertTrue(api.set_grid_snap_enabled(True))
            self.assertIn("Grid", snapper.configured_modes)

            api.restore_snap_profile()
            self.assertIs(view, snapper.popped_view)
            self.assertIsNone(context.interaction_plane)

    def test_plan_snap_api_installs_reference_frame_grid_and_restores_it(self):
        """Plan Edit owns a temporary lattice and leaves Draft's provider intact."""

        plane = SimpleNamespace(
            position=FreeCAD.Vector(100, 200, 300),
            u=FreeCAD.Vector(0, 1, 0),
            v=FreeCAD.Vector(-1, 0, 0),
        )
        session = SimpleNamespace(
            viewport=SimpleNamespace(get_interaction_plane=lambda: plane),
        )
        pushed = []

        class _Snapper:
            def push_interaction_grid(self, grid):
                pushed.append(grid)

            def pop_interaction_grid(self, grid):
                self.restored = grid
                return grid

        snapper = _Snapper()
        with patch.object(FreeCADGui, "Snapper", snapper, create=True):
            api = plan_snap.PlanSnapAPI(session, ())
            grid = api.apply_plan_grid()
            self.assertIs(grid, pushed[0])
            self.assertAlmostEqual(100.0, grid.spacing)
            self.assertEqual(10, grid.major_every)
            self.assertEqual(FreeCAD.Vector(100, 200, 300), grid.origin)
            self.assertEqual(FreeCAD.Vector(0, 1, 0), grid.u_axis)
            self.assertEqual(FreeCAD.Vector(-1, 0, 0), grid.v_axis)
            self.assertIs(grid, api.apply_plan_grid())
            self.assertIs(grid, api.restore_plan_grid())
            self.assertIs(grid, snapper.restored)
            self.assertIsNone(api.restore_plan_grid())

    def test_contextual_task_panel_consumes_provider_tools(self):
        provider = _ContextualToolProvider()
        session = ContextualSession(
            FreeCADGui.ActiveDocument.ActiveView, sources=(), providers=(provider,)
        )
        try:
            self.pump_gui_events(20)
            self.assertTrue(session.action_panel._shown)
            self.assertEqual(("inspect",), tuple(tool.key for tool in session.contextual_tools))
            self.assertTrue(session.activate_tool(session.contextual_tools[0]))
            self.assertEqual(["inspect"], provider.executed)
        finally:
            session.close()

    def test_contextual_point_host_uses_the_representation_reference_plane(self):
        frame = FreeCAD.Placement(
            FreeCAD.Vector(100, 200, 300),
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90),
        )
        request = RepresentationRequest(
            purpose=RepresentationPurpose.SECTION, reference_frame=frame
        )
        host = ContextualInteractionHost(request)
        plane = host.get_interaction_plane()
        projected = plane.project_point(FreeCAD.Vector(125, 900, 340))
        local = frame.inverse().multVec(projected)
        self.assertAlmostEqual(0.0, local.z, places=7)

    def test_contextual_capability_matrix_is_explicit(self):
        model = RepresentationRequest(purpose=RepresentationPurpose.MODEL)
        plan = RepresentationRequest(purpose=RepresentationPurpose.PLAN)
        section = RepresentationRequest(purpose=RepresentationPurpose.SECTION)
        elevation = RepresentationRequest(purpose=RepresentationPurpose.ELEVATION)
        self.assertTrue(context_policy.supports(model, "create-wall"))
        self.assertTrue(context_policy.supports(plan, "create-wall"))
        self.assertFalse(context_policy.supports(section, "create-wall"))
        self.assertFalse(context_policy.supports(elevation, "create-wall"))
        self.assertTrue(context_policy.supports(section, "insert-opening"))
        self.assertFalse(context_policy.supports(section, "wall-path"))

    @staticmethod
    def _wall_preview_session(renderer):
        def footprint(path, width, align):
            start, end = path
            axis = end.sub(start)
            axis.normalize()
            lateral = axis.cross(FreeCAD.Vector(0, 0, 1))
            half_width = float(width) * 0.5
            if align == "Left":
                low, high = -float(width), 0.0
            elif align == "Right":
                low, high = 0.0, float(width)
            else:
                low, high = -half_width, half_width
            return [
                start + lateral * low,
                end + lateral * low,
                end + lateral * high,
                start + lateral * high,
            ]

        return SimpleNamespace(
            contextual_rendering=renderer,
            representation_request=SimpleNamespace(request=RepresentationRequest()),
            wall_edit=SimpleNamespace(get_preview_footprint=footprint),
        )

    def test_semantic_wall_creation_tracker_uses_contextual_preview(self):
        from bimplan.tools.wall_create import SemanticWallPreviewTracker

        renderer = SimpleNamespace(
            previews=[],
            cleared=[],
            set_preview_state=lambda state: renderer.previews.append(state),
            clear_preview=lambda source: renderer.cleared.append(source),
        )
        tracker = SemanticWallPreviewTracker(self._wall_preview_session(renderer))
        tracker.width(200)
        tracker.on()
        tracker.update([FreeCAD.Vector(), FreeCAD.Vector(1000, 0, 0)])

        self.assertEqual(1, len(renderer.previews))
        state = renderer.previews[0]
        source = state.primary_source
        representation = state.representation_for(source)
        self.assertIs(source, representation.source)
        self.assertEqual(1, len(representation.cut_geometry))
        self.assertEqual(1, len(representation.projected_geometry))

        tracker.finalize()
        self.assertEqual([source], renderer.cleared)

    def test_embedded_wall_point_request_preserves_plan_task_panel(self):
        from draftguitools import gui_base
        from bimplan.runtime.embedded_commands import _PlanEditWallHost

        host = _PlanEditWallHost(SimpleNamespace())
        callback = lambda point: None
        with patch.object(gui_base.DraftInteractionHost, "request_point") as request_point:
            host.request_point(callback, title="First Point of Wall")

        request_point.assert_called_once()
        self.assertIs(request_point.call_args.kwargs["callback"], callback)
        self.assertFalse(request_point.call_args.kwargs["task_ui"])

    def test_native_plan_wall_chains_points_without_draft_task_ui(self):
        from bimplan.runtime.session_state import PlanCreationPreviewState
        from bimplan.tools import wall_create

        state = PlanCreationPreviewState(
            wall_params={"width": 200.0, "height": 3000.0, "align": "Center", "offset": 0.0}
        )
        selected = []
        projected = []
        deferred = []

        def project_once(point):
            projected.append(FreeCAD.Vector(point))
            return FreeCAD.Vector(point)

        session = SimpleNamespace(
            creation_preview_state=state,
            viewport=SimpleNamespace(project_plan_point=project_once),
            contextual_rendering=SimpleNamespace(clear_preview=lambda source: None),
            selection=SimpleNamespace(
                sync=SimpleNamespace(set_gui_selection=lambda objects: selected.extend(objects))
            ),
            lifecycle_state=SimpleNamespace(tearing_down=False),
            current_tool="Wall",
            view=object(),
        )
        session.wall_create = wall_create.PlanWallCreateAPI(session)
        created_walls = [object(), object()]

        snapper = getattr(FreeCADGui, "Snapper", SimpleNamespace())
        with patch.object(FreeCADGui, "Snapper", snapper, create=True), patch.object(
            snapper, "getPoint", create=True
        ) as get_point, patch.object(
            FreeCADGui, "invokeLater", side_effect=lambda callback: deferred.append(callback)
        ), patch.object(wall_create, "_create_wall_segment", side_effect=created_walls) as create_segment:
            wall_create.handle_wall_point(session, FreeCAD.Vector(100, 200, 0))
            create_segment.assert_not_called()
            self.assertEqual(len(deferred), 1)
            self.assertEqual(get_point.call_count, 0)
            deferred.pop()()
            self.assertEqual(get_point.call_count, 1)
            wall_create.handle_wall_point(session, FreeCAD.Vector(900, 350, 0))
            self.assertEqual(len(deferred), 1)
            deferred.pop()()
            self.assertEqual(get_point.call_count, 2)
            wall_create.handle_wall_point(session, FreeCAD.Vector(900, 900, 0))

        self.assertEqual(create_segment.call_count, 2)
        start, end = create_segment.call_args_list[0].args[1:]
        self.assertTrue(start.isEqual(FreeCAD.Vector(100, 200, 0), 1e-7))
        self.assertTrue(end.isEqual(FreeCAD.Vector(900, 200, 0), 1e-7))
        second_start, second_end = create_segment.call_args_list[1].args[1:]
        self.assertTrue(second_start.isEqual(end, 1e-7))
        self.assertTrue(second_end.isEqual(FreeCAD.Vector(900, 900, 0), 1e-7))
        self.assertIs(state.wall_previous, created_walls[-1])
        self.assertTrue(state.wall_start.isEqual(second_end, 1e-7))
        self.assertEqual(selected, [])
        self.assertEqual(len(projected), 3)
        self.assertEqual(len(deferred), 1)
        self.assertEqual(get_point.call_count, 2)
        self.assertFalse(get_point.call_args.kwargs["task_ui"])

    def test_created_wall_is_added_without_rebuilding_existing_representations(self):
        """Wall chaining incrementally installs the new semantic source."""

        from bimplan.runtime.session import PlanEditSession

        existing = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            renderer = session.contextual_rendering.renderer
            existing_representation = renderer._representations[existing]
            with patch.object(
                session.contextual_rendering,
                "refresh_all",
                wraps=session.contextual_rendering.refresh_all,
            ) as refresh_all:
                created = Arch.makeWall(
                    length=1800, width=200, height=2500, align="Center"
                )
                session.visibility.register_plan_object(created)
                self.document.recompute()
                self.pump_gui_events(4)

            refresh_all.assert_not_called()
            self.assertIs(existing_representation, renderer._representations[existing])
            self.assertIn(created, renderer._representations)
        finally:
            session.shutdown(close_dialog=True)

    def test_rectangular_wall_preview_is_one_semantic_representation(self):
        from bimplan.tools.wall_create import _wall_preview_representation

        renderer = SimpleNamespace()
        session = self._wall_preview_session(renderer)
        corners = [
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(1000, 0, 0),
            FreeCAD.Vector(1000, 800, 0),
            FreeCAD.Vector(0, 800, 0),
        ]
        source = object()
        representation = _wall_preview_representation(
            session,
            source,
            tuple(zip(corners, corners[1:] + corners[:1])),
            200,
        )

        self.assertIs(source, representation.source)
        self.assertEqual(4, len(representation.cut_geometry))
        self.assertEqual(4, len(representation.projected_geometry))

    def test_window_creation_preview_coordinates_opening_and_host_cut(self):
        from bimcommands import BimWall
        from bimplan.tools.window_create import (
            _build_window_creation_preview_state,
            _get_window_preview_points,
        )

        wall = BimWall.create_baseless_wall_from_endpoints(
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(2000, 0, 0),
            width=200,
            height=2500,
            auto_group=False,
        )
        self.document.recompute()
        request = RepresentationRequest("Plan", cut_offset=1000, target_offset=0)
        session = SimpleNamespace(
            representation_request=SimpleNamespace(request=request),
        )
        points = _get_window_preview_points(
            session,
            FreeCAD.Vector(1000, 0, 0),
            wall=wall,
        )
        source = object()
        state = _build_window_creation_preview_state(session, wall, points, source)

        self.assertIs(wall, state.primary_source)
        opening_entry = state.entry_for(source)
        host_entry = state.entry_for(wall)
        self.assertIsNotNone(opening_entry)
        self.assertIsNotNone(host_entry)
        self.assertFalse(opening_entry.affects_spatial_boundary)
        self.assertTrue(host_entry.replace_committed)
        self.assertFalse(host_entry.affects_spatial_boundary)
        self.assertEqual(1, len(opening_entry.representation.cut_geometry))
        self.assertTrue(host_entry.representation.cut_geometry)
        self.assertLess(
            sum(face.Area for face in host_entry.representation.cut_geometry),
            2000 * 200,
        )

    def test_window_creation_preview_realizes_and_clears_as_one_coin_state(self):
        from bimcommands import BimWall
        from bimplan.tools.window_create import (
            _build_window_creation_preview_state,
            _get_window_preview_points,
        )

        wall = BimWall.create_baseless_wall_from_endpoints(
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(2000, 0, 0),
            width=200,
            height=2500,
            auto_group=False,
        )
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            points = _get_window_preview_points(
                session,
                FreeCAD.Vector(1000, 0, 0),
                wall=wall,
            )
            source = object()
            state = _build_window_creation_preview_state(session, wall, points, source)
            self.assertTrue(session.contextual_rendering.set_preview_state(state))
            session.viewport.flush_scene_graph_mutations()

            renderer = session.contextual_rendering.renderer
            self.assertIn(source, renderer._preview_nodes)
            self.assertIn(wall, renderer._preview_nodes)
            self.assertIn(wall, renderer._preview_replaced_sources)
            self.assertIn(wall, renderer._preview_groups)

            self.assertTrue(session.contextual_rendering.clear_preview(wall))
            session.viewport.flush_scene_graph_mutations()
            self.assertFalse(renderer._preview_nodes)
            self.assertFalse(renderer._preview_replaced_sources)
        finally:
            session.shutdown(close_dialog=False)

    def test_plan_window_creation_uses_atomic_opening_construction(self):
        from bimcommands import BimWall
        from bimplan.tools.window_create import create_hosted_opening

        wall = BimWall.create_baseless_wall_from_endpoints(
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(2400, 0, 0),
            width=200,
            height=2500,
            auto_group=False,
        )
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            window = create_hosted_opening(session, wall, FreeCAD.Vector(1200, 0, 0))
            self.assertIn(wall, tuple(window.Hosts))
            self.assertEqual("Window", window.IfcType)
            self.assertAlmostEqual(900.0, window.Width.Value)
            self.assertAlmostEqual(1200.0, window.Height.Value)
            self.assertFalse(window.Shape.isNull())

            window_name = window.Name
            self.document.undo()
            self.document.recompute()
            self.assertIsNone(self.document.getObject(window_name))
            self.assertIsNotNone(self.document.getObject(wall.Name))
        finally:
            session.shutdown(close_dialog=False)

    def test_plan_door_creation_uses_atomic_preset_construction(self):
        from bimcommands import BimWall
        from bimplan.tools.window_create import create_hosted_opening

        wall = BimWall.create_baseless_wall_from_endpoints(
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(2400, 0, 0),
            width=200,
            height=2500,
            auto_group=False,
        )
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            session.creation_preview_state.opening_kind = "Door"
            door = create_hosted_opening(session, wall, FreeCAD.Vector(1200, 0, 0))
            self.assertIn(wall, tuple(door.Hosts))
            self.assertEqual("Door", door.IfcType)
            self.assertAlmostEqual(900.0, door.Width.Value)
            self.assertAlmostEqual(2100.0, door.Height.Value)
            self.assertFalse(door.Shape.isNull())

            door_name = door.Name
            self.document.undo()
            self.document.recompute()
            self.assertIsNone(self.document.getObject(door_name))
            self.assertIsNotNone(self.document.getObject(wall.Name))
        finally:
            session.shutdown(close_dialog=False)

    def test_space_creation_previews_use_semantic_geometry(self):
        from bimplan.tools.space_interaction import (
            _build_plan_region_preview_representation,
            _build_space_separator_preview_representation,
        )

        session = SimpleNamespace(
            representation_request=SimpleNamespace(request=RepresentationRequest("Plan")),
        )
        points = (
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(1000, 0, 0),
            FreeCAD.Vector(500, 800, 0),
        )
        region_source = object()
        region = _build_plan_region_preview_representation(
            session,
            region_source,
            (
                (points[0], points[1], False),
                (points[1], points[2], False),
                (points[2], points[0], True),
            ),
        )
        self.assertIs(region_source, region.source)
        self.assertEqual(3, len(region.projected_geometry))
        self.assertEqual(1, len(region.cut_geometry))
        self.assertEqual(
            ["ProposedRegionEdge", "ProposedRegionEdge", "ProposedRegionClosure"],
            [
                mapping.role
                for mapping in region.source_mappings
                if mapping.geometry in region.projected_geometry
            ],
        )

        separator_source = object()
        separator = _build_space_separator_preview_representation(
            session,
            separator_source,
            points[0],
            points[1],
        )
        self.assertIs(separator_source, separator.source)
        self.assertEqual(1, len(separator.projected_geometry))
        self.assertEqual("ProposedSpaceSeparator", separator.source_mappings[0].role)

    def test_space_creation_preview_realizes_and_clears_in_coin(self):
        from bimplan.tools.space_interaction import (
            _build_plan_region_preview_representation,
        )

        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            source = object()
            points = (
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(1000, 0, 0),
                FreeCAD.Vector(500, 800, 0),
            )
            representation = _build_plan_region_preview_representation(
                session,
                source,
                (
                    (points[0], points[1], False),
                    (points[1], points[2], False),
                    (points[2], points[0], True),
                ),
            )
            self.assertTrue(
                session.contextual_rendering.set_preview_state(
                    preview_state_from_representation(representation)
                )
            )
            session.viewport.flush_scene_graph_mutations()
            renderer = session.contextual_rendering.renderer
            self.assertIn(source, renderer._preview_nodes)

            self.assertTrue(session.contextual_rendering.clear_preview(source))
            session.viewport.flush_scene_graph_mutations()
            self.assertNotIn(source, renderer._preview_nodes)
        finally:
            session.shutdown(close_dialog=False)

    def test_space_candidate_preview_keeps_identity_across_hover_updates(self):
        import ArchRepresentation
        from bimplan.overlays import spaces as overlay_spaces
        from bimplan.tools import space_regions

        self.assertIs(
            overlay_spaces._space_candidate_preview_style({"claimed": True}),
            ArchRepresentation.BIMPreviewStyle.MUTED,
        )
        self.assertIs(
            overlay_spaces._space_candidate_preview_style({"valid": False}, hovered=True),
            ArchRepresentation.BIMPreviewStyle.INVALID,
        )

        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            face_a = Part.Face(
                Part.makePolygon(
                    [
                        FreeCAD.Vector(0, 0, 0),
                        FreeCAD.Vector(800, 0, 0),
                        FreeCAD.Vector(800, 600, 0),
                        FreeCAD.Vector(0, 600, 0),
                        FreeCAD.Vector(0, 0, 0),
                    ]
                )
            )
            face_b = face_a.copy()
            face_b.translate(FreeCAD.Vector(1000, 0, 0))
            candidate_a = {"index": 1, "face": face_a}
            candidate_b = {"index": 2, "face": face_b}
            session.current_tool = "Pick Space Region"
            session.space_region_pick_state.candidates = [candidate_a, candidate_b]

            captured = []
            original = session.contextual_rendering.set_preview_state

            def capture(state, valid=True):
                captured.append(state)
                return original(state, valid=valid)

            with patch.object(session.contextual_rendering, "set_preview_state", capture):
                overlay_spaces.sync_space_region_pick_overlays(session)
                initial_sources = dict(session.space_region_pick_state.preview_sources)
                session.space_region_pick_state.hovered_candidate = candidate_b
                overlay_spaces.sync_space_region_pick_overlays(session)

            self.assertEqual(initial_sources, session.space_region_pick_state.preview_sources)
            self.assertEqual(2, len(captured[-1].entries))
            self.assertIs(
                captured[-1].entry_for(initial_sources[1]).style,
                ArchRepresentation.BIMPreviewStyle.AVAILABLE,
            )
            self.assertIs(
                captured[-1].entry_for(initial_sources[2]).style,
                ArchRepresentation.BIMPreviewStyle.EMPHASIZED,
            )
            session.viewport.flush_scene_graph_mutations()
            renderer = session.contextual_rendering.renderer
            self.assertEqual(set(initial_sources.values()), set(renderer._preview_nodes))

            preview_key = session.space_region_pick_state.preview_key
            space_regions.reset_space_region_pick_state(session)
            session.viewport.flush_scene_graph_mutations()
            self.assertFalse(renderer._preview_nodes)
            self.assertIsNone(session.space_region_pick_state.preview_key)
            self.assertIsNotNone(preview_key)
        finally:
            session.shutdown(close_dialog=False)

    def test_storey_entry_helper_selects_source_and_runs_shared_command(self):
        from bimcommands.BimPlanEdit import start_plan_edit_for

        storey, _contained = self._make_storey("Plan Storey", 0)
        with patch.object(FreeCADGui, "runCommand") as run_command:
            start_plan_edit_for(storey)

        self.assertEqual([storey], FreeCADGui.Selection.getSelection())
        run_command.assert_called_once_with("BIM_PlanEdit")

    def test_rectangular_wall_run_uses_command_owned_creation_api(self):
        from bimcommands import BimWall

        points = [
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Vector(1000, 0, 0),
            FreeCAD.Vector(1000, 800, 0),
            FreeCAD.Vector(0, 800, 0),
        ]
        walls = BimWall.create_wall_run_from_points(
            points,
            width=200,
            height=2500,
            closed=True,
            auto_group=False,
        )
        self.assertEqual(4, len(walls))
        self.assertTrue(all(wall.Base is None for wall in walls))

    def test_provider_rehost_api_preserves_pose(self):
        from bimplan.tools import hosted_openings

        host = self.document.addObject("Part::Feature", "Host")
        opening = self.document.addObject("Part::FeaturePython", "Opening")
        opening.addProperty("App::PropertyLinkList", "Hosts")
        opening.Placement.Base = FreeCAD.Vector(120, 80, 40)
        before = FreeCAD.Placement(opening.Placement)

        self.assertTrue(hosted_openings.rehost_object(opening, host, preserve_world_position=True))
        self.assertEqual([host], list(opening.Hosts))
        self.assertTrue(opening.Placement.Base.isEqual(before.Base, 1e-7))

    def test_provider_registry_preserves_order_and_replaces_by_identity(self):
        registry = PlanEditRegistry()
        first = _TestProvider("first")
        second = _TestProvider("second")
        replacement = _TestProvider("first")

        registry.register_provider(first)
        registry.register_provider(second)
        registry.register_provider(replacement)

        self.assertEqual(("first", "second"), registry.provider_ids())
        self.assertEqual((replacement, second), registry.iter_providers())
        self.assertIs(replacement, registry.get_provider("first"))
        self.assertIs(second, registry.unregister_provider(second))
        self.assertEqual(("first",), registry.provider_ids())

    def test_provider_registry_rejects_missing_identity(self):
        registry = PlanEditRegistry()

        with self.assertRaises(ValueError):
            registry.register_provider(_TestProvider(""))

    def _make_storey(self, label, elevation):
        storey = Arch.makeBuildingPart(name=label)
        storey.Label = label
        storey.IfcType = "Building Storey"
        storey.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, elevation), FreeCAD.Rotation())
        contained = self.document.addObject("App::DocumentObjectGroup", "ContainedObject")
        storey.addObject(contained)
        self.document.recompute()
        return storey, contained

    def test_storey_collection_uses_arch_semantics_and_keeps_legacy_floors(self):
        low_storey, _ = self._make_storey("Low Storey", 0)
        high_storey, _ = self._make_storey("High Storey", 3000)
        high_storey.LevelOffset = 125
        legacy_floor = self.document.addObject("App::FeaturePython", "LegacyStorey")
        legacy_floor.addProperty("App::PropertyPlacement", "Placement", "Base")
        legacy_floor.Proxy = type("LegacyFloorProxy", (), {"Type": "Floor"})()
        legacy_floor.Placement = FreeCAD.Placement(
            FreeCAD.Vector(0, 0, 1500), FreeCAD.Rotation()
        )
        session = SimpleNamespace(doc=self.document, storeys=[])

        storeys = collect_storeys(session)

        self.assertEqual(storeys, [low_storey, legacy_floor, high_storey])
        self.assertEqual(get_storey_elevation(high_storey), 3000)
        FreeCADGui.Selection.clearSelection()
        try:
            FreeCADGui.Selection.addSelection(high_storey)
            self.assertIs(find_initial_storey(SimpleNamespace(storeys=storeys)), high_storey)
        finally:
            FreeCADGui.Selection.clearSelection()

    def test_session_visibility_and_camera_are_reversible(self):
        lower_storey, lower_wall = self._make_storey("Lower Storey", 0)
        upper_storey, upper_wall = self._make_storey("Upper Storey", 3000)

        gui_document = FreeCADGui.ActiveDocument
        view = gui_document.ActiveView
        original_camera = view.getCamera()
        original_camera_type = view.getCameraType()
        original_visibility = {
            obj.Name: obj.ViewObject.Visibility
            for obj in (lower_storey, lower_wall, upper_storey, upper_wall)
        }

        session = PlanEditSession()
        try:
            self.assertTrue(session.enter())
            self.assertEqual(session.active_storey.Name, lower_storey.Name)
            self.assertEqual(view.getCameraType(), "Orthographic")
            self.assertEqual(view.getViewVisibility(lower_storey), "Visible")
            self.assertEqual(view.getViewVisibility(lower_wall), "Visible")
            self.assertEqual(view.getViewVisibility(upper_storey), "Hidden")
            self.assertEqual(view.getViewVisibility(upper_wall), "Hidden")

            session.storey.set_active_storey(upper_storey)
            self.assertEqual(view.getViewVisibility(lower_storey), "Hidden")
            self.assertEqual(view.getViewVisibility(lower_wall), "Hidden")
            self.assertEqual(view.getViewVisibility(upper_storey), "Visible")
            self.assertEqual(view.getViewVisibility(upper_wall), "Visible")
            self.assertEqual(
                {
                    obj.Name: obj.ViewObject.Visibility
                    for obj in (lower_storey, lower_wall, upper_storey, upper_wall)
                },
                original_visibility,
            )
        finally:
            session.finish(close_dialog=False)

        self.assertEqual(view.getCameraType(), original_camera_type)
        self.assertEqual(view.getCamera(), original_camera)
        for obj in (lower_storey, lower_wall, upper_storey, upper_wall):
            self.assertEqual(view.getViewVisibility(obj), "Inherit")
            self.assertEqual(obj.ViewObject.Visibility, original_visibility[obj.Name])

    def test_task_panel_uses_compact_empty_context_state(self):
        FreeCADGui.Selection.clearSelection()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            panel = session.task_panel
            self.assertIsNotNone(panel)
            self.assertEqual("PLAN", panel.header_mode_label.text())
            self.assertIn("Select an element", panel.status.text())
            self.assertTrue(panel.modify_group.isHidden())
            self.assertTrue(panel.view_settings_content.isHidden())
            self.assertLessEqual(panel.form.minimumSizeHint().width(), 300)

            panel.view_settings_toggle.setChecked(True)
            self.assertFalse(panel.view_settings_content.isHidden())
            self.assertLessEqual(panel.form.minimumSizeHint().width(), 300)
            self.assertTrue(panel.grid_snap_checkbox.isChecked())
            panel.view_settings_toggle.setChecked(False)
            self.pump_gui_events(2)
            self.assertTrue(panel.form.updatesEnabled())
        finally:
            session.shutdown(close_dialog=True)

    def test_task_panel_does_not_expose_plan_exit_control(self):
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            self.assertIsNotNone(session.task_panel)
            self.assertFalse(hasattr(session.task_panel, "exit_button"))
        finally:
            session.shutdown(close_dialog=True)

    def test_task_panel_wall_type_controls_assign_duplicate_and_reset(self):
        wall_type = Arch.makeWallType("Exterior 300")
        wall_type.Function = "Exterior"
        wall_type.Width = 300
        wall_type.PlanHatch = "Diagonal"
        wall = Arch.makeWall(length=2000, wall_type=wall_type)
        wall.Width = 350
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)

        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            panel = session.task_panel
            self.pump_gui_events(10)
            panel.refresh_from_session()
            self.assertIs(panel._wall_type_items[panel.wall_type_combo.currentIndex()], wall_type)
            self.assertIn("Exterior", panel.wall_type_summary.text())
            self.assertIn("Overrides: Width", panel.wall_type_summary.text())
            self.assertTrue(panel.wall_type_reset_button.isEnabled())

            panel.wall_type_reset_button.click()
            self.pump_gui_events(5)
            self.assertEqual([], list(wall.TypeOverrides))
            self.assertAlmostEqual(300.0, ArchWall.get_resolved_wall_defaults(wall).width)

            self.assertTrue(panel.wall_type_duplicate_button.isEnabled())
            panel.wall_type_duplicate_button.click()
            self.pump_gui_events(5)
            duplicated = wall.WallType
            self.assertIsNot(duplicated, wall_type)
            self.assertEqual("Exterior", str(duplicated.Function))
            self.assertEqual("Diagonal", str(duplicated.PlanHatch))
            self.assertAlmostEqual(300.0, duplicated.Width.Value)

            panel.wall_type_settings_toggle.setChecked(True)
            panel.wall_type_label_edit.setText("Exterior 420")
            panel.wall_type_width_edit.setText("420 mm")
            panel.wall_type_height_edit.setText("3100 mm")
            panel.wall_type_hatch_combo.setCurrentIndex(
                panel.wall_type_hatch_combo.findText("Cross")
            )
            panel.wall_type_hatch_spacing_edit.setText("80 mm")
            panel.wall_type_hatch_angle_edit.setText("30 deg")
            panel.wall_type_apply_button.click()
            self.pump_gui_events(5)
            self.assertEqual("Exterior 420", duplicated.Label)
            self.assertEqual("Cross", str(duplicated.PlanHatch))
            self.assertAlmostEqual(420.0, duplicated.Width.Value)
            self.assertAlmostEqual(3100.0, duplicated.DefaultHeight.Value)
            self.assertAlmostEqual(80.0, duplicated.PlanHatchSpacing.Value)
            self.assertAlmostEqual(30.0, duplicated.PlanHatchAngle.Value)
            self.assertAlmostEqual(420.0, ArchWall.get_resolved_wall_defaults(wall).width)
            self.assertIs(
                panel._wall_type_items[panel.wall_type_combo.currentIndex()], duplicated
            )

            panel.wall_type_combo.setCurrentIndex(0)
            self.pump_gui_events(5)
            self.assertIsNone(wall.WallType)
        finally:
            session.shutdown(close_dialog=True)
            FreeCADGui.Selection.clearSelection()

    def test_plan_select_drag_and_ctrl_click_share_semantic_selection(self):
        wall_a = Arch.makeWall(
            length=1500,
            width=200,
            height=2500,
            align="Center",
        )
        wall_a.Placement.Base = FreeCAD.Vector(-2000, 0, 0)
        wall_b = Arch.makeWall(
            length=1500,
            width=200,
            height=2500,
            align="Center",
        )
        wall_b.Placement.Base = FreeCAD.Vector(1000, 0, 0)
        self.document.recompute()
        view = FreeCADGui.activeDocument().activeView()
        native_selection_enabled = view.isSelectionEnabled()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            self.assertFalse(view.isSelectionEnabled())
            session.view.fitAll()
            self.pump_gui_events(10)
            bounds = []
            for wall in (wall_a, wall_b):
                projected = [
                    session.view.getPointOnScreen(point)
                    for polyline in session.overlays.geometry.get_wall_overlay_polylines(wall)
                    for point in polyline
                ]
                bounds.append(
                    (
                        min(point[0] for point in projected),
                        min(point[1] for point in projected),
                        max(point[0] for point in projected),
                        max(point[1] for point in projected),
                    )
                )
            self.assertTrue(all(item is not None for item in bounds))
            start = (
                min(item[0] for item in bounds) - 10,
                min(item[1] for item in bounds) - 10,
            )
            end = (
                max(item[2] for item in bounds) + 10,
                max(item[3] for item in bounds) + 10,
            )
            event_manager = session.viewer.getSoEventManager()

            def send_button(point, state, ctrl=False):
                event = coin.SoMouseButtonEvent()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event.setButton(coin.SoMouseButtonEvent.BUTTON1)
                event.setState(state)
                event.setCtrlDown(bool(ctrl))
                event_manager.processEvent(event)

            def send_move(point):
                event = coin.SoLocation2Event()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event_manager.processEvent(event)

            send_button(start, coin.SoButtonEvent.DOWN)
            send_move(end)
            send_button(end, coin.SoButtonEvent.UP)
            self.pump_gui_events(10)
            self.assertEqual({wall_a, wall_b}, set(FreeCADGui.Selection.getSelection()))

            wall_a_center = session.view.getPointOnScreen(wall_a.Shape.CenterOfMass)
            with patch.object(session.picking, "pick_edit_node", return_value=None), patch.object(
                session.picking, "pick", return_value=("wall", wall_a)
            ):
                send_button(wall_a_center, coin.SoButtonEvent.DOWN, ctrl=True)
                send_button(wall_a_center, coin.SoButtonEvent.UP, ctrl=True)
                self.assertEqual([wall_b], FreeCADGui.Selection.getSelection())
                self.pump_gui_events(10)
            self.assertEqual([wall_b], FreeCADGui.Selection.getSelection())
        finally:
            session.shutdown(close_dialog=True)
            self.assertEqual(native_selection_enabled, view.isSelectionEnabled())
            FreeCADGui.Selection.clearSelection()

    def test_shutdown_discards_pending_view_updates(self):
        session = PlanEditSession()
        self.assertTrue(session.enter())
        callbacks = []
        self.assertTrue(
            session.viewport.queue_scene_graph_mutation(
                "test-pending-mutation", lambda: callbacks.append(True)
            )
        )
        session.shutdown(close_dialog=False)

        self.assertFalse(callbacks)
        self.assertTrue(session.viewport_state.scene_graph_mutations)
        session.viewport.flush_scene_graph_mutations()
        self.assertFalse(session.viewport_state.scene_graph_mutations)

    def test_contextual_renderer_mutations_are_deferred_and_coalesced(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            renderer = session.contextual_rendering.renderer
            original_node = renderer._object_nodes[wall]
            original_geometry_nodes = tuple(
                binding.group for binding in renderer._geometry_bindings[wall]
            )

            session.overlays.geometry.invalidate_plan_overlay_geometry_cache(
                wall, kinds=("representation",)
            )
            session.contextual_rendering.refresh_object(wall)
            session.contextual_rendering.refresh_object(wall)

            key = ("contextual-renderer", ("representation", wall))
            self.assertIn(key, session.viewport_state.scene_graph_mutations)
            self.assertIs(original_node, renderer._object_nodes[wall])
            session.viewport.flush_scene_graph_mutations()
            self.assertIs(original_node, renderer._object_nodes[wall])
            self.assertEqual(
                original_geometry_nodes,
                tuple(binding.group for binding in renderer._geometry_bindings[wall]),
            )

            stale_callbacks = []
            self.assertTrue(
                session.contextual_rendering._queue_renderer_mutation(
                    "stale-renderer-work", lambda _renderer: stale_callbacks.append(True)
                )
            )
            session.contextual_rendering.close()
            self.assertIsNone(session.contextual_rendering.renderer)
            self.assertIsNotNone(renderer.root)
            session.viewport.flush_scene_graph_mutations()
            self.assertFalse(stale_callbacks)
            self.assertIsNone(renderer.root)
        finally:
            session.shutdown(close_dialog=False)

    def test_contextual_edit_refreshes_are_deferred_coalesced_and_guarded(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        callbacks = []
        try:
            with patch.object(
                FreeCADGui, "invokeLater", side_effect=callbacks.append
            ), patch.object(
                session.contextual_rendering, "_refresh_source"
            ) as refresh_source:
                session.contextual_rendering._queue_edit_refresh((wall,), {wall}, set())
                session.contextual_rendering._queue_edit_refresh((wall,), set(), set())
                self.assertEqual(1, len(callbacks))
                callbacks.pop()()
                refresh_source.assert_called_once_with(wall, reuse_edit_handles=None)
                session.contextual_rendering._queue_edit_refresh((wall,), {wall}, set())
                stale_callback = callbacks.pop()
                session.contextual_rendering.close()
                stale_callback()
                self.assertEqual(1, refresh_source.call_count)
        finally:
            session.shutdown(close_dialog=False)

    def test_reapplying_same_plan_context_preserves_rendered_nodes(self):
        """An identical saved-plan request must not rebuild contextual geometry."""

        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            renderer = session.contextual_rendering.renderer
            original_node = renderer._object_nodes[wall]

            session.representation_request.set_source(
                session.representation_request.source,
                fit=False,
            )
            session.viewport.flush_scene_graph_mutations()

            self.assertIs(original_node, renderer._object_nodes[wall])
        finally:
            session.shutdown(close_dialog=False)

    def test_plan_representation_geometry_survives_session_switch(self):
        """Returning from Model reuses Plan geometry and rehides native shapes."""

        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        original_visibility = view.getViewVisibility(wall)
        first_session = PlanEditSession()
        self.assertTrue(first_session.enter())
        self.assertEqual("Hidden", view.getViewVisibility(wall))
        first_representation = first_session.contextual_rendering.renderer._representations[wall]
        first_node = first_session.contextual_rendering.renderer._object_nodes[wall]
        first_session.shutdown(close_dialog=False)
        first_session.viewport.flush_scene_graph_mutations()
        self.assertEqual(original_visibility, view.getViewVisibility(wall))

        second_session = PlanEditSession()
        self.assertTrue(second_session.enter())
        try:
            self.assertEqual("Hidden", view.getViewVisibility(wall))
            second_representation = second_session.contextual_rendering.renderer._representations[
                wall
            ]
            self.assertIs(first_representation, second_representation)
            self.assertIs(
                first_node,
                second_session.contextual_rendering.renderer._object_nodes[wall],
            )
        finally:
            second_session.shutdown(close_dialog=False)

        wall.Width = wall.Width.Value + 50
        self.document.recompute()
        third_session = PlanEditSession()
        self.assertTrue(third_session.enter())
        try:
            changed_representation = third_session.contextual_rendering.renderer._representations[
                wall
            ]
            self.assertIsNot(second_representation, changed_representation)
        finally:
            third_session.shutdown(close_dialog=False)

    def test_model_transition_suspends_plan_geometry_before_returning(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        original_visibility = view.getViewVisibility(wall)
        session = activate_representation_request(
            RepresentationRequest(purpose=RepresentationPurpose.PLAN)
        )
        self.assertIsNotNone(session)
        renderer = session.contextual_rendering.renderer
        self.assertEqual(coin.SO_SWITCH_ALL, renderer.root.whichChild.getValue())

        activate_representation_request(
            RepresentationRequest(purpose=RepresentationPurpose.MODEL)
        )

        self.assertEqual(coin.SO_SWITCH_NONE, renderer.root.whichChild.getValue())
        self.assertEqual(original_visibility, view.getViewVisibility(wall))

    def test_document_close_discards_pending_semantic_preview(self):
        original_document = self.document
        preview_document = FreeCAD.newDocument("PlanEditPreviewTeardown")
        preview_document_name = preview_document.Name
        FreeCAD.setActiveDocument(preview_document_name)
        FreeCADGui.activeDocument().activeView()
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        preview_document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        renderer = session.contextual_rendering.renderer
        try:
            session.selection.state.set_selected_plan_target("wall", wall)
            session.contextual_rendering.refresh_object(wall)
            session.viewport.flush_scene_graph_mutations()
            handle = next(
                handle
                for handle in session.contextual_rendering.edit_handles_for(wall)
                if handle.role == "WallWidth"
            )
            self.assertTrue(session.contextual_editing.begin(handle))
            preview = session.contextual_editing.preview(
                FreeCAD.Vector(handle.point) + FreeCAD.Vector(0, 80, 0)
            )
            self.assertTrue(preview.validation.allowed)
            self.assertTrue(session.viewport_state.scene_graph_mutations)

            FreeCAD.closeDocument(preview_document_name)
            self.pump_gui_events()

            self.assertTrue(session.lifecycle_state.tearing_down)
            self.assertIsNone(session.contextual_rendering.renderer)
            self.assertIsNone(renderer.root)
            self.assertFalse(renderer._preview_nodes)
            self.assertFalse(session.viewport_state.scene_graph_mutations)
        finally:
            if preview_document_name in FreeCAD.listDocuments():
                FreeCAD.closeDocument(preview_document_name)
            FreeCAD.setActiveDocument(original_document.Name)

    def test_repeated_sessions_clear_preview_nodes_from_retained_layer(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()

        for step in range(3):
            session = PlanEditSession()
            self.assertTrue(session.enter())
            renderer = session.contextual_rendering.renderer
            view = session.view
            try:
                session.selection.state.set_selected_plan_target("wall", wall)
                session.contextual_rendering.refresh_object(wall)
                session.viewport.flush_scene_graph_mutations()
                handle = next(
                    handle
                    for handle in session.contextual_rendering.edit_handles_for(wall)
                    if handle.role == "WallWidth"
                )
                self.assertTrue(session.contextual_editing.begin(handle))
                preview = session.contextual_editing.preview(
                    FreeCAD.Vector(handle.point) + FreeCAD.Vector(0, 25 * (step + 1), 0)
                )
                self.assertTrue(preview.validation.allowed)
            finally:
                session.shutdown(close_dialog=False)
                session.viewport.flush_scene_graph_mutations()

            self.assertIsNotNone(renderer.root)
            self.assertEqual(coin.SO_SWITCH_NONE, renderer.root.whichChild.getValue())
            self.assertFalse(renderer._preview_nodes)
            self.assertFalse(session.viewport_state.scene_graph_mutations)
            self.assertEqual("Inherit", view.getViewVisibility(wall))

    def test_contextual_interaction_renderer_preserves_source_visibility(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        representation = wall.Proxy.getRepresentation(
            wall,
            RepresentationRequest(purpose="Plan", cut_offset=1000, target_offset=0),
        )
        renderer = ContextualInteractionRenderer(view)
        try:
            renderer.set_representation(representation)
            self.assertEqual("Inherit", view.getViewVisibility(wall))
            self.assertTrue(renderer._object_nodes[wall].getNumChildren())
            self.assertIsNone(renderer.pick_mapping((0, 0), lambda point: point))
            ray = ray_from_view(view, view.getPointOnScreen(wall.Shape.BoundBox.Center))
            self.assertAlmostEqual(1.0, ray.direction.Length)

            renderer.set_visible_handle_sources((wall,))
            self.assertEqual("Inherit", view.getViewVisibility(wall))
            renderer.remove_representation(wall)
            self.assertEqual("Inherit", view.getViewVisibility(wall))
        finally:
            renderer.close()

        renderer = ContextualRepresentationRenderer(view)
        try:
            renderer.set_representation(representation)
            self.assertEqual("Hidden", view.getViewVisibility(wall))
            view_provider = wall.ViewObject.Proxy
            self.assertEqual(1, view_provider._footprint_refresh_defer_depth)
            with patch.object(
                view_provider,
                "updateFootprint",
                wraps=view_provider.updateFootprint,
            ) as update_footprint:
                self.assertFalse(view_provider.refreshFootprint())
                update_footprint.assert_not_called()
                renderer.remove_representation(wall)
                update_footprint.assert_called_once()
            self.assertEqual(0, view_provider._footprint_refresh_defer_depth)
            self.assertFalse(view_provider._footprint_refresh_dirty)
            self.assertEqual("Inherit", view.getViewVisibility(wall))

            renderer.set_representation(representation)
            self.assertEqual(1, view_provider._footprint_refresh_defer_depth)
            with (
                patch.object(
                    view_provider, "_isFootprintVisibleInAnyView", return_value=True
                ),
                patch.object(
                    view_provider,
                    "updateFootprint",
                    wraps=view_provider.updateFootprint,
                ) as update_footprint,
            ):
                self.assertTrue(view_provider.refreshFootprint())
                update_footprint.assert_called_once()
            self.assertEqual(0, view_provider._footprint_refresh_defer_depth)
            renderer.remove_representation(wall)

            with patch.object(
                view_provider, "_isFootprintVisibleInAnyView", return_value=True
            ):
                renderer.set_representation(representation)
            self.assertNotIn(wall, renderer._deferred_footprint_sources)
            self.assertEqual(0, view_provider._footprint_refresh_defer_depth)
            renderer.remove_representation(wall)
        finally:
            renderer.close()
        self.assertEqual("Inherit", view.getViewVisibility(wall))

    def test_standard_3d_contextual_editing_keeps_model_visible_and_commits(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Left")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        camera_pose = tuple(
            line.strip()
            for line in view.getCamera().splitlines()
            if not line.strip().startswith(("nearDistance", "farDistance"))
        )
        camera_type = view.getCameraType()
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        session = ContextualSession(view)
        try:
            self.pump_gui_events(20)
            renderer = session.renderer
            self.assertIn(wall, renderer.sources)
            self.assertEqual("Inherit", view.getViewVisibility(wall))
            self.assertIsNotNone(renderer._object_nodes[wall])

            capabilities = renderer._representations[wall]
            self.assertFalse(hasattr(capabilities, "cut_geometry"))
            roles = {handle.subelement for handle in capabilities.edit_handles}
            self.assertTrue(
                {
                    "Path.Start",
                    "Path.End",
                    "Path",
                    "Width.PositiveFace",
                    "Offset",
                    "Height",
                }.issubset(roles)
            )

            height_handle = next(
                handle for handle in capabilities.edit_handles if handle.subelement == "Height"
            )
            self.assertTrue(session.begin_handle_edit(height_handle))
            target = BIMEditRay(
                height_handle.point + FreeCAD.Vector(1000, 0, 500),
                FreeCAD.Vector(-1, 0, 0),
            )
            preview = session.preview_pointer(target)
            self.assertTrue(preview.validation.allowed)
            self.assertAlmostEqual(3000.0, preview.value)
            result = session.commit_pointer(target)
            self.assertTrue(result.success)
            self.pump_gui_events(20)

            self.assertAlmostEqual(3000.0, wall.Height.Value)
            self.assertEqual("Inherit", view.getViewVisibility(wall))
            self.assertEqual(camera_type, view.getCameraType())
            current_camera_pose = tuple(
                line.strip()
                for line in view.getCamera().splitlines()
                if not line.strip().startswith(("nearDistance", "farDistance"))
            )
            self.assertEqual(camera_pose, current_camera_pose)
            self.assertIsNone(session.active_edit)
        finally:
            session.close()
            FreeCADGui.Selection.clearSelection()
        self.assertEqual("Inherit", view.getViewVisibility(wall))

    def test_model_context_exposes_provider_actions_for_the_selection(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Left")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        session = ContextualSession(view)
        try:
            self.pump_gui_events(20)
            labels = {action.label for action in session.contextual_actions}
            self.assertIn("Move Wall", labels)
            self.assertIn("Edit Wall Path Endpoint", labels)
            self.assertIn("Edit Wall Height", labels)
            self.assertEqual(1, len(session.inspector_sections))

            height_action = next(
                action
                for action in session.contextual_actions
                if action.handle_subelement == "Height"
            )
            self.assertTrue(session.activate_action(height_action))
            self.assertEqual("Height", session.active_edit.subelement)
            self.assertIsNotNone(session.host._value_input)
        finally:
            session.close()
            FreeCADGui.Selection.clearSelection()

    def test_contextual_opening_creation_has_cross_context_parity(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Left")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        results = {}

        for kind in ("Window", "Door"):
            for purpose in (
                RepresentationPurpose.MODEL,
                RepresentationPurpose.SECTION,
                RepresentationPurpose.ELEVATION,
            ):
                request = RepresentationRequest(purpose=purpose)
                session = ContextualSession(
                    view,
                    request=request,
                    sources=(wall,),
                    providers=architectural_contextual_providers(),
                )
                try:
                    self.pump_gui_events(20)
                    callbacks = []
                    session.host.request_point = (
                        lambda callback, **_kwargs: callbacks.append(callback)
                    )
                    action_key = "create-{}".format(kind.lower())
                    actions_by_key = {
                        item.key: item for item in session.contextual_actions
                    }
                    self.assertIn(
                        action_key,
                        actions_by_key,
                        "{} action missing in {}".format(kind, purpose.value),
                    )
                    action = actions_by_key[action_key]
                    self.assertTrue(session.activate_action(action))
                    self.assertEqual(1, len(callbacks))
                    opening = callbacks[0](FreeCAD.Vector(1500, 0, 0), wall)
                    self.document.recompute()
                    self.assertEqual(kind, opening.IfcType)
                    self.assertIn(wall, tuple(opening.Hosts))
                    self.assertFalse(opening.Shape.isNull())
                    results[(kind, purpose)] = (
                        opening.Width.Value,
                        opening.Height.Value,
                        opening.Placement.Base,
                        opening.Shape.Volume,
                    )
                    opening_name = opening.Name
                finally:
                    session.close()
                self.document.undo()
                self.document.recompute()
                self.assertIsNone(self.document.getObject(opening_name))

        for kind in ("Window", "Door"):
            model = results[(kind, RepresentationPurpose.MODEL)]
            for purpose in (
                RepresentationPurpose.SECTION,
                RepresentationPurpose.ELEVATION,
            ):
                result = results[(kind, purpose)]
                self.assertAlmostEqual(model[0], result[0])
                self.assertAlmostEqual(model[1], result[1])
                self.assertLess(model[2].distanceToPoint(result[2]), 1e-7)
                self.assertAlmostEqual(model[3], result[3], delta=1e-6)

    def test_contextual_wall_creation_follows_context_capability_policy(self):
        view = FreeCADGui.ActiveDocument.ActiveView
        results = []
        for purpose in RepresentationPurpose.MODEL, RepresentationPurpose.PLAN:
            session = ContextualSession(
                view,
                request=RepresentationRequest(purpose=purpose),
                sources=(),
                providers=architectural_contextual_providers(),
            )
            callbacks = []
            try:
                self.pump_gui_events(20)
                session.host.request_point = lambda callback, **_kwargs: callbacks.append(callback)
                action = next(item for item in session.contextual_actions if item.key == "create-wall")
                self.assertTrue(session.activate_action(action))
                callbacks.pop(0)(FreeCAD.Vector(0, 0, 0))
                wall = callbacks.pop(0)(FreeCAD.Vector(2000, 0, 0))
                results.append((wall.Length.Value, wall.Width.Value, wall.Height.Value, wall.Align))
                wall_name = wall.Name
            finally:
                session.close()
            self.document.undo()
            self.document.recompute()
            self.assertIsNone(self.document.getObject(wall_name))
        self.assertEqual(results[0], results[1])
        for purpose in RepresentationPurpose.SECTION, RepresentationPurpose.ELEVATION:
            session = ContextualSession(
                view,
                request=RepresentationRequest(purpose=purpose),
                sources=(),
                providers=architectural_contextual_providers(),
            )
            try:
                self.pump_gui_events(20)
                self.assertNotIn(
                    "create-wall", {item.key for item in session.contextual_actions}
                )
            finally:
                session.close()

    def test_contextual_wall_creation_preview_and_cancel_are_reversible(self):
        view = FreeCADGui.ActiveDocument.ActiveView
        session = ContextualSession(
            view, sources=(), providers=architectural_contextual_providers()
        )
        requests = []
        try:
            self.pump_gui_events(20)
            session.host.request_point = lambda callback, **kwargs: requests.append((callback, kwargs))
            action = next(item for item in session.contextual_actions if item.key == "create-wall")
            self.assertTrue(session.activate_action(action))
            requests.pop(0)[0](FreeCAD.Vector())
            callback, options = requests.pop(0)
            options["move_callback"](FreeCAD.Vector(1200, 0, 0))
            self.assertTrue(session.renderer._preview_nodes)
            self.assertIsNotNone(session.host._value_input)
            callback(None)
            self.assertFalse(session.renderer._preview_nodes)
            self.assertIsNone(session.host._value_input)
        finally:
            session.close()

    def test_standard_3d_ray_constraints_commit_path_move_and_offset(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Left")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        session = ContextualSession(view)
        try:
            self.pump_gui_events(20)

            def edit_handle(subelement, ray_origin, ray_direction):
                handle = next(
                    item
                    for item in session.renderer.edit_handles_for(wall)
                    if item.subelement == subelement
                )
                self.assertTrue(session.begin_handle_edit(handle), subelement)
                ray = BIMEditRay(ray_origin, ray_direction)
                preview = session.preview_pointer(ray)
                self.assertTrue(preview.validation.allowed, preview.validation.reason)
                result = session.commit_pointer(ray)
                self.assertTrue(result.success, result.reason)
                self.pump_gui_events(20)
                return preview

            original = tuple(wall.Proxy.calc_endpoints(wall))
            axis = original[1] - original[0]
            axis.normalize()
            lateral = axis.cross(FreeCAD.Vector(0, 0, 1))
            lateral.normalize()

            start_target = original[0] + axis * 100.0
            edit_handle(
                "Path.Start",
                start_target + lateral * 1000.0,
                -lateral,
            )
            stretched = tuple(wall.Proxy.calc_endpoints(wall))
            self.assertTrue(stretched[0].isEqual(start_target, 1e-6))
            self.assertTrue(stretched[1].isEqual(original[1], 1e-6))

            end_target = stretched[1] + axis * 100.0
            edit_handle(
                "Path.End",
                end_target + lateral * 1000.0,
                -lateral,
            )
            extended = tuple(wall.Proxy.calc_endpoints(wall))
            self.assertTrue(extended[1].isEqual(end_target, 1e-6))

            midpoint = (extended[0] + extended[1]) * 0.5
            move_target = midpoint + lateral * 150.0
            edit_handle(
                "Path",
                move_target + FreeCAD.Vector(0, 0, 1000),
                FreeCAD.Vector(0, 0, -1),
            )
            moved = tuple(wall.Proxy.calc_endpoints(wall))
            move_delta = move_target - midpoint
            self.assertTrue(moved[0].isEqual(extended[0] + move_delta, 1e-6))
            self.assertTrue(moved[1].isEqual(extended[1] + move_delta, 1e-6))

            initial_offset = wall.Offset.Value
            offset_handle = next(
                item
                for item in session.renderer.edit_handles_for(wall)
                if item.subelement == "Offset"
            )
            offset_target = offset_handle.point + offset_handle.direction * 50.0
            edit_handle(
                "Offset",
                offset_target + FreeCAD.Vector(0, 0, 1000),
                FreeCAD.Vector(0, 0, -1),
            )
            self.assertAlmostEqual(initial_offset + 50.0, wall.Offset.Value)
            self.assertEqual("Inherit", view.getViewVisibility(wall))
        finally:
            session.close()
            FreeCADGui.Selection.clearSelection()

    def test_standard_3d_contextual_editing_callbacks_toggle_with_command(self):
        from bimcommands.BimContextualEdit3D import BIM_ContextualEdit3D
        from bimcontextual.session import active_session

        command = BIM_ContextualEdit3D()
        self.assertTrue(command.IsActive())
        command.Activated()
        session = active_session()
        self.assertIsNotNone(session)
        try:
            self.assertEqual(3, len(session.host._drag_callbacks))
            command.Activated()
            self.assertIsNone(active_session())
            self.assertTrue(session._closed)
        finally:
            if active_session() is session:
                session.close()

    def test_section_contextual_edit_uses_section_frame_and_shared_host(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        section = Arch.makeSectionPlane([wall])
        section.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        camera = tuple(
            line.strip()
            for line in view.getCamera().splitlines()
            if not line.strip().startswith(("nearDistance", "farDistance"))
        )
        session = ContextualSession(
            view,
            request=section.Proxy.getRepresentationRequest(section),
            sources=(wall,),
            orient_to_request=True,
        )
        try:
            self.pump_gui_events(20)
            self.assertEqual("Hidden", view.getViewVisibility(section))
            self.assertTrue(section.ViewObject.Visibility)
            self.assertIs(
                RepresentationPurpose.SECTION,
                session.request.purpose,
            )
            height = next(
                item
                for item in session.renderer.edit_handles_for(wall)
                if item.subelement == "Height"
            )
            self.assertTrue(session.begin_handle_edit(height))
            result = session.controller.commit_value(2800.0)
            self.assertTrue(result.success, result.reason)
            self.assertAlmostEqual(2800.0, wall.Height.Value)
            self.assertEqual(3, len(session.host._drag_callbacks))
        finally:
            session.close()
            self.pump_gui_events(10)
        self.assertEqual("Inherit", view.getViewVisibility(section))
        self.assertTrue(section.ViewObject.Visibility)
        restored_camera = tuple(
            line.strip()
            for line in view.getCamera().splitlines()
            if not line.strip().startswith(("nearDistance", "farDistance"))
        )
        self.assertEqual(camera, restored_camera)

    def test_elevation_contextual_edit_uses_shared_host(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        elevation = Arch.makeSectionPlane([wall])
        elevation.Purpose = "Elevation"
        frame = FreeCAD.Placement(
            FreeCAD.Vector(1500, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
        request = RepresentationRequest(
            purpose=RepresentationPurpose.ELEVATION,
            reference_frame=frame,
            projection_range=(0.0, 5000.0),
            source=elevation,
        )
        self.document.recompute()
        session = ContextualSession(
            FreeCADGui.ActiveDocument.ActiveView,
            request=request,
            sources=(wall,),
            orient_to_request=True,
        )
        try:
            self.pump_gui_events(20)
            self.assertEqual(
                "Hidden",
                FreeCADGui.ActiveDocument.ActiveView.getViewVisibility(elevation),
            )
            self.assertTrue(elevation.ViewObject.Visibility)
            self.assertIs(RepresentationPurpose.ELEVATION, session.request.purpose)
            self.assertTrue(session.renderer.replace_source)
            self.assertTrue(session.renderer.render_representation)
            self.assertTrue(
                session.renderer._representations[wall].projected_geometry
            )
            height = next(
                item
                for item in session.renderer.edit_handles_for(wall)
                if item.subelement == "Height"
            )
            self.assertTrue(session.begin_handle_edit(height))
            session.host._value_input[1].setProperty("quantityString", "2.9 m")
            session.host._value_input[1].returnPressed.emit()
            self.assertAlmostEqual(2900.0, wall.Height.Value)
            self.assertIsNone(session.active_edit)
        finally:
            session.close()

    def test_elevation_session_refreshes_persisted_presentation_profile(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        elevation = Arch.makeSectionPlane([wall])
        elevation.Purpose = "Elevation"
        request = elevation.Proxy.getRepresentationRequest(elevation)
        self.document.recompute()
        session = ContextualSession(
            FreeCADGui.ActiveDocument.ActiveView,
            request=request,
            sources=(wall,),
        )
        try:
            self.pump_gui_events(20)
            elevation.ShowSilhouettes = False
            elevation.VisibleLineWidth = 2.0
            elevation.SilhouetteLineWidth = 3.0
            self.document.recompute()
            self.assertTrue(session.refresh_request_from_source(elevation))
            self.pump_gui_events(20)
            self.assertFalse(session.request.presentation_profile["show_silhouettes"])
            self.assertEqual(2.0, session.controller.request.presentation_profile["visible_line_width"])
            self.assertIs(session.request, session.host.request)
        finally:
            session.close()

    def test_section_plane_task_panel_edits_elevation_presentation_profile(self):
        from ArchSectionPlane import SectionPlaneTaskPanel

        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        elevation = Arch.makeSectionPlane([wall])
        elevation.Purpose = "Elevation"
        panel = SectionPlaneTaskPanel()
        panel.obj = elevation
        panel.update()
        try:
            self.assertTrue(panel.presentation_widget.isEnabled())
            self.assertTrue(panel.showSilhouettes.isChecked())
            self.assertEqual(1.0, panel.visibleLineWidth.value())
            self.assertEqual(1.35, panel.silhouetteLineWidth.value())
            panel.showSilhouettes.setChecked(False)
            panel.visibleLineWidth.setValue(2.0)
            panel.silhouetteLineWidth.setValue(3.0)
            self.assertFalse(elevation.ShowSilhouettes)
            self.assertEqual(2.0, elevation.VisibleLineWidth)
            self.assertEqual(3.0, elevation.SilhouetteLineWidth)
        finally:
            panel.reject()

    def test_elevation_projection_failure_preserves_last_valid_view(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        elevation = Arch.makeSectionPlane([wall])
        elevation.Purpose = "Elevation"
        request = RepresentationRequest(
            purpose=RepresentationPurpose.ELEVATION,
            reference_frame=elevation.Placement,
            projection_range=(-5000.0, 0.0),
            source=elevation,
        )
        self.document.recompute()
        session = ContextualSession(
            FreeCADGui.ActiveDocument.ActiveView,
            request=request,
            sources=(wall,),
        )
        try:
            self.pump_gui_events(20)
            previous = session.renderer._representations[wall]
            with patch(
                "ArchSectionProjection.project_elevation_scope",
                side_effect=RuntimeError("synthetic OCC failure"),
            ):
                session._refresh_selection()
            self.assertIs(previous, session.renderer._representations[wall])
            self.assertIn("last valid view", session._last_projection_error)
        finally:
            session.close()
        self.assertEqual(
            "Inherit", FreeCADGui.ActiveDocument.ActiveView.getViewVisibility(elevation)
        )
        self.assertTrue(elevation.ViewObject.Visibility)

    def test_section_plane_exposes_its_contextual_edit_command(self):
        section = Arch.makeSectionPlane(name="ContextualSection")
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        with patch.object(FreeCADGui, "runCommand") as run_command:
            section.ViewObject.Proxy.startContextualEdit("BIM_SectionEdit")

        self.assertEqual([section], FreeCADGui.Selection.getSelection())
        run_command.assert_called_once_with("BIM_SectionEdit")

    def test_standard_3d_pointer_drag_commits_a_semantic_width_edit(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        session = ContextualSession(view)
        try:
            view.viewAxonometric()
            view.fitAll()
            for _ in range(4):
                view.zoomIn()
            self.pump_gui_events(20)
            handle = next(
                handle
                for handle in session.renderer.edit_handles_for(wall)
                if handle.subelement == "Width.PositiveFace"
            )
            start = view.getPointOnScreen(handle.point)
            target = view.getPointOnScreen(handle.point + handle.direction * 50.0)
            picked = session.renderer.pick_edit_handle(start, view.getPointOnScreen)
            self.assertEqual(
                handle.subelement,
                getattr(picked, "subelement", None),
                msg="screen start={!r}, handles={!r}".format(
                    start,
                    tuple(
                        (item.subelement, view.getPointOnScreen(item.point))
                        for item in session.renderer.edit_handles_for(wall)
                    ),
                ),
            )
            target_ray = ray_from_view(view, (round(target[0]), round(target[1])))
            projected_target = handle.constraint.project(target_ray)
            pointer_delta = (projected_target - handle.point).dot(handle.direction)
            self.assertGreater(pointer_delta, 10.0)
            self.assertLess(pointer_delta, 1000.0)
            event_manager = view.getViewer().getSoEventManager()

            def send_button(point, state):
                event = coin.SoMouseButtonEvent()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event.setButton(coin.SoMouseButtonEvent.BUTTON1)
                event.setState(state)
                event_manager.processEvent(event)

            def send_move(point):
                event = coin.SoLocation2Event()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event_manager.processEvent(event)

            send_button(start, coin.SoButtonEvent.DOWN)
            self.pump_gui_events(20)
            self.assertIsNotNone(session.active_edit)
            self.assertEqual(handle.subelement, session.active_edit.subelement)
            send_move(target)
            self.pump_gui_events(20)
            send_button(target, coin.SoButtonEvent.UP)
            self.pump_gui_events(40)

            self.assertAlmostEqual(200.0 + pointer_delta, wall.Width.Value, delta=10.0)
            self.assertIsNone(session.active_edit)
            self.assertEqual("Inherit", view.getViewVisibility(wall))

            height_handle = next(
                handle
                for handle in session.renderer.edit_handles_for(wall)
                if handle.subelement == "Height"
            )
            height_start = view.getPointOnScreen(height_handle.point)
            height_target = view.getPointOnScreen(
                height_handle.point + height_handle.direction * 50.0
            )
            height_before_cancel = wall.Height.Value
            send_button(height_start, coin.SoButtonEvent.DOWN)
            self.pump_gui_events(20)
            self.assertEqual("Height", session.active_edit.subelement)
            send_move(height_target)
            self.pump_gui_events(20)
            escape = coin.SoKeyboardEvent()
            escape.setKey(coin.SoKeyboardEvent.ESCAPE)
            escape.setState(coin.SoKeyboardEvent.DOWN)
            event_manager.processEvent(escape)
            self.pump_gui_events(20)

            self.assertIsNone(session.active_edit)
            self.assertAlmostEqual(height_before_cancel, wall.Height.Value)

            height_handle = next(
                handle
                for handle in session.renderer.edit_handles_for(wall)
                if handle.subelement == "Height"
            )
            send_button(view.getPointOnScreen(height_handle.point), coin.SoButtonEvent.DOWN)
            self.pump_gui_events(20)
            self.assertEqual("Height", session.active_edit.subelement)

            value_field = session.host._value_input[1]
            value_field.setProperty("quantityString", "2.8 m")
            value_field.returnPressed.emit()
            self.pump_gui_events(30)

            self.assertAlmostEqual(2800.0, wall.Height.Value)
            self.assertIsNone(session.active_edit)
        finally:
            session.close()
            FreeCADGui.Selection.clearSelection()

    def test_contextual_edit_consumes_declared_recompute_and_visual_sources(self):
        base = object()
        source = object()
        unrelated = object()
        impact = SimpleNamespace(
            recompute=SimpleNamespace(roots=(base, None)),
            representation_sources=(source, None),
        )

        consumed = plan_document_visuals._contextual_edit_consumed_sources((impact,))

        self.assertEqual({base, source}, consumed)
        self.assertNotIn(unrelated, consumed)

    def test_contextual_wall_width_edit_is_transactional(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            handle = next(
                item
                for item in session.contextual_rendering.edit_handles_for(wall)
                if item.subelement == "Width.PositiveFace"
            )
            session.contextual_editing.begin(handle)
            invalid = session.contextual_editing.commit(handle.point - handle.direction * 250)
            self.assertFalse(invalid.success)
            self.assertAlmostEqual(200.0, wall.Width.Value)

            session.contextual_editing.begin(handle)
            preview = session.contextual_editing.preview(handle.point + handle.direction * 50)
            self.assertTrue(preview.validation.allowed)
            self.assertNotIn(wall, session.contextual_rendering.renderer._preview_nodes)
            self.assertIn(
                ("contextual-preview", wall),
                session.viewport_state.scene_graph_mutations,
            )
            session.viewport.flush_scene_graph_mutations()
            preview_node = session.contextual_rendering.renderer._preview_nodes[wall]
            self.assertTrue(preview_node.isOfType(coin.SoSeparator.getClassTypeId()))
            self.assertNotEqual(
                -1, session.contextual_rendering.renderer.root.findChild(preview_node)
            )
            session.contextual_editing.cancel()
            session.viewport.flush_scene_graph_mutations()
            self.assertNotIn(wall, session.contextual_rendering.renderer._preview_nodes)

            session.contextual_editing.begin(handle)
            from bimplan import object_visibility

            renderer = session.contextual_rendering.renderer
            representation_before = renderer._representations[wall]
            root_before = renderer._object_nodes[wall]
            geometry_nodes_before = tuple(
                binding.group for binding in renderer._geometry_bindings[wall]
            )
            with patch.object(
                object_visibility,
                "apply_storey_visibility",
                wraps=object_visibility.apply_storey_visibility,
            ) as apply_storey_visibility:
                result = session.contextual_editing.commit(
                    handle.point + handle.direction * 50
                )
            apply_storey_visibility.assert_not_called()
            session.viewport.flush_scene_graph_mutations()

            self.assertTrue(result.success)
            self.assertAlmostEqual(250.0, wall.Width.Value)
            self.assertEqual("Right", wall.Align)
            self.assertAlmostEqual(-100.0, wall.Offset.Value)
            self.assertNotIn(wall, session.contextual_rendering.renderer._preview_nodes)
            self.assertIs(root_before, renderer._object_nodes[wall])
            self.assertIsNot(representation_before, renderer._representations[wall])
            self.assertEqual(
                geometry_nodes_before,
                tuple(binding.group for binding in renderer._geometry_bindings[wall]),
            )
            self.document.undo()
            self.assertAlmostEqual(200.0, wall.Width.Value)
            self.assertEqual("Center", wall.Align)
        finally:
            session.shutdown(close_dialog=False)

    def test_coin_event_activation_of_semantic_wall_handle_is_event_safe(self):
        import DraftGui
        from bimplan.selection import edit_nodes as plan_edit_nodes
        from draftguitools import gui_snapper

        created_toolbar = not hasattr(FreeCADGui, "draftToolBar")
        if created_toolbar:
            FreeCADGui.draftToolBar = DraftGui.DraftToolBar()
        created_snapper = not hasattr(FreeCADGui, "Snapper")
        if created_snapper:
            FreeCADGui.Snapper = gui_snapper.Snapper()

        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            session.selection.state.set_selected_plan_target_state("wall", wall)
            session.contextual_rendering.sync_visible_handles()
            session.view.fitAll()
            self.pump_gui_events()
            handle = next(
                item
                for item in session.contextual_rendering.edit_handles_for(wall)
                if item.subelement == "Width.PositiveFace"
            )
            start = session.view.getPointOnScreen(handle.point)
            self.assertIs(
                handle,
                session.contextual_rendering.pick_edit_handle(start),
            )

            event_manager = session.viewer.getSoEventManager()

            def send_move(point):
                event = coin.SoLocation2Event()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event_manager.processEvent(event)

            def send_button(point, state):
                event = coin.SoMouseButtonEvent()
                event.setPosition(coin.SbVec2s(round(point[0]), round(point[1])))
                event.setButton(coin.SoMouseButtonEvent.BUTTON1)
                event.setState(state)
                event_manager.processEvent(event)

            send_move(start)
            self.pump_gui_events(20)
            edit_node = handle
            with patch.object(session.picking, "pick_edit_node", return_value=edit_node):
                send_button(start, coin.SoButtonEvent.DOWN)
            self.assertIsNone(session.contextual_editing.editor)
            self.pump_gui_events(20)
            self.assertIsNotNone(session.contextual_editing.editor)
            session.contextual_editing.cancel()
        finally:
            session.shutdown(close_dialog=False)
            if created_snapper:
                del FreeCADGui.Snapper
            if created_toolbar:
                del FreeCADGui.draftToolBar

    def test_native_wall_semantic_handle_activates_wall_interaction_without_draft_grips(
        self,
    ):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            session.selection.state.set_selected_plan_target("wall", wall)
            self.assertFalse(hasattr(session.overlay_tracker_state, "grip_trackers"))

            renderer = session.contextual_rendering.renderer
            self.assertTrue(session.contextual_rendering.set_source_visible(wall, False))
            session.viewport.flush_scene_graph_mutations()
            self.assertEqual(
                coin.SO_SWITCH_NONE, renderer._object_nodes[wall].whichChild.getValue()
            )
            self.assertTrue(session.contextual_rendering.set_source_visible(wall, True))
            session.viewport.flush_scene_graph_mutations()
            self.assertEqual(coin.SO_SWITCH_ALL, renderer._object_nodes[wall].whichChild.getValue())

            handle = next(
                item
                for item in session.contextual_rendering.edit_handles_for(wall)
                if item.role == "WallMove"
            )
            handle_switch = renderer._handle_switches[wall]
            self.assertTrue(
                all(
                    handle_switch.getChild(index).getTypeId()
                    == coin.SoType.fromName("SoFCOverlayGlyph")
                    for index in range(handle_switch.getNumChildren())
                )
            )
            with patch.object(FreeCADGui, "Snapper", create=True) as snapper:
                self.assertTrue(session.contextual_editing.activate(handle))
            self.assertIs(handle, session.contextual_editing.editor.handle)
            snapper.getPoint.assert_called_once()
        finally:
            session.shutdown(close_dialog=False)

    def test_endpoint_square_resizes_unjoined_wall_along_its_axis(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        original_end = FreeCAD.Vector(wall.Proxy.calc_endpoints(wall)[1])
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            session.selection.state.set_selected_plan_target("wall", wall)
            handle = next(
                item
                for item in session.contextual_rendering.edit_handles_for(wall)
                if item.role == "WallPathEnd"
            )
            self.assertEqual("Square", handle.glyph)
            target = original_end + FreeCAD.Vector(200, 400, 0)
            expected_end = original_end + FreeCAD.Vector(200, 0, 0)

            with patch.object(FreeCADGui, "Snapper", create=True) as snapper:
                self.assertTrue(session.contextual_editing.activate(handle))
            callbacks = snapper.getPoint.call_args.kwargs
            callbacks["movecallback"](target, None)
            preview = session.contextual_editing.preview(target)
            self.assertTrue(preview.value.isEqual(expected_end, 1e-7))
            callbacks["callback"](target, None)
            self.pump_gui_events(20)

            endpoints = wall.Proxy.calc_endpoints(wall)
            self.assertTrue(endpoints[1].isEqual(expected_end, 1e-7))
            original_axis = original_end.sub(endpoints[0])
            resized_axis = endpoints[1].sub(endpoints[0])
            self.assertLess(original_axis.cross(resized_axis).Length, 1e-7)
            self.document.undo()
            self.document.recompute()
            restored = wall.Proxy.calc_endpoints(wall)
            self.assertTrue(restored[1].isEqual(original_end, 1e-7))
        finally:
            session.shutdown(close_dialog=False)

    def test_center_circle_moves_wall_opening_and_joint_as_one_transaction(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        original = [FreeCAD.Vector(point) for point in wall.Proxy.calc_endpoints(wall)]
        midpoint = (original[0] + original[1]) * 0.5
        joined = Arch.makeWall(length=1800, width=200, height=2500, align="Center")
        joined.Placement = FreeCAD.Placement(
            original[1],
            FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90),
        )
        opening = self.document.addObject("Part::FeaturePython", "HostedOpening")
        opening.addProperty("App::PropertyLinkList", "Hosts")
        opening.Hosts = [wall]
        opening.Placement.Base = midpoint
        opening.Proxy = _HostedOpeningProxy(opening)
        joint = Arch.makeWallJoint(wall, joined, "Miter")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            session.selection.state.set_selected_plan_target("wall", wall)
            handle = next(
                item
                for item in session.contextual_rendering.edit_handles_for(wall)
                if item.role == "WallMove"
            )
            self.assertEqual("Circle", handle.glyph)
            delta = FreeCAD.Vector(0, 250, 0)
            target = midpoint + delta

            opening_api = type(session.openings)
            with (
                patch.object(FreeCADGui, "Snapper", create=True) as snapper,
                patch.object(
                    opening_api,
                    "get_wall_hosted_openings",
                    return_value=[opening],
                ),
                patch.object(opening_api, "refresh_opening_footprint_display"),
                patch.object(opening_api, "refresh_opening_host_footprint_displays"),
            ):
                self.assertTrue(session.contextual_editing.activate(handle))
                callbacks = snapper.getPoint.call_args.kwargs
                callbacks["movecallback"](target, None)
                preview = session.contextual_editing.preview(target)
                self.assertTrue(preview.value.isEqual(midpoint + delta, 1e-7))
                callbacks["callback"](target, None)
                self.pump_gui_events(20)

            moved = wall.Proxy.calc_endpoints(wall)
            self.assertTrue(moved[0].isEqual(original[0] + delta, 1e-7))
            self.assertTrue(moved[1].isEqual(original[1] + delta, 1e-7))
            self.assertTrue(opening.Placement.Base.isEqual(midpoint + delta, 1e-7))
            self.assertEqual("OK", joint.Status, joint.StatusMessage)
            self.document.undo()
            self.document.recompute()
            restored = wall.Proxy.calc_endpoints(wall)
            self.assertTrue(restored[0].isEqual(original[0], 1e-7))
            self.assertTrue(restored[1].isEqual(original[1], 1e-7))
            self.assertTrue(opening.Placement.Base.isEqual(midpoint, 1e-7))
        finally:
            session.shutdown(close_dialog=False)

    def test_wall_move_rejects_an_unsolved_relation_before_preview_or_commit(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        joined = Arch.makeWall(length=1800, width=200, height=2500, align="Center")
        joined.Placement.Base = FreeCAD.Vector(3000, 0, 0)
        Arch.makeWallJoint(wall, joined, "Miter")
        self.document.recompute()
        capabilities = wall.Proxy.getEditCapabilities(
            wall, RepresentationRequest(purpose=RepresentationPurpose.MODEL)
        )
        operation = next(
            handle.operation
            for handle in capabilities.edit_handles
            if handle.role == "WallMove"
        )
        failed = SimpleNamespace(
            is_ok=lambda: False,
            status_message="Joined walls cannot meet at this candidate.",
        )
        with patch.object(ArchWallRelation, "solve_wall_joint_inputs", return_value=failed):
            validation = operation.validate(wall, FreeCAD.Vector(1600, 200, 0))
        self.assertFalse(validation.allowed)
        self.assertIn("cannot meet", validation.reason)

    def test_semantic_wall_move_repositions_hosted_opening(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        endpoints = tuple(wall.Proxy.calc_endpoints(wall))
        midpoint = (endpoints[0] + endpoints[1]) * 0.5
        opening = self.document.addObject("Part::FeaturePython", "SemanticOpening")
        opening.addProperty("App::PropertyLinkList", "Hosts")
        opening.Hosts = [wall]
        opening.Placement.Base = midpoint
        opening.Proxy = _HostedOpeningProxy(opening)

        delta = FreeCAD.Vector(0, 350, 0)
        apply_wall_candidate(wall, "Move", midpoint + delta)

        moved = wall.Proxy.calc_endpoints(wall)
        self.assertTrue(moved[0].isEqual(endpoints[0] + delta, 1e-7))
        self.assertTrue(moved[1].isEqual(endpoints[1] + delta, 1e-7))
        self.assertTrue(opening.Placement.Base.isEqual(midpoint + delta, 1e-7))

    def test_joint_diamond_moves_both_wall_endpoints_atomically(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        original_corner = FreeCAD.Vector(wall.Proxy.calc_endpoints(wall)[1])
        joined = Arch.makeWall(length=1800, width=200, height=2500, align="Center")
        joined.Placement = FreeCAD.Placement(
            original_corner + FreeCAD.Vector(0, 900, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90),
        )
        joint = Arch.makeWallJoint(wall, joined, "Miter")
        self.document.recompute()
        original_wall_points = [FreeCAD.Vector(point) for point in wall.Proxy.calc_endpoints(wall)]
        original_joined_points = [
            FreeCAD.Vector(point) for point in joined.Proxy.calc_endpoints(joined)
        ]

        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            solution = ArchWallRelation.solve_wall_joint(joint)
            self.assertTrue(
                solution.is_ok(),
                "{}; wall={!r}; joined={!r}".format(
                    solution.status_message,
                    wall.Proxy.calc_endpoints(wall),
                    joined.Proxy.calc_endpoints(joined),
                ),
            )
            self.assertTrue(wall.Proxy._can_edit_native_path(wall))
            self.assertTrue(joined.Proxy._can_edit_native_path(joined))
            self.assertIsNotNone(solution.trim_for_wall(wall))
            self.assertIsNotNone(solution.trim_for_wall(joined))
            direct = wall.Proxy.getRepresentation(wall, session.representation_request.request)
            self.assertIn("WallJointMove", [handle.role for handle in direct.edit_handles])
            session.selection.state.set_selected_plan_target("wall", wall)
            session.contextual_rendering.refresh_object(wall)
            session.viewport.flush_scene_graph_mutations()
            handles = session.contextual_rendering.edit_handles_for(wall)
            self.assertIn("WallJointMove", [handle.role for handle in handles])
            joint_handle = next(handle for handle in handles if handle.role == "WallJointMove")
            self.assertEqual("Diamond", joint_handle.glyph)
            self.assertEqual(13, joint_handle.glyph_size)
            self.assertFalse(
                any(handle.subelement == "Path.End" for handle in handles),
                "A relation-owned corner must not also expose a free endpoint handle",
            )

            target = original_corner + FreeCAD.Vector(250, 175, 0)
            self.assertTrue(session.contextual_editing.begin(joint_handle))
            preview_targets = [
                original_corner + FreeCAD.Vector(25 * step, 17.5 * step, 0) for step in range(1, 11)
            ]
            for preview_target in preview_targets:
                preview = session.contextual_editing.preview(preview_target)
                self.assertTrue(preview.validation.allowed)
            target = preview_targets[-1]
            preview_queue_key = ("contextual-preview-state", wall)
            self.assertIn(preview_queue_key, session.viewport_state.scene_graph_mutations)
            session.viewport.flush_scene_graph_mutations()
            renderer = session.contextual_rendering.renderer
            self.assertTrue(preview.validation.allowed)
            self.assertEqual({wall, joined}, set(renderer._preview_nodes))
            self.assertEqual(1, len(renderer._preview_groups))
            self.assertEqual({wall, joined}, renderer._preview_replaced_sources)
            self.assertTrue(
                wall.Proxy.calc_endpoints(wall)[1].isEqual(original_wall_points[1], 1e-7)
            )
            self.assertTrue(
                joined.Proxy.calc_endpoints(joined)[0].isEqual(original_joined_points[0], 1e-7)
            )
            session.contextual_editing.cancel()
            session.viewport.flush_scene_graph_mutations()
            self.assertFalse(renderer._preview_nodes)
            self.assertFalse(renderer._preview_replaced_sources)

            self.assertTrue(session.contextual_editing.begin(joint_handle))
            result = session.contextual_editing.commit(target)
            session.viewport.flush_scene_graph_mutations()

            self.assertTrue(result.success, result.reason)
            wall_points = wall.Proxy.calc_endpoints(wall)
            joined_points = joined.Proxy.calc_endpoints(joined)
            self.assertTrue(wall_points[1].isEqual(target, 1e-7))
            self.assertTrue(joined_points[0].isEqual(target, 1e-7))
            self.assertEqual("OK", joint.Status, joint.StatusMessage)

            self.document.undo()
            self.document.recompute()
            restored_wall = wall.Proxy.calc_endpoints(wall)
            restored_joined = joined.Proxy.calc_endpoints(joined)
            self.assertTrue(restored_wall[1].isEqual(original_wall_points[1], 1e-7))
            self.assertTrue(restored_joined[0].isEqual(original_joined_points[0], 1e-7))
        finally:
            session.shutdown(close_dialog=False)

    def test_contextual_representation_mapping_drives_wall_pick_and_handle_pick(self):
        from bimplan.picking import edit_nodes as picking_edit_nodes
        from bimplan.selection import edit_nodes as selection_edit_nodes

        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        session = PlanEditSession()
        self.assertTrue(session.enter())
        try:
            session.view.fitAll()
            self.pump_gui_events()
            screen_point = session.view.getPointOnScreen(wall.Shape.BoundBox.Center)
            picked_mapping = session.contextual_rendering.pick_mapping(screen_point, radius_px=8)
            self.assertIsNotNone(picked_mapping)
            self.assertIs(wall, picked_mapping.source)
            self.assertTrue(session.picking.hover(screen_point, force=True))
            self.assertIs(wall, session.hovered_wall)
            self.assertTrue(session.viewport_state.scene_graph_flush_queued)
            self.pump_gui_events()
            self.assertGreater(len(session.overlay_tracker_state.wall_hover_trackers), 0)

            geometry_mapping = ContextualNodeMapping(wall, "Face1", "Cut", object())
            with patch.object(
                session.contextual_rendering,
                "pick_mapping",
                return_value=geometry_mapping,
            ):
                target = session.picking.pick((10, 10))
            self.assertEqual("wall", target.kind)
            self.assertIs(wall, target.obj)

            handle = next(
                item
                for item in session.contextual_rendering.edit_handles_for(wall)
                if item.role == "WallWidth"
            )
            handle_screen_point = session.view.getPointOnScreen(handle.point)
            self.assertIsNone(session.contextual_rendering.pick_edit_handle(handle_screen_point))
            session.selection.state.set_selected_plan_target("wall", wall)
            session.viewport.flush_scene_graph_mutations()
            self.assertIs(
                handle,
                session.contextual_rendering.pick_edit_handle(handle_screen_point),
            )
            with patch.object(
                session.contextual_rendering,
                "pick_edit_handle",
                return_value=handle,
            ):
                node = picking_edit_nodes.get_edit_node(session, (10, 10))
            self.assertEqual("contextual_handle", selection_edit_nodes.get_edit_node_kind(node))
            self.assertEqual((wall, handle), selection_edit_nodes.get_edit_node_payload(node))
        finally:
            session.shutdown(close_dialog=False)
