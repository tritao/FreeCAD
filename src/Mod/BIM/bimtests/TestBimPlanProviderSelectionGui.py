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

import Draft
import FreeCAD
import FreeCADGui
from bimcommands import BimPlanSession
from bimplan import selection as plan_selection
from bimplan import targets as plan_targets
from bimplan.providers import (
    PlanOverlaySpec,
    PlanOverlayTargetKind,
    PlanOverlayTargetSpec,
    PlanProviderTargetSpec,
)
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

            self.assertEqual(("provider", marker), session._get_selected_plan_target())
            self.assertEqual([marker], FreeCADGui.Selection.getSelection())
            self.assertEqual((marker,), session.get_selected_objects())
            self.assertEqual(
                ("provider", marker),
                plan_targets.get_plan_pick_target_for_object(session, marker),
            )

            self.assertTrue(session.set_plan_provider_overlay_mode("architecture"))
            self.assertEqual(("provider", marker), session._get_selected_plan_target())
            self.assertEqual([marker], FreeCADGui.Selection.getSelection())
            self.assertEqual((marker,), session.get_selected_objects())
            self.assertEqual(
                (None, None),
                plan_targets.get_plan_pick_target_for_object(session, marker),
            )

            self.assertTrue(session.set_plan_provider_overlay_mode("electrical"))
            self.assertEqual(("provider", marker), session._get_selected_plan_target())
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
            session._sync_provider_overlays()
            self.assertGreater(len(session._provider_overlay_trackers), 0)

            session._set_gui_selection_object(marker)
            session._refresh_primary_selected_plan_target()
            self.pump_gui_events()

            self.assertEqual(("provider", marker), session._get_selected_plan_target())
            self.assertGreater(len(session._provider_selected_trackers), 0)
            self.assertEqual([], session._provider_hover_trackers)

        session.shutdown(close_dialog=False)
        self.pump_gui_events()
