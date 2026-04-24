# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 Furgo                                              *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""GUI tests for BIM Plan Edit provider target selection behavior."""

import Arch
import Draft
import FreeCAD
import FreeCADGui
from bimcommands import BimPlanSession
from bimplan import selection as plan_selection
from bimplan.selection import targets as plan_targets
from bimplan.providers import (
    PlanEditHandleSpec,
    PlanEditProvider,
    PlanOverlaySpec,
    PlanOverlayTargetKind,
    PlanOverlayTargetSpec,
    PlanProviderTargetSpec,
)
from bimplan.providers import get_plan_edit_registry
from bimtests.ArchWallGuiTestUtils import ArchWallGuiTestCase
from unittest.mock import patch


class TestBimPlanProviderSelectionGui(ArchWallGuiTestCase):
    def _make_provider_target_spec(self, obj, category="electrical", role="fixture"):
        return PlanProviderTargetSpec(
            key="{}:{}:{}".format(category, self.document.Name, obj.Name),
            label=obj.Label,
            provider_id="test-provider-{}".format(category),
            document_name=self.document.Name,
            object_name=obj.Name,
            semantic_document_name=self.document.Name,
            semantic_object_name=obj.Name,
            category=category,
            role=role,
        )

    def _make_provider_overlay_spec(self, obj, category="electrical"):
        point = FreeCAD.Vector(getattr(getattr(obj, "Placement", None), "Base", FreeCAD.Vector()))
        return PlanOverlaySpec(
            key="{}-overlay-{}".format(category, obj.Name),
            label=obj.Label,
            provider_id="test-provider-{}".format(category),
            category=category,
            points=((point.x, point.y, point.z),),
            point_targets=(
                PlanOverlayTargetSpec(
                    document_name=self.document.Name,
                    object_name=obj.Name,
                    target_kind=PlanOverlayTargetKind.PROVIDER,
                ),
            ),
        )

    class _ProviderMoveHandleTestProvider(PlanEditProvider):
        provider_id = "test-provider-handle"
        display_name = "Provider Handle Test"

        def __init__(self, obj):
            self.obj = obj
            self.calls = []
            self.last_point = None

        def get_targets(self, context):
            del context
            if self.obj is None or getattr(self.obj, "Document", None) is None:
                return ()
            doc_name = str(getattr(self.obj.Document, "Name", "") or "")
            return (
                PlanProviderTargetSpec(
                    key="fixture-target",
                    label=self.obj.Label,
                    provider_id=self.provider_id,
                    document_name=doc_name,
                    object_name=self.obj.Name,
                    semantic_document_name=doc_name,
                    semantic_object_name=self.obj.Name,
                    category="electrical",
                    role="fixture",
                ),
            )

        def get_edit_handles(self, context):
            target = context.get_primary_target()
            if target is None or target.kind != "provider" or target.object_name != self.obj.Name:
                return ()
            point = FreeCAD.Vector(getattr(getattr(self.obj, "Placement", None), "Base", None))
            return (
                PlanEditHandleSpec(
                    key="move-fixture",
                    point=(point.x, point.y, point.z),
                    label="Move",
                    target_key="fixture-target",
                    prompt="Pick new fixture position",
                    role="move",
                ),
            )

        def execute_action(self, action_key, context, session, payload=None):
            del context, session
            self.calls.append((action_key, payload))
            if payload is None:
                return False
            point = payload.get("point")
            if point is None:
                return False
            self.last_point = FreeCAD.Vector(point)
            if hasattr(self.obj, "X") and hasattr(self.obj, "Y"):
                self.obj.X = float(point.x)
                self.obj.Y = float(point.y)
                if hasattr(self.obj, "Z"):
                    self.obj.Z = float(point.z)
            else:
                placement = self.obj.Placement.copy()
                placement.Base = FreeCAD.Vector(point.x, point.y, point.z)
                self.obj.Placement = placement
            return True

    class _ProviderRehostHandleTestProvider(PlanEditProvider):
        provider_id = "test-provider-rehost"
        display_name = "Provider Rehost Test"

        def __init__(self, obj):
            self.obj = obj
            self.calls = []

        def get_targets(self, context):
            del context
            if self.obj is None or getattr(self.obj, "Document", None) is None:
                return ()
            doc_name = str(getattr(self.obj.Document, "Name", "") or "")
            return (
                PlanProviderTargetSpec(
                    key="fixture-target",
                    label=self.obj.Label,
                    provider_id=self.provider_id,
                    document_name=doc_name,
                    object_name=self.obj.Name,
                    semantic_document_name=doc_name,
                    semantic_object_name=self.obj.Name,
                    category="electrical",
                    role="fixture",
                ),
            )

        def get_edit_handles(self, context):
            target = context.get_primary_target()
            if target is None or target.kind != "provider" or target.object_name != self.obj.Name:
                return ()
            point = FreeCAD.Vector(getattr(getattr(self.obj, "Placement", None), "Base", None))
            return (
                PlanEditHandleSpec(
                    key="rehost-fixture",
                    point=(point.x, point.y, point.z),
                    label="Rehost",
                    target_key="fixture-target",
                    action_key="rehost-fixture",
                    prompt="Pick new host wall",
                    role="rehost",
                ),
            )

        def execute_action(self, action_key, context, session, payload=None):
            del context, session
            self.calls.append((action_key, payload))
            if action_key != "rehost-fixture" or payload is None:
                return False
            host_kind, host_obj = payload.get("host_target") or (None, None)
            if host_kind != "wall" or host_obj is None:
                return False
            placement_point = payload.get("placement_point")
            if not Arch.rehostObject(self.obj, host_obj, preserve_world_position=True):
                return False
            if placement_point is None:
                return False
            if hasattr(self.obj, "X") and hasattr(self.obj, "Y"):
                self.obj.X = float(placement_point.x)
                self.obj.Y = float(placement_point.y)
                if hasattr(self.obj, "Z"):
                    self.obj.Z = float(placement_point.z)
            else:
                placement = self.obj.Placement.copy()
                placement.Base = FreeCAD.Vector(placement_point)
                self.obj.Placement = placement
            return True

    def test_plan_edit_hidden_provider_target_is_excluded_from_pick_resolution(self):
        """Provider targets outside the active overlay mode should not resolve as pick targets."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "get_plan_provider_targets",
            return_value=(self._make_provider_target_spec(marker),),
        ):
            self.assertEqual(
                (None, None), plan_targets.get_plan_pick_target_for_object(session, marker)
            )
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            self.assertTrue(session._is_plan_provider_target_object(marker))
            self.assertEqual(
                ("provider", marker),
                plan_targets.get_plan_pick_target_for_object(session, marker),
            )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_hidden_provider_target_clears_preselection(self):
        """Hidden provider targets should not remain preselected in Plan Edit."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session,
                "get_plan_provider_targets",
                return_value=(self._make_provider_target_spec(marker),),
            ),
            patch.object(
                plan_selection, "_clear_gui_preselection", return_value=True
            ) as clear_mock,
        ):
            session.setPreselection(self.document.Name, marker.Name, "")
            clear_mock.assert_called_once_with()

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_visible_provider_target_keeps_preselection(self):
        """Visible provider targets should not be filtered out of preselection."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))

        with (
            patch.object(
                session,
                "get_plan_provider_targets",
                return_value=(self._make_provider_target_spec(marker),),
            ),
            patch.object(
                plan_selection, "_clear_gui_preselection", return_value=True
            ) as clear_mock,
        ):
            session.setPreselection(self.document.Name, marker.Name, "")
            clear_mock.assert_not_called()

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_overlay_mode_change_clears_hidden_provider_preselection(self):
        """Changing overlay mode should clear provider preselection that becomes hidden."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session,
                "get_plan_provider_targets",
                return_value=(self._make_provider_target_spec(marker),),
            ),
            patch.object(plan_selection, "_get_gui_preselection_object", return_value=marker),
            patch.object(
                plan_selection, "_clear_gui_preselection", return_value=True
            ) as clear_mock,
        ):
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            clear_mock.assert_not_called()
            self.assertTrue(session.set_plan_provider_overlay_mode("architecture"))
            clear_mock.assert_called_once_with()

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_selection_survives_overlay_mode_switch(self):
        """Selected provider targets should persist across overlay mode changes."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "get_plan_provider_targets",
            return_value=(self._make_provider_target_spec(marker),),
        ):
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            self.assertTrue(session._is_plan_provider_target_object(marker))

            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())
            self.assertEqual([marker], FreeCADGui.Selection.getSelection())
            self.assertEqual((marker,), session.get_selected_objects())
            self.assertEqual(
                ("provider", marker),
                plan_targets.get_plan_pick_target_for_object(session, marker),
            )

            self.assertTrue(session.set_plan_provider_overlay_mode("architecture"))
            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())
            self.assertEqual([marker], FreeCADGui.Selection.getSelection())
            self.assertEqual((marker,), session.get_selected_objects())
            self.assertEqual(
                (None, None),
                plan_targets.get_plan_pick_target_for_object(session, marker),
            )

            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())
            self.assertEqual([marker], FreeCADGui.Selection.getSelection())
            self.assertEqual((marker,), session.get_selected_objects())
            self.assertEqual(
                ("provider", marker),
                plan_targets.get_plan_pick_target_for_object(session, marker),
            )

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_provider_target_shows_selection_overlay(self):
        """Selected provider targets should render a distinct selection overlay."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session,
                "get_plan_provider_targets",
                return_value=(self._make_provider_target_spec(marker),),
            ),
            patch.object(
                session,
                "get_plan_provider_overlays",
                return_value=(self._make_provider_overlay_spec(marker),),
            ),
        ):
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            session.overlays.sync_provider_overlays()
            self.assertGreater(len(session._provider_overlay_trackers), 0)

            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())
            self.assertGreater(len(session._provider_selected_trackers), 0)
            self.assertEqual([], session._provider_hover_trackers)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_provider_target_shows_move_handle(self):
        """Selected provider targets with editable placement should expose a move handle."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "get_plan_provider_targets",
            return_value=(self._make_provider_target_spec(marker),),
        ):
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())
            handles = session.providers.get_selected_provider_edit_handles(marker)
            self.assertEqual(1, len(handles))
            self.assertEqual("move", handles[0].key)
            self.assertEqual(1, len(session._provider_handle_trackers))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_provider_target_can_move_by_handle(self):
        """Selected provider targets should move through the built-in placement handle."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with (
            patch.object(
                session,
                "get_plan_provider_targets",
                return_value=(self._make_provider_target_spec(marker),),
            ),
        ):
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            handle = session.providers.get_selected_provider_edit_handles(marker)[0]
            with patch.object(FreeCADGui.Snapper, "getPoint", return_value=None):
                session.providers.activate_provider_handle_now(marker, 0)
                self.assertEqual("Move Provider", session.current_tool)
                self.assertIs(marker, session._edit_provider)
                self.assertEqual(0, session._edit_provider_handle_index)
                self.assertIsNotNone(session._edit_provider_handle)
                session.providers.cancel_provider_handle_point_pick()
                self.pump_gui_events()

            session.current_tool = "Move Provider"
            session._edit_provider = marker
            session._edit_provider_handle_index = 0
            session._edit_provider_handle = handle
            session.providers.finish_provider_handle_point_pick(FreeCAD.Vector(450, 650, 0))
            self.assertAlmostEqual(450.0, marker.Placement.Base.x, delta=1e-6)
            self.assertAlmostEqual(650.0, marker.Placement.Base.y, delta=1e-6)
            self.pump_gui_events()

            self.assertAlmostEqual(450.0, marker.Placement.Base.x, delta=1e-6)
            self.assertAlmostEqual(650.0, marker.Placement.Base.y, delta=1e-6)
            self.assertEqual("Select", session.current_tool)
            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_provider_target_shows_builtin_rehost_handle(self):
        """Hostable provider targets should expose a built-in rehost handle."""

        wall = Arch.makeWall(length=3000, width=200, height=2500)
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        marker.addProperty("App::PropertyLinkList", "Hosts", "Component")
        marker.Hosts = [wall]
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "get_plan_provider_targets",
            return_value=(self._make_provider_target_spec(marker),),
        ):
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            handles = session.providers.get_selected_provider_edit_handles(marker)
            self.assertEqual(["move", "rehost"], [handle.key for handle in handles])
            self.assertEqual(2, len(session._provider_handle_trackers))

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_selected_provider_target_can_rehost_by_builtin_handle(self):
        """Built-in provider rehost handles should update the host and placement."""

        wall_a = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b.Placement.Base = FreeCAD.Vector(0, 1500, 0)
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        marker.addProperty("App::PropertyLinkList", "Hosts", "Component")
        marker.Hosts = [wall_a]
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        session = BimPlanSession.start_session()
        self.assertIsNotNone(session)
        self.pump_gui_events()

        with patch.object(
            session,
            "get_plan_provider_targets",
            return_value=(self._make_provider_target_spec(marker),),
        ):
            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            indexed_handles = list(
                enumerate(session.providers.get_selected_provider_edit_handles(marker))
            )
            handle_index, handle = next(
                (idx, handle) for idx, handle in indexed_handles if handle.key == "rehost"
            )

            pick_point = FreeCAD.Vector(1200, 1500, 0)
            expected_point = session._project_provider_point_to_host(pick_point, wall_b)

            session.current_tool = "Move Provider"
            session._edit_provider = marker
            session._edit_provider_handle_index = handle_index
            session._edit_provider_handle = handle
            session.providers.finish_provider_handle_point_pick(pick_point, obj=wall_b)
            self.pump_gui_events()

            self.assertEqual([wall_b], list(marker.Hosts))
            self.assertAlmostEqual(float(marker.X), expected_point.x, delta=1e-6)
            self.assertAlmostEqual(float(marker.Y), expected_point.y, delta=1e-6)
            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())

        session.shutdown(close_dialog=False)
        self.pump_gui_events()

    def test_plan_edit_provider_handle_dispatches_provider_action(self):
        """Provider-owned edit handles should dispatch through provider actions."""

        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        provider = self._ProviderMoveHandleTestProvider(marker)
        registry = get_plan_edit_registry()
        registry.register_provider(provider)
        try:
            session = BimPlanSession.start_session()
            self.assertIsNotNone(session)
            self.pump_gui_events()

            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())
            handles = session.providers.get_selected_provider_edit_handles(marker)
            self.assertEqual(1, len(handles))
            self.assertEqual("move-fixture", handles[0].action_key)

            session.current_tool = "Move Provider"
            session._edit_provider = marker
            session._edit_provider_handle_index = 0
            session._edit_provider_handle = handles[0]
            session.providers.finish_provider_handle_point_pick(FreeCAD.Vector(800, 900, 0))
            self.assertEqual(FreeCAD.Vector(800, 900, 0), provider.last_point)
            self.assertAlmostEqual(800.0, marker.Placement.Base.x, delta=1e-6)
            self.assertAlmostEqual(900.0, marker.Placement.Base.y, delta=1e-6)
            self.pump_gui_events()

            self.assertEqual(1, len(provider.calls))
            action_key, payload = provider.calls[0]
            self.assertEqual("move-fixture", action_key)
            self.assertIs(marker, payload["target_object"])
            self.assertEqual("move-fixture", payload["handle_key"])
            self.assertEqual("fixture-target", payload["target_key"])
            self.assertAlmostEqual(800.0, marker.Placement.Base.x, delta=1e-6)
            self.assertAlmostEqual(900.0, marker.Placement.Base.y, delta=1e-6)
            self.assertEqual(("provider", marker), session.selection.get_selected_plan_target())

            session.shutdown(close_dialog=False)
            self.pump_gui_events()
        finally:
            registry.unregister_provider(provider)

    def test_plan_edit_provider_rehost_handle_dispatches_host_payload(self):
        """Provider-owned rehost handles should receive host-aware payloads."""

        wall_a = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b = Arch.makeWall(length=3000, width=200, height=2500)
        wall_b.Placement.Base = FreeCAD.Vector(0, 1500, 0)
        marker = Draft.makePoint(FreeCAD.Vector(100, 200, 0))
        marker.Label = "Electrical Marker"
        marker.addProperty("App::PropertyLinkList", "Hosts", "Component")
        marker.Hosts = [wall_a]
        self.document.recompute()
        FreeCADGui.Selection.clearSelection()

        provider = self._ProviderRehostHandleTestProvider(marker)
        registry = get_plan_edit_registry()
        registry.register_provider(provider)
        try:
            session = BimPlanSession.start_session()
            self.assertIsNotNone(session)
            self.pump_gui_events()

            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            handles = session.providers.get_selected_provider_edit_handles(marker)
            self.assertEqual(1, len(handles))
            self.assertEqual("rehost-fixture", handles[0].action_key)

            pick_point = FreeCAD.Vector(1200, 1500, 0)
            expected_point = session._project_provider_point_to_host(pick_point, wall_b)

            session.current_tool = "Move Provider"
            session._edit_provider = marker
            session._edit_provider_handle_index = 0
            session._edit_provider_handle = handles[0]
            session.providers.finish_provider_handle_point_pick(pick_point, obj=wall_b)
            self.pump_gui_events()

            self.assertEqual(1, len(provider.calls))
            action_key, payload = provider.calls[0]
            self.assertEqual("rehost-fixture", action_key)
            self.assertEqual(("wall", wall_b), payload["host_target"])
            self.assertEqual("snap", payload["host_source"])
            self.assertEqual(("wall", wall_b), payload["snap_target"])
            self.assertIs(wall_b, payload["snap_object"])
            self.assertAlmostEqual(expected_point.x, payload["placement_point"].x, delta=1e-6)
            self.assertAlmostEqual(expected_point.y, payload["placement_point"].y, delta=1e-6)
            self.assertEqual([wall_b], list(marker.Hosts))
            self.assertAlmostEqual(float(marker.X), expected_point.x, delta=1e-6)
            self.assertAlmostEqual(float(marker.Y), expected_point.y, delta=1e-6)

            session.shutdown(close_dialog=False)
            self.pump_gui_events()
        finally:
            registry.unregister_provider(provider)
