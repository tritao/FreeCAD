# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared overlay management helpers for BIM Plan Edit."""

from bimplan import document_visuals as plan_document_visuals

_PLAN_VISUAL_HOVERED_WALL = plan_document_visuals.PLAN_VISUAL_HOVERED_WALL
_PLAN_VISUAL_HOVERED_OPENING = plan_document_visuals.PLAN_VISUAL_HOVERED_OPENING
_PLAN_VISUAL_HOVERED_SYMBOL = plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL
_PLAN_VISUAL_HOVERED_PROVIDER = plan_document_visuals.PLAN_VISUAL_HOVERED_PROVIDER
_PLAN_VISUAL_HOVERED_SPACE = plan_document_visuals.PLAN_VISUAL_HOVERED_SPACE
_PLAN_VISUAL_HOVERED_REGION = plan_document_visuals.PLAN_VISUAL_HOVERED_REGION
_PLAN_VISUAL_SELECTED_PROVIDER = plan_document_visuals.PLAN_VISUAL_SELECTED_PROVIDER
_PLAN_VISUAL_SELECTED_OPENING = plan_document_visuals.PLAN_VISUAL_SELECTED_OPENING
_PLAN_VISUAL_SELECTED_SYMBOL = plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL
_PLAN_VISUAL_SELECTED_SPACE = plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE
_PLAN_VISUAL_SELECTED_REGION = plan_document_visuals.PLAN_VISUAL_SELECTED_REGION
_PLAN_VISUAL_SECONDARY_SELECTION = plan_document_visuals.PLAN_VISUAL_SECONDARY_SELECTION
_PLAN_VISUAL_SPACE_REGION_PICK = plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK
_PLAN_VISUAL_WALL_GRIPS = plan_document_visuals.PLAN_VISUAL_WALL_GRIPS
_PLAN_VISUAL_WALL_EDIT_PREVIEW = plan_document_visuals.PLAN_VISUAL_WALL_EDIT_PREVIEW
_PLAN_VISUAL_PROVIDER_OVERLAYS = plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
_PLAN_VISUAL_VIEW_SCALE = plan_document_visuals.PLAN_VISUAL_VIEW_SCALE
_PLAN_VISUAL_ALL = plan_document_visuals.PLAN_VISUAL_ALL


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _session_is_inactive(session):
    if session._tearing_down or getattr(session, "_finishing", False):
        return True
    document_is_alive = getattr(session, "_document_is_alive", None)
    if callable(document_is_alive):
        return not document_is_alive()
    return False


def queue_plan_overlay_visual_refresh(session, visuals, visual_all, visual_selected_space):
    if _session_is_inactive(session):
        return
    dirty = set(visuals) if visuals else {visual_all}
    if visual_all in dirty or visual_selected_space in dirty:
        session.overlays.invalidate_selected_space_overlay_cache()
    session._dirty_plan_visuals.update(dirty)
    if session._overlay_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        dirty = session.overlays.consume_dirty_plan_visuals()
        session.overlays.refresh_plan_overlay_visuals(dirty)
        return
    session._overlay_refresh_queued = True
    QtCore.QTimer.singleShot(0, session.overlays.flush_plan_overlay_visual_refresh)


def queue_plan_overlay_view_scale_refresh(session, visual_view_scale, delay_ms):
    if _session_is_inactive(session):
        return
    session._dirty_plan_visuals.add(visual_view_scale)
    if session._overlay_refresh_queued or session._view_scale_overlay_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        dirty = session.overlays.consume_dirty_plan_visuals(default_all=False)
        if dirty:
            session.overlays.refresh_plan_overlay_visuals(dirty)
        return
    session._view_scale_overlay_refresh_queued = True
    QtCore.QTimer.singleShot(
        max(0, int(delay_ms)), session.overlays.flush_view_scale_overlay_refresh
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
        session.overlays.consume_dirty_plan_visuals(default_all=False)
        return
    dirty = session.overlays.consume_dirty_plan_visuals()
    session.overlays.refresh_plan_overlay_visuals(dirty)


def flush_view_scale_overlay_refresh(session):
    session._view_scale_overlay_refresh_queued = False
    if _session_is_inactive(session):
        session.overlays.consume_dirty_plan_visuals(default_all=False)
        return
    if session._overlay_refresh_queued:
        return
    dirty = session.overlays.consume_dirty_plan_visuals(default_all=False)
    if not dirty:
        return
    session.overlays.refresh_plan_overlay_visuals(dirty)


def refresh_plan_overlay_view_scale(session):
    with _perf_trace_span(session, "refresh_plan_overlay_view_scale"):
        if session.current_tool == "Join":
            session.overlays.sync_junction_node_overlays()
            if session.hovered_wall:
                session.overlays.sync_hovered_wall_overlay()
            return
        if session.current_tool == "Set Space Text":
            if session.selection.is_selected_plan_target("space"):
                session.overlays.sync_selected_space_overlay()
            return
        if session.current_tool == "Pick Space Region":
            if session._space_region_candidates:
                session.overlays.sync_space_region_pick_overlays()
            if session.selection.get_selected_plan_targets():
                session.overlays.sync_secondary_selected_overlays()
            return
        if session.current_tool == "Provider Point":
            session.overlays.sync_provider_overlays()
            session.overlays.sync_provider_point_preview()
            return
        if session.current_tool != "Select":
            return
        if session.hovered_wall or session.selection.is_selected_plan_target("wall"):
            session.overlays.sync_junction_node_overlays()
        if session.hovered_wall:
            session.overlays.sync_hovered_wall_overlay()
            session.overlays.sync_hovered_wall_opening_context_overlay()
        if session.selection.is_selected_plan_target("wall"):
            session.overlays.sync_selected_wall_overlay()
            session.overlays.sync_selected_wall_opening_context_overlay()
            session.overlays.sync_wall_grips()
        if session.hovered_opening:
            session.overlays.sync_hovered_opening_overlay()
        if session.selection.is_selected_plan_target("opening"):
            session.overlays.sync_selected_opening_overlay()
            session.overlays.sync_selected_opening_handles()
        if session.hovered_symbol:
            session.overlays.sync_hovered_symbol_overlay()
        session.overlays.sync_provider_overlays()
        if session.hovered_provider:
            session.overlays.sync_hovered_provider_overlay()
        if (
            session.selection.is_selected_plan_target("provider")
            or session.status_text.get_provider_selected_objects()
        ):
            session.overlays.sync_selected_provider_overlay()
        if session.selection.is_selected_plan_target("symbol"):
            session.overlays.sync_selected_symbol_overlay()
            session.overlays.sync_selected_symbol_handles()
        if session.hovered_space:
            session.overlays.sync_hovered_space_overlay()
        if session.selection.is_selected_plan_target("space"):
            session.overlays.sync_selected_space_overlay()
        if session.hovered_region:
            session.overlays.sync_hovered_region_overlay()
        if session.selection.is_selected_plan_target("region"):
            session.overlays.sync_selected_region_overlay()
        if session.selection.get_secondary_selected_plan_targets():
            session.overlays.sync_secondary_selected_overlays()


def refresh_plan_overlay_visuals(session, dirty=None):
    if session._tearing_down or session._finishing or not session._document_is_alive():
        return
    dirty = set(dirty or {_PLAN_VISUAL_ALL})
    refresh_all = _PLAN_VISUAL_ALL in dirty
    if not refresh_all and _PLAN_VISUAL_VIEW_SCALE in dirty:
        session.overlays.refresh_plan_overlay_view_scale()
        dirty.discard(_PLAN_VISUAL_VIEW_SCALE)
        if not dirty:
            return
    if session.current_tool == "Join":
        if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
            session.overlays.sync_hovered_wall_overlay()
        session.overlays.sync_junction_node_overlays()
        session.overlays.clear_hovered_wall_opening_context_overlay()
        session.overlays.clear_hovered_opening_overlay()
        session.overlays.clear_hovered_symbol_overlay()
        session.overlays.clear_hovered_provider_overlay()
        session.overlays.clear_hovered_space_overlay()
        session.overlays.clear_hovered_region_overlay()
        session.overlays.clear_space_region_pick_overlays()
        session.overlays.clear_selected_provider_overlay()
        session.overlays.clear_selected_provider_handles()
        session.overlays.clear_selected_opening_overlay()
        session.overlays.clear_selected_symbol_overlay()
        session.overlays.clear_selected_space_overlay()
        session.overlays.clear_selected_region_overlay()
        session.overlays.clear_provider_overlays()
        session.overlays.clear_provider_point_preview()
        session.overlays.clear_secondary_selected_overlays()
        session.overlays.clear_selected_opening_handles()
        session.overlays.clear_selected_symbol_handles()
        session.overlays.clear_selected_wall_opening_context_overlay()
        session.overlays.clear_wall_grips()
        session.overlays.clear_selected_wall_overlay()
        return
    if session.current_tool == "Region":
        session.overlays.clear_junction_node_overlays()
        session.overlays.clear_hovered_wall_overlay()
        session.overlays.clear_hovered_wall_opening_context_overlay()
        session.overlays.clear_hovered_opening_overlay()
        session.overlays.clear_hovered_symbol_overlay()
        session.overlays.clear_hovered_provider_overlay()
        session.overlays.clear_hovered_space_overlay()
        session.overlays.clear_hovered_region_overlay()
        session.overlays.clear_space_region_pick_overlays()
        session.overlays.clear_selected_provider_overlay()
        session.overlays.clear_selected_provider_handles()
        session.overlays.clear_selected_opening_overlay()
        session.overlays.clear_selected_symbol_overlay()
        session.overlays.clear_selected_space_overlay()
        session.overlays.clear_selected_region_overlay()
        session.overlays.clear_provider_overlays()
        session.overlays.clear_provider_point_preview()
        session.overlays.clear_secondary_selected_overlays()
        session.overlays.clear_selected_opening_handles()
        session.overlays.clear_selected_symbol_handles()
        session.overlays.clear_selected_wall_opening_context_overlay()
        session.overlays.clear_wall_grips()
        session.overlays.clear_selected_wall_overlay()
        return
    if session.current_tool == "Set Space Text":
        session.overlays.clear_junction_node_overlays()
        session.overlays.clear_hovered_wall_overlay()
        session.overlays.clear_hovered_wall_opening_context_overlay()
        session.overlays.clear_hovered_opening_overlay()
        session.overlays.clear_hovered_symbol_overlay()
        session.overlays.clear_hovered_provider_overlay()
        session.overlays.clear_hovered_space_overlay()
        session.overlays.clear_hovered_region_overlay()
        session.overlays.clear_space_region_pick_overlays()
        session.overlays.clear_selected_provider_overlay()
        session.overlays.clear_selected_provider_handles()
        session.overlays.clear_selected_opening_overlay()
        session.overlays.clear_selected_symbol_overlay()
        session.overlays.clear_selected_region_overlay()
        session.overlays.clear_provider_overlays()
        session.overlays.clear_provider_point_preview()
        session.overlays.clear_secondary_selected_overlays()
        session.overlays.clear_selected_opening_handles()
        session.overlays.clear_selected_symbol_handles()
        session.overlays.clear_selected_wall_opening_context_overlay()
        session.overlays.clear_wall_grips()
        session.overlays.clear_selected_wall_overlay()
        if session.selection.is_selected_plan_target("space") and (
            refresh_all or _PLAN_VISUAL_SELECTED_SPACE in dirty
        ):
            session.spaces.refresh_selected_space_visuals()
        return
    if session.current_tool == "Pick Space Region":
        session.overlays.clear_junction_node_overlays()
        session.overlays.clear_hovered_wall_overlay()
        session.overlays.clear_hovered_wall_opening_context_overlay()
        session.overlays.clear_hovered_opening_overlay()
        session.overlays.clear_hovered_symbol_overlay()
        session.overlays.clear_hovered_provider_overlay()
        session.overlays.clear_hovered_space_overlay()
        session.overlays.clear_hovered_region_overlay()
        session.overlays.clear_selected_provider_overlay()
        session.overlays.clear_selected_provider_handles()
        session.overlays.clear_selected_opening_overlay()
        session.overlays.clear_selected_symbol_overlay()
        session.overlays.clear_selected_space_overlay()
        session.overlays.clear_selected_region_overlay()
        session.overlays.clear_provider_overlays()
        session.overlays.clear_provider_point_preview()
        session.overlays.clear_selected_opening_handles()
        session.overlays.clear_selected_symbol_handles()
        session.overlays.clear_selected_wall_opening_context_overlay()
        session.overlays.clear_wall_grips()
        session.overlays.clear_selected_wall_overlay()
        if (
            refresh_all
            or _PLAN_VISUAL_SECONDARY_SELECTION in dirty
            or _PLAN_VISUAL_SPACE_REGION_PICK in dirty
        ):
            session.overlays.sync_secondary_selected_overlays()
            session.overlays.sync_space_region_pick_overlays()
        return
    if session.current_tool == "Provider Point":
        session.overlays.clear_junction_node_overlays()
        session.overlays.clear_hovered_wall_overlay()
        session.overlays.clear_hovered_wall_opening_context_overlay()
        session.overlays.clear_hovered_opening_overlay()
        session.overlays.clear_hovered_symbol_overlay()
        session.overlays.clear_hovered_provider_overlay()
        session.overlays.clear_hovered_space_overlay()
        session.overlays.clear_hovered_region_overlay()
        session.overlays.clear_space_region_pick_overlays()
        session.overlays.clear_selected_provider_overlay()
        session.overlays.clear_selected_provider_handles()
        session.overlays.clear_selected_opening_overlay()
        session.overlays.clear_selected_symbol_overlay()
        session.overlays.clear_selected_space_overlay()
        session.overlays.clear_selected_region_overlay()
        session.overlays.clear_secondary_selected_overlays()
        session.overlays.clear_selected_opening_handles()
        session.overlays.clear_selected_symbol_handles()
        session.overlays.clear_selected_wall_opening_context_overlay()
        session.overlays.clear_wall_grips()
        session.overlays.clear_selected_wall_overlay()
        if refresh_all or _PLAN_VISUAL_PROVIDER_OVERLAYS in dirty:
            session.overlays.sync_provider_overlays()
        session.overlays.sync_provider_point_preview()
        return
    if session.current_tool == "Window":
        session.overlays.clear_junction_node_overlays()
        session.overlays.clear_hovered_wall_overlay()
        session.overlays.clear_hovered_wall_opening_context_overlay()
        session.overlays.clear_hovered_opening_overlay()
        session.overlays.clear_hovered_symbol_overlay()
        session.overlays.clear_hovered_provider_overlay()
        session.overlays.clear_hovered_space_overlay()
        session.overlays.clear_hovered_region_overlay()
        session.overlays.clear_space_region_pick_overlays()
        session.overlays.clear_selected_provider_overlay()
        session.overlays.clear_selected_opening_overlay()
        session.overlays.clear_selected_symbol_overlay()
        session.overlays.clear_selected_space_overlay()
        session.overlays.clear_selected_region_overlay()
        session.overlays.clear_provider_overlays()
        session.overlays.clear_provider_point_preview()
        session.overlays.clear_secondary_selected_overlays()
        session.overlays.clear_selected_opening_handles()
        session.overlays.clear_selected_symbol_handles()
        session.overlays.clear_selected_wall_opening_context_overlay()
        session.overlays.clear_wall_grips()
        session.overlays.clear_selected_wall_overlay()
        return
    if session.current_tool == "Select":
        session.overlays.clear_space_region_pick_overlays()
        session.overlays.sync_junction_node_overlays()
        if refresh_all or _PLAN_VISUAL_HOVERED_WALL in dirty:
            session.overlays.sync_hovered_wall_overlay()
        session.overlays.sync_selected_wall_opening_context_overlay()
        session.overlays.sync_hovered_wall_opening_context_overlay()
        if refresh_all or _PLAN_VISUAL_HOVERED_OPENING in dirty:
            session.overlays.sync_hovered_opening_overlay()
        if refresh_all or _PLAN_VISUAL_HOVERED_SYMBOL in dirty:
            session.overlays.sync_hovered_symbol_overlay()
        if refresh_all or _PLAN_VISUAL_HOVERED_PROVIDER in dirty:
            session.overlays.sync_hovered_provider_overlay()
        if refresh_all or _PLAN_VISUAL_HOVERED_SPACE in dirty:
            session.overlays.sync_hovered_space_overlay()
        if refresh_all or _PLAN_VISUAL_HOVERED_REGION in dirty:
            session.overlays.sync_hovered_region_overlay()
        if refresh_all or _PLAN_VISUAL_SELECTED_OPENING in dirty:
            session.overlays.sync_selected_opening_overlay()
            session.overlays.sync_selected_opening_handles()
        if refresh_all or _PLAN_VISUAL_SELECTED_SYMBOL in dirty:
            session.overlays.sync_selected_symbol_overlay()
            session.overlays.sync_selected_symbol_handles()
        if refresh_all or _PLAN_VISUAL_SELECTED_REGION in dirty:
            session.overlays.sync_selected_region_overlay()
        if refresh_all or _PLAN_VISUAL_SELECTED_SPACE in dirty:
            session.overlays.sync_selected_space_overlay()
        if refresh_all or _PLAN_VISUAL_SECONDARY_SELECTION in dirty:
            session.overlays.sync_secondary_selected_overlays()
        if refresh_all or _PLAN_VISUAL_SPACE_REGION_PICK in dirty:
            session.overlays.clear_space_region_pick_overlays()
        if refresh_all or _PLAN_VISUAL_WALL_GRIPS in dirty:
            session.overlays.sync_selected_wall_overlay()
            session.overlays.sync_wall_grips()
        provider_overlays_dirty = refresh_all or _PLAN_VISUAL_PROVIDER_OVERLAYS in dirty
        if provider_overlays_dirty:
            session.overlays.sync_provider_overlays()
        if provider_overlays_dirty or refresh_all or _PLAN_VISUAL_SELECTED_PROVIDER in dirty:
            session.overlays.sync_selected_provider_overlay()
            session.overlays.sync_selected_provider_handles()
        session.overlays.clear_provider_point_preview()
        return


def finalize_trackers(trackers):
    for tracker in trackers:
        try:
            if hasattr(tracker, "off"):
                tracker.off()
        except Exception:
            pass
        try:
            tracker.finalize()
        except Exception:
            pass


def make_plan_line_tracker(DraftTrackers, label, **kwargs):
    tracker = DraftTrackers.lineTracker(**kwargs)
    if hasattr(tracker, "setDebugLabel"):
        tracker.setDebugLabel("BimPlanSession:{}".format(label))
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
        if drawstyle is not None and hasattr(drawstyle, "lineWidth"):
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
                tracker = session.overlays.make_plan_line_tracker(
                    DraftTrackers,
                    label,
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                current_trackers.append(tracker)
    for tracker, (start, end) in zip(current_trackers, segments):
        session.overlays.set_plan_line_tracker_width(tracker, width)
        tracker.setColor(color)
        if not transferred:
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
    return current_trackers, current_hover_trackers, transferred
