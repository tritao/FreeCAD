# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared lifecycle helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimplan.runtime import command_gate as plan_command_gate
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.tools import spaces as plan_spaces
from bimplan.selection import target_dispatch as plan_target_dispatch
from bimplan.selection import target_kinds as plan_target_kinds

translate = FreeCAD.Qt.translate


class PlanLifecycleAPI:
    """Owned session surface for Plan Edit lifecycle helpers."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def connect_teardown_signal(self, signal):
        return connect_teardown_signal(self.session, signal)

    def connect_teardown_signals(self, QtGui):
        return connect_teardown_signals(self.session, QtGui)

    def disconnect_teardown_signals(self):
        return disconnect_teardown_signals(self.session)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def activate_select_tool(self):
        return activate_select_tool(self.session)

    def cancel_pending_edit(self):
        return cancel_pending_edit(self.session)

    def stop_snapper(self):
        return stop_snapper(self.session)

    def set_draft_point_focus_suppressed(self, suppressed):
        return set_draft_point_focus_suppressed(self.session, suppressed)


def connect_teardown_signal(session, signal):
    try:
        signal.connect(session.begin_teardown)
    except (AttributeError, RuntimeError, TypeError):
        return
    session.lifecycle_state.teardown_signal_sources.append(signal)


def connect_teardown_signals(session, QtGui):
    app = QtGui.QApplication.instance()
    if app:
        connect_teardown_signal(session, app.aboutToQuit)
    main_window = session.viewport.get_main_window()
    if main_window:
        try:
            signal = main_window.mainWindowClosed
        except AttributeError:
            signal = None
        if signal is not None:
            connect_teardown_signal(session, signal)


def disconnect_teardown_signals(session):
    lifecycle_state = session.lifecycle_state
    for signal in lifecycle_state.teardown_signal_sources:
        try:
            signal.disconnect(session.begin_teardown)
        except (TypeError, RuntimeError):
            pass
    lifecycle_state.teardown_signal_sources = []


def _discard_view_runtime_references(session):
    viewport_state = session.viewport_state
    session.viewport.clear_viewport_status_chip()
    session.viewport.restore_preselection_state()
    session.doc = None
    session.gui_doc = None
    session.view = None
    session.viewer = None
    viewport_state.saved_navigation_style = None
    viewport_state.saved_navigation_state = {}
    viewport_state.saved_view_action_state = {}
    viewport_state.saved_preselection_state = None
    viewport_state.plan_preselection_forced = False
    viewport_state.saved_camera = None
    viewport_state.saved_camera_type = None
    viewport_state.working_plane = None
    viewport_state.interaction_plane = None


def _discard_selection_runtime_references(session):
    selection_state = session.selection_state
    session.selection.state.set_selected_plan_target_state()
    selection_state.secondary_selected_plan_targets_state = []
    session.hovered_wall = None
    session.hovered_opening = None
    session.hovered_symbol = None
    session.hovered_provider = None
    session.hovered_space = None
    session.hovered_region = None
    selection_state.pending_selected_plan_target = None


def _discard_provider_runtime_references(session):
    provider_point_state = session.provider_point_state
    provider_transient_state = session.provider_transient_state
    provider_transient_state.provider_selected_objects = []
    provider_point_state.provider_point_host_target = None
    provider_point_state.provider_point_host_source = ""
    provider_point_state.provider_point_preview_trackers = []
    provider_point_state.provider_point_preview_render_state = None
    provider_point_state.provider_point_preview_style_state = None
    provider_point_state.provider_point_preview_source_point = None
    provider_point_state.provider_point_preview_point = None
    provider_point_state.provider_point_preview_host_target = None
    provider_point_state.provider_point_preview_host_source = ""
    session.provider_runtime_state.target_collection_depth = 0


def _discard_space_runtime_references(session):
    space_region_pick_state = session.space_region_pick_state
    plan_region_tool_state = session.plan_region_tool_state
    interaction_state = session.interaction_state
    space_region_pick_state.boundaries = []
    space_region_pick_state.candidates = []
    space_region_pick_state.hovered_candidate = None
    space_region_pick_state.seed_space = None
    plan_region_tool_state.points = []
    plan_region_tool_state.preview_trackers = []
    plan_region_tool_state.parent_space = None
    interaction_state.edit_space = None


def _discard_edit_runtime_references(session):
    wall_edit_state = session.wall_edit_state
    interaction_state = session.interaction_state
    wall_edit_state.edit_wall = None
    interaction_state.edit_opening = None
    interaction_state.edit_opening_handle_index = None
    interaction_state.edit_symbol = None
    interaction_state.edit_symbol_handle_role = None
    interaction_state.edit_symbol_start_placement = None
    interaction_state.edit_symbol_reference_point = None
    wall_edit_state.edit_endpoint = None
    wall_edit_state.edit_endpoints = None
    wall_edit_state.preview_points = None
    wall_edit_state.preview_line_tracker = None
    wall_edit_state.preview_footprint_trackers = []
    wall_edit_state.preview_grip_trackers = []
    wall_edit_state.wall_edit_readout_trackers = []
    wall_edit_state.wall_edit_opening_preview_trackers = []
    wall_edit_state.wall_edit_active_readout_tracker = None
    wall_edit_state.wall_edit_active_readout_mode = None
    wall_edit_state.edit_wall_visibility = None


def _discard_overlay_runtime_references(session):
    overlay_tracker_state = session.overlay_tracker_state
    overlay_tracker_state.junction_node_trackers = []
    overlay_tracker_state.space_region_pick_trackers = []


def _discard_creation_preview_runtime_references(session):
    creation_preview_state = session.creation_preview_state
    creation_preview_state.rect_wall_start = None
    creation_preview_state.rect_wall_params = None
    creation_preview_state.rect_wall_preview_trackers = []


def _discard_embedded_tool_runtime_references(session):
    interaction_state = session.interaction_state
    interaction_state.embedded_host = None
    interaction_state.embedded_tool = None
    interaction_state.embedded_tool_name = None


def discard_runtime_references(session):
    _discard_view_runtime_references(session)
    _discard_selection_runtime_references(session)
    _discard_provider_runtime_references(session)
    _discard_space_runtime_references(session)
    _discard_edit_runtime_references(session)
    _discard_overlay_runtime_references(session)
    _discard_creation_preview_runtime_references(session)
    _discard_embedded_tool_runtime_references(session)


def clear_hover_visuals(
    session,
    kinds=None,
    *,
    include_junction_nodes=False,
    include_hovered_wall_opening_context=False,
):
    if include_junction_nodes:
        session.overlays.walls.clear_junction_node_overlays()
    if include_hovered_wall_opening_context:
        session.overlays.walls.clear_hovered_wall_opening_context_overlay()
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
        session.overlays.walls.clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        kinds=kinds,
        clear_handle_kinds=clear_handle_kinds,
    )
    if include_selected_wall_opening_context:
        session.overlays.openings.clear_selected_wall_opening_context_overlay()
    if include_secondary_selection:
        session.overlays.spaces.clear_secondary_selected_overlays()


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
        session.overlays.providers.clear_provider_overlays()
    if include_provider_point_preview:
        session.overlays.providers.clear_provider_point_preview()
    if include_space_region_pick:
        session.overlays.spaces.clear_space_region_pick_overlays()
    if include_opening_handle_pool:
        session.overlays.openings.discard_opening_handle_tracker_pool()
    if include_opening_move_preview:
        session.openings.clear_opening_move_preview()
    if include_symbol_edit_preview:
        session.symbols.clear_symbol_edit_preview()
    if include_plan_region_preview:
        session.spaces.clear_plan_region_preview()


def detach_runtime_observers(session):
    session.selection.sync.detach_selection_observer()
    session.document_visuals.detach_document_observer()
    session.viewport.unregister_edit_callbacks()


def _clear_space_text_pick_state(session):
    plan_spaces.reset_space_text_pick_state(session)


def _clear_space_region_pick_state(session):
    plan_spaces.reset_space_region_pick_state(session, clear_overlays=False)


def _cancel_current_tool_for_finish(session):
    if session.current_tool == plan_runtime_tools.PlanTool.MOVE_PROVIDER:
        session.providers.cancel_provider_handle_point_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.MOVE_OPENING:
        session.openings.cancel_opening_handle_point_pick()
        return True
    if session.current_tool in (
        plan_runtime_tools.PlanTool.MOVE_SYMBOL,
        plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
    ):
        session.symbols.cancel_symbol_handle_point_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION:
        session.spaces.cancel_space_region_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.REGION:
        session.spaces.cancel_plan_region_tool()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
        session.spaces.cancel_space_text_position_pick()
        return True
    if session.current_tool == plan_runtime_tools.PlanTool.WINDOW:
        session.windows.cancel_window_tool()
        return True
    return False


def _cancel_finish_fallback(session):
    if session.providers.has_active_provider_point_tool():
        session.providers.cancel_provider_point_tool()
        return True
    if session.embedded_tools.has_active():
        session.embedded_tools.cancel()
        return True
    if session.wall_create.has_active_rect_wall_tool():
        session.wall_create.cancel_rect_wall_tool()
        return True
    if session.wall_edit.has_active_wall_edit():
        session.wall_edit.cancel_wall_edit()
        return True
    return False


def _cancel_current_tool_for_begin_teardown(session):
    if session.current_tool == plan_runtime_tools.PlanTool.MOVE_PROVIDER:
        session.providers.cancel_provider_handle_point_pick()
    elif session.current_tool == plan_runtime_tools.PlanTool.MOVE_OPENING:
        session.openings.cancel_opening_handle_point_pick()
    elif session.current_tool in (
        plan_runtime_tools.PlanTool.MOVE_SYMBOL,
        plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
    ):
        session.symbols.cancel_symbol_handle_point_pick()
    elif session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
        _clear_space_text_pick_state(session)
    elif session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION:
        _clear_space_region_pick_state(session)


def _cancel_current_tool_for_shutdown(session):
    if session.current_tool in (
        plan_runtime_tools.PlanTool.MOVE_SYMBOL,
        plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
    ):
        session.symbols.cancel_symbol_handle_point_pick()


def _cleanup_begin_teardown(session):
    session.viewport.clear_viewport_status_chip()
    session.status_text.clear_input_hints()
    session.embedded_tools.cancel()
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)
    session.wall_edit.cancel_wall_edit(restore=False, refresh=False)
    cancel_pending_edit(session)
    _cancel_current_tool_for_begin_teardown(session)
    clear_hover_visuals(
        session,
        include_junction_nodes=True,
        include_hovered_wall_opening_context=True,
    )
    clear_selection_visuals(
        session,
        clear_handle_kinds=(
            plan_target_kinds.PLAN_TARGET_PROVIDER,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
        ),
        include_wall_grips=True,
        include_selected_wall_opening_context=True,
        include_secondary_selection=True,
    )
    clear_transient_visuals(
        session,
        include_provider_overlays=True,
        include_provider_point_preview=True,
        include_space_region_pick=True,
        include_opening_handle_pool=True,
        include_opening_move_preview=True,
        include_symbol_edit_preview=True,
        include_plan_region_preview=True,
    )
    detach_runtime_observers(session)


def _cleanup_shutdown(session, *, teardown=False):
    session.viewport.clear_viewport_status_chip()
    session.status_text.clear_input_hints()
    session.embedded_tools.cancel()
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.wall_edit.cancel_wall_edit(restore=not teardown, refresh=False)
    cancel_pending_edit(session)
    _cancel_current_tool_for_shutdown(session)
    clear_hover_visuals(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_WALL,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
            plan_target_kinds.PLAN_TARGET_PROVIDER,
        ),
        include_junction_nodes=True,
        include_hovered_wall_opening_context=True,
    )
    clear_selection_visuals(
        session,
        clear_handle_kinds=(
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
        ),
        include_wall_grips=True,
        include_selected_wall_opening_context=True,
    )
    clear_transient_visuals(
        session,
        include_provider_overlays=True,
        include_provider_point_preview=True,
        include_opening_handle_pool=True,
        include_opening_move_preview=True,
        include_symbol_edit_preview=True,
    )
    detach_runtime_observers(session)


def finish(session, close_dialog=True):
    if _cancel_current_tool_for_finish(session):
        return True
    if _cancel_finish_fallback(session):
        return True
    return session.shutdown(close_dialog=close_dialog)


def begin_teardown(session):
    if session.lifecycle_state.tearing_down:
        return
    session.lifecycle_state.tearing_down = True
    plan_command_gate.uninstall(session)
    _cleanup_begin_teardown(session)


def shutdown(session, close_dialog=True, teardown=False):
    plan_command_gate.uninstall(session)
    if not session.document_visuals.document_is_alive():
        session.begin_teardown()
    teardown = teardown or session.lifecycle_state.tearing_down
    panel = session.task_panel
    session.task_panel = None
    _cleanup_shutdown(session, teardown=teardown)
    if panel:
        try:
            mark_closed = getattr(panel, "mark_closed", None)
            if callable(mark_closed):
                mark_closed()
        except (AttributeError, RuntimeError, TypeError):
            pass
        if close_dialog and not teardown:
            try:
                close = getattr(panel, "close", None)
                if callable(close):
                    close()
            except (AttributeError, RuntimeError, TypeError):
                pass
        else:
            try:
                detach = getattr(panel, "detach", None)
                if callable(detach):
                    detach()
            except (AttributeError, RuntimeError, TypeError):
                pass
    if teardown:
        discard_runtime_references(session)
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


def activate_select_tool(session):
    if session.current_tool in (
        plan_runtime_tools.PlanTool.MOVE_SYMBOL,
        plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
    ):
        session.symbols.cancel_symbol_handle_point_pick()
        return
    if session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION:
        session.spaces.cancel_space_region_pick()
        return
    if session.providers.has_active_provider_point_tool():
        session.providers.cancel_provider_point_tool()
        return
    if session.embedded_tools.has_active():
        session.embedded_tools.cancel()
    if session.wall_create.has_active_rect_wall_tool():
        session.wall_create.cancel_rect_wall_tool()
    if session.windows.has_active_window_tool():
        session.windows.cancel_window_tool()
    if session.spaces.has_active_plan_region_tool():
        session.spaces.cancel_plan_region_tool()
    if session.spaces.has_active_space_separator_tool():
        session.spaces.cancel_space_separator_tool()
    session.wall_edit.cancel_wall_edit()
    session.wall_relations.cancel_join_tool()


def _reset_pending_edit_state(session, *, clear_opening_edit=False):
    wall_edit_state = session.wall_edit_state
    interaction_state = session.interaction_state
    opening_transient_state = session.opening_transient_state
    wall_edit_state.wall_edit_modal_active = False
    session.wall_edit.restore_edit_wall_visibility()
    session.wall_edit.clear_wall_edit_preview()
    wall_edit_state.edit_wall = None
    wall_edit_state.edit_endpoint = None
    wall_edit_state.edit_endpoints = None
    wall_edit_state.wall_edit_opening_clearances = {}
    wall_edit_state.wall_edit_opening_clearances_queued = False
    wall_edit_state.wall_edit_task_panel_refresh_queued = False
    wall_edit_state.preview_points = None
    wall_edit_state.wall_edit_length_edit_queued = False
    session.lifecycle_state.ignore_selection_changes = False
    interaction_state.embedded_host = None
    interaction_state.embedded_tool = None
    interaction_state.embedded_tool_name = None
    opening_transient_state.edit_opening_move_anchor = "center"
    opening_transient_state.edit_opening_move_raw_point = None
    if clear_opening_edit:
        interaction_state.edit_opening = None
        interaction_state.edit_opening_handle_index = None


def cancel_pending_edit(session):
    if session.lifecycle_state.tearing_down:
        _reset_pending_edit_state(session)
        session.wall_relations.clear_plan_relation_status()
        return
    stop_snapper(session)
    session.snap.pop_opening_move_snap_profile()
    FreeCAD.activeDraftCommand = None
    _reset_pending_edit_state(session, clear_opening_edit=True)
    session.wall_relations.clear_plan_relation_status()
    session.overlays.walls.sync_wall_grips()
    plan_target_dispatch.sync_selected_target_visuals(
        session,
        kinds=plan_target_kinds.PENDING_EDIT_VISUAL_SYNC_KINDS,
        force=True,
    )


def stop_snapper(session):
    del session
    snapper = getattr(FreeCADGui, "Snapper", None)
    if not snapper:
        return
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    _set_toolbar_point_focus_suppressed(toolbar, False)
    try:
        snapper.getPoint()
        snapper.off()
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def set_draft_point_focus_suppressed(session, suppressed):
    del session
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    if not toolbar:
        return
    _set_toolbar_point_focus_suppressed(toolbar, bool(suppressed))


def _set_toolbar_point_focus_suppressed(toolbar, suppressed):
    if toolbar is None:
        return
    set_focus_suppressed = getattr(toolbar, "setPointFocusSuppressed", None)
    if callable(set_focus_suppressed):
        try:
            set_focus_suppressed(bool(suppressed))
        except (AttributeError, RuntimeError, TypeError):
            pass
        return
    if getattr(toolbar, "suppress_point_focus", None) is not None:
        try:
            toolbar.suppress_point_focus = bool(suppressed)
        except (AttributeError, RuntimeError, TypeError):
            pass
