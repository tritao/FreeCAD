# SPDX-License-Identifier: LGPL-2.1-or-later

"""Symbol overlay and handle tracker helpers for BIM Plan Edit."""

import math

import FreeCAD
import FreeCADGui
from bimplan import document_visuals as plan_document_visuals
from . import manager as overlay_manager


def _overlay_runtime_api(session):
    overlays = getattr(session, "overlays", None)
    return getattr(overlays, "runtime", overlays)


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _symbol_tracker_state(session):
    return session.overlay_tracker_state


def _symbol_preview_state(session):
    return session.opening_transient_state


class PlanSymbolOverlayService:
    """Owned session surface for symbol overlay behavior."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def clear_symbol_edit_preview(self, *args, **kwargs):
        return clear_symbol_edit_preview(self.session, *args, **kwargs)

    def get_plan_symbol_instances(self, *args, **kwargs):
        return get_plan_symbol_instances(self.session, *args, **kwargs)

    def get_symbol_global_placement(self, *args, **kwargs):
        return get_symbol_global_placement(self.session, *args, **kwargs)

    def get_symbol_parent_global_placement(self, *args, **kwargs):
        return get_symbol_parent_global_placement(self.session, *args, **kwargs)

    def get_symbol_plan_proxy(self, *args, **kwargs):
        return get_symbol_plan_proxy(self.session, *args, **kwargs)

    def get_symbol_semantic_proxy(self, *args, **kwargs):
        return get_symbol_semantic_proxy(self.session, *args, **kwargs)

    def get_symbol_overlay_polylines(self, *args, **kwargs):
        return get_symbol_overlay_polylines(self.session, *args, **kwargs)

    def get_symbol_overlay_segments(self, *args, **kwargs):
        return get_symbol_overlay_segments(self.session, *args, **kwargs)

    def get_symbol_overlay_screen_polylines(self, *args, **kwargs):
        return get_symbol_overlay_screen_polylines(self.session, *args, **kwargs)

    def get_symbol_overlay_screen_bounds(self, *args, **kwargs):
        return get_symbol_overlay_screen_bounds(self.session, *args, **kwargs)

    def refresh_selected_symbol_visuals(self, *args, **kwargs):
        return refresh_selected_symbol_visuals(self.session, *args, **kwargs)

    def create_symbol_overlay_trackers(self, *args, **kwargs):
        return create_symbol_overlay_trackers(self.session, *args, **kwargs)

    def sync_hovered_symbol_overlay(self, *args, **kwargs):
        return sync_hovered_symbol_overlay(self.session, *args, **kwargs)

    def clear_hovered_symbol_overlay(self, *args, **kwargs):
        return clear_hovered_symbol_overlay(self.session, *args, **kwargs)

    def sync_selected_symbol_overlay(self, *args, **kwargs):
        return sync_selected_symbol_overlay(self.session, *args, **kwargs)

    def clear_selected_symbol_overlay(self, *args, **kwargs):
        return clear_selected_symbol_overlay(self.session, *args, **kwargs)

    def get_symbol_rotation_snap_increment_degrees(self, *args, **kwargs):
        return get_symbol_rotation_snap_increment_degrees(self.session, *args, **kwargs)

    def get_symbol_rotation_snap_step_radians(self, *args, **kwargs):
        return get_symbol_rotation_snap_step_radians(self.session, *args, **kwargs)

    def symbol_rotation_free_angle_override_active(self, *args, **kwargs):
        return symbol_rotation_free_angle_override_active(self.session, *args, **kwargs)

    def resolve_symbol_handle_target_point(self, *args, **kwargs):
        return resolve_symbol_handle_target_point(self.session, *args, **kwargs)

    def get_symbol_handle_radius(self, *args, **kwargs):
        return get_symbol_handle_radius(self.session, *args, **kwargs)

    def get_selected_symbol_handle_specs(self, *args, **kwargs):
        return get_selected_symbol_handle_specs(self.session, *args, **kwargs)

    def get_symbol_anchor_point(self, *args, **kwargs):
        return get_symbol_anchor_point(self.session, *args, **kwargs)

    def get_symbol_facing_vector(self, *args, **kwargs):
        return get_symbol_facing_vector(self.session, *args, **kwargs)

    def sync_selected_symbol_handles(self, *args, **kwargs):
        return sync_selected_symbol_handles(self.session, *args, **kwargs)

    def clear_selected_symbol_handles(self, *args, **kwargs):
        return clear_selected_symbol_handles(self.session, *args, **kwargs)

    def sync_symbol_edit_preview(self, *args, **kwargs):
        return sync_symbol_edit_preview(self.session, *args, **kwargs)

    def pick_selected_symbol_handle(self, *args, **kwargs):
        return pick_selected_symbol_handle(self.session, *args, **kwargs)

    def get_symbol_local_anchor(self, *args, **kwargs):
        return get_symbol_local_anchor(self.session, *args, **kwargs)

    def get_symbol_local_facing(self, *args, **kwargs):
        return get_symbol_local_facing(self.session, *args, **kwargs)

    def is_symbol_visual_dependency(self, symbol, obj):
        return is_symbol_visual_dependency(self.session, symbol, obj)

    def refresh_target_document_visual_dependency(self, symbol, obj, prop):
        return refresh_target_document_visual_dependency(self.session, symbol, obj, prop)

    def refresh_symbol_visual_footprint(self, symbol):
        return refresh_symbol_visual_footprint(self.session, symbol)

    def handle_document_visual_dependency_change(self, obj, prop):
        return handle_document_visual_dependency_change(self.session, obj, prop)

    def handle_deleted_visual_target(self, obj):
        return handle_deleted_visual_target(self.session, obj)

    def refresh_document_dependent_visuals(self):
        return refresh_document_dependent_visuals(self.session)


def get_symbol_global_placement(session, symbol, placement=None):
    current_global = session.visibility.get_plan_object_global_placement(symbol)
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
    current_global = session.visibility.get_plan_object_global_placement(symbol)
    if placement is None:
        return current_global
    try:
        return current_global.multiply(placement.inverse())
    except Exception:
        return FreeCAD.Placement()


def get_symbol_plan_proxy(session, symbol, *attrs):
    semantic_obj = session.visibility.get_plan_semantic_object(symbol)
    view_object = getattr(semantic_obj, "ViewObject", None)
    proxy = getattr(view_object, "Proxy", None) if view_object else None
    if not proxy:
        return None
    for attr in attrs:
        if getattr(proxy, attr, None) is None:
            return None
    return proxy


def get_symbol_semantic_proxy(session, symbol, *attrs):
    semantic_obj = session.visibility.get_plan_semantic_object(symbol)
    proxy = getattr(semantic_obj, "Proxy", None)
    if not proxy:
        return None
    for attr in attrs:
        if getattr(proxy, attr, None) is None:
            return None
    return proxy


def get_symbol_overlay_polylines(session, symbol, placement=None):
    if not session.visibility.is_plan_symbol_instance(symbol):
        return []
    proxy = get_symbol_plan_proxy(session, symbol, "_collect_local_footprint_polylines")
    if not proxy:
        return []
    try:
        local_polylines = list(proxy._collect_local_footprint_polylines() or [])
    except Exception:
        return []

    placement = get_symbol_global_placement(session, symbol, placement=placement)
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
    for polyline in get_symbol_overlay_polylines(session, symbol, placement=placement):
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
        _perf_count(session, "plan_symbol_instances_cache_hits")
        return cache_record[1]

    symbols = []
    with _perf_trace_span(session, "build_plan_symbol_instances_cache"):
        for obj in getattr(session.doc, "Objects", []) or []:
            _perf_count(session, "plan_symbol_instance_objects_scanned")
            if session.visibility.is_plan_symbol_instance(obj):
                symbols.append(obj)
    result = tuple(symbols)
    session.overlay_cache_state.plan_symbol_instances_cache = (doc_name, result)
    return result


def _get_symbol_screen_geometry_key(session, symbol):
    placement = session.visibility.get_plan_object_global_placement(symbol)
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
    if not session.visibility.is_plan_symbol_instance(symbol) or not session.view:
        return ()
    projection_key = session.viewport.get_plan_projection_cache_key()
    if projection_key is None:
        return ()
    cache_state = session.overlay_cache_state
    if projection_key != cache_state.symbol_overlay_screen_cache_projection_key:
        cache_state.symbol_overlay_screen_cache = {}
        cache_state.symbol_overlay_screen_cache_projection_key = projection_key
    symbol_key = session.visibility.get_document_object_key(symbol)
    if symbol_key is None:
        return ()
    geometry_key = _get_symbol_screen_geometry_key(session, symbol)
    cache_key = (projection_key, geometry_key)
    cached = cache_state.symbol_overlay_screen_cache.get(symbol_key)
    if cached is not None and cached[0] == cache_key:
        _perf_count(session, "symbol_overlay_screen_polylines_cache_hits")
        return cached[1]

    projected_polylines = []
    for polyline in get_symbol_overlay_polylines(session, symbol):
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
    cache_state.symbol_overlay_screen_cache[symbol_key] = (
        cache_key,
        result,
        _get_screen_polyline_bounds(result),
    )
    return result


def _get_screen_polyline_bounds(projected_polylines):
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    for polyline in projected_polylines or ():
        for point in polyline or ():
            try:
                point_x = float(point[0])
                point_y = float(point[1])
            except Exception:
                continue
            min_x = point_x if min_x is None else min(min_x, point_x)
            min_y = point_y if min_y is None else min(min_y, point_y)
            max_x = point_x if max_x is None else max(max_x, point_x)
            max_y = point_y if max_y is None else max(max_y, point_y)
    if min_x is None:
        return None
    return (min_x, min_y, max_x, max_y)


def get_symbol_overlay_screen_bounds(session, symbol):
    if not session.visibility.is_plan_symbol_instance(symbol) or not session.view:
        return None
    projection_key = session.viewport.get_plan_projection_cache_key()
    if projection_key is None:
        return None
    cache_state = session.overlay_cache_state
    if projection_key != cache_state.symbol_overlay_screen_cache_projection_key:
        cache_state.symbol_overlay_screen_cache = {}
        cache_state.symbol_overlay_screen_cache_projection_key = projection_key
    symbol_key = session.visibility.get_document_object_key(symbol)
    if symbol_key is None:
        return None
    geometry_key = _get_symbol_screen_geometry_key(session, symbol)
    cache_key = (projection_key, geometry_key)
    cached = cache_state.symbol_overlay_screen_cache.get(symbol_key)
    if cached is None or cached[0] != cache_key:
        get_symbol_overlay_screen_polylines(session, symbol)
        cached = cache_state.symbol_overlay_screen_cache.get(symbol_key)
    if cached is None or cached[0] != cache_key:
        return None
    return cached[2]


def refresh_selected_symbol_visuals(session):
    sync_selected_symbol_overlay(session)
    sync_selected_symbol_handles(session)
    session.viewport.request_view_redraw()


def is_symbol_visual_dependency(session, symbol, obj):
    if not session.visibility.is_plan_symbol_instance(symbol) or not obj:
        return False
    if obj == symbol:
        return True
    semantic_obj = session.visibility.get_plan_semantic_object(symbol)
    if obj == semantic_obj:
        return True
    if obj == getattr(semantic_obj, "Base", None):
        return True
    return obj in (getattr(semantic_obj, "PlanSymbols", None) or [])


def refresh_target_document_visual_dependency(session, symbol, obj, prop):
    if not (
        is_symbol_visual_dependency(session, symbol, obj)
        and prop in plan_document_visuals.SYMBOL_VISUAL_PROPERTIES
    ):
        return False
    plan_document_visuals.refresh_plan_object_footprint_display(session, symbol)
    return True


def refresh_symbol_visual_footprint(session, symbol):
    if symbol is None:
        return False
    plan_document_visuals.refresh_plan_object_footprint_display(session, symbol)
    return True


def handle_document_visual_dependency_change(session, obj, prop):
    selected_symbol = session.selection.state.get_selected_plan_target_object("symbol")
    if refresh_target_document_visual_dependency(session, selected_symbol, obj, prop):
        _overlay_runtime_api(session).queue_plan_overlay_visual_refresh(
            plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL
        )
        return True
    hovered_symbol = session.hovered_symbol
    if (
        hovered_symbol
        and not session.selection.state.is_selected_plan_target("symbol", hovered_symbol)
        and refresh_target_document_visual_dependency(session, hovered_symbol, obj, prop)
    ):
        _overlay_runtime_api(session).queue_plan_overlay_visual_refresh(
            plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL
        )
        return True
    return False


def handle_deleted_visual_target(session, obj):
    if obj == session.hovered_symbol:
        session.hovered_symbol = None
        clear_hovered_symbol_overlay(session)
    if session.selection.refresh.clear_selected_plan_target_if_matches("symbol", obj):
        refresh_selected_symbol_visuals(session)
        return True
    return False


def refresh_document_dependent_visuals(session):
    visuals = []
    selected_symbol = session.selection.state.get_selected_plan_target_object("symbol")
    if refresh_symbol_visual_footprint(session, selected_symbol):
        visuals.append(plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL)
    hovered_symbol = session.hovered_symbol
    if (
        hovered_symbol
        and not session.selection.state.is_selected_plan_target("symbol", hovered_symbol)
        and refresh_symbol_visual_footprint(session, hovered_symbol)
    ):
        visuals.append(plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL)
    return tuple(visuals)


def create_symbol_overlay_trackers(session, symbol, color, width, tracker_store, placement=None):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for polyline in get_symbol_overlay_polylines(session, symbol, placement=placement):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = overlay_manager.make_plan_line_tracker(
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
    with _perf_trace_span(session, "sync_hovered_symbol_overlay"):
        tracker_state = _symbol_tracker_state(session)
        clear_hovered_symbol_overlay(session)
        if session.current_tool != "Select":
            return
        if not session.visibility.is_plan_symbol_instance(session.hovered_symbol):
            return
        if session.selection.state.is_selected_plan_target("symbol", session.hovered_symbol):
            return
        create_symbol_overlay_trackers(
            session,
            session.hovered_symbol,
            color=(0.38, 0.62, 0.96),
            width=session.viewport.scaled_line_width(2),
            tracker_store=tracker_state.symbol_hover_trackers,
        )


def clear_hovered_symbol_overlay(session):
    tracker_state = _symbol_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.symbol_hover_trackers)
    tracker_state.symbol_hover_trackers = []


def sync_selected_symbol_overlay(session):
    with _perf_trace_span(session, "sync_selected_symbol_overlay"):
        tracker_state = _symbol_tracker_state(session)
        symbol = session.selection.state.get_selected_plan_target_object("symbol")
        if session.current_tool != "Select" or not session.visibility.is_plan_symbol_instance(
            symbol
        ):
            clear_selected_symbol_overlay(session)
            return
        width = session.viewport.scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_symbol_overlay(session)
            return
        segments = get_symbol_overlay_segments(session, symbol)
        _perf_count(session, "selected_symbol_overlay_segments", len(segments))
        color = (0.12, 0.38, 0.95)
        transferred_trackers = False
        if len(tracker_state.symbol_overlay_trackers) != len(segments):
            if (
                not tracker_state.symbol_overlay_trackers
                and session.hovered_symbol == symbol
                and len(tracker_state.symbol_hover_trackers) == len(segments)
            ):
                tracker_state.symbol_overlay_trackers = tracker_state.symbol_hover_trackers
                tracker_state.symbol_hover_trackers = []
                transferred_trackers = True
                _perf_count(session, "selected_symbol_overlay_tracker_transfers")
            else:
                clear_selected_symbol_overlay(session)
                for _start, _end in segments:
                    tracker = overlay_manager.make_plan_line_tracker(
                        DraftTrackers,
                        "selected-symbol-overlay:{}".format(getattr(symbol, "Name", "unknown")),
                        scolor=color,
                        swidth=width,
                        ontop=True,
                    )
                    tracker_state.symbol_overlay_trackers.append(tracker)
        for tracker, (start, end) in zip(tracker_state.symbol_overlay_trackers, segments):
            overlay_manager.set_plan_line_tracker_width(tracker, width)
            tracker.setColor(color)
            if not transferred_trackers:
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()


def clear_selected_symbol_overlay(session):
    tracker_state = _symbol_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.symbol_overlay_trackers)
    tracker_state.symbol_overlay_trackers = []


def get_symbol_local_anchor(session, symbol):
    semantic_obj = session.visibility.get_plan_semantic_object(symbol)
    proxy = get_symbol_semantic_proxy(session, symbol, "get_plan_anchor")
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
    semantic_obj = session.visibility.get_plan_semantic_object(symbol)
    proxy = get_symbol_semantic_proxy(session, symbol, "get_plan_facing")
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
    placement = get_symbol_global_placement(session, symbol, placement=placement)
    anchor = get_symbol_local_anchor(session, symbol)
    try:
        return placement.multVec(anchor)
    except Exception:
        base = getattr(placement, "Base", None)
        if base is None:
            return FreeCAD.Vector()
        return FreeCAD.Vector(base.x, base.y, base.z)


def get_symbol_facing_vector(session, symbol, placement=None):
    placement = get_symbol_global_placement(session, symbol, placement=placement)
    facing = get_symbol_local_facing(session, symbol)
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
    params = getattr(session.performance_state, "plan_edit_params", None)
    if not params:
        return True
    try:
        return params.GetBool("SymbolRotateAngleSnap", True)
    except Exception:
        return True


def get_symbol_rotation_snap_increment_degrees(session):
    params = getattr(session.performance_state, "plan_edit_params", None)
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
    return math.radians(get_symbol_rotation_snap_increment_degrees(session))


def format_symbol_rotation_snap_label(session):
    increment = get_symbol_rotation_snap_increment_degrees(session)
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
    if not session.symbols.symbol_rotation_snap_enabled():
        return target_point
    if session.overlays.symbols.symbol_rotation_free_angle_override_active():
        return target_point

    snap_step = math.radians(session.overlays.symbols.get_symbol_rotation_snap_increment_degrees())
    if snap_step <= 1e-9:
        return target_point

    anchor = session.symbols.get_symbol_anchor_point(symbol, placement=placement)
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
    placement = placement or session.visibility.get_plan_object_global_placement(symbol)
    anchor = session.symbols.get_symbol_anchor_point(symbol, placement=placement)
    radius = 0.0
    for polyline in get_symbol_overlay_polylines(session, symbol, placement=placement):
        for point in polyline:
            radius = max(
                radius,
                math.hypot(float(point.x) - float(anchor.x), float(point.y) - float(anchor.y)),
            )
    units_per_pixel = session.viewport.get_plan_view_units_per_pixel() or 10.0
    return max(radius * 1.2, 28.0 * units_per_pixel, 300.0)


def get_selected_symbol_handle_specs(session, symbol):
    from draftutils import params

    if not session.visibility.is_plan_symbol_instance(symbol):
        return []

    placement = session.visibility.get_plan_object_global_placement(symbol)
    anchor = session.symbols.get_symbol_anchor_point(symbol, placement=placement)
    radius = get_symbol_handle_radius(session, symbol, placement=placement)
    rotate_direction = session.symbols.get_symbol_facing_vector(symbol, placement=placement)
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
    with _perf_trace_span(session, "sync_selected_symbol_handles"):
        tracker_state = _symbol_tracker_state(session)
        symbol = session.selection.state.get_selected_plan_target_object("symbol")
        if session.current_tool != "Select":
            clear_selected_symbol_handles(session)
            return
        if not session.visibility.is_plan_symbol_instance(symbol):
            clear_selected_symbol_handles(session)
            return
        clear_selected_symbol_handles(session)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return
        specs = get_selected_symbol_handle_specs(session, symbol)
        _perf_count(session, "selected_symbol_handles", len(specs))
        for idx, (_role, point, marker) in enumerate(specs):
            tracker = DraftTrackers.editTracker(
                pos=point,
                idx=idx,
                marker=marker,
                inactive=True,
            )
            tracker.on()
            tracker_state.symbol_handle_trackers.append(tracker)


def clear_selected_symbol_handles(session):
    tracker_state = _symbol_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.symbol_handle_trackers)
    tracker_state.symbol_handle_trackers = []


def pick_selected_symbol_handle(session, mouse_pos, radius_px=10):
    symbol = session.selection.state.get_selected_plan_target_object("symbol")
    if not session.visibility.is_plan_symbol_instance(symbol) or not session.view:
        return None
    try:
        cursor_x = int(mouse_pos[0])
        cursor_y = int(mouse_pos[1])
    except Exception:
        return None
    best_role = None
    best_distance_sq = None
    for role, point, _marker in get_selected_symbol_handle_specs(session, symbol):
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
    preview_state = _symbol_preview_state(session)
    session.symbols.clear_symbol_edit_preview()
    if session.current_tool not in ("Move Symbol", "Rotate Symbol"):
        return
    if not session.visibility.is_plan_symbol_instance(symbol) or placement is None:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    preview_color = (0.12, 0.38, 0.95)
    create_symbol_overlay_trackers(
        session,
        symbol,
        color=preview_color,
        width=session.viewport.scaled_line_width(3),
        tracker_store=preview_state.symbol_edit_preview_trackers,
        placement=placement,
    )
    if guide_start is None or guide_end is None:
        return
    guide = overlay_manager.make_plan_line_tracker(
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
    preview_state.symbol_edit_preview_trackers.append(guide)


def clear_symbol_edit_preview(session):
    preview_state = _symbol_preview_state(session)
    overlay_manager.finalize_trackers(preview_state.symbol_edit_preview_trackers)
    preview_state.symbol_edit_preview_trackers = []
