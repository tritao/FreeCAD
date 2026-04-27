# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space and region overlay helpers for BIM Plan Edit."""

from bimplan.tools import space_regions as plan_space_regions

from . import geometry as overlay_geometry
from . import manager as overlay_manager
from .. import selection as plan_selection


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _space_tracker_state(session):
    return session.overlay_tracker_state


def _space_overlay_state(session):
    return session.overlay_transient_state


def sync_secondary_selected_overlays(session):
    from . import openings as overlay_openings
    from . import symbols as overlay_symbols
    from . import walls as overlay_walls

    tracker_state = _space_tracker_state(session)
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
    for target_ref in selected_targets:
        if target_ref.kind == "wall":
            overlay_walls.create_wall_overlay_trackers(
                session,
                target_ref.obj,
                color=color,
                width=width,
                tracker_store=tracker_state.secondary_selection_trackers,
            )
        elif target_ref.kind == "opening":
            overlay_openings.create_opening_overlay_trackers(
                session,
                target_ref.obj,
                color=color,
                width=width,
                tracker_store=tracker_state.secondary_selection_trackers,
            )
        elif target_ref.kind == "symbol":
            overlay_symbols.create_symbol_overlay_trackers(
                session,
                target_ref.obj,
                color=color,
                width=width,
                tracker_store=tracker_state.secondary_selection_trackers,
            )
        elif target_ref.kind == "region":
            create_region_overlay_trackers(
                session,
                target_ref.obj,
                color=color,
                width=width,
                tracker_store=tracker_state.secondary_selection_trackers,
            )
        elif target_ref.kind == "space":
            create_space_overlay_trackers(
                session,
                target_ref.obj,
                color=color,
                width=width,
                tracker_store=tracker_state.secondary_selection_trackers,
            )


def clear_secondary_selected_overlays(session):
    tracker_state = _space_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.secondary_selection_trackers)
    tracker_state.secondary_selection_trackers = []


def sync_space_region_pick_overlays(session):
    tracker_state = _space_tracker_state(session)
    clear_space_region_pick_overlays(session)
    if session.current_tool != "Pick Space Region":
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    hovered_candidate = plan_space_regions.get_hovered_space_region_candidate(session)
    for candidate in plan_space_regions.get_space_region_pick_candidates(session):
        hovered = candidate is hovered_candidate
        color = (0.90, 0.52, 0.10) if hovered else (0.22, 0.44, 0.88)
        width = session.viewport.scaled_line_width(3 if hovered else 2)
        dotted = not hovered
        for polyline in plan_space_regions.get_space_region_candidate_polylines(
            session,
            candidate,
        ):
            if len(polyline) < 2:
                continue
            for start, end in zip(polyline, polyline[1:]):
                tracker = overlay_manager.make_plan_line_tracker(
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
                tracker_state.space_region_pick_trackers.append(tracker)


def clear_space_region_pick_overlays(session):
    tracker_state = _space_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.space_region_pick_trackers)
    tracker_state.space_region_pick_trackers = []


def create_space_overlay_trackers(session, space, color, width, tracker_store):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for polyline in overlay_geometry.get_space_overlay_polylines(session, space):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = overlay_manager.make_plan_line_tracker(
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

    for polyline in overlay_geometry.get_region_overlay_polylines(session, region):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = overlay_manager.make_plan_line_tracker(
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
    tracker_state = _space_tracker_state(session)
    clear_hovered_space_overlay(session)
    if session.current_tool != "Select":
        return
    if not session.selection.is_plan_space_object(session.hovered_space):
        return
    if session.selection.is_selected_plan_target("space", session.hovered_space):
        return
    create_space_overlay_trackers(
        session,
        session.hovered_space,
        color=(0.38, 0.62, 0.96),
        width=session.viewport.scaled_line_width(2),
        tracker_store=tracker_state.space_hover_trackers,
    )


def clear_hovered_space_overlay(session):
    tracker_state = _space_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.space_hover_trackers)
    tracker_state.space_hover_trackers = []


def sync_hovered_region_overlay(session):
    tracker_state = _space_tracker_state(session)
    clear_hovered_region_overlay(session)
    if session.current_tool != "Select":
        return
    if not session.selection.is_plan_region_object(session.hovered_region):
        return
    if session.selection.is_selected_plan_target("region", session.hovered_region):
        return
    create_region_overlay_trackers(
        session,
        session.hovered_region,
        color=(0.38, 0.62, 0.96),
        width=session.viewport.scaled_line_width(2),
        tracker_store=tracker_state.region_hover_trackers,
    )


def clear_hovered_region_overlay(session):
    tracker_state = _space_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.region_hover_trackers)
    tracker_state.region_hover_trackers = []


def invalidate_selected_space_overlay_cache(session):
    _space_overlay_state(session).selected_space_overlay_dirty = True


def sync_selected_space_overlay(session):
    with _perf_trace_span(session, "sync_selected_space_overlay"):
        overlay_state = _space_overlay_state(session)
        tracker_state = _space_tracker_state(session)
        space = plan_selection.get_selected_plan_target_object(session, "space")
        if session.current_tool not in (
            "Select",
            "Set Space Text",
        ) or not session.selection.is_plan_space_object(space):
            clear_selected_space_overlay(session)
            return
        width = session.viewport.scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_space_overlay(session)
            return
        color = (0.12, 0.38, 0.95)
        space_key = session.visibility.get_document_object_key(space)
        geometry_key = space_key
        render_state = (space_key, round(float(width), 3), color)
        if (
            not overlay_state.selected_space_overlay_dirty
            and overlay_state.selected_space_overlay_render_state == render_state
        ):
            _perf_count(session, "selected_space_overlay_cache_hits")
            return
        if (
            not overlay_state.selected_space_overlay_dirty
            and overlay_state.selected_space_overlay_geometry_key == geometry_key
        ):
            segments = overlay_state.selected_space_overlay_segments
            _perf_count(session, "selected_space_overlay_segment_cache_hits")
        else:
            segments = tuple(overlay_geometry.get_space_overlay_segments(session, space))
            overlay_state.selected_space_overlay_geometry_key = geometry_key
            overlay_state.selected_space_overlay_segments = segments
        _perf_count(session, "selected_space_overlay_segments", len(segments))
        tracker_state.space_overlay_trackers, _, _ = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=tracker_state.space_overlay_trackers,
            segments=segments,
            label="selected-space-overlay:{}".format(getattr(space, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_space_overlay(session),
        )
        overlay_state.selected_space_overlay_geometry_key = geometry_key
        overlay_state.selected_space_overlay_segments = segments
        overlay_state.selected_space_overlay_render_state = render_state
        overlay_state.selected_space_overlay_dirty = False


def clear_selected_space_overlay(session):
    tracker_state = _space_tracker_state(session)
    overlay_state = _space_overlay_state(session)
    overlay_manager.finalize_trackers(tracker_state.space_overlay_trackers)
    tracker_state.space_overlay_trackers = []
    overlay_state.selected_space_overlay_dirty = False
    overlay_state.selected_space_overlay_geometry_key = None
    overlay_state.selected_space_overlay_segments = ()
    overlay_state.selected_space_overlay_render_state = None


def sync_selected_region_overlay(session):
    with _perf_trace_span(session, "sync_selected_region_overlay"):
        tracker_state = _space_tracker_state(session)
        region = plan_selection.get_selected_plan_target_object(session, "region")
        if session.current_tool != "Select" or not session.selection.is_plan_region_object(region):
            clear_selected_region_overlay(session)
            return
        width = session.viewport.scaled_line_width(3)
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_region_overlay(session)
            return
        segments = overlay_geometry.get_region_overlay_segments(session, region)
        _perf_count(session, "selected_region_overlay_segments", len(segments))
        color = (0.12, 0.38, 0.95)
        tracker_state.region_overlay_trackers, _, _ = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=tracker_state.region_overlay_trackers,
            segments=segments,
            label="selected-region-overlay:{}".format(getattr(region, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_region_overlay(session),
        )


def clear_selected_region_overlay(session):
    tracker_state = _space_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.region_overlay_trackers)
    tracker_state.region_overlay_trackers = []
