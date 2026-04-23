# SPDX-License-Identifier: LGPL-2.1-or-later

"""Hosted window creation and editing helpers for BIM Plan Edit."""

import ArchWindow
import FreeCAD
import FreeCADGui
from bimplan import hosted_openings as plan_hosted_openings
from bimplan import selection as plan_selection

translate = FreeCAD.Qt.translate

DEFAULT_WINDOW_WIDTH = 900.0
DEFAULT_WINDOW_HEIGHT = 1200.0
DEFAULT_WINDOW_SILL_HEIGHT = 900.0
DEFAULT_WINDOW_FRAME_THICKNESS = 60.0
DEFAULT_WINDOW_GLASS_THICKNESS = 10.0


def get_window_style_preset_options():
    return ArchWindow.getWindowPresetNames("window")


def can_edit_window_style_preset(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canApplyWindowPreset(window))


def can_edit_window_width(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canEditWindowWidth(window))


def can_edit_window_height(window):
    return bool(ArchWindow.isWindowObject(window) and ArchWindow.canEditWindowHeight(window))


def can_edit_window(window):
    return bool(
        can_edit_window_style_preset(window)
        or can_edit_window_width(window)
        or can_edit_window_height(window)
    )


def get_window_width_mm(window):
    return ArchWindow.getWindowWidthMm(window)


def get_window_width_user_string(window):
    return ArchWindow.getWindowWidthUserString(window)


def get_window_height_mm(window):
    return ArchWindow.getWindowHeightMm(window)


def get_window_height_user_string(window):
    return ArchWindow.getWindowHeightUserString(window)


def get_selected_window_style_preset(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    if not ArchWindow.isWindowObject(window):
        return ""
    preset_name = ArchWindow.getWindowPresetName(window)
    if preset_name in get_window_style_preset_options():
        return preset_name
    return ""


def can_apply_selected_window_style_preset(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return can_edit_window_style_preset(window)


def get_selected_window_width_mm(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_width_mm(window)


def get_selected_window_width_text(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_width_user_string(window)


def get_selected_window_height_mm(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_height_mm(window)


def get_selected_window_height_text(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return get_window_height_user_string(window)


def can_apply_selected_window_width(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return can_edit_window_width(window)


def can_apply_selected_window_height(session):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    return can_edit_window_height(window)


def can_apply_selected_window_size(session, width_value=None, height_value=None):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    resize_targets = _resolve_window_resize_targets(
        window,
        width_value=width_value,
        height_value=height_value,
    )
    if resize_targets is None:
        return False

    target_width, target_height = resize_targets
    status = ArchWindow.validateWindowResize(
        window,
        width=target_width,
        height=target_height,
    )
    return bool(status.allowed and not status.noop)


def apply_selected_window_style_preset(session, preset_name):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    if not can_edit_window_style_preset(window):
        return False

    preset_name = str(preset_name or "").strip()
    if preset_name not in get_window_style_preset_options():
        return False

    if not ArchWindow.applyWindowPreset(
        window,
        preset_name,
        transaction_label=translate("BIM_PlanEdit", "Change Window Style"),
    ):
        return False

    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)
    session._refresh_task_panel_status()
    return True


def set_selected_window_width(session, value):
    return _set_selected_window_size(
        session,
        width_value=value,
        transaction_label=translate("BIM_PlanEdit", "Change Window Width"),
    )


def set_selected_window_height(session, value):
    return _set_selected_window_size(
        session,
        height_value=value,
        transaction_label=translate("BIM_PlanEdit", "Change Window Height"),
    )


def set_selected_window_size(session, width_value=None, height_value=None):
    return _set_selected_window_size(
        session,
        width_value=width_value,
        height_value=height_value,
        transaction_label=translate("BIM_PlanEdit", "Change Window Size"),
    )


def can_place_window(session):
    return get_window_host_wall(session) is not None


def get_window_host_wall(session):
    wall = plan_selection.get_selected_plan_target_object(session, "wall")
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
    session.viewport.queue_focus_plan_view()
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
    sketch.addConstraint(Sketcher.Constraint("Horizontal", start_index))
    sketch.addConstraint(Sketcher.Constraint("Vertical", start_index + 1))
    sketch.addConstraint(Sketcher.Constraint("Horizontal", start_index + 2))
    sketch.addConstraint(Sketcher.Constraint("Vertical", start_index + 3))
    return start_index


def _add_outer_rectangle_size_constraints(sketch, start_index, width, height):
    import Sketcher

    sketch.addConstraint(Sketcher.Constraint("DistanceX", start_index, 1, start_index, 2, width))
    sketch.renameConstraint(sketch.ConstraintCount - 1, "Width")
    sketch.addConstraint(
        Sketcher.Constraint("DistanceY", start_index + 1, 1, start_index + 1, 2, height)
    )
    sketch.renameConstraint(sketch.ConstraintCount - 1, "Height")


def _link_inner_rectangle_to_outer_rectangle(sketch, outer_start, inner_start, inset):
    import Sketcher

    sketch.addConstraint(
        Sketcher.Constraint("DistanceX", outer_start + 3, 2, inner_start + 3, 2, inset)
    )
    sketch.addConstraint(
        Sketcher.Constraint("DistanceX", inner_start + 1, 1, outer_start + 1, 1, inset)
    )
    sketch.addConstraint(Sketcher.Constraint("DistanceY", outer_start, 1, inner_start, 1, inset))
    sketch.addConstraint(
        Sketcher.Constraint("DistanceY", inner_start + 2, 2, outer_start + 2, 2, inset)
    )


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
    outer_start = _add_rectangle(sketch, -half_width, y_min, half_width, y_max)
    _add_outer_rectangle_size_constraints(sketch, outer_start, DEFAULT_WINDOW_WIDTH, y_max - y_min)
    if DEFAULT_WINDOW_WIDTH > inset * 2.0 and DEFAULT_WINDOW_HEIGHT > inset * 2.0:
        inner_start = _add_rectangle(
            sketch,
            -half_width + inset,
            y_min + inset,
            half_width - inset,
            y_max - inset,
        )
        _link_inner_rectangle_to_outer_rectangle(sketch, outer_start, inner_start, inset)
    return sketch


def create_window(session, wall, point):
    import Arch

    center = project_window_point_to_host(session, point, wall)
    if center is None:
        return None

    def build_window():
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
        return window

    window = plan_hosted_openings.create_hosted_opening(
        session,
        wall,
        build_window,
        translate("BIM_PlanEdit", "Create Window"),
    )
    if not session._is_hosted_opening_object(window):
        raise RuntimeError("Created window is not hosted")
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


def _set_selected_window_size(
    session,
    width_value=None,
    height_value=None,
    transaction_label=None,
):
    window = plan_selection.get_selected_plan_target_object(session, "opening")
    resize_targets = _resolve_window_resize_targets(
        window,
        width_value=width_value,
        height_value=height_value,
    )
    if resize_targets is None:
        return False

    target_width, target_height = resize_targets
    if not ArchWindow.resizeWindow(
        window,
        width=target_width,
        height=target_height,
        preserve_anchor=True,
        transaction_label=transaction_label,
    ):
        return False

    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)
    session._refresh_task_panel_status()
    return True


def _resolve_window_resize_targets(window, width_value=None, height_value=None):
    if not ArchWindow.isWindowObject(window):
        return None

    target_width = None
    if can_edit_window_width(window) and width_value is not None:
        target_width = _parse_length_mm(width_value)
        current_width = get_window_width_mm(window)
        if target_width is None or target_width <= 0.0:
            return None
        if current_width is not None and abs(target_width - current_width) <= 1e-6:
            target_width = None

    target_height = None
    if can_edit_window_height(window) and height_value is not None:
        target_height = _parse_length_mm(height_value)
        current_height = get_window_height_mm(window)
        if target_height is None or target_height <= 0.0:
            return None
        if current_height is not None and abs(target_height - current_height) <= 1e-6:
            target_height = None

    if target_width is None and target_height is None:
        return None
    return target_width, target_height


def _parse_length_mm(value):
    if value is None:
        return None

    length = _coerce_length_mm(value)
    if length is not None:
        return length

    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(FreeCAD.Units.Quantity(text).Value)
    except Exception:
        return None


def _coerce_length_mm(value):
    try:
        value = value.Value
    except AttributeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
