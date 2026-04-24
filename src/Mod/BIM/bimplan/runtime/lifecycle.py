# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared lifecycle helpers for BIM Plan Edit."""

from dataclasses import dataclass

import FreeCAD
import FreeCADGui
from bimplan.runtime import command_gate as plan_command_gate
from bimplan import selection as plan_selection
from bimplan.tools import spaces as plan_spaces
from bimplan.tools import window_create as plan_window_create
from bimplan.selection import target_dispatch as plan_target_dispatch
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.tools.hosted_openings import _PlanEditCommandHost, _PlanEditWallHost

translate = FreeCAD.Qt.translate


def _bind_lifecycle_call(func):
    def method(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    return method


_PLAN_LIFECYCLE_API_BOUND_METHODS = (
    "activate_select_tool",
    "activate_window_tool",
    "activate_plan_region_tool",
    "activate_space_separator_tool",
    "activate_space_tool",
    "activate_move_tool",
    "on_embedded_command_started",
    "on_embedded_command_finished",
    "start_embedded_tool",
    "cancel_pending_edit",
    "stop_snapper",
    "set_draft_point_focus_suppressed",
    "has_active_embedded_tool",
    "cancel_embedded_tool",
)


class PlanLifecycleAPI:
    """Owned session surface for Plan Edit lifecycle helpers."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def activate_wall_tool(self):
        from bimplan.tools import wall_create as plan_wall_create

        return plan_wall_create.activate_wall_tool(self.session)

    def activate_rect_wall_tool(self):
        from bimplan.tools import wall_create as plan_wall_create

        return plan_wall_create.activate_rect_wall_tool(self.session)

    def activate_join_tool(self):
        from bimplan.tools import wall_relations as plan_wall_relations

        return plan_wall_relations.activate_join_tool(self.session)

    def connect_teardown_signal(self, signal):
        return connect_teardown_signal(self.session, signal)

    def connect_teardown_signals(self, QtGui):
        return connect_teardown_signals(self.session, QtGui)

    def disconnect_teardown_signals(self):
        return disconnect_teardown_signals(self.session)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)


def connect_teardown_signal(session, signal):
    try:
        signal.connect(session.begin_teardown)
    except Exception:
        return
    session._teardown_signal_sources.append(signal)


def connect_teardown_signals(session, QtGui):
    app = QtGui.QApplication.instance()
    if app:
        session.lifecycle.connect_teardown_signal(app.aboutToQuit)
    main_window = session.viewport.get_main_window()
    if main_window:
        try:
            signal = main_window.mainWindowClosed
        except AttributeError:
            signal = None
        if signal is not None:
            session.lifecycle.connect_teardown_signal(signal)


def disconnect_teardown_signals(session):
    for signal in session._teardown_signal_sources:
        try:
            signal.disconnect(session.begin_teardown)
        except Exception:
            pass
    session._teardown_signal_sources = []


def discard_runtime_references(session):
    session.viewport.clear_viewport_status_chip()
    session.viewport.restore_preselection_state()
    session.doc = None
    session.gui_doc = None
    session.view = None
    session.viewer = None
    session._saved_navigation_style = None
    session._saved_navigation_state = {}
    session._saved_view_action_state = {}
    session._saved_preselection_state = None
    session._plan_preselection_forced = False
    session.selection.set_selected_plan_target_state()
    session._provider_selected_objects = []
    session._provider_point_host_target = None
    session._provider_point_host_source = ""
    session._provider_point_preview_render_state = None
    session._provider_point_preview_style_state = None
    session._provider_point_preview_source_point = None
    session._provider_point_preview_point = None
    session._provider_point_preview_host_target = None
    session._provider_point_preview_host_source = ""
    session._secondary_selected_plan_targets_state = []
    session.hovered_wall = None
    session.hovered_opening = None
    session.hovered_symbol = None
    session.hovered_provider = None
    session.hovered_space = None
    session.hovered_region = None
    session._space_region_pick_boundaries = []
    session._space_region_candidates = []
    session._hovered_space_region_candidate = None
    session._space_region_pick_seed_space = None
    session._pending_selected_plan_target = None
    session._plan_provider_target_collection_depth = 0
    session._edit_wall = None
    session._edit_opening = None
    session._edit_opening_handle_index = None
    session._edit_symbol = None
    session._edit_symbol_handle_role = None
    session._edit_symbol_start_placement = None
    session._edit_symbol_reference_point = None
    session._plan_region_points = []
    session._plan_region_parent_space = None
    session._edit_space = None
    session._edit_endpoint = None
    session._edit_endpoints = None
    session._preview_points = None
    session._junction_node_trackers = []
    session._preview_footprint_trackers = []
    session._rect_wall_start = None
    session._rect_wall_params = None
    session._rect_wall_preview_trackers = []
    session._space_region_pick_trackers = []
    session._edit_wall_visibility = None
    session._embedded_host = None
    session._embedded_tool = None
    session._embedded_tool_name = None


def clear_hover_visuals(
    session,
    kinds=None,
    *,
    include_junction_nodes=False,
    include_hovered_wall_opening_context=False,
):
    if include_junction_nodes:
        session.overlays.clear_junction_node_overlays()
    if include_hovered_wall_opening_context:
        session.overlays.clear_hovered_wall_opening_context_overlay()
    plan_target_dispatch.clear_hovered_target_visuals(session, kinds=kinds)


def clear_selection_visuals(
    session,
    kinds=None,
    *,
    clear_handle_kinds=None,
    include_wall_grips=False,
    include_selected_wall_opening_context=False,
    include_secondary_selection=False,
):
    if include_wall_grips:
        session.overlays.clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        kinds=kinds,
        clear_handle_kinds=clear_handle_kinds,
    )
    if include_selected_wall_opening_context:
        session.overlays.clear_selected_wall_opening_context_overlay()
    if include_secondary_selection:
        session.overlays.clear_secondary_selected_overlays()


def clear_transient_visuals(
    session,
    *,
    include_provider_overlays=False,
    include_provider_point_preview=False,
    include_space_region_pick=False,
    include_opening_handle_pool=False,
    include_opening_move_preview=False,
    include_symbol_edit_preview=False,
    include_plan_region_preview=False,
):
    if include_provider_overlays:
        session.overlays.clear_provider_overlays()
    if include_provider_point_preview:
        session.overlays.clear_provider_point_preview()
    if include_space_region_pick:
        session.overlays.clear_space_region_pick_overlays()
    if include_opening_handle_pool:
        session.overlays.discard_opening_handle_tracker_pool()
    if include_opening_move_preview:
        session.openings.clear_opening_move_preview()
    if include_symbol_edit_preview:
        session.symbols.clear_symbol_edit_preview()
    if include_plan_region_preview:
        session.spaces.clear_plan_region_preview()


def detach_runtime_observers(session):
    session.selection.detach_selection_observer()
    session.document_visuals.detach_document_observer()
    session.viewport.unregister_edit_callbacks()


def _clear_space_text_pick_state(session):
    plan_spaces.reset_space_text_pick_state(session)


def _clear_space_region_pick_state(session):
    plan_spaces.reset_space_region_pick_state(session, clear_overlays=False)


def _dispatch_current_tool(session, handler_specs):
    handler_spec = handler_specs.get(session.current_tool)
    if handler_spec is None:
        return False
    if isinstance(handler_spec, str):
        _resolve_action_callable(session, handler_spec)()
    else:
        handler_spec(session)
    return True


def _resolve_action_callable(session, method_name):
    target = session
    parts = str(method_name or "").split(".")
    for part in parts:
        target = getattr(target, part)
    return target


@dataclass(frozen=True)
class ActivationActionSpec:
    method_name: str
    kwargs: tuple = ()
    predicate_name: str | None = None
    current_tools: tuple = ()
    stop_after: bool = False


@dataclass(frozen=True)
class ToolActivationProfile:
    preflight_actions: tuple = ()
    clear_selection_kinds: tuple = ()
    clear_handle_kinds: tuple = ()
    include_wall_grips: bool = False
    include_selected_wall_opening_context: bool = False
    include_secondary_selection: bool = False
    clear_selected_target: bool = False
    clear_hovered_targets: bool = False
    clear_plan_relation_status: bool = True
    capture_state: object = None
    setup: object = None
    start: object = None


@dataclass(frozen=True)
class CleanupProfile:
    action_specs: tuple = ()
    current_tool_handler_specs: object = None
    hover_visual_kwargs: tuple = ()
    selection_visual_kwargs: tuple = ()
    transient_visual_kwargs: tuple = ()
    detach_observers: bool = True


_FINISH_TOOL_HANDLER_SPECS = {
    "Move Provider": "providers.cancel_provider_handle_point_pick",
    "Move Opening": "openings.cancel_opening_handle_point_pick",
    "Move Symbol": "symbols.cancel_symbol_handle_point_pick",
    "Rotate Symbol": "symbols.cancel_symbol_handle_point_pick",
    "Pick Space Region": "spaces.cancel_space_region_pick",
    "Region": "spaces.cancel_plan_region_tool",
    "Set Space Text": "spaces.cancel_space_text_position_pick",
    "Window": "windows.cancel_window_tool",
}

_BEGIN_TEARDOWN_TOOL_HANDLER_SPECS = {
    "Move Provider": "providers.cancel_provider_handle_point_pick",
    "Move Opening": "openings.cancel_opening_handle_point_pick",
    "Move Symbol": "symbols.cancel_symbol_handle_point_pick",
    "Rotate Symbol": "symbols.cancel_symbol_handle_point_pick",
    "Set Space Text": _clear_space_text_pick_state,
    "Pick Space Region": _clear_space_region_pick_state,
}

_SHUTDOWN_TOOL_HANDLER_SPECS = {
    "Move Symbol": "symbols.cancel_symbol_handle_point_pick",
    "Rotate Symbol": "symbols.cancel_symbol_handle_point_pick",
}

_ACTION_CANCEL_SPACE_REGION_PICK = ActivationActionSpec(
    "spaces.cancel_space_region_pick",
    kwargs=(("refresh", False),),
)
_ACTION_CANCEL_SPACE_REGION_PICK_AND_RETURN = ActivationActionSpec(
    "spaces.cancel_space_region_pick",
    current_tools=("Pick Space Region",),
    stop_after=True,
)
_ACTION_CANCEL_PLAN_REGION_TOOL = ActivationActionSpec(
    "spaces.cancel_plan_region_tool",
    kwargs=(("refresh", False),),
)
_ACTION_CANCEL_PLAN_REGION_TOOL_IF_ACTIVE = ActivationActionSpec(
    "spaces.cancel_plan_region_tool",
    predicate_name="spaces.has_active_plan_region_tool",
)
_ACTION_CANCEL_RECT_WALL_TOOL = ActivationActionSpec(
    "_cancel_rect_wall_tool",
    kwargs=(("refresh", False),),
)
_ACTION_CANCEL_RECT_WALL_TOOL_IF_ACTIVE = ActivationActionSpec(
    "_cancel_rect_wall_tool",
    predicate_name="_has_active_rect_wall_tool",
)
_ACTION_CANCEL_WINDOW_TOOL = ActivationActionSpec(
    "windows.cancel_window_tool",
    kwargs=(("refresh", False),),
)
_ACTION_CANCEL_WINDOW_TOOL_IF_ACTIVE = ActivationActionSpec(
    "windows.cancel_window_tool",
    predicate_name="windows.has_active_window_tool",
)
_ACTION_CANCEL_SPACE_SEPARATOR_TOOL = ActivationActionSpec(
    "spaces.cancel_space_separator_tool",
    kwargs=(("refresh", False),),
)
_ACTION_CANCEL_SPACE_SEPARATOR_TOOL_IF_ACTIVE = ActivationActionSpec(
    "spaces.cancel_space_separator_tool",
    predicate_name="spaces.has_active_space_separator_tool",
)
_ACTION_CANCEL_PROVIDER_POINT_TOOL = ActivationActionSpec(
    "providers.cancel_provider_point_tool",
    kwargs=(("refresh", False),),
)
_ACTION_CANCEL_PROVIDER_POINT_TOOL_AND_RETURN = ActivationActionSpec(
    "providers.cancel_provider_point_tool",
    predicate_name="providers.has_active_provider_point_tool",
    stop_after=True,
)
_ACTION_CANCEL_EMBEDDED_TOOL_ALWAYS = ActivationActionSpec("lifecycle.cancel_embedded_tool")
_ACTION_CANCEL_EMBEDDED_TOOL_AND_RETURN = ActivationActionSpec(
    "lifecycle.cancel_embedded_tool",
    predicate_name="lifecycle.has_active_embedded_tool",
    stop_after=True,
)
_ACTION_CANCEL_EMBEDDED_TOOL = ActivationActionSpec(
    "lifecycle.cancel_embedded_tool",
    predicate_name="lifecycle.has_active_embedded_tool",
)
_ACTION_CANCEL_SYMBOL_HANDLE_PICK_AND_RETURN = ActivationActionSpec(
    "symbols.cancel_symbol_handle_point_pick",
    current_tools=("Move Symbol", "Rotate Symbol"),
    stop_after=True,
)
_ACTION_CANCEL_PENDING_EDIT = ActivationActionSpec("lifecycle.cancel_pending_edit")
_ACTION_CANCEL_WALL_EDIT = ActivationActionSpec("wall_edit.cancel_wall_edit")
_ACTION_CANCEL_WALL_EDIT_AND_RETURN = ActivationActionSpec(
    "wall_edit.cancel_wall_edit",
    predicate_name="wall_edit.has_active_wall_edit",
    stop_after=True,
)
_ACTION_CANCEL_WALL_EDIT_NO_REFRESH = ActivationActionSpec(
    "wall_edit.cancel_wall_edit",
    kwargs=(("refresh", False),),
)
_ACTION_CANCEL_SPACE_TEXT_PICK = ActivationActionSpec(
    "spaces.cancel_space_text_position_pick",
    current_tools=("Set Space Text",),
)
_ACTION_CANCEL_JOIN_TOOL = ActivationActionSpec("_cancel_join_tool")
_ACTION_CLEAR_VIEWPORT_STATUS_CHIP = ActivationActionSpec("viewport.clear_viewport_status_chip")
_ACTION_CLEAR_INPUT_HINTS = ActivationActionSpec("status_text.clear_input_hints")
_ACTION_CANCEL_WALL_EDIT_NO_RESTORE_NO_REFRESH = ActivationActionSpec(
    "wall_edit.cancel_wall_edit",
    kwargs=(("restore", False), ("refresh", False)),
)
_ACTION_CANCEL_WALL_EDIT_RESTORE_NO_REFRESH = ActivationActionSpec(
    "wall_edit.cancel_wall_edit",
    kwargs=(("restore", True), ("refresh", False)),
)

_WINDOW_TOOL_SELECTION_KINDS = (
    plan_target_kinds.PLAN_TARGET_WALL,
    plan_target_kinds.PLAN_TARGET_OPENING,
    plan_target_kinds.PLAN_TARGET_SYMBOL,
    plan_target_kinds.PLAN_TARGET_SPACE,
    plan_target_kinds.PLAN_TARGET_REGION,
)

_PLAN_REGION_TOOL_SELECTION_KINDS = (
    plan_target_kinds.PLAN_TARGET_WALL,
    plan_target_kinds.PLAN_TARGET_REGION,
    plan_target_kinds.PLAN_TARGET_SPACE,
)

_SPACE_SEPARATOR_TOOL_SELECTION_KINDS = (
    plan_target_kinds.PLAN_TARGET_WALL,
    plan_target_kinds.PLAN_TARGET_SPACE,
)

_MOVE_TOOL_SELECTION_KINDS = (plan_target_kinds.PLAN_TARGET_WALL,)


def _run_activation_action_specs(session, action_specs):
    for action_spec in action_specs:
        if action_spec.current_tools and session.current_tool not in action_spec.current_tools:
            continue
        if (
            action_spec.predicate_name
            and not _resolve_action_callable(
                session,
                action_spec.predicate_name,
            )()
        ):
            continue
        kwargs = dict(action_spec.kwargs)
        _resolve_action_callable(session, action_spec.method_name)(**kwargs)
        if action_spec.stop_after:
            return True
    return False


def _activate_tool_with_profile(session, profile):
    context = profile.capture_state(session) if callable(profile.capture_state) else None
    _run_activation_action_specs(session, profile.preflight_actions)
    if profile.clear_plan_relation_status:
        session.wall_relations.clear_plan_relation_status()
    if profile.clear_selected_target:
        session.selection.set_selected_plan_target()
    if profile.clear_hovered_targets:
        session.selection.clear_hovered_plan_targets()
    if profile.clear_selection_kinds:
        clear_selection_visuals(
            session,
            kinds=profile.clear_selection_kinds,
            clear_handle_kinds=profile.clear_handle_kinds,
            include_wall_grips=profile.include_wall_grips,
            include_selected_wall_opening_context=profile.include_selected_wall_opening_context,
            include_secondary_selection=profile.include_secondary_selection,
        )
    if callable(profile.setup):
        profile.setup(session, context)
    if callable(profile.start):
        return profile.start(session, context)
    return True


def _apply_cleanup_profile(session, profile):
    _run_activation_action_specs(session, profile.action_specs)
    if profile.current_tool_handler_specs:
        _dispatch_current_tool(session, profile.current_tool_handler_specs)
    if profile.hover_visual_kwargs:
        clear_hover_visuals(session, **dict(profile.hover_visual_kwargs))
    if profile.selection_visual_kwargs:
        clear_selection_visuals(session, **dict(profile.selection_visual_kwargs))
    if profile.transient_visual_kwargs:
        clear_transient_visuals(session, **dict(profile.transient_visual_kwargs))
    if profile.detach_observers:
        detach_runtime_observers(session)


def _capture_selected_space(session):
    return plan_selection.get_selected_plan_target_object(
        session,
        plan_target_kinds.PLAN_TARGET_SPACE,
    )


def _prepare_window_tool(session, context):
    del context
    session.windows.clear_window_preview()


def _start_window_tool(session, context):
    del context
    return plan_window_create.activate_window_tool(session)


def _prepare_plan_region_tool(session, parent_space):
    plan_spaces.prepare_plan_region_tool_state(session, parent_space=parent_space)


def _start_snap_tool(session, tool_name, callback, title, *, movecallback=None):
    session.current_tool = tool_name
    FreeCAD.activeDraftCommand = session
    kwargs = {
        "callback": callback,
        "title": title,
    }
    if movecallback is not None:
        kwargs["movecallback"] = movecallback
    FreeCADGui.Snapper.getPoint(**kwargs)
    session.task_panels.refresh_task_panel_status()


def _start_plan_region_tool(session, context):
    return _start_snap_tool(
        session,
        "Region",
        session.spaces.handle_plan_region_point,
        translate("BIM_PlanEdit", "First region point"),
        movecallback=session.spaces.update_plan_region_preview,
    )


def _prepare_space_separator_tool(session, context):
    del context
    from bimplan.tools import wall_create as plan_wall_create

    plan_spaces.prepare_space_separator_tool_state(
        session,
        height=plan_wall_create.get_wall_defaults(session)["height"],
    )


def _start_space_separator_tool(session, context):
    del context
    return _start_snap_tool(
        session,
        "Separator",
        session.spaces.handle_space_separator_point,
        translate("BIM_PlanEdit", "Separator start point"),
    )


def _start_space_tool(session, context):
    del context
    return session.spaces.create_space_from_current_selection()


def _start_move_tool(session, context):
    del context
    from draftguitools import gui_move

    return session.lifecycle.start_embedded_tool("Move", gui_move.Move())


_WINDOW_TOOL_ACTIVATION_PROFILE = ToolActivationProfile(
    preflight_actions=(
        _ACTION_CANCEL_SPACE_REGION_PICK,
        _ACTION_CANCEL_PLAN_REGION_TOOL,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_SPACE_SEPARATOR_TOOL,
        _ACTION_CANCEL_PROVIDER_POINT_TOOL,
        _ACTION_CANCEL_EMBEDDED_TOOL,
        _ACTION_CANCEL_WALL_EDIT,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    clear_selection_kinds=_WINDOW_TOOL_SELECTION_KINDS,
    clear_handle_kinds=(plan_target_kinds.PLAN_TARGET_OPENING,),
    include_wall_grips=True,
    include_selected_wall_opening_context=True,
    include_secondary_selection=True,
    setup=_prepare_window_tool,
    start=_start_window_tool,
)

_PLAN_REGION_TOOL_ACTIVATION_PROFILE = ToolActivationProfile(
    preflight_actions=(
        _ACTION_CANCEL_SPACE_REGION_PICK,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_WINDOW_TOOL,
        _ACTION_CANCEL_SPACE_SEPARATOR_TOOL,
        _ACTION_CANCEL_PROVIDER_POINT_TOOL,
        _ACTION_CANCEL_EMBEDDED_TOOL,
        _ACTION_CANCEL_WALL_EDIT,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    clear_selection_kinds=_PLAN_REGION_TOOL_SELECTION_KINDS,
    include_wall_grips=True,
    include_selected_wall_opening_context=True,
    include_secondary_selection=True,
    clear_selected_target=True,
    clear_hovered_targets=True,
    capture_state=_capture_selected_space,
    setup=_prepare_plan_region_tool,
    start=_start_plan_region_tool,
)

_SPACE_SEPARATOR_TOOL_ACTIVATION_PROFILE = ToolActivationProfile(
    preflight_actions=(
        _ACTION_CANCEL_SPACE_REGION_PICK,
        _ACTION_CANCEL_PLAN_REGION_TOOL,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_WINDOW_TOOL,
        _ACTION_CANCEL_PROVIDER_POINT_TOOL,
        _ACTION_CANCEL_EMBEDDED_TOOL,
        _ACTION_CANCEL_WALL_EDIT,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    clear_selection_kinds=_SPACE_SEPARATOR_TOOL_SELECTION_KINDS,
    include_wall_grips=True,
    include_selected_wall_opening_context=True,
    include_secondary_selection=True,
    clear_selected_target=True,
    setup=_prepare_space_separator_tool,
    start=_start_space_separator_tool,
)

_SPACE_TOOL_ACTIVATION_PROFILE = ToolActivationProfile(
    preflight_actions=(
        _ACTION_CANCEL_SPACE_REGION_PICK,
        _ACTION_CANCEL_PLAN_REGION_TOOL,
        _ACTION_CANCEL_SPACE_TEXT_PICK,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_WINDOW_TOOL,
        _ACTION_CANCEL_SPACE_SEPARATOR_TOOL,
        _ACTION_CANCEL_PROVIDER_POINT_TOOL,
        _ACTION_CANCEL_EMBEDDED_TOOL,
        _ACTION_CANCEL_WALL_EDIT_NO_REFRESH,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    start=_start_space_tool,
)

_MOVE_TOOL_ACTIVATION_PROFILE = ToolActivationProfile(
    preflight_actions=(
        _ACTION_CANCEL_SPACE_REGION_PICK,
        _ACTION_CANCEL_PLAN_REGION_TOOL,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_WINDOW_TOOL,
        _ACTION_CANCEL_SPACE_SEPARATOR_TOOL,
        _ACTION_CANCEL_PROVIDER_POINT_TOOL,
        _ACTION_CANCEL_WALL_EDIT,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    clear_selection_kinds=_MOVE_TOOL_SELECTION_KINDS,
    include_wall_grips=True,
    start=_start_move_tool,
)

_FINISH_FALLBACK_ACTION_SPECS = (
    _ACTION_CANCEL_PROVIDER_POINT_TOOL_AND_RETURN,
    _ACTION_CANCEL_EMBEDDED_TOOL_AND_RETURN,
    ActivationActionSpec(
        "_cancel_rect_wall_tool",
        predicate_name="_has_active_rect_wall_tool",
        stop_after=True,
    ),
    _ACTION_CANCEL_WALL_EDIT_AND_RETURN,
)

_BEGIN_TEARDOWN_CLEANUP_PROFILE = CleanupProfile(
    action_specs=(
        _ACTION_CLEAR_VIEWPORT_STATUS_CHIP,
        _ACTION_CLEAR_INPUT_HINTS,
        _ACTION_CANCEL_EMBEDDED_TOOL_ALWAYS,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_WINDOW_TOOL,
        _ACTION_CANCEL_PLAN_REGION_TOOL,
        _ACTION_CANCEL_PROVIDER_POINT_TOOL,
        _ACTION_CANCEL_WALL_EDIT_NO_RESTORE_NO_REFRESH,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    current_tool_handler_specs=_BEGIN_TEARDOWN_TOOL_HANDLER_SPECS,
    hover_visual_kwargs=(
        ("include_junction_nodes", True),
        ("include_hovered_wall_opening_context", True),
    ),
    selection_visual_kwargs=(
        (
            "clear_handle_kinds",
            (
                plan_target_kinds.PLAN_TARGET_PROVIDER,
                plan_target_kinds.PLAN_TARGET_OPENING,
                plan_target_kinds.PLAN_TARGET_SYMBOL,
            ),
        ),
        ("include_wall_grips", True),
        ("include_selected_wall_opening_context", True),
        ("include_secondary_selection", True),
    ),
    transient_visual_kwargs=(
        ("include_provider_overlays", True),
        ("include_provider_point_preview", True),
        ("include_space_region_pick", True),
        ("include_opening_handle_pool", True),
        ("include_opening_move_preview", True),
        ("include_symbol_edit_preview", True),
        ("include_plan_region_preview", True),
    ),
)

_SHUTDOWN_CLEANUP_PROFILE = CleanupProfile(
    action_specs=(
        _ACTION_CLEAR_VIEWPORT_STATUS_CHIP,
        _ACTION_CLEAR_INPUT_HINTS,
        _ACTION_CANCEL_EMBEDDED_TOOL_ALWAYS,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_SPACE_SEPARATOR_TOOL,
        _ACTION_CANCEL_WALL_EDIT_RESTORE_NO_REFRESH,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    current_tool_handler_specs=_SHUTDOWN_TOOL_HANDLER_SPECS,
    hover_visual_kwargs=(
        (
            "kinds",
            (
                plan_target_kinds.PLAN_TARGET_WALL,
                plan_target_kinds.PLAN_TARGET_OPENING,
                plan_target_kinds.PLAN_TARGET_SYMBOL,
                plan_target_kinds.PLAN_TARGET_PROVIDER,
            ),
        ),
        ("include_junction_nodes", True),
        ("include_hovered_wall_opening_context", True),
    ),
    selection_visual_kwargs=(
        (
            "clear_handle_kinds",
            (
                plan_target_kinds.PLAN_TARGET_OPENING,
                plan_target_kinds.PLAN_TARGET_SYMBOL,
            ),
        ),
        ("include_wall_grips", True),
        ("include_selected_wall_opening_context", True),
    ),
    transient_visual_kwargs=(
        ("include_provider_overlays", True),
        ("include_provider_point_preview", True),
        ("include_opening_handle_pool", True),
        ("include_opening_move_preview", True),
        ("include_symbol_edit_preview", True),
    ),
)

_TEARDOWN_SHUTDOWN_CLEANUP_PROFILE = CleanupProfile(
    action_specs=(
        _ACTION_CLEAR_VIEWPORT_STATUS_CHIP,
        _ACTION_CLEAR_INPUT_HINTS,
        _ACTION_CANCEL_EMBEDDED_TOOL_ALWAYS,
        _ACTION_CANCEL_RECT_WALL_TOOL,
        _ACTION_CANCEL_SPACE_SEPARATOR_TOOL,
        _ACTION_CANCEL_WALL_EDIT_NO_RESTORE_NO_REFRESH,
        _ACTION_CANCEL_PENDING_EDIT,
    ),
    current_tool_handler_specs=_SHUTDOWN_TOOL_HANDLER_SPECS,
    hover_visual_kwargs=_SHUTDOWN_CLEANUP_PROFILE.hover_visual_kwargs,
    selection_visual_kwargs=_SHUTDOWN_CLEANUP_PROFILE.selection_visual_kwargs,
    transient_visual_kwargs=_SHUTDOWN_CLEANUP_PROFILE.transient_visual_kwargs,
)


def finish(session, close_dialog=True):
    if _dispatch_current_tool(session, _FINISH_TOOL_HANDLER_SPECS):
        return True
    if _run_activation_action_specs(session, _FINISH_FALLBACK_ACTION_SPECS):
        return True
    return session.shutdown(close_dialog=close_dialog)


def begin_teardown(session):
    if session._tearing_down:
        return
    session._tearing_down = True
    plan_command_gate.uninstall(session)
    _apply_cleanup_profile(session, _BEGIN_TEARDOWN_CLEANUP_PROFILE)


def shutdown(session, close_dialog=True, teardown=False):
    plan_command_gate.uninstall(session)
    if not session.document_visuals.document_is_alive():
        session.begin_teardown()
    teardown = teardown or session._tearing_down
    panel = session.task_panel
    session.task_panel = None
    profile = _TEARDOWN_SHUTDOWN_CLEANUP_PROFILE if teardown else _SHUTDOWN_CLEANUP_PROFILE
    _apply_cleanup_profile(session, profile)
    if panel:
        try:
            mark_closed = getattr(panel, "mark_closed", None)
            if callable(mark_closed):
                mark_closed()
        except Exception:
            pass
        if close_dialog and not teardown:
            try:
                close = getattr(panel, "close", None)
                if callable(close):
                    close()
            except Exception:
                pass
        else:
            try:
                detach = getattr(panel, "detach", None)
                if callable(detach):
                    detach()
            except Exception:
                pass
    if teardown:
        session.lifecycle.discard_runtime_references()
    else:
        session.viewport.restore_state()
        if session.doc:
            try:
                session.doc.recompute()
            except ReferenceError:
                session.doc = None
            except RuntimeError:
                session.doc = None
        FreeCAD.Console.PrintMessage(translate("BIM_PlanEdit", "Exited BIM Plan Edit mode.\n"))
    return True


def on_embedded_command_started(session, tool_name, command=None):
    if session._tearing_down:
        return
    session._embedded_tool_name = tool_name
    if command is not None:
        session._embedded_tool = command
    session.current_tool = tool_name
    session.overlays.sync_selected_wall_opening_context_overlay()
    session.task_panels.refresh_task_panel_status()


def on_embedded_command_finished(session, tool_name, command=None):
    if session._tearing_down:
        return
    if command is None or session._embedded_tool is command:
        session._embedded_host = None
        session._embedded_tool = None
        session._embedded_tool_name = None
    if session.current_tool == tool_name:
        session.current_tool = "Select"
        session.overlays.sync_selected_wall_opening_context_overlay()
        session.task_panels.refresh_task_panel_status()


def activate_select_tool(session):
    _run_activation_action_specs(
        session,
        (
            _ACTION_CANCEL_SYMBOL_HANDLE_PICK_AND_RETURN,
            _ACTION_CANCEL_SPACE_REGION_PICK_AND_RETURN,
            _ACTION_CANCEL_PROVIDER_POINT_TOOL_AND_RETURN,
            _ACTION_CANCEL_EMBEDDED_TOOL,
            _ACTION_CANCEL_RECT_WALL_TOOL_IF_ACTIVE,
            _ACTION_CANCEL_WINDOW_TOOL_IF_ACTIVE,
            _ACTION_CANCEL_PLAN_REGION_TOOL_IF_ACTIVE,
            _ACTION_CANCEL_SPACE_SEPARATOR_TOOL_IF_ACTIVE,
            _ACTION_CANCEL_WALL_EDIT,
            _ACTION_CANCEL_JOIN_TOOL,
        ),
    )


def activate_window_tool(session):
    return _activate_tool_with_profile(session, _WINDOW_TOOL_ACTIVATION_PROFILE)


def activate_plan_region_tool(session):
    return _activate_tool_with_profile(session, _PLAN_REGION_TOOL_ACTIVATION_PROFILE)


def activate_space_separator_tool(session):
    return _activate_tool_with_profile(session, _SPACE_SEPARATOR_TOOL_ACTIVATION_PROFILE)


def activate_space_tool(session):
    return _activate_tool_with_profile(session, _SPACE_TOOL_ACTIVATION_PROFILE)


def activate_move_tool(session):
    return _activate_tool_with_profile(session, _MOVE_TOOL_ACTIVATION_PROFILE)


def start_embedded_tool(session, tool_name, command, host_class=None):
    session.current_tool = tool_name
    plan_target_dispatch.clear_hovered_targets(
        session,
        kinds=plan_target_kinds.EMBEDDED_TOOL_CLEAR_HOVERED_KINDS,
    )
    session.overlays.sync_secondary_selected_overlays()
    session.task_panels.refresh_task_panel_status()
    session._embedded_tool = command
    session._embedded_tool_name = tool_name
    host_class = _PlanEditCommandHost if host_class is None else host_class
    if host_class is _PlanEditWallHost:
        session._embedded_host = host_class(session, command)
    else:
        session._embedded_host = host_class(session, tool_name, command)
    command.Activated(host=session._embedded_host)


def _reset_pending_edit_state(session, *, clear_opening_edit=False):
    session._wall_edit_modal_active = False
    session.wall_edit.restore_edit_wall_visibility()
    session.wall_edit.clear_wall_edit_preview()
    session._edit_wall = None
    session._edit_endpoint = None
    session._edit_endpoints = None
    session._wall_edit_opening_clearances = {}
    session._wall_edit_opening_clearances_queued = False
    session._wall_edit_task_panel_refresh_queued = False
    session._preview_points = None
    session._wall_edit_length_edit_queued = False
    session._ignore_selection_changes = False
    session._embedded_host = None
    session._embedded_tool = None
    session._embedded_tool_name = None
    session._edit_opening_move_anchor = "center"
    session._edit_opening_move_raw_point = None
    if clear_opening_edit:
        session._edit_opening = None
        session._edit_opening_handle_index = None


def cancel_pending_edit(session):
    if session._tearing_down:
        _reset_pending_edit_state(session)
        session.wall_relations.clear_plan_relation_status()
        return
    stop_snapper(session)
    session.snap.pop_opening_move_snap_profile()
    FreeCAD.activeDraftCommand = None
    _reset_pending_edit_state(session, clear_opening_edit=True)
    session.wall_relations.clear_plan_relation_status()
    session.overlays.sync_wall_grips()
    plan_target_dispatch.sync_selected_target_visuals(
        session,
        kinds=plan_target_kinds.PENDING_EDIT_VISUAL_SYNC_KINDS,
        force=True,
    )


def cancel_embedded_tool(session, tool_name=None):
    if session._tearing_down or session._embedded_tool is None:
        return
    if tool_name is not None and session._embedded_tool_name != tool_name:
        return
    tool = session._embedded_tool
    if hasattr(tool, "cancel_interactive"):
        try:
            tool.cancel_interactive()
            return
        except Exception:
            pass
    if hasattr(tool, "finish"):
        try:
            tool.finish(cont=False)
        except Exception:
            pass


def stop_snapper(session):
    del session
    snapper = getattr(FreeCADGui, "Snapper", None)
    if not snapper:
        return
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    if toolbar and hasattr(toolbar, "setPointFocusSuppressed"):
        try:
            toolbar.setPointFocusSuppressed(False)
        except Exception:
            pass
    elif toolbar and hasattr(toolbar, "suppress_point_focus"):
        try:
            toolbar.suppress_point_focus = False
        except Exception:
            pass
    try:
        snapper.getPoint()
        snapper.off()
    except Exception:
        pass


def set_draft_point_focus_suppressed(session, suppressed):
    del session
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    if not toolbar:
        return
    if hasattr(toolbar, "setPointFocusSuppressed"):
        try:
            toolbar.setPointFocusSuppressed(bool(suppressed))
        except Exception:
            pass
        return
    if hasattr(toolbar, "suppress_point_focus"):
        try:
            toolbar.suppress_point_focus = bool(suppressed)
        except Exception:
            pass


def has_active_embedded_tool(session):
    return session._embedded_tool is not None


for _method_name in _PLAN_LIFECYCLE_API_BOUND_METHODS:
    setattr(PlanLifecycleAPI, _method_name, _bind_lifecycle_call(globals()[_method_name]))
