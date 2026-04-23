# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
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

"""Session-owned composition API import surface for Plan Edit domains."""

from bimplan.providers.runtime import PlanProvidersAPI
from bimplan import selection as plan_selection
from bimplan import document_visuals as plan_document_visuals
from bimplan.runtime.session_state import PlanInteractionAPI
from bimplan.runtime import view as plan_view
from bimplan.selection.selection import PlanSelectionAPI as _PlanSelectionAPI
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.runtime.view import PlanViewportAPI
from bimplan.status_text import PlanStatusTextAPI
from bimplan.tools.symbol_edit import PlanSymbolsAPI
from bimplan.tools import spaces as plan_spaces
from bimplan.tools.spaces import PlanSpacesAPI as _PlanSpacesAPI
from bimplan.tools.wall_edit import PlanWallEditAPI
from bimplan.tools.wall_relations import PlanWallRelationsAPI
from bimplan.tools.window_create import PlanWindowsAPI


class PlanSelectionAPI(_PlanSelectionAPI):
    def get_selected_plan_target_state(self):
        return plan_selection.get_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
        )

    def set_selected_plan_target_state(self, kind=None, obj=None):
        return plan_selection.set_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
            kind=kind,
            obj=obj,
        )


class PlanSpacesAPI(_PlanSpacesAPI):
    def set_hovered_space_region_candidate(self, candidate):
        return plan_spaces.set_hovered_space_region_candidate(
            self.session,
            candidate,
            plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK,
        )
