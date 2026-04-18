# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared overlay management helpers for BIM Plan Edit."""


def _session_is_inactive(session):
    return session._tearing_down or getattr(session, "_finishing", False)


def queue_plan_overlay_visual_refresh(session, visuals, visual_all, visual_selected_space):
    if _session_is_inactive(session):
        return
    dirty = set(visuals) if visuals else {visual_all}
    if visual_all in dirty or visual_selected_space in dirty:
        session._invalidate_selected_space_overlay_cache()
    session._dirty_plan_visuals.update(dirty)
    if session._overlay_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        dirty = session._consume_dirty_plan_visuals()
        session._refresh_plan_overlay_visuals(dirty)
        return
    session._overlay_refresh_queued = True
    QtCore.QTimer.singleShot(0, session._flush_plan_overlay_visual_refresh)


def queue_plan_overlay_view_scale_refresh(session, visual_view_scale, delay_ms):
    if _session_is_inactive(session):
        return
    session._dirty_plan_visuals.add(visual_view_scale)
    if session._overlay_refresh_queued or session._view_scale_overlay_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        dirty = session._consume_dirty_plan_visuals(default_all=False)
        if dirty:
            session._refresh_plan_overlay_visuals(dirty)
        return
    session._view_scale_overlay_refresh_queued = True
    QtCore.QTimer.singleShot(max(0, int(delay_ms)), session._flush_view_scale_overlay_refresh)


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
        session._consume_dirty_plan_visuals(default_all=False)
        return
    dirty = session._consume_dirty_plan_visuals()
    session._refresh_plan_overlay_visuals(dirty)


def flush_view_scale_overlay_refresh(session):
    session._view_scale_overlay_refresh_queued = False
    if _session_is_inactive(session):
        session._consume_dirty_plan_visuals(default_all=False)
        return
    if session._overlay_refresh_queued:
        return
    dirty = session._consume_dirty_plan_visuals(default_all=False)
    if not dirty:
        return
    session._refresh_plan_overlay_visuals(dirty)


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
