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
from bimplan import targets as plan_targets
from bimplan.providers import PlanProviderTargetSpec
from bimtests.ArchWallGuiTestUtils import ArchWallGuiTestCase
from unittest.mock import patch


class TestBimPlanProviderSelectionGui(ArchWallGuiTestCase):
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
            return_value=(
                PlanProviderTargetSpec(
                    key="electrical-fixture:{}:{}".format(self.document.Name, marker.Name),
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
