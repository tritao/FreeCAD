# SPDX-License-Identifier: LGPL-2.1-or-later

"""Select tool behavior for BIM Plan Edit."""

from bimplan.runtime import tools as plan_runtime_tools
from bimplan.selection import edit_nodes as plan_edit_nodes


_DRAG_THRESHOLD_PX = 4.0


class SelectTool(plan_runtime_tools.PlanToolHandler):
    """Default Plan Edit selection and edit-node activation tool."""

    tool_id = plan_runtime_tools.PlanTool.SELECT

    def on_mouse_move(self, mouse_pos, event_callback):
        state = self.session.input_event_state
        if state.selection_press_pos is not None:
            state.selection_last_pos = mouse_pos
            dx = float(mouse_pos[0]) - float(state.selection_press_pos[0])
            dy = float(mouse_pos[1]) - float(state.selection_press_pos[1])
            if not state.selection_dragging and dx * dx + dy * dy >= _DRAG_THRESHOLD_PX**2:
                state.selection_dragging = True
                _show_selection_rubber_band(self.session)
            if state.selection_dragging:
                _update_selection_rubber_band(self.session)
            self.session.input.set_event_handled(event_callback)
            return True
        return sync_selectable_hover(self.session, mouse_pos)

    def on_left_mouse_down(self, mouse_pos, event_callback, additive=False):
        if not additive:
            node = self.session.picking.pick_edit_node(mouse_pos)
            if node and _activate_edit_node(self.session, node, event_callback):
                return True
        state = self.session.input_event_state
        state.selection_press_pos = tuple(mouse_pos)
        state.selection_last_pos = tuple(mouse_pos)
        state.selection_additive = bool(additive)
        state.selection_dragging = False
        # Claim only the press. The release is retained for click-vs-drag resolution.
        self.session.input.set_event_handled(event_callback)
        return True

    def on_left_mouse_up(self, event_callback):
        session = self.session
        state = session.input_event_state
        mouse_pos = state.selection_last_pos or state.selection_press_pos
        additive = bool(state.selection_additive)
        dragging = bool(state.selection_dragging)
        start = state.selection_press_pos
        clear_selection_gesture(session)

        if dragging:
            session.selection.activation.select_plan_targets_in_screen_rect(
                start,
                mouse_pos,
                additive=additive,
            )
            return True

        if additive:
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


def _selection_viewport_widget(session):
    try:
        graphics_view = session.view.graphicsView()
        viewport = graphics_view.viewport()
        return viewport if viewport is not None else graphics_view
    except Exception:
        return None


def _selection_qt_rect(session):
    from PySide import QtCore

    state = session.input_event_state
    widget = _selection_viewport_widget(session)
    if widget is None or state.selection_press_pos is None or state.selection_last_pos is None:
        return None
    height = int(widget.height())
    ratio = float(widget.devicePixelRatioF())
    start = QtCore.QPoint(
        int(round(state.selection_press_pos[0] / ratio)),
        height - int(round(state.selection_press_pos[1] / ratio)),
    )
    end = QtCore.QPoint(
        int(round(state.selection_last_pos[0] / ratio)),
        height - int(round(state.selection_last_pos[1] / ratio)),
    )
    return QtCore.QRect(start, end).normalized()


def _show_selection_rubber_band(session):
    from PySide import QtWidgets

    state = session.input_event_state
    widget = _selection_viewport_widget(session)
    if widget is None:
        return
    if state.selection_rubber_band is None:
        state.selection_rubber_band = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Rectangle, widget
        )
    _update_selection_rubber_band(session)
    state.selection_rubber_band.show()


def _update_selection_rubber_band(session):
    state = session.input_event_state
    rect = _selection_qt_rect(session)
    if state.selection_rubber_band is not None and rect is not None:
        state.selection_rubber_band.setGeometry(rect)


def clear_selection_gesture(session):
    state = session.input_event_state
    if state.selection_rubber_band is not None:
        state.selection_rubber_band.hide()
    state.selection_press_pos = None
    state.selection_last_pos = None
    state.selection_additive = False
    state.selection_dragging = False


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
