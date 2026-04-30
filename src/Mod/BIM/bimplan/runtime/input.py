# SPDX-License-Identifier: LGPL-2.1-or-later

"""Input event routing for BIM Plan Edit."""

from bimplan.providers.edit import ProviderMoveTool
from bimplan.providers.point import ProviderPointTool
from bimplan.runtime.tools import PlanTool, coerce_plan_tool
from bimplan.tools.opening_edit import OpeningMoveTool
from bimplan.tools.select import SelectTool
from bimplan.tools.space_regions import PickSpaceRegionTool
from bimplan.tools.spaces import RegionTool, SpaceSeparatorTool, SpaceTextTool
from bimplan.tools.symbol_edit import SymbolEditTool
from bimplan.tools.wall_create import RectWallTool
from bimplan.tools.wall_edit import WallEditTool
from bimplan.tools.wall_relations import JoinTool
from bimplan.tools.window_create import WindowTool


def _overlay_runtime_api(session):
    overlays = getattr(session, "overlays", None)
    return getattr(overlays, "runtime", overlays)


_TOOL_HANDLERS = {
    PlanTool.JOIN: JoinTool,
    PlanTool.MOVE_OPENING: OpeningMoveTool,
    PlanTool.MOVE_PROVIDER: ProviderMoveTool,
    PlanTool.MOVE_SYMBOL: SymbolEditTool,
    PlanTool.PICK_SPACE_REGION: PickSpaceRegionTool,
    PlanTool.PROVIDER_POINT: ProviderPointTool,
    PlanTool.RECT_WALL: RectWallTool,
    PlanTool.REGION: RegionTool,
    PlanTool.ROTATE_SYMBOL: SymbolEditTool,
    PlanTool.SEPARATOR: SpaceSeparatorTool,
    PlanTool.SET_SPACE_TEXT: SpaceTextTool,
    PlanTool.SELECT: SelectTool,
    PlanTool.WINDOW: WindowTool,
}

_LEFT_MOUSE_DOWN_TOOLS = frozenset(
    (
        PlanTool.JOIN,
        PlanTool.PICK_SPACE_REGION,
        PlanTool.SELECT,
    )
)

_MOUSE_MOVE_TOOLS = _LEFT_MOUSE_DOWN_TOOLS

_MOUSE_MOVE_RECORD_HOVER_AFTER_TOOLS = frozenset(
    (
        PlanTool.JOIN,
        PlanTool.SELECT,
    )
)

_ESCAPE_TOOL_HANDLERS = {
    PlanTool.MOVE_PROVIDER: ProviderMoveTool,
    PlanTool.MOVE_SYMBOL: SymbolEditTool,
    PlanTool.ROTATE_SYMBOL: SymbolEditTool,
    PlanTool.SET_SPACE_TEXT: SpaceTextTool,
}


def _provider_point_api(session):
    providers = getattr(session, "providers", None)
    return getattr(providers, "point", providers)


_ESCAPE_ACTIVE_TOOL_FALLBACKS = (
    (
        lambda session: _provider_point_api(session).has_active_provider_point_tool(),
        ProviderPointTool,
    ),
    (
        lambda session: session.windows.has_active_window_tool(),
        WindowTool,
    ),
    (
        lambda session: session.wall_create.has_active_rect_wall_tool(),
        RectWallTool,
    ),
    (
        lambda session: session.spaces.has_active_plan_region_tool(),
        RegionTool,
    ),
    (
        lambda session: session.spaces.has_active_space_separator_tool(),
        SpaceSeparatorTool,
    ),
)

_HOVER_CLEARERS = (
    "set_hovered_wall",
    "set_hovered_opening",
    "set_hovered_symbol",
    "set_hovered_provider",
    "set_hovered_space",
    "set_hovered_region",
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
    return coerce_plan_tool(session.current_tool)


def _get_tool_handler(session, tool=None):
    handler_class = _TOOL_HANDLERS.get(tool or _coerce_current_tool(session))
    if handler_class is None:
        return None
    return handler_class(session)


def _get_current_tool_handler(session, supported_tools):
    current_tool = _coerce_current_tool(session)
    if current_tool not in supported_tools:
        return None
    return _get_tool_handler(session, current_tool)


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


def _describe_plan_target(session, target):
    return session.performance.plan_perf_describe_target(target.kind, target.obj)


def _clear_hovered_targets(session):
    hover = session.selection.hover
    for method_name in _HOVER_CLEARERS:
        getattr(hover, method_name)(None)


def _handle_left_mouse_button_release(session, event_callback):
    if not session.input_event_state.consume_left_button_release:
        return False
    session.input_event_state.consume_left_button_release = False
    session.input.set_event_handled(event_callback)
    return True


def _handle_left_mouse_button_down(session, mouse_pos, event_callback):
    session.input_event_state.consume_left_button_release = False
    handler = _get_current_tool_handler(session, _LEFT_MOUSE_DOWN_TOOLS)
    if handler is None:
        return
    handler.on_left_mouse_down(mouse_pos, event_callback)


def _record_hovered_after(session):
    hovered_after = session.selection.hover.get_hovered_plan_target()
    session.performance.plan_perf_set_fields(
        hovered_after=_describe_plan_target(session, hovered_after),
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
    selected_before_description = _describe_plan_target(session, selected_before)
    with session.performance.plan_perf_trace_event(
        "mouse_pressed",
        button=str(event.getButton()),
        state=str(event.getState()),
        mouse_pos=mouse_pos,
        selected_before=selected_before_description,
    ):
        if event.getButton() != coin.SoMouseButtonEvent.BUTTON1:
            return
        with session.performance.plan_pick_debug_scope(
            "mouse_pressed_pick",
            button=str(event.getButton()),
            state=str(event.getState()),
            mouse_pos=mouse_pos,
            selected_before=selected_before_description,
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
                    selected_after=_describe_plan_target(session, selected_after),
                )


def on_mouse_moved(session, event_callback):
    if session.lifecycle_state.tearing_down:
        return
    mouse_pos = _get_mouse_event_position(event_callback.getEvent())
    hovered_before = session.selection.hover.get_hovered_plan_target()
    with session.performance.plan_perf_trace_event(
        "mouse_moved",
        mouse_pos=mouse_pos,
        hovered_before=_describe_plan_target(session, hovered_before),
    ):
        current_tool = _coerce_current_tool(session)
        handler = _get_current_tool_handler(session, _MOUSE_MOVE_TOOLS)
        if handler is not None:
            if (
                handler.on_mouse_move(mouse_pos, event_callback)
                and current_tool in _MOUSE_MOVE_RECORD_HOVER_AFTER_TOOLS
            ):
                _record_hovered_after(session)
            return
        _clear_hovered_targets(session)


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
        _overlay_runtime_api(session).queue_plan_overlay_view_scale_refresh()


def _handle_direct_tool_key_press(session, key, event_callback, coin):
    handler = _get_tool_handler(session)
    return bool(handler and handler.on_key(key, event_callback, coin))


def _handle_global_key_press(session, key, event_callback, coin):
    return WallEditTool(session).on_key(key, event_callback, coin)


def _handle_escape_cancels(session):
    handler_class = _ESCAPE_TOOL_HANDLERS.get(_coerce_current_tool(session))
    if handler_class is not None:
        return handler_class(session).cancel()
    for predicate, handler_class in _ESCAPE_ACTIVE_TOOL_FALLBACKS:
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
    if _handle_global_key_press(session, key, event_callback, coin):
        return
    if key != coin.SoKeyboardEvent.ESCAPE:
        return
    if _handle_escape_cancels(session):
        return
