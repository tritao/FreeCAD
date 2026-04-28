# SPDX-License-Identifier: LGPL-2.1-or-later

"""Input event routing for BIM Plan Edit."""

from bimplan import document_visuals as plan_document_visuals
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.tools import space_regions as plan_space_regions
from bimplan.tools import select as plan_select_tool


class PlanInputAPI:
    """Owned session surface for Plan Edit input event handlers."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def on_mouse_pressed(self, event_callback):
        return on_mouse_pressed(self.session, event_callback)

    def on_mouse_moved(self, event_callback):
        return on_mouse_moved(self.session, event_callback)

    def on_mouse_wheel(self, event_callback):
        return on_mouse_wheel(self.session, event_callback)

    def on_key_pressed(self, event_callback):
        return on_key_pressed(self.session, event_callback)

    def set_event_handled(self, event_callback):
        return set_event_handled(self.session, event_callback)

    def claim_left_button_click(self, event_callback):
        return claim_left_button_click(self.session, event_callback)


def _get_event_handled_setter(event_callback):
    setter = getattr(event_callback, "setHandled", None)
    return setter if callable(setter) else None


def set_event_handled(session, event_callback):
    del session
    setter = _get_event_handled_setter(event_callback)
    if setter is None:
        return
    try:
        setter()
    except Exception:
        pass


def claim_left_button_click(session, event_callback):
    # Plan Edit owns overlay-driven picks, so also swallow the matching
    # button release to prevent the base 3D view selection pass from
    # clearing or replacing the GUI selection afterwards.
    session.input_event_state.consume_left_button_release = True
    session.input.set_event_handled(event_callback)


def _get_mouse_event_position(event):
    try:
        pos = event.getPosition().getValue()
        return (pos[0], pos[1])
    except Exception:
        return None


def _handle_join_tool_mouse_down(session, mouse_pos, event_callback):
    target_kind, target_wall = session.picking.pick(mouse_pos)
    source_wall = session.selection.state.get_selected_plan_target_object("wall")
    if (
        target_kind == "wall"
        and session.selection.targets.is_plan_selectable_wall(target_wall)
        and target_wall != source_wall
        and session.wall_relations.apply_plan_wall_join(source_wall, target_wall)
    ):
        session.input.claim_left_button_click(event_callback)


def _handle_pick_space_region_mouse_down(session, mouse_pos, event_callback):
    candidate = session.spaces.pick_space_region_candidate(mouse_pos)
    if candidate:
        session.spaces.activate_space_region_candidate(candidate, event_callback)


def _handle_left_mouse_button_release(session, event_callback):
    if not session.input_event_state.consume_left_button_release:
        return False
    session.input_event_state.consume_left_button_release = False
    session.input.set_event_handled(event_callback)
    return True


def _handle_left_mouse_button_down(session, mouse_pos, event_callback):
    session.input_event_state.consume_left_button_release = False
    if session.current_tool == plan_runtime_tools.PlanTool.JOIN:
        _handle_join_tool_mouse_down(session, mouse_pos, event_callback)
        return
    if session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION:
        _handle_pick_space_region_mouse_down(session, mouse_pos, event_callback)
        return
    if session.current_tool != plan_runtime_tools.PlanTool.SELECT:
        return
    plan_select_tool.SelectTool(session).on_left_mouse_down(mouse_pos, event_callback)


def on_mouse_pressed(session, event_callback):
    if session.lifecycle_state.tearing_down:
        return
    try:
        from pivy import coin
    except Exception:
        return

    event = event_callback.getEvent()
    mouse_pos = _get_mouse_event_position(event)
    selected_before = session.selection.state.get_selected_plan_target()
    with session.performance.plan_perf_trace_event(
        "mouse_pressed",
        button=str(event.getButton()),
        state=str(event.getState()),
        mouse_pos=mouse_pos,
        selected_before=session.performance.plan_perf_describe_target(
            selected_before.kind, selected_before.obj
        ),
    ):
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return
        with session.performance.plan_pick_debug_scope(
            "mouse_pressed_pick",
            button=str(event.getButton()),
            state=str(event.getState()),
            mouse_pos=mouse_pos,
            selected_before=session.performance.plan_perf_describe_target(
                selected_before.kind, selected_before.obj
            ),
        ):
            try:
                if event.getState() == coin.SoMouseButtonEvent.UP:
                    if _handle_left_mouse_button_release(session, event_callback):
                        return

                if event.getState() == coin.SoMouseButtonEvent.DOWN:
                    if mouse_pos is None:
                        return
                    _handle_left_mouse_button_down(session, mouse_pos, event_callback)
            finally:
                selected_after = session.selection.state.get_selected_plan_target()
                session.performance.plan_perf_set_fields(
                    handled=bool(getattr(event_callback, "_handled", False)),
                    selected_after=session.performance.plan_perf_describe_target(
                        selected_after.kind, selected_after.obj
                    ),
                )


def on_mouse_moved(session, event_callback):
    if session.lifecycle_state.tearing_down:
        return
    event = event_callback.getEvent()
    try:
        pos = event.getPosition().getValue()
        mouse_pos = (pos[0], pos[1])
    except Exception:
        mouse_pos = None
    hovered_before = session.selection.hover.get_hovered_plan_target()
    with session.performance.plan_perf_trace_event(
        "mouse_moved",
        mouse_pos=mouse_pos,
        hovered_before=session.performance.plan_perf_describe_target(
            hovered_before.kind, hovered_before.obj
        ),
    ):
        if session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION:
            if mouse_pos is not None:
                plan_space_regions.set_hovered_space_region_candidate(
                    session,
                    session.spaces.pick_space_region_candidate(mouse_pos),
                    plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK,
                )
                session.overlays.manager.refresh_plan_overlay_visuals()
            return
        if session.current_tool not in (
            plan_runtime_tools.PlanTool.SELECT,
            plan_runtime_tools.PlanTool.JOIN,
        ):
            session.selection.hover.set_hovered_wall(None)
            session.selection.hover.set_hovered_opening(None)
            session.selection.hover.set_hovered_symbol(None)
            session.selection.hover.set_hovered_provider(None)
            session.selection.hover.set_hovered_space(None)
            session.selection.hover.set_hovered_region(None)
            return
        if mouse_pos is None:
            return
        if not session.picking.hover(mouse_pos):
            return
        if (
            session.overlay_tracker_state.grip_trackers
            or session.selection.state.is_selected_plan_target("wall")
        ):
            session.overlays.walls.sync_wall_grips()
        session.viewport.request_view_redraw()
        hovered_after = session.selection.hover.get_hovered_plan_target()
        session.performance.plan_perf_set_fields(
            hovered_after=session.performance.plan_perf_describe_target(
                hovered_after.kind, hovered_after.obj
            ),
        )


def on_mouse_wheel(session, event_callback):
    if session.lifecycle_state.tearing_down:
        return
    event = event_callback.getEvent()
    try:
        event_type_name = str(event.getTypeId().getName())
    except Exception:
        event_type_name = ""
    if event_type_name != "SoMouseWheelEvent":
        return
    with session.performance.plan_perf_trace_event("mouse_wheel", event_type=event_type_name):
        session.overlays.queue_plan_overlay_view_scale_refresh()


def _set_key_event_handled(event_callback):
    setter = _get_event_handled_setter(event_callback)
    if setter is not None:
        setter()


def _handle_direct_tool_key_press(session, key, event_callback, coin):
    if (
        session.current_tool == plan_runtime_tools.PlanTool.MOVE_OPENING
        and key == coin.SoKeyboardEvent.A
    ):
        if session.openings.cycle_opening_move_anchor():
            session.openings.refresh_opening_move_preview_from_raw_point()
            session.task_panels.refresh_task_panel_status()
        return True
    if (
        session.current_tool
        in (
            plan_runtime_tools.PlanTool.MOVE_SYMBOL,
            plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
        )
        and key == coin.SoKeyboardEvent.ESCAPE
    ):
        session.symbols.cancel_symbol_handle_point_pick()
        return True
    if (
        session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION
        and key == coin.SoKeyboardEvent.ESCAPE
    ):
        session.spaces.cancel_space_region_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.REGION and key in (
        coin.SoKeyboardEvent.RETURN,
        coin.SoKeyboardEvent.ENTER,
    ):
        if session.spaces.finalize_plan_region():
            _set_key_event_handled(event_callback)
        return True
    if (
        session.current_tool == plan_runtime_tools.PlanTool.REGION
        and key == coin.SoKeyboardEvent.ESCAPE
    ):
        session.spaces.cancel_plan_region_tool()
        return True
    if (
        session.current_tool == plan_runtime_tools.PlanTool.PROVIDER_POINT
        and key == coin.SoKeyboardEvent.ESCAPE
    ):
        session.providers.cancel_provider_point_tool()
        return True
    if (
        session.current_tool == plan_runtime_tools.PlanTool.MOVE_PROVIDER
        and key == coin.SoKeyboardEvent.ESCAPE
    ):
        session.providers.cancel_provider_handle_point_pick()
        return True
    if (
        session.current_tool == plan_runtime_tools.PlanTool.WINDOW
        and key == coin.SoKeyboardEvent.ESCAPE
    ):
        session.windows.cancel_window_tool()
        return True
    return False


def _handle_join_tool_key_press(session, key, event_callback, coin):
    if session.current_tool != plan_runtime_tools.PlanTool.JOIN:
        return False
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


def _handle_wall_edit_key_press(session, key, event_callback, coin):
    if session.wall_edit.is_wall_move_edit_active() and key == coin.SoKeyboardEvent.TAB:
        if session.wall_edit.start_wall_readout_edit(cycle=True):
            _set_key_event_handled(event_callback)
        return True
    if session.wall_edit.is_wall_readout_edit_active() and key in (
        coin.SoKeyboardEvent.RETURN,
        coin.SoKeyboardEvent.ENTER,
    ):
        if session.wall_edit.start_wall_readout_edit():
            _set_key_event_handled(event_callback)
        return True
    if session.wall_edit.is_wall_stretch_edit_active() and key == coin.SoKeyboardEvent.TAB:
        if session.wall_edit.start_wall_readout_edit():
            _set_key_event_handled(event_callback)
        return True
    return False


def _handle_escape_cancels(session):
    if (
        session.wall_edit_state.edit_wall
        and session.current_tool != plan_runtime_tools.PlanTool.SELECT
    ):
        session.wall_edit.cancel_wall_edit_point_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.MOVE_OPENING:
        session.openings.cancel_opening_handle_point_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.MOVE_PROVIDER:
        session.providers.cancel_provider_handle_point_pick()
        return True
    if session.current_tool in (
        plan_runtime_tools.PlanTool.MOVE_SYMBOL,
        plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
    ):
        session.symbols.cancel_symbol_handle_point_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
        session.spaces.cancel_space_text_position_pick()
        return True
    if session.providers.has_active_provider_point_tool():
        session.providers.cancel_provider_point_tool()
        return True
    if session.windows.has_active_window_tool():
        session.windows.cancel_window_tool()
        return True
    if session.wall_create.has_active_rect_wall_tool():
        session.wall_create.cancel_rect_wall_tool()
        return True
    if session.spaces.has_active_plan_region_tool():
        session.spaces.cancel_plan_region_tool()
        return True
    if session.spaces.has_active_space_separator_tool():
        session.spaces.cancel_space_separator_tool()
        return True
    return False


def on_key_pressed(session, event_callback):
    if session.lifecycle_state.tearing_down:
        return
    try:
        from pivy import coin
    except Exception:
        return
    event = event_callback.getEvent()
    key = event.getKey()
    if _handle_direct_tool_key_press(session, key, event_callback, coin):
        return
    if _handle_join_tool_key_press(session, key, event_callback, coin):
        return
    if _handle_wall_edit_key_press(session, key, event_callback, coin):
        return
    if key != coin.SoKeyboardEvent.ESCAPE:
        return
    if _handle_escape_cancels(session):
        return
