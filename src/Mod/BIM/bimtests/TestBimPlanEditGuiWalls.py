# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall editing and join GUI tests."""

from .TestBimPlanEditGuiBase import *  # noqa: F401,F403
from .TestBimPlanEditGuiBase import BimPlanEditGuiBase


class BimPlanEditGuiWallsMixin:
    def test_plan_edit_embedded_wall_uses_sane_top_plane(self):
        """Embedded wall creation in Plan Edit should start from a clean top plane."""

        self.params.SetInt("WallBaseline", 0)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session.lifecycle.activate_wall_tool()
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Wall")
        self.assertIsNotNone(session._embedded_tool, "Wall tool should be embedded in Plan Edit.")
        self.assertIsInstance(session._embedded_tool, current_arch_wall_class())

        self.assertPlaneIsSaneTop(session.viewport.get_interaction_plane())
        self.assertPlaneIsSaneTop(session._embedded_tool._plane)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_embedded_wall_first_update_stays_sane(self):
        """The first embedded wall preview update in Plan Edit should stay bounded."""

        self.params.SetInt("WallBaseline", 0)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        session.lifecycle.activate_wall_tool()
        self.pump_gui_events()

        cmd = session._embedded_tool
        self.assertIsInstance(cmd, current_arch_wall_class())

        cmd.tracker = MockTracker()
        first = FreeCAD.Vector(1000, 1000, 0)
        second = FreeCAD.Vector(3000, 1000, 0)

        cmd.getPoint(first)
        self.assertEqual(len(cmd.points), 1)

        self.assertTrue(
            FreeCADGui.Control.activeDialog(),
            "Embedded wall point picking should open a live Draft dialog.",
        )
        cmd.update(second, None)

        self.assertPlaneIsSaneTop(cmd._plane)
        self.assertIsNotNone(cmd.tracker.last_points, "Expected a preview update on the tracker.")
        self.assertEqual(len(cmd.tracker.last_points), 2)
        for point in cmd.tracker.last_points:
            self.assertLess(abs(point.x), 1e6)
            self.assertLess(abs(point.y), 1e6)
            self.assertLess(abs(point.z), 1e6)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_rect_wall_tool_creates_four_walls(self):
        """Plan Edit should create a rectangular run as four baseless walls."""

        level = Arch.makeFloor(name="Level 0")
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        before = {obj.Name for obj in self.document.Objects}
        session.lifecycle.activate_rect_wall_tool()
        self.pump_gui_events()

        self.assertEqual(session.current_tool, "Rect Wall")

        session.wall_create.handle_rect_wall_point(FreeCAD.Vector(0, 0, 0))
        session.wall_create.handle_rect_wall_point(FreeCAD.Vector(3000, 2000, 0))
        self.pump_gui_events()

        created = [obj for obj in self.document.Objects if obj.Name not in before]
        walls = [obj for obj in created if Draft.getType(obj) == "Wall"]
        self.assertEqual(len(walls), 4, "Expected exactly four walls from a rectangular run.")
        for wall in walls:
            self.assertIn(level, wall.InListRecursive)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_rect_wall_tool_autojoins_closed_run(self):
        """Rectangular wall runs should autojoin as one closed addition host when enabled."""

        arch_params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Arch")
        original_autojoin = arch_params.GetBool("autoJoinWalls", False)

        try:
            arch_params.SetBool("autoJoinWalls", True)
            level = Arch.makeFloor(name="Level 0")
            self.document.recompute()

            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(level)

            session = BimPlanSession.start_session()
            self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
            self.pump_gui_events()

            before = {obj.Name for obj in self.document.Objects}
            session.lifecycle.activate_rect_wall_tool()
            self.pump_gui_events()

            session.wall_create.handle_rect_wall_point(FreeCAD.Vector(0, 0, 0))
            session.wall_create.handle_rect_wall_point(FreeCAD.Vector(3000, 2000, 0))
            self.pump_gui_events()

            created = [obj for obj in self.document.Objects if obj.Name not in before]
            walls = [obj for obj in created if Draft.getType(obj) == "Wall"]
            self.assertEqual(len(walls), 4)
            self.assertEqual(sum(len(wall.Additions) for wall in walls), 3)

            session.shutdown(close_dialog=False)
            self.pump_gui_events()
        finally:
            arch_params.SetBool("autoJoinWalls", original_autojoin)

    def test_plan_edit_rect_wall_tool_undo_redo_roundtrip(self):
        """Rect wall creation should roundtrip cleanly through document undo/redo."""

        level = Arch.makeFloor(name="Level 0")
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        initial_wall_names = {
            obj.Name for obj in self.document.Objects if Draft.getType(obj) == "Wall"
        }

        session.lifecycle.activate_rect_wall_tool()
        self.pump_gui_events()
        session.wall_create.handle_rect_wall_point(FreeCAD.Vector(0, 0, 0))
        session.wall_create.handle_rect_wall_point(FreeCAD.Vector(3000, 2000, 0))
        self.pump_gui_events()

        created_walls = [
            obj
            for obj in self.document.Objects
            if Draft.getType(obj) == "Wall" and obj.Name not in initial_wall_names
        ]
        self.assertEqual(len(created_walls), 4)
        for wall in created_walls:
            self.assertIn(level, wall.InListRecursive)
        self._assert_wall_selection_visual_consistency(session)

        self._undo_document()
        undone_walls = [
            obj
            for obj in self.document.Objects
            if Draft.getType(obj) == "Wall" and obj.Name not in initial_wall_names
        ]
        self.assertEqual(len(undone_walls), 0)
        self._assert_wall_selection_visual_consistency(session)

        self._redo_document()
        redone_walls = [
            obj
            for obj in self.document.Objects
            if Draft.getType(obj) == "Wall" and obj.Name not in initial_wall_names
        ]
        self.assertEqual(len(redone_walls), 4)
        for wall in redone_walls:
            self.assertIn(level, wall.InListRecursive)
        self._assert_wall_selection_visual_consistency(session)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hides_joined_wall_additions(self):
        """Joined child walls should stay hidden so their footprints do not overdraw the host."""

        host = Arch.makeWall(length=3000, width=200, height=2500)
        child = Arch.makeWall(length=3000, width=200, height=2500)
        Arch.addComponents(child, host)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(host.ViewObject.Visibility)
        self.assertFalse(
            child.ViewObject.Visibility,
            "Joined child walls should stay hidden in Plan Edit to avoid double rendering.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_ctrl_click_adds_wall_to_selection_without_replacing_primary_target(self):
        """Ctrl-click should build a wall selection set while keeping the current primary wall."""

        from PySide import QtCore

        level = Arch.makeFloor(name="Level 0")
        wall_a = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        level.addObject(wall_a)
        level.addObject(wall_b)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", wall_a),
            ),
        ):
            session.input.on_mouse_pressed(self._make_fake_left_mouse_press())

        self._assert_selected_plan_target(session, "wall", wall_a)
        self.pump_gui_events()
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [wall_a.Name])

        with (
            patch(
                "PySide.QtGui.QApplication.keyboardModifiers",
                return_value=QtCore.Qt.ControlModifier,
            ),
            patch.object(
                session.selection,
                "get_edit_node",
                return_value=None,
            ),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", wall_b),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session.input.on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        self._assert_selected_plan_target(session, "wall", wall_a)
        self.assertEqual(
            [obj.Name for obj in FreeCADGui.Selection.getSelection()],
            [wall_a.Name, wall_b.Name],
        )
        self.assertEqual(session.selection.state.get_selected_plan_target(), ("wall", wall_a))
        self.assertEqual(
            session.selection.state.get_secondary_selected_plan_targets(), [("wall", wall_b)]
        )
        self.assertGreater(len(session._secondary_selection_trackers), 0)
        self.assertIn("Selection set: 2 walls", session.task_panel.status.text())

        with (
            patch(
                "PySide.QtGui.QApplication.keyboardModifiers",
                return_value=QtCore.Qt.ControlModifier,
            ),
            patch.object(
                session.selection,
                "get_edit_node",
                return_value=None,
            ),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", wall_a),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session.input.on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        self._assert_selected_plan_target(session, "wall", wall_b)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [wall_b.Name])
        self.assertEqual(session.selection.state.get_selected_plan_target(), ("wall", wall_b))
        self.assertEqual(session.selection.state.get_secondary_selected_plan_targets(), [])
        self.assertEqual(len(session._secondary_selection_trackers), 0)
        self.assertNotIn("Selection set:", session.task_panel.status.text())

        session.shutdown(close_dialog=False)

        self.pump_gui_events()

    def test_plan_edit_real_view_hovered_wall_shows_preselection_overlay(self):
        """Real view-based hover should pick a wall and keep the warm path cheap."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        faces = list(
            getattr(getattr(wall, "Proxy", None), "getFootprint", lambda _obj: [])(wall) or []
        )
        self.assertTrue(faces)
        face = faces[0]
        point = FreeCAD.Vector(face.CenterOfMass)
        screen_pos = session.view.getPointOnScreen(point)
        mouse_pos = (int(screen_pos[0]), int(screen_pos[1]))

        move = self._make_fake_mouse_move_event(*mouse_pos)
        session.input.on_mouse_moved(move)
        self.pump_gui_events()

        self.assertIs(session.hovered_wall, wall)
        self.assertGreater(len(session._wall_hover_trackers), 0)

        move_again = self._make_fake_mouse_move_event(*mouse_pos)
        session.input.on_mouse_moved(move_again)
        self.pump_gui_events()

        self.assertIs(session.hovered_wall, wall)
        self.assertGreater(len(session._wall_hover_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_empty_canvas_click_clears_selected_wall(self):
        """Transient empty GUI selection should not immediately deselect a clicked wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.selection,
            "get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session.selection.activation.activate_wall_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(session._pending_selected_plan_target, ("wall", wall))

        FreeCADGui.Selection.clearSelection()
        self.pump_gui_events()

        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertIsNone(session._pending_selected_plan_target)

        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=(None, None),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))
        self.pump_gui_events(timeout_ms=500)

        self._assert_no_selected_plan_target(session)
        self.assertIsNone(session._pending_selected_plan_target)
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertEqual(self._get_scenegraph_edit_nodes(session), [])

    def test_plan_edit_empty_canvas_click_clears_lingering_storey_gui_selection(self):
        """Select-mode empty clicks should clear the initial storey GUI selection."""

        level = Arch.makeFloor(name="Level 0")
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [level.Name])

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=(None, None),
            ),
        ):
            callback = self._make_fake_left_mouse_press()
            session.input.on_mouse_pressed(callback)
        self.pump_gui_events(timeout_ms=500)

        self.assertTrue(callback._handled)
        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self._assert_no_selected_plan_target(session)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hovered_wall_shows_preselection_overlay(self):
        """Walls should get a lightweight hover overlay before actual selection."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.selection,
            "get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            session.selection.hover.update_hovered_plan_target((100, 100))

        self.assertIs(session.hovered_wall, wall)
        self.assertIsNone(session.hovered_opening)
        self.assertGreater(len(session._wall_hover_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 0)

    def test_plan_edit_hovered_wall_shows_hosted_opening_context(self):
        """Hovering a wall should passively highlight its hosted openings."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        self._make_hosted_door(wall, name="HoverWallContextDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.selection,
            "get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            session.selection.hover.update_hovered_plan_target((100, 100))

        self.assertIs(session.hovered_wall, wall)
        self._assert_no_selected_plan_target(session)
        self.assertGreater(len(session._wall_hover_trackers), 0)
        self.assertGreater(len(session._hovered_wall_opening_context_trackers), 0)
        self.assertEqual(len(session._opening_hover_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 0)

    def test_plan_edit_clicking_hovered_wall_selects_it(self):
        """Clicking a hovered wall should promote it to selected wall state."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.selection,
            "get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session.selection.activation.activate_wall_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._wall_hover_trackers), 0)
        self.assertGreater(len(session._wall_overlay_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_real_click_selection_draws_wall_outline_before_deferred_grips(self):
        """Real wall clicks should paint the selected outline immediately, before grip sync lands."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", wall),
            ),
            patch.object(session.viewport, "request_view_redraw") as request_view_redraw,
        ):
            callback = self._make_fake_left_mouse_press()
            session.input.on_mouse_pressed(callback)

            self.assertTrue(callback._handled)
            self._assert_selected_plan_target(session, "wall", wall)
            self.assertEqual(len(session._wall_hover_trackers), 0)
            self.assertGreater(len(session._wall_overlay_trackers), 0)
            self.assertEqual(len(session._grip_trackers), 0)
            request_view_redraw.assert_called()

        self.pump_gui_events(timeout_ms=250)

        self._assert_selected_plan_target(session, "wall", wall)
        self.assertGreater(len(session._wall_overlay_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_wall_refresh_can_force_grip_resync_for_same_wall(self):
        """Forced selection refresh should repair wall grips even when the selected wall is unchanged."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.selection,
            "get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session.selection.activation.activate_wall_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_wall_visuals(session, wall)

        bogus_points = (
            FreeCAD.Vector(999.0, 0.0, 0.0),
            FreeCAD.Vector(1111.0, 0.0, 0.0),
            FreeCAD.Vector(1234.0, 0.0, 0.0),
        )
        for tracker, bogus in zip(session._grip_trackers, bogus_points):
            tracker.set(bogus)

        session.selection.refresh.refresh_primary_selected_plan_target(force_wall_visual_resync=True)
        self.pump_gui_events(timeout_ms=250)

        self._assert_selected_wall_visuals(session, wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_wall_shows_hosted_opening_context(self):
        """Selecting a wall should highlight hosted openings without selecting them."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="WallContextDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.selection,
            "get_plan_target_at_position",
            return_value=("wall", wall),
        ):
            activated = session.selection.activation.activate_wall_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertGreater(len(session._wall_overlay_trackers), 0)
        self.assertEqual(len(session._grip_trackers), 3)
        self.assertGreater(len(session._selected_wall_opening_context_trackers), 0)
        self.assertEqual(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 0)

        session.selection.activation.select_opening_for_plan_edit(door)

        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session._wall_overlay_trackers), 0)
        self.assertEqual(len(session._selected_wall_opening_context_trackers), 0)
        self.assertGreater(len(session._opening_overlay_trackers), 0)
        self.assertEqual(len(session._opening_handle_trackers), 3)

    def test_plan_edit_join_mode_hover_tracks_candidate_wall(self):
        """Join mode should keep a hovered candidate wall visible for joining."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.lifecycle.activate_join_tool()

        self.assertEqual(session.current_tool, "Join")
        self._assert_selected_plan_target(session, "wall", source_wall)
        self.assertEqual(len(session._grip_trackers), 0)

        with patch.object(
            session.selection,
            "get_plan_target_at_position",
            return_value=("wall", target_wall),
        ):
            session.selection.hover.update_hovered_plan_target((100, 100))
            session.overlays.manager.refresh_plan_overlay_visuals()

        self.assertIs(session.hovered_wall, target_wall)
        self.assertIsNone(session.hovered_opening)
        self.assertGreater(len(session._wall_hover_trackers), 0)
        self.assertEqual(len(session._hovered_wall_opening_context_trackers), 0)

    def test_plan_edit_join_mode_cancel_restores_selected_wall_grips(self):
        """Canceling join mode should return to Select with the source wall active."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        self.assertEqual(len(session._grip_trackers), 3)

        session.lifecycle.activate_join_tool()
        self.assertEqual(session.current_tool, "Join")
        self.assertEqual(len(session._grip_trackers), 0)

        session.wall_relations.cancel_join_tool()

        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "wall", source_wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_join_mode_cycles_join_type_with_tab(self):
        """Join mode should cycle the active join type and reflect it in the UI."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.lifecycle.activate_join_tool()

        self.assertEqual(session.wall_relations.get_plan_join_type(), "Miter")
        self.assertEqual(
            session.task_panel.join_type_combo.currentIndex(),
            session.task_panel.join_type_combo.findData("Miter"),
        )

        from pivy import coin

        event_callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.TAB))
        session.input.on_key_pressed(event_callback)

        self.assertEqual(session.wall_relations.get_plan_join_type(), "Butt")
        self.assertEqual(
            session.task_panel.join_type_combo.currentIndex(),
            session.task_panel.join_type_combo.findData("Butt"),
        )
        self.assertTrue(event_callback._handled)
        _title, body = session._get_status_chip_text()
        self.assertIn("butt joint", body.lower())
        self.assertIn("Join type: Butt", session.task_panel.status.text())

    def test_plan_edit_join_mode_creates_wall_joint_from_clicked_candidate(self):
        """Join mode should create a BIM wall joint from the selected and clicked walls."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.lifecycle.activate_join_tool()

        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Miter")
        self.assertEqual(joint.Status, "OK")
        self.assertEqual({joint.WallA, joint.WallB}, {source_wall, target_wall})

        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_wall_visuals(session, source_wall)
        self.assertIsNone(session.selection.state.get_selected_target_for_kind("opening"))
        self.assertEqual(len(session._grip_trackers), 3)
        self.assertEqual(len(session._wall_hover_trackers), 0)

    def test_plan_edit_join_mode_uses_selected_join_type_from_dock(self):
        """Join mode should create the join type currently selected in the dock."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        butt_index = session.task_panel.join_type_combo.findData("Butt")
        self.assertGreaterEqual(butt_index, 0)
        session.task_panel.join_type_combo.setCurrentIndex(butt_index)
        self.pump_gui_events()

        self.assertEqual(session.wall_relations.get_plan_join_type(), "Butt")

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.lifecycle.activate_join_tool()

        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Butt")
        trimmed_wall = joint.WallA if joint.ButtTrimmed == "WallA" else joint.WallB
        self.assertIs(trimmed_wall, target_wall)
        self.assertEqual(joint.Status, "OK")

    def test_plan_edit_join_mode_updates_existing_joint_for_hovered_pair(self):
        """Join mode should surface and update an existing wall joint for the hovered pair."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.wall_relations.set_plan_join_type("Butt")
        session.lifecycle.activate_join_tool()
        session.selection.hover.set_hovered_wall(target_wall)

        self.assertTrue(session.task_panel.unjoin_button.isEnabled())
        _title, body = session._get_status_chip_text()
        self.assertIn("Existing joint", body)
        self.assertIn("change it to a butt joint", body.lower())
        self.assertIn("Existing joint", session.task_panel.status.text())

        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        self.assertIs(joints[0], joint)
        self.assertEqual(joint.JointType, "Butt")
        self.assertEqual(session.current_tool, "Select")

    def test_plan_edit_join_mode_unjoins_hovered_pair(self):
        """Join mode should remove the existing joint for the hovered wall pair."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.lifecycle.activate_join_tool()
        session.selection.hover.set_hovered_wall(target_wall)

        self.assertTrue(session.task_panel.unjoin_button.isEnabled())
        self.assertTrue(session.wall_relations.unjoin_current_plan_wall_pair())
        self.pump_gui_events()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 0)
        self.assertEqual(session.current_tool, "Join")
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)
        self.assertIs(session.hovered_wall, target_wall)
        self.assertFalse(session.task_panel.unjoin_button.isEnabled())
        _title, body = session._get_status_chip_text()
        self.assertIn("Candidate wall", body)
        self.assertIn("create a miter joint", body.lower())

    def test_plan_edit_join_mode_undo_redo_roundtrip(self):
        """Wall join creation should roundtrip cleanly through document undo/redo."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.lifecycle.activate_join_tool()

        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Miter")
        self.assertEqual({joint.WallA, joint.WallB}, {source_wall, target_wall})
        self._assert_selected_wall_visuals(session, source_wall)
        self.assertEqual(len(session._wall_hover_trackers), 0)

        self._undo_document()
        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(joints, [])
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)
        self.assertEqual(len(session._wall_hover_trackers), 0)

        self._redo_document()
        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Miter")
        self.assertEqual({joint.WallA, joint.WallB}, {source_wall, target_wall})
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)
        self.assertEqual(len(session._wall_hover_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_join_update_undo_keeps_adjacent_wall_linked_spaces_distinct(self):
        """Updating an existing wall joint should keep adjacent spaces distinct through undo/redo."""

        from bimcommands.BimJoin import BIM_Join_Miter

        FreeCADGui.Selection.clearSelection()
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        (
            _level,
            walls,
            divider_wall,
            _boundaries,
            created_spaces,
        ) = self._create_adjacent_wall_linked_spaces(session)
        source_wall = next(wall for wall in walls if wall.Label == "South Wall")
        target_wall = divider_wall

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.pump_gui_events()

        sorted_spaces = self._assert_spaces_stay_distinct(created_spaces)
        initial_centers = [float(space.Shape.CenterOfMass.x) for space in sorted_spaces]
        initial_areas = [float(space.Proxy.getArea(space)) for space in sorted_spaces]

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.wall_relations.set_plan_join_type("Butt")
        session.lifecycle.activate_join_tool()
        session.selection.hover.set_hovered_wall(target_wall)

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", target_wall),
            ),
        ):
            session.input.on_mouse_pressed(self._make_fake_left_mouse_press())

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Butt")
        updated_spaces = self._assert_spaces_stay_distinct(created_spaces)
        updated_centers = [float(space.Shape.CenterOfMass.x) for space in updated_spaces]
        updated_areas = [float(space.Proxy.getArea(space)) for space in updated_spaces]
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)

        self._undo_document()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Miter")

        restored_spaces = self._assert_spaces_stay_distinct(created_spaces)
        restored_centers = [float(space.Shape.CenterOfMass.x) for space in restored_spaces]
        restored_areas = [float(space.Proxy.getArea(space)) for space in restored_spaces]
        for initial_center, restored_center in zip(initial_centers, restored_centers):
            self.assertAlmostEqual(restored_center, initial_center, delta=1e-6)
        for initial_area, restored_area in zip(initial_areas, restored_areas):
            self.assertAlmostEqual(restored_area, initial_area, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)

        self._redo_document()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Butt")

        redone_spaces = self._assert_spaces_stay_distinct(created_spaces)
        redone_centers = [float(space.Shape.CenterOfMass.x) for space in redone_spaces]
        redone_areas = [float(space.Proxy.getArea(space)) for space in redone_spaces]
        for updated_center, redone_center in zip(updated_centers, redone_centers):
            self.assertAlmostEqual(redone_center, updated_center, delta=1e-6)
        for updated_area, redone_area in zip(updated_areas, redone_areas):
            self.assertAlmostEqual(redone_area, updated_area, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_unjoin_undo_keeps_adjacent_wall_linked_spaces_distinct(self):
        """Unjoining a wall pair should keep adjacent spaces distinct through undo/redo."""

        from bimcommands.BimJoin import BIM_Join_Miter

        FreeCADGui.Selection.clearSelection()
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        (
            _level,
            walls,
            divider_wall,
            _boundaries,
            created_spaces,
        ) = self._create_adjacent_wall_linked_spaces(session)
        source_wall = next(wall for wall in walls if wall.Label == "South Wall")
        target_wall = divider_wall

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.pump_gui_events()

        sorted_spaces = self._assert_spaces_stay_distinct(created_spaces)
        initial_centers = [float(space.Shape.CenterOfMass.x) for space in sorted_spaces]
        initial_areas = [float(space.Proxy.getArea(space)) for space in sorted_spaces]

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        session.lifecycle.activate_join_tool()
        session.selection.hover.set_hovered_wall(target_wall)

        self.assertTrue(session.wall_relations.unjoin_current_plan_wall_pair())
        self.pump_gui_events()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(joints, [])
        updated_spaces = self._assert_spaces_stay_distinct(created_spaces)
        updated_centers = [float(space.Shape.CenterOfMass.x) for space in updated_spaces]
        updated_areas = [float(space.Proxy.getArea(space)) for space in updated_spaces]
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)

        self._undo_document()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Miter")

        restored_spaces = self._assert_spaces_stay_distinct(created_spaces)
        restored_centers = [float(space.Shape.CenterOfMass.x) for space in restored_spaces]
        restored_areas = [float(space.Proxy.getArea(space)) for space in restored_spaces]
        for initial_center, restored_center in zip(initial_centers, restored_centers):
            self.assertAlmostEqual(restored_center, initial_center, delta=1e-6)
        for initial_area, restored_area in zip(initial_areas, restored_areas):
            self.assertAlmostEqual(restored_area, initial_area, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)

        self._redo_document()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        self.assertEqual(joints, [])

        redone_spaces = self._assert_spaces_stay_distinct(created_spaces)
        redone_centers = [float(space.Shape.CenterOfMass.x) for space in redone_spaces]
        redone_areas = [float(space.Proxy.getArea(space)) for space in redone_spaces]
        for updated_center, redone_center in zip(updated_centers, redone_centers):
            self.assertAlmostEqual(redone_center, updated_center, delta=1e-6)
        for updated_area, redone_area in zip(updated_areas, redone_areas):
            self.assertAlmostEqual(redone_area, updated_area, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), source_wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_wall_shows_junction_node_overlay(self):
        """Selecting a wall in a wall junction should show the junction node overlay."""

        carrier_wall = Arch.makeWall(length=3000, width=200, height=2500)
        carrier_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(1500, 0, 0), FreeCAD.Rotation())
        branch_up = Arch.makeWall(length=1500, width=200, height=2500)
        branch_up.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        branch_down = Arch.makeWall(length=1500, width=200, height=2500)
        branch_down.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        junction = Arch.makeWallJunction([carrier_wall, branch_up, branch_down])
        self.document.recompute()
        self.assertEqual(junction.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(carrier_wall)

        self.assertGreater(len(session._junction_node_trackers), 0)

    def test_plan_edit_join_promotes_wall_pair_to_junction(self):
        """Joining a third compatible wall should promote the cluster to a wall junction."""

        carrier_wall = Arch.makeWall(length=3000, width=200, height=2500)
        carrier_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(1500, 0, 0), FreeCAD.Rotation())
        branch_up = Arch.makeWall(length=1500, width=200, height=2500)
        branch_up.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        branch_down = Arch.makeWall(length=1500, width=200, height=2500)
        branch_down.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Tee

        joint = Arch.makeWallJoint(branch_up, carrier_wall, "Tee")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Tee()._configure_joint(joint, branch_up, carrier_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(carrier_wall)
        session.lifecycle.activate_join_tool()

        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", branch_down),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        junctions = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJunction"
        ]
        self.assertEqual(len(joints), 0)
        self.assertEqual(len(junctions), 1)
        junction = junctions[0]
        self.assertEqual(junction.Status, "OK")
        self.assertEqual(
            {wall.Name for wall in junction.Walls},
            {carrier_wall.Name, branch_up.Name, branch_down.Name},
        )
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), carrier_wall)
        self.assertGreater(len(session._junction_node_trackers), 0)

    def test_plan_edit_join_promotion_undo_redo_roundtrip(self):
        """Junction promotion should roundtrip cleanly through undo/redo."""

        carrier_wall = Arch.makeWall(length=3000, width=200, height=2500)
        carrier_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(1500, 0, 0), FreeCAD.Rotation())
        branch_up = Arch.makeWall(length=1500, width=200, height=2500)
        branch_up.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, 750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        branch_down = Arch.makeWall(length=1500, width=200, height=2500)
        branch_down.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -750, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Tee

        initial_joint = Arch.makeWallJoint(branch_up, carrier_wall, "Tee")
        self.assertIsNotNone(initial_joint)
        self.assertTrue(BIM_Join_Tee()._configure_joint(initial_joint, branch_up, carrier_wall))
        self.document.recompute()
        self.assertEqual(initial_joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(carrier_wall)
        session.lifecycle.activate_join_tool()

        from pivy import coin

        class _FakeMousePosition:
            def __init__(self, x, y):
                self._value = (x, y)

            def getValue(self):
                return self._value

        class _FakeMouseEvent:
            def __init__(self, x, y):
                self._position = _FakeMousePosition(x, y)

            def getButton(self):
                return coin.SoMouseButtonEvent.BUTTON1

            def getState(self):
                return coin.SoMouseButtonEvent.DOWN

            def getPosition(self):
                return self._position

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", branch_down),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        junctions = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJunction"
        ]
        self.assertEqual(len(joints), 0)
        self.assertEqual(len(junctions), 1)
        junction = junctions[0]
        self.assertEqual(junction.Status, "OK")
        self.assertEqual(
            {wall.Name for wall in junction.Walls},
            {carrier_wall.Name, branch_up.Name, branch_down.Name},
        )
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), carrier_wall)
        self.assertGreater(len(session._junction_node_trackers), 0)

        self._undo_document()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        junctions = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJunction"
        ]
        self.assertEqual(len(junctions), 0)
        self.assertEqual(len(joints), 1)
        joint = joints[0]
        self.assertEqual(joint.JointType, "Tee")
        self.assertEqual({joint.WallA, joint.WallB}, {branch_up, carrier_wall})
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), carrier_wall)
        self.assertEqual(len(session._junction_node_trackers), 0)

        self._redo_document()

        joints = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJoint"
        ]
        junctions = [
            obj
            for obj in self.document.Objects
            if getattr(getattr(obj, "Proxy", None), "Type", None) == "WallJunction"
        ]
        self.assertEqual(len(joints), 0)
        self.assertEqual(len(junctions), 1)
        junction = junctions[0]
        self.assertEqual(junction.Status, "OK")
        self.assertEqual(
            {wall.Name for wall in junction.Walls},
            {carrier_wall.Name, branch_up.Name, branch_down.Name},
        )
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), carrier_wall)
        self.assertGreater(len(session._junction_node_trackers), 0)

    def test_plan_edit_wall_resize_keeps_relation_status_clear_when_join_stays_resolvable(
        self,
    ):
        """Wall resize should keep relation status clear when the committed join remains valid."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(3000, -1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        original_endpoints = source_wall.Proxy.calc_endpoints(source_wall)
        new_points = [
            original_endpoints[0],
            original_endpoints[0].add(FreeCAD.Vector(1000, 0, 0)),
        ]

        session.wall_edit.commit_wall_edit_points(source_wall, "End", source_wall.Proxy, new_points)
        self.pump_gui_events()
        self.pump_gui_events()

        self.assertEqual(joint.Status, "OK")
        self.assertIsNone(session._plan_relation_status_message)
        _title, body = session._get_status_chip_text()
        self.assertNotIn("Relation warning", body)
        self.assertNotIn("Relation warning", session.task_panel.status.text())

    def test_plan_edit_joined_wall_preview_uses_trimmed_footprint(self):
        """Wall stretch preview should clip the footprint using active wall joins."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session._edit_wall = source_wall
        endpoints = source_wall.Proxy.calc_endpoints(source_wall)
        plain = session.wall_edit.get_preview_footprint(endpoints)
        polylines, warnings = session.wall_edit.get_preview_footprint_polylines(endpoints)

        self.assertEqual(warnings, [])
        self.assertEqual(len(polylines), 1)
        closed_plain = [FreeCAD.Vector(point) for point in plain]
        closed_plain.append(FreeCAD.Vector(plain[0]))
        preview = polylines[0]
        self.assertNotEqual(len(preview), 0)
        self.assertFalse(
            len(preview) == len(closed_plain)
            and all(
                preview_point.distanceToPoint(plain_point) < 1e-6
                for preview_point, plain_point in zip(preview, closed_plain)
            )
        )

    def test_plan_edit_joined_wall_preview_drops_trim_when_span_no_longer_reaches_join(self):
        """Wall stretch preview should fall back to the plain footprint when the edited span no longer reaches the join."""

        source_wall = Arch.makeWall(length=3000, width=200, height=2500)
        source_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation())
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(
            FreeCAD.Vector(1500, -1500, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90)
        )
        self.document.recompute()

        from bimcommands.BimJoin import BIM_Join_Miter

        joint = Arch.makeWallJoint(source_wall, target_wall, "Miter")
        self.assertIsNotNone(joint)
        self.assertTrue(BIM_Join_Miter()._configure_joint(joint, source_wall, target_wall))
        self.document.recompute()
        self.assertEqual(joint.Status, "OK")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.activation.select_wall_for_plan_edit(source_wall)
        original_endpoints = source_wall.Proxy.calc_endpoints(source_wall)
        session._wall_edit_modal_active = True
        session._edit_wall = source_wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"

        invalid_points = [
            original_endpoints[0],
            original_endpoints[0].add(FreeCAD.Vector(1000, 0, 0)),
        ]
        session.wall_edit.sync_wall_edit_preview(invalid_points)
        self.pump_gui_events()

        self.assertIsNone(session._plan_relation_status_message)
        plain = session.wall_edit.get_preview_footprint(invalid_points)
        polylines, warnings = session.wall_edit.get_preview_footprint_polylines(invalid_points)
        self.assertEqual(warnings, [])
        self.assertEqual(len(polylines), 1)
        closed_plain = [FreeCAD.Vector(point) for point in plain]
        closed_plain.append(FreeCAD.Vector(plain[0]))
        self.assertEqual(len(polylines[0]), len(closed_plain))
        self.assertTrue(
            all(
                preview_point.distanceToPoint(plain_point) < 1e-6
                for preview_point, plain_point in zip(polylines[0], closed_plain)
            )
        )

    def test_plan_edit_wall_grip_move_uses_point_pick_commit(self):
        """Wall grips should use click-move-click editing instead of hold-drag."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(2)

        self.assertEqual(session.current_tool, "Move Wall")
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertIn("callback", captured)
        self.assertIn("movecallback", captured)
        self.assertIn("last", captured)
        self.assertTrue(captured.get("noTracker"))

        new_midpoint = captured["last"].add(FreeCAD.Vector(1000, 0, 0))
        captured["movecallback"](new_midpoint, None)
        self.assertIsNotNone(session._preview_points)
        self.assertNotEqual(session._preview_points, list(original_endpoints))

        captured["callback"](new_midpoint, None)
        self.pump_gui_events()

        moved_endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(
            moved_endpoints[0].x - original_endpoints[0].x,
            1000.0,
            delta=1e-6,
        )
        self.assertAlmostEqual(
            moved_endpoints[1].x - original_endpoints[1].x,
            1000.0,
            delta=1e-6,
        )
        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_wall_grip_move_escape_cancels_and_keeps_selection(self):
        """Esc should cancel an active wall point-pick edit and restore wall grips."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(2)

        new_midpoint = captured["last"].add(FreeCAD.Vector(1000, 0, 0))
        captured["movecallback"](new_midpoint, None)

        from pivy import coin

        session.input.on_key_pressed(
            self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.ESCAPE))
        )
        self.pump_gui_events()

        canceled_endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(canceled_endpoints[0].x, original_endpoints[0].x, delta=1e-6)
        self.assertAlmostEqual(canceled_endpoints[1].x, original_endpoints[1].x, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._grip_trackers), 3)

    def test_plan_edit_wall_grip_activation_is_deferred(self):
        """Wall grip activation should defer point-pick start until after the click event unwinds."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        calls = []

        def fake_single_shot(delay, callback):
            calls.append((delay, callback))

        with patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot):
            session.wall_edit.activate_wall_grip(2)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 0)
        self.assertEqual(session.current_tool, "Select")

        # Late selection clears from the click should not break the deferred grip activation.
        session.selection.state.set_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            calls[0][1]()

        self.assertEqual(session.current_tool, "Move Wall")
        self._assert_selected_plan_target(session, "wall", wall)

    def test_plan_edit_clearing_wall_selection_removes_edit_nodes_from_scenegraph(self):
        """Clearing wall selection should not leave stale EditNode grips in the viewer scene graph."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session.selection.activation.select_wall_for_plan_edit(wall))
        self.pump_gui_events(timeout_ms=500)

        edit_nodes = self._get_scenegraph_edit_nodes(session)
        self.assertEqual(
            edit_nodes,
            [(wall.Name, "EditNode2"), (wall.Name, "EditNode1"), (wall.Name, "EditNode0")],
        )

        session.selection.activation.clear_plan_selection_state()
        self.pump_gui_events(timeout_ms=500)

        self.assertEqual(session.selection.state.get_selected_plan_target(), (None, None))
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertEqual(len(session._preview_grip_trackers), 0)
        self.assertEqual(self._get_scenegraph_edit_nodes(session), [])

    def test_plan_edit_gui_wall_deselection_removes_edit_nodes_from_scenegraph(self):
        """GUI deselection should not leave stale EditNode grips in the viewer scene graph."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events(timeout_ms=500)
        session.selection.refresh.refresh_primary_selected_plan_target()
        self.pump_gui_events(timeout_ms=500)

        self.assertEqual(
            self._get_scenegraph_edit_nodes(session),
            [(wall.Name, "EditNode2"), (wall.Name, "EditNode1"), (wall.Name, "EditNode0")],
        )

        FreeCADGui.Selection.clearSelection()
        self.pump_gui_events(timeout_ms=500)

        self.assertEqual(session.selection.state.get_selected_plan_target(), (None, None))
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertEqual(len(session._preview_grip_trackers), 0)
        self.assertEqual(self._get_scenegraph_edit_nodes(session), [])

    def test_plan_edit_wall_tool_activation_clears_selected_wall_edit_nodes(self):
        """Entering the embedded Wall tool should not leave selected-wall EditNode grips behind."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events(timeout_ms=500)
        session.selection.refresh.refresh_primary_selected_plan_target()
        self.pump_gui_events(timeout_ms=500)

        self.assertEqual(
            self._get_scenegraph_edit_nodes(session),
            [(wall.Name, "EditNode2"), (wall.Name, "EditNode1"), (wall.Name, "EditNode0")],
        )

        session.lifecycle.activate_wall_tool()
        self.pump_gui_events(timeout_ms=500)

        self.assertEqual(session.current_tool, "Wall")
        self.assertEqual(session.selection.state.get_selected_plan_target(), (None, None))
        self.assertEqual(len(session._grip_trackers), 0)
        self.assertEqual(self._get_scenegraph_edit_nodes(session), [])

    def test_plan_edit_wall_move_preview_shows_delta_readouts(self):
        """Moving a wall should show horizontal and vertical temporary readouts."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = original_endpoints

        moved_points = [
            original_endpoints[0].add(FreeCAD.Vector(500, 250, 0)),
            original_endpoints[1].add(FreeCAD.Vector(500, 250, 0)),
        ]

        session.wall_edit.sync_wall_edit_preview(moved_points)

        self.assertEqual(len(session._wall_edit_readout_trackers), 2)
        self.assertTrue(
            all(hasattr(tracker, "dimnode") for tracker in session._wall_edit_readout_trackers)
        )
        self.assertEqual(
            sorted(
                int(tracker.dimnode.datumtype.getValue())
                for tracker in session._wall_edit_readout_trackers
            ),
            [2, 3],
        )
        self.assertTrue(
            all(
                tracker.offset == session.wall_edit.get_wall_edit_readout_offset(tracker.mode)
                for tracker in session._wall_edit_readout_trackers
            )
        )
        self.assertTrue(
            all(tracker.offset >= 100.0 for tracker in session._wall_edit_readout_trackers)
        )

    def test_plan_edit_wall_stretch_preview_shows_length_readout(self):
        """Stretching a wall endpoint should show one aligned temporary length readout."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Align = "Center"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"

        stretched_points = [
            original_endpoints[0],
            original_endpoints[1].add(FreeCAD.Vector(800, 0, 0)),
        ]

        session.wall_edit.sync_wall_edit_preview(stretched_points)

        self.assertEqual(len(session._wall_edit_readout_trackers), 1)
        tracker = session._wall_edit_readout_trackers[0]
        self.assertTrue(hasattr(tracker, "label"))
        self.assertTrue(hasattr(tracker, "startEdit"))
        self.assertEqual(tracker.mode, 1)
        self.assertGreater(tracker.offset, wall.Width.Value / 2.0)

    def test_plan_edit_readout_offset_grows_when_zoomed_out(self):
        """Aligned readout offsets should grow when the same wall is viewed farther out."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Align = "Center"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(session.viewport, "get_plan_view_units_per_pixel", return_value=1.0):
            close_offset = session.wall_edit.get_aligned_readout_offset_for_wall(wall)

        with patch.object(session.viewport, "get_plan_view_units_per_pixel", return_value=40.0):
            far_offset = session.wall_edit.get_aligned_readout_offset_for_wall(wall)

        self.assertGreater(far_offset, close_offset)

    def test_plan_edit_ignores_deleted_view_wrappers_in_overlay_scaling(self):
        """Overlay scaling should fall back cleanly when the underlying Qt view was deleted."""

        class DeletedView:
            def __getattribute__(self, name):
                if name in ("getCameraNode", "getSize", "redraw"):
                    raise RuntimeError(f"Cannot access attribute '{name}' of deleted object")
                return object.__getattribute__(self, name)

        session = BimPlanSession.PlanEditSession()
        session.view = DeletedView()
        session.viewer = object()

        self.assertIsNone(session.viewport.get_plan_view_height())
        self.assertIsNone(session.view)
        self.assertIsNone(session.viewer)
        self.assertEqual(session.viewport.scaled_line_width(3), 3.0)

    def test_plan_edit_wall_stretch_enter_starts_length_edit(self):
        """Enter should activate in-view length editing for a wall stretch preview."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(1)

        from pivy import coin

        callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.RETURN))
        session.input.on_key_pressed(callback)
        self.pump_gui_events()

        self.assertTrue(callback._handled)
        self.assertIsNotNone(session._wall_edit_active_readout_tracker)
        self.assertTrue(session._wall_edit_active_readout_tracker.isInEdit())

    def test_plan_edit_wall_move_enter_starts_offset_edit(self):
        """Enter should activate in-view offset editing for a wall move preview."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(2)

        from pivy import coin

        callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.RETURN))
        session.input.on_key_pressed(callback)
        self.pump_gui_events()

        self.assertTrue(callback._handled)
        self.assertEqual(len(session._wall_edit_readout_trackers), 2)
        self.assertIsNotNone(session._wall_edit_active_readout_tracker)
        self.assertEqual(session._wall_edit_active_readout_tracker.mode, 2)
        self.assertTrue(session._wall_edit_active_readout_tracker.isInEdit())

    def test_plan_edit_wall_move_tab_cycles_active_offset_axis(self):
        """Tab should cycle the active in-view move offset between X and Y."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(2)

        from pivy import coin

        callback = self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.TAB))
        session.input.on_key_pressed(callback)
        self.pump_gui_events()

        self.assertTrue(callback._handled)
        self.assertIsNotNone(session._wall_edit_active_readout_tracker)
        self.assertEqual(session._wall_edit_active_readout_tracker.mode, 3)
        self.assertTrue(session._wall_edit_active_readout_tracker.isInEdit())

    def test_plan_edit_wall_stretch_length_edit_updates_preview(self):
        """Numeric wall stretch edits should drive the preview without rebuilding the label."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Stretch End"
        session.wall_edit.sync_wall_edit_preview(list(original_endpoints))

        tracker = session._wall_edit_active_readout_tracker
        self.assertIsNotNone(tracker)

        session.wall_edit.on_wall_stretch_length_changed(4200.0)

        self.assertIs(session._wall_edit_active_readout_tracker, tracker)
        self.assertAlmostEqual(session._preview_points[0].x, original_endpoints[0].x, delta=1e-6)
        self.assertAlmostEqual(
            session._preview_points[1].x, original_endpoints[0].x + 4200.0, delta=1e-6
        )

    def test_plan_edit_wall_move_offset_edit_updates_preview(self):
        """Numeric wall move edits should drive the preview without rebuilding the labels."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Move Wall"
        session.wall_edit.sync_wall_edit_preview(list(original_endpoints))

        tracker = session._wall_edit_active_readout_tracker
        self.assertIsNotNone(tracker)
        self.assertEqual(tracker.mode, 2)

        session.wall_edit.on_wall_move_delta_changed(2, 500.0)

        self.assertIs(session._wall_edit_active_readout_tracker, tracker)
        self.assertAlmostEqual(
            session._preview_points[0].x, original_endpoints[0].x + 500.0, delta=1e-6
        )
        self.assertAlmostEqual(
            session._preview_points[1].x, original_endpoints[1].x + 500.0, delta=1e-6
        )

    def test_plan_edit_wall_move_offset_edit_commits_wall(self):
        """Accepting a typed wall move offset should commit the translated wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "Move"
        session._edit_endpoints = original_endpoints
        session.current_tool = "Move Wall"
        session.wall_edit.sync_wall_edit_preview(list(original_endpoints))

        session.wall_edit.on_wall_move_delta_finished(2, 500.0)
        self.pump_gui_events()

        endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(endpoints[0].x, original_endpoints[0].x + 500.0, delta=1e-6)
        self.assertAlmostEqual(endpoints[1].x, original_endpoints[1].x + 500.0, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), wall)

    def test_plan_edit_wall_move_undo_redo_roundtrip(self):
        """Wall move undo/redo should restore wall geometry and selected-wall visuals."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        initial_start, initial_end = self._get_wall_endpoints(wall)
        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        moved_midpoint = None
        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(2)
            moved_midpoint = FreeCAD.Vector(captured["last"]).add(FreeCAD.Vector(500.0, 0.0, 0.0))
            captured["callback"](moved_midpoint, None)

        moved_start, moved_end = self._get_wall_endpoints(wall)
        self.assertAlmostEqual(moved_start.x, initial_start.x + 500.0, delta=1e-6)
        self.assertAlmostEqual(moved_end.x, initial_end.x + 500.0, delta=1e-6)
        self._assert_selected_wall_visuals(session, wall)
        self._assert_no_wall_edit_preview_visuals(session)

        self._undo_document()
        undo_start, undo_end = self._get_wall_endpoints(wall)
        self.assertLess(undo_start.distanceToPoint(initial_start), 1e-6)
        self.assertLess(undo_end.distanceToPoint(initial_end), 1e-6)
        self._assert_wall_selection_visual_consistency(session)
        self._assert_no_wall_edit_preview_visuals(session)

        self._redo_document()
        redo_start, redo_end = self._get_wall_endpoints(wall)
        self.assertLess(redo_start.distanceToPoint(moved_start), 1e-6)
        self.assertLess(redo_end.distanceToPoint(moved_end), 1e-6)
        self._assert_wall_selection_visual_consistency(session)
        self._assert_no_wall_edit_preview_visuals(session)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_wall_stretch_length_edit_commits_wall(self):
        """Accepting a typed wall stretch length should commit the resized wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(1)

        session.wall_edit.on_wall_stretch_length_finished(4200.0)
        self.pump_gui_events()

        endpoints = wall.Proxy.calc_endpoints(wall)
        self.assertAlmostEqual(endpoints[1].sub(endpoints[0]).Length, 4200.0, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), wall)

    def test_plan_edit_wall_edit_refreshes_hosted_opening_footprints(self):
        """Wall edits should refresh footprints for openings hosted by that wall."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="WallEditDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(
                session.document_visuals,
                "refresh_opening_footprint_display",
            ) as refresh_opening,
        ):
            session.wall_edit.start_wall_grip_edit(2)
            new_midpoint = captured["last"].add(FreeCAD.Vector(400, 0, 0))
            captured["callback"](new_midpoint, None)

        refresh_opening.assert_any_call(door)

    def test_plan_edit_wall_stretch_clamps_hosted_opening_inside_wall(self):
        """Shortening a wall should move hosted openings back inside the valid span."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="ClampAfterStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        door_proxy.move_along_host(rightmost)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_end = original_endpoints[0].add(axis.multiply(1600.0))

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(1)
            captured["callback"](shortened_end, None)

        updated_context = door_proxy.get_plan_move_context()
        current_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(current_center)
        current_center_u = (
            FreeCAD.Vector(current_center)
            .sub(updated_context["origin"])
            .dot(updated_context["axis_u"])
        )
        self.assertAlmostEqual(current_center_u, updated_context["move_u_max"], delta=1e-6)
        self.assertIn("callback", captured)
        self.assertIn("movecallback", captured)

    def test_plan_edit_wall_stretch_preview_shows_repositioned_opening_overlay(self):
        """Stretch preview should show hosted openings in their predicted post-resize position."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="PreviewStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        self.assertTrue(door_proxy.move_along_host(rightmost))
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        session._edit_wall = wall
        session._edit_endpoint = "End"
        session._edit_endpoints = original_endpoints
        session._wall_edit_opening_clearances = (
            session.wall_edit.snapshot_wall_hosted_opening_clearances(wall, original_endpoints)
        )
        session.current_tool = "Stretch End"

        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_points = [
            original_endpoints[0],
            original_endpoints[0].add(axis.multiply(1600.0)),
        ]

        layout = session.openings.compute_wall_hosted_opening_layout(wall, shortened_points)
        self.assertIsNotNone(layout)
        item = next(candidate for candidate in layout if candidate["opening"] is door)
        delta = FreeCAD.Vector(item["target_point"]).sub(item["current"])
        self.assertGreater(delta.Length, 1e-6)

        original_polylines = session.overlays.geometry.get_opening_overlay_polylines(door)
        self.assertTrue(original_polylines)
        first_polyline = next(polyline for polyline in original_polylines if len(polyline) >= 2)

        session.wall_edit.sync_wall_edit_preview(shortened_points)

        expected_segment_count = sum(
            max(len(polyline) - 1, 0) for polyline in original_polylines if len(polyline) >= 2
        )
        self.assertEqual(
            len(session._wall_edit_opening_preview_trackers),
            expected_segment_count,
        )

        tracker = session._wall_edit_opening_preview_trackers[0]
        expected_start = FreeCAD.Vector(first_polyline[0]).add(delta)
        expected_end = FreeCAD.Vector(first_polyline[1]).add(delta)
        self.assertLess(tracker.p1().distanceToPoint(expected_start), 1e-6)
        self.assertLess(tracker.p2().distanceToPoint(expected_end), 1e-6)

    def test_plan_edit_wall_stretch_preserves_opening_edge_clearance(self):
        """Stretching a wall endpoint should preserve existing opening edge clearance when possible."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="PreserveEdgeClearanceDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        target_center_u = 750.0
        target_point = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(target_center_u)
        )
        target_point.z = move_context["base_z"]
        self.assertTrue(door_proxy.move_along_host(target_point))
        self.document.recompute()

        initial_context = door_proxy.get_plan_move_context()
        initial_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(initial_center)
        initial_center_u = (
            FreeCAD.Vector(initial_center)
            .sub(initial_context["origin"])
            .dot(initial_context["axis_u"])
        )
        initial_left_clearance = initial_center_u - initial_context["opening_half_width_u"]
        self.assertAlmostEqual(initial_left_clearance, 300.0, delta=1e-6)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        new_start = FreeCAD.Vector(original_endpoints[0]).add(FreeCAD.Vector(200.0, 0.0, 0.0))

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(0)
            captured["callback"](new_start, None)

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_axis_u = FreeCAD.Vector(wall_end).sub(wall_start)
        self.assertGreater(wall_axis_u.Length, 0.0)
        wall_axis_u.normalize()

        updated_context = door_proxy.get_plan_move_context()
        updated_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(updated_center)
        updated_center_u = FreeCAD.Vector(updated_center).sub(wall_start).dot(wall_axis_u)
        updated_left_clearance = updated_center_u - updated_context["opening_half_width_u"]
        self.assertAlmostEqual(updated_left_clearance, initial_left_clearance, delta=1e-6)

    def test_plan_edit_wall_stretch_undo_redo_roundtrip_with_hosted_opening(self):
        """Wall stretch undo/redo should restore both wall geometry and hosted opening layout."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="UndoRedoStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        target_center_u = 750.0
        target_point = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(target_center_u)
        )
        target_point.z = move_context["base_z"]
        self.assertTrue(door_proxy.move_along_host(target_point))
        self.document.recompute()

        initial_start, initial_end = self._get_wall_endpoints(wall)
        initial_center_u, half_width = self._get_hosted_opening_center_u(door)
        initial_left_clearance = initial_center_u - half_width

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        new_start = FreeCAD.Vector(initial_start).add(FreeCAD.Vector(200.0, 0.0, 0.0))
        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(0)
            captured["callback"](new_start, None)

        updated_start, updated_end = self._get_wall_endpoints(wall)
        self.assertGreater(updated_start.distanceToPoint(initial_start), 1e-6)
        self.assertLess(updated_end.distanceToPoint(initial_end), 1e-6)
        updated_center_u, updated_half_width = self._get_hosted_opening_center_u(door)
        updated_left_clearance = updated_center_u - updated_half_width
        self.assertAlmostEqual(updated_left_clearance, initial_left_clearance, delta=1e-6)
        self._assert_selected_wall_visuals(session, wall)
        self._assert_no_wall_edit_preview_visuals(session)

        self._undo_document()
        undo_start, undo_end = self._get_wall_endpoints(wall)
        self.assertLess(undo_start.distanceToPoint(initial_start), 1e-6)
        self.assertLess(undo_end.distanceToPoint(initial_end), 1e-6)
        undo_center_u, undo_half_width = self._get_hosted_opening_center_u(door)
        self.assertAlmostEqual(undo_center_u, initial_center_u, delta=1e-6)
        self.assertAlmostEqual(undo_center_u - undo_half_width, initial_left_clearance, delta=1e-6)
        self._assert_wall_selection_visual_consistency(session)
        self._assert_no_wall_edit_preview_visuals(session)

        self._redo_document()
        redo_start, redo_end = self._get_wall_endpoints(wall)
        self.assertLess(redo_start.distanceToPoint(updated_start), 1e-6)
        self.assertLess(redo_end.distanceToPoint(updated_end), 1e-6)
        redo_center_u, redo_half_width = self._get_hosted_opening_center_u(door)
        self.assertAlmostEqual(redo_center_u, updated_center_u, delta=1e-6)
        self.assertAlmostEqual(redo_center_u - redo_half_width, updated_left_clearance, delta=1e-6)
        self._assert_wall_selection_visual_consistency(session)
        self._assert_no_wall_edit_preview_visuals(session)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_wall_stretch_keeps_opening_symbol_centered_on_slot(self):
        """Hosted opening symbols should stay centered on the actual slot after wall resize."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="CenteredAfterStretchDoor", width=900.0)
        self.document.recompute()

        door_proxy = door.ViewObject.Proxy
        move_context = door_proxy.get_plan_move_context()
        rightmost = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(move_context["move_u_max"])
        )
        rightmost.z = move_context["base_z"]
        door_proxy.move_along_host(rightmost)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_endpoints = wall.Proxy.calc_endpoints(wall)
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        shortened_end = original_endpoints[0].add(axis.multiply(1600.0))

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.wall_edit.start_wall_grip_edit(1)
            captured["callback"](shortened_end, None)

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_end = FreeCAD.Vector(wall_end)
        wall_axis_u = wall_end.sub(wall_start)
        self.assertGreater(wall_axis_u.Length, 0.0)
        wall_axis_u.normalize()

        actual_center = door_proxy.get_plan_center_point()
        self.assertIsNotNone(actual_center)
        actual_center_u = FreeCAD.Vector(actual_center).sub(wall_start).dot(wall_axis_u)
        actual_context = door_proxy.get_plan_move_context()
        self.assertIsNotNone(actual_context)

        overlay_polylines = door_proxy.get_plan_overlay_polylines()
        self.assertTrue(overlay_polylines)
        centerline = overlay_polylines[-1]
        self.assertEqual(len(centerline), 2)
        symbol_center = FreeCAD.Vector(centerline[0]).add(centerline[1]).multiply(0.5)
        symbol_center_u = symbol_center.sub(wall_start).dot(wall_axis_u)

        self.assertAlmostEqual(symbol_center_u, actual_center_u, delta=1e-6)

        wall_faces = wall.Proxy.getFootprint(wall)
        self.assertTrue(wall_faces)

        def get_u_bounds(face):
            u_values = []
            for wire in face.Wires:
                for vertex in wire.Vertexes:
                    u_values.append(vertex.Point.sub(wall_start).dot(wall_axis_u))
            return min(u_values), max(u_values)

        wall_bounds = sorted((get_u_bounds(face) for face in wall_faces), key=lambda item: item[0])
        left_jamb_u = actual_center_u - actual_context["opening_half_width_u"]
        right_jamb_u = actual_center_u + actual_context["opening_half_width_u"]

        if len(wall_bounds) == 2:
            gap_center_u = (wall_bounds[0][1] + wall_bounds[1][0]) * 0.5
            gap_width = wall_bounds[1][0] - wall_bounds[0][1]
            self.assertAlmostEqual(gap_center_u, actual_center_u, delta=1e-6)
            self.assertAlmostEqual(
                gap_width, actual_context["opening_half_width_u"] * 2.0, delta=1e-6
            )
            return

        self.assertEqual(len(wall_bounds), 1)
        single_min_u, single_max_u = wall_bounds[0]
        flush_start = (
            abs(single_min_u - right_jamb_u) < 1e-6 and abs(single_max_u - wall_length) < 1e-6
        )
        flush_end = abs(single_min_u) < 1e-6 and abs(single_max_u - left_jamb_u) < 1e-6
        self.assertTrue(flush_start or flush_end)

    def test_plan_edit_clicking_hovered_wall_reuses_hover_target_without_repick(self):
        """A hovered wall click should promote the hovered target without another pick pass."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.hover.set_hovered_wall(wall)
        session._hover_pick_last_mouse_pos = (250.0, 250.0)
        self.assertIs(session.hovered_wall, wall)

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
            ) as get_target,
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session.input.on_mouse_pressed(press)

        self.assertEqual(get_target.call_count, 0)
        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self.pump_gui_events()
        self.assertEqual(len(session._grip_trackers), 3)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [wall.Name])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_picked_wall_shows_wall_grips(self):
        """A raw wall click should leave visible wall edit grips after deferred sync."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", wall),
            ),
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session.input.on_mouse_pressed(press)

        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(len(session._grip_trackers), 0)
        self.pump_gui_events()
        self.assertEqual(len(session._grip_trackers), 3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_multi_edge_base_wall_keeps_grips_hidden(self):
        """Multi-edge base walls are selectable but do not expose endpoint grips."""

        wire = Draft.make_wire(
            [
                FreeCAD.Vector(0, 0, 0),
                FreeCAD.Vector(1500, 0, 0),
                FreeCAD.Vector(1500, 1000, 0),
            ],
            closed=False,
        )
        wall = Arch.makeWall(wire, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", wall),
            ),
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session.input.on_mouse_pressed(press)

        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertFalse(session.wall_edit.is_selected_wall_endpoint_editable())
        self.pump_gui_events()
        self.assertEqual(len(session._grip_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_click_after_skipped_hover_repicks_target(self):
        """A throttled hover must not let a stale hovered wall steal the click."""

        stale_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall = Arch.makeWall(length=3000, width=200, height=2500)
        target_wall.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 1000, 0), FreeCAD.Rotation())
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        session.selection.hover.set_hovered_wall(stale_wall)
        session._hover_pick_dirty = True

        with (
            patch.object(session.selection, "get_edit_node", return_value=None),
            patch.object(
                session.selection,
                "get_plan_target_at_position",
                return_value=("wall", target_wall),
            ) as get_target,
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session.input.on_mouse_pressed(press)

        self.assertEqual(get_target.call_count, 1)
        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", target_wall)
        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self.pump_gui_events()
        self.assertEqual(len(session._grip_trackers), 3)
        self.assertEqual(
            [obj.Name for obj in FreeCADGui.Selection.getSelection()],
            [target_wall.Name],
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_shows_grips_for_straight_base_wall(self):
        """Straight base-driven walls should get the same grip overlays as baseless walls."""

        base = Draft.make_line(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(3000, 0, 0))
        wall = Arch.makeWall(base, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, wall.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        self.assertTrue(session.wall_edit.is_selected_wall_endpoint_editable())
        self.assertEqual(len(session._grip_trackers), 3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clears_selected_wall_when_host_shape_changes(self):
        """Selected wall grips should be cleared if a hosted opening changes the wall shape."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(wall)
        self.pump_gui_events()
        self.assertIs(session.selection.state.get_selected_target_for_kind("wall"), wall)
        self.assertGreater(len(session._grip_trackers), 0)

        self._make_hosted_door(wall, name="ResetDoor")
        self.pump_gui_events()

        self.assertIsNone(session.selection.state.get_selected_target_for_kind("wall"))
        self.assertEqual(len(session._grip_trackers), 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()


class TestBimPlanEditGuiWalls(BimPlanEditGuiWallsMixin, BimPlanEditGuiBase):
    """Wall editing and join Plan Edit GUI suite."""

    pass
