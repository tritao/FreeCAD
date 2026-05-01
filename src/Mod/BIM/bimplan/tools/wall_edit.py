# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall edit interaction control for BIM Plan Edit."""

from contextlib import nullcontext

import FreeCAD
import FreeCADGui
from bimplan.runtime import capabilities as runtime_capabilities
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.transactions import PlanEditTransaction

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = 10.0


def _wall_edit_state(session):
    return session.wall_edit_state


def _interaction_state(session):
    return session.interaction_state


def _get_callable_attr(obj, attr_name):
    return runtime_capabilities.get_callable(obj, attr_name)


def _get_wall_endpoint_proxy(wall):
    proxy = getattr(wall, "Proxy", None)
    calc_endpoints = _get_callable_attr(proxy, "calc_endpoints")
    set_from_endpoints = _get_callable_attr(proxy, "set_from_endpoints")
    if calc_endpoints is None or set_from_endpoints is None:
        return None
    return proxy


def _tracker_supports_edit(tracker):
    return _get_callable_attr(tracker, "startEdit") is not None


def _tracker_is_in_edit(tracker):
    is_in_edit = _get_callable_attr(tracker, "isInEdit")
    return bool(is_in_edit and is_in_edit())


def _focus_tracker_spinbox(tracker):
    label = getattr(tracker, "label", None)
    focus_to_spinbox = _get_callable_attr(label, "setFocusToSpinbox")
    if focus_to_spinbox is not None:
        focus_to_spinbox()


def _stop_tracker_edit(tracker):
    stop_edit = _get_callable_attr(tracker, "stopEdit")
    if stop_edit is not None:
        stop_edit()


def _tracker_update_points(tracker, start, end, *, sync_spinbox):
    update_points = _get_callable_attr(tracker, "updatePoints")
    if update_points is not None:
        update_points(start, end, sync_spinbox=sync_spinbox)
        return
    tracker.p1(start)
    tracker.p2(end)


def _set_editing_canceled_callback(dim, callback):
    set_callback = _get_callable_attr(dim, "setEditingCanceledCallback")
    if set_callback is not None:
        set_callback(callback)


def _supports_value_changed_callback(dim):
    return _get_callable_attr(dim, "setValueChangedCallback") is not None


def _set_dim_color(dim, readout_color):
    dimnode = getattr(dim, "dimnode", None)
    text_color = getattr(dimnode, "textColor", None) if dimnode is not None else None
    set_value = _get_callable_attr(text_color, "setValue")
    if set_value is not None:
        set_value(readout_color)
        return
    dim.setColor(readout_color)


def has_active_wall_edit(session):
    return (
        is_wall_edit_modal_active(session)
        or _interaction_state(session).embedded_tool_name == "Wall"
    )


def is_wall_edit_modal_active(session):
    state = _wall_edit_state(session)
    return bool(state.wall_edit_modal_active and state.edit_wall)


def is_selected_wall_endpoint_editable(session):
    wall = session.selection.state.get_selected_plan_target_object("wall")
    if not wall:
        return False
    if _get_wall_endpoint_proxy(wall) is None:
        return False
    base = getattr(wall, "Base", None)
    if not base:
        return True
    try:
        shape = getattr(base, "Shape", None)
        edges = tuple(getattr(shape, "Edges", ()) or ())
        if len(edges) == 1 and not bool(getattr(edges[0], "Closed", False)):
            return True

        import Draft

        return Draft.getType(base) in {"Line", "BezCurve"}
    except Exception:
        return False


def cancel_wall_edit(session, restore=True, refresh=True):
    if not has_active_wall_edit(session):
        if refresh:
            session.current_tool = "Select"
            session.task_panels.refresh_task_panel_status()
        return False

    cancel_wall_subtool(session)

    session.current_tool = "Select"
    session.lifecycle.cancel_pending_edit(restore_wall_visibility=restore)
    session.wall_relations.restore_selected_wall_relation_status()
    session.overlays.openings.sync_selected_wall_opening_context_overlay()
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return True


def cancel_wall_subtool(session):
    session.embedded_tools.cancel("Wall")


def _validate_wall_edit_start(session):
    if not is_selected_wall_endpoint_editable(session):
        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "Select a straight wall before using wall grips.\n",
            )
        )
        return None, None

    wall = session.selection.state.get_selected_plan_target_object("wall")
    proxy = _get_wall_endpoint_proxy(wall)
    if proxy is None:
        return None, None

    endpoints = proxy.calc_endpoints(wall)
    if len(endpoints) != 2:
        return None, None
    return wall, endpoints


def _set_wall_edit_start_state(session, wall, endpoints, mode):
    state = _wall_edit_state(session)
    state.wall_edit_generation += 1
    session.wall_relations.clear_plan_relation_status()
    session.current_tool = "Move Wall" if mode == "Move" else f"Stretch {mode}"
    session.selection.hover.set_hovered_wall(None)
    session.selection.hover.set_hovered_opening(None)
    session.selection.hover.set_hovered_symbol(None)
    session.selection.hover.set_hovered_provider(None)
    if not session.selection.state.is_selected_plan_target("wall", wall):
        session.selection.state.set_selected_plan_target("wall", wall)
    session.overlays.walls.clear_selected_wall_overlay()
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    state.wall_edit_modal_active = True
    state.edit_wall = wall
    state.edit_endpoint = mode
    state.edit_endpoints = endpoints


def _queue_wall_edit_start_opening_clearances(session, wall, endpoints):
    state = _wall_edit_state(session)
    state.wall_edit_opening_clearances = {}
    state.wall_edit_opening_clearances_queued = False
    if state.edit_endpoint not in ("Start", "End"):
        return
    with session.performance.plan_perf_trace_span("snapshot_wall_edit_opening_clearances"):
        state.wall_edit_opening_clearances = snapshot_wall_hosted_opening_clearances(
            session,
            wall,
            endpoints,
        )


def _prepare_wall_edit_preview(session, wall, endpoints):
    state = _wall_edit_state(session)
    state.preview_points = list(endpoints)
    state.edit_wall_visibility = None
    try:
        state.edit_wall_visibility = wall.ViewObject.Visibility
        wall.ViewObject.Visibility = False
    except Exception:
        state.edit_wall_visibility = None
    session.overlays.walls.clear_wall_grips()
    session.overlays.walls.clear_selected_wall_overlay()
    sync_wall_edit_preview(session, state.preview_points, include_opening_preview=False)


def start_wall_edit(session, mode):
    with session.performance.plan_perf_trace_span("start_wall_edit"):
        with session.performance.plan_perf_trace_span("start_wall_edit_validate"):
            wall, endpoints = _validate_wall_edit_start(session)
            if wall is None or endpoints is None:
                return

        with session.performance.plan_perf_trace_span("start_wall_edit_state"):
            _set_wall_edit_start_state(session, wall, endpoints, mode)

        with session.performance.plan_perf_trace_span("start_wall_edit_queue_opening_clearances"):
            _queue_wall_edit_start_opening_clearances(session, wall, endpoints)

        with session.performance.plan_perf_trace_span("start_wall_edit_preview"):
            _prepare_wall_edit_preview(session, wall, endpoints)

        queue_wall_edit_task_panel_refresh(session)
        resume_wall_edit_point_pick(session)


def resume_wall_edit_point_pick(session):
    with session.performance.plan_perf_trace_span("resume_wall_edit_point_pick"):
        state = _wall_edit_state(session)
        if not is_wall_edit_modal_active(session):
            return
        mode = state.edit_endpoint
        title = {
            "Start": translate("BIM_PlanEdit", "Pick new start point"),
            "End": translate("BIM_PlanEdit", "Pick new end point"),
            "Move": translate("BIM_PlanEdit", "Pick new wall midpoint"),
        }.get(mode, translate("BIM_PlanEdit", "Pick wall point"))
        last = get_wall_edit_reference_point(session)

        session.snap.set_active_draft_command()
        if getattr(FreeCADGui, "Snapper", None):
            try:
                with session.performance.plan_perf_trace_span("wall_edit_snapper_set_select_mode"):
                    FreeCADGui.Snapper.setSelectMode(False)
            except Exception:
                pass
        with session.performance.plan_perf_trace_span("wall_edit_focus_suppression"):
            session.snap.set_point_focus_suppressed(True)
        with session.performance.plan_perf_trace_span("wall_edit_snapper_get_point"):
            FreeCADGui.Snapper.getPoint(
                callback=lambda point=None, obj=None: finish_wall_edit(
                    session, point=point, obj=obj
                ),
                movecallback=lambda point=None, obj=None: update_wall_edit_point_pick(
                    session,
                    point=point,
                    snap_info=obj,
                ),
                last=last,
                title=title,
                noTracker=True,
            )
        with session.performance.plan_perf_trace_span("wall_edit_queue_focus_plan_view"):
            session.viewport.queue_focus_plan_view()


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
    for opening in session.openings.get_wall_hosted_openings(wall):
        proxy = session.openings.get_opening_plan_proxy(
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
    state = _wall_edit_state(session)
    if (
        session.lifecycle_state.tearing_down
        or state.wall_edit_opening_clearances
        or state.wall_edit_opening_clearances_queued
        or state.edit_endpoint not in ("Start", "End")
    ):
        return
    try:
        from PySide import QtCore
    except ImportError:
        return
    state.wall_edit_opening_clearances_queued = True
    QtCore.QTimer.singleShot(0, lambda: prime_wall_edit_opening_clearances(session))


def prime_wall_edit_opening_clearances(session):
    state = _wall_edit_state(session)
    state.wall_edit_opening_clearances_queued = False
    if (
        session.lifecycle_state.tearing_down
        or not is_wall_stretch_edit_active(session)
        or state.wall_edit_opening_clearances
    ):
        return
    with session.performance.plan_perf_trace_event("queued_wall_edit_opening_clearances"):
        state.wall_edit_opening_clearances = snapshot_wall_hosted_opening_clearances(
            session,
            state.edit_wall,
            state.edit_endpoints,
        )


def ensure_wall_edit_opening_clearances(session, wall, endpoints):
    state = _wall_edit_state(session)
    if state.wall_edit_opening_clearances or state.edit_endpoint not in ("Start", "End"):
        return
    state.wall_edit_opening_clearances_queued = False
    with session.performance.plan_perf_trace_span("ensure_wall_edit_opening_clearances"):
        state.wall_edit_opening_clearances = snapshot_wall_hosted_opening_clearances(
            session,
            wall,
            endpoints,
        )


def queue_wall_edit_task_panel_refresh(session):
    state = _wall_edit_state(session)
    if session.lifecycle_state.tearing_down or state.wall_edit_task_panel_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        session.task_panels.refresh_task_panel_status(reason="selection")
        return
    state.wall_edit_task_panel_refresh_queued = True
    QtCore.QTimer.singleShot(0, lambda: flush_wall_edit_task_panel_refresh(session))


def flush_wall_edit_task_panel_refresh(session):
    _wall_edit_state(session).wall_edit_task_panel_refresh_queued = False
    if session.lifecycle_state.tearing_down or not is_wall_edit_modal_active(session):
        return
    with session.performance.plan_perf_trace_event("queued_wall_edit_task_panel_refresh"):
        session.task_panels.refresh_task_panel_status(reason="selection")


def finish_wall_edit(session, point=None, obj=None):
    del obj

    state = _wall_edit_state(session)
    wall = state.edit_wall
    endpoint = state.edit_endpoint
    new_points = compute_wall_edit_points(session, point)

    if point is None or not wall or not endpoint:
        session.current_tool = "Select"
        session.lifecycle.cancel_pending_edit()
        session.wall_relations.restore_selected_wall_relation_status()
        session.task_panels.refresh_task_panel_status()
        return

    if not new_points:
        if endpoint in ("Start", "End") and state.edit_endpoints:
            _resume_wall_edit_after_invalid_point(session)
            return
        session.current_tool = "Select"
        session.lifecycle.cancel_pending_edit()
        session.wall_relations.restore_selected_wall_relation_status()
        session.task_panels.refresh_task_panel_status()
        return

    proxy = _get_wall_endpoint_proxy(wall)
    if proxy is None:
        session.current_tool = "Select"
        session.lifecycle.cancel_pending_edit()
        session.wall_relations.restore_selected_wall_relation_status()
        session.task_panels.refresh_task_panel_status()
        return

    commit_wall_edit_points(session, wall, endpoint, proxy, new_points)


def _abort_wall_edit_commit(session, openings_fit=True, refresh=True):
    if not openings_fit:
        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "The resized wall cannot contain its hosted openings.\n",
            )
        )
    session.current_tool = "Select"
    session.lifecycle.cancel_pending_edit()
    session.wall_relations.restore_selected_wall_relation_status()
    if refresh:
        session.task_panels.refresh_task_panel_status()


def _warn_post_commit_recompute_failure(session, transaction_name, exc):
    message = str(exc or "").strip() or type(exc).__name__
    FreeCAD.Console.PrintWarning(
        translate(
            "BIM_PlanEdit",
            "Completed {action}, but follow-up recompute failed: {error}\n",
        ).format(action=transaction_name, error=message)
    )


def _apply_wall_edit_transaction(session, wall, proxy, new_points, transaction_name):
    openings_fit = True
    suppress_boundary_console = nullcontext()
    try:
        import ArchSpace

        suppress_boundary_console = ArchSpace.suppress_boundary_failure_console_reports()
    except Exception:
        pass
    try:
        with PlanEditTransaction(session.doc, transaction_name):
            proxy.set_from_endpoints(wall, new_points)
            with suppress_boundary_console:
                session.doc.recompute()
            openings_fit = session.openings.resolve_wall_hosted_opening_layout(wall)
            if not openings_fit:
                raise RuntimeError("Hosted openings no longer fit within resized wall")
    except Exception:
        _abort_wall_edit_commit(session, openings_fit=openings_fit, refresh=False)
        return False
    try:
        session.doc.recompute()
    except Exception as exc:
        _warn_post_commit_recompute_failure(session, transaction_name, exc)
    return True


def _finalize_wall_edit_commit(session, wall):
    session.openings.refresh_wall_hosted_opening_footprints(wall)
    session.selection.sync.set_gui_selection_object(wall)
    session.current_tool = "Select"
    session.lifecycle.cancel_pending_edit()
    session.selection.state.set_selected_plan_target("wall", wall, pending_restore=True)
    session.wall_relations.update_wall_relation_status(wall)
    session.selection.refresh.restore_selected_wall_visuals()
    session.task_panels.refresh_task_panel_status()


def commit_wall_edit_points(session, wall, endpoint, proxy, new_points):
    if not wall or not endpoint or not proxy or not new_points:
        _abort_wall_edit_commit(session, openings_fit=True, refresh=True)
        return

    transaction_name = (
        translate("BIM_PlanEdit", "Move Wall")
        if endpoint == "Move"
        else translate("BIM_PlanEdit", "Stretch Wall Endpoint")
    )
    if not _apply_wall_edit_transaction(session, wall, proxy, new_points, transaction_name):
        return
    _finalize_wall_edit_commit(session, wall)


def start_wall_grip_edit(session, grip_index):
    if grip_index not in (0, 1, 2) or not is_selected_wall_endpoint_editable(session):
        return
    start_wall_edit(session, {0: "Start", 1: "End", 2: "Move"}[grip_index])


def activate_wall_grip(session, grip_index, wall=None):
    if wall is None:
        wall = session.selection.state.get_selected_plan_target_object("wall")
    try:
        from PySide import QtCore
    except ImportError:
        activate_wall_grip_now(session, grip_index, wall)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda wall=wall, grip_index=grip_index: activate_wall_grip_now(session, grip_index, wall),
    )


def activate_wall_grip_now(session, grip_index, wall=None):
    with session.performance.plan_perf_trace_span("activate_wall_grip_now"):
        if session.lifecycle_state.tearing_down or session.current_tool != "Select" or not wall:
            return
        with session.performance.plan_perf_trace_span("activate_wall_grip_set_target"):
            if not session.selection.state.is_selected_plan_target("wall", wall):
                session.selection.state.set_selected_plan_target("wall", wall)
        with session.performance.plan_perf_trace_span("activate_wall_grip_start_edit"):
            start_wall_grip_edit(session, grip_index)


def get_wall_edit_reference_point(session):
    state = _wall_edit_state(session)
    if not state.edit_endpoints or len(state.edit_endpoints) != 2:
        return None
    if state.edit_endpoint == "Move":
        return (state.edit_endpoints[0] + state.edit_endpoints[1]) * 0.5
    if state.edit_endpoint == "Start":
        return state.edit_endpoints[0]
    if state.edit_endpoint == "End":
        return state.edit_endpoints[1]
    return None


def compute_wall_edit_points(session, point):
    state = _wall_edit_state(session)
    endpoint = state.edit_endpoint
    original_endpoints = state.edit_endpoints
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
    state = _wall_edit_state(session)
    endpoint = state.edit_endpoint
    original_endpoints = state.edit_endpoints
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


def get_preview_footprint(session, points, width=None, align=None):
    wall = _wall_edit_state(session).edit_wall
    if not points or len(points) != 2:
        return None

    if width is None and wall:
        width = getattr(getattr(wall, "Width", None), "Value", 0.0) or 0.0
    if width <= 0:
        return None

    axis = points[1].sub(points[0])
    if axis.Length < _MIN_WALL_LENGTH:
        return None
    axis.normalize()
    rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
    perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))

    if align is None:
        align = getattr(wall, "Align", "Center") if wall else "Center"
    if align == "Center":
        y_min = -width / 2
        y_max = width / 2
    elif align == "Left":
        y_min = -width
        y_max = 0.0
    else:
        y_min = 0.0
        y_max = width

    return [
        points[0].add(FreeCAD.Vector(perp).multiply(y_min)),
        points[1].add(FreeCAD.Vector(perp).multiply(y_min)),
        points[1].add(FreeCAD.Vector(perp).multiply(y_max)),
        points[0].add(FreeCAD.Vector(perp).multiply(y_max)),
    ]


def make_preview_wall_adapter(session, wall, endpoints):
    del session
    if not wall or not endpoints or len(endpoints) != 2:
        return None

    real_proxy = getattr(wall, "Proxy", None)
    preview_points = [FreeCAD.Vector(point) for point in endpoints]

    class _PreviewWallProxy:
        def __init__(self, wrapped_proxy):
            self._wrapped_proxy = wrapped_proxy
            self.Type = getattr(wrapped_proxy, "Type", None)

        def calc_endpoints(self, _obj):
            return [FreeCAD.Vector(point) for point in preview_points]

        def get_width(self, _obj, widths=False):
            get_width = _get_callable_attr(self._wrapped_proxy, "get_width")
            if get_width is not None:
                return get_width(wall, widths=widths)
            width = getattr(getattr(wall, "Width", None), "Value", getattr(wall, "Width", None))
            return width

        def get_layers(self, _obj):
            get_layers = _get_callable_attr(self._wrapped_proxy, "get_layers")
            if get_layers is not None:
                return get_layers(wall)
            return None

    class _PreviewWall:
        def __init__(self):
            self.Proxy = _PreviewWallProxy(real_proxy)
            self.Label = getattr(wall, "Label", getattr(wall, "Name", ""))
            self.Name = getattr(wall, "Name", "")
            self.Document = getattr(wall, "Document", None)
            self.InList = getattr(wall, "InList", [])
            # Force solver helpers to read transient preview endpoints
            # instead of the original baseline object.
            self.Base = None
            self.Width = getattr(wall, "Width", None)
            self.Align = getattr(wall, "Align", "Center")

    return _PreviewWall()


def solve_preview_wall_relation(session, relation, wall, preview_wall):
    del session
    if not relation or not wall or not preview_wall:
        return None

    import ArchWallJoinUtils
    import ArchWallJunctionUtils

    if ArchWallJoinUtils.is_wall_joint(relation):
        wall_a = preview_wall if getattr(relation, "WallA", None) == wall else relation.WallA
        wall_b = preview_wall if getattr(relation, "WallB", None) == wall else relation.WallB
        return ArchWallJoinUtils.solve_wall_joint_inputs(
            wall_a,
            wall_b,
            getattr(relation, "JointType", "Miter"),
            getattr(relation, "ButtTrimmed", "Auto"),
            getattr(relation, "TeeStem", "Auto"),
            getattr(relation, "EndA", "Auto"),
            getattr(relation, "EndB", "Auto"),
        )

    if ArchWallJoinUtils.is_wall_junction(relation):
        walls = [
            preview_wall if linked_wall == wall else linked_wall
            for linked_wall in list(getattr(relation, "Walls", []) or [])
        ]
        carrier_wall = (
            preview_wall if getattr(relation, "CarrierWall", None) == wall else relation.CarrierWall
        )
        return ArchWallJunctionUtils.solve_wall_junction_inputs(
            walls,
            getattr(relation, "CarrierMode", "Auto"),
            carrier_wall,
        )

    return None


def collect_preview_wall_relation_data(session, wall, points):
    if not wall or not points or len(points) != 2:
        return {"Start": None, "End": None, "Conflicts": set()}, []

    preview_wall = make_preview_wall_adapter(session, wall, points)
    if not preview_wall:
        return {"Start": None, "End": None, "Conflicts": set()}, []

    import ArchWallJoinUtils

    claims = {"Start": [], "End": []}
    warnings = []
    for relation in ArchWallJoinUtils.iter_wall_relations(wall):
        solution = solve_preview_wall_relation(session, relation, wall, preview_wall)
        if not solution:
            continue
        if not solution.is_ok():
            warnings.append(
                (
                    getattr(relation, "Label", getattr(relation, "Name", "")),
                    getattr(solution, "status", "SolverError"),
                    str(getattr(solution, "status_message", "") or "").strip(),
                )
            )
            continue
        end_name, plane = ArchWallJoinUtils.get_trim_for_wall(solution, preview_wall)
        if end_name and plane:
            claims[end_name].append((relation, plane))

    result = {"Start": None, "End": None, "Conflicts": set()}
    for end_name, entries in claims.items():
        if len(entries) == 1:
            result[end_name] = entries[0][1]
        elif len(entries) > 1:
            result["Conflicts"].add(end_name)
            warnings.append(
                (
                    translate("BIM_PlanEdit", "{end_name} preview trims").format(end_name=end_name),
                    "Conflict",
                    translate(
                        "BIM_PlanEdit",
                        "Multiple wall relations trim the same wall end in preview.",
                    ),
                )
            )
    return result, warnings


def clip_preview_polygon_to_plane(polygon, plane_placement, ref_point, tol=1e-7):
    if not polygon or len(polygon) < 3 or plane_placement is None or ref_point is None:
        return polygon

    plane_origin = FreeCAD.Vector(plane_placement.Base)
    plane_normal = plane_placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
    if plane_normal.Length <= tol:
        return polygon
    plane_normal.normalize()

    ref_distance = plane_normal.dot(FreeCAD.Vector(ref_point).sub(plane_origin))

    def signed_distance(point):
        return plane_normal.dot(FreeCAD.Vector(point).sub(plane_origin))

    def is_inside(distance):
        if ref_distance >= 0:
            return distance >= -tol
        return distance <= tol

    def intersect(prev_point, curr_point, prev_distance, curr_distance):
        denom = prev_distance - curr_distance
        if abs(denom) <= tol:
            return FreeCAD.Vector(curr_point)
        factor = prev_distance / denom
        segment = FreeCAD.Vector(curr_point).sub(prev_point)
        return FreeCAD.Vector(prev_point).add(segment.multiply(factor))

    result = []
    prev_point = FreeCAD.Vector(polygon[-1])
    prev_distance = signed_distance(prev_point)
    prev_inside = is_inside(prev_distance)
    for current_point in polygon:
        current_point = FreeCAD.Vector(current_point)
        current_distance = signed_distance(current_point)
        current_inside = is_inside(current_distance)
        if current_inside:
            if not prev_inside:
                result.append(intersect(prev_point, current_point, prev_distance, current_distance))
            result.append(current_point)
        elif prev_inside:
            result.append(intersect(prev_point, current_point, prev_distance, current_distance))
        prev_point = current_point
        prev_distance = current_distance
        prev_inside = current_inside
    return result


def get_preview_footprint_polylines(session, points):
    footprint = get_preview_footprint(session, points)
    if not footprint or len(footprint) < 3:
        return [], []

    relation_endings, warnings = collect_preview_wall_relation_data(
        session, _wall_edit_state(session).edit_wall, points
    )
    polygon = [FreeCAD.Vector(point) for point in footprint]
    for end_name in ("Start", "End"):
        plane = relation_endings.get(end_name)
        if plane is None or end_name in relation_endings.get("Conflicts", set()):
            continue
        ref_point = points[1] if end_name == "Start" else points[0]
        polygon = clip_preview_polygon_to_plane(polygon, plane, ref_point)
        if not polygon or len(polygon) < 3:
            break

    if not polygon or len(polygon) < 3:
        return [], warnings

    closed = list(polygon)
    closed.append(FreeCAD.Vector(closed[0]))
    return [closed], warnings


def get_readout_base_gap(session):
    from draftutils import params

    units_per_pixel = session.viewport.get_plan_view_units_per_pixel() or 0.0
    text_height_pixels = float(params.get_param_view("MarkerSize") or 0.0) * 2.0 * 96.0 / 72.0
    return max(100.0, text_height_pixels * units_per_pixel * 1.25)


def get_aligned_readout_offset_for_wall(session, wall):
    width = getattr(getattr(wall, "Width", None), "Value", 0.0) if wall else 0.0
    width = float(width or 0.0)
    base_gap = max(width * 0.25, get_readout_base_gap(session))
    if width <= 0:
        return base_gap
    align = getattr(wall, "Align", "Center") if wall else "Center"
    if align == "Left":
        return base_gap
    if align == "Right":
        return -(base_gap)
    return width * 0.5 + base_gap


def get_wall_edit_readout_offset(session, mode):
    if mode in (2, 3):
        return get_readout_base_gap(session)
    if mode != 1:
        return None
    return get_aligned_readout_offset_for_wall(session, _wall_edit_state(session).edit_wall)


def get_opening_move_readout_offset(session, opening):
    host = next(iter(getattr(opening, "Hosts", None) or []), None) if opening else None
    return get_aligned_readout_offset_for_wall(session, host)


def _ensure_wall_edit_preview_axis_tracker(session, DraftTrackers):
    state = _wall_edit_state(session)
    if state.preview_line_tracker is None:
        state.preview_line_tracker = session.overlays.manager.make_plan_line_tracker(
            DraftTrackers,
            "wall-edit-preview-axis",
            swidth=session.viewport.scaled_line_width(2),
            ontop=True,
        )
        state.preview_line_tracker.on()
    return state.preview_line_tracker


def _update_wall_edit_preview_relation_status(session, relation_warnings):
    task_panel_state = session.task_panel_state
    previous_relation_status = task_panel_state.relation_status_message
    if relation_warnings:
        label, status, _detail = relation_warnings[0]
        task_panel_state.relation_status_message = translate(
            "BIM_PlanEdit", "Preview warning: {label} ({status})"
        ).format(label=label, status=status)
    elif is_wall_edit_modal_active(session):
        session.wall_relations.clear_plan_relation_status()
    return previous_relation_status


def _get_wall_edit_preview_segments(polylines):
    segments = []
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        segments.extend(zip(polyline, polyline[1:]))
    return segments


def _ensure_wall_edit_preview_footprint_trackers(session, segments, DraftTrackers, color, width):
    state = _wall_edit_state(session)
    if len(state.preview_footprint_trackers) != len(segments):
        session.overlays.manager.finalize_trackers(state.preview_footprint_trackers)
        state.preview_footprint_trackers = []
        for _start, _end in segments:
            tracker = session.overlays.manager.make_plan_line_tracker(
                DraftTrackers,
                "wall-edit-preview-footprint",
                scolor=color,
                swidth=width,
                ontop=True,
            )
            state.preview_footprint_trackers.append(tracker)


def _sync_wall_edit_preview_footprint_trackers(session, segments, DraftTrackers):
    state = _wall_edit_state(session)
    color = (0.22, 0.53, 0.98)
    width = session.viewport.scaled_line_width(2)
    _ensure_wall_edit_preview_footprint_trackers(
        session,
        segments,
        DraftTrackers,
        color,
        width,
    )
    for tracker, (start, end) in zip(state.preview_footprint_trackers, segments):
        tracker.setColor(color)
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()


def _get_wall_edit_preview_grip_specs(session, points, marker_size):
    midpoint = (points[0] + points[1]) * 0.5
    midpoint_marker = FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size)
    return (
        (points[0], 0, None),
        (points[1], 1, None),
        (midpoint, 2, midpoint_marker),
    )


def _sync_wall_edit_preview_grip_trackers(session, grip_specs, DraftTrackers):
    state = _wall_edit_state(session)
    if not state.preview_grip_trackers:
        for position, idx, marker in grip_specs:
            tracker = DraftTrackers.editTracker(
                pos=position,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            state.preview_grip_trackers.append(tracker)
        return

    for tracker, (position, _idx, _marker) in zip(state.preview_grip_trackers, grip_specs):
        tracker.set(position)
        tracker.on()


def update_wall_edit_preview_geometry(session, points):
    if not points or len(points) != 2:
        return

    try:
        import draftguitools.gui_trackers as DraftTrackers
        from draftutils import params
    except Exception:
        return

    axis_tracker = _ensure_wall_edit_preview_axis_tracker(session, DraftTrackers)
    axis_tracker.p1(points[0])
    axis_tracker.p2(points[1])

    polylines, relation_warnings = get_preview_footprint_polylines(session, points)
    previous_relation_status = _update_wall_edit_preview_relation_status(
        session,
        relation_warnings,
    )
    segments = _get_wall_edit_preview_segments(polylines)
    _sync_wall_edit_preview_footprint_trackers(session, segments, DraftTrackers)

    if previous_relation_status != session.task_panel_state.relation_status_message:
        session.task_panels.refresh_task_panel_status()

    marker_size = session.viewport.scaled_marker_size(params.get_param_view("MarkerSize"))
    grip_specs = _get_wall_edit_preview_grip_specs(session, points, marker_size)
    _sync_wall_edit_preview_grip_trackers(session, grip_specs, DraftTrackers)


def sync_wall_edit_preview(session, points, include_opening_preview=True):
    update_wall_edit_preview_geometry(session, points)
    sync_wall_edit_readout(session, points)
    if include_opening_preview:
        sync_wall_hosted_opening_preview(session, points)
    else:
        clear_wall_hosted_opening_preview(session)


def is_wall_move_edit_active(session):
    state = _wall_edit_state(session)
    return bool(
        state.edit_wall and state.edit_endpoint == "Move" and session.current_tool == "Move Wall"
    )


def is_wall_stretch_edit_active(session):
    state = _wall_edit_state(session)
    return bool(
        state.edit_wall
        and state.edit_endpoint in ("Start", "End")
        and session.current_tool in ("Stretch Start", "Stretch End")
    )


def is_wall_readout_edit_active(session):
    return bool(is_wall_move_edit_active(session) or is_wall_stretch_edit_active(session))


def clear_wall_edit_preview(session):
    state = _wall_edit_state(session)
    if state.preview_line_tracker:
        session.overlays.manager.finalize_trackers([state.preview_line_tracker])
    state.preview_line_tracker = None

    session.overlays.manager.finalize_trackers(state.preview_footprint_trackers)
    state.preview_footprint_trackers = []

    session.overlays.manager.finalize_trackers(state.preview_grip_trackers)
    state.preview_grip_trackers = []
    clear_wall_edit_readout(session)
    clear_wall_hosted_opening_preview(session)


def get_wall_hosted_opening_preview_segments(session, wall, points):
    if not wall or not points or len(points) != 2:
        return []
    if _wall_edit_state(session).edit_endpoint not in ("Start", "End"):
        return []

    layout = session.openings.compute_wall_hosted_opening_layout(wall, points)
    if layout is None:
        return []

    segments = []
    for item in layout:
        delta = FreeCAD.Vector(item["target_point"]).sub(item["current"])
        if delta.Length < 1e-6:
            continue
        for polyline in session.overlays.geometry.get_opening_overlay_polylines(item["opening"]):
            if len(polyline) < 2:
                continue
            translated = [FreeCAD.Vector(point).add(delta) for point in polyline]
            segments.extend(zip(translated, translated[1:]))
    return segments


def sync_wall_hosted_opening_preview(session, points):
    state = _wall_edit_state(session)
    wall = state.edit_wall
    if session.current_tool not in ("Stretch Start", "Stretch End") or not wall:
        clear_wall_hosted_opening_preview(session)
        return

    segments = get_wall_hosted_opening_preview_segments(session, wall, points)
    if not segments:
        clear_wall_hosted_opening_preview(session)
        return

    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        clear_wall_hosted_opening_preview(session)
        return

    color = (0.12, 0.38, 0.95)
    width = session.viewport.scaled_line_width(2)
    if len(state.wall_edit_opening_preview_trackers) != len(segments):
        clear_wall_hosted_opening_preview(session)
        for _start, _end in segments:
            tracker = session.overlays.manager.make_plan_line_tracker(
                DraftTrackers,
                "wall-edit-opening-preview",
                scolor=color,
                swidth=width,
                ontop=True,
            )
            state.wall_edit_opening_preview_trackers.append(tracker)

    for tracker, (start, end) in zip(state.wall_edit_opening_preview_trackers, segments):
        tracker.setColor(color)
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()


def clear_wall_hosted_opening_preview(session):
    state = _wall_edit_state(session)
    session.overlays.manager.finalize_trackers(state.wall_edit_opening_preview_trackers)
    state.wall_edit_opening_preview_trackers = []


def refresh_wall_hosted_opening_footprints(session, wall):
    for opening in session.openings.get_wall_hosted_openings(wall):
        session.openings.refresh_opening_footprint_display(opening)
        session.openings.refresh_opening_host_footprint_displays(opening)


def _get_wall_hosted_opening_layout_axis(endpoints):
    if not endpoints or len(endpoints) != 2:
        return None, None, None
    wall_origin = FreeCAD.Vector(endpoints[0])
    wall_end = FreeCAD.Vector(endpoints[1])
    wall_axis_u = wall_end.sub(wall_origin)
    wall_length = wall_axis_u.Length
    if wall_length < 1e-9:
        return wall_origin, None, None
    wall_axis_u.normalize()
    return wall_origin, wall_axis_u, wall_length


def _get_wall_hosted_opening_layout_item(session, opening, wall_origin, wall_axis_u, wall_length):
    state = _wall_edit_state(session)
    proxy = session.openings.get_opening_plan_proxy(
        opening, "get_plan_move_context", "move_along_host", "get_plan_center_point"
    )
    if not proxy:
        return None
    context = proxy.get_plan_move_context()
    if not context:
        return None
    current_center = proxy.get_plan_center_point()
    if current_center is None:
        return None
    current = FreeCAD.Vector(current_center)
    desired_u = current.sub(wall_origin).dot(wall_axis_u)
    half_width = float(context.get("opening_half_width_u") or 0.0)
    clearance_seed = state.wall_edit_opening_clearances.get(getattr(opening, "Name", ""))
    if clearance_seed:
        if state.edit_endpoint == "Start":
            desired_u = max(
                desired_u,
                half_width + float(clearance_seed.get("left_clearance") or 0.0),
            )
        elif state.edit_endpoint == "End":
            desired_u = min(
                desired_u,
                wall_length - half_width - float(clearance_seed.get("right_clearance") or 0.0),
            )
    low = half_width
    high = wall_length - half_width
    if low > high:
        midpoint = wall_length * 0.5
        low = midpoint
        high = midpoint
    return {
        "opening": opening,
        "proxy": proxy,
        "current": current,
        "desired_u": desired_u,
        "low": low,
        "high": high,
        "half_width": half_width,
        "clearance_seed": clearance_seed,
    }


def _collect_wall_hosted_opening_layout_items(session, wall, wall_origin, wall_axis_u, wall_length):
    openings = []
    for opening in session.openings.get_wall_hosted_openings(wall):
        item = _get_wall_hosted_opening_layout_item(
            session,
            opening,
            wall_origin,
            wall_axis_u,
            wall_length,
        )
        if item is not None:
            openings.append(item)
    openings.sort(key=lambda item: (item["desired_u"], getattr(item["opening"], "Name", "")))
    return openings


def _resolve_wall_hosted_opening_layout_bounds(openings):
    left = []
    for index, item in enumerate(openings):
        minimum = item["low"]
        if index > 0:
            minimum = max(
                minimum,
                left[index - 1] + openings[index - 1]["half_width"] + item["half_width"],
            )
        if minimum > item["high"] + 1e-6:
            return None, None
        left.append(minimum)

    right = [0.0] * len(openings)
    for index in range(len(openings) - 1, -1, -1):
        maximum = openings[index]["high"]
        if index < len(openings) - 1:
            maximum = min(
                maximum,
                right[index + 1]
                - openings[index]["half_width"]
                - openings[index + 1]["half_width"],
            )
        if maximum < openings[index]["low"] - 1e-6:
            return None, None
        right[index] = maximum
    return left, right


def _resolve_wall_hosted_opening_layout_centers(openings, left, right):
    resolved = []
    for index, item in enumerate(openings):
        center_u = min(max(item["desired_u"], left[index]), right[index])
        if index > 0:
            center_u = max(
                center_u,
                resolved[index - 1] + openings[index - 1]["half_width"] + item["half_width"],
            )
        if center_u > right[index] + 1e-6:
            return None
        resolved.append(center_u)
    return resolved


def _build_wall_hosted_opening_layout(openings, resolved, wall_origin, wall_axis_u):
    layout = []
    for item, center_u in zip(openings, resolved):
        target_point = wall_origin.add(FreeCAD.Vector(wall_axis_u).multiply(center_u))
        target_point.z = item["current"].z
        layout.append(
            {
                **item,
                "target_center_u": center_u,
                "target_point": target_point,
            }
        )
    return layout


def compute_wall_hosted_opening_layout(session, wall, endpoints):
    if not wall:
        return []
    wall_origin, wall_axis_u, wall_length = _get_wall_hosted_opening_layout_axis(endpoints)
    if wall_origin is None:
        return []
    if wall_axis_u is None or wall_length is None:
        return None
    ensure_wall_edit_opening_clearances(session, wall, endpoints)

    openings = _collect_wall_hosted_opening_layout_items(
        session,
        wall,
        wall_origin,
        wall_axis_u,
        wall_length,
    )
    if not openings:
        return []

    left, right = _resolve_wall_hosted_opening_layout_bounds(openings)
    if left is None or right is None:
        return None
    resolved = _resolve_wall_hosted_opening_layout_centers(openings, left, right)
    if resolved is None:
        return None
    return _build_wall_hosted_opening_layout(openings, resolved, wall_origin, wall_axis_u)


def resolve_wall_hosted_opening_layout(session, wall):
    wall_proxy = _get_wall_endpoint_proxy(wall)
    if wall_proxy is None:
        return True
    try:
        endpoints = wall_proxy.calc_endpoints(wall)
    except Exception:
        return True
    layout = session.openings.compute_wall_hosted_opening_layout(wall, endpoints)
    if layout is None:
        return False
    for item in layout:
        if not item["proxy"].move_along_host(item["target_point"]):
            return False

    return True


def get_wall_edit_readout_specs(session, points):
    state = _wall_edit_state(session)
    if not points or len(points) != 2 or not state.edit_endpoints:
        return []

    original_points = state.edit_endpoints
    if state.edit_endpoint == "Move":
        original_midpoint = (original_points[0] + original_points[1]) * 0.5
        new_midpoint = (points[0] + points[1]) * 0.5
        return [
            (2, original_midpoint, new_midpoint),
            (3, original_midpoint, new_midpoint),
        ]

    return [(1, points[0], points[1])]


def get_default_wall_edit_readout_mode(session, specs):
    state = _wall_edit_state(session)
    modes = [mode for mode, _start, _end in specs]
    if not modes:
        return None
    if is_wall_move_edit_active(session):
        if state.wall_edit_active_readout_mode in modes:
            return state.wall_edit_active_readout_mode
        if 2 in modes:
            return 2
    if 1 in modes:
        return 1
    return modes[0]


def bind_wall_edit_readout_callbacks(session, dim, mode):
    if mode == 1:
        dim.setValueChangedCallback(lambda value: on_wall_stretch_length_changed(session, value))
        dim.setEditingFinishedCallback(
            lambda value: on_wall_stretch_length_finished(session, value)
        )
        _set_editing_canceled_callback(
            dim, lambda value: on_wall_stretch_length_canceled(session, value)
        )
        return

    dim.setValueChangedCallback(
        lambda value, delta_mode=mode: on_wall_move_delta_changed(session, delta_mode, value)
    )
    dim.setEditingFinishedCallback(
        lambda value, delta_mode=mode: on_wall_move_delta_finished(session, delta_mode, value)
    )
    _set_editing_canceled_callback(
        dim, lambda value, delta_mode=mode: on_wall_move_delta_canceled(session, delta_mode, value)
    )


def update_wall_edit_readouts_in_place(session, points, active_mode=None):
    state = _wall_edit_state(session)
    specs = {
        mode: (start, end) for mode, start, end in get_wall_edit_readout_specs(session, points)
    }
    for tracker in state.wall_edit_readout_trackers:
        mode = getattr(tracker, "mode", None)
        if mode not in specs:
            continue
        start, end = specs[mode]
        _tracker_update_points(tracker, start, end, sync_spinbox=(mode != active_mode))
        tracker.on()


def _make_wall_edit_readout_tracker(session, DraftTrackers, mode):
    try:
        if is_wall_readout_edit_active(session):
            return DraftTrackers.editableArchDimTracker(mode=mode)
        return DraftTrackers.archDimTracker(mode=mode)
    except Exception:
        return None


def _configure_wall_edit_readout_tracker(session, dim, mode, start, end, readout_color):
    try:
        _set_dim_color(dim, readout_color)
    except Exception:
        pass
    offset = get_wall_edit_readout_offset(session, mode)
    if offset is not None:
        dim.offset = offset
    dim.p1(start)
    dim.p2(end)
    dim.on()
    if is_wall_readout_edit_active(session) and _supports_value_changed_callback(dim):
        bind_wall_edit_readout_callbacks(session, dim, mode)


def _track_active_wall_edit_readout(session, dim, mode, active_mode):
    state = _wall_edit_state(session)
    if (
        is_wall_readout_edit_active(session)
        and _supports_value_changed_callback(dim)
        and mode == active_mode
    ):
        state.wall_edit_active_readout_mode = mode
        state.wall_edit_active_readout_tracker = dim
    if state.wall_edit_active_readout_tracker is None:
        state.wall_edit_active_readout_tracker = dim


def _sync_wall_edit_readout_trackers(session, DraftTrackers, dims, active_mode, readout_color):
    state = _wall_edit_state(session)
    for mode, start, end in dims:
        dim = _make_wall_edit_readout_tracker(session, DraftTrackers, mode)
        if dim is None:
            continue
        _configure_wall_edit_readout_tracker(session, dim, mode, start, end, readout_color)
        _track_active_wall_edit_readout(session, dim, mode, active_mode)
        state.wall_edit_readout_trackers.append(dim)


def sync_wall_edit_readout(session, points):
    state = _wall_edit_state(session)
    clear_wall_edit_readout(session)
    if not points or len(points) != 2 or not state.edit_endpoints:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return

    readout_color = (0.12, 0.38, 0.95)
    dims = get_wall_edit_readout_specs(session, points)
    active_mode = get_default_wall_edit_readout_mode(session, dims)
    state.wall_edit_active_readout_mode = active_mode
    _sync_wall_edit_readout_trackers(
        session,
        DraftTrackers,
        dims,
        active_mode,
        readout_color,
    )


def clear_wall_edit_readout(session):
    state = _wall_edit_state(session)
    session.overlays.manager.finalize_trackers(state.wall_edit_readout_trackers)
    state.wall_edit_readout_trackers = []
    state.wall_edit_active_readout_tracker = None
    state.wall_edit_active_readout_mode = None
    state.wall_edit_length_edit_queued = False


def get_wall_edit_readout_tracker(session, mode):
    for tracker in _wall_edit_state(session).wall_edit_readout_trackers:
        if getattr(tracker, "mode", None) == mode:
            return tracker
    return None


def cycle_wall_move_readout_mode(session):
    state = _wall_edit_state(session)
    if not is_wall_move_edit_active(session):
        return False
    modes = [
        getattr(tracker, "mode", None)
        for tracker in state.wall_edit_readout_trackers
        if getattr(tracker, "mode", None) in (2, 3)
    ]
    modes = [mode for mode in modes if mode is not None]
    if not modes:
        return False
    current_mode = (
        state.wall_edit_active_readout_mode
        if state.wall_edit_active_readout_mode in modes
        else modes[0]
    )
    next_mode = modes[(modes.index(current_mode) + 1) % len(modes)]
    state.wall_edit_active_readout_mode = next_mode
    tracker = get_wall_edit_readout_tracker(session, next_mode)
    if tracker is not None:
        state.wall_edit_active_readout_tracker = tracker
    return True


def start_wall_readout_edit(session, cycle=False):
    state = _wall_edit_state(session)
    tracker = state.wall_edit_active_readout_tracker
    if not is_wall_readout_edit_active(session):
        return False
    if cycle and is_wall_move_edit_active(session):
        if tracker is not None and _tracker_is_in_edit(tracker):
            _stop_tracker_edit(tracker)
        if not cycle_wall_move_readout_mode(session):
            return False
        tracker = state.wall_edit_active_readout_tracker
    if tracker is None:
        return False
    if not _tracker_supports_edit(tracker):
        return False
    if _tracker_is_in_edit(tracker):
        _focus_tracker_spinbox(tracker)
        return True
    if state.wall_edit_length_edit_queued:
        return True
    state.wall_edit_length_edit_queued = True
    session.snap.stop_snapper()
    try:
        from PySide import QtCore
    except ImportError:
        state.wall_edit_length_edit_queued = False
        tracker.startEdit(tracker.Distance)
        return True
    QtCore.QTimer.singleShot(
        0, lambda: start_wall_readout_edit_now(session, tracker, tracker.Distance)
    )
    return True


def start_wall_stretch_length_edit(session):
    return start_wall_readout_edit(session, cycle=False)


def start_wall_readout_edit_now(session, tracker, value):
    state = _wall_edit_state(session)
    state.wall_edit_length_edit_queued = False
    if not is_wall_readout_edit_active(session):
        return
    if tracker is None or tracker is not state.wall_edit_active_readout_tracker:
        return
    if not _tracker_supports_edit(tracker):
        return
    if _tracker_is_in_edit(tracker):
        _focus_tracker_spinbox(tracker)
        return
    try:
        tracker.startEdit(value)
    except Exception:
        return


def on_wall_stretch_length_changed(session, value):
    state = _wall_edit_state(session)
    if not is_wall_stretch_edit_active(session):
        return
    new_points = compute_wall_edit_points_from_length(session, value)
    tracker = state.wall_edit_active_readout_tracker
    if not new_points or tracker is None:
        return
    state.preview_points = new_points
    update_wall_edit_preview_geometry(session, new_points)
    update_wall_edit_readouts_in_place(session, new_points, active_mode=1)
    sync_wall_hosted_opening_preview(session, new_points)


def on_wall_stretch_length_finished(session, value):
    state = _wall_edit_state(session)
    if not is_wall_stretch_edit_active(session):
        return
    wall = state.edit_wall
    endpoint = state.edit_endpoint
    proxy = getattr(wall, "Proxy", None)
    new_points = compute_wall_edit_points_from_length(session, value)
    if not new_points or not proxy:
        return
    state.preview_points = new_points
    commit_wall_edit_points(session, wall, endpoint, proxy, new_points)


def on_wall_stretch_length_canceled(session, value):
    del value
    if not is_wall_stretch_edit_active(session):
        return
    schedule_wall_edit_readout_cancel(session)


def compute_wall_edit_points_from_move_delta(session, mode, value):
    state = _wall_edit_state(session)
    if not is_wall_move_edit_active(session) or not state.edit_endpoints:
        return None
    original_endpoints = state.edit_endpoints
    original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
    preview_points = state.preview_points if state.preview_points else original_endpoints
    current_midpoint = (preview_points[0] + preview_points[1]) * 0.5
    target_midpoint = FreeCAD.Vector(current_midpoint)
    if mode == 2:
        target_midpoint.x = original_midpoint.x + float(value)
    elif mode == 3:
        target_midpoint.y = original_midpoint.y + float(value)
    else:
        return None
    delta = target_midpoint.sub(original_midpoint)
    return [original_endpoints[0].add(delta), original_endpoints[1].add(delta)]


def on_wall_move_delta_changed(session, mode, value):
    state = _wall_edit_state(session)
    if not is_wall_move_edit_active(session):
        return
    new_points = compute_wall_edit_points_from_move_delta(session, mode, value)
    if not new_points:
        return
    state.preview_points = new_points
    update_wall_edit_preview_geometry(session, new_points)
    update_wall_edit_readouts_in_place(session, new_points, active_mode=mode)
    sync_wall_hosted_opening_preview(session, new_points)


def on_wall_move_delta_finished(session, mode, value):
    state = _wall_edit_state(session)
    if not is_wall_move_edit_active(session):
        return
    wall = state.edit_wall
    endpoint = state.edit_endpoint
    proxy = getattr(wall, "Proxy", None)
    new_points = compute_wall_edit_points_from_move_delta(session, mode, value)
    if not new_points or not proxy:
        return
    state.preview_points = new_points
    commit_wall_edit_points(session, wall, endpoint, proxy, new_points)


def on_wall_move_delta_canceled(session, mode, value):
    del mode, value
    if not is_wall_move_edit_active(session):
        return
    schedule_wall_edit_readout_cancel(session)


def schedule_wall_edit_readout_cancel(session):
    state = _wall_edit_state(session)
    resume_token = (
        state.wall_edit_generation,
        state.edit_wall,
        state.edit_endpoint,
        state.wall_edit_active_readout_tracker,
        state.wall_edit_active_readout_mode,
        session.current_tool,
    )
    preview_points = None
    if state.preview_points:
        preview_points = [FreeCAD.Vector(point) for point in state.preview_points]
    elif state.edit_endpoints:
        preview_points = [FreeCAD.Vector(point) for point in state.edit_endpoints]
    try:
        from PySide import QtCore
    except ImportError:
        finish_wall_edit_readout_canceled(session, preview_points, resume_token=resume_token)
        return
    QtCore.QTimer.singleShot(
        0,
        lambda pts=preview_points, token=resume_token: finish_wall_edit_readout_canceled(
            session,
            pts,
            resume_token=token,
        ),
    )


def finish_wall_edit_readout_canceled(session, preview_points, *, resume_token=None):
    state = _wall_edit_state(session)
    if resume_token is not None:
        current_token = (
            state.wall_edit_generation,
            state.edit_wall,
            state.edit_endpoint,
            state.wall_edit_active_readout_tracker,
            state.wall_edit_active_readout_mode,
            session.current_tool,
        )
        if current_token != resume_token:
            return
    if not is_wall_readout_edit_active(session):
        return
    if preview_points:
        sync_wall_edit_preview(session, preview_points)
    resume_wall_edit_point_pick(session)


def _resume_wall_edit_after_invalid_point(session):
    state = _wall_edit_state(session)
    preview_points = state.preview_points or state.edit_endpoints
    if preview_points:
        sync_wall_edit_preview(session, preview_points)
    FreeCAD.Console.PrintWarning(
        translate(
            "BIM_PlanEdit",
            "Pick a point that keeps the wall at least {length:g} mm long.\n",
        ).format(length=_MIN_WALL_LENGTH)
    )
    resume_wall_edit_point_pick(session)


def restore_edit_wall_visibility(session):
    state = _wall_edit_state(session)
    wall = state.edit_wall
    if wall is not None and state.edit_wall_visibility is not None:
        try:
            wall.ViewObject.Visibility = state.edit_wall_visibility
        except Exception:
            pass
    state.edit_wall_visibility = None


def update_wall_edit_preview(session, point):
    state = _wall_edit_state(session)
    new_points = compute_wall_edit_points(session, point)
    if not new_points:
        return
    state.preview_points = new_points
    sync_wall_edit_preview(session, new_points)


def update_wall_edit_point_pick(session, point=None, snap_info=None):
    del snap_info
    state = _wall_edit_state(session)
    if state.wall_edit_active_readout_tracker and _tracker_is_in_edit(
        state.wall_edit_active_readout_tracker
    ):
        return
    update_wall_edit_preview(session, point)


def cancel_wall_edit_point_pick(session):
    session.current_tool = "Select"
    session.lifecycle.cancel_pending_edit()
    session.wall_relations.restore_selected_wall_relation_status()
    session.task_panels.refresh_task_panel_status()


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class WallEditTool(plan_runtime_tools.PlanToolHandler):
    """Keyboard behavior for active wall point-pick edits."""

    def on_key(self, key, event_callback, coin):
        session = self.session
        if is_wall_move_edit_active(session) and key == coin.SoKeyboardEvent.TAB:
            if start_wall_readout_edit(session, cycle=True):
                _set_key_event_handled(event_callback)
            return True
        if is_wall_readout_edit_active(session) and key in (
            coin.SoKeyboardEvent.RETURN,
            coin.SoKeyboardEvent.ENTER,
        ):
            if start_wall_readout_edit(session):
                _set_key_event_handled(event_callback)
            return True
        if is_wall_stretch_edit_active(session) and key == coin.SoKeyboardEvent.TAB:
            if start_wall_readout_edit(session):
                _set_key_event_handled(event_callback)
            return True
        if (
            _wall_edit_state(session).edit_wall
            and session.current_tool != plan_runtime_tools.PlanTool.SELECT
            and key == coin.SoKeyboardEvent.ESCAPE
        ):
            cancel_wall_edit_point_pick(session)
            return True
        return False


def _set_key_event_handled(event_callback):
    setter = getattr(event_callback, "setHandled", None)
    if callable(setter):
        setter()


def reset_pending_edit_state(session, *, restore_wall_visibility=True):
    state = _wall_edit_state(session)
    state.wall_edit_generation += 1
    state.wall_edit_modal_active = False
    if restore_wall_visibility:
        session.wall_edit.restore_edit_wall_visibility()
    else:
        state.edit_wall_visibility = None
    session.wall_edit.clear_wall_edit_preview()
    state.edit_wall = None
    state.edit_endpoint = None
    state.edit_endpoints = None
    state.wall_edit_opening_clearances = {}
    state.wall_edit_opening_clearances_queued = False
    state.wall_edit_task_panel_refresh_queued = False
    state.preview_points = None
    state.wall_edit_length_edit_queued = False


def discard_runtime_references(session):
    state = _wall_edit_state(session)
    state.edit_wall = None
    state.edit_endpoint = None
    state.edit_endpoints = None
    state.preview_points = None
    state.preview_line_tracker = None
    state.preview_footprint_trackers = []
    state.preview_grip_trackers = []
    state.wall_edit_readout_trackers = []
    state.wall_edit_opening_preview_trackers = []
    state.wall_edit_active_readout_tracker = None
    state.wall_edit_active_readout_mode = None
    state.edit_wall_visibility = None


class PlanWallEditAPI(_SessionAPI):
    """Owned session surface for Plan Edit wall edit behavior."""

    __slots__ = ()

    def has_active_wall_edit(self, *args, **kwargs):
        return has_active_wall_edit(self.session, *args, **kwargs)

    def is_wall_edit_modal_active(self, *args, **kwargs):
        return is_wall_edit_modal_active(self.session, *args, **kwargs)

    def is_selected_wall_endpoint_editable(self, *args, **kwargs):
        return is_selected_wall_endpoint_editable(self.session, *args, **kwargs)

    def cancel_wall_edit(self, *args, **kwargs):
        return cancel_wall_edit(self.session, *args, **kwargs)

    def cancel_for_select(self):
        return self.cancel_wall_edit()

    def reset_pending_edit_state(self, *args, **kwargs):
        return reset_pending_edit_state(self.session, *args, **kwargs)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def cancel_wall_subtool(self, *args, **kwargs):
        return cancel_wall_subtool(self.session, *args, **kwargs)

    def start_wall_edit(self, *args, **kwargs):
        return start_wall_edit(self.session, *args, **kwargs)

    def resume_wall_edit_point_pick(self, *args, **kwargs):
        return resume_wall_edit_point_pick(self.session, *args, **kwargs)

    def snapshot_wall_hosted_opening_clearances(self, *args, **kwargs):
        return snapshot_wall_hosted_opening_clearances(self.session, *args, **kwargs)

    def queue_wall_edit_opening_clearances(self, *args, **kwargs):
        return queue_wall_edit_opening_clearances(self.session, *args, **kwargs)

    def prime_wall_edit_opening_clearances(self, *args, **kwargs):
        return prime_wall_edit_opening_clearances(self.session, *args, **kwargs)

    def ensure_wall_edit_opening_clearances(self, *args, **kwargs):
        return ensure_wall_edit_opening_clearances(self.session, *args, **kwargs)

    def queue_wall_edit_task_panel_refresh(self, *args, **kwargs):
        return queue_wall_edit_task_panel_refresh(self.session, *args, **kwargs)

    def flush_wall_edit_task_panel_refresh(self, *args, **kwargs):
        return flush_wall_edit_task_panel_refresh(self.session, *args, **kwargs)

    def finish_wall_edit(self, *args, **kwargs):
        return finish_wall_edit(self.session, *args, **kwargs)

    def commit_wall_edit_points(self, *args, **kwargs):
        return commit_wall_edit_points(self.session, *args, **kwargs)

    def start_wall_grip_edit(self, *args, **kwargs):
        return start_wall_grip_edit(self.session, *args, **kwargs)

    def activate_wall_grip(self, *args, **kwargs):
        return activate_wall_grip(self.session, *args, **kwargs)

    def activate_wall_grip_now(self, *args, **kwargs):
        return activate_wall_grip_now(self.session, *args, **kwargs)

    def get_wall_edit_reference_point(self, *args, **kwargs):
        return get_wall_edit_reference_point(self.session, *args, **kwargs)

    def compute_wall_edit_points(self, *args, **kwargs):
        return compute_wall_edit_points(self.session, *args, **kwargs)

    def compute_wall_edit_points_from_length(self, *args, **kwargs):
        return compute_wall_edit_points_from_length(self.session, *args, **kwargs)

    def get_preview_footprint(self, *args, **kwargs):
        return get_preview_footprint(self.session, *args, **kwargs)

    def make_preview_wall_adapter(self, *args, **kwargs):
        return make_preview_wall_adapter(self.session, *args, **kwargs)

    def solve_preview_wall_relation(self, *args, **kwargs):
        return solve_preview_wall_relation(self.session, *args, **kwargs)

    def collect_preview_wall_relation_data(self, *args, **kwargs):
        return collect_preview_wall_relation_data(self.session, *args, **kwargs)

    def get_preview_footprint_polylines(self, *args, **kwargs):
        return get_preview_footprint_polylines(self.session, *args, **kwargs)

    def get_readout_base_gap(self, *args, **kwargs):
        return get_readout_base_gap(self.session, *args, **kwargs)

    def get_aligned_readout_offset_for_wall(self, *args, **kwargs):
        return get_aligned_readout_offset_for_wall(self.session, *args, **kwargs)

    def get_wall_edit_readout_offset(self, *args, **kwargs):
        return get_wall_edit_readout_offset(self.session, *args, **kwargs)

    def get_opening_move_readout_offset(self, *args, **kwargs):
        return get_opening_move_readout_offset(self.session, *args, **kwargs)

    def update_wall_edit_preview_geometry(self, *args, **kwargs):
        return update_wall_edit_preview_geometry(self.session, *args, **kwargs)

    def sync_wall_edit_preview(self, *args, **kwargs):
        return sync_wall_edit_preview(self.session, *args, **kwargs)

    def is_wall_move_edit_active(self, *args, **kwargs):
        return is_wall_move_edit_active(self.session, *args, **kwargs)

    def is_wall_stretch_edit_active(self, *args, **kwargs):
        return is_wall_stretch_edit_active(self.session, *args, **kwargs)

    def is_wall_readout_edit_active(self, *args, **kwargs):
        return is_wall_readout_edit_active(self.session, *args, **kwargs)

    def clear_wall_edit_preview(self, *args, **kwargs):
        return clear_wall_edit_preview(self.session, *args, **kwargs)

    def get_wall_hosted_opening_preview_segments(self, *args, **kwargs):
        return get_wall_hosted_opening_preview_segments(self.session, *args, **kwargs)

    def sync_wall_hosted_opening_preview(self, *args, **kwargs):
        return sync_wall_hosted_opening_preview(self.session, *args, **kwargs)

    def clear_wall_hosted_opening_preview(self, *args, **kwargs):
        return clear_wall_hosted_opening_preview(self.session, *args, **kwargs)

    def get_wall_edit_readout_specs(self, *args, **kwargs):
        return get_wall_edit_readout_specs(self.session, *args, **kwargs)

    def get_default_wall_edit_readout_mode(self, *args, **kwargs):
        return get_default_wall_edit_readout_mode(self.session, *args, **kwargs)

    def bind_wall_edit_readout_callbacks(self, *args, **kwargs):
        return bind_wall_edit_readout_callbacks(self.session, *args, **kwargs)

    def update_wall_edit_readouts_in_place(self, *args, **kwargs):
        return update_wall_edit_readouts_in_place(self.session, *args, **kwargs)

    def sync_wall_edit_readout(self, *args, **kwargs):
        return sync_wall_edit_readout(self.session, *args, **kwargs)

    def clear_wall_edit_readout(self, *args, **kwargs):
        return clear_wall_edit_readout(self.session, *args, **kwargs)

    def get_wall_edit_readout_tracker(self, *args, **kwargs):
        return get_wall_edit_readout_tracker(self.session, *args, **kwargs)

    def cycle_wall_move_readout_mode(self, *args, **kwargs):
        return cycle_wall_move_readout_mode(self.session, *args, **kwargs)

    def start_wall_readout_edit(self, *args, **kwargs):
        return start_wall_readout_edit(self.session, *args, **kwargs)

    def start_wall_stretch_length_edit(self, *args, **kwargs):
        return start_wall_stretch_length_edit(self.session, *args, **kwargs)

    def start_wall_readout_edit_now(self, *args, **kwargs):
        return start_wall_readout_edit_now(self.session, *args, **kwargs)

    def on_wall_stretch_length_changed(self, *args, **kwargs):
        return on_wall_stretch_length_changed(self.session, *args, **kwargs)

    def on_wall_stretch_length_finished(self, *args, **kwargs):
        return on_wall_stretch_length_finished(self.session, *args, **kwargs)

    def on_wall_stretch_length_canceled(self, *args, **kwargs):
        return on_wall_stretch_length_canceled(self.session, *args, **kwargs)

    def compute_wall_edit_points_from_move_delta(self, *args, **kwargs):
        return compute_wall_edit_points_from_move_delta(self.session, *args, **kwargs)

    def on_wall_move_delta_changed(self, *args, **kwargs):
        return on_wall_move_delta_changed(self.session, *args, **kwargs)

    def on_wall_move_delta_finished(self, *args, **kwargs):
        return on_wall_move_delta_finished(self.session, *args, **kwargs)

    def on_wall_move_delta_canceled(self, *args, **kwargs):
        return on_wall_move_delta_canceled(self.session, *args, **kwargs)

    def schedule_wall_edit_readout_cancel(self, *args, **kwargs):
        return schedule_wall_edit_readout_cancel(self.session, *args, **kwargs)

    def finish_wall_edit_readout_canceled(self, *args, **kwargs):
        return finish_wall_edit_readout_canceled(self.session, *args, **kwargs)

    def restore_edit_wall_visibility(self, *args, **kwargs):
        return restore_edit_wall_visibility(self.session, *args, **kwargs)

    def update_wall_edit_preview(self, *args, **kwargs):
        return update_wall_edit_preview(self.session, *args, **kwargs)

    def update_wall_edit_point_pick(self, *args, **kwargs):
        return update_wall_edit_point_pick(self.session, *args, **kwargs)

    def cancel_wall_edit_point_pick(self, *args, **kwargs):
        return cancel_wall_edit_point_pick(self.session, *args, **kwargs)

    def refresh_wall_hosted_opening_footprints(self, *args, **kwargs):
        return refresh_wall_hosted_opening_footprints(self.session, *args, **kwargs)

    def compute_wall_hosted_opening_layout(self, *args, **kwargs):
        return compute_wall_hosted_opening_layout(self.session, *args, **kwargs)

    def resolve_wall_hosted_opening_layout(self, *args, **kwargs):
        return resolve_wall_hosted_opening_layout(self.session, *args, **kwargs)

    clip_preview_polygon_to_plane = staticmethod(clip_preview_polygon_to_plane)
