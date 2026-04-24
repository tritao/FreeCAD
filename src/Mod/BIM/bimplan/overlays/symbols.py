# SPDX-License-Identifier: LGPL-2.1-or-later

"""Symbol overlay and handle tracker helpers for BIM Plan Edit."""

import math

import FreeCAD
import FreeCADGui
from .. import selection as plan_selection


def get_symbol_global_placement(session, symbol, placement=None):
    current_global = session._get_plan_object_global_placement(symbol)
    if placement is None:
        return current_global
    current_local = getattr(symbol, "Placement", None)
    if current_local is None:
        return placement
    try:
        parent_global = current_global.multiply(current_local.inverse())
        return parent_global.multiply(placement)
    except Exception:
        return placement


def get_symbol_parent_global_placement(session, symbol, placement=None):
    placement = placement or getattr(symbol, "Placement", None)
    current_global = session._get_plan_object_global_placement(symbol)
    if placement is None:
        return current_global
    try:
        return current_global.multiply(placement.inverse())
    except Exception:
        return FreeCAD.Placement()


def get_symbol_plan_proxy(session, symbol, *attrs):
    semantic_obj = session._get_plan_semantic_object(symbol)
    view_object = getattr(semantic_obj, "ViewObject", None)
    proxy = getattr(view_object, "Proxy", None) if view_object else None
    if not proxy:
        return None
    for attr in attrs:
        if not hasattr(proxy, attr):
            return None
    return proxy


def get_symbol_semantic_proxy(session, symbol, *attrs):
    semantic_obj = session._get_plan_semantic_object(symbol)
    proxy = getattr(semantic_obj, "Proxy", None)
    if not proxy:
        return None
    for attr in attrs:
        if not hasattr(proxy, attr):
            return None
    return proxy


def get_symbol_overlay_polylines(session, symbol, placement=None):
    if not session._is_plan_symbol_instance(symbol):
        return []
    proxy = session._get_symbol_plan_proxy(symbol, "_collect_local_footprint_polylines")
    if not proxy:
        return []
    try:
        local_polylines = list(proxy._collect_local_footprint_polylines() or [])
    except Exception:
        return []

    placement = session._get_symbol_global_placement(symbol, placement=placement)
    polylines = []
    for polyline in local_polylines:
        points = []
        for point in polyline:
            if isinstance(point, FreeCAD.Vector):
                local_point = FreeCAD.Vector(point)
            else:
                try:
                    z_value = point[2] if len(point) > 2 else 0.0
                    local_point = FreeCAD.Vector(point[0], point[1], z_value)
                except Exception:
                    continue
            try:
                points.append(placement.multVec(local_point))
            except Exception:
                continue
        if len(points) >= 2:
            polylines.append(points)
    return polylines


def get_symbol_overlay_segments(session, symbol, placement=None):
    segments = []
    for polyline in session._get_symbol_overlay_polylines(symbol, placement=placement):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            segments.append((start, end))
    return segments


def get_plan_symbol_instances(session):
    if not session.doc:
        return ()
    doc_name = getattr(session.doc, "Name", None)
    cache_record = session.overlay_cache_state.plan_symbol_instances_cache
    if cache_record is not None and cache_record[0] == doc_name:
        session._plan_perf_count("plan_symbol_instances_cache_hits")
        return cache_record[1]

    symbols = []
    with session._plan_perf_trace_span("build_plan_symbol_instances_cache"):
        for obj in getattr(session.doc, "Objects", []) or []:
            session._plan_perf_count("plan_symbol_instance_objects_scanned")
            if session._is_plan_symbol_instance(obj):
                symbols.append(obj)
    result = tuple(symbols)
    session.overlay_cache_state.plan_symbol_instances_cache = (doc_name, result)
    return result


def _get_symbol_screen_geometry_key(session, symbol):
    placement = session._get_plan_object_global_placement(symbol)
    try:
        base = placement.Base
        rotation = tuple(float(value) for value in placement.Rotation.Q)
        return (
            round(float(base.x), 6),
            round(float(base.y), 6),
            round(float(base.z), 6),
            tuple(round(value, 9) for value in rotation),
        )
    except Exception:
        return None


def get_symbol_overlay_screen_polylines(session, symbol):
    if not session._is_plan_symbol_instance(symbol) or not session.view:
        return ()
    projection_key = session.viewport.get_plan_projection_cache_key()
    if projection_key is None:
        return ()
    symbol_key = session._get_document_object_key(symbol)
    if symbol_key is None:
        return ()
    geometry_key = _get_symbol_screen_geometry_key(session, symbol)
    cache_key = (projection_key, geometry_key)
    cached = session.overlay_cache_state.symbol_overlay_screen_cache.get(symbol_key)
    if cached is not None and cached[0] == cache_key:
        session._plan_perf_count("symbol_overlay_screen_polylines_cache_hits")
        return cached[1]

    projected_polylines = []
    for polyline in session._get_symbol_overlay_polylines(symbol):
        if len(polyline) < 2:
            continue
        projected = []
        try:
            for poly_point in polyline:
                screen_point = session.view.getPointOnScreen(poly_point)
                projected.append((float(screen_point[0]), float(screen_point[1])))
        except Exception:
            projected = []
        if len(projected) >= 2:
            projected_polylines.append(tuple(projected))
    result = tuple(projected_polylines)
    session.overlay_cache_state.symbol_overlay_screen_cache[symbol_key] = (cache_key, result)
    return result


def refresh_selected_symbol_visuals(session):
    session._sync_selected_symbol_overlay()
    session.overlays.sync_selected_symbol_handles()
    session.viewport.request_view_redraw()


def create_symbol_overlay_trackers(session, symbol, color, width, tracker_store, placement=None):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for polyline in session._get_symbol_overlay_polylines(symbol, placement=placement):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = session.overlays.make_plan_line_tracker(
                DraftTrackers,
                "symbol-overlay:{}".format(getattr(symbol, "Name", "unknown")),
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            tracker_store.append(tracker)


def sync_hovered_symbol_overlay(session):
    with session._plan_perf_trace_span("sync_hovered_symbol_overlay"):
        session._clear_hovered_symbol_overlay()
        if session.current_tool != "Select":
            return
        if not session._is_plan_symbol_instance(session.hovered_symbol):
            return
        if session._is_selected_plan_target("symbol", session.hovered_symbol):
            return
        session._create_symbol_overlay_trackers(
            session.hovered_symbol,
            color=(0.38, 0.62, 0.96),
            width=session.viewport.scaled_line_width(2),
            tracker_store=session._symbol_hover_trackers,
        )


def clear_hovered_symbol_overlay(session):
    session.overlays.finalize_trackers(session._symbol_hover_trackers)
    session._symbol_hover_trackers = []


def sync_selected_symbol_overlay(session):
    with session._plan_perf_trace_span("sync_selected_symbol_overlay"):
        symbol = plan_selection.get_selected_plan_target_object(session, "symbol")
        if session.current_tool != "Select" or not session._is_plan_symbol_instance(symbol):
            session._clear_selected_symbol_overlay()
            return
        width = session.viewport.scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            session._clear_selected_symbol_overlay()
            return
        segments = session._get_symbol_overlay_segments(symbol)
        session._plan_perf_count("selected_symbol_overlay_segments", len(segments))
        color = (0.12, 0.38, 0.95)
        transferred_trackers = False
        if len(session._symbol_overlay_trackers) != len(segments):
            if (
                not session._symbol_overlay_trackers
                and session.hovered_symbol == symbol
                and len(session._symbol_hover_trackers) == len(segments)
            ):
                session._symbol_overlay_trackers = session._symbol_hover_trackers
                session._symbol_hover_trackers = []
                transferred_trackers = True
                session._plan_perf_count("selected_symbol_overlay_tracker_transfers")
            else:
                session._clear_selected_symbol_overlay()
                for _start, _end in segments:
                    tracker = session.overlays.make_plan_line_tracker(
                        DraftTrackers,
                        "selected-symbol-overlay:{}".format(getattr(symbol, "Name", "unknown")),
                        scolor=color,
                        swidth=width,
                        ontop=True,
                    )
                    session._symbol_overlay_trackers.append(tracker)
        for tracker, (start, end) in zip(session._symbol_overlay_trackers, segments):
            session.overlays.set_plan_line_tracker_width(tracker, width)
            tracker.setColor(color)
            if not transferred_trackers:
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()


def clear_selected_symbol_overlay(session):
    session.overlays.finalize_trackers(session._symbol_overlay_trackers)
    session._symbol_overlay_trackers = []


def get_symbol_local_anchor(session, symbol):
    semantic_obj = session._get_plan_semantic_object(symbol)
    proxy = session._get_symbol_semantic_proxy(symbol, "get_plan_anchor")
    if proxy:
        try:
            return FreeCAD.Vector(proxy.get_plan_anchor(semantic_obj))
        except Exception:
            pass
    try:
        import ArchEquipment

        return ArchEquipment.get_plan_anchor(semantic_obj)
    except Exception:
        return FreeCAD.Vector()


def get_symbol_local_facing(session, symbol):
    semantic_obj = session._get_plan_semantic_object(symbol)
    proxy = session._get_symbol_semantic_proxy(symbol, "get_plan_facing")
    if proxy:
        try:
            facing = FreeCAD.Vector(proxy.get_plan_facing(semantic_obj))
        except Exception:
            facing = None
    else:
        facing = None
    if facing is None:
        try:
            import ArchEquipment

            facing = ArchEquipment.get_plan_facing(semantic_obj)
        except Exception:
            facing = FreeCAD.Vector(1, 0, 0)
    facing = FreeCAD.Vector(facing.x, facing.y, 0)
    if facing.Length < 0.001:
        return FreeCAD.Vector(1, 0, 0)
    facing.normalize()
    return facing


def get_symbol_anchor_point(session, symbol, placement=None):
    placement = session._get_symbol_global_placement(symbol, placement=placement)
    anchor = session._get_symbol_local_anchor(symbol)
    try:
        return placement.multVec(anchor)
    except Exception:
        base = getattr(placement, "Base", None)
        if base is None:
            return FreeCAD.Vector()
        return FreeCAD.Vector(base.x, base.y, base.z)


def get_symbol_facing_vector(session, symbol, placement=None):
    placement = session._get_symbol_global_placement(symbol, placement=placement)
    facing = session._get_symbol_local_facing(symbol)
    try:
        facing = placement.Rotation.multVec(facing)
    except Exception:
        pass
    facing = FreeCAD.Vector(facing.x, facing.y, 0)
    if facing.Length < 0.001:
        return FreeCAD.Vector()
    facing.normalize()
    return facing


def symbol_rotation_snap_enabled(session):
    params = getattr(session, "_plan_edit_params", None)
    if not params:
        return True
    try:
        return params.GetBool("SymbolRotateAngleSnap", True)
    except Exception:
        return True


def get_symbol_rotation_snap_increment_degrees(session):
    params = getattr(session, "_plan_edit_params", None)
    if not params:
        return 15.0
    try:
        increment = float(params.GetFloat("SymbolRotateAngleIncrement", 15.0))
    except Exception:
        increment = 15.0
    if increment <= 0.001:
        return 15.0
    return min(increment, 180.0)


def get_symbol_rotation_snap_step_radians(session):
    return math.radians(session.overlays.get_symbol_rotation_snap_increment_degrees())


def format_symbol_rotation_snap_label(session):
    increment = session.overlays.get_symbol_rotation_snap_increment_degrees()
    rounded = round(increment)
    if abs(increment - rounded) < 1e-9:
        return "{}°".format(int(rounded))
    return "{}°".format(("{:.3f}".format(increment)).rstrip("0").rstrip("."))


def symbol_rotation_free_angle_override_active(session):
    try:
        from PySide import QtCore, QtGui

        modifiers = QtGui.QApplication.keyboardModifiers()
        return bool(modifiers & QtCore.Qt.ShiftModifier)
    except Exception:
        return False


def resolve_symbol_handle_target_point(session, symbol, handle_role, point, placement=None):
    if point is None:
        return None
    if isinstance(point, FreeCAD.Vector):
        target_point = FreeCAD.Vector(point.x, point.y, point.z)
    else:
        try:
            z_value = point[2] if len(point) > 2 else 0.0
            target_point = FreeCAD.Vector(point[0], point[1], z_value)
        except Exception:
            return None
    if handle_role != "rotate":
        return target_point
    if not session._symbol_rotation_snap_enabled():
        return target_point
    if session.overlays.symbol_rotation_free_angle_override_active():
        return target_point

    snap_step = session.overlays.get_symbol_rotation_snap_step_radians()
    if snap_step <= 1e-9:
        return target_point

    anchor = session._get_symbol_anchor_point(symbol, placement=placement)
    vector = FreeCAD.Vector(target_point.x - anchor.x, target_point.y - anchor.y, 0)
    radius = math.hypot(vector.x, vector.y)
    if radius < 0.001:
        return target_point

    snapped_angle = round(math.atan2(vector.y, vector.x) / snap_step) * snap_step
    return FreeCAD.Vector(
        anchor.x + radius * math.cos(snapped_angle),
        anchor.y + radius * math.sin(snapped_angle),
        anchor.z,
    )


def get_symbol_handle_radius(session, symbol, placement=None):
    placement = placement or session._get_plan_object_global_placement(symbol)
    anchor = session._get_symbol_anchor_point(symbol, placement=placement)
    radius = 0.0
    for polyline in session._get_symbol_overlay_polylines(symbol, placement=placement):
        for point in polyline:
            radius = max(
                radius,
                math.hypot(float(point.x) - float(anchor.x), float(point.y) - float(anchor.y)),
            )
    units_per_pixel = session.viewport.get_plan_view_units_per_pixel() or 10.0
    return max(radius * 1.2, 28.0 * units_per_pixel, 300.0)


def get_selected_symbol_handle_specs(session, symbol):
    from draftutils import params

    if not session._is_plan_symbol_instance(symbol):
        return []

    placement = session._get_plan_object_global_placement(symbol)
    anchor = session._get_symbol_anchor_point(symbol, placement=placement)
    radius = session.overlays.get_symbol_handle_radius(symbol, placement=placement)
    rotate_direction = session._get_symbol_facing_vector(symbol, placement=placement)
    if rotate_direction.Length < 0.001:
        rotate_direction = FreeCAD.Vector(1, 0, 0)
    rotate_offset = rotate_direction.multiply(radius)
    marker_size = session.viewport.scaled_marker_size(params.get_param_view("MarkerSize"))
    return [
        (
            "move",
            anchor,
            FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size),
        ),
        (
            "rotate",
            anchor.add(rotate_offset),
            FreeCADGui.getMarkerIndex("CIRCLE_FILLED", marker_size),
        ),
    ]


def sync_selected_symbol_handles(session):
    with session._plan_perf_trace_span("sync_selected_symbol_handles"):
        symbol = plan_selection.get_selected_plan_target_object(session, "symbol")
        if session.current_tool != "Select":
            session.overlays.clear_selected_symbol_handles()
            return
        if not session._is_plan_symbol_instance(symbol):
            session.overlays.clear_selected_symbol_handles()
            return
        session.overlays.clear_selected_symbol_handles()
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return
        specs = session.overlays.get_selected_symbol_handle_specs(symbol)
        session._plan_perf_count("selected_symbol_handles", len(specs))
        for idx, (_role, point, marker) in enumerate(specs):
            tracker = DraftTrackers.editTracker(
                pos=point,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            session._symbol_handle_trackers.append(tracker)


def clear_selected_symbol_handles(session):
    session.overlays.finalize_trackers(session._symbol_handle_trackers)
    session._symbol_handle_trackers = []


def pick_selected_symbol_handle(session, mouse_pos, radius_px=10):
    symbol = plan_selection.get_selected_plan_target_object(session, "symbol")
    if not session._is_plan_symbol_instance(symbol) or not session.view:
        return None
    try:
        cursor_x = int(mouse_pos[0])
        cursor_y = int(mouse_pos[1])
    except Exception:
        return None
    best_role = None
    best_distance_sq = None
    for role, point, _marker in session.overlays.get_selected_symbol_handle_specs(symbol):
        try:
            screen_x, screen_y = session.view.getPointOnScreen(point)
        except Exception:
            continue
        dx = float(screen_x) - float(cursor_x)
        dy = float(screen_y) - float(cursor_y)
        distance_sq = dx * dx + dy * dy
        if distance_sq > radius_px * radius_px:
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_role = role
            best_distance_sq = distance_sq
    return best_role


def sync_symbol_edit_preview(session, symbol, placement, guide_start=None, guide_end=None):
    session._clear_symbol_edit_preview()
    if session.current_tool not in ("Move Symbol", "Rotate Symbol"):
        return
    if not session._is_plan_symbol_instance(symbol) or placement is None:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    preview_color = (0.12, 0.38, 0.95)
    session._create_symbol_overlay_trackers(
        symbol,
        color=preview_color,
        width=session.viewport.scaled_line_width(3),
        tracker_store=session._symbol_edit_preview_trackers,
        placement=placement,
    )
    if guide_start is None or guide_end is None:
        return
    guide = session.overlays.make_plan_line_tracker(
        DraftTrackers,
        "symbol-edit-guide:{}".format(getattr(symbol, "Name", "unknown")),
        dotted=True,
        scolor=preview_color,
        swidth=session.viewport.scaled_line_width(1),
        ontop=True,
    )
    guide.p1(guide_start)
    guide.p2(guide_end)
    guide.on()
    session._symbol_edit_preview_trackers.append(guide)


def clear_symbol_edit_preview(session):
    session.overlays.finalize_trackers(session._symbol_edit_preview_trackers)
    session._symbol_edit_preview_trackers = []
