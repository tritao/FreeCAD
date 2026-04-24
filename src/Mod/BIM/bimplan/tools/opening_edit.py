# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opening edit interaction helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate

OPENING_MOVE_ANCHORS = ("center", "left", "right")


def get_selected_opening_edit_handles(session, opening):
    proxy = session._get_opening_view_proxy(opening, "get_plan_edit_handles")
    if not proxy:
        return []
    return list(proxy.get_plan_edit_handles() or [])


def get_opening_plan_proxy(session, opening, *attrs):
    if not opening:
        return None
    proxy = getattr(opening, "Proxy", None)
    if proxy and all(hasattr(proxy, attr) for attr in attrs):
        return proxy
    return session._get_opening_view_proxy(opening, *attrs)


def get_opening_view_proxy(session, opening, *attrs):
    if not opening:
        return None
    view_object = getattr(opening, "ViewObject", None)
    proxy = getattr(view_object, "Proxy", None)
    if not proxy:
        return None
    for attr in attrs:
        if not hasattr(proxy, attr):
            return None
    return proxy


def project_opening_handle_point(session, opening, handle, point):
    if point is None or not opening or getattr(handle, "role", None) != "move":
        return point
    proxy = session._get_opening_plan_proxy(opening, "project_point_to_host_axis")
    if not proxy:
        return point
    return proxy.project_point_to_host_axis(point, anchor=session._edit_opening_move_anchor)


def get_opening_move_anchor_modes(session, opening):
    proxy = session._get_opening_plan_proxy(opening, "get_plan_move_anchor_modes")
    if not proxy:
        return OPENING_MOVE_ANCHORS
    modes = tuple(proxy.get_plan_move_anchor_modes() or ())
    return modes or OPENING_MOVE_ANCHORS


def execute_opening_handle(session, opening, handle_index, point=None):
    proxy = session._get_opening_view_proxy(opening, "execute_plan_edit_handle")
    if not proxy:
        return False
    return bool(
        proxy.execute_plan_edit_handle(
            handle_index,
            point,
            anchor=session._edit_opening_move_anchor,
        )
    )


def get_opening_move_preview_state(session, opening, point):
    if not opening or point is None:
        return None
    proxy = session._get_opening_view_proxy(opening, "get_plan_move_preview_state")
    if not proxy:
        return None
    return proxy.get_plan_move_preview_state(point, anchor=session._edit_opening_move_anchor)


def sync_opening_move_preview(session, opening, point):
    session._clear_opening_move_preview()
    if session.current_tool != "Move Opening" or not opening or point is None:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    preview_state = session._get_opening_move_preview_state(opening, point)
    if not preview_state:
        return

    preview_color = (0.12, 0.38, 0.95)
    for polyline in preview_state.get("polylines", []):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = session.overlays.make_plan_line_tracker(
                DraftTrackers,
                "opening-move-preview:{}".format(getattr(opening, "Name", "unknown")),
                scolor=preview_color,
                swidth=session.viewport.scaled_line_width(3),
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            session._opening_move_preview_trackers.append(tracker)

    guide_start = preview_state.get("guide_start")
    guide_end = preview_state.get("guide_end")
    if guide_start is None or guide_end is None:
        return

    guide = session.overlays.make_plan_line_tracker(
        DraftTrackers,
        "opening-move-guide:{}".format(getattr(opening, "Name", "unknown")),
        dotted=True,
        scolor=preview_color,
        swidth=session.viewport.scaled_line_width(1),
        ontop=True,
    )
    guide.p1(guide_start)
    guide.p2(guide_end)
    guide.on()
    session._opening_move_preview_trackers.append(guide)

    try:
        dim = DraftTrackers.archDimTracker(mode=1)
    except Exception:
        return
    dim.dimnode.textColor.setValue(preview_color)
    dim.offset = session._get_opening_move_readout_offset(opening)
    dim.p1(guide_start)
    dim.p2(guide_end)
    dim.on()
    session._opening_move_preview_trackers.append(dim)


def clear_opening_move_preview(session):
    session.overlays.finalize_trackers(session._opening_move_preview_trackers)
    session._opening_move_preview_trackers = []


def cycle_opening_move_anchor(session):
    if session.current_tool != "Move Opening":
        return False
    anchor_modes = session._get_opening_move_anchor_modes(session._edit_opening)
    try:
        current_index = anchor_modes.index(session._edit_opening_move_anchor)
    except ValueError:
        current_index = 0
    session._edit_opening_move_anchor = anchor_modes[(current_index + 1) % len(anchor_modes)]
    return True


def refresh_opening_move_preview_from_raw_point(session):
    opening = session._edit_opening
    handle_index = session._edit_opening_handle_index
    if not opening or handle_index is None:
        return
    handles = session._get_selected_opening_edit_handles(opening)
    if handle_index < 0 or handle_index >= len(handles):
        return
    handle = handles[handle_index]
    raw_point = session._edit_opening_move_raw_point
    if raw_point is None:
        raw_point = handle.point
    point = session._project_opening_handle_point(opening, handle, raw_point)
    session._sync_opening_move_preview(opening, point)


def queue_opening_move_initial_preview(session, opening, point):
    def run_preview():
        with session._plan_perf_trace_event("queued_opening_move_initial_preview"):
            session._sync_opening_move_preview(opening, point)

    try:
        from PySide import QtCore
    except ImportError:
        run_preview()
        return
    QtCore.QTimer.singleShot(0, run_preview)


def activate_opening_handle(session, opening, handle_index):
    try:
        from PySide import QtCore
    except ImportError:
        session._activate_opening_handle_now(opening, handle_index)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda: session._activate_opening_handle_now(opening, handle_index),
    )


def activate_opening_handle_now(session, opening, handle_index):
    with session._plan_perf_trace_span("activate_opening_handle_now"):
        if session._tearing_down or not opening:
            return
        with session._plan_perf_trace_span("activate_opening_handle_set_target"):
            session._set_selected_plan_target("opening", opening)
            session.overlays.clear_wall_grips()
        with session._plan_perf_trace_span("activate_opening_handle_get_handles"):
            handles = session._get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            return
        handle = handles[handle_index]
        if handle.interaction == "point_pick":
            with session._plan_perf_trace_span("activate_opening_handle_start_point_pick"):
                session._start_opening_handle_point_pick(opening, handle_index, handle)
        else:
            with session._plan_perf_trace_span("activate_opening_handle_execute"):
                session._execute_selected_opening_handle(opening, handle_index, handle)


def start_opening_handle_point_pick(session, opening, handle_index, handle):
    with session._plan_perf_trace_span("start_opening_handle_point_pick"):
        if not opening:
            return
        with session._plan_perf_trace_span("start_opening_handle_state"):
            session.current_tool = "Move Opening"
            session._set_hovered_wall(None)
            session._set_hovered_opening(None)
            session.overlays.sync_secondary_selected_overlays()
            session._edit_opening = opening
            session._edit_opening_handle_index = handle_index
            session._edit_opening_move_anchor = "center"
            session._edit_opening_move_raw_point = FreeCAD.Vector(handle.point)
            session.overlays.clear_selected_opening_overlay()
            session.overlays.clear_selected_opening_handles()
        with session._plan_perf_trace_span("start_opening_handle_preview"):
            queue_opening_move_initial_preview(session, opening, handle.point)
        session._refresh_task_panel_status(selection_only=True)
        FreeCAD.activeDraftCommand = session
        with session._plan_perf_trace_span("opening_handle_push_snap_profile"):
            session._push_opening_move_snap_profile()
        with session._plan_perf_trace_span("opening_handle_focus_suppression"):
            session._set_draft_point_focus_suppressed(True)
        with session._plan_perf_trace_span("opening_handle_snapper_get_point"):
            FreeCADGui.Snapper.getPoint(
                last=handle.point,
                callback=session._finish_opening_handle_point_pick,
                movecallback=session._update_opening_handle_point_pick,
                title=handle.title or translate("BIM_PlanEdit", "Pick new opening position"),
                noTracker=True,
            )
        with session._plan_perf_trace_span("opening_handle_queue_focus_plan_view"):
            session.viewport.queue_focus_plan_view()


def update_opening_handle_point_pick(session, point=None, snap_info=None):
    del snap_info
    opening = session._edit_opening
    handle_index = session._edit_opening_handle_index
    if not opening or handle_index is None:
        session._clear_opening_move_preview()
        return
    handles = session._get_selected_opening_edit_handles(opening)
    if handle_index < 0 or handle_index >= len(handles):
        session._clear_opening_move_preview()
        return
    handle = handles[handle_index]
    session._edit_opening_move_raw_point = FreeCAD.Vector(point) if point is not None else None
    point = session._project_opening_handle_point(opening, handle, point)
    session._sync_opening_move_preview(opening, point)


def finish_opening_handle_point_pick(session, point=None, obj=None):
    del obj
    opening = session._edit_opening
    handle_index = session._edit_opening_handle_index
    session._edit_opening = None
    session._edit_opening_handle_index = None
    session._pop_opening_move_snap_profile()
    FreeCAD.activeDraftCommand = None
    session._clear_opening_move_preview()
    session._edit_opening_move_raw_point = None

    if point is None or not opening:
        session.current_tool = "Select"
        session._edit_opening_move_anchor = "center"
        session.overlays.sync_selected_opening_overlay()
        session.overlays.sync_selected_opening_handles()
        session._refresh_task_panel_status()
        return

    handles = session._get_selected_opening_edit_handles(opening)
    if handle_index is None or handle_index < 0 or handle_index >= len(handles):
        session.current_tool = "Select"
        session._edit_opening_move_anchor = "center"
        session._refresh_task_panel_status()
        return
    handle = handles[handle_index]
    point = session._project_opening_handle_point(opening, handle, point)

    try:
        session.doc.openTransaction(handle.transaction or translate("BIM_PlanEdit", "Edit Opening"))
        moved = session._execute_opening_handle(opening, handle_index, point)
        if not moved:
            raise RuntimeError("Unable to execute opening handle")
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        session._edit_opening_move_anchor = "center"
        session._restore_selected_opening(opening)
        return

    session._edit_opening_move_anchor = "center"
    session.current_tool = "Select"
    session._refresh_task_panel_status()
    session._queue_restore_selected_opening(opening)


def cancel_opening_handle_point_pick(session):
    opening = session._edit_opening
    session._edit_opening = None
    session._edit_opening_handle_index = None
    session._stop_snapper()
    session._pop_opening_move_snap_profile()
    FreeCAD.activeDraftCommand = None
    session._clear_opening_move_preview()
    session._edit_opening_move_anchor = "center"
    session._edit_opening_move_raw_point = None
    session.current_tool = "Select"
    if opening:
        session._set_selected_plan_target("opening", opening, pending_restore=True)
    session.overlays.sync_selected_opening_overlay()
    session.overlays.sync_selected_opening_handles()
    session._refresh_task_panel_status()


def restore_selected_opening(session, opening):
    session.current_tool = "Select"
    if opening:
        session._set_selected_plan_target("opening", opening, pending_restore=True)
    else:
        session._set_selected_plan_target()
    if not opening:
        session.overlays.sync_selected_opening_overlay()
        session.overlays.sync_selected_opening_handles()
        session._refresh_task_panel_status()
        return
    session._set_gui_selection_object(opening)
    session.overlays.sync_selected_opening_overlay()
    session.overlays.sync_selected_opening_handles()
    session._refresh_task_panel_status()


def queue_restore_selected_opening(session, opening):
    try:
        from PySide import QtCore
    except ImportError:
        session._restore_selected_opening(opening)
        return
    QtCore.QTimer.singleShot(0, lambda: session._restore_selected_opening(opening))


def execute_selected_opening_handle(session, opening, handle_index, handle):
    try:
        session.doc.openTransaction(handle.transaction or translate("BIM_PlanEdit", "Edit Opening"))
        executed = session._execute_opening_handle(opening, handle_index)
        if not executed:
            raise RuntimeError("Unable to execute opening handle")
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return
    session._set_selected_plan_target("opening", opening, pending_restore=True)
    session.overlays.sync_selected_opening_overlay()
    session.overlays.sync_selected_opening_handles()
