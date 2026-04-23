# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-owned overlay rendering for BIM Plan Edit."""

from contextlib import nullcontext
import math

import FreeCAD
from bimplan.providers import PlanOverlayMarkerKind
from .. import selection_access as plan_selection_access

_PROVIDER_OVERLAY_POINT_PREFIX = "ProviderOverlayPoint"
_PROVIDER_OVERLAY_PICK_TRACKER_SCALE = 0.14
_PROVIDER_HOVER_COLOR = (0.38, 0.62, 0.96)
_PROVIDER_HOVER_MARKER_SCALE = 1.2
_PROVIDER_HOVER_WIDTH_DELTA = 1.0
_PROVIDER_SELECTED_COLOR = (0.12, 0.38, 0.95)
_PROVIDER_SELECTED_MARKER_SCALE = 1.3
_PROVIDER_SELECTED_WIDTH_DELTA = 1.5
_PROVIDER_POINT_PREVIEW_MARKER_SIZE = 180.0
_PROVIDER_POINT_PREVIEW_HOSTED_COLOR = (0.12, 0.38, 0.95)
_PROVIDER_POINT_PREVIEW_UNHOSTED_COLOR = (0.95, 0.52, 0.10)
_PROVIDER_POINT_PREVIEW_HOST_COLOR = (0.10, 0.58, 0.38)


def sync_provider_overlays(session):
    with session._plan_perf_trace_span("sync_provider_overlays"):
        document_is_alive = getattr(session, "_document_is_alive", None)
        if (
            session._tearing_down
            or getattr(session, "_finishing", False)
            or (callable(document_is_alive) and not document_is_alive())
            or session.current_tool not in ("Select", "Provider Point")
            or session._plan_provider_integrations_disabled()
        ):
            clear_provider_overlays(session)
            return

        with session._plan_provider_refresh_cache_scope():
            overlays = tuple(
                overlay
                for overlay in session.get_plan_provider_overlays()
                if bool(getattr(overlay, "visible", True))
                and session.is_plan_provider_overlay_visible(overlay)
            )
        render_state = (
            overlays,
            round(float(session._get_plan_overlay_scale()), 4),
        )
        if render_state == session._provider_overlay_state:
            session._plan_perf_count("provider_overlay_cache_hits")
            return

        clear_provider_overlays(session)
        session._provider_overlay_state = render_state

        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return

        for overlay in overlays:
            _create_provider_overlay_trackers(session, DraftTrackers, overlay)
        session._plan_perf_count(
            "provider_overlay_trackers",
            len(session._provider_overlay_trackers),
        )


def clear_provider_overlays(session):
    session._finalize_trackers(session._provider_overlay_trackers)
    session._provider_overlay_trackers = []
    session._provider_overlay_state = None


def sync_hovered_provider_overlay(session):
    with session._plan_perf_trace_span("sync_hovered_provider_overlay"):
        clear_hovered_provider_overlay(session)
        if session.current_tool != "Select":
            return
        plan_provider_integrations_disabled = getattr(
            session, "_plan_provider_integrations_disabled", None
        )
        if callable(plan_provider_integrations_disabled) and plan_provider_integrations_disabled():
            return
        provider_obj = getattr(session, "hovered_provider", None)
        if provider_obj is None:
            return
        if session._is_selected_plan_target("provider", provider_obj):
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            return
        specs = _get_hovered_provider_segment_specs(session)
        if not specs:
            return
        for spec in specs:
            tracker = session._make_plan_line_tracker(
                DraftTrackers,
                spec["label"],
                dotted=spec["dotted"],
                scolor=spec["color"],
                swidth=spec["width"],
                ontop=True,
            )
            tracker.p1(spec["start"])
            tracker.p2(spec["end"])
            tracker.on()
            session._provider_hover_trackers.append(tracker)
        session._plan_perf_count("hovered_provider_trackers", len(session._provider_hover_trackers))


def clear_hovered_provider_overlay(session):
    session._finalize_trackers(session._provider_hover_trackers)
    session._provider_hover_trackers = []


def sync_selected_provider_overlay(session):
    with session._plan_perf_trace_span("sync_selected_provider_overlay"):
        if session.current_tool != "Select":
            clear_selected_provider_overlay(session)
            return
        plan_provider_integrations_disabled = getattr(
            session, "_plan_provider_integrations_disabled", None
        )
        if callable(plan_provider_integrations_disabled) and plan_provider_integrations_disabled():
            clear_selected_provider_overlay(session)
            return
        selected_objects = _get_selected_provider_objects(session)
        if not selected_objects:
            clear_selected_provider_overlay(session)
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_provider_overlay(session)
            return
        specs = _get_selected_provider_segment_specs(session, selected_objects)
        if not specs:
            clear_selected_provider_overlay(session)
            return
        selected_keys = tuple(
            key
            for key in (
                session._get_document_object_key(provider_obj) for provider_obj in selected_objects
            )
            if key is not None
        )
        render_state = (
            selected_keys,
            _get_provider_segment_render_state(session, specs),
        )
        if render_state == session._selected_provider_overlay_render_state:
            session._plan_perf_count("selected_provider_overlay_cache_hits")
            return
        clear_selected_provider_overlay(session)
        for spec in specs:
            tracker = session._make_plan_line_tracker(
                DraftTrackers,
                spec["label"],
                dotted=spec["dotted"],
                scolor=spec["color"],
                swidth=spec["width"],
                ontop=True,
            )
            tracker.p1(spec["start"])
            tracker.p2(spec["end"])
            tracker.on()
            session._provider_selected_trackers.append(tracker)
        session._selected_provider_overlay_render_state = render_state
        session._plan_perf_count(
            "selected_provider_trackers",
            len(session._provider_selected_trackers),
        )


def clear_selected_provider_overlay(session):
    session._finalize_trackers(session._provider_selected_trackers)
    session._provider_selected_trackers = []
    session._selected_provider_overlay_render_state = None


def get_selected_provider_handle_specs(session, provider_obj):
    try:
        from draftutils import params
    except ImportError:
        return []
    if not session._is_selected_plan_target("provider", provider_obj):
        return []
    marker_size = session._scaled_marker_size(params.get_param_view("MarkerSize"))
    specs = []
    for idx, handle in enumerate(session._get_selected_provider_edit_handles(provider_obj)):
        point = _to_vector(getattr(handle, "point", None))
        if point is None:
            continue
        marker = _get_provider_handle_marker(getattr(handle, "marker_kind", None), marker_size)
        specs.append((idx, handle, point, marker))
    return specs


def sync_selected_provider_handles(session):
    with session._plan_perf_trace_span("sync_selected_provider_handles"):
        provider_obj = plan_selection_access.get_selected_plan_target_object(session, "provider")
        if session.current_tool != "Select":
            session._clear_selected_provider_handles()
            return
        if not session._is_plan_provider_target_object(provider_obj):
            session._clear_selected_provider_handles()
            return
        specs = tuple(session._get_selected_provider_handle_specs(provider_obj))
        render_state = (
            session._get_document_object_key(provider_obj),
            tuple(
                (
                    int(idx),
                    str(getattr(handle, "key", "") or ""),
                    round(float(point.x), 6),
                    round(float(point.y), 6),
                    round(float(point.z), 6),
                    -1 if marker is None else int(marker),
                )
                for idx, handle, point, marker in specs
            ),
        )
        if session._selected_provider_handle_render_state == render_state and len(
            session._provider_handle_trackers
        ) == len(specs):
            session._plan_perf_count("selected_provider_handle_cache_hits")
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            session._clear_selected_provider_handles()
            return
        session._clear_selected_provider_handles()
        for idx, _handle, point, marker in specs:
            kwargs = dict(
                pos=point,
                idx=idx,
                inactive=True,
            )
            if marker is not None:
                kwargs["marker"] = marker
            tracker = DraftTrackers.editTracker(**kwargs)
            tracker.on()
            session._provider_handle_trackers.append(tracker)
        session._selected_provider_handle_render_state = render_state


def clear_selected_provider_handles(session):
    session._finalize_trackers(session._provider_handle_trackers)
    session._provider_handle_trackers = []
    session._selected_provider_handle_render_state = None


def pick_selected_provider_handle(session, mouse_pos, radius_px=10):
    provider_obj = plan_selection_access.get_selected_plan_target_object(session, "provider")
    if not session._is_plan_provider_target_object(provider_obj) or not session.view:
        return None
    try:
        cursor_x = int(mouse_pos[0])
        cursor_y = int(mouse_pos[1])
    except Exception:
        return None
    best_index = None
    best_distance_sq = None
    for idx, _handle, point, _marker in session._get_selected_provider_handle_specs(provider_obj):
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
            best_index = idx
            best_distance_sq = distance_sq
    return best_index


def sync_provider_point_preview(session):
    if session.current_tool != "Provider Point" or session._provider_point_preview_point is None:
        clear_provider_point_preview(session)
        return

    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        clear_provider_point_preview(session)
        return

    specs = _get_provider_point_preview_segment_specs(session)
    if not specs:
        clear_provider_point_preview(session)
        return

    render_state = _get_provider_segment_render_state(session, specs)
    if render_state == session._provider_point_preview_render_state:
        session._plan_perf_count("provider_point_preview_cache_hits")
        return

    style_state = tuple((spec["label"], spec["dotted"]) for spec in specs)
    if (
        len(session._provider_point_preview_trackers) != len(specs)
        or style_state != session._provider_point_preview_style_state
    ):
        _clear_provider_point_preview_trackers(session)
        session._provider_point_preview_style_state = style_state
        for spec in specs:
            tracker = session._make_plan_line_tracker(
                DraftTrackers,
                spec["label"],
                dotted=spec["dotted"],
                scolor=spec["color"],
                swidth=spec["width"],
                ontop=True,
            )
            session._provider_point_preview_trackers.append(tracker)

    for tracker, spec in zip(session._provider_point_preview_trackers, specs):
        session._set_plan_line_tracker_width(tracker, spec["width"])
        tracker.setColor(spec["color"])
        tracker.p1(spec["start"])
        tracker.p2(spec["end"])
        tracker.on()

    session._provider_point_preview_render_state = render_state
    session._plan_perf_count(
        "provider_point_preview_trackers",
        len(session._provider_point_preview_trackers),
    )


def clear_provider_point_preview(session):
    _clear_provider_point_preview_trackers(session)
    session._provider_point_preview_source_point = None
    session._provider_point_preview_point = None
    session._provider_point_preview_host_target = None
    session._provider_point_preview_host_source = ""


def _clear_provider_point_preview_trackers(session):
    session._finalize_trackers(session._provider_point_preview_trackers)
    session._provider_point_preview_trackers = []
    session._provider_point_preview_render_state = None
    session._provider_point_preview_style_state = None


def _get_provider_point_preview_segment_specs(session):
    point = _to_vector(session._provider_point_preview_point)
    if point is None:
        return ()
    source = _to_vector(session._provider_point_preview_source_point)
    if source is None:
        source = point
    host_kind, host_obj = _normalize_host_target(session._provider_point_preview_host_target)
    hosted = host_kind == "wall" and host_obj is not None
    preview_color = (
        _PROVIDER_POINT_PREVIEW_HOSTED_COLOR if hosted else _PROVIDER_POINT_PREVIEW_UNHOSTED_COLOR
    )
    width = session._scaled_line_width(2)
    specs = []
    specs.extend(
        _get_point_marker_segment_specs(
            point,
            label="provider-point-preview-marker",
            color=preview_color,
            width=width,
            dotted=not hosted,
            marker_size=session._scaled_marker_size(_PROVIDER_POINT_PREVIEW_MARKER_SIZE),
            marker_kind=PlanOverlayMarkerKind.CROSS,
        )
    )
    if hosted:
        specs.extend(
            _get_provider_point_host_segment_specs(
                session,
                host_obj,
                color=_PROVIDER_POINT_PREVIEW_HOST_COLOR,
                width=session._scaled_line_width(2),
            )
        )
        if FreeCAD.Vector(source).sub(point).Length > 1e-6:
            specs.append(
                {
                    "label": "provider-point-preview-tether",
                    "start": source,
                    "end": point,
                    "color": preview_color,
                    "width": session._scaled_line_width(1),
                    "dotted": True,
                }
            )
    return tuple(specs)


def _get_point_marker_segment_specs(
    point,
    *,
    label,
    color,
    width,
    dotted,
    marker_size,
    marker_kind,
):
    if marker_kind == PlanOverlayMarkerKind.CIRCLE:
        return _get_circle_marker_segment_specs(
            point,
            label=label,
            color=color,
            width=width,
            dotted=dotted,
            marker_size=marker_size,
        )
    if marker_kind == PlanOverlayMarkerKind.CIRCLE_CROSS:
        return _get_circle_marker_segment_specs(
            point,
            label=label,
            color=color,
            width=width,
            dotted=dotted,
            marker_size=marker_size,
        ) + _get_cross_marker_segment_specs(
            point,
            label=label,
            color=color,
            width=width,
            dotted=dotted,
            marker_size=marker_size * 0.7,
        )
    if marker_kind == PlanOverlayMarkerKind.DIAMOND:
        half_size = max(1.0, float(marker_size) / 2.0)
        return _get_polyline_marker_segment_specs(
            (
                FreeCAD.Vector(point.x, point.y + half_size, point.z),
                FreeCAD.Vector(point.x + half_size, point.y, point.z),
                FreeCAD.Vector(point.x, point.y - half_size, point.z),
                FreeCAD.Vector(point.x - half_size, point.y, point.z),
            ),
            label=label,
            color=color,
            width=width,
            dotted=dotted,
            closed=True,
        )
    if marker_kind == PlanOverlayMarkerKind.HOURGLASS:
        half_size = max(1.0, float(marker_size) / 2.0)
        return _get_polyline_marker_segment_specs(
            (
                FreeCAD.Vector(point.x - half_size, point.y + half_size, point.z),
                FreeCAD.Vector(point.x + half_size, point.y + half_size, point.z),
                FreeCAD.Vector(point.x - half_size, point.y - half_size, point.z),
                FreeCAD.Vector(point.x + half_size, point.y - half_size, point.z),
            ),
            label=label,
            color=color,
            width=width,
            dotted=dotted,
            closed=True,
        )
    if marker_kind == PlanOverlayMarkerKind.SQUARE:
        half_size = max(1.0, float(marker_size) / 2.0)
        return _get_polyline_marker_segment_specs(
            (
                FreeCAD.Vector(point.x - half_size, point.y + half_size, point.z),
                FreeCAD.Vector(point.x + half_size, point.y + half_size, point.z),
                FreeCAD.Vector(point.x + half_size, point.y - half_size, point.z),
                FreeCAD.Vector(point.x - half_size, point.y - half_size, point.z),
            ),
            label=label,
            color=color,
            width=width,
            dotted=dotted,
            closed=True,
        )
    return _get_cross_marker_segment_specs(
        point,
        label=label,
        color=color,
        width=width,
        dotted=dotted,
        marker_size=marker_size,
    )


def _get_provider_handle_marker(marker_kind, marker_size):
    try:
        import FreeCADGui
    except Exception:
        return None
    marker_name = {
        PlanOverlayMarkerKind.CIRCLE: "CIRCLE_FILLED",
        PlanOverlayMarkerKind.CIRCLE_CROSS: "CIRCLE_FILLED",
        PlanOverlayMarkerKind.CROSS: "CROSS",
        PlanOverlayMarkerKind.DIAMOND: "DIAMOND_FILLED",
        PlanOverlayMarkerKind.HOURGLASS: "DIAMOND_FILLED",
        PlanOverlayMarkerKind.SQUARE: "SQUARE_FILLED",
    }.get(marker_kind, "DIAMOND_FILLED")
    try:
        return FreeCADGui.getMarkerIndex(marker_name, marker_size)
    except Exception:
        return None


def _get_cross_marker_segment_specs(point, *, label, color, width, dotted, marker_size):
    half_size = max(1.0, float(marker_size) / 2.0)
    return (
        {
            "label": label,
            "start": FreeCAD.Vector(point.x - half_size, point.y, point.z),
            "end": FreeCAD.Vector(point.x + half_size, point.y, point.z),
            "color": color,
            "width": width,
            "dotted": dotted,
        },
        {
            "label": label,
            "start": FreeCAD.Vector(point.x, point.y - half_size, point.z),
            "end": FreeCAD.Vector(point.x, point.y + half_size, point.z),
            "color": color,
            "width": width,
            "dotted": dotted,
        },
    )


def _get_circle_marker_segment_specs(point, *, label, color, width, dotted, marker_size):
    radius = max(1.0, float(marker_size) / 2.0)
    segments = max(8, int(round(radius / 25.0)))
    circle_points = []
    for index in range(segments):
        angle = (2.0 * math.pi * index) / float(segments)
        circle_points.append(
            FreeCAD.Vector(
                point.x + math.cos(angle) * radius,
                point.y + math.sin(angle) * radius,
                point.z,
            )
        )
    return _get_polyline_marker_segment_specs(
        tuple(circle_points),
        label=label,
        color=color,
        width=width,
        dotted=dotted,
        closed=True,
    )


def _get_polyline_marker_segment_specs(points, *, label, color, width, dotted, closed):
    points = tuple(_to_vector(point) for point in tuple(points or ()))
    points = tuple(point for point in points if point is not None)
    if len(points) < 2:
        return ()
    segment_points = points + (points[0],) if closed else points
    return tuple(
        {
            "label": label,
            "start": start,
            "end": end,
            "color": color,
            "width": width,
            "dotted": dotted,
        }
        for start, end in zip(segment_points, segment_points[1:])
    )


def _get_provider_point_host_segment_specs(session, host_wall, *, color, width):
    specs = []
    for polyline in session._get_wall_overlay_polylines(host_wall):
        points = tuple(_to_vector(point) for point in tuple(polyline or ()))
        points = tuple(point for point in points if point is not None)
        if len(points) < 2:
            continue
        for start, end in zip(points, points[1:]):
            specs.append(
                {
                    "label": "provider-point-preview-host",
                    "start": start,
                    "end": end,
                    "color": color,
                    "width": width,
                    "dotted": False,
                }
            )
    return tuple(specs)


def _get_provider_segment_render_state(session, specs):
    return (
        round(float(session._get_plan_overlay_scale()), 4),
        tuple(
            (
                spec["label"],
                _round_vector(spec["start"]),
                _round_vector(spec["end"]),
                _round_tuple(spec["color"]),
                round(float(spec["width"]), 4),
                bool(spec["dotted"]),
            )
            for spec in specs
        ),
    )


def _get_selected_provider_objects(session):
    selected_objects = []
    seen = set()
    for provider_obj in (
        plan_selection_access.get_selected_plan_target_object(session, "provider"),
        *tuple(getattr(session, "_get_provider_selected_objects", lambda: ())() or ()),
    ):
        if provider_obj is None:
            continue
        object_key = session._get_document_object_key(provider_obj)
        if object_key is None or object_key in seen:
            continue
        seen.add(object_key)
        selected_objects.append(provider_obj)
    return tuple(selected_objects)


def _get_selected_provider_segment_specs(session, selected_objects):
    selected_keys = {
        key
        for key in (
            session._get_document_object_key(provider_obj) for provider_obj in selected_objects
        )
        if key is not None
    }
    if not selected_keys:
        return ()
    specs = []
    for overlay in _get_visible_provider_overlays(session):
        key = str(getattr(overlay, "key", "") or "overlay")
        marker_size = session._scaled_marker_size(
            float(getattr(overlay, "marker_size", 160.0) or 160.0) * _PROVIDER_SELECTED_MARKER_SCALE
        )
        width = session._scaled_line_width(
            max(2.0, float(getattr(overlay, "line_width", 2.0) or 2.0))
            + _PROVIDER_SELECTED_WIDTH_DELTA
        )
        point_targets = tuple(getattr(overlay, "point_targets", ()) or ())
        for index, point in enumerate(tuple(getattr(overlay, "points", ()) or ())):
            target = point_targets[index] if index < len(point_targets) else None
            if not _provider_target_matches_object(session, target, selected_keys):
                continue
            point_vector = _to_vector(point)
            if point_vector is None:
                continue
            specs.extend(
                _get_point_marker_segment_specs(
                    point_vector,
                    label="selected-provider-overlay:{}".format(key),
                    color=_PROVIDER_SELECTED_COLOR,
                    width=width,
                    dotted=False,
                    marker_size=marker_size,
                    marker_kind=PlanOverlayMarkerKind.CIRCLE,
                )
            )
    return tuple(specs)


def _get_hovered_provider_segment_specs(session):
    provider_obj = getattr(session, "hovered_provider", None)
    object_key = session._get_document_object_key(provider_obj)
    if object_key is None:
        return ()
    specs = []
    for overlay in _get_visible_provider_overlays(session):
        key = str(getattr(overlay, "key", "") or "overlay")
        marker_size = session._scaled_marker_size(
            float(getattr(overlay, "marker_size", 160.0) or 160.0) * _PROVIDER_HOVER_MARKER_SCALE
        )
        width = session._scaled_line_width(
            max(2.0, float(getattr(overlay, "line_width", 2.0) or 2.0))
            + _PROVIDER_HOVER_WIDTH_DELTA
        )
        marker_kind = overlay.marker_kind
        point_targets = tuple(getattr(overlay, "point_targets", ()) or ())
        for index, point in enumerate(tuple(getattr(overlay, "points", ()) or ())):
            target = point_targets[index] if index < len(point_targets) else None
            if not _provider_target_matches_object(session, target, object_key):
                continue
            point_vector = _to_vector(point)
            if point_vector is None:
                continue
            specs.extend(
                _get_point_marker_segment_specs(
                    point_vector,
                    label="hovered-provider-overlay:{}".format(key),
                    color=_PROVIDER_HOVER_COLOR,
                    width=width,
                    dotted=False,
                    marker_size=marker_size,
                    marker_kind=marker_kind,
                )
            )
    return tuple(specs)


def _get_visible_provider_overlays(session):
    refresh_scope_factory = getattr(session, "_plan_provider_refresh_cache_scope", None)
    refresh_scope = refresh_scope_factory() if callable(refresh_scope_factory) else nullcontext()
    with refresh_scope:
        return tuple(
            overlay
            for overlay in session.get_plan_provider_overlays()
            if bool(getattr(overlay, "visible", True))
            and session.is_plan_provider_overlay_visible(overlay)
        )


def _create_provider_overlay_trackers(session, DraftTrackers, overlay):
    color = tuple(getattr(overlay, "color", (0.2, 0.55, 0.85)) or (0.2, 0.55, 0.85))
    width = session._scaled_line_width(float(getattr(overlay, "line_width", 2.0) or 2.0))
    dotted = bool(getattr(overlay, "dotted", False))
    key = str(getattr(overlay, "key", "") or "overlay")
    for polyline in tuple(getattr(overlay, "polylines", ()) or ()):
        _create_polyline_trackers(
            session,
            DraftTrackers,
            "provider-overlay:{}".format(key),
            polyline,
            color=color,
            width=width,
            dotted=dotted,
        )
    marker_size = float(getattr(overlay, "marker_size", 160.0) or 160.0)
    marker_kind = overlay.marker_kind
    point_targets = tuple(getattr(overlay, "point_targets", ()) or ())
    for index, point in enumerate(tuple(getattr(overlay, "points", ()) or ())):
        target = point_targets[index] if index < len(point_targets) else None
        _create_point_marker_trackers(
            session,
            DraftTrackers,
            "provider-overlay-point:{}".format(key),
            _to_vector(point),
            marker_size=marker_size,
            marker_kind=marker_kind,
            color=color,
            width=width,
            dotted=dotted,
            target=target,
            target_index=index,
        )


def _create_polyline_trackers(session, DraftTrackers, label, polyline, *, color, width, dotted):
    points = tuple(_to_vector(point) for point in tuple(polyline or ()))
    points = tuple(point for point in points if point is not None)
    if len(points) < 2:
        return
    for start, end in zip(points, points[1:]):
        tracker = session._make_plan_line_tracker(
            DraftTrackers,
            label,
            dotted=dotted,
            scolor=color,
            swidth=width,
            ontop=True,
        )
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()
        session._provider_overlay_trackers.append(tracker)


def _create_point_marker_trackers(
    session,
    DraftTrackers,
    label,
    point,
    *,
    marker_size,
    marker_kind,
    color,
    width,
    dotted,
    target=None,
    target_index=0,
):
    if point is None:
        return
    for spec in _get_point_marker_segment_specs(
        point,
        label=label,
        color=color,
        width=width,
        dotted=dotted,
        marker_size=marker_size,
        marker_kind=marker_kind,
    ):
        tracker = session._make_plan_line_tracker(
            DraftTrackers,
            spec["label"],
            dotted=spec["dotted"],
            scolor=spec["color"],
            swidth=spec["width"],
            ontop=True,
        )
        tracker.p1(spec["start"])
        tracker.p2(spec["end"])
        tracker.on()
        session._provider_overlay_trackers.append(tracker)
    _create_target_pick_tracker(
        session,
        DraftTrackers,
        point,
        target,
        target_index=target_index,
        marker_size=marker_size,
    )


def _create_target_pick_tracker(
    session, DraftTrackers, point, target, *, target_index, marker_size
):
    if point is None or not _has_target_identity(target):
        return
    marker = None
    try:
        import FreeCADGui

        marker = FreeCADGui.getMarkerIndex(
            "CIRCLE",
            int(
                max(
                    4.0,
                    session._scaled_marker_size(marker_size * _PROVIDER_OVERLAY_PICK_TRACKER_SCALE),
                )
            ),
        )
    except Exception:
        marker = None
    kwargs = {
        "pos": point,
        "idx": int(target_index),
        "inactive": False,
    }
    if marker is not None:
        kwargs["marker"] = marker
    try:
        tracker = DraftTrackers.editTracker(**kwargs)
    except Exception:
        return
    if not _retarget_pick_tracker(session, tracker, target, target_index):
        session._finalize_trackers([tracker])
        return
    try:
        tracker.on()
    except Exception:
        pass
    session._provider_overlay_trackers.append(tracker)


def _has_target_identity(target):
    return bool(str(getattr(target, "object_name", "") or "").strip())


def _get_target_identity(session, target):
    if not _has_target_identity(target):
        return None
    document_name = str(getattr(target, "document_name", "") or "").strip()
    if not document_name:
        document_name = str(getattr(getattr(session, "doc", None), "Name", "") or "")
    object_name = str(getattr(target, "object_name", "") or "").strip()
    if not document_name or not object_name:
        return None
    return (document_name, object_name)


def _provider_target_matches_object(session, target, object_key):
    if object_key is None:
        return False
    target_identity = _get_target_identity(session, target)
    if isinstance(object_key, (set, frozenset)):
        return target_identity in object_key
    if isinstance(object_key, tuple) and object_key and isinstance(object_key[0], tuple):
        return target_identity in object_key
    return target_identity == object_key


def _retarget_pick_tracker(session, tracker, target, target_index):
    selnode = getattr(tracker, "selnode", None)
    if selnode is None:
        return False
    document_name = str(getattr(target, "document_name", "") or "").strip()
    if not document_name:
        document_name = str(getattr(getattr(session, "doc", None), "Name", "") or "")
    object_name = str(getattr(target, "object_name", "") or "").strip()
    if not document_name or not object_name:
        return False
    target_kind = target.target_kind.value if target.target_kind is not None else ""
    target_kind = target_kind.replace(":", "_")
    subname = "{}:{}:{}".format(_PROVIDER_OVERLAY_POINT_PREFIX, target_kind, int(target_index))
    try:
        if hasattr(selnode, "useNewSelection"):
            selnode.useNewSelection = False
        selnode.documentName.setValue(document_name)
        selnode.objectName.setValue(object_name)
        selnode.subElementName.setValue(subname)
    except Exception:
        return False
    return True


def _to_vector(point):
    if point is None:
        return None
    if isinstance(point, FreeCAD.Vector):
        return FreeCAD.Vector(point)
    try:
        return FreeCAD.Vector(float(point[0]), float(point[1]), float(point[2]))
    except (TypeError, ValueError, IndexError):
        return None


def _normalize_host_target(target):
    if not target:
        return (None, None)
    try:
        host_kind, host_obj = target
    except Exception:
        return (None, None)
    if host_kind == "wall" and host_obj is not None:
        return host_kind, host_obj
    return (None, None)


def _round_vector(point):
    return (
        round(float(point.x), 4),
        round(float(point.y), 4),
        round(float(point.z), 4),
    )


def _round_tuple(values):
    return tuple(round(float(value), 4) for value in tuple(values or ()))
