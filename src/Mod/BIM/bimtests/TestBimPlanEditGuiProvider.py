# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider integration GUI tests."""

from .TestBimPlanEditGuiBase import *  # noqa: F401,F403
from .TestBimPlanEditGuiBase import (
    BimPlanEditGuiBase,
    _DeletedDocument,
    _TestPlanProvider,
)


class BimPlanEditGuiProviderMixin:
    def test_plan_edit_renders_registered_provider_contributions(self):
        from PySide import QtGui

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        panel = session.task_panel
        self.assertIsNotNone(panel, "Plan Edit task panel should be attached.")
        panel.refresh_from_session()
        self.pump_gui_events()

        self.assertFalse(panel.integration_panel.isHidden())
        self.assertTrue(panel.integration_panel.isVisibleTo(panel.form))
        labels = [
            str(widget.text())
            for widget in panel.integration_panel.findChildren(QtGui.QLabel)
        ]
        self.assertTrue(any("Action Needed" in text for text in labels))
        self.assertTrue(any("Utilities" in text for text in labels))
        self.assertTrue(any("More Context" in text for text in labels))
        self.assertTrue(any("Mode" in text for text in labels))
        self.assertTrue(any("Selection" in text for text in labels))
        self.assertTrue(any("Provider needs review" in text for text in labels))
        self.assertTrue(any("Test Selection" in text for text in labels))
        self.assertTrue(
            any(
                "Context panel content should appear in the Plan Edit dock." in text
                for text in labels
            )
        )
        self.assertTrue(any("Integration Summary" in text for text in labels))
        self.assertTrue(any("Overlays" in text for text in labels))

        overlay_checkboxes = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QCheckBox)
            if "Provider Preview" in str(widget.text())
        ]
        self.assertEqual(1, len(overlay_checkboxes))
        overlay_key = session.providers.get_plan_provider_overlay_visibility_key(
            "test-plan-provider",
            "provider-preview",
        )
        self.assertTrue(overlay_checkboxes[0].isChecked())
        self.assertNotIn(overlay_key, session._provider_overlay_visibility)
        overlay_checkboxes[0].setChecked(False)
        self.pump_gui_events()
        self.assertFalse(session._provider_overlay_visibility[overlay_key])
        overlay_checkboxes[0].setChecked(True)
        self.pump_gui_events()
        self.assertNotIn(overlay_key, session._provider_overlay_visibility)

        buttons = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QPushButton)
            if str(widget.text()) == "Apply Test Fix"
        ]
        self.assertEqual(1, len(buttons))

        buttons[0].click()
        self.pump_gui_events()
        self.assertEqual([("apply-provider-fix", "")], provider.executed_actions)

        tool_buttons = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QPushButton)
            if str(widget.text()) == "Run Test Tool"
        ]
        self.assertEqual(1, len(tool_buttons))

        tool_buttons[0].click()
        self.pump_gui_events()
        self.assertEqual(
            [("apply-provider-fix", ""), ("run-provider-tool", "")],
            provider.executed_actions,
        )
        self.assertGreater(provider.tool_calls, 0)
        self.assertGreater(provider.overlay_calls, 0)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_overlay_mode_filters_provider_overlay_categories(self):
        from PySide import QtGui

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session, "Plan Edit session should start in GUI tests.")
        self.pump_gui_events()

        panel = session.task_panel
        self.assertIsNotNone(panel, "Plan Edit task panel should be attached.")
        panel.refresh_from_session()
        self.pump_gui_events()

        self.assertEqual(
            "architecture", session.providers.get_plan_provider_overlay_mode()
        )

        architecture_checkboxes = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QCheckBox)
            if "Preview" in str(widget.text())
        ]
        self.assertTrue(
            any(
                "Provider Preview" in str(widget.text())
                for widget in architecture_checkboxes
            )
        )
        self.assertFalse(
            any(
                "Electrical Preview" in str(widget.text())
                for widget in architecture_checkboxes
            )
        )

        overlay_mode_combo = panel._integration_overlay_mode_combo
        self.assertIsNotNone(overlay_mode_combo)
        self.assertTrue(overlay_mode_combo.isVisibleTo(panel.integration_panel))

        overlay_mode_combo.setCurrentIndex(overlay_mode_combo.findData("electrical"))
        self.pump_gui_events()

        self.assertEqual(
            "electrical", session.providers.get_plan_provider_overlay_mode()
        )
        electrical_checkboxes = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QCheckBox)
            if "Preview" in str(widget.text())
        ]
        self.assertTrue(
            any(
                "Electrical Preview" in str(widget.text())
                for widget in electrical_checkboxes
            )
        )
        self.assertFalse(
            any(
                "Provider Preview" in str(widget.text())
                for widget in electrical_checkboxes
            )
        )

        self.assertIsNotNone(overlay_mode_combo)
        overlay_mode_combo.setCurrentIndex(overlay_mode_combo.findData("all"))
        self.pump_gui_events()

        self.assertEqual("all", session.providers.get_plan_provider_overlay_mode())
        all_mode_checkboxes = [
            widget
            for widget in panel.integration_panel.findChildren(QtGui.QCheckBox)
            if "Preview" in str(widget.text())
        ]
        self.assertTrue(
            any(
                "Provider Preview" in str(widget.text())
                for widget in all_mode_checkboxes
            )
        )
        self.assertTrue(
            any(
                "Electrical Preview" in str(widget.text())
                for widget in all_mode_checkboxes
            )
        )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_can_disable_provider_integrations_for_perf(self):
        """A temporary perf switch should bypass providers and hide the integration panel."""

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        with patch.dict("os.environ", {"FC_BIM_PLAN_EDIT_DISABLE_INTEGRATIONS": "1"}):
            session = BimPlanSession.start_session()
            self.assertIsNotNone(session)
            self.pump_gui_events()

            panel = session.task_panel
            self.assertIsNotNone(panel)
            panel.refresh_from_session()
            self.pump_gui_events(timeout_ms=500)

            self.assertEqual(0, provider.issue_calls)
            self.assertEqual(0, provider.section_calls)
            self.assertEqual(0, provider.tool_calls)
            self.assertEqual(0, provider.overlay_calls)
            self.assertTrue(panel.integration_panel.isHidden())
            self.assertFalse(
                session.providers.execute_plan_provider_action(
                    "test-plan-provider", "apply-provider-fix"
                )
            )
            self.assertEqual([], provider.executed_actions)

            session.shutdown(close_dialog=False)
            self.pump_gui_events()

    def test_plan_edit_provider_collection_ignores_deleted_document(self):
        """Queued provider refreshes should not touch a deleted document wrapper."""

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        session = BimPlanSession.PlanEditSession()
        session.doc = _DeletedDocument()

        try:
            self.assertEqual((), session.providers.get_plan_provider_tools())
            self.assertIsNone(session.doc)
            self.assertEqual(0, provider.tool_calls)
        finally:
            session.shutdown(close_dialog=False, teardown=True)

    def test_plan_edit_queued_overlay_refresh_ignores_deleted_document(self):
        """Queued overlay refreshes should drain without provider sync after document deletion."""

        session = BimPlanSession.PlanEditSession()
        session.doc = _DeletedDocument()
        session._overlay_refresh_queued = True
        session._dirty_plan_visuals.add(plan_document_visuals.PLAN_VISUAL_ALL)

        try:
            with patch.object(
                session.overlays.manager,
                "refresh_plan_overlay_visuals",
            ) as refresh_visuals:
                session.overlays.manager.flush_plan_overlay_visual_refresh()

            refresh_visuals.assert_not_called()
            self.assertFalse(session._overlay_refresh_queued)
            self.assertFalse(session._dirty_plan_visuals)
            self.assertIsNone(session.doc)
        finally:
            session.shutdown(close_dialog=False, teardown=True)

    def test_plan_edit_provider_point_tool_dispatches_plan_point(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            tooltip="Click in plan to place a test marker.",
            transaction_label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction=PlanToolInteraction.POINT,
            prompt="Click a plan point to place a test marker.",
        )
        captured = []

        def _capture_action(
            provider_id, action_key, transaction_label="", payload=None
        ):
            captured.append((provider_id, action_key, transaction_label, payload))
            return True

        snap_info = {
            "Object": wall.Name,
            "Component": "Edge1",
            "SubName": "Edge1",
        }
        selected_target = ("wall", wall)
        selected_targets = ("selected-wall-target",)
        hovered_target = ("wall", wall)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint") as get_point,
            patch.object(
                FreeCADGui.Snapper,
                "snapInfo",
                snap_info,
                create=True,
            ),
            patch.object(
                session.providers,
                "execute_plan_provider_action",
                side_effect=_capture_action,
            ),
            patch.object(
                session.selection.state,
                "get_selected_plan_target",
                return_value=selected_target,
            ),
            patch.object(
                session.selection.state,
                "get_selected_plan_targets",
                return_value=selected_targets,
            ),
            patch.object(
                session.selection.hover,
                "get_hovered_plan_target",
                return_value=hovered_target,
            ),
        ):
            self.assertTrue(session.providers.start_plan_provider_point_tool(tool))
            self.assertEqual("Provider Point", session.current_tool)
            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            session.providers.handle_provider_point_tool_point(raw_point, wall)
            self.assertEqual("Provider Point", session.current_tool)
            self.assertGreaterEqual(get_point.call_count, 2)
            self.assertTrue(session.providers.cancel_provider_point_tool())

        self.assertEqual(1, len(captured))
        provider_id, action_key, transaction_label, payload = captured[0]
        self.assertEqual("test-plan-provider", provider_id)
        self.assertEqual("place-test-marker", action_key)
        self.assertEqual("Place Test Marker", transaction_label)
        self.assertIs(tool, payload["tool"])
        self.assertEqual(120.0, payload["point"].x)
        self.assertEqual(340.0, payload["point"].y)
        self.assertEqual(("wall", wall), payload["host_target"])
        self.assertEqual("selected", payload["host_source"])
        expected_placement = session.providers.project_provider_point_to_host(
            payload["point"], wall
        )
        self.assertIsNotNone(expected_placement)
        self.assertAlmostEqual(expected_placement.x, payload["placement_point"].x)
        self.assertAlmostEqual(expected_placement.y, payload["placement_point"].y)
        self.assertEqual(999.0, payload["raw_point"].z)
        self.assertEqual(snap_info, payload["snap_info"])
        self.assertIs(wall, payload["snap_object"])
        self.assertEqual(("wall", wall), payload["snap_target"])
        self.assertEqual(self.document.Name, payload["snap_document_name"])
        self.assertEqual(wall.Name, payload["snap_object_name"])
        self.assertEqual("Edge1", payload["snap_component"])
        self.assertEqual("Edge1", payload["snap_subname"])
        self.assertEqual(selected_target, payload["selected_target"])
        self.assertEqual(selected_targets, payload["selected_targets"])
        self.assertEqual(hovered_target, payload["hovered_target"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_point_tool_uses_selected_wall_host_context(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction=PlanToolInteraction.POINT,
        )
        captured = []

        def _capture_action(
            provider_id, action_key, transaction_label="", payload=None
        ):
            captured.append((provider_id, action_key, transaction_label, payload))
            return True

        with (
            patch.object(FreeCADGui.Snapper, "getPoint"),
            patch.object(FreeCADGui.Snapper, "snapInfo", {}, create=True),
            patch.object(
                session.providers,
                "execute_plan_provider_action",
                side_effect=_capture_action,
            ),
        ):
            self.assertTrue(
                session.selection.activation.select_wall_for_plan_edit(
                    wall, sync_gui_selection=True
                )
            )
            self.assertTrue(session.providers.start_plan_provider_point_tool(tool))
            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            session.providers.handle_provider_point_tool_point(raw_point, None)
            self.assertTrue(session.providers.cancel_provider_point_tool())

        self.assertEqual(1, len(captured))
        payload = captured[0][3]
        self.assertEqual(("wall", wall), payload["host_target"])
        self.assertEqual("selected", payload["host_source"])
        expected_placement = session.providers.project_provider_point_to_host(
            payload["point"], wall
        )
        self.assertIsNotNone(expected_placement)
        self.assertAlmostEqual(expected_placement.x, payload["placement_point"].x)
        self.assertAlmostEqual(expected_placement.y, payload["placement_point"].y)
        self.assertEqual((None, None), payload["snap_target"])

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_point_tool_previews_selected_wall_host(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction=PlanToolInteraction.POINT,
        )
        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.Snapper, "snapInfo", {}, create=True),
        ):
            self.assertTrue(
                session.selection.activation.select_wall_for_plan_edit(
                    wall, sync_gui_selection=True
                )
            )
            self.assertTrue(session.providers.start_plan_provider_point_tool(tool))
            self.assertIn("movecallback", captured)

            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            captured["movecallback"](raw_point, None)

            plan_point = session.viewport.project_plan_point(raw_point)
            expected_placement = session.providers.project_provider_point_to_host(
                plan_point, wall
            )
            self.assertIsNotNone(expected_placement)
            self.assertEqual(
                ("wall", wall), session._provider_point_preview_host_target
            )
            self.assertEqual("selected", session._provider_point_preview_host_source)
            self.assertAlmostEqual(
                expected_placement.x, session._provider_point_preview_point.x
            )
            self.assertAlmostEqual(
                expected_placement.y, session._provider_point_preview_point.y
            )
            self.assertGreater(len(session._provider_point_preview_trackers), 2)

            self.assertTrue(session.providers.cancel_provider_point_tool())

        self.assertIsNone(session._provider_point_preview_point)
        self.assertEqual([], session._provider_point_preview_trackers)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_point_tool_previews_unhosted_point(self):
        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        tool = PlanToolSpec(
            key="place-test-marker",
            label="Place Test Marker",
            provider_id="test-plan-provider",
            interaction=PlanToolInteraction.POINT,
        )
        captured = {}

        def fake_get_point(**kwargs):
            captured.update(kwargs)

        with (
            patch.object(FreeCADGui.Snapper, "getPoint", side_effect=fake_get_point),
            patch.object(FreeCADGui.Snapper, "setSelectMode", return_value=None),
            patch.object(FreeCADGui.Snapper, "snapInfo", {}, create=True),
            patch.object(
                session.selection.state,
                "get_selected_plan_target",
                return_value=(None, None),
            ),
            patch.object(
                session.selection.state, "get_selected_plan_targets", return_value=()
            ),
            patch.object(
                session.selection.hover,
                "get_hovered_plan_target",
                return_value=(None, None),
            ),
        ):
            self.assertTrue(session.providers.start_plan_provider_point_tool(tool))
            self.assertIn("movecallback", captured)

            raw_point = FreeCAD.Vector(120.0, 340.0, 999.0)
            captured["movecallback"](raw_point, None)

            plan_point = session.viewport.project_plan_point(raw_point)
            self.assertEqual((None, None), session._provider_point_preview_host_target)
            self.assertEqual("", session._provider_point_preview_host_source)
            self.assertAlmostEqual(
                plan_point.x, session._provider_point_preview_point.x
            )
            self.assertAlmostEqual(
                plan_point.y, session._provider_point_preview_point.y
            )
            self.assertEqual(2, len(session._provider_point_preview_trackers))

            self.assertTrue(session.providers.cancel_provider_point_tool())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_wall_selection_skips_provider_refresh(self):
        """Wall selection should not trigger provider integration refreshes."""

        registry = get_plan_edit_registry()
        registry.clear()
        self.addCleanup(registry.clear)

        provider = _TestPlanProvider()
        registry.register_provider(provider)

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        panel = session.task_panel
        self.assertIsNotNone(panel)
        panel.refresh_from_session()
        self.pump_gui_events()
        provider.issue_calls = 0
        provider.section_calls = 0
        provider.tool_calls = 0
        provider.overlay_calls = 0

        session.selection.hover.set_hovered_wall(wall)
        with patch.object(
            session.selection.picking, "get_edit_node", return_value=None
        ):
            press = self._make_fake_left_mouse_press(250, 250)
            session.input.on_mouse_pressed(press)

        self.assertTrue(press._handled)
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual(0, provider.issue_calls)
        self.assertEqual(0, provider.section_calls)
        self.assertEqual(0, provider.tool_calls)
        self.assertEqual(0, provider.overlay_calls)

        self.pump_gui_events(timeout_ms=500)
        self.assertEqual(0, provider.issue_calls)
        self.assertEqual(0, provider.section_calls)
        self.assertEqual(0, provider.tool_calls)
        self.assertEqual(0, provider.overlay_calls)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_overlay_point_selects_target_object(self):
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        node = self._make_fake_selection_node(
            self.document.Name,
            marker.Name,
            "ProviderOverlayPoint:object:0",
        )
        event = self._make_fake_left_mouse_press()

        self.assertTrue(
            session.selection.activation.activate_provider_overlay_target_node(
                ("provider_overlay_point", node),
                event,
            )
        )
        self.assertTrue(event._handled)
        self.assertIn(marker, FreeCADGui.Selection.getSelection())
        self._assert_no_selected_plan_target(session)
        self.assertIn("Object: Electrical Marker", session.task_panel.status.text())
        self.assertIn("integration details", session.task_panel.status.text())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_additive_provider_overlay_point_keeps_wall_selection(self):
        wall = Arch.makeWall(length=3000, width=200, height=2500)
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(
            session.selection.activation.select_wall_for_plan_edit(
                wall, sync_gui_selection=True
            )
        )
        self.pump_gui_events()
        self._assert_selected_plan_target(session, "wall", wall)
        self.assertEqual([wall], FreeCADGui.Selection.getSelection())

        node = self._make_fake_selection_node(
            self.document.Name,
            marker.Name,
            "ProviderOverlayPoint:object:0",
        )
        event = self._make_fake_left_mouse_press()

        with patch.object(
            session.selection.picking,
            "get_edit_node",
            return_value=("provider_overlay_point", node),
        ):
            self.assertTrue(
                session.selection.activation.toggle_plan_target_selection_at_position(
                    (250, 250), event
                )
            )

        self.assertTrue(event._handled)
        selection = FreeCADGui.Selection.getSelection()
        self.assertIn(wall, selection)
        self.assertIn(marker, session._provider_selected_objects)
        self.assertIn(marker, session.selection.get_selected_objects())
        self._assert_selected_plan_target(session, "wall", wall)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_overlay_target_detects_clicked_raw_object(self):
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        original_view = session.view

        class FakeView:
            def getObjectsInfo(self, _mouse_pos):
                return (
                    {
                        "Document": marker.Document.Name,
                        "Object": marker.Name,
                    },
                )

        try:
            session.view = FakeView()
            with (
                patch.object(
                    session,
                    "get_plan_provider_overlays",
                    return_value=(
                        PlanOverlaySpec(
                            key="electrical-marker",
                            point_targets=(
                                PlanOverlayTargetSpec(
                                    document_name=marker.Document.Name,
                                    object_name=marker.Name,
                                    target_kind=PlanOverlayTargetKind.OBJECT,
                                ),
                            ),
                        ),
                    ),
                ),
                patch.object(
                    session.providers,
                    "is_plan_provider_overlay_visible",
                    return_value=True,
                ),
            ):
                self.assertEqual(
                    plan_edit_nodes.ProviderOverlayTargetEditNode("object", marker),
                    session.selection.picking.get_edit_node((100, 100)),
                )
        finally:
            session.view = original_view

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_overlay_point_selects_provider_target(self):
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        node = self._make_fake_selection_node(
            self.document.Name,
            marker.Name,
            "ProviderOverlayPoint:provider:0",
        )
        event = self._make_fake_left_mouse_press()

        with patch.object(
            session,
            "get_plan_provider_targets",
            return_value=(
                PlanProviderTargetSpec(
                    key="electrical-fixture:{}:{}".format(
                        self.document.Name, marker.Name
                    ),
                    label=marker.Label,
                    provider_id="materia-electrical-fixtures",
                    document_name=self.document.Name,
                    object_name=marker.Name,
                    semantic_document_name=self.document.Name,
                    semantic_object_name=marker.Name,
                    category="electrical",
                    role="fixture",
                ),
            ),
        ):
            self.assertTrue(
                session.selection.activation.activate_provider_overlay_target_node(
                    ("provider_overlay_point", node),
                    event,
                )
            )
            self.assertTrue(event._handled)
            self.assertEqual(
                ("provider", marker), session.selection.state.get_selected_plan_target()
            )
            self.assertEqual([], session._provider_selected_objects)
            self.assertIn(marker, FreeCADGui.Selection.getSelection())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()


class TestBimPlanEditGuiProvider(BimPlanEditGuiProviderMixin, BimPlanEditGuiBase):
    """Provider integration Plan Edit GUI suite."""

    pass
