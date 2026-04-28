# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall join tool behavior for BIM Plan Edit."""

from bimplan.runtime import tools as plan_runtime_tools
from bimplan.tools import select as plan_select_tool


class JoinTool(plan_runtime_tools.PlanToolHandler):
    """Interactive wall join/unjoin tool."""

    tool_id = plan_runtime_tools.PlanTool.JOIN

    def on_mouse_move(self, mouse_pos, event_callback):
        del event_callback
        return plan_select_tool.sync_selectable_hover(self.session, mouse_pos)

    def on_left_mouse_down(self, mouse_pos, event_callback):
        session = self.session
        target_kind, target_wall = session.picking.pick(mouse_pos)
        source_wall = session.selection.state.get_selected_plan_target_object("wall")
        if (
            target_kind == "wall"
            and session.selection.targets.is_plan_selectable_wall(target_wall)
            and target_wall != source_wall
            and session.wall_relations.apply_plan_wall_join(source_wall, target_wall)
        ):
            session.input.claim_left_button_click(event_callback)
            return True
        return False

    def on_key(self, key, event_callback, coin):
        session = self.session
        if key == coin.SoKeyboardEvent.TAB:
            if session.wall_relations.cycle_plan_join_type():
                _set_key_event_handled(event_callback)
            return True
        if key in (
            getattr(coin.SoKeyboardEvent, "DELETE", None),
            getattr(coin.SoKeyboardEvent, "BACKSPACE", None),
        ):
            if session.wall_relations.unjoin_current_plan_wall_pair():
                _set_key_event_handled(event_callback)
            return True
        if key == coin.SoKeyboardEvent.ESCAPE:
            session.wall_relations.cancel_join_tool()
            return True
        return False


def _set_key_event_handled(event_callback):
    setter = getattr(event_callback, "setHandled", None)
    if callable(setter):
        setter()
