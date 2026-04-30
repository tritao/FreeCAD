# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opening and window GUI tests."""

from .TestBimPlanEditGuiBase import *  # noqa: F401,F403
from .TestBimPlanEditGuiBase import BimPlanEditGuiBase


class BimPlanEditGuiOpeningsMixin:
    def test_plan_edit_forces_hosted_doors_visible(self):
        """Hosted doors should become visible in Plan Edit even if the regular 3D view keeps them hidden."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall)
        door.ViewObject.Visibility = False

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Visibility)
        self.assertFalse(door.ViewObject.Selectable)
        self.assertTrue(hasattr(door.ViewObject.Proxy, "lcoords"))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Selectable)

    def test_plan_edit_hosted_openings_are_custom_pick_only(self):
        """Hosted openings should rely on Plan Edit picking instead of native overlap selection."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="CustomPickDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Visibility)
        self.assertFalse(
            door.ViewObject.Selectable,
            "Hosted openings should be selected through Plan Edit, not native wall overlap hits.",
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

        self.assertTrue(door.ViewObject.Selectable)

    def test_plan_edit_hosted_door_populates_footprint_lines(self):
        """Hosted doors should have committed footprint line data while Plan Edit is active."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="PlanDoor")
        door.ViewObject.Visibility = False

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = door.ViewObject.Proxy
        self.assertTrue(door.ViewObject.Visibility)
        self.assertFalse(door.ViewObject.Selectable)
        self.assertTrue(hasattr(proxy, "lcoords"))
        self.assertTrue(hasattr(proxy, "lset"))
        self.assertGreater(proxy.lcoords.point.getNum(), 0)
        self.assertGreater(proxy.lset.numVertices.getNum(), 0)

    def test_plan_edit_selecting_hosted_door_does_not_enable_wall_grips(self):
        """Hosted opening selection should not re-enter wall endpoint edit mode."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="SelectableDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertFalse(door.ViewObject.Selectable)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session.overlay_tracker_state.grip_trackers), 0)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)

        self.assertEqual(len(session.opening_transient_state.opening_handle_trackers), 3)

    def test_plan_edit_window_tool_creates_hosted_window_on_selected_wall(self):
        """The Plan Edit Window tool should create a real hosted Arch Window."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        captured = {}
        prehost_window_shapes = []

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        original_add_components = Arch.addComponents

        def record_add_components(objects, host):
            window = objects[0] if isinstance(objects, list) else objects
            prehost_window_shapes.append(
                bool(
                    getattr(window, "Shape", None)
                    and not window.Shape.isNull()
                    and window.Shape.Solids
                )
            )
            return original_add_components(objects, host)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(Arch, "addComponents", side_effect=record_add_components),
        ):
            self.assertTrue(
                session.selection.activation.select_wall_for_plan_edit(
                    wall, sync_gui_selection=True
                )
            )
            self.assertTrue(session.windows.can_place_window())

            before = {obj.Name for obj in self.document.Objects}
            self.assertTrue(session.windows.activate_window_tool())
            self.assertEqual(session.current_tool, "Window")
            self.assertIs(session.creation_preview_state.window_host_wall, wall)
            self.assertIn("callback", captured)
            self.assertIn("movecallback", captured)

            point = FreeCAD.Vector(1200, 100, 0)
            captured["movecallback"](point, None)
            self.assertEqual(4, len(session.creation_preview_state.window_preview_trackers))

            captured["callback"](point, None)

        self.pump_gui_events()

        created = [obj for obj in self.document.Objects if obj.Name not in before]
        windows = [
            obj
            for obj in created
            if getattr(obj, "IfcType", "") == "Window"
            and session.openings.is_hosted_opening_object(obj)
        ]
        self.assertEqual(1, len(windows))

        window = windows[0]
        self.assertEqual([True], prehost_window_shapes)
        self.assertIn(wall, window.Hosts)
        self.assertIn(level, window.InListRecursive)
        self.assertAlmostEqual(float(getattr(window.Width, "Value", window.Width)), 900.0)
        self.assertAlmostEqual(float(getattr(window.Height, "Value", window.Height)), 1200.0)
        self.assertAlmostEqual(window.Base.getDatum("Width").Value, 900.0, delta=1e-6)
        self.assertAlmostEqual(window.Base.getDatum("Height").Value, 1200.0, delta=1e-6)
        self.assertAlmostEqual(window.Base.Placement.Base.z, 900.0, delta=1e-6)
        self.assertAlmostEqual(window.Shape.BoundBox.ZMin, 900.0, delta=1e-6)
        self.assertEqual(session.current_tool, "Select")
        self._assert_selected_plan_target(session, "opening", window)

    def test_plan_edit_window_tool_uses_current_snap_wall_for_host(self):
        """Window placement should follow the wall under the cursor, not stale selection."""

        level = Arch.makeFloor(name="Level 0")
        wall_a = Arch.makeWall(length=3000, width=200, height=2500)
        base_b = Draft.makeLine(FreeCAD.Vector(2000, 0, 0), FreeCAD.Vector(2000, 3000, 0))
        wall_b = Arch.makeWall(base_b, width=200, height=2500, name="SnapWall")
        level.addObject(wall_a)
        level.addObject(wall_b)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        captured = {}
        snap_info = {
            "Document": self.document.Name,
            "Object": wall_b.Name,
            "Component": "Face1",
            "SubName": "Face1",
        }

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.Snapper, "snapInfo", snap_info, create=True),
        ):
            self.assertTrue(
                session.selection.activation.select_wall_for_plan_edit(
                    wall_a, sync_gui_selection=True
                )
            )
            self.assertTrue(session.windows.activate_window_tool())
            self.assertIs(session.creation_preview_state.window_host_wall, wall_a)

            before = {obj.Name for obj in self.document.Objects}
            point = FreeCAD.Vector(2100, 1200, 0)
            captured["movecallback"](point, None)
            self.assertIs(session.creation_preview_state.window_host_wall, wall_b)

            captured["callback"](point, None)

        self.pump_gui_events()

        created = [obj for obj in self.document.Objects if obj.Name not in before]
        windows = [
            obj
            for obj in created
            if getattr(obj, "IfcType", "") == "Window"
            and session.openings.is_hosted_opening_object(obj)
        ]
        self.assertEqual(1, len(windows))

        window = windows[0]
        self.assertIn(wall_b, window.Hosts)
        self.assertNotIn(wall_a, window.Hosts)
        self.assertAlmostEqual(window.Base.Placement.Base.x, 2000.0, delta=1e-6)
        self.assertAlmostEqual(window.Base.Placement.Base.y, 1200.0, delta=1e-6)
        self.assertAlmostEqual(window.Base.Placement.Base.z, 900.0, delta=1e-6)

        sketch_x_axis = window.Base.Placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
        self.assertAlmostEqual(abs(sketch_x_axis.x), 0.0, delta=1e-6)
        self.assertAlmostEqual(abs(sketch_x_axis.y), 1.0, delta=1e-6)

    def test_plan_edit_shutdown_cancels_active_window_tool(self):
        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        try:
            with (
                patch.object(FreeCADGui.Snapper, "getPoint", return_value=None),
                patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            ):
                self.assertTrue(
                    session.selection.activation.select_wall_for_plan_edit(
                        wall, sync_gui_selection=True
                    )
                )
                self.assertTrue(session.windows.activate_window_tool())

            self.assertEqual("Window", session.current_tool)
            self.assertIs(session.creation_preview_state.window_host_wall, wall)

            self.assertTrue(session.shutdown(close_dialog=False))
            self.pump_gui_events()

            self.assertEqual("Select", session.current_tool)
            self.assertIsNone(session.creation_preview_state.window_host_wall)
            self.assertIsNone(session.doc)
            self.assertIsNone(BimPlanSession.get_active_session())
        finally:
            if BimPlanSession.get_active_session() is session:
                session.shutdown(close_dialog=False)
                self.pump_gui_events()

    def test_plan_edit_selected_window_status_uses_window_label(self):
        """Hosted windows should be labelled as windows, not generic openings."""

        level, wall, window = self._make_windowed_plan_wall()
        del wall

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, window.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        self._assert_selected_plan_target(session, "opening", window)
        self.assertTrue(
            session.status_text.format_plan_target_selection_state("opening", window).startswith(
                "Window:"
            )
        )
        self.assertIn("selected window", session.status_text.format_opening_selection_help(window))

    def test_plan_edit_selected_window_shows_style_editor(self):
        """Selected windows should expose preset switching in the task panel."""

        level, wall, window = self._make_windowed_plan_wall()
        del wall

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        combo = panel.window_preset_combo

        self.assertFalse(panel.window_editor.isHidden())
        self.assertIsNotNone(panel.window_width_edit)
        self.assertIsNotNone(panel.window_height_edit)
        self.assertEqual(
            session.windows.get_selected_window_width_text(), str(panel.window_width_edit.text())
        )
        self.assertEqual(
            session.windows.get_selected_window_height_text(), str(panel.window_height_edit.text())
        )
        self.assertIsNotNone(panel.window_size_apply_button)
        self.assertFalse(panel.window_size_apply_button.isEnabled())
        self.assertIsNotNone(combo)
        self.assertFalse(combo.isEditable())
        self.assertEqual("Custom / Current", str(combo.itemText(0)))
        self.assertEqual("", str(combo.itemData(0) or ""))
        self.assertEqual(
            ["Custom / Current"] + list(session.windows.get_window_style_preset_options()),
            [str(combo.itemText(index)) for index in range(combo.count())],
        )
        self.assertFalse(panel.window_preset_apply_button.isEnabled())
        self.assertIn("change its width, height, or style", panel.status.text().lower())

    def test_plan_edit_selected_window_can_change_width(self):
        """Selected windows should accept width edits without drifting their center."""

        def get_shape_center(obj):
            bound_box = obj.Shape.BoundBox
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                (float(bound_box.ZMin) + float(bound_box.ZMax)) * 0.5,
            )

        def get_shape_size(obj):
            bound_box = obj.Shape.BoundBox
            return (
                max(float(bound_box.XLength), float(bound_box.YLength)),
                float(bound_box.ZLength),
            )

        level, wall, window = self._make_windowed_plan_wall()
        original_center = get_shape_center(window.Base)
        original_width, original_height = get_shape_size(window.Base)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        panel.window_width_edit.setText("950 mm")
        self.pump_gui_events()
        self.assertTrue(panel.window_size_apply_button.isEnabled())

        panel.window_size_apply_button.click()
        self.pump_gui_events(timeout_ms=500)
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        updated_center = get_shape_center(window.Base)
        updated_width, updated_height = get_shape_size(window.Base)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(original_center.x, updated_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, updated_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, updated_center.z, delta=1e-6)
        self.assertAlmostEqual(original_width, 800.0, delta=1e-6)
        self.assertAlmostEqual(updated_width, 950.0, delta=1e-6)
        self.assertAlmostEqual(updated_height, original_height, delta=1e-6)
        self.assertAlmostEqual(
            float(getattr(window.Width, "Value", window.Width)), 950.0, delta=1e-6
        )
        self.assertEqual(
            session.windows.get_selected_window_width_text(), str(panel.window_width_edit.text())
        )
        self.assertFalse(panel.window_size_apply_button.isEnabled())

    def test_plan_edit_selected_window_width_undo_redo_roundtrip(self):
        """Width edits should roundtrip cleanly through undo/redo."""

        def get_shape_center(obj):
            bound_box = obj.Shape.BoundBox
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                (float(bound_box.ZMin) + float(bound_box.ZMax)) * 0.5,
            )

        level, wall, window = self._make_windowed_plan_wall()
        original_center = get_shape_center(window.Base)
        original_width = ArchWindow.getWindowWidthMm(window)
        original_height = ArchWindow.getWindowHeightMm(window)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        panel.window_width_edit.setText("950 mm")
        self.pump_gui_events()
        self.assertTrue(panel.window_size_apply_button.isEnabled())

        panel.window_size_apply_button.click()
        self.pump_gui_events(timeout_ms=500)
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        updated_center = get_shape_center(window.Base)
        updated_width = ArchWindow.getWindowWidthMm(window)
        updated_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(updated_width, 950.0, delta=1e-6)
        self.assertAlmostEqual(updated_height, original_height, delta=1e-6)
        self.assertAlmostEqual(original_center.x, updated_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, updated_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, updated_center.z, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

        self._undo_document()
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        undo_center = get_shape_center(window.Base)
        undo_width = ArchWindow.getWindowWidthMm(window)
        undo_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(undo_width, original_width, delta=1e-6)
        self.assertAlmostEqual(undo_height, original_height, delta=1e-6)
        self.assertAlmostEqual(original_center.x, undo_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, undo_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, undo_center.z, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

        self._redo_document()
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        redo_center = get_shape_center(window.Base)
        redo_width = ArchWindow.getWindowWidthMm(window)
        redo_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(redo_width, updated_width, delta=1e-6)
        self.assertAlmostEqual(redo_height, updated_height, delta=1e-6)
        self.assertAlmostEqual(updated_center.x, redo_center.x, delta=1e-6)
        self.assertAlmostEqual(updated_center.y, redo_center.y, delta=1e-6)
        self.assertAlmostEqual(updated_center.z, redo_center.z, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

    def test_plan_edit_selected_window_can_change_height(self):
        """Selected windows should accept height edits without drifting their center."""

        def get_shape_center(obj):
            bound_box = obj.Shape.BoundBox
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                (float(bound_box.ZMin) + float(bound_box.ZMax)) * 0.5,
            )

        level, wall, window = self._make_windowed_plan_wall()
        original_center = get_shape_center(window.Base)
        original_width = ArchWindow.getWindowWidthMm(window)
        original_height = ArchWindow.getWindowHeightMm(window)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        panel.window_height_edit.setText("1400 mm")
        self.pump_gui_events()
        self.assertTrue(panel.window_size_apply_button.isEnabled())

        panel.window_size_apply_button.click()
        self.pump_gui_events(timeout_ms=500)
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        updated_center = get_shape_center(window.Base)
        updated_width = ArchWindow.getWindowWidthMm(window)
        updated_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(original_center.x, updated_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, updated_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, updated_center.z, delta=1e-6)
        self.assertAlmostEqual(original_width, 800.0, delta=1e-6)
        self.assertAlmostEqual(original_height, 1200.0, delta=1e-6)
        self.assertAlmostEqual(updated_width, original_width, delta=1e-6)
        self.assertAlmostEqual(updated_height, 1400.0, delta=1e-6)
        self.assertAlmostEqual(
            float(getattr(window.Height, "Value", window.Height)), 1400.0, delta=1e-6
        )
        self.assertEqual(
            session.windows.get_selected_window_height_text(), str(panel.window_height_edit.text())
        )
        self.assertFalse(panel.window_size_apply_button.isEnabled())

    def test_plan_edit_selected_window_height_undo_redo_roundtrip(self):
        """Height edits should roundtrip cleanly through undo/redo."""

        def get_shape_center(obj):
            bound_box = obj.Shape.BoundBox
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                (float(bound_box.ZMin) + float(bound_box.ZMax)) * 0.5,
            )

        level, wall, window = self._make_windowed_plan_wall()
        original_center = get_shape_center(window.Base)
        original_width = ArchWindow.getWindowWidthMm(window)
        original_height = ArchWindow.getWindowHeightMm(window)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        panel.window_height_edit.setText("1400 mm")
        self.pump_gui_events()
        self.assertTrue(panel.window_size_apply_button.isEnabled())

        panel.window_size_apply_button.click()
        self.pump_gui_events(timeout_ms=500)
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        updated_center = get_shape_center(window.Base)
        updated_width = ArchWindow.getWindowWidthMm(window)
        updated_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(updated_width, original_width, delta=1e-6)
        self.assertAlmostEqual(updated_height, 1400.0, delta=1e-6)
        self.assertAlmostEqual(original_center.x, updated_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, updated_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, updated_center.z, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

        self._undo_document()
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        undo_center = get_shape_center(window.Base)
        undo_width = ArchWindow.getWindowWidthMm(window)
        undo_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(undo_width, original_width, delta=1e-6)
        self.assertAlmostEqual(undo_height, original_height, delta=1e-6)
        self.assertAlmostEqual(original_center.x, undo_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, undo_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, undo_center.z, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

        self._redo_document()
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        redo_center = get_shape_center(window.Base)
        redo_width = ArchWindow.getWindowWidthMm(window)
        redo_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(redo_width, updated_width, delta=1e-6)
        self.assertAlmostEqual(redo_height, updated_height, delta=1e-6)
        self.assertAlmostEqual(updated_center.x, redo_center.x, delta=1e-6)
        self.assertAlmostEqual(updated_center.y, redo_center.y, delta=1e-6)
        self.assertAlmostEqual(updated_center.z, redo_center.z, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

    def test_plan_edit_selected_window_can_change_size_together(self):
        """Selected windows should apply width and height changes in one step."""

        def get_shape_center(obj):
            bound_box = obj.Shape.BoundBox
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                (float(bound_box.ZMin) + float(bound_box.ZMax)) * 0.5,
            )

        level, wall, window = self._make_windowed_plan_wall()
        original_center = get_shape_center(window.Base)
        original_width = ArchWindow.getWindowWidthMm(window)
        original_height = ArchWindow.getWindowHeightMm(window)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        panel.window_width_edit.setText("950 mm")
        panel.window_height_edit.setText("1400 mm")
        self.pump_gui_events()
        self.assertTrue(panel.window_size_apply_button.isEnabled())

        panel.window_size_apply_button.click()
        self.pump_gui_events(timeout_ms=500)
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        updated_center = get_shape_center(window.Base)
        updated_width = ArchWindow.getWindowWidthMm(window)
        updated_height = ArchWindow.getWindowHeightMm(window)
        self.assertIn(wall, window.Hosts)
        self.assertAlmostEqual(original_center.x, updated_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, updated_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, updated_center.z, delta=1e-6)
        self.assertAlmostEqual(original_width, 800.0, delta=1e-6)
        self.assertAlmostEqual(original_height, 1200.0, delta=1e-6)
        self.assertAlmostEqual(updated_width, 950.0, delta=1e-6)
        self.assertAlmostEqual(updated_height, 1400.0, delta=1e-6)
        self.assertAlmostEqual(
            float(getattr(window.Width, "Value", window.Width)), 950.0, delta=1e-6
        )
        self.assertAlmostEqual(
            float(getattr(window.Height, "Value", window.Height)), 1400.0, delta=1e-6
        )
        self.assertEqual(
            session.windows.get_selected_window_width_text(), str(panel.window_width_edit.text())
        )
        self.assertEqual(
            session.windows.get_selected_window_height_text(), str(panel.window_height_edit.text())
        )
        self.assertFalse(panel.window_size_apply_button.isEnabled())

    def test_plan_edit_selected_window_can_apply_built_in_style_preset(self):
        """Selected windows should accept built-in preset rewrites without drifting."""

        from ArchWindowPresets import WindowPresets

        def get_shape_center(obj):
            bound_box = obj.Shape.BoundBox
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                (float(bound_box.ZMin) + float(bound_box.ZMax)) * 0.5,
            )

        def get_shape_size(obj):
            bound_box = obj.Shape.BoundBox
            return (
                max(float(bound_box.XLength), float(bound_box.YLength)),
                float(bound_box.ZLength),
            )

        level, wall, window = self._make_windowed_plan_wall()
        original_parts = list(window.WindowParts)
        original_center = get_shape_center(window.Base)
        original_width, original_height = get_shape_size(window.Base)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        combo = panel.window_preset_combo
        target_style = "Sliding 2-pane"
        target_index = combo.findText(target_style)

        self.assertGreaterEqual(target_index, 0)
        combo.setCurrentIndex(target_index)
        self.pump_gui_events()
        self.assertTrue(panel.window_preset_apply_button.isEnabled())

        panel.window_preset_apply_button.click()
        self.pump_gui_events(timeout_ms=500)
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        self.assertIn(wall, window.Hosts)
        self.assertEqual(
            WindowPresets.index(target_style) + 1, int(getattr(window, "Preset", 0) or 0)
        )
        self.assertEqual(target_style, session.windows.get_selected_window_style_preset())
        self.assertNotEqual(original_parts, list(window.WindowParts))
        updated_center = get_shape_center(window.Base)
        self.assertAlmostEqual(original_center.x, updated_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, updated_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, updated_center.z, delta=1e-6)
        self.assertAlmostEqual(
            original_width,
            max(
                float(window.Base.Shape.BoundBox.XLength), float(window.Base.Shape.BoundBox.YLength)
            ),
            delta=1e-6,
        )
        self.assertAlmostEqual(
            original_height,
            float(window.Base.Shape.BoundBox.ZLength),
            delta=1e-6,
        )
        self.assertAlmostEqual(
            original_width, float(getattr(window.Width, "Value", window.Width)), delta=1e-6
        )
        self.assertAlmostEqual(
            original_height,
            float(getattr(window.Height, "Value", window.Height)),
            delta=1e-6,
        )
        self.assertEqual(target_style, str(panel.window_preset_combo.currentText()))
        self.assertFalse(panel.window_preset_apply_button.isEnabled())

    def test_plan_edit_selected_window_preset_undo_redo_roundtrip(self):
        """Built-in window preset rewrites should roundtrip cleanly through undo/redo."""

        from ArchWindowPresets import WindowPresets

        def get_shape_center(obj):
            bound_box = obj.Shape.BoundBox
            return FreeCAD.Vector(
                (float(bound_box.XMin) + float(bound_box.XMax)) * 0.5,
                (float(bound_box.YMin) + float(bound_box.YMax)) * 0.5,
                (float(bound_box.ZMin) + float(bound_box.ZMax)) * 0.5,
            )

        def get_shape_size(obj):
            bound_box = obj.Shape.BoundBox
            return (
                max(float(bound_box.XLength), float(bound_box.YLength)),
                float(bound_box.ZLength),
            )

        level, wall, window = self._make_windowed_plan_wall()
        original_parts = list(window.WindowParts)
        original_preset = int(getattr(window, "Preset", 0) or 0)
        original_center = get_shape_center(window.Base)
        original_width, original_height = get_shape_size(window.Base)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        combo = panel.window_preset_combo
        target_style = "Sliding 2-pane"
        target_index = combo.findText(target_style)

        self.assertGreaterEqual(target_index, 0)
        combo.setCurrentIndex(target_index)
        self.pump_gui_events()
        self.assertTrue(panel.window_preset_apply_button.isEnabled())

        panel.window_preset_apply_button.click()
        self.pump_gui_events(timeout_ms=500)
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        updated_parts = list(window.WindowParts)
        updated_center = get_shape_center(window.Base)
        updated_width, updated_height = get_shape_size(window.Base)
        updated_preset = int(getattr(window, "Preset", 0) or 0)

        self.assertIn(wall, window.Hosts)
        self.assertNotEqual(original_parts, updated_parts)
        self.assertNotEqual(original_preset, updated_preset)
        self.assertEqual(WindowPresets.index(target_style) + 1, updated_preset)
        self.assertEqual(target_style, session.windows.get_selected_window_style_preset())
        self.assertAlmostEqual(original_center.x, updated_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, updated_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, updated_center.z, delta=1e-6)
        self.assertAlmostEqual(original_width, updated_width, delta=1e-6)
        self.assertAlmostEqual(original_height, updated_height, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

        self._undo_document()
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        self.assertIn(wall, window.Hosts)
        self.assertEqual(original_parts, list(window.WindowParts))
        self.assertEqual(original_preset, int(getattr(window, "Preset", 0) or 0))
        restored_center = get_shape_center(window.Base)
        restored_width, restored_height = get_shape_size(window.Base)
        self.assertAlmostEqual(original_center.x, restored_center.x, delta=1e-6)
        self.assertAlmostEqual(original_center.y, restored_center.y, delta=1e-6)
        self.assertAlmostEqual(original_center.z, restored_center.z, delta=1e-6)
        self.assertAlmostEqual(original_width, restored_width, delta=1e-6)
        self.assertAlmostEqual(original_height, restored_height, delta=1e-6)
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

        self._redo_document()
        panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        self.assertIn(wall, window.Hosts)
        self.assertEqual(updated_parts, list(window.WindowParts))
        self.assertEqual(updated_preset, int(getattr(window, "Preset", 0) or 0))
        redone_center = get_shape_center(window.Base)
        redone_width, redone_height = get_shape_size(window.Base)
        self.assertAlmostEqual(updated_center.x, redone_center.x, delta=1e-6)
        self.assertAlmostEqual(updated_center.y, redone_center.y, delta=1e-6)
        self.assertAlmostEqual(updated_center.z, redone_center.z, delta=1e-6)
        self.assertAlmostEqual(updated_width, redone_width, delta=1e-6)
        self.assertAlmostEqual(updated_height, redone_height, delta=1e-6)
        self.assertEqual(target_style, session.windows.get_selected_window_style_preset())
        self.assertIs(session.selection.state.get_selected_target_for_kind("opening"), window)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertGreaterEqual(len(session.opening_transient_state.opening_handle_trackers), 1)
        self._assert_no_opening_move_preview_visuals(session)

    def test_plan_edit_selected_window_shows_contextual_window_guidance(self):
        """Selected hosted windows should contribute BIM window guidance."""

        from PySide import QtGui

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        level, wall, window = self._make_windowed_plan_wall()
        del wall

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_opening_for_plan_edit(
                window, sync_gui_selection=True
            )
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        panel = session.task_panel
        self.assertFalse(panel.integration_panel.isHidden())
        labels = [
            str(widget.text()) for widget in panel.integration_panel.findChildren(QtGui.QLabel)
        ]
        self.assertTrue(any("BIM Windows: Window" in text for text in labels))
        self.assertTrue(any("Host wall:" in text for text in labels))
        self.assertTrue(any("Status: hosted" in text for text in labels))

        buttons = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QPushButton)
            if str(widget.text()) in {"Recompute host", "Select host wall", "Center on host"}
        ]
        self.assertEqual(3, len(buttons))

    def test_plan_edit_selected_wall_shows_contextual_window_markers(self):
        """Selected walls should expose hosted windows through provider overlays."""

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        level, wall, window = self._make_windowed_plan_wall()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_wall_for_plan_edit(wall, sync_gui_selection=True)
        )
        session.task_panel.refresh_from_session()
        self.pump_gui_events(timeout_ms=500)

        overlays = [
            overlay
            for overlay in session.providers.runtime.get_plan_provider_overlays()
            if getattr(overlay, "provider_id", "") == "bim-window"
        ]
        self.assertEqual(1, len(overlays))
        self.assertEqual("Hosted windows", overlays[0].label)
        self.assertEqual(1, len(overlays[0].points))
        self.assertEqual(1, len(overlays[0].point_targets))
        self.assertEqual(window.Name, overlays[0].point_targets[0].object_name)
        self.assertEqual(
            PlanOverlayTargetKind.OPENING,
            overlays[0].point_targets[0].target_kind,
        )

    def test_plan_edit_hovered_hosted_door_shows_preselection_overlay(self):
        """Hosted openings should get a hover overlay independent of global preselection."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="HoverDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.picking,
            "pick",
            return_value=("opening", door),
        ):
            session.picking.hover((100, 100))

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session.overlay_tracker_state.opening_hover_trackers), 0)
        self.assertEqual(len(session.opening_transient_state.opening_handle_trackers), 0)

    def test_plan_edit_clicking_hovered_hosted_door_selects_it(self):
        """Clicking a hovered hosted opening should promote it to selected opening state."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClickHoverDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.picking,
            "pick",
            return_value=("opening", door),
        ):
            activated = session.selection.activation.activate_opening_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session.overlay_tracker_state.grip_trackers), 0)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertEqual(len(session.opening_transient_state.opening_handle_trackers), 3)

    def test_plan_edit_real_view_picking_hover_and_click_hosted_door(self):
        """Real view-based hover and click should pick a hosted opening."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="RealPickDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = getattr(door.ViewObject, "Proxy", None)
        self.assertIsNotNone(proxy)
        projected_polylines = list(
            session.overlays.geometry.get_opening_overlay_screen_polylines(door) or []
        )
        self.assertTrue(projected_polylines)
        self.assertGreaterEqual(len(projected_polylines[0]), 2)

        start = projected_polylines[0][0]
        end = projected_polylines[0][1]
        mouse_pos = (
            int((float(start[0]) + float(end[0])) * 0.5),
            int((float(start[1]) + float(end[1])) * 0.5),
        )

        move = self._make_fake_mouse_move_event(*mouse_pos)
        session.input.on_mouse_moved(move)
        self.pump_gui_events()

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session.overlay_tracker_state.opening_hover_trackers), 0)

        move_again = self._make_fake_mouse_move_event(*mouse_pos)
        session.input.on_mouse_moved(move_again)
        self.pump_gui_events()

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session.overlay_tracker_state.opening_hover_trackers), 0)

        press = self._make_fake_left_mouse_press(*mouse_pos)
        session.input.on_mouse_pressed(press)
        self.pump_gui_events()

        release = self._make_fake_left_mouse_release(*mouse_pos)
        session.input.on_mouse_pressed(release)
        self.pump_gui_events()

        self.assertTrue(press._handled)
        self.assertTrue(release._handled)
        self.assertFalse(session.input_event_state.consume_left_button_release)
        self._assert_selected_plan_target(session, "opening", door)
        self.assertEqual(len(session.overlay_tracker_state.grip_trackers), 0)
        self.assertGreater(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertEqual(len(session.opening_transient_state.opening_handle_trackers), 3)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_opening_overlay_geometry_separates_symbol_and_guides(self):
        """Hovered openings should render only symbol geometry while selection keeps guides."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="OverlayGeometryDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = getattr(door.ViewObject, "Proxy", None)
        self.assertIsNotNone(proxy)

        overlay_geometry = proxy.get_plan_overlay_geometry()
        symbol_polylines = tuple(overlay_geometry.get("symbol_polylines", ()))
        guide_polylines = tuple(overlay_geometry.get("guide_polylines", ()))
        self.assertEqual(len(symbol_polylines), 3)
        self.assertEqual(len(guide_polylines), 1)

        symbol_segments = sum(max(len(polyline) - 1, 0) for polyline in symbol_polylines)
        combined_segments = sum(
            max(len(polyline) - 1, 0)
            for polyline in tuple(proxy.get_plan_overlay_polylines() or ())
        )
        self.assertEqual(combined_segments, symbol_segments + 1)

        session.selection.hover.set_hovered_opening(door)
        self.pump_gui_events()
        self.assertEqual(len(session.overlay_tracker_state.opening_hover_trackers), symbol_segments)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()
        self.assertEqual(
            len(session.overlay_tracker_state.opening_overlay_trackers), combined_segments
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_empty_canvas_click_clears_selected_opening(self):
        """Empty canvas clicks should clear an internally selected opening."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClearRestoreDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        calls = []

        def fake_single_shot(delay, callback):
            calls.append((delay, callback))

        with (
            patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot),
            patch.object(
                session.picking,
                "pick",
                return_value=("opening", door),
            ),
        ):
            activated = session.selection.activation.activate_opening_target((100, 100))

        self.assertTrue(activated)
        self._assert_selected_plan_target(session, "opening", door)
        restore_calls = [
            call
            for call in calls
            if call[0] == 0 and getattr(call[1], "__name__", "") == "<lambda>"
        ]
        self.assertGreaterEqual(len(restore_calls), 1)
        self.assertEqual(session.selection_state.pending_selected_plan_target, ("opening", door))

        restore_calls[0][1]()
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])

        FreeCADGui.Selection.clearSelection()
        self.pump_gui_events()

        self.assertEqual(FreeCADGui.Selection.getSelection(), [])
        self._assert_selected_plan_target(session, "opening", door)
        self.assertIsNone(session.selection_state.pending_selected_plan_target)

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
            patch.object(session.picking, "pick_edit_node", return_value=None),
            patch.object(
                session.picking,
                "pick",
                return_value=(None, None),
            ),
        ):
            session.input.on_mouse_pressed(self._FakeEventCallback(_FakeMouseEvent(250, 250)))

        self.pump_gui_events()
        self._assert_no_selected_plan_target(session)
        self.assertIsNone(session.selection_state.pending_selected_plan_target)
        self.assertEqual(len(session.overlay_tracker_state.opening_overlay_trackers), 0)
        self.assertEqual(len(session.opening_transient_state.opening_handle_trackers), 0)

    def test_plan_edit_opening_move_uses_reduced_snap_profile(self):
        """Opening move should use a constrained snap profile while point-picking."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="MoveDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        handle = session.openings.get_selected_opening_edit_handles(door)[0]
        captured = {}
        pushed_modes = []
        popped = []

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(
                FreeCADGui.Snapper,
                "push_snap_modes",
                side_effect=lambda modes: pushed_modes.append(set(modes)),
            ),
            patch.object(
                FreeCADGui.Snapper, "pop_snap_modes", side_effect=lambda: popped.append(True)
            ),
        ):
            session.openings.start_opening_handle_point_pick(door, 0, handle)

            self.assertEqual(pushed_modes, [set(BimPlanSession._OPENING_MOVE_SNAP_SET)])
            self.assertEqual(session.current_tool, "Move Opening")
            self.assertIn("callback", captured)
            self.assertIn("movecallback", captured)
            self.assertIn("last", captured)
            self.assertTrue(captured.get("noTracker"))

            captured["callback"](handle.point, None)

        self.assertEqual(len(popped), 1)
        self.assertEqual(session.current_tool, "Select")

    def test_plan_edit_opening_move_clamps_to_host_span(self):
        """Opening move projection should stay within the valid host wall span."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ClampedDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        origin = context["origin"]
        axis_u = context["axis_u"]
        far_before = origin.add(FreeCAD.Vector(axis_u).multiply(-100000))
        far_after = origin.add(FreeCAD.Vector(axis_u).multiply(100000))

        projected_before = proxy.project_point_to_host_axis(far_before)
        projected_after = proxy.project_point_to_host_axis(far_after)

        before_u = projected_before.sub(origin).dot(axis_u)
        after_u = projected_after.sub(origin).dot(axis_u)

        self.assertAlmostEqual(before_u, context["move_u_min"], delta=1e-6)
        self.assertAlmostEqual(after_u, context["move_u_max"], delta=1e-6)

    def test_plan_edit_opening_move_anchor_offsets_center_from_edge_alignment(self):
        """Opening move anchors should offset the center from left/right jamb picks."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="AnchoredDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        origin = context["origin"]
        axis_u = context["axis_u"]
        center_u = (context["move_u_min"] + context["move_u_max"]) * 0.5
        half_width = context["opening_half_width_u"]

        left_edge_point = origin.add(FreeCAD.Vector(axis_u).multiply(center_u - half_width))
        right_edge_point = origin.add(FreeCAD.Vector(axis_u).multiply(center_u + half_width))

        projected_left = proxy.project_point_to_host_axis(left_edge_point, anchor="left")
        projected_right = proxy.project_point_to_host_axis(right_edge_point, anchor="right")

        projected_left_u = projected_left.sub(origin).dot(axis_u)
        projected_right_u = projected_right.sub(origin).dot(axis_u)

        self.assertAlmostEqual(projected_left_u, center_u, delta=1e-6)
        self.assertAlmostEqual(projected_right_u, center_u, delta=1e-6)

    def test_plan_edit_opening_overlay_stays_within_wall_span_at_limit(self):
        """Hosted opening overlay should stay inside the host wall span at the move limit."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="BoundedSymbolDoor", width=900.0)
        self.document.recompute()

        proxy = door.ViewObject.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        left_limit = context["origin"].add(
            FreeCAD.Vector(context["axis_u"]).multiply(context["move_u_min"])
        )
        left_limit.z = context["base_z"]
        proxy.move_along_host(left_limit)
        self.document.recompute()

        wall_start, wall_end = wall.Proxy.calc_endpoints(wall)
        wall_start = FreeCAD.Vector(wall_start)
        wall_end = FreeCAD.Vector(wall_end)
        wall_axis_u = wall_end.sub(wall_start)
        wall_length = wall_axis_u.Length
        self.assertGreater(wall_length, 0.0)
        wall_axis_u.normalize()

        overlay_us = []
        for polyline in proxy.get_plan_overlay_polylines():
            for point in polyline:
                overlay_us.append(FreeCAD.Vector(point).sub(wall_start).dot(wall_axis_u))

        self.assertTrue(overlay_us)
        self.assertGreaterEqual(min(overlay_us), -1e-6)
        self.assertLessEqual(max(overlay_us), wall_length + 1e-6)

    def test_plan_edit_opening_move_a_cycles_anchor(self):
        """A should cycle opening move anchors while the point-pick is active."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="TabDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        handle = session.openings.get_selected_opening_edit_handles(door)[0]

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", return_value=None),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(
                session.openings,
                "refresh_opening_move_preview_from_raw_point",
                return_value=None,
            ) as refresh_preview,
        ):
            session.openings.start_opening_handle_point_pick(door, 0, handle)

            from pivy import coin

            session.input.on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.A))
            )
            self.assertEqual(session.opening_transient_state.edit_opening_move_anchor, "left")

            session.input.on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.A))
            )
            self.assertEqual(session.opening_transient_state.edit_opening_move_anchor, "right")

            session.input.on_key_pressed(
                self._FakeEventCallback(self._FakeKeyEvent(coin.SoKeyboardEvent.A))
            )
            self.assertEqual(session.opening_transient_state.edit_opening_move_anchor, "center")

            self.assertEqual(refresh_preview.call_count, 3)

            session.openings.cancel_opening_handle_point_pick()

    def test_plan_edit_opening_move_undo_redo_roundtrip(self):
        """Opening move undo/redo should restore hosted opening layout and selected-opening visuals."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="UndoRedoOpeningMoveDoor", width=900.0)
        self.document.recompute()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        initial_center_u, initial_half_width = self._get_hosted_opening_center_u(door)
        handle = session.openings.get_selected_opening_edit_handles(door)[0]
        move_context = door.ViewObject.Proxy.get_plan_move_context()
        target_center_u = min(move_context["move_u_max"], initial_center_u + 450.0)
        target_point = move_context["origin"].add(
            FreeCAD.Vector(move_context["axis_u"]).multiply(target_center_u)
        )
        target_point.z = move_context["base_z"]
        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.openings.start_opening_handle_point_pick(door, 0, handle)
            captured["callback"](target_point, None)

        self.pump_gui_events()

        updated_center_u, updated_half_width = self._get_hosted_opening_center_u(door)
        self.assertGreater(abs(updated_center_u - initial_center_u), 1e-6)
        self.assertAlmostEqual(updated_half_width, initial_half_width, delta=1e-6)
        self._assert_selected_opening_visuals(session, door)
        self._assert_no_opening_move_preview_visuals(session)

        self._undo_document()
        undo_center_u, undo_half_width = self._get_hosted_opening_center_u(door)
        self.assertAlmostEqual(undo_center_u, initial_center_u, delta=1e-6)
        self.assertAlmostEqual(undo_half_width, initial_half_width, delta=1e-6)
        self._assert_opening_selection_visual_consistency(session)
        self._assert_no_opening_move_preview_visuals(session)

        self._redo_document()
        redo_center_u, redo_half_width = self._get_hosted_opening_center_u(door)
        self.assertAlmostEqual(redo_center_u, updated_center_u, delta=1e-6)
        self.assertAlmostEqual(redo_half_width, updated_half_width, delta=1e-6)
        self._assert_opening_selection_visual_consistency(session)
        self._assert_no_opening_move_preview_visuals(session)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_opening_move_updates_input_hints(self):
        """Active opening move should publish placement/cancel/anchor hints."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="HintDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        handle = session.openings.get_selected_opening_edit_handles(door)[0]

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", return_value=None),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.HintManager, "show") as show_hints,
        ):
            session.openings.start_opening_handle_point_pick(door, 0, handle)

        self.assertTrue(show_hints.called)
        hints = show_hints.call_args.args
        self.assertEqual(len(hints), 3)
        self.assertEqual(hints[0].message, "%1 place opening")
        self.assertEqual(hints[1].message, "%1 cycle move anchor")
        self.assertEqual(hints[2].message, "%1 cancel")

    def test_plan_edit_shutdown_cancels_active_opening_move(self):
        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="ShutdownOpeningMoveDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        handle = session.openings.get_selected_opening_edit_handles(door)[0]
        pushed_modes = []

        try:
            with (
                patch.object(FreeCADGui.Snapper, "getPoint", return_value=None),
                patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
                patch.object(
                    FreeCADGui.Snapper,
                    "push_snap_modes",
                    side_effect=lambda modes: pushed_modes.append(set(modes)),
                ),
            ):
                session.openings.start_opening_handle_point_pick(door, 0, handle)
                self.assertEqual("Move Opening", session.current_tool)
                self.assertIs(session.interaction_state.edit_opening, door)

                self.assertTrue(session.shutdown(close_dialog=False))
                self.pump_gui_events()

            self.assertEqual([set(BimPlanSession._OPENING_MOVE_SNAP_SET)], pushed_modes)
            self.assertEqual("Select", session.current_tool)
            self.assertIsNone(session.interaction_state.edit_opening)
            self.assertIsNone(session.interaction_state.edit_opening_handle_index)
            self.assertIsNone(session.opening_transient_state.edit_opening_move_raw_point)
            self.assertFalse(session.opening_transient_state.opening_move_snap_profile_pushed)
            self.assertEqual("center", session.opening_transient_state.edit_opening_move_anchor)
            self.assertIsNone(session.doc)
            self.assertIsNone(BimPlanSession.get_active_session())
        finally:
            if BimPlanSession.get_active_session() is session:
                session.shutdown(close_dialog=False)
                self.pump_gui_events()

    def test_plan_edit_opening_move_preview_offsets_readout_outside_host_wall(self):
        """Opening move preview readout should sit outside the host wall footprint."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        wall.Align = "Center"
        self.document.recompute()

        door = self._make_hosted_door(wall, name="OpeningPreviewOffsetDoor")
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        proxy = door.Proxy
        context = proxy.get_plan_move_context()
        self.assertIsNotNone(context)

        preview_point = context["origin"].add(
            FreeCAD.Vector(context["axis_u"]).multiply(context["move_u_max"])
        )
        preview_point.z = context["base_z"]

        session.current_tool = "Move Opening"
        session.opening_transient_state.edit_opening_move_anchor = "center"
        session.openings.sync_opening_move_preview(door, preview_point)

        dim_trackers = [
            tracker
            for tracker in session.opening_transient_state.opening_move_preview_trackers
            if hasattr(tracker, "dimnode") and hasattr(tracker, "offset")
        ]
        self.assertEqual(len(dim_trackers), 1)
        self.assertGreater(dim_trackers[0].offset, wall.Width.Value / 2.0)

    def test_plan_edit_opening_handle_activation_is_deferred(self):
        """Deferred opening handle activation should survive late selection clears."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="DeferredDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        handle = session.openings.get_selected_opening_edit_handles(door)[0]
        calls = []

        def fake_single_shot(delay, callback):
            calls.append((delay, callback))

        with patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot):
            session.openings.activate_opening_handle(door, 0)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 0)
        session.selection.state.set_selected_plan_target()

        if handle.interaction == "point_pick":
            captured = {}

            def fake_get_point(**kwargs):
                captured.update(kwargs)

            with (
                patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
                patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            ):
                calls[0][1]()

            self.assertEqual(session.current_tool, "Move Opening")
            self._assert_selected_plan_target(session, "opening", door)
            self.assertIs(session.interaction_state.edit_opening, door)
            self.assertIn("callback", captured)
        else:
            original_parts = list(door.WindowParts)
            calls[0][1]()
            self._assert_selected_plan_target(session, "opening", door)
            self.assertNotEqual(original_parts, list(door.WindowParts))

    def test_plan_edit_stale_opening_restore_does_not_resume_newer_edit(self):
        """A queued opening restore must not override a newer opening edit session."""

        wall = Arch.makeWall(length=4000, width=200, height=2500)
        self.document.recompute()

        door_a = self._make_hosted_door(wall, name="RestoreDoorA")
        door_b = self._make_hosted_door(wall, name="RestoreDoorB")
        door_b.Placement.Base = FreeCAD.Vector(1800, 0, 0)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        queued_callbacks = []

        def fake_single_shot(delay, callback):
            self.assertEqual(delay, 0)
            queued_callbacks.append(callback)

        with patch("PySide.QtCore.QTimer.singleShot", side_effect=fake_single_shot):
            session.openings.queue_restore_selected_opening(door_a)

        self.assertEqual(len(queued_callbacks), 1)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", return_value=None),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
        ):
            session.openings.activate_opening_handle_now(door_b, 0)

        self.assertEqual(session.current_tool, "Move Opening")
        self.assertIs(session.interaction_state.edit_opening, door_b)
        self._assert_selected_plan_target(session, "opening", door_b)

        queued_callbacks[0]()

        self.assertEqual(session.current_tool, "Move Opening")
        self.assertIs(session.interaction_state.edit_opening, door_b)
        self._assert_selected_plan_target(session, "opening", door_b)

    def test_plan_edit_hovered_opening_replaces_selected_wall_context_overlay(self):
        """Hovered openings should not be hidden by selected-wall context overlays."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="HoverContextDoor")

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session.selection.activation.select_wall_for_plan_edit(wall))
        self.assertGreater(
            len(session.overlay_tracker_state.selected_wall_opening_context_trackers), 0
        )
        self.assertEqual(len(session.overlay_tracker_state.opening_hover_trackers), 0)

        session.selection.hover.set_hovered_opening(door)

        self.assertIs(session.hovered_opening, door)
        self.assertGreater(len(session.overlay_tracker_state.opening_hover_trackers), 0)
        self.assertEqual(
            len(session.overlay_tracker_state.selected_wall_opening_context_trackers), 0
        )

        from bimplan.overlays import openings as opening_overlays

        with patch(
            "bimplan.overlays.openings.sync_hovered_opening_overlay",
            wraps=opening_overlays.sync_hovered_opening_overlay,
        ) as sync_hover:
            session.selection.state.set_selected_plan_target("wall", wall)

        self.assertGreater(sync_hover.call_count, 0)
        self.assertGreater(len(session.overlay_tracker_state.opening_hover_trackers), 0)
        self.assertEqual(
            len(session.overlay_tracker_state.selected_wall_opening_context_trackers), 0
        )

        session.selection.hover.set_hovered_opening(None)

        self.assertIsNone(session.hovered_opening)
        self.assertEqual(len(session.overlay_tracker_state.opening_hover_trackers), 0)
        self.assertGreater(
            len(session.overlay_tracker_state.selected_wall_opening_context_trackers), 0
        )

    def test_plan_edit_can_flip_selected_door_hinge(self):
        """Selected door handles should expose hinge flipping in Plan Edit."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()

        door = self._make_hosted_door(wall, name="FlipDoor")
        original_parts = list(door.WindowParts)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.document.Name, door.Name)
        self.pump_gui_events()
        session.selection.refresh.refresh_primary_selected_plan_target()

        session.openings.activate_opening_handle(door, 1)
        self.pump_gui_events()

        self.assertNotEqual(original_parts, list(door.WindowParts))

    def test_plan_edit_clicking_opening_populates_selection_ex(self):
        """Clicked opening selection should create a real SelectionEx entry for property view."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="SelectionDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session.picking,
            "pick",
            return_value=("opening", door),
        ):
            activated = session.selection.activation.activate_opening_target((100, 100))

        self.assertTrue(activated)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, door.Name)
        self.assertIs(session.view.getActiveObject("Arch"), door)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_opening_handle_populates_selection_ex(self):
        """Opening handle clicks should also create a real SelectionEx entry."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="HandleSelectionDoor")

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session.picking,
                "pick_edit_node",
                return_value=("opening_handle", door, 0),
            ),
            patch.object(session.openings, "activate_opening_handle") as activate_handle,
        ):
            callback = self._make_fake_left_mouse_press()
            session.input.on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        activate_handle.assert_called_once_with(door, 0)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, door.Name)
        self.assertIs(session.view.getActiveObject("Arch"), door)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_clicking_opening_edit_node_populates_selection_ex(self):
        """Opening edit-node hits should populate property-view selection before handle activation."""

        level = Arch.makeFloor(name="Level 0")
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        level.addObject(wall)
        self.document.recompute()
        door = self._make_hosted_door(wall, name="EditNodeSelectionDoor")

        class _FakeField:
            def __init__(self, value):
                self._value = value

            def getValue(self):
                return self._value

        class _FakePickedPoint:
            def __init__(self, document_name, object_name, sub_element_name):
                self.documentName = _FakeField(document_name)
                self.objectName = _FakeField(object_name)
                self.subElementName = _FakeField(sub_element_name)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(level)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        picked_point = _FakePickedPoint(self.document.Name, door.Name, "EditNode0")
        with (
            patch.object(
                session.picking,
                "pick_edit_node",
                return_value=("edit_node", picked_point),
            ),
            patch.object(session.openings, "activate_opening_handle") as activate_handle,
        ):
            callback = self._make_fake_left_mouse_press()
            session.input.on_mouse_pressed(callback)

        self.assertTrue(callback._handled)
        activate_handle.assert_called_once_with(door, 0)
        self.assertEqual([obj.Name for obj in FreeCADGui.Selection.getSelection()], [door.Name])
        selection_ex = FreeCADGui.Selection.getSelectionEx("*")
        self.assertEqual(len(selection_ex), 1)
        self.assertEqual(selection_ex[0].ObjectName, door.Name)
        self.assertIs(session.view.getActiveObject("Arch"), door)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()


class TestBimPlanEditGuiOpenings(BimPlanEditGuiOpeningsMixin, BimPlanEditGuiBase):
    """Opening and window Plan Edit GUI suite."""

    pass
