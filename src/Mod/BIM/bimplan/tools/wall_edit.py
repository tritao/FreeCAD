# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall edit interaction control for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimplan import selection as plan_selection

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = 10.0


def has_active_wall_edit(session):
    return session.wall_edit.is_wall_edit_modal_active() or session._embedded_tool_name == "Wall"


def is_wall_edit_modal_active(session):
    return bool(session._wall_edit_modal_active and session._edit_wall)


def is_selected_wall_endpoint_editable(session):
    wall = plan_selection.get_selected_plan_target_object(session, "wall")
    if not wall:
        return False
    proxy = getattr(wall, "Proxy", None)
    if not (hasattr(proxy, "calc_endpoints") and hasattr(proxy, "set_from_endpoints")):
        return False
    if not getattr(wall, "Base", None):
        return True
    try:
        import Draft

        return Draft.getType(getattr(wall, "Base", None)) == "BezCurve"
    except Exception:
        return False


def cancel_wall_edit(session, restore=True, refresh=True):
    del restore
    if not session.wall_edit.has_active_wall_edit():
        if refresh:
            session.current_tool = "Select"
            session.task_panels.refresh_task_panel_status()
        return False

    session.wall_edit.cancel_wall_subtool()

    session.current_tool = "Select"
    session.lifecycle.cancel_pending_edit()
    session.overlays.sync_selected_wall_opening_context_overlay()
    if refresh:
        session.task_panels.refresh_task_panel_status()
    return True


def cancel_wall_subtool(session):
    session.lifecycle.cancel_embedded_tool("Wall")


def start_wall_edit(session, mode):
    with session.performance.plan_perf_trace_span("start_wall_edit"):
        with session.performance.plan_perf_trace_span("start_wall_edit_validate"):
            if not session.is_selected_wall_endpoint_editable():
                FreeCAD.Console.PrintError(
                    translate(
                        "BIM_PlanEdit",
                        "Select a straight wall before using wall grips.\n",
                    )
                )
                return

            wall = plan_selection.get_selected_plan_target_object(session, "wall")
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

        with session.performance.plan_perf_trace_span("start_wall_edit_state"):
            session.wall_relations.clear_plan_relation_status()
            session.current_tool = "Move Wall" if mode == "Move" else f"Stretch {mode}"
            session.selection.set_hovered_wall(None)
            session.selection.set_hovered_opening(None)
            session.selection.set_hovered_symbol(None)
            session.selection.set_hovered_provider(None)
            if not session.selection.is_selected_plan_target("wall", wall):
                session.selection.set_selected_plan_target("wall", wall)
            session.overlays.clear_selected_wall_overlay()
            session.overlays.clear_selected_wall_opening_context_overlay()
            session._wall_edit_modal_active = True
            session._edit_wall = wall
            session._edit_endpoint = mode
            session._edit_endpoints = endpoints

        with session.performance.plan_perf_trace_span("start_wall_edit_queue_opening_clearances"):
            session._wall_edit_opening_clearances = {}
            session.wall_edit.queue_wall_edit_opening_clearances()

        with session.performance.plan_perf_trace_span("start_wall_edit_preview"):
            session._preview_points = list(endpoints)
            session._edit_wall_visibility = None
            try:
                session._edit_wall_visibility = wall.ViewObject.Visibility
                wall.ViewObject.Visibility = False
            except Exception:
                session._edit_wall_visibility = None
            session.overlays.clear_wall_grips()
            session.overlays.clear_selected_wall_overlay()
            session.wall_edit.sync_wall_edit_preview(
                session._preview_points, include_opening_preview=False
            )

        session.wall_edit.queue_wall_edit_task_panel_refresh()
        session.wall_edit.resume_wall_edit_point_pick()


def resume_wall_edit_point_pick(session):
    with session.performance.plan_perf_trace_span("resume_wall_edit_point_pick"):
        if not session.wall_edit.is_wall_edit_modal_active():
            return
        mode = session._edit_endpoint
        title = {
            "Start": translate("BIM_PlanEdit", "Pick new start point"),
            "End": translate("BIM_PlanEdit", "Pick new end point"),
            "Move": translate("BIM_PlanEdit", "Pick new wall midpoint"),
        }.get(mode, translate("BIM_PlanEdit", "Pick wall point"))
        last = session.wall_edit.get_wall_edit_reference_point()

        FreeCAD.activeDraftCommand = session
        if getattr(FreeCADGui, "Snapper", None):
            try:
                with session.performance.plan_perf_trace_span("wall_edit_snapper_set_select_mode"):
                    FreeCADGui.Snapper.setSelectMode(False)
            except Exception:
                pass
        with session.performance.plan_perf_trace_span("wall_edit_focus_suppression"):
            session.lifecycle.set_draft_point_focus_suppressed(True)
        with session.performance.plan_perf_trace_span("wall_edit_snapper_get_point"):
            FreeCADGui.Snapper.getPoint(
                callback=session.wall_edit.finish_wall_edit,
                movecallback=session.wall_edit.update_wall_edit_point_pick,
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
    QtCore.QTimer.singleShot(0, session.wall_edit.prime_wall_edit_opening_clearances)


def prime_wall_edit_opening_clearances(session):
    session._wall_edit_opening_clearances_queued = False
    if (
        session._tearing_down
        or not session.wall_edit.is_wall_stretch_edit_active()
        or session._wall_edit_opening_clearances
    ):
        return
    with session.performance.plan_perf_trace_event("queued_wall_edit_opening_clearances"):
        session._wall_edit_opening_clearances = (
            session.wall_edit.snapshot_wall_hosted_opening_clearances(
                session._edit_wall,
                session._edit_endpoints,
            )
        )


def ensure_wall_edit_opening_clearances(session, wall, endpoints):
    if session._wall_edit_opening_clearances or session._edit_endpoint not in ("Start", "End"):
        return
    session._wall_edit_opening_clearances_queued = False
    with session.performance.plan_perf_trace_span("ensure_wall_edit_opening_clearances"):
        session._wall_edit_opening_clearances = (
            session.wall_edit.snapshot_wall_hosted_opening_clearances(
                wall,
                endpoints,
            )
        )


def queue_wall_edit_task_panel_refresh(session):
    if session._tearing_down or session._wall_edit_task_panel_refresh_queued:
        return
    try:
        from PySide import QtCore
    except ImportError:
        session.task_panels.refresh_task_panel_status(selection_only=True)
        return
    session._wall_edit_task_panel_refresh_queued = True
    QtCore.QTimer.singleShot(0, session.wall_edit.flush_wall_edit_task_panel_refresh)


def flush_wall_edit_task_panel_refresh(session):
    session._wall_edit_task_panel_refresh_queued = False
    if session._tearing_down or not session.wall_edit.is_wall_edit_modal_active():
        return
    with session.performance.plan_perf_trace_event("queued_wall_edit_task_panel_refresh"):
        session.task_panels.refresh_task_panel_status(selection_only=True)


def finish_wall_edit(session, point=None, obj=None):
    del obj

    wall = session._edit_wall
    endpoint = session._edit_endpoint
    new_points = session.wall_edit.compute_wall_edit_points(point)

    if point is None or not wall or not endpoint or not new_points:
        session.current_tool = "Select"
        session.lifecycle.cancel_pending_edit()
        session.task_panels.refresh_task_panel_status()
        return

    proxy = getattr(wall, "Proxy", None)
    if (
        not proxy
        or not hasattr(proxy, "calc_endpoints")
        or not hasattr(proxy, "set_from_endpoints")
    ):
        session.current_tool = "Select"
        session.lifecycle.cancel_pending_edit()
        session.task_panels.refresh_task_panel_status()
        return

    session.wall_edit.commit_wall_edit_points(wall, endpoint, proxy, new_points)


def commit_wall_edit_points(session, wall, endpoint, proxy, new_points):
    if not wall or not endpoint or not proxy or not new_points:
        session.current_tool = "Select"
        session.lifecycle.cancel_pending_edit()
        session.task_panels.refresh_task_panel_status()
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
        openings_fit = session.openings.resolve_wall_hosted_opening_layout(wall)
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
        session.lifecycle.cancel_pending_edit()
        return
    session.openings.refresh_wall_hosted_opening_footprints(wall)
    session.selection.set_gui_selection_object(wall)
    session.current_tool = "Select"
    session.lifecycle.cancel_pending_edit()
    session.selection.set_selected_plan_target("wall", wall, pending_restore=True)
    session.wall_relations.update_wall_relation_status(wall)
    session.overlays.sync_wall_grips()
    session.task_panels.refresh_task_panel_status()


def start_wall_grip_edit(session, grip_index):
    if grip_index not in (0, 1, 2) or not session.is_selected_wall_endpoint_editable():
        return
    session.wall_edit.start_wall_edit({0: "Start", 1: "End", 2: "Move"}[grip_index])


def activate_wall_grip(session, grip_index, wall=None):
    if wall is None:
        wall = plan_selection.get_selected_plan_target_object(session, "wall")
    try:
        from PySide import QtCore
    except ImportError:
        session.wall_edit.activate_wall_grip_now(grip_index, wall)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda wall=wall, grip_index=grip_index: session.wall_edit.activate_wall_grip_now(
            grip_index, wall
        ),
    )


def activate_wall_grip_now(session, grip_index, wall=None):
    with session.performance.plan_perf_trace_span("activate_wall_grip_now"):
        if session._tearing_down or session.current_tool != "Select" or not wall:
            return
        with session.performance.plan_perf_trace_span("activate_wall_grip_set_target"):
            if not session.selection.is_selected_plan_target("wall", wall):
                session.selection.set_selected_plan_target("wall", wall)
        with session.performance.plan_perf_trace_span("activate_wall_grip_start_edit"):
            session.wall_edit.start_wall_grip_edit(grip_index)


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


def get_preview_footprint(session, points, width=None, align=None):
    wall = session._edit_wall
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
            if self._wrapped_proxy and hasattr(self._wrapped_proxy, "get_width"):
                return self._wrapped_proxy.get_width(wall, widths=widths)
            width = getattr(getattr(wall, "Width", None), "Value", getattr(wall, "Width", None))
            return width

        def get_layers(self, _obj):
            if self._wrapped_proxy and hasattr(self._wrapped_proxy, "get_layers"):
                return self._wrapped_proxy.get_layers(wall)
            return None

    class _PreviewWall:
        def __init__(self):
            self._wall = wall
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

        def __getattr__(self, attr):
            return getattr(self._wall, attr)

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

    preview_wall = session.wall_edit.make_preview_wall_adapter(wall, points)
    if not preview_wall:
        return {"Start": None, "End": None, "Conflicts": set()}, []

    import ArchWallJoinUtils

    claims = {"Start": [], "End": []}
    warnings = []
    for relation in ArchWallJoinUtils.iter_wall_relations(wall):
        solution = session.wall_edit.solve_preview_wall_relation(relation, wall, preview_wall)
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
    footprint = session.wall_edit.get_preview_footprint(points)
    if not footprint or len(footprint) < 3:
        return [], []

    relation_endings, warnings = session.wall_edit.collect_preview_wall_relation_data(
        session._edit_wall, points
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
    base_gap = max(width * 0.25, session.wall_edit.get_readout_base_gap())
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
        return session.wall_edit.get_readout_base_gap()
    if mode != 1:
        return None
    return session.wall_edit.get_aligned_readout_offset_for_wall(session._edit_wall)


def get_opening_move_readout_offset(session, opening):
    host = next(iter(getattr(opening, "Hosts", None) or []), None) if opening else None
    return session.wall_edit.get_aligned_readout_offset_for_wall(host)


def update_wall_edit_preview_geometry(session, points):
    if not points or len(points) != 2:
        return

    try:
        import draftguitools.gui_trackers as DraftTrackers
        from draftutils import params
    except Exception:
        return

    if session._preview_line_tracker is None:
        session._preview_line_tracker = session.overlays.make_plan_line_tracker(
            DraftTrackers,
            "wall-edit-preview-axis",
            swidth=session.viewport.scaled_line_width(2),
            ontop=True,
        )
        session._preview_line_tracker.on()
    session._preview_line_tracker.p1(points[0])
    session._preview_line_tracker.p2(points[1])

    previous_relation_status = session._plan_relation_status_message
    polylines, relation_warnings = session.wall_edit.get_preview_footprint_polylines(points)
    if relation_warnings:
        label, status, _detail = relation_warnings[0]
        session._plan_relation_status_message = translate(
            "BIM_PlanEdit", "Preview warning: {label} ({status})"
        ).format(label=label, status=status)
    elif session.wall_edit.is_wall_edit_modal_active():
        session.wall_relations.clear_plan_relation_status()

    segments = []
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        segments.extend(zip(polyline, polyline[1:]))

    color = (0.22, 0.53, 0.98)
    width = session.viewport.scaled_line_width(2)
    if len(session._preview_footprint_trackers) != len(segments):
        session.overlays.finalize_trackers(session._preview_footprint_trackers)
        session._preview_footprint_trackers = []
        for _start, _end in segments:
            tracker = session.overlays.make_plan_line_tracker(
                DraftTrackers,
                "wall-edit-preview-footprint",
                scolor=color,
                swidth=width,
                ontop=True,
            )
            session._preview_footprint_trackers.append(tracker)

    for tracker, (start, end) in zip(session._preview_footprint_trackers, segments):
        tracker.setColor(color)
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()

    if previous_relation_status != session._plan_relation_status_message:
        session.task_panels.refresh_task_panel_status()

    midpoint = (points[0] + points[1]) * 0.5
    marker_size = session.viewport.scaled_marker_size(params.get_param_view("MarkerSize"))
    midpoint_marker = FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size)

    grip_specs = (
        (points[0], 0, None),
        (points[1], 1, None),
        (midpoint, 2, midpoint_marker),
    )
    if not session._preview_grip_trackers:
        for position, idx, marker in grip_specs:
            tracker = DraftTrackers.editTracker(
                pos=position,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            session._preview_grip_trackers.append(tracker)
        return

    for tracker, (position, _idx, _marker) in zip(session._preview_grip_trackers, grip_specs):
        tracker.set(position)
        tracker.on()


def sync_wall_edit_preview(session, points, include_opening_preview=True):
    session.wall_edit.update_wall_edit_preview_geometry(points)
    session.wall_edit.sync_wall_edit_readout(points)
    if include_opening_preview:
        session.wall_edit.sync_wall_hosted_opening_preview(points)
    else:
        session.wall_edit.clear_wall_hosted_opening_preview()


def is_wall_move_edit_active(session):
    return bool(
        session._edit_wall
        and session._edit_endpoint == "Move"
        and session.current_tool == "Move Wall"
    )


def is_wall_stretch_edit_active(session):
    return bool(
        session._edit_wall
        and session._edit_endpoint in ("Start", "End")
        and session.current_tool in ("Stretch Start", "Stretch End")
    )


def is_wall_readout_edit_active(session):
    return bool(
        session.wall_edit.is_wall_move_edit_active()
        or session.wall_edit.is_wall_stretch_edit_active()
    )


def clear_wall_edit_preview(session):
    if session._preview_line_tracker:
        try:
            session._preview_line_tracker.finalize()
        except Exception:
            pass
    session._preview_line_tracker = None

    session.overlays.finalize_trackers(session._preview_footprint_trackers)
    session._preview_footprint_trackers = []

    for tracker in session._preview_grip_trackers:
        try:
            tracker.finalize()
        except Exception:
            pass
    session._preview_grip_trackers = []
    session.wall_edit.clear_wall_edit_readout()
    session.wall_edit.clear_wall_hosted_opening_preview()


def get_wall_hosted_opening_preview_segments(session, wall, points):
    if not wall or not points or len(points) != 2:
        return []
    if session._edit_endpoint not in ("Start", "End"):
        return []

    layout = session.openings.compute_wall_hosted_opening_layout(wall, points)
    if layout is None:
        return []

    segments = []
    for item in layout:
        delta = FreeCAD.Vector(item["target_point"]).sub(item["current"])
        if delta.Length < 1e-6:
            continue
        for polyline in session.overlays.get_opening_overlay_polylines(item["opening"]):
            if len(polyline) < 2:
                continue
            translated = [FreeCAD.Vector(point).add(delta) for point in polyline]
            segments.extend(zip(translated, translated[1:]))
    return segments


def sync_wall_hosted_opening_preview(session, points):
    wall = session._edit_wall
    if session.current_tool not in ("Stretch Start", "Stretch End") or not wall:
        session.wall_edit.clear_wall_hosted_opening_preview()
        return

    segments = session.wall_edit.get_wall_hosted_opening_preview_segments(wall, points)
    if not segments:
        session.wall_edit.clear_wall_hosted_opening_preview()
        return

    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        session.wall_edit.clear_wall_hosted_opening_preview()
        return

    color = (0.12, 0.38, 0.95)
    width = session.viewport.scaled_line_width(2)
    if len(session._wall_edit_opening_preview_trackers) != len(segments):
        session.wall_edit.clear_wall_hosted_opening_preview()
        for _start, _end in segments:
            tracker = session.overlays.make_plan_line_tracker(
                DraftTrackers,
                "wall-edit-opening-preview",
                scolor=color,
                swidth=width,
                ontop=True,
            )
            session._wall_edit_opening_preview_trackers.append(tracker)

    for tracker, (start, end) in zip(session._wall_edit_opening_preview_trackers, segments):
        tracker.setColor(color)
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()


def clear_wall_hosted_opening_preview(session):
    session.overlays.finalize_trackers(session._wall_edit_opening_preview_trackers)
    session._wall_edit_opening_preview_trackers = []


def refresh_wall_hosted_opening_footprints(session, wall):
    for opening in session.openings.get_wall_hosted_openings(wall):
        session.document_visuals.refresh_opening_footprint_display(opening)


def compute_wall_hosted_opening_layout(session, wall, endpoints):
    if not wall:
        return []
    if not endpoints or len(endpoints) != 2:
        return []
    wall_origin = FreeCAD.Vector(endpoints[0])
    wall_end = FreeCAD.Vector(endpoints[1])
    wall_axis_u = wall_end.sub(wall_origin)
    wall_length = wall_axis_u.Length
    if wall_length < 1e-9:
        return None
    wall_axis_u.normalize()
    session.wall_edit.ensure_wall_edit_opening_clearances(wall, endpoints)

    openings = []
    for opening in session.openings.get_wall_hosted_openings(wall):
        proxy = session.openings.get_opening_plan_proxy(
            opening, "get_plan_move_context", "move_along_host", "get_plan_center_point"
        )
        if not proxy:
            continue
        context = proxy.get_plan_move_context()
        if not context:
            continue
        current_center = proxy.get_plan_center_point()
        if current_center is None:
            continue
        current = FreeCAD.Vector(current_center)
        delta = current.sub(wall_origin)
        half_width = float(context.get("opening_half_width_u") or 0.0)
        desired_u = delta.dot(wall_axis_u)
        clearance_seed = session._wall_edit_opening_clearances.get(getattr(opening, "Name", ""))
        if clearance_seed:
            if session._edit_endpoint == "Start":
                desired_u = max(
                    desired_u,
                    half_width + float(clearance_seed.get("left_clearance") or 0.0),
                )
            elif session._edit_endpoint == "End":
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
        item = {
            "opening": opening,
            "proxy": proxy,
            "current": current,
            "desired_u": desired_u,
            "low": low,
            "high": high,
            "half_width": half_width,
            "clearance_seed": clearance_seed,
        }
        openings.append(item)

    if not openings:
        return []

    openings.sort(key=lambda item: (item["desired_u"], getattr(item["opening"], "Name", "")))

    left = []
    for index, item in enumerate(openings):
        minimum = item["low"]
        if index > 0:
            minimum = max(
                minimum,
                left[index - 1] + openings[index - 1]["half_width"] + item["half_width"],
            )
        if minimum > item["high"] + 1e-6:
            return None
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
            return None
        right[index] = maximum

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


def resolve_wall_hosted_opening_layout(session, wall):
    wall_proxy = getattr(wall, "Proxy", None)
    if not wall_proxy or not hasattr(wall_proxy, "calc_endpoints"):
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
    if not points or len(points) != 2 or not session._edit_endpoints:
        return []

    original_points = session._edit_endpoints
    if session._edit_endpoint == "Move":
        original_midpoint = (original_points[0] + original_points[1]) * 0.5
        new_midpoint = (points[0] + points[1]) * 0.5
        return [
            (2, original_midpoint, new_midpoint),
            (3, original_midpoint, new_midpoint),
        ]

    return [(1, points[0], points[1])]


def get_default_wall_edit_readout_mode(session, specs):
    modes = [mode for mode, _start, _end in specs]
    if not modes:
        return None
    if session.wall_edit.is_wall_move_edit_active():
        if session._wall_edit_active_readout_mode in modes:
            return session._wall_edit_active_readout_mode
        if 2 in modes:
            return 2
    if 1 in modes:
        return 1
    return modes[0]


def bind_wall_edit_readout_callbacks(session, dim, mode):
    if mode == 1:
        dim.setValueChangedCallback(session.wall_edit.on_wall_stretch_length_changed)
        dim.setEditingFinishedCallback(session.wall_edit.on_wall_stretch_length_finished)
        if hasattr(dim, "setEditingCanceledCallback"):
            dim.setEditingCanceledCallback(session.wall_edit.on_wall_stretch_length_canceled)
        return

    dim.setValueChangedCallback(
        lambda value, delta_mode=mode: session.wall_edit.on_wall_move_delta_changed(
            delta_mode, value
        )
    )
    dim.setEditingFinishedCallback(
        lambda value, delta_mode=mode: session.wall_edit.on_wall_move_delta_finished(
            delta_mode, value
        )
    )
    if hasattr(dim, "setEditingCanceledCallback"):
        dim.setEditingCanceledCallback(
            lambda value, delta_mode=mode: session.wall_edit.on_wall_move_delta_canceled(
                delta_mode, value
            )
        )


def update_wall_edit_readouts_in_place(session, points, active_mode=None):
    specs = {
        mode: (start, end)
        for mode, start, end in session.wall_edit.get_wall_edit_readout_specs(points)
    }
    for tracker in session._wall_edit_readout_trackers:
        mode = getattr(tracker, "mode", None)
        if mode not in specs:
            continue
        start, end = specs[mode]
        if hasattr(tracker, "updatePoints"):
            tracker.updatePoints(start, end, sync_spinbox=(mode != active_mode))
        else:
            tracker.p1(start)
            tracker.p2(end)
        tracker.on()


def sync_wall_edit_readout(session, points):
    session.wall_edit.clear_wall_edit_readout()
    if not points or len(points) != 2 or not session._edit_endpoints:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return

    readout_color = (0.12, 0.38, 0.95)
    dims = session.wall_edit.get_wall_edit_readout_specs(points)
    active_mode = session.wall_edit.get_default_wall_edit_readout_mode(dims)
    session._wall_edit_active_readout_mode = active_mode

    for mode, start, end in dims:
        try:
            if session.wall_edit.is_wall_readout_edit_active():
                dim = DraftTrackers.editableArchDimTracker(mode=mode)
            else:
                dim = DraftTrackers.archDimTracker(mode=mode)
        except Exception:
            continue
        try:
            if hasattr(dim, "dimnode"):
                dim.dimnode.textColor.setValue(readout_color)
            else:
                dim.setColor(readout_color)
        except Exception:
            pass
        offset = session.wall_edit.get_wall_edit_readout_offset(mode)
        if offset is not None:
            dim.offset = offset
        dim.p1(start)
        dim.p2(end)
        dim.on()
        if session.wall_edit.is_wall_readout_edit_active() and hasattr(
            dim, "setValueChangedCallback"
        ):
            session.wall_edit.bind_wall_edit_readout_callbacks(dim, mode)
            if mode == active_mode:
                session._wall_edit_active_readout_mode = mode
                session._wall_edit_active_readout_tracker = dim
        if session._wall_edit_active_readout_tracker is None:
            session._wall_edit_active_readout_tracker = dim
        session._wall_edit_readout_trackers.append(dim)


def clear_wall_edit_readout(session):
    session.overlays.finalize_trackers(session._wall_edit_readout_trackers)
    session._wall_edit_readout_trackers = []
    session._wall_edit_active_readout_tracker = None
    session._wall_edit_active_readout_mode = None
    session._wall_edit_length_edit_queued = False


def get_wall_edit_readout_tracker(session, mode):
    for tracker in session._wall_edit_readout_trackers:
        if getattr(tracker, "mode", None) == mode:
            return tracker
    return None


def cycle_wall_move_readout_mode(session):
    if not session.wall_edit.is_wall_move_edit_active():
        return False
    modes = [
        getattr(tracker, "mode", None)
        for tracker in session._wall_edit_readout_trackers
        if getattr(tracker, "mode", None) in (2, 3)
    ]
    modes = [mode for mode in modes if mode is not None]
    if not modes:
        return False
    current_mode = (
        session._wall_edit_active_readout_mode
        if session._wall_edit_active_readout_mode in modes
        else modes[0]
    )
    next_mode = modes[(modes.index(current_mode) + 1) % len(modes)]
    session._wall_edit_active_readout_mode = next_mode
    tracker = session.wall_edit.get_wall_edit_readout_tracker(next_mode)
    if tracker is not None:
        session._wall_edit_active_readout_tracker = tracker
    return True


def start_wall_readout_edit(session, cycle=False):
    tracker = session._wall_edit_active_readout_tracker
    if not session.wall_edit.is_wall_readout_edit_active():
        return False
    if cycle and session.wall_edit.is_wall_move_edit_active():
        if (
            tracker is not None
            and hasattr(tracker, "isInEdit")
            and tracker.isInEdit()
            and hasattr(tracker, "stopEdit")
        ):
            tracker.stopEdit()
        if not session.wall_edit.cycle_wall_move_readout_mode():
            return False
        tracker = session._wall_edit_active_readout_tracker
    if tracker is None:
        return False
    if not hasattr(tracker, "startEdit"):
        return False
    if hasattr(tracker, "isInEdit") and tracker.isInEdit():
        if hasattr(tracker, "label"):
            tracker.label.setFocusToSpinbox()
        return True
    if session._wall_edit_length_edit_queued:
        return True
    session._wall_edit_length_edit_queued = True
    session.lifecycle.stop_snapper()
    try:
        from PySide import QtCore
    except ImportError:
        session._wall_edit_length_edit_queued = False
        tracker.startEdit(tracker.Distance)
        return True
    QtCore.QTimer.singleShot(
        0, lambda: session.wall_edit.start_wall_readout_edit_now(tracker, tracker.Distance)
    )
    return True


def start_wall_stretch_length_edit(session):
    return session.wall_edit.start_wall_readout_edit(cycle=False)


def start_wall_readout_edit_now(session, tracker, value):
    session._wall_edit_length_edit_queued = False
    if not session.wall_edit.is_wall_readout_edit_active():
        return
    if tracker is None or tracker is not session._wall_edit_active_readout_tracker:
        return
    if not hasattr(tracker, "startEdit"):
        return
    if hasattr(tracker, "isInEdit") and tracker.isInEdit():
        if hasattr(tracker, "label"):
            tracker.label.setFocusToSpinbox()
        return
    try:
        tracker.startEdit(value)
    except Exception:
        return


def on_wall_stretch_length_changed(session, value):
    if not session.wall_edit.is_wall_stretch_edit_active():
        return
    new_points = session.wall_edit.compute_wall_edit_points_from_length(value)
    tracker = session._wall_edit_active_readout_tracker
    if not new_points or tracker is None:
        return
    session._preview_points = new_points
    session.wall_edit.update_wall_edit_preview_geometry(new_points)
    session.wall_edit.update_wall_edit_readouts_in_place(new_points, active_mode=1)
    session.wall_edit.sync_wall_hosted_opening_preview(new_points)


def on_wall_stretch_length_finished(session, value):
    if not session.wall_edit.is_wall_stretch_edit_active():
        return
    wall = session._edit_wall
    endpoint = session._edit_endpoint
    proxy = getattr(wall, "Proxy", None)
    new_points = session.wall_edit.compute_wall_edit_points_from_length(value)
    if not new_points or not proxy:
        return
    session._preview_points = new_points
    session.wall_edit.commit_wall_edit_points(wall, endpoint, proxy, new_points)


def on_wall_stretch_length_canceled(session, value):
    del value
    if not session.wall_edit.is_wall_stretch_edit_active():
        return
    session.wall_edit.schedule_wall_edit_readout_cancel()


def compute_wall_edit_points_from_move_delta(session, mode, value):
    if not session.wall_edit.is_wall_move_edit_active() or not session._edit_endpoints:
        return None
    original_endpoints = session._edit_endpoints
    original_midpoint = (original_endpoints[0] + original_endpoints[1]) * 0.5
    preview_points = session._preview_points if session._preview_points else original_endpoints
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
    if not session.wall_edit.is_wall_move_edit_active():
        return
    new_points = session.wall_edit.compute_wall_edit_points_from_move_delta(mode, value)
    if not new_points:
        return
    session._preview_points = new_points
    session.wall_edit.update_wall_edit_preview_geometry(new_points)
    session.wall_edit.update_wall_edit_readouts_in_place(new_points, active_mode=mode)
    session.wall_edit.sync_wall_hosted_opening_preview(new_points)


def on_wall_move_delta_finished(session, mode, value):
    if not session.wall_edit.is_wall_move_edit_active():
        return
    wall = session._edit_wall
    endpoint = session._edit_endpoint
    proxy = getattr(wall, "Proxy", None)
    new_points = session.wall_edit.compute_wall_edit_points_from_move_delta(mode, value)
    if not new_points or not proxy:
        return
    session._preview_points = new_points
    session.wall_edit.commit_wall_edit_points(wall, endpoint, proxy, new_points)


def on_wall_move_delta_canceled(session, mode, value):
    del mode, value
    if not session.wall_edit.is_wall_move_edit_active():
        return
    session.wall_edit.schedule_wall_edit_readout_cancel()


def schedule_wall_edit_readout_cancel(session):
    preview_points = None
    if session._preview_points:
        preview_points = [FreeCAD.Vector(point) for point in session._preview_points]
    elif session._edit_endpoints:
        preview_points = [FreeCAD.Vector(point) for point in session._edit_endpoints]
    try:
        from PySide import QtCore
    except ImportError:
        session.wall_edit.finish_wall_edit_readout_canceled(preview_points)
        return
    QtCore.QTimer.singleShot(
        0, lambda pts=preview_points: session.wall_edit.finish_wall_edit_readout_canceled(pts)
    )


def finish_wall_edit_readout_canceled(session, preview_points):
    if not session.wall_edit.is_wall_readout_edit_active():
        return
    if preview_points:
        session.wall_edit.sync_wall_edit_preview(preview_points)
    session.wall_edit.resume_wall_edit_point_pick()


def restore_edit_wall_visibility(session):
    wall = session._edit_wall
    if wall is not None and session._edit_wall_visibility is not None:
        try:
            wall.ViewObject.Visibility = session._edit_wall_visibility
        except Exception:
            pass
    session._edit_wall_visibility = None


def update_wall_edit_preview(session, point):
    new_points = session.wall_edit.compute_wall_edit_points(point)
    if not new_points:
        return
    session._preview_points = new_points
    session.wall_edit.sync_wall_edit_preview(new_points)


def update_wall_edit_point_pick(session, point=None, snap_info=None):
    del snap_info
    if session._wall_edit_active_readout_tracker and hasattr(
        session._wall_edit_active_readout_tracker, "isInEdit"
    ):
        if session._wall_edit_active_readout_tracker.isInEdit():
            return
    session.wall_edit.update_wall_edit_preview(point)


def cancel_wall_edit_point_pick(session):
    session.current_tool = "Select"
    session.lifecycle.cancel_pending_edit()
    session.task_panels.refresh_task_panel_status()


from functools import wraps


def _bind_session_call(func):
    @wraps(func)
    def method(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    return method


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class PlanWallEditAPI(_SessionAPI):
    """Owned session surface for Plan Edit wall edit behavior."""

    __slots__ = ()

    has_active_wall_edit = _bind_session_call(has_active_wall_edit)
    is_wall_edit_modal_active = _bind_session_call(is_wall_edit_modal_active)
    is_selected_wall_endpoint_editable = _bind_session_call(is_selected_wall_endpoint_editable)
    cancel_wall_edit = _bind_session_call(cancel_wall_edit)
    cancel_wall_subtool = _bind_session_call(cancel_wall_subtool)
    start_wall_edit = _bind_session_call(start_wall_edit)
    resume_wall_edit_point_pick = _bind_session_call(resume_wall_edit_point_pick)
    snapshot_wall_hosted_opening_clearances = _bind_session_call(
        snapshot_wall_hosted_opening_clearances
    )
    queue_wall_edit_opening_clearances = _bind_session_call(queue_wall_edit_opening_clearances)
    prime_wall_edit_opening_clearances = _bind_session_call(prime_wall_edit_opening_clearances)
    ensure_wall_edit_opening_clearances = _bind_session_call(ensure_wall_edit_opening_clearances)
    queue_wall_edit_task_panel_refresh = _bind_session_call(queue_wall_edit_task_panel_refresh)
    flush_wall_edit_task_panel_refresh = _bind_session_call(flush_wall_edit_task_panel_refresh)
    finish_wall_edit = _bind_session_call(finish_wall_edit)
    commit_wall_edit_points = _bind_session_call(commit_wall_edit_points)
    start_wall_grip_edit = _bind_session_call(start_wall_grip_edit)
    activate_wall_grip = _bind_session_call(activate_wall_grip)
    activate_wall_grip_now = _bind_session_call(activate_wall_grip_now)
    get_wall_edit_reference_point = _bind_session_call(get_wall_edit_reference_point)
    compute_wall_edit_points = _bind_session_call(compute_wall_edit_points)
    compute_wall_edit_points_from_length = _bind_session_call(compute_wall_edit_points_from_length)
    get_preview_footprint = _bind_session_call(get_preview_footprint)
    make_preview_wall_adapter = _bind_session_call(make_preview_wall_adapter)
    solve_preview_wall_relation = _bind_session_call(solve_preview_wall_relation)
    collect_preview_wall_relation_data = _bind_session_call(collect_preview_wall_relation_data)
    get_preview_footprint_polylines = _bind_session_call(get_preview_footprint_polylines)
    get_readout_base_gap = _bind_session_call(get_readout_base_gap)
    get_aligned_readout_offset_for_wall = _bind_session_call(get_aligned_readout_offset_for_wall)
    get_wall_edit_readout_offset = _bind_session_call(get_wall_edit_readout_offset)
    get_opening_move_readout_offset = _bind_session_call(get_opening_move_readout_offset)
    update_wall_edit_preview_geometry = _bind_session_call(update_wall_edit_preview_geometry)
    sync_wall_edit_preview = _bind_session_call(sync_wall_edit_preview)
    is_wall_move_edit_active = _bind_session_call(is_wall_move_edit_active)
    is_wall_stretch_edit_active = _bind_session_call(is_wall_stretch_edit_active)
    is_wall_readout_edit_active = _bind_session_call(is_wall_readout_edit_active)
    clear_wall_edit_preview = _bind_session_call(clear_wall_edit_preview)
    get_wall_hosted_opening_preview_segments = _bind_session_call(
        get_wall_hosted_opening_preview_segments
    )
    sync_wall_hosted_opening_preview = _bind_session_call(sync_wall_hosted_opening_preview)
    clear_wall_hosted_opening_preview = _bind_session_call(clear_wall_hosted_opening_preview)
    get_wall_edit_readout_specs = _bind_session_call(get_wall_edit_readout_specs)
    get_default_wall_edit_readout_mode = _bind_session_call(get_default_wall_edit_readout_mode)
    bind_wall_edit_readout_callbacks = _bind_session_call(bind_wall_edit_readout_callbacks)
    update_wall_edit_readouts_in_place = _bind_session_call(update_wall_edit_readouts_in_place)
    sync_wall_edit_readout = _bind_session_call(sync_wall_edit_readout)
    clear_wall_edit_readout = _bind_session_call(clear_wall_edit_readout)
    get_wall_edit_readout_tracker = _bind_session_call(get_wall_edit_readout_tracker)
    cycle_wall_move_readout_mode = _bind_session_call(cycle_wall_move_readout_mode)
    start_wall_readout_edit = _bind_session_call(start_wall_readout_edit)
    start_wall_stretch_length_edit = _bind_session_call(start_wall_stretch_length_edit)
    start_wall_readout_edit_now = _bind_session_call(start_wall_readout_edit_now)
    on_wall_stretch_length_changed = _bind_session_call(on_wall_stretch_length_changed)
    on_wall_stretch_length_finished = _bind_session_call(on_wall_stretch_length_finished)
    on_wall_stretch_length_canceled = _bind_session_call(on_wall_stretch_length_canceled)
    compute_wall_edit_points_from_move_delta = _bind_session_call(
        compute_wall_edit_points_from_move_delta
    )
    on_wall_move_delta_changed = _bind_session_call(on_wall_move_delta_changed)
    on_wall_move_delta_finished = _bind_session_call(on_wall_move_delta_finished)
    on_wall_move_delta_canceled = _bind_session_call(on_wall_move_delta_canceled)
    schedule_wall_edit_readout_cancel = _bind_session_call(schedule_wall_edit_readout_cancel)
    finish_wall_edit_readout_canceled = _bind_session_call(finish_wall_edit_readout_canceled)
    restore_edit_wall_visibility = _bind_session_call(restore_edit_wall_visibility)
    update_wall_edit_preview = _bind_session_call(update_wall_edit_preview)
    update_wall_edit_point_pick = _bind_session_call(update_wall_edit_point_pick)
    cancel_wall_edit_point_pick = _bind_session_call(cancel_wall_edit_point_pick)
    refresh_wall_hosted_opening_footprints = _bind_session_call(
        refresh_wall_hosted_opening_footprints
    )
    compute_wall_hosted_opening_layout = _bind_session_call(compute_wall_hosted_opening_layout)
    resolve_wall_hosted_opening_layout = _bind_session_call(resolve_wall_hosted_opening_layout)

    clip_preview_polygon_to_plane = staticmethod(clip_preview_polygon_to_plane)
