# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-owned overlay rendering for BIM Plan Edit."""

import FreeCAD

_PROVIDER_OVERLAY_POINT_PREFIX = "ProviderOverlayPoint"


def sync_provider_overlays(session):
    with session._plan_perf_trace_span("sync_provider_overlays"):
        if (
            session.current_tool not in ("Select", "Provider Point")
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
    point_targets = tuple(getattr(overlay, "point_targets", ()) or ())
    for index, point in enumerate(tuple(getattr(overlay, "points", ()) or ())):
        target = point_targets[index] if index < len(point_targets) else None
        _create_cross_marker_trackers(
            session,
            DraftTrackers,
            "provider-overlay-point:{}".format(key),
            _to_vector(point),
            marker_size=marker_size,
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


def _create_cross_marker_trackers(
    session,
    DraftTrackers,
    label,
    point,
    *,
    marker_size,
    color,
    width,
    dotted,
    target=None,
    target_index=0,
):
    if point is None:
        return
    half_size = max(1.0, marker_size / 2.0)
    segments = (
        (
            FreeCAD.Vector(point.x - half_size, point.y, point.z),
            FreeCAD.Vector(point.x + half_size, point.y, point.z),
        ),
        (
            FreeCAD.Vector(point.x, point.y - half_size, point.z),
            FreeCAD.Vector(point.x, point.y + half_size, point.z),
        ),
    )
    for start, end in segments:
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
            int(max(2.0, session._scaled_marker_size(marker_size * 0.08))),
        )
    except Exception:
        marker = None
    kwargs = {
        "pos": point,
        "idx": int(target_index),
        "inactive": True,
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
    target_kind = str(getattr(target, "target_kind", "") or "").strip().replace(":", "_")
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
