# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared overlay management helpers for BIM Plan Edit."""

from bimplan import document_visuals as plan_document_visuals
from bimplan.runtime import tools as plan_runtime_tools


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _session_is_inactive(session):
    if session.lifecycle_state.tearing_down or session.lifecycle_state.finishing:
        return True
    return not session.document_visuals.document_is_alive()


def queue_plan_overlay_visual_refresh(session, visuals, visual_all, visual_selected_space):
    if _session_is_inactive(session):
        return
    dirty = set(visuals) if visuals else {visual_all}
    if visual_all in dirty or visual_selected_space in dirty:
        from . import spaces as overlay_spaces

        overlay_spaces.invalidate_selected_space_overlay_cache(session)
    session._dirty_plan_visuals.update(dirty)
    if session._overlay_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        dirty = consume_dirty_plan_visuals(session, plan_document_visuals.PLAN_VISUAL_ALL)
        refresh_plan_overlay_visuals(session, dirty)
        return
    session._overlay_refresh_queued = True
    QtCore.QTimer.singleShot(0, lambda: flush_plan_overlay_visual_refresh(session))


def queue_plan_overlay_view_scale_refresh(session, visual_view_scale, delay_ms):
    if _session_is_inactive(session):
        return
    session._dirty_plan_visuals.add(visual_view_scale)
    if session._overlay_refresh_queued or session._view_scale_overlay_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        dirty = consume_dirty_plan_visuals(
            session,
            plan_document_visuals.PLAN_VISUAL_ALL,
            default_all=False,
        )
        if dirty:
            refresh_plan_overlay_visuals(session, dirty)
        return
    session._view_scale_overlay_refresh_queued = True
    QtCore.QTimer.singleShot(
        max(0, int(delay_ms)), lambda: flush_view_scale_overlay_refresh(session)
    )


def consume_dirty_plan_visuals(session, visual_all, default_all=True):
    dirty = set(session._dirty_plan_visuals)
    session._dirty_plan_visuals.clear()
    if dirty:
        return dirty
    if default_all:
        return {visual_all}
    return set()


def flush_plan_overlay_visual_refresh(session):
    session._overlay_refresh_queued = False
    if _session_is_inactive(session):
        consume_dirty_plan_visuals(
            session,
            plan_document_visuals.PLAN_VISUAL_ALL,
            default_all=False,
        )
        return
    dirty = consume_dirty_plan_visuals(session, plan_document_visuals.PLAN_VISUAL_ALL)
    refresh_plan_overlay_visuals(session, dirty)


def flush_view_scale_overlay_refresh(session):
    session._view_scale_overlay_refresh_queued = False
    if _session_is_inactive(session):
        consume_dirty_plan_visuals(
            session,
            plan_document_visuals.PLAN_VISUAL_ALL,
            default_all=False,
        )
        return
    if session._overlay_refresh_queued:
        return
    dirty = consume_dirty_plan_visuals(
        session,
        plan_document_visuals.PLAN_VISUAL_ALL,
        default_all=False,
    )
    if not dirty:
        return
    refresh_plan_overlay_visuals(session, dirty)


def refresh_plan_overlay_view_scale(session):
    from . import openings as overlay_openings
    from . import providers as overlay_providers
    from . import spaces as overlay_spaces
    from . import symbols as overlay_symbols
    from . import walls as overlay_walls

    with _perf_trace_span(session, "refresh_plan_overlay_view_scale"):
        if session.current_tool == plan_runtime_tools.PlanTool.JOIN:
            overlay_walls.sync_junction_node_overlays(session)
            if session.hovered_wall:
                overlay_walls.sync_hovered_wall_overlay(session)
            return
        if session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
            if session.selection.is_selected_plan_target("space"):
                overlay_spaces.sync_selected_space_overlay(session)
            return
        if session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION:
            if session.spaces.has_space_region_pick_candidates():
                overlay_spaces.sync_space_region_pick_overlays(session)
            if session.selection.get_selected_plan_targets():
                overlay_spaces.sync_secondary_selected_overlays(session)
            return
        if session.current_tool == plan_runtime_tools.PlanTool.PROVIDER_POINT:
            overlay_providers.sync_provider_overlays(session)
            overlay_providers.sync_provider_point_preview(session)
            return
        if session.current_tool != plan_runtime_tools.PlanTool.SELECT:
            return
        if session.hovered_wall or session.selection.is_selected_plan_target("wall"):
            overlay_walls.sync_junction_node_overlays(session)
        if session.hovered_wall:
            overlay_walls.sync_hovered_wall_overlay(session)
            overlay_walls.sync_hovered_wall_opening_context_overlay(session)
        if session.selection.is_selected_plan_target("wall"):
            overlay_walls.sync_selected_wall_overlay(session)
            overlay_openings.sync_selected_wall_opening_context_overlay(session)
            overlay_walls.sync_wall_grips(session)
        if session.hovered_opening:
            overlay_openings.sync_hovered_opening_overlay(session)
        if session.selection.is_selected_plan_target("opening"):
            overlay_openings.sync_selected_opening_overlay(session)
            overlay_openings.sync_selected_opening_handles(session)
        if session.hovered_symbol:
            overlay_symbols.sync_hovered_symbol_overlay(session)
        overlay_providers.sync_provider_overlays(session)
        if session.hovered_provider:
            overlay_providers.sync_hovered_provider_overlay(session)
        if (
            session.selection.is_selected_plan_target("provider")
            or session.status_text.get_provider_selected_objects()
        ):
            overlay_providers.sync_selected_provider_overlay(session)
        if session.selection.is_selected_plan_target("symbol"):
            overlay_symbols.sync_selected_symbol_overlay(session)
            overlay_symbols.sync_selected_symbol_handles(session)
        if session.hovered_space:
            overlay_spaces.sync_hovered_space_overlay(session)
        if session.selection.is_selected_plan_target("space"):
            overlay_spaces.sync_selected_space_overlay(session)
        if session.hovered_region:
            overlay_spaces.sync_hovered_region_overlay(session)
        if session.selection.is_selected_plan_target("region"):
            overlay_spaces.sync_selected_region_overlay(session)
        if session.selection.get_secondary_selected_plan_targets():
            overlay_spaces.sync_secondary_selected_overlays(session)


def _clear_common_overlay_visuals(
    session,
    *,
    clear_selected_space=False,
    clear_selected_region=False,
    clear_secondary_selection=False,
    clear_space_region_pick=True,
    clear_selected_provider_handles=True,
):
    from . import openings as overlay_openings
    from . import providers as overlay_providers
    from . import spaces as overlay_spaces
    from . import symbols as overlay_symbols
    from . import walls as overlay_walls

    overlay_walls.clear_junction_node_overlays(session)
    overlay_walls.clear_hovered_wall_overlay(session)
    overlay_walls.clear_hovered_wall_opening_context_overlay(session)
    overlay_openings.clear_hovered_opening_overlay(session)
    overlay_symbols.clear_hovered_symbol_overlay(session)
    overlay_providers.clear_hovered_provider_overlay(session)
    overlay_spaces.clear_hovered_space_overlay(session)
    overlay_spaces.clear_hovered_region_overlay(session)
    if clear_space_region_pick:
        overlay_spaces.clear_space_region_pick_overlays(session)
    overlay_providers.clear_selected_provider_overlay(session)
    if clear_selected_provider_handles:
        overlay_providers.clear_selected_provider_handles(session)
    overlay_openings.clear_selected_opening_overlay(session)
    overlay_symbols.clear_selected_symbol_overlay(session)
    if clear_selected_space:
        overlay_spaces.clear_selected_space_overlay(session)
    if clear_selected_region:
        overlay_spaces.clear_selected_region_overlay(session)
    overlay_providers.clear_provider_overlays(session)
    overlay_providers.clear_provider_point_preview(session)
    if clear_secondary_selection:
        overlay_spaces.clear_secondary_selected_overlays(session)
    overlay_openings.clear_selected_opening_handles(session)
    overlay_symbols.clear_selected_symbol_handles(session)
    overlay_openings.clear_selected_wall_opening_context_overlay(session)
    overlay_walls.clear_wall_grips(session)
    overlay_walls.clear_selected_wall_overlay(session)


def _refresh_join_tool_overlays(session, dirty, refresh_all):
    from . import openings as overlay_openings
    from . import providers as overlay_providers
    from . import spaces as overlay_spaces
    from . import symbols as overlay_symbols
    from . import walls as overlay_walls

    if refresh_all or plan_document_visuals.PLAN_VISUAL_HOVERED_WALL in dirty:
        overlay_walls.sync_hovered_wall_overlay(session)
    overlay_walls.sync_junction_node_overlays(session)
    overlay_walls.clear_hovered_wall_opening_context_overlay(session)
    overlay_openings.clear_hovered_opening_overlay(session)
    overlay_symbols.clear_hovered_symbol_overlay(session)
    overlay_providers.clear_hovered_provider_overlay(session)
    overlay_spaces.clear_hovered_space_overlay(session)
    overlay_spaces.clear_hovered_region_overlay(session)
    overlay_spaces.clear_space_region_pick_overlays(session)
    overlay_providers.clear_selected_provider_overlay(session)
    overlay_providers.clear_selected_provider_handles(session)
    overlay_openings.clear_selected_opening_overlay(session)
    overlay_symbols.clear_selected_symbol_overlay(session)
    overlay_spaces.clear_selected_space_overlay(session)
    overlay_spaces.clear_selected_region_overlay(session)
    overlay_providers.clear_provider_overlays(session)
    overlay_providers.clear_provider_point_preview(session)
    overlay_spaces.clear_secondary_selected_overlays(session)
    overlay_openings.clear_selected_opening_handles(session)
    overlay_symbols.clear_selected_symbol_handles(session)
    overlay_openings.clear_selected_wall_opening_context_overlay(session)
    overlay_walls.clear_wall_grips(session)
    overlay_walls.clear_selected_wall_overlay(session)


def _refresh_region_tool_overlays(session):
    _clear_common_overlay_visuals(
        session,
        clear_selected_space=True,
        clear_selected_region=True,
        clear_secondary_selection=True,
    )


def _refresh_set_space_text_overlays(session, dirty, refresh_all):
    _clear_common_overlay_visuals(
        session,
        clear_selected_region=True,
        clear_secondary_selection=True,
    )
    if session.selection.is_selected_plan_target("space") and (
        refresh_all or plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE in dirty
    ):
        session.spaces.refresh_selected_space_visuals()


def _refresh_pick_space_region_overlays(session, dirty, refresh_all):
    _clear_common_overlay_visuals(
        session,
        clear_selected_space=True,
        clear_selected_region=True,
        clear_space_region_pick=False,
        clear_secondary_selection=False,
    )
    if (
        refresh_all
        or plan_document_visuals.PLAN_VISUAL_SECONDARY_SELECTION in dirty
        or plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK in dirty
    ):
        from . import spaces as overlay_spaces

        overlay_spaces.sync_secondary_selected_overlays(session)
        overlay_spaces.sync_space_region_pick_overlays(session)


def _refresh_provider_point_overlays(session, dirty, refresh_all):
    _clear_common_overlay_visuals(
        session,
        clear_selected_space=True,
        clear_selected_region=True,
        clear_secondary_selection=True,
    )
    if refresh_all or plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS in dirty:
        from . import providers as overlay_providers

        overlay_providers.sync_provider_overlays(session)
    else:
        from . import providers as overlay_providers

    overlay_providers.sync_provider_point_preview(session)


def _refresh_window_tool_overlays(session):
    _clear_common_overlay_visuals(
        session,
        clear_selected_space=True,
        clear_selected_region=True,
        clear_secondary_selection=True,
        clear_selected_provider_handles=False,
    )


def _refresh_select_tool_overlays(session, dirty, refresh_all):
    from . import openings as overlay_openings
    from . import providers as overlay_providers
    from . import spaces as overlay_spaces
    from . import symbols as overlay_symbols
    from . import walls as overlay_walls

    overlay_spaces.clear_space_region_pick_overlays(session)
    overlay_walls.sync_junction_node_overlays(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_HOVERED_WALL in dirty:
        overlay_walls.sync_hovered_wall_overlay(session)
    overlay_openings.sync_selected_wall_opening_context_overlay(session)
    overlay_walls.sync_hovered_wall_opening_context_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_HOVERED_OPENING in dirty:
        overlay_openings.sync_hovered_opening_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL in dirty:
        overlay_symbols.sync_hovered_symbol_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_HOVERED_PROVIDER in dirty:
        overlay_providers.sync_hovered_provider_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_HOVERED_SPACE in dirty:
        overlay_spaces.sync_hovered_space_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_HOVERED_REGION in dirty:
        overlay_spaces.sync_hovered_region_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_SELECTED_OPENING in dirty:
        overlay_openings.sync_selected_opening_overlay(session)
        overlay_openings.sync_selected_opening_handles(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL in dirty:
        overlay_symbols.sync_selected_symbol_overlay(session)
        overlay_symbols.sync_selected_symbol_handles(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_SELECTED_REGION in dirty:
        overlay_spaces.sync_selected_region_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE in dirty:
        overlay_spaces.sync_selected_space_overlay(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_SECONDARY_SELECTION in dirty:
        overlay_spaces.sync_secondary_selected_overlays(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK in dirty:
        overlay_spaces.clear_space_region_pick_overlays(session)
    if refresh_all or plan_document_visuals.PLAN_VISUAL_WALL_GRIPS in dirty:
        overlay_walls.sync_selected_wall_overlay(session)
        overlay_walls.sync_wall_grips(session)
    provider_overlays_dirty = (
        refresh_all or plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS in dirty
    )
    if provider_overlays_dirty:
        overlay_providers.sync_provider_overlays(session)
    if (
        provider_overlays_dirty
        or refresh_all
        or plan_document_visuals.PLAN_VISUAL_SELECTED_PROVIDER in dirty
    ):
        overlay_providers.sync_selected_provider_overlay(session)
        overlay_providers.sync_selected_provider_handles(session)
    overlay_providers.clear_provider_point_preview(session)


def refresh_plan_overlay_visuals(session, dirty=None):
    if (
        session.lifecycle_state.tearing_down
        or session.lifecycle_state.finishing
        or not session.document_visuals.document_is_alive()
    ):
        return
    dirty = set(dirty or {plan_document_visuals.PLAN_VISUAL_ALL})
    refresh_all = plan_document_visuals.PLAN_VISUAL_ALL in dirty
    if not refresh_all and plan_document_visuals.PLAN_VISUAL_VIEW_SCALE in dirty:
        refresh_plan_overlay_view_scale(session)
        dirty.discard(plan_document_visuals.PLAN_VISUAL_VIEW_SCALE)
        if not dirty:
            return
    if session.current_tool == plan_runtime_tools.PlanTool.JOIN:
        _refresh_join_tool_overlays(session, dirty, refresh_all)
        return
    if session.current_tool == plan_runtime_tools.PlanTool.REGION:
        _refresh_region_tool_overlays(session)
        return
    if session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
        _refresh_set_space_text_overlays(session, dirty, refresh_all)
        return
    if session.current_tool == plan_runtime_tools.PlanTool.PICK_SPACE_REGION:
        _refresh_pick_space_region_overlays(session, dirty, refresh_all)
        return
    if session.current_tool == plan_runtime_tools.PlanTool.PROVIDER_POINT:
        _refresh_provider_point_overlays(session, dirty, refresh_all)
        return
    if session.current_tool == plan_runtime_tools.PlanTool.WINDOW:
        _refresh_window_tool_overlays(session)
        return
    if session.current_tool == plan_runtime_tools.PlanTool.SELECT:
        _refresh_select_tool_overlays(session, dirty, refresh_all)
        return


def finalize_trackers(trackers):
    for tracker in trackers:
        off = getattr(tracker, "off", None)
        try:
            if callable(off):
                off()
        except Exception:
            pass
        try:
            tracker.finalize()
        except Exception:
            pass


def make_plan_line_tracker(DraftTrackers, label, **kwargs):
    tracker = DraftTrackers.lineTracker(**kwargs)
    set_debug_label = getattr(tracker, "setDebugLabel", None)
    if callable(set_debug_label):
        set_debug_label("BimPlanSession:{}".format(label))
    return tracker


def set_plan_line_tracker_width(tracker, width):
    if tracker is None or width is None:
        return
    switch = getattr(tracker, "switch", None)
    if switch is None:
        return
    try:
        separator = switch.getChild(0)
        drawstyle = separator.getChild(0) if separator is not None else None
        if drawstyle is not None and getattr(drawstyle, "lineWidth", None) is not None:
            drawstyle.lineWidth = width
    except Exception:
        return


def sync_segment_overlay_trackers(
    session,
    DraftTrackers,
    *,
    trackers,
    segments,
    label,
    color,
    width,
    clear_fn,
    hover_trackers=None,
    transfer_perf_key="",
):
    transferred = False
    current_trackers = trackers if trackers is not None else []
    current_hover_trackers = hover_trackers if hover_trackers is not None else None
    if len(current_trackers) != len(segments):
        if (
            hover_trackers is not None
            and not current_trackers
            and current_hover_trackers is not None
            and len(current_hover_trackers) == len(segments)
        ):
            current_trackers = current_hover_trackers
            current_hover_trackers = []
            transferred = True
            if transfer_perf_key:
                _perf_count(session, transfer_perf_key)
        else:
            clear_fn()
            current_trackers = []
            for _start, _end in segments:
                tracker = make_plan_line_tracker(
                    DraftTrackers,
                    label,
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                current_trackers.append(tracker)
    for tracker, (start, end) in zip(current_trackers, segments):
        set_plan_line_tracker_width(tracker, width)
        tracker.setColor(color)
        if not transferred:
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
    return current_trackers, current_hover_trackers, transferred
