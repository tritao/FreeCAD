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
from bimplan.providers import PlanProviderTargetSpec
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
