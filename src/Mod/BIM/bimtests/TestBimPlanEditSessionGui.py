# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI tests for the viewer-local BIM Plan Edit session."""

from unittest.mock import patch

import Arch
import ArchWallRelation
import FreeCAD
import FreeCADGui
from pivy import coin
from ArchRepresentation import BIMEditRay, RepresentationContext
from bimtests.TestArchBaseGui import TestArchBaseGui
from bimplan.runtime.session import PlanEditSession
from bimplan.contextual_edit_3d import BIM3DContextualEditingSession
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


class _HostedOpeningProxy:
    """Minimal semantic opening used to exercise host-relative wall movement."""

    def __init__(self, obj):
        self.Object = obj

    def get_plan_move_context(self):
        return {"opening_half_width_u": 50.0}

    def get_plan_center_point(self):
        return FreeCAD.Vector(self.Object.Placement.Base)

    def move_along_host(self, point):
        placement = FreeCAD.Placement(self.Object.Placement)
        placement.Base = FreeCAD.Vector(point)
        self.Object.Placement = placement
        return True


class TestBimPlanEditSessionGui(TestArchBaseGui):
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

    def test_task_panel_exit_finishes_the_session(self):
        session = PlanEditSession()

        self.assertTrue(session.enter())
        self.assertIsNotNone(session.task_panel)
        gui_document = session.gui_doc
        self.assertTrue(FreeCADGui.Control.activeDialog(gui_document))
        from PySide import QtGui

        main_window = FreeCADGui.getMainWindow()
        self.assertIsNotNone(main_window.findChild(QtGui.QWidget, "BIMPlanEditContextControls"))
        session.task_panel.exit_button.click()

        self.assertIsNone(session.task_panel)
        self.assertIsNone(session.viewport_state.view_context_layer)
        self.assertFalse(FreeCADGui.Control.activeDialog(gui_document))

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

            session.overlays.geometry.invalidate_plan_overlay_geometry_cache(
                wall, kinds=("representation",)
            )
            session.contextual_rendering.refresh_object(wall)
            session.contextual_rendering.refresh_object(wall)

            key = ("contextual-renderer", ("representation", wall))
            self.assertIn(key, session.viewport_state.scene_graph_mutations)
            self.assertIs(original_node, renderer._object_nodes[wall])
            session.viewport.flush_scene_graph_mutations()
            self.assertIsNot(original_node, renderer._object_nodes[wall])

            session.contextual_rendering.close()
            self.assertIsNone(session.contextual_rendering.renderer)
            self.assertIsNotNone(renderer.root)
            session.viewport.flush_scene_graph_mutations()
            self.assertIsNone(renderer.root)
        finally:
            session.shutdown(close_dialog=False)

    def test_contextual_interaction_renderer_preserves_source_visibility(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        representation = wall.Proxy.getRepresentation(
            wall,
            RepresentationContext(purpose="Plan", cut_offset=1000, target_offset=0),
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
        session = BIM3DContextualEditingSession(view)
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

    def test_standard_3d_ray_constraints_commit_path_move_and_offset(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Left")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        session = BIM3DContextualEditingSession(view)
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
        from bimplan.contextual_edit_3d import active_session

        command = BIM_ContextualEdit3D()
        self.assertTrue(command.IsActive())
        command.Activated()
        session = active_session()
        self.assertIsNotNone(session)
        try:
            self.assertEqual(3, len(session._callbacks))
            command.Activated()
            self.assertIsNone(active_session())
            self.assertTrue(session._closed)
        finally:
            if active_session() is session:
                session.close()

    def test_standard_3d_pointer_drag_commits_a_semantic_width_edit(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500, align="Center")
        self.document.recompute()
        view = FreeCADGui.ActiveDocument.ActiveView
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        session = BIM3DContextualEditingSession(view)
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
            focal_point = view.getPointOnFocalPlane((round(target[0]), round(target[1])))
            projected_target = handle.constraint.project(target_ray)
            pointer_delta = (projected_target - handle.point).dot(handle.direction)
            self.assertAlmostEqual(
                50.0,
                pointer_delta,
                delta=15.0,
                msg=(
                    "projected {} mm from screen {} for handle point {}; ray {}, {}; "
                    "focal point {} projects to {}"
                ).format(
                    pointer_delta,
                    target,
                    handle.point,
                    target_ray.origin,
                    target_ray.direction,
                    focal_point,
                    view.getPointOnScreen(focal_point),
                ),
            )
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

            self.assertAlmostEqual(250.0, wall.Width.Value, delta=10.0)
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

            keyboard_keys = {
                "2": coin.SoKeyboardEvent.NUMBER_2,
                "8": coin.SoKeyboardEvent.NUMBER_8,
                ".": coin.SoKeyboardEvent.PERIOD,
                " ": coin.SoKeyboardEvent.SPACE,
                "m": coin.SoKeyboardEvent.M,
            }

            def send_key(key, character=""):
                event = coin.SoKeyboardEvent()
                event.setKey(key)
                if character:
                    event.setPrintableCharacter(character)
                event.setState(coin.SoKeyboardEvent.DOWN)
                event_manager.processEvent(event)

            for character in "2.8 m":
                send_key(keyboard_keys[character], character)
            send_key(coin.SoKeyboardEvent.RETURN)
            self.pump_gui_events(30)

            self.assertAlmostEqual(2800.0, wall.Height.Value)
            self.assertIsNone(session.active_edit)
        finally:
            session.close()
            FreeCADGui.Selection.clearSelection()

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
            self.assertTrue(preview_node.isOfType(coin.SoType.fromName("SoPreviewShape")))
            self.assertNotEqual(
                -1, session.contextual_rendering.renderer.root.findChild(preview_node)
            )
            session.contextual_editing.cancel()
            session.viewport.flush_scene_graph_mutations()
            self.assertNotIn(wall, session.contextual_rendering.renderer._preview_nodes)

            session.contextual_editing.begin(handle)
            result = session.contextual_editing.commit(handle.point + handle.direction * 50)
            session.viewport.flush_scene_graph_mutations()

            self.assertTrue(result.success)
            self.assertAlmostEqual(250.0, wall.Width.Value)
            self.assertEqual("Right", wall.Align)
            self.assertAlmostEqual(-100.0, wall.Offset.Value)
            self.assertNotIn(wall, session.contextual_rendering.renderer._preview_nodes)
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
            edit_node = plan_edit_nodes.ContextualHandleEditNode(wall, handle)
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
            wall_edit_type = type(session.wall_edit)
            with patch.object(wall_edit_type, "start_wall_edit") as start_wall_edit:
                with patch.object(wall_edit_type, "has_active_wall_edit", return_value=True):
                    self.assertTrue(session.contextual_editing.activate(handle))
            start_wall_edit.assert_called_once_with("Move")
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
            self.assertTrue(session.wall_edit_state.preview_points[1].isEqual(expected_end, 1e-7))
            callbacks["callback"](target, None)

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
                preview = session.wall_edit_state.preview_points
                self.assertTrue(preview[0].isEqual(original[0] + delta, 1e-7))
                self.assertTrue(preview[1].isEqual(original[1] + delta, 1e-7))
                callbacks["callback"](target, None)

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
            direct = wall.Proxy.getRepresentation(wall, session.representation_context.context)
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
            preview = session.contextual_editing.preview(target)
            session.viewport.flush_scene_graph_mutations()
            renderer = session.contextual_rendering.renderer
            self.assertTrue(preview.validation.allowed)
            self.assertEqual({wall, joined}, set(renderer._preview_nodes))
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
