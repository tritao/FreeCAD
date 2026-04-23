# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared lifecycle helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimplan import command_gate as plan_command_gate
from bimplan import window_create as plan_window_create
from bimplan import target_dispatch as plan_target_dispatch
from bimplan import target_kinds as plan_target_kinds
from bimplan.hosts import _PlanEditCommandHost, _PlanEditWallHost

translate = FreeCAD.Qt.translate


def clear_hover_visuals(
    session,
    kinds=None,
    *,
    include_junction_nodes=False,
    include_hovered_wall_opening_context=False,
):
    if include_junction_nodes:
        session._clear_junction_node_overlays()
    if include_hovered_wall_opening_context:
        session._clear_hovered_wall_opening_context_overlay()
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
        session._clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        kinds=kinds,
        clear_handle_kinds=clear_handle_kinds,
    )
    if include_selected_wall_opening_context:
        session._clear_selected_wall_opening_context_overlay()
    if include_secondary_selection:
        session._clear_secondary_selected_overlays()


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
        session._clear_provider_overlays()
    if include_provider_point_preview:
        session._clear_provider_point_preview()
    if include_space_region_pick:
        session._clear_space_region_pick_overlays()
    if include_opening_handle_pool:
        session._discard_opening_handle_tracker_pool()
    if include_opening_move_preview:
        session._clear_opening_move_preview()
    if include_symbol_edit_preview:
        session._clear_symbol_edit_preview()
    if include_plan_region_preview:
        session._clear_plan_region_preview()


def detach_runtime_observers(session):
    session._detach_selection_observer()
    session._detach_document_observer()
    session._unregister_edit_callbacks()


def finish(session, close_dialog=True):
    if session.current_tool == "Move Provider":
        session._cancel_provider_handle_point_pick()
        return True
    if session.current_tool == "Move Opening":
        session._cancel_opening_handle_point_pick()
        return True
    if session.current_tool in ("Move Symbol", "Rotate Symbol"):
        session._cancel_symbol_handle_point_pick()
        return True
    if session.current_tool == "Pick Space Region":
        session._cancel_space_region_pick()
        return True
    if session.current_tool == "Region":
        session._cancel_plan_region_tool()
        return True
    if session.current_tool == "Set Space Text":
        session._cancel_space_text_position_pick()
        return True
    if session.current_tool == "Window":
        session._cancel_window_tool()
        return True
    if session._has_active_provider_point_tool():
        session._cancel_provider_point_tool()
        return True
    if session._has_active_embedded_tool():
        session._cancel_embedded_tool()
        return True
    if session._has_active_rect_wall_tool():
        session._cancel_rect_wall_tool()
        return True
    if session._has_active_wall_edit():
        session._cancel_wall_edit()
        return True
    return session.shutdown(close_dialog=close_dialog)


def begin_teardown(session):
    if session._tearing_down:
        return
    session._tearing_down = True
    plan_command_gate.uninstall(session)
    session._clear_viewport_status_chip()
    session._clear_input_hints()
    session._cancel_embedded_tool()
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_window_tool(refresh=False)
    session._cancel_plan_region_tool(refresh=False)
    session._cancel_provider_point_tool(refresh=False)
    session._cancel_wall_edit(restore=False, refresh=False)
    session._cancel_pending_edit()
    if session.current_tool == "Move Provider":
        session._cancel_provider_handle_point_pick()
    if session.current_tool in ("Move Symbol", "Rotate Symbol"):
        session._cancel_symbol_handle_point_pick()
    if session.current_tool == "Set Space Text":
        session._edit_space = None
    if session.current_tool == "Pick Space Region":
        session._space_region_pick_boundaries = []
        session._space_region_candidates = []
        session._hovered_space_region_candidate = None
        session._space_region_pick_seed_space = None
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


def shutdown(session, close_dialog=True, teardown=False):
    plan_command_gate.uninstall(session)
    if not session._document_is_alive():
        session.begin_teardown()
    teardown = teardown or session._tearing_down
    panel = session.task_panel
    session.task_panel = None
    session._cancel_embedded_tool()
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_space_separator_tool(refresh=False)
    session._cancel_wall_edit(restore=not teardown, refresh=False)
    session._cancel_pending_edit()
    if session.current_tool in ("Move Symbol", "Rotate Symbol"):
        session._cancel_symbol_handle_point_pick()
    session._clear_viewport_status_chip()
    session._clear_input_hints()
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
        session._discard_runtime_references()
    else:
        session.restore_state()
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
    session._sync_selected_wall_opening_context_overlay()
    session._refresh_task_panel_status()


def on_embedded_command_finished(session, tool_name, command=None):
    if session._tearing_down:
        return
    if command is None or session._embedded_tool is command:
        session._embedded_host = None
        session._embedded_tool = None
        session._embedded_tool_name = None
    if session.current_tool == tool_name:
        session.current_tool = "Select"
        session._sync_selected_wall_opening_context_overlay()
        session._refresh_task_panel_status()


def activate_select_tool(session):
    if session.current_tool in ("Move Symbol", "Rotate Symbol"):
        session._cancel_symbol_handle_point_pick()
        return
    if session.current_tool == "Pick Space Region":
        session._cancel_space_region_pick()
        return
    if session._has_active_provider_point_tool():
        session._cancel_provider_point_tool()
        return
    if session._has_active_embedded_tool():
        session._cancel_embedded_tool()
    if session._has_active_rect_wall_tool():
        session._cancel_rect_wall_tool()
    if session._has_active_window_tool():
        session._cancel_window_tool()
    if session._has_active_plan_region_tool():
        session._cancel_plan_region_tool()
    if session._has_active_space_separator_tool():
        session._cancel_space_separator_tool()
    session._cancel_wall_edit()
    session._cancel_join_tool()


def activate_window_tool(session):
    session._cancel_space_region_pick(refresh=False)
    session._cancel_plan_region_tool(refresh=False)
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_space_separator_tool(refresh=False)
    session._cancel_provider_point_tool(refresh=False)
    if session._has_active_embedded_tool():
        session._cancel_embedded_tool()
    session._cancel_wall_edit()
    session._cancel_pending_edit()
    session._clear_plan_relation_status()
    clear_selection_visuals(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_WALL,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
            plan_target_kinds.PLAN_TARGET_SPACE,
            plan_target_kinds.PLAN_TARGET_REGION,
        ),
        clear_handle_kinds=(plan_target_kinds.PLAN_TARGET_OPENING,),
        include_wall_grips=True,
        include_selected_wall_opening_context=True,
        include_secondary_selection=True,
    )
    session._clear_window_preview()
    return plan_window_create.activate_window_tool(session)


def activate_plan_region_tool(session):
    parent_space = session._get_selected_plan_target_object("space")
    session._cancel_space_region_pick(refresh=False)
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_window_tool(refresh=False)
    session._cancel_space_separator_tool(refresh=False)
    session._cancel_provider_point_tool(refresh=False)
    if session._has_active_embedded_tool():
        session._cancel_embedded_tool()
    session._cancel_wall_edit()
    session._cancel_pending_edit()
    session._clear_plan_relation_status()
    session._set_selected_plan_target()
    session._clear_hovered_plan_targets()
    clear_selection_visuals(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_WALL,
            plan_target_kinds.PLAN_TARGET_REGION,
            plan_target_kinds.PLAN_TARGET_SPACE,
        ),
        include_wall_grips=True,
        include_selected_wall_opening_context=True,
        include_secondary_selection=True,
    )
    session._clear_plan_region_preview()
    session._plan_region_points = []
    session._plan_region_parent_space = parent_space
    session.current_tool = "Region"
    FreeCAD.activeDraftCommand = session
    FreeCADGui.Snapper.getPoint(
        callback=session._handle_plan_region_point,
        movecallback=session._update_plan_region_preview,
        title=translate("BIM_PlanEdit", "First region point"),
    )
    session._refresh_task_panel_status()


def activate_space_separator_tool(session):
    session._cancel_space_region_pick(refresh=False)
    session._cancel_plan_region_tool(refresh=False)
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_window_tool(refresh=False)
    session._cancel_provider_point_tool(refresh=False)
    if session._has_active_embedded_tool():
        session._cancel_embedded_tool()
    session._cancel_wall_edit()
    session._cancel_pending_edit()
    session._clear_plan_relation_status()
    session._set_selected_plan_target()
    clear_selection_visuals(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_WALL,
            plan_target_kinds.PLAN_TARGET_SPACE,
        ),
        include_wall_grips=True,
        include_selected_wall_opening_context=True,
        include_secondary_selection=True,
    )
    session._clear_space_separator_preview()
    session._space_separator_start = None
    session._space_separator_height = session._get_wall_defaults()["height"]
    session.current_tool = "Separator"
    FreeCAD.activeDraftCommand = session
    FreeCADGui.Snapper.getPoint(
        callback=session._handle_space_separator_point,
        title=translate("BIM_PlanEdit", "Separator start point"),
    )
    session._refresh_task_panel_status()


def activate_space_tool(session):
    session._cancel_space_region_pick(refresh=False)
    session._cancel_plan_region_tool(refresh=False)
    if session.current_tool == "Set Space Text":
        session._cancel_space_text_position_pick()
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_window_tool(refresh=False)
    session._cancel_space_separator_tool(refresh=False)
    session._cancel_provider_point_tool(refresh=False)
    if session._has_active_embedded_tool():
        session._cancel_embedded_tool()
    session._cancel_wall_edit(refresh=False)
    session._cancel_pending_edit()
    session._clear_plan_relation_status()
    return session._create_space_from_current_selection()


def activate_move_tool(session):
    from draftguitools import gui_move

    session._cancel_space_region_pick(refresh=False)
    session._cancel_plan_region_tool(refresh=False)
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_window_tool(refresh=False)
    session._cancel_space_separator_tool(refresh=False)
    session._cancel_provider_point_tool(refresh=False)
    session._cancel_wall_edit()
    session._cancel_pending_edit()
    session._clear_plan_relation_status()
    clear_selection_visuals(
        session,
        kinds=(plan_target_kinds.PLAN_TARGET_WALL,),
        include_wall_grips=True,
    )
    session._start_embedded_tool("Move", gui_move.Move())


def start_embedded_tool(session, tool_name, command, host_class=None):
    session.current_tool = tool_name
    plan_target_dispatch.clear_hovered_targets(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_WALL,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
            plan_target_kinds.PLAN_TARGET_PROVIDER,
            plan_target_kinds.PLAN_TARGET_REGION,
        ),
    )
    session._sync_secondary_selected_overlays()
    session._refresh_task_panel_status()
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
    session._restore_edit_wall_visibility()
    session._clear_wall_edit_preview()
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
        session._clear_plan_relation_status()
        return
    session._stop_snapper()
    session._pop_opening_move_snap_profile()
    FreeCAD.activeDraftCommand = None
    _reset_pending_edit_state(session, clear_opening_edit=True)
    session._clear_plan_relation_status()
    session._sync_wall_grips()
    plan_target_dispatch.sync_selected_target_visuals(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SPACE,
            plan_target_kinds.PLAN_TARGET_PROVIDER,
        ),
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
