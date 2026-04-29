# SPDX-License-Identifier: LGPL-2.1-or-later

"""Select tool behavior for BIM Plan Edit."""

import FreeCAD

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
    if (
        session.overlay_tracker_state.grip_trackers
        or session.selection.state.is_selected_plan_target("wall")
    ):
        session.overlays.walls.sync_wall_grips()
    session.viewport.request_view_redraw()
    return True


def _activate_edit_node(session, node, event_callback):
    node_kind = plan_edit_nodes.get_edit_node_kind(node)
    if node_kind == "opening_handle":
        obj, index = plan_edit_nodes.get_edit_node_payload(node)
        session.selection.activation.select_opening_for_plan_edit(obj)
        session.selection.sync.set_gui_selection_object(obj)
        session.openings.activate_opening_handle(obj, index)
    elif node_kind == "provider_handle":
        obj, index = plan_edit_nodes.get_edit_node_payload(node)
        session.selection.state.set_selected_plan_target_state("provider", obj)
        session.overlays.walls.clear_wall_grips()
        session.overlays.walls.clear_selected_wall_overlay()
        session.providers.activate_provider_handle(obj, index)
    elif node_kind == "symbol_handle":
        obj, role = plan_edit_nodes.get_edit_node_payload(node)
        session.selection.state.set_selected_plan_target_state("symbol", obj)
        session.overlays.walls.clear_wall_grips()
        session.overlays.walls.clear_selected_wall_overlay()
        session.symbols.activate_symbol_handle(obj, role)
    elif node_kind in ("provider_overlay_point", "provider_overlay_target"):
        if not session.selection.activation.activate_provider_overlay_target_node(
            node, event_callback
        ):
            return False
    else:
        edit_point = _get_ray_edit_node_point(node)
        if edit_point is None:
            return False
        obj, index = edit_point
        if session.openings.is_hosted_opening_object(obj):
            session.selection.activation.select_opening_for_plan_edit(obj)
            session.selection.sync.set_gui_selection_object(obj)
            session.openings.activate_opening_handle(obj, index)
        else:
            session.selection.state.set_selected_plan_target_state("wall", obj)
            session.wall_edit.activate_wall_grip(index, wall=obj)
    session.input.claim_left_button_click(event_callback)
    return True


def _get_ray_edit_node_point(node):
    (point,) = plan_edit_nodes.get_edit_node_payload(node)
    try:
        doc = FreeCAD.getDocument(str(point.documentName.getValue()))
        obj = doc.getObject(str(point.objectName.getValue()))
        index = int(str(point.subElementName.getValue())[8:])
    except Exception:
        return None
    return obj, index
