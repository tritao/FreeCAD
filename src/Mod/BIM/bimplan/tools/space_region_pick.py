# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space/region pick tool behavior for BIM Plan Edit."""

from bimplan import document_visuals as plan_document_visuals
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.tools import space_regions as plan_space_regions


class PickSpaceRegionTool(plan_runtime_tools.PlanToolHandler):
    """Interactive picker for existing space/region candidates."""

    tool_id = plan_runtime_tools.PlanTool.PICK_SPACE_REGION

    def on_mouse_move(self, mouse_pos, event_callback):
        del event_callback
        if mouse_pos is None:
            return False
        plan_space_regions.set_hovered_space_region_candidate(
            self.session,
            self.session.spaces.pick_space_region_candidate(mouse_pos),
            plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK,
        )
        self.session.overlays.manager.refresh_plan_overlay_visuals()
        return True

    def on_left_mouse_down(self, mouse_pos, event_callback):
        candidate = self.session.spaces.pick_space_region_candidate(mouse_pos)
        if not candidate:
            return False
        self.session.spaces.activate_space_region_candidate(candidate, event_callback)
        return True

    def on_key(self, key, event_callback, coin):
        del event_callback
        if key != coin.SoKeyboardEvent.ESCAPE:
            return False
        self.session.spaces.cancel_space_region_pick()
        return True
