# SPDX-License-Identifier: LGPL-2.1-or-later

"""Input event routing for BIM Plan Edit."""

from bimplan.providers import edit as plan_provider_edit_tool
from bimplan.providers import point as plan_provider_point_tool
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.tools import join as plan_join_tool
from bimplan.tools import opening_edit as plan_opening_tool
from bimplan.tools import select as plan_select_tool
from bimplan.tools import spaces as plan_spaces_tool
from bimplan.tools import space_region_pick as plan_space_region_pick_tool
from bimplan.tools import symbol_edit as plan_symbol_tool
from bimplan.tools import wall_create as plan_wall_create_tool
from bimplan.tools import wall_edit as plan_wall_edit_tool
from bimplan.tools import window_create as plan_window_tool

_LEFT_MOUSE_DOWN_TOOL_HANDLERS = {
    plan_runtime_tools.PlanTool.JOIN: plan_join_tool.JoinTool,
    plan_runtime_tools.PlanTool.PICK_SPACE_REGION: (
        plan_space_region_pick_tool.PickSpaceRegionTool
    ),
    plan_runtime_tools.PlanTool.SELECT: plan_select_tool.SelectTool,
}

_MOUSE_MOVE_TOOL_HANDLERS = {
    plan_runtime_tools.PlanTool.JOIN: plan_join_tool.JoinTool,
    plan_runtime_tools.PlanTool.PICK_SPACE_REGION: (
        plan_space_region_pick_tool.PickSpaceRegionTool
    ),
    plan_runtime_tools.PlanTool.SELECT: plan_select_tool.SelectTool,
}

_MOUSE_MOVE_RECORD_HOVER_AFTER_TOOLS = frozenset(
    (
        plan_runtime_tools.PlanTool.JOIN,
        plan_runtime_tools.PlanTool.SELECT,
    )
)

_KEY_TOOL_HANDLERS = {
    plan_runtime_tools.PlanTool.JOIN: plan_join_tool.JoinTool,
    plan_runtime_tools.PlanTool.MOVE_OPENING: plan_opening_tool.OpeningMoveTool,
    plan_runtime_tools.PlanTool.MOVE_PROVIDER: plan_provider_edit_tool.ProviderMoveTool,
    plan_runtime_tools.PlanTool.MOVE_SYMBOL: plan_symbol_tool.SymbolEditTool,
    plan_runtime_tools.PlanTool.PICK_SPACE_REGION: (
        plan_space_region_pick_tool.PickSpaceRegionTool
    ),
    plan_runtime_tools.PlanTool.PROVIDER_POINT: plan_provider_point_tool.ProviderPointTool,
    plan_runtime_tools.PlanTool.RECT_WALL: plan_wall_create_tool.RectWallTool,
    plan_runtime_tools.PlanTool.REGION: plan_spaces_tool.RegionTool,
    plan_runtime_tools.PlanTool.ROTATE_SYMBOL: plan_symbol_tool.SymbolEditTool,
    plan_runtime_tools.PlanTool.SEPARATOR: plan_spaces_tool.SpaceSeparatorTool,
    plan_runtime_tools.PlanTool.SET_SPACE_TEXT: plan_spaces_tool.SpaceTextTool,
    plan_runtime_tools.PlanTool.WINDOW: plan_window_tool.WindowTool,
}


def _current_tool_is(*tools):
    tool_set = frozenset(tools)
    return lambda session: _coerce_current_tool(session) in tool_set


_ESCAPE_CANCEL_HANDLERS = (
    (
        _current_tool_is(plan_runtime_tools.PlanTool.MOVE_PROVIDER),
        plan_provider_edit_tool.ProviderMoveTool,
    ),
    (
        _current_tool_is(
            plan_runtime_tools.PlanTool.MOVE_SYMBOL,
            plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
        ),
        plan_symbol_tool.SymbolEditTool,
    ),
    (
        _current_tool_is(plan_runtime_tools.PlanTool.SET_SPACE_TEXT),
        plan_spaces_tool.SpaceTextTool,
    ),
    (
        lambda session: session.providers.has_active_provider_point_tool(),
        plan_provider_point_tool.ProviderPointTool,
    ),
    (
        lambda session: session.windows.has_active_window_tool(),
        plan_window_tool.WindowTool,
    ),
    (
        lambda session: session.wall_create.has_active_rect_wall_tool(),
        plan_wall_create_tool.RectWallTool,
    ),
    (
        lambda session: session.spaces.has_active_plan_region_tool(),
        plan_spaces_tool.RegionTool,
    ),
    (
        lambda session: session.spaces.has_active_space_separator_tool(),
        plan_spaces_tool.SpaceSeparatorTool,
    ),
)


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


def _coerce_current_tool(session):
    return plan_runtime_tools.coerce_plan_tool(session.current_tool)


def _get_current_tool_handler(session, registry):
    handler_class = registry.get(_coerce_current_tool(session))
    if handler_class is None:
        return None
    return handler_class(session)


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


def _handle_left_mouse_button_release(session, event_callback):
    if not session.input_event_state.consume_left_button_release:
        return False
    session.input_event_state.consume_left_button_release = False
    session.input.set_event_handled(event_callback)
    return True


def _handle_left_mouse_button_down(session, mouse_pos, event_callback):
    session.input_event_state.consume_left_button_release = False
    handler = _get_current_tool_handler(session, _LEFT_MOUSE_DOWN_TOOL_HANDLERS)
    if handler is None:
        return
    handler.on_left_mouse_down(mouse_pos, event_callback)


def _record_hovered_after(session):
    hovered_after = session.selection.hover.get_hovered_plan_target()
    session.performance.plan_perf_set_fields(
        hovered_after=session.performance.plan_perf_describe_target(
            hovered_after.kind, hovered_after.obj
        ),
    )


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
        current_tool = _coerce_current_tool(session)
        handler = _get_current_tool_handler(session, _MOUSE_MOVE_TOOL_HANDLERS)
        if handler is not None:
            if (
                handler.on_mouse_move(mouse_pos, event_callback)
                and current_tool in _MOUSE_MOVE_RECORD_HOVER_AFTER_TOOLS
            ):
                _record_hovered_after(session)
            return
        session.selection.hover.set_hovered_wall(None)
        session.selection.hover.set_hovered_opening(None)
        session.selection.hover.set_hovered_symbol(None)
        session.selection.hover.set_hovered_provider(None)
        session.selection.hover.set_hovered_space(None)
        session.selection.hover.set_hovered_region(None)
        return


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


def _handle_direct_tool_key_press(session, key, event_callback, coin):
    handler = _get_current_tool_handler(session, _KEY_TOOL_HANDLERS)
    return bool(handler and handler.on_key(key, event_callback, coin))


def _handle_escape_cancels(session):
    for predicate, handler_class in _ESCAPE_CANCEL_HANDLERS:
        if predicate(session):
            handler_class(session).cancel()
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
    if plan_wall_edit_tool.WallEditTool(session).on_key(key, event_callback, coin):
        return
    if key != coin.SoKeyboardEvent.ESCAPE:
        return
    if _handle_escape_cancels(session):
        return
