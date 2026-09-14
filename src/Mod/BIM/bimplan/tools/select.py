# SPDX-License-Identifier: LGPL-2.1-or-later

"""Select tool behavior for BIM Plan Edit."""

from bimplan.runtime import tools as plan_runtime_tools
from bimplan.selection import edit_nodes as plan_edit_nodes


class SelectTool(plan_runtime_tools.PlanToolHandler):
    """Default Plan Edit selection and edit-node activation tool."""

    tool_id = plan_runtime_tools.PlanTool.SELECT

    def on_mouse_move(self, mouse_pos, event_callback):
        del event_callback
        return sync_selectable_hover(self.session, mouse_pos)

    def on_left_mouse_down(self, mouse_pos, event_callback):
        session = self.session
        if session.selection.activation.is_plan_additive_selection_active():
            if not session.selection.activation.toggle_plan_target_selection_at_position(
                mouse_pos, event_callback
            ):
                session.input.claim_left_button_click(event_callback)
            return True

        node = session.picking.pick_edit_node(mouse_pos)
        if not node:
            if session.selection.activation.activate_semantic_plan_target(
                mouse_pos, event_callback
            ):
                return True
            session.selection.sync.schedule_clear_plan_selection_state()
            session.input.claim_left_button_click(event_callback)
            return True

        return _activate_edit_node(session, node, event_callback)


def sync_selectable_hover(session, mouse_pos):
    if mouse_pos is None:
        return False
    if not session.picking.hover(mouse_pos):
        return False
    session.viewport.request_view_redraw()
    return True


def _activate_edit_node(session, node, event_callback):
    node_kind = plan_edit_nodes.get_edit_node_kind(node)
    if node_kind == "provider_handle":
        obj, index = plan_edit_nodes.get_edit_node_payload(node)
        session.selection.state.set_selected_plan_target_state("provider", obj)
        session.overlays.walls.clear_selected_wall_overlay()
        session.providers.activate_provider_handle(obj, index)
    elif node_kind == "symbol_handle":
        obj, role = plan_edit_nodes.get_edit_node_payload(node)
        session.selection.state.set_selected_plan_target_state("symbol", obj)
        session.overlays.walls.clear_selected_wall_overlay()
        session.symbols.activate_symbol_handle(obj, role)
    elif node_kind in ("provider_overlay_point", "provider_overlay_target"):
        if not session.selection.activation.activate_provider_overlay_target_node(
            node, event_callback
        ):
            return False
    elif node_kind == "contextual_handle":
        obj, handle = plan_edit_nodes.get_edit_node_payload(node)
        if not session.viewport.queue_scene_graph_mutation(
            ("activate-contextual-handle", id(handle)),
            lambda: _activate_contextual_handle(session, obj, handle),
        ):
            return False
    else:
        return False
    session.input.claim_left_button_click(event_callback)
    return True
def _activate_contextual_handle(session, obj, handle):
    """Start point acquisition only after the current Coin event has returned."""

    target_ref = session.selection.targets.get_plan_target_for_object(obj)
    if target_ref.kind is not None:
        session.selection.state.set_selected_plan_target_state(target_ref.kind, target_ref.obj)
        session.selection.sync.set_gui_selection_object(target_ref.obj)
    return session.contextual_editing.activate(handle)
