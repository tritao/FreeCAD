# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall edit interaction control for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = 10.0


def has_active_wall_edit(session):
    return session._is_wall_edit_modal_active() or session._embedded_tool_name == "Wall"


def is_wall_edit_modal_active(session):
    return bool(session._wall_edit_modal_active and session._edit_wall)


def cancel_wall_edit(session, restore=True, refresh=True):
    del restore
    if not session._has_active_wall_edit():
        if refresh:
            session.current_tool = "Select"
            session._refresh_task_panel_status()
        return False

    session._cancel_wall_subtool()

    session.current_tool = "Select"
    session._cancel_pending_edit()
    session._sync_selected_wall_opening_context_overlay()
    if refresh:
        session._refresh_task_panel_status()
    return True


def cancel_wall_subtool(session):
    session._cancel_embedded_tool("Wall")


def start_wall_edit(session, mode):
    with session._plan_perf_trace_span("start_wall_edit"):
        with session._plan_perf_trace_span("start_wall_edit_validate"):
            if not session.is_selected_wall_endpoint_editable():
                FreeCAD.Console.PrintError(
                    translate(
                        "BIM_PlanEdit",
                        "Select a straight wall before using wall grips.\n",
                    )
                )
                return

            wall = session._get_selected_plan_target_object("wall")
            proxy = getattr(wall, "Proxy", None)
            if (
                not proxy
                or not hasattr(proxy, "calc_endpoints")
                or not hasattr(proxy, "set_from_endpoints")
            ):
                return

            endpoints = proxy.calc_endpoints(wall)
            if len(endpoints) != 2:
                return

        with session._plan_perf_trace_span("start_wall_edit_state"):
            session._clear_plan_relation_status()
            session.current_tool = "Move Wall" if mode == "Move" else f"Stretch {mode}"
            session._set_hovered_wall(None)
            session._set_hovered_opening(None)
            session._set_hovered_symbol(None)
            session._set_hovered_provider(None)
            if not session._is_selected_plan_target("wall", wall):
                session._set_selected_plan_target("wall", wall)
            session._clear_selected_wall_overlay()
            session._clear_selected_wall_opening_context_overlay()
            session._wall_edit_modal_active = True
            session._edit_wall = wall
            session._edit_endpoint = mode
            session._edit_endpoints = endpoints

        with session._plan_perf_trace_span("start_wall_edit_queue_opening_clearances"):
            session._wall_edit_opening_clearances = {}
            session._queue_wall_edit_opening_clearances()

        with session._plan_perf_trace_span("start_wall_edit_preview"):
            session._preview_points = list(endpoints)
            session._edit_wall_visibility = None
            try:
                session._edit_wall_visibility = wall.ViewObject.Visibility
                wall.ViewObject.Visibility = False
            except Exception:
                session._edit_wall_visibility = None
            session._clear_wall_grips()
            session._clear_selected_wall_overlay()
            session._sync_wall_edit_preview(session._preview_points, include_opening_preview=False)

        session._queue_wall_edit_task_panel_refresh()
        session._resume_wall_edit_point_pick()


def resume_wall_edit_point_pick(session):
    with session._plan_perf_trace_span("resume_wall_edit_point_pick"):
        if not session._is_wall_edit_modal_active():
            return
        mode = session._edit_endpoint
        title = {
            "Start": translate("BIM_PlanEdit", "Pick new start point"),
            "End": translate("BIM_PlanEdit", "Pick new end point"),
            "Move": translate("BIM_PlanEdit", "Pick new wall midpoint"),
        }.get(mode, translate("BIM_PlanEdit", "Pick wall point"))
        last = session._get_wall_edit_reference_point()

        FreeCAD.activeDraftCommand = session
        if getattr(FreeCADGui, "Snapper", None):
            try:
                with session._plan_perf_trace_span("wall_edit_snapper_set_select_mode"):
                    FreeCADGui.Snapper.setSelectMode(False)
            except Exception:
                pass
        with session._plan_perf_trace_span("wall_edit_focus_suppression"):
            session._set_draft_point_focus_suppressed(True)
        with session._plan_perf_trace_span("wall_edit_snapper_get_point"):
            FreeCADGui.Snapper.getPoint(
                callback=session._finish_wall_edit,
                movecallback=session._update_wall_edit_point_pick,
                last=last,
                title=title,
                noTracker=True,
            )
        with session._plan_perf_trace_span("wall_edit_queue_focus_plan_view"):
            session._queue_focus_plan_view()


def snapshot_wall_hosted_opening_clearances(session, wall, endpoints):
    if not wall or not endpoints or len(endpoints) != 2:
        return {}

    wall_origin = FreeCAD.Vector(endpoints[0])
    wall_axis_u = FreeCAD.Vector(endpoints[1]).sub(wall_origin)
    wall_length = wall_axis_u.Length
    if wall_length < 1e-9:
        return {}
    wall_axis_u.normalize()

    snapshot = {}
    for opening in session._get_wall_hosted_openings(wall):
        proxy = session._get_opening_plan_proxy(
            opening, "get_plan_move_context", "get_plan_center_point"
        )
        if not proxy:
            continue
        context = proxy.get_plan_move_context()
        center = proxy.get_plan_center_point()
        if not context or center is None:
            continue
        half_width = float(context.get("opening_half_width_u") or 0.0)
        center_u = FreeCAD.Vector(center).sub(wall_origin).dot(wall_axis_u)
        snapshot[getattr(opening, "Name", "")] = {
            "center_u": center_u,
            "left_clearance": max(0.0, center_u - half_width),
            "right_clearance": max(0.0, wall_length - (center_u + half_width)),
        }
    return snapshot


def queue_wall_edit_opening_clearances(session):
    if (
        session._tearing_down
        or session._wall_edit_opening_clearances
        or session._wall_edit_opening_clearances_queued
        or session._edit_endpoint not in ("Start", "End")
    ):
        return
    try:
        from PySide import QtCore
    except ImportError:
        return
    session._wall_edit_opening_clearances_queued = True
    QtCore.QTimer.singleShot(0, session._prime_wall_edit_opening_clearances)


def prime_wall_edit_opening_clearances(session):
    session._wall_edit_opening_clearances_queued = False
    if (
        session._tearing_down
        or not session._is_wall_stretch_edit_active()
        or session._wall_edit_opening_clearances
    ):
        return
    with session._plan_perf_trace_event("queued_wall_edit_opening_clearances"):
        session._wall_edit_opening_clearances = session._snapshot_wall_hosted_opening_clearances(
            session._edit_wall,
            session._edit_endpoints,
        )


def ensure_wall_edit_opening_clearances(session, wall, endpoints):
    if session._wall_edit_opening_clearances or session._edit_endpoint not in ("Start", "End"):
        return
    session._wall_edit_opening_clearances_queued = False
    with session._plan_perf_trace_span("ensure_wall_edit_opening_clearances"):
        session._wall_edit_opening_clearances = session._snapshot_wall_hosted_opening_clearances(
            wall,
            endpoints,
        )


def queue_wall_edit_task_panel_refresh(session):
    if session._tearing_down or session._wall_edit_task_panel_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        session._refresh_task_panel_status(selection_only=True)
        return
    session._wall_edit_task_panel_refresh_queued = True
    QtCore.QTimer.singleShot(0, session._flush_wall_edit_task_panel_refresh)


def flush_wall_edit_task_panel_refresh(session):
    session._wall_edit_task_panel_refresh_queued = False
    if session._tearing_down or not session._is_wall_edit_modal_active():
        return
    with session._plan_perf_trace_event("queued_wall_edit_task_panel_refresh"):
        session._refresh_task_panel_status(selection_only=True)


def finish_wall_edit(session, point=None, obj=None):
    del obj

    wall = session._edit_wall
    endpoint = session._edit_endpoint
    new_points = session._compute_wall_edit_points(point)

    if point is None or not wall or not endpoint or not new_points:
        session.current_tool = "Select"
        session._cancel_pending_edit()
        session._refresh_task_panel_status()
        return

    proxy = getattr(wall, "Proxy", None)
    if (
        not proxy
        or not hasattr(proxy, "calc_endpoints")
        or not hasattr(proxy, "set_from_endpoints")
    ):
        session.current_tool = "Select"
        session._cancel_pending_edit()
        session._refresh_task_panel_status()
        return

    session._commit_wall_edit_points(wall, endpoint, proxy, new_points)


def commit_wall_edit_points(session, wall, endpoint, proxy, new_points):
    if not wall or not endpoint or not proxy or not new_points:
        session.current_tool = "Select"
        session._cancel_pending_edit()
        session._refresh_task_panel_status()
        return

    transaction_name = (
        translate("BIM_PlanEdit", "Move Wall")
        if endpoint == "Move"
        else translate("BIM_PlanEdit", "Stretch Wall Endpoint")
    )
    openings_fit = True

    try:
        session.doc.openTransaction(transaction_name)
        proxy.set_from_endpoints(wall, new_points)
        session.doc.recompute()
        openings_fit = session._resolve_wall_hosted_opening_layout(wall)
        if not openings_fit:
            raise RuntimeError("Hosted openings no longer fit within resized wall")
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        if not openings_fit:
            FreeCAD.Console.PrintError(
                translate(
                    "BIM_PlanEdit",
                    "The resized wall cannot contain its hosted openings.\n",
                )
            )
        session.current_tool = "Select"
        session._cancel_pending_edit()
        return
    session._refresh_wall_hosted_opening_footprints(wall)
    session._set_gui_selection_object(wall)
    session.current_tool = "Select"
    session._cancel_pending_edit()
    session._set_selected_plan_target("wall", wall, pending_restore=True)
    session._update_wall_relation_status(wall)
    session._sync_wall_grips()
    session._refresh_task_panel_status()


def start_wall_grip_edit(session, grip_index):
    if grip_index not in (0, 1, 2) or not session.is_selected_wall_endpoint_editable():
        return
    session._start_wall_edit({0: "Start", 1: "End", 2: "Move"}[grip_index])


def activate_wall_grip(session, grip_index, wall=None):
    if wall is None:
        wall = session._get_selected_plan_target_object("wall")
    try:
        from PySide import QtCore
    except ImportError:
        session._activate_wall_grip_now(grip_index, wall)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda wall=wall, grip_index=grip_index: session._activate_wall_grip_now(grip_index, wall),
    )


def activate_wall_grip_now(session, grip_index, wall=None):
    with session._plan_perf_trace_span("activate_wall_grip_now"):
        if session._tearing_down or session.current_tool != "Select" or not wall:
            return
        with session._plan_perf_trace_span("activate_wall_grip_set_target"):
            if not session._is_selected_plan_target("wall", wall):
                session._set_selected_plan_target("wall", wall)
        with session._plan_perf_trace_span("activate_wall_grip_start_edit"):
            session._start_wall_grip_edit(grip_index)


def get_wall_edit_reference_point(session):
    if not session._edit_endpoints or len(session._edit_endpoints) != 2:
        return None
    if session._edit_endpoint == "Move":
        return (session._edit_endpoints[0] + session._edit_endpoints[1]) * 0.5
    if session._edit_endpoint == "Start":
        return session._edit_endpoints[0]
    if session._edit_endpoint == "End":
        return session._edit_endpoints[1]
    return None


def compute_wall_edit_points(session, point):
    endpoint = session._edit_endpoint
    original_endpoints = session._edit_endpoints
    if point is None or not endpoint or not original_endpoints:
        return None

    if endpoint == "Start":
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        projected = axis.dot(point.sub(original_endpoints[1]))
        if projected > -_MIN_WALL_LENGTH:
            return None
        return [original_endpoints[1].add(axis.multiply(projected)), original_endpoints[1]]
    elif endpoint == "End":
        axis = original_endpoints[1].sub(original_endpoints[0]).normalize()
        projected = axis.dot(point.sub(original_endpoints[0]))
        if projected < _MIN_WALL_LENGTH:
            return None
        return [original_endpoints[0], original_endpoints[0].add(axis.multiply(projected))]

    original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
    delta = point.sub(original_midpoint)
    return [original_endpoints[0].add(delta), original_endpoints[1].add(delta)]


def compute_wall_edit_points_from_length(session, length):
    endpoint = session._edit_endpoint
    original_endpoints = session._edit_endpoints
    if endpoint not in ("Start", "End") or not original_endpoints:
        return None

    length = max(float(length), _MIN_WALL_LENGTH)
    axis = original_endpoints[1].sub(original_endpoints[0])
    if axis.Length < _MIN_WALL_LENGTH:
        return None
    axis.normalize()

    if endpoint == "Start":
        end = original_endpoints[1]
        return [end.sub(FreeCAD.Vector(axis).multiply(length)), end]

    start = original_endpoints[0]
    return [start, start.add(FreeCAD.Vector(axis).multiply(length))]
