# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space and region overlay helpers for BIM Plan Edit."""

from . import manager as overlay_manager
from .. import selection as plan_selection


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def sync_secondary_selected_overlays(session):
    clear_secondary_selected_overlays(session)
    if session.current_tool not in ("Select", "Pick Space Region"):
        return
    color = (0.12, 0.72, 0.68)
    width = session.viewport.scaled_line_width(2)
    selected_targets = (
        session.selection.get_selected_plan_targets()
        if session.current_tool == "Pick Space Region"
        else session.selection.get_secondary_selected_plan_targets()
    )
    for target_kind, target_obj in selected_targets:
        if target_kind == "wall":
            session.overlays.create_wall_overlay_trackers(
                target_obj,
                color=color,
                width=width,
                tracker_store=session._secondary_selection_trackers,
            )
        elif target_kind == "opening":
            session.overlays.create_opening_overlay_trackers(
                target_obj,
                color=color,
                width=width,
                tracker_store=session._secondary_selection_trackers,
            )
        elif target_kind == "symbol":
            session.overlays.create_symbol_overlay_trackers(
                target_obj,
                color=color,
                width=width,
                tracker_store=session._secondary_selection_trackers,
            )
        elif target_kind == "region":
            create_region_overlay_trackers(
                session,
                target_obj,
                color=color,
                width=width,
                tracker_store=session._secondary_selection_trackers,
            )
        elif target_kind == "space":
            create_space_overlay_trackers(
                session,
                target_obj,
                color=color,
                width=width,
                tracker_store=session._secondary_selection_trackers,
            )


def clear_secondary_selected_overlays(session):
    session.overlays.finalize_trackers(session._secondary_selection_trackers)
    session._secondary_selection_trackers = []


def sync_space_region_pick_overlays(session):
    clear_space_region_pick_overlays(session)
    if session.current_tool != "Pick Space Region":
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for candidate in session._space_region_candidates:
        hovered = candidate is session._hovered_space_region_candidate
        color = (0.90, 0.52, 0.10) if hovered else (0.22, 0.44, 0.88)
        width = session.viewport.scaled_line_width(3 if hovered else 2)
        dotted = not hovered
        for polyline in session.spaces.get_space_region_candidate_polylines(candidate):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = session.overlays.make_plan_line_tracker(
                    DraftTrackers,
                    "space-region-pick:{}".format(candidate.get("index", "unknown")),
                    dotted=dotted,
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                tracker.p1(start)
                tracker.p2(end)
                tracker.on()
                session._space_region_pick_trackers.append(tracker)


def clear_space_region_pick_overlays(session):
    session.overlays.finalize_trackers(session._space_region_pick_trackers)
    session._space_region_pick_trackers = []


def create_space_overlay_trackers(session, space, color, width, tracker_store):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for polyline in session.overlays.get_space_overlay_polylines(space):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = session.overlays.make_plan_line_tracker(
                DraftTrackers,
                "space-overlay:{}".format(getattr(space, "Name", "unknown")),
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            tracker_store.append(tracker)


def create_region_overlay_trackers(session, region, color, width, tracker_store):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for polyline in session.overlays.get_region_overlay_polylines(region):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = session.overlays.make_plan_line_tracker(
                DraftTrackers,
                "region-overlay:{}".format(getattr(region, "Name", "unknown")),
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            tracker_store.append(tracker)


def sync_hovered_space_overlay(session):
    clear_hovered_space_overlay(session)
    if session.current_tool != "Select":
        return
    if not session._is_plan_space_object(session.hovered_space):
        return
    if session._is_selected_plan_target("space", session.hovered_space):
        return
    create_space_overlay_trackers(
        session,
        session.hovered_space,
        color=(0.38, 0.62, 0.96),
        width=session.viewport.scaled_line_width(2),
        tracker_store=session._space_hover_trackers,
    )


def clear_hovered_space_overlay(session):
    session.overlays.finalize_trackers(session._space_hover_trackers)
    session._space_hover_trackers = []


def sync_hovered_region_overlay(session):
    clear_hovered_region_overlay(session)
    if session.current_tool != "Select":
        return
    if not session._is_plan_region_object(session.hovered_region):
        return
    if session._is_selected_plan_target("region", session.hovered_region):
        return
    create_region_overlay_trackers(
        session,
        session.hovered_region,
        color=(0.38, 0.62, 0.96),
        width=session.viewport.scaled_line_width(2),
        tracker_store=session._region_hover_trackers,
    )


def clear_hovered_region_overlay(session):
    session.overlays.finalize_trackers(session._region_hover_trackers)
    session._region_hover_trackers = []


def invalidate_selected_space_overlay_cache(session):
    session._selected_space_overlay_dirty = True


def sync_selected_space_overlay(session):
    with _perf_trace_span(session, "sync_selected_space_overlay"):
        space = plan_selection.get_selected_plan_target_object(session, "space")
        if session.current_tool not in (
            "Select",
            "Set Space Text",
        ) or not session._is_plan_space_object(space):
            clear_selected_space_overlay(session)
            return
        width = session.viewport.scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_space_overlay(session)
            return
        color = (0.12, 0.38, 0.95)
        space_key = session._get_document_object_key(space)
        geometry_key = space_key
        render_state = (space_key, round(float(width), 3), color)
        if (
            not session._selected_space_overlay_dirty
            and session._selected_space_overlay_render_state == render_state
        ):
            _perf_count(session, "selected_space_overlay_cache_hits")
            return
        if (
            not session._selected_space_overlay_dirty
            and session._selected_space_overlay_geometry_key == geometry_key
        ):
            segments = session._selected_space_overlay_segments
            _perf_count(session, "selected_space_overlay_segment_cache_hits")
        else:
            segments = tuple(session.overlays.get_space_overlay_segments(space))
            session._selected_space_overlay_geometry_key = geometry_key
            session._selected_space_overlay_segments = segments
        _perf_count(session, "selected_space_overlay_segments", len(segments))
        session._space_overlay_trackers, _, _ = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=session._space_overlay_trackers,
            segments=segments,
            label="selected-space-overlay:{}".format(getattr(space, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_space_overlay(session),
        )
        session._selected_space_overlay_geometry_key = geometry_key
        session._selected_space_overlay_segments = segments
        session._selected_space_overlay_render_state = render_state
        session._selected_space_overlay_dirty = False


def clear_selected_space_overlay(session):
    session.overlays.finalize_trackers(session._space_overlay_trackers)
    session._space_overlay_trackers = []
    session._selected_space_overlay_dirty = False
    session._selected_space_overlay_geometry_key = None
    session._selected_space_overlay_segments = ()
    session._selected_space_overlay_render_state = None


def sync_selected_region_overlay(session):
    with _perf_trace_span(session, "sync_selected_region_overlay"):
        region = plan_selection.get_selected_plan_target_object(session, "region")
        if session.current_tool != "Select" or not session._is_plan_region_object(region):
            clear_selected_region_overlay(session)
            return
        width = session.viewport.scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_region_overlay(session)
            return
        segments = session.overlays.get_region_overlay_segments(region)
        _perf_count(session, "selected_region_overlay_segments", len(segments))
        color = (0.12, 0.38, 0.95)
        session._region_overlay_trackers, _, _ = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=session._region_overlay_trackers,
            segments=segments,
            label="selected-region-overlay:{}".format(getattr(region, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_region_overlay(session),
        )


def clear_selected_region_overlay(session):
    session.overlays.finalize_trackers(session._region_overlay_trackers)
    session._region_overlay_trackers = []
