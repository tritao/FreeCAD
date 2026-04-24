# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opening overlay and handle tracker helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from . import geometry as overlay_geometry
from . import manager as overlay_manager
from .. import selection as plan_selection


def get_opening_handle_markers(session, marker_size=None):
    from draftutils import params

    if marker_size is None:
        marker_size = session.viewport.scaled_marker_size(params.get_param_view("MarkerSize"))
    return {
        "move": FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size),
        "flip_hinge": FreeCADGui.getMarkerIndex("CIRCLE_FILLED", marker_size),
        "flip_opening": FreeCADGui.getMarkerIndex("CROSS", marker_size),
    }


def set_opening_handle_tracker_marker(tracker, marker):
    if tracker is None or marker is None:
        return
    marker_node = getattr(tracker, "marker", None)
    if marker_node is None:
        return
    try:
        marker_node.markerIndex = marker
    except Exception:
        return


def discard_opening_handle_tracker_pool(session):
    if session._opening_handle_tracker_pool:
        session.overlays.finalize_trackers(session._opening_handle_tracker_pool)
    session._opening_handle_tracker_pool = []
    session._opening_handle_tracker_pool_queued = False


def queue_prime_opening_handle_tracker_pool(session):
    if (
        session._tearing_down
        or session.current_tool != "Select"
        or session._opening_handle_tracker_pool
        or session._opening_handle_trackers
        or session._opening_handle_tracker_pool_queued
        or not session.doc
    ):
        return
    try:
        from PySide import QtCore
    except ImportError:
        return
    session._opening_handle_tracker_pool_queued = True
    QtCore.QTimer.singleShot(0, session.overlays.prime_opening_handle_tracker_pool)


def prime_opening_handle_tracker_pool(session):
    session._opening_handle_tracker_pool_queued = False
    if (
        session._tearing_down
        or session.current_tool != "Select"
        or session._opening_handle_tracker_pool
        or session._opening_handle_trackers
        or not session.doc
    ):
        return
    try:
        has_hosted_opening = any(
            session._is_hosted_opening_object(obj) for obj in getattr(session.doc, "Objects", ())
        )
    except Exception:
        has_hosted_opening = False
    if not has_hosted_opening:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return
    markers = session.overlays.get_opening_handle_markers()
    pooled_trackers = []
    try:
        for idx, role in enumerate(("move", "flip_hinge", "flip_opening")):
            tracker = DraftTrackers.editTracker(
                pos=FreeCAD.Vector(),
                idx=idx,
                marker=markers[role],
                inactive=True,
            )
            tracker.off()
            pooled_trackers.append(tracker)
    except Exception:
        session.overlays.finalize_trackers(pooled_trackers)
        return
    session._opening_handle_tracker_pool = pooled_trackers
    session._plan_perf_count("opening_handle_pool_primes")


def sync_hovered_opening_overlay(session):
    with session._plan_perf_trace_span("sync_hovered_opening_overlay"):
        opening = session.hovered_opening
        if session.current_tool != "Select":
            clear_hovered_opening_overlay(session)
            return
        if not session._is_hosted_opening_object(opening):
            clear_hovered_opening_overlay(session)
            return
        if session._is_selected_plan_target("opening", opening):
            clear_hovered_opening_overlay(session)
            return
        width = session.viewport.scaled_line_width(2)
        color = (0.38, 0.62, 0.96)
        render_state = (
            session._get_document_object_key(opening),
            round(float(width), 3),
            color,
        )
        if (
            not session._hovered_opening_overlay_dirty
            and session._hovered_opening_overlay_render_state == render_state
        ):
            for tracker in session._opening_hover_trackers:
                try:
                    raise_tracker = getattr(tracker, "raiseTracker", None)
                    if callable(raise_tracker):
                        raise_tracker()
                except Exception:
                    pass
            session._plan_perf_count("hovered_opening_overlay_cache_hits")
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_hovered_opening_overlay(session)
            return
        segments = overlay_geometry.get_opening_overlay_segments(session, opening)
        session._plan_perf_count("hovered_opening_overlay_segments", len(segments))
        if len(session._opening_hover_trackers) != len(segments):
            clear_hovered_opening_overlay(session)
            for _start, _end in segments:
                tracker = session.overlays.make_plan_line_tracker(
                    DraftTrackers,
                    "opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                session._opening_hover_trackers.append(tracker)
        for tracker, (start, end) in zip(session._opening_hover_trackers, segments):
            session.overlays.set_plan_line_tracker_width(tracker, width)
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            try:
                raise_tracker = getattr(tracker, "raiseTracker", None)
                if callable(raise_tracker):
                    raise_tracker()
            except Exception:
                pass
        session._hovered_opening_overlay_render_state = render_state
        session._hovered_opening_overlay_dirty = False


def clear_hovered_opening_overlay(session):
    session.overlays.finalize_trackers(session._opening_hover_trackers)
    session._opening_hover_trackers = []
    session._hovered_opening_overlay_dirty = False
    session._hovered_opening_overlay_render_state = None


def invalidate_hovered_opening_overlay_cache(session):
    session._hovered_opening_overlay_dirty = True


def create_opening_overlay_trackers(
    session, opening, color, width, tracker_store, include_guides=False
):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    if include_guides:
        polylines = overlay_geometry.get_opening_combined_overlay_polylines(session, opening)
    else:
        polylines = overlay_geometry.get_opening_overlay_polylines(session, opening)

    for polyline in polylines:
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = session.overlays.make_plan_line_tracker(
                DraftTrackers,
                "opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            tracker_store.append(tracker)


def sync_selected_opening_overlay(session):
    with session._plan_perf_trace_span("sync_selected_opening_overlay"):
        opening = plan_selection.get_selected_plan_target_object(session, "opening")
        if session.current_tool != "Select" or not session._is_hosted_opening_object(opening):
            clear_selected_opening_overlay(session)
            return
        width = session.viewport.scaled_line_width(3)
        color = (0.12, 0.38, 0.95)
        render_state = (
            session._get_document_object_key(opening),
            round(float(width), 3),
            color,
        )
        if (
            not session._selected_opening_overlay_dirty
            and session._selected_opening_overlay_render_state == render_state
        ):
            session._plan_perf_count("selected_opening_overlay_cache_hits")
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_opening_overlay(session)
            return
        segments = overlay_geometry.get_opening_combined_overlay_segments(session, opening)
        session._plan_perf_count("selected_opening_overlay_segments", len(segments))
        (
            session._opening_overlay_trackers,
            session._opening_hover_trackers,
            transferred_trackers,
        ) = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=session._opening_overlay_trackers,
            hover_trackers=session._opening_hover_trackers,
            segments=segments,
            label="selected-opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_opening_overlay(session),
            transfer_perf_key="selected_opening_overlay_tracker_transfers",
        )
        if transferred_trackers:
            session._hovered_opening_overlay_render_state = None
        session._selected_opening_overlay_render_state = render_state
        session._selected_opening_overlay_dirty = False


def clear_selected_opening_overlay(session):
    session.overlays.finalize_trackers(session._opening_overlay_trackers)
    session._opening_overlay_trackers = []
    session._selected_opening_overlay_dirty = False
    session._selected_opening_overlay_render_state = None


def invalidate_selected_opening_overlay_cache(session):
    session._selected_opening_overlay_dirty = True


def sync_selected_wall_opening_context_overlay(session):
    clear_selected_wall_opening_context_overlay(session)
    wall = plan_selection.get_selected_plan_target_object(session, "wall")
    if session.current_tool != "Select" or not wall or session._is_selected_plan_target("opening"):
        return
    color = (0.46, 0.58, 0.82)
    width = session.viewport.scaled_line_width(2)
    for opening in session._get_wall_hosted_openings(wall):
        if opening == session.hovered_opening:
            continue
        create_opening_overlay_trackers(
            session,
            opening,
            color=color,
            width=width,
            tracker_store=session._selected_wall_opening_context_trackers,
        )


def clear_selected_wall_opening_context_overlay(session):
    session.overlays.finalize_trackers(session._selected_wall_opening_context_trackers)
    session._selected_wall_opening_context_trackers = []


def get_selected_opening_handle_specs(session, opening):
    from draftutils import params

    handle_specs = []
    marker_size = session.viewport.scaled_marker_size(params.get_param_view("MarkerSize"))
    markers = session.overlays.get_opening_handle_markers(marker_size)
    for idx, handle in enumerate(session._get_selected_opening_edit_handles(opening)):
        if handle.role not in markers or handle.point is None:
            continue
        handle_specs.append((idx, handle.role, handle.point, markers[handle.role]))
    return handle_specs


def sync_selected_opening_handles(session):
    with session._plan_perf_trace_span("sync_selected_opening_handles"):
        from draftutils import params

        opening = plan_selection.get_selected_plan_target_object(session, "opening")
        if session.current_tool != "Select":
            clear_selected_opening_handles(session)
            return
        if not session._is_hosted_opening_object(opening):
            clear_selected_opening_handles(session)
            return
        specs = tuple(get_selected_opening_handle_specs(session, opening))
        marker_size = session.viewport.scaled_marker_size(params.get_param_view("MarkerSize"))
        handle_entries = tuple(
            (
                int(idx),
                str(role),
                round(float(point.x), 6),
                round(float(point.y), 6),
                round(float(point.z), 6),
                int(marker_size),
            )
            for idx, role, point, _marker in specs
        )
        render_state = (
            session._get_document_object_key(opening),
            handle_entries,
        )
        if session._selected_opening_handle_render_state == render_state and len(
            session._opening_handle_trackers
        ) == len(specs):
            session._plan_perf_count("selected_opening_handle_cache_hits")
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_opening_handles(session)
            return
        if len(session._opening_handle_trackers) == len(specs):
            for tracker, (_idx, _role, point, marker) in zip(
                session._opening_handle_trackers, specs
            ):
                session.overlays.set_opening_handle_tracker_marker(tracker, marker)
                tracker.set(point)
                tracker.on()
            session._plan_perf_count("selected_opening_handle_tracker_reuses")
        else:
            if not session._opening_handle_trackers and len(
                session._opening_handle_tracker_pool
            ) == len(specs):
                session._opening_handle_trackers = session._opening_handle_tracker_pool
                session._opening_handle_tracker_pool = []
                for tracker, (_idx, _role, point, marker) in zip(
                    session._opening_handle_trackers, specs
                ):
                    session.overlays.set_opening_handle_tracker_marker(tracker, marker)
                    tracker.set(point)
                    tracker.on()
                session._plan_perf_count("selected_opening_handle_pool_reuses")
            else:
                clear_selected_opening_handles(session)
                if session._opening_handle_tracker_pool and len(
                    session._opening_handle_tracker_pool
                ) != len(specs):
                    session.overlays.discard_opening_handle_tracker_pool()
                for idx, _role, point, marker in specs:
                    tracker = DraftTrackers.editTracker(
                        pos=point,
                        idx=idx,
                        marker=marker,
                        inactive=True,
                    )
                    tracker.on()
                    session._opening_handle_trackers.append(tracker)
        session._selected_opening_handle_render_state = render_state


def clear_selected_opening_handles(session):
    if session._opening_handle_trackers:
        session.overlays.discard_opening_handle_tracker_pool()
        for tracker in session._opening_handle_trackers:
            try:
                tracker.off()
            except Exception:
                pass
        session._opening_handle_tracker_pool = session._opening_handle_trackers
    session._opening_handle_trackers = []
    session._selected_opening_handle_render_state = None
