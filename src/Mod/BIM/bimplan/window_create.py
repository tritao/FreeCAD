# SPDX-License-Identifier: LGPL-2.1-or-later

"""Hosted window creation helpers for BIM Plan Edit."""

from contextlib import nullcontext

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate

DEFAULT_WINDOW_WIDTH = 900.0
DEFAULT_WINDOW_HEIGHT = 1200.0
DEFAULT_WINDOW_SILL_HEIGHT = 900.0
DEFAULT_WINDOW_FRAME_THICKNESS = 60.0
DEFAULT_WINDOW_GLASS_THICKNESS = 10.0


def can_place_window(session):
    return get_window_host_wall(session) is not None


def get_window_host_wall(session):
    wall = session._get_selected_plan_target_object("wall")
    if session._is_plan_selectable_wall(wall):
        return wall
    wall = getattr(session, "hovered_wall", None)
    if session._is_plan_selectable_wall(wall):
        return wall
    return None


def activate_window_tool(session):
    wall = get_window_host_wall(session)
    if not wall:
        FreeCAD.Console.PrintWarning(
            translate("BIM_PlanEdit", "Select or hover a wall before placing a window.\n")
        )
        return False

    session._set_selected_plan_target("wall", wall)
    session._restore_gui_selection(wall)
    session._window_host_wall = wall
    session.current_tool = "Window"
    FreeCAD.activeDraftCommand = session
    try:
        FreeCADGui.Snapper.setSelectMode(False)
    except Exception:
        pass
    session._set_draft_point_focus_suppressed(True)
    FreeCADGui.Snapper.getPoint(
        callback=session._handle_window_tool_point,
        movecallback=session._update_window_tool_preview,
        title=translate("BIM_PlanEdit", "Window location"),
        noTracker=True,
    )
    session._queue_focus_plan_view()
    session._refresh_task_panel_status()
    return True


def has_active_window_tool(session):
    return session.current_tool == "Window" or session._window_host_wall is not None


def clear_window_preview(session):
    session._finalize_trackers(session._window_preview_trackers)
    session._window_preview_trackers = []


def cancel_window_tool(session, refresh=True):
    if not has_active_window_tool(session):
        return False
    session._stop_snapper()
    clear_window_preview(session)
    session._window_host_wall = None
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if refresh:
        session._refresh_task_panel_status()
    return True


def _coerce_length(value, default=0.0):
    try:
        value = value.Value
    except AttributeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _get_wall_axis_context(wall):
    proxy = getattr(wall, "Proxy", None)
    if proxy is None or not hasattr(proxy, "calc_endpoints"):
        return None
    try:
        endpoints = proxy.calc_endpoints(wall)
        start = FreeCAD.Vector(endpoints[0])
        end = FreeCAD.Vector(endpoints[1])
    except Exception:
        return None
    axis = end.sub(start)
    axis.z = 0.0
    length = axis.Length
    if length <= 1e-9:
        return None
    axis.normalize()
    vertical = FreeCAD.Vector(0, 0, 1)
    normal = axis.cross(vertical)
    if normal.Length <= 1e-9:
        return None
    normal.normalize()
    wall_width = _coerce_length(getattr(wall, "Width", None), 200.0)
    return {
        "start": start,
        "end": end,
        "axis": axis,
        "vertical": vertical,
        "normal": normal,
        "length": length,
        "base_z": start.z,
        "wall_width": wall_width,
    }


def _get_window_snap_info(info=None):
    if isinstance(info, dict):
        return dict(info)
    snapper = getattr(FreeCADGui, "Snapper", None)
    if snapper is None:
        return {}
    snap_info = getattr(snapper, "snapInfo", None)
    if isinstance(snap_info, dict):
        return dict(snap_info)
    return {}


def _resolve_window_snap_object(session, snap_object=None, snap_info=None):
    if snap_object is not None and not isinstance(snap_object, dict):
        return snap_object
    snap_info = _get_window_snap_info(snap_info)
    object_name = str(snap_info.get("Object", "") or "").strip()
    if not object_name:
        return None
    doc = session.doc
    document_name = str(snap_info.get("Document", "") or "").strip()
    if document_name:
        try:
            doc = FreeCAD.getDocument(document_name)
        except Exception:
            doc = session.doc
    if doc is None:
        return None
    try:
        return doc.getObject(object_name)
    except Exception:
        return None


def _get_opening_host_wall(session, opening):
    if not session._is_hosted_opening_object(opening):
        return None
    for host in getattr(opening, "Hosts", None) or ():
        if session._is_plan_selectable_wall(host):
            return host
    return None


def _get_wall_from_target(session, target_kind, target_obj):
    if target_kind == "wall" and session._is_plan_selectable_wall(target_obj):
        return target_obj
    if target_kind == "opening":
        return _get_opening_host_wall(session, target_obj)
    return None


def _get_wall_from_snap_object(session, snap_object):
    if snap_object is None:
        return None
    target_kind, target_obj = session._get_plan_target_for_object(snap_object)
    wall = _get_wall_from_target(session, target_kind, target_obj)
    if wall is not None:
        return wall
    if session._is_plan_selectable_wall(snap_object):
        return snap_object
    wall = _get_opening_host_wall(session, snap_object)
    if wall is not None:
        return wall

    linked_objects = []
    try:
        linked_objects.extend(snap_object.InList)
    except Exception:
        pass
    try:
        linked_objects.extend(snap_object.InListRecursive)
    except Exception:
        pass
    for candidate in linked_objects:
        target_kind, target_obj = session._get_plan_target_for_object(candidate)
        wall = _get_wall_from_target(session, target_kind, target_obj)
        if wall is not None:
            return wall
    return None


def resolve_window_host_wall(session, snap_object=None, snap_info=None):
    snap_info = _get_window_snap_info(snap_info)
    resolved_snap_object = _resolve_window_snap_object(
        session,
        snap_object=snap_object,
        snap_info=snap_info,
    )
    wall = _get_wall_from_snap_object(session, resolved_snap_object)
    if wall is not None:
        return wall
    wall = getattr(session, "_window_host_wall", None)
    if session._is_plan_selectable_wall(wall):
        return wall
    return get_window_host_wall(session)


def project_window_point_to_host(session, point, wall=None):
    wall = wall or resolve_window_host_wall(session)
    if point is None or wall is None:
        return None
    context = _get_wall_axis_context(wall)
    if not context:
        return None
    try:
        source = FreeCAD.Vector(point)
    except Exception:
        return None
    offset = source.sub(context["start"])
    offset.z = 0.0
    half_width = DEFAULT_WINDOW_WIDTH * 0.5
    target_u = offset.dot(context["axis"])
    if context["length"] >= DEFAULT_WINDOW_WIDTH:
        target_u = min(max(target_u, half_width), context["length"] - half_width)
    else:
        target_u = context["length"] * 0.5
    projected = context["start"].add(FreeCAD.Vector(context["axis"]).multiply(target_u))
    projected.z = context["base_z"]
    return projected


def _get_window_preview_points(session, point, wall=None):
    wall = wall or resolve_window_host_wall(session)
    center = project_window_point_to_host(session, point, wall)
    context = _get_wall_axis_context(wall)
    if center is None or not context:
        return ()
    half_width = DEFAULT_WINDOW_WIDTH * 0.5
    half_depth = max(context["wall_width"], 80.0) * 0.5
    axis = context["axis"]
    normal = context["normal"]
    return (
        center.add(FreeCAD.Vector(axis).multiply(-half_width)).add(
            FreeCAD.Vector(normal).multiply(-half_depth)
        ),
        center.add(FreeCAD.Vector(axis).multiply(half_width)).add(
            FreeCAD.Vector(normal).multiply(-half_depth)
        ),
        center.add(FreeCAD.Vector(axis).multiply(half_width)).add(
            FreeCAD.Vector(normal).multiply(half_depth)
        ),
        center.add(FreeCAD.Vector(axis).multiply(-half_width)).add(
            FreeCAD.Vector(normal).multiply(half_depth)
        ),
    )


def update_window_tool_preview(session, point=None, info=None):
    wall = resolve_window_host_wall(session, snap_object=info, snap_info=info)
    if wall is not None:
        session._window_host_wall = wall
    points = _get_window_preview_points(session, point, wall=wall)
    clear_window_preview(session)
    if len(points) != 4:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return
    color = (0.12, 0.38, 0.95)
    width = session._scaled_line_width(2)
    for index, (start, end) in enumerate(zip(points, points[1:] + points[:1])):
        tracker = session._make_plan_line_tracker(
            DraftTrackers,
            "window-placement-preview:{}".format(index),
            scolor=color,
            swidth=width,
            ontop=True,
        )
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()
        session._window_preview_trackers.append(tracker)


def _add_rectangle(sketch, x_min, y_min, x_max, y_max):
    import Part
    import Sketcher

    start_index = sketch.GeometryCount
    sketch.addGeometry(
        Part.LineSegment(FreeCAD.Vector(x_min, y_min, 0), FreeCAD.Vector(x_max, y_min, 0))
    )
    sketch.addGeometry(
        Part.LineSegment(FreeCAD.Vector(x_max, y_min, 0), FreeCAD.Vector(x_max, y_max, 0))
    )
    sketch.addGeometry(
        Part.LineSegment(FreeCAD.Vector(x_max, y_max, 0), FreeCAD.Vector(x_min, y_max, 0))
    )
    sketch.addGeometry(
        Part.LineSegment(FreeCAD.Vector(x_min, y_max, 0), FreeCAD.Vector(x_min, y_min, 0))
    )
    sketch.addConstraint(Sketcher.Constraint("Coincident", start_index, 2, start_index + 1, 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", start_index + 1, 2, start_index + 2, 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", start_index + 2, 2, start_index + 3, 1))
    sketch.addConstraint(Sketcher.Constraint("Coincident", start_index + 3, 2, start_index, 1))


def _make_window_base_sketch(session, wall, center):
    context = _get_wall_axis_context(wall)
    if not context:
        return None

    sketch = session.doc.addObject("Sketcher::SketchObject", "PlanWindowSketch")
    axis = context["axis"]
    vertical = context["vertical"]
    normal = context["normal"]
    rotation = FreeCAD.Rotation(axis, vertical, normal, "XYZ")
    placement_base = FreeCAD.Vector(center).add(
        FreeCAD.Vector(vertical).multiply(DEFAULT_WINDOW_SILL_HEIGHT)
    )
    sketch.Placement = FreeCAD.Placement(placement_base, rotation)

    half_width = DEFAULT_WINDOW_WIDTH * 0.5
    y_min = 0.0
    y_max = DEFAULT_WINDOW_HEIGHT
    inset = DEFAULT_WINDOW_FRAME_THICKNESS
    _add_rectangle(sketch, -half_width, y_min, half_width, y_max)
    if DEFAULT_WINDOW_WIDTH > inset * 2.0 and DEFAULT_WINDOW_HEIGHT > inset * 2.0:
        _add_rectangle(
            sketch,
            -half_width + inset,
            y_min + inset,
            half_width - inset,
            y_max - inset,
        )
    return sketch


def create_window(session, wall, point):
    import Arch

    center = project_window_point_to_host(session, point, wall)
    if center is None:
        return None

    window = None
    defer_updates = getattr(session, "defer_document_visual_updates", None)
    update_scope = defer_updates() if defer_updates else nullcontext()
    with update_scope:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Create Window"))
        try:
            sketch = _make_window_base_sketch(session, wall, center)
            if sketch is None:
                raise RuntimeError("Unable to create window sketch")
            session.doc.recompute()
            window = Arch.makeWindow(
                baseobj=sketch,
                width=DEFAULT_WINDOW_WIDTH,
                height=DEFAULT_WINDOW_HEIGHT,
                name="Window",
            )
            window.IfcType = "Window"
            window.Width = DEFAULT_WINDOW_WIDTH
            window.Height = DEFAULT_WINDOW_HEIGHT
            window.HoleDepth = 0
            window.WindowParts = [
                "Frame",
                "Frame",
                "Wire0,Wire1",
                str(DEFAULT_WINDOW_FRAME_THICKNESS),
                "0",
                "Glass",
                "Glass panel",
                "Wire1",
                str(DEFAULT_WINDOW_GLASS_THICKNESS),
                str(DEFAULT_WINDOW_FRAME_THICKNESS * 0.5),
            ]
            # Build the opening before it is hosted. Window shape changes touch
            # hosts, so doing this while unhosted avoids a second wall/window
            # recompute pass after Arch.addComponents().
            session.doc.recompute()
            Arch.addComponents(window, wall)
            session._add_object_to_active_storey(window)
            session.doc.recompute()
            if not session._is_hosted_opening_object(window):
                raise RuntimeError("Created window is not hosted")
            session.doc.commitTransaction()
        except Exception:
            try:
                session.doc.abortTransaction()
            except Exception:
                pass
            raise
    return window


def handle_window_tool_point(session, point=None, obj=None):
    if point is None:
        cancel_window_tool(session)
        return
    wall = resolve_window_host_wall(session, snap_object=obj)
    if not session._is_plan_selectable_wall(wall):
        cancel_window_tool(session)
        FreeCAD.Console.PrintWarning(
            translate("BIM_PlanEdit", "Select or hover a wall before placing a window.\n")
        )
        return
    try:
        window = create_window(session, wall, point)
    except Exception:
        cancel_window_tool(session)
        FreeCAD.Console.PrintError(translate("BIM_PlanEdit", "Failed to create the window.\n"))
        return
    session._invalidate_wall_hosted_openings_cache()
    session._register_plan_object(window)
    cancel_window_tool(session, refresh=False)
    session._restore_selected_opening(window)
    session._refresh_task_panel_status()
