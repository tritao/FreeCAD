# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall overlay and grip tracker helpers for BIM Plan Edit."""

import FreeCAD

from . import geometry as overlay_geometry
from . import manager as overlay_manager
from . import openings as overlay_openings


class PlanWallOverlayService:
    """Owned session surface for wall overlays and grips."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def discard_runtime_references(self):
        self.session.overlay_tracker_state.junction_node_trackers = []

    def sync_hovered_wall_overlay(self, *args, **kwargs):
        return sync_hovered_wall_overlay(self.session, *args, **kwargs)

    def clear_hovered_wall_overlay(self, *args, **kwargs):
        return clear_hovered_wall_overlay(self.session, *args, **kwargs)

    def sync_selected_wall_overlay(self, *args, **kwargs):
        return sync_selected_wall_overlay(self.session, *args, **kwargs)

    def clear_selected_wall_overlay(self, *args, **kwargs):
        return clear_selected_wall_overlay(self.session, *args, **kwargs)

    def apply_selected_wall_selection_feedback(self, *args, **kwargs):
        return apply_selected_wall_selection_feedback(self.session, *args, **kwargs)

    def get_plan_context_junctions(self, *args, **kwargs):
        return get_plan_context_junctions(self.session, *args, **kwargs)

    def create_junction_node_trackers(self, *args, **kwargs):
        return create_junction_node_trackers(self.session, *args, **kwargs)

    def sync_junction_node_overlays(self, *args, **kwargs):
        return sync_junction_node_overlays(self.session, *args, **kwargs)

    def clear_junction_node_overlays(self, *args, **kwargs):
        return clear_junction_node_overlays(self.session, *args, **kwargs)

    def sync_hovered_wall_opening_context_overlay(self, *args, **kwargs):
        return sync_hovered_wall_opening_context_overlay(self.session, *args, **kwargs)

    def clear_hovered_wall_opening_context_overlay(self, *args, **kwargs):
        return clear_hovered_wall_opening_context_overlay(self.session, *args, **kwargs)

    def create_wall_overlay_trackers(self, *args, **kwargs):
        return create_wall_overlay_trackers(self.session, *args, **kwargs)


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_event(session, name, **fields):
    return session.performance.plan_perf_trace_event(name, **fields)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _wall_tracker_state(session):
    return session.overlay_tracker_state


def sync_hovered_wall_overlay(session):
    clear_hovered_wall_overlay(session)
    if session.current_tool not in ("Select", "Join"):
        return
    if not session.hovered_wall or session.selection.state.is_selected_plan_target(
        "wall", session.hovered_wall
    ):
        return
    create_wall_overlay_trackers(
        session,
        session.hovered_wall,
        color=(0.42, 0.62, 0.9),
        width=session.viewport.scaled_line_width(2),
        tracker_store=_wall_tracker_state(session).wall_hover_trackers,
    )


def clear_hovered_wall_overlay(session):
    tracker_state = _wall_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.wall_hover_trackers)
    tracker_state.wall_hover_trackers = []


def sync_selected_wall_overlay(session):
    with _perf_trace_span(session, "sync_selected_wall_overlay"):
        wall = session.selection.state.get_selected_plan_target_object("wall")
        if (
            session.current_tool != "Select"
            or not session.selection.targets.is_plan_selectable_wall(wall)
        ):
            clear_selected_wall_overlay(session)
            return
        width = session.viewport.scaled_line_width(4)
        color = (0.12, 0.38, 0.95)
        segments = overlay_geometry.build_overlay_segments_from_polylines(
            overlay_geometry.get_wall_overlay_polylines(session, wall)
        )
        _perf_count(session, "selected_wall_overlay_segments", len(segments))
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_wall_overlay(session)
            return
        (
            _wall_tracker_state(session).wall_overlay_trackers,
            _wall_tracker_state(session).wall_hover_trackers,
            _,
        ) = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=_wall_tracker_state(session).wall_overlay_trackers,
            hover_trackers=_wall_tracker_state(session).wall_hover_trackers,
            segments=segments,
            label="selected-wall-overlay:{}".format(getattr(wall, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_wall_overlay(session),
            transfer_perf_key="selected_wall_overlay_tracker_transfers",
        )


def clear_selected_wall_overlay(session):
    tracker_state = _wall_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.wall_overlay_trackers)
    tracker_state.wall_overlay_trackers = []


def apply_selected_wall_selection_feedback(session):
    tracker_state = _wall_tracker_state(session)
    had_wall_visuals = bool(tracker_state.wall_overlay_trackers)
    wall = session.selection.state.get_selected_plan_target_object("wall")
    if session.current_tool == "Select" and session.selection.targets.is_plan_selectable_wall(wall):
        sync_selected_wall_overlay(session)
        session.viewport.request_view_redraw()
        return
    clear_selected_wall_overlay(session)
    if had_wall_visuals:
        session.viewport.request_view_redraw()


def get_plan_context_junctions(session):
    if session.current_tool not in ("Select", "Join"):
        return []

    import ArchWallRelation

    junctions = []
    seen = set()
    selected_wall = session.selection.state.get_selected_plan_target_object("wall")
    for wall in (selected_wall, session.hovered_wall):
        if not session.selection.targets.is_plan_selectable_wall(wall):
            continue
        for relation in ArchWallRelation.iter_wall_relations(wall):
            if not ArchWallRelation.is_wall_junction(relation):
                continue
            relation_name = getattr(relation, "Name", None)
            if not relation_name or relation_name in seen:
                continue
            seen.add(relation_name)
            if getattr(relation, "Status", "") not in ("OK", "Conflict"):
                continue
            junctions.append(relation)
    return junctions


def create_junction_node_trackers(session, junction, color, width, tracker_store):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    intersection = getattr(junction, "Intersection", None)
    if intersection is None:
        return
    units_per_pixel = session.viewport.get_plan_view_units_per_pixel() or 1.0
    half_size = max(units_per_pixel * 8.0, 20.0)
    center = FreeCAD.Vector(intersection)
    offsets = (
        (
            FreeCAD.Vector(-half_size, -half_size, 0),
            FreeCAD.Vector(half_size, half_size, 0),
        ),
        (
            FreeCAD.Vector(-half_size, half_size, 0),
            FreeCAD.Vector(half_size, -half_size, 0),
        ),
    )
    for start_offset, end_offset in offsets:
        tracker = overlay_manager.make_plan_line_tracker(
            DraftTrackers,
            "junction-node:{}".format(getattr(junction, "Name", "unknown")),
            scolor=color,
            swidth=width,
            ontop=True,
        )
        tracker.p1(center.add(start_offset))
        tracker.p2(center.add(end_offset))
        tracker.on()
        tracker_store.append(tracker)


def sync_junction_node_overlays(session):
    clear_junction_node_overlays(session)
    selected_wall = session.selection.state.get_selected_plan_target_object("wall")
    for junction in get_plan_context_junctions(session):
        if selected_wall and selected_wall in (getattr(junction, "Walls", None) or []):
            color = (0.92, 0.58, 0.12)
            width = session.viewport.scaled_line_width(2)
        else:
            color = (0.82, 0.70, 0.32)
            width = session.viewport.scaled_line_width(1)
        create_junction_node_trackers(
            session,
            junction,
            color=color,
            width=width,
            tracker_store=_wall_tracker_state(session).junction_node_trackers,
        )


def clear_junction_node_overlays(session):
    tracker_state = _wall_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.junction_node_trackers)
    tracker_state.junction_node_trackers = []


def sync_hovered_wall_opening_context_overlay(session):
    clear_hovered_wall_opening_context_overlay(session)
    if session.current_tool != "Select":
        return
    if not session.hovered_wall or session.selection.state.is_selected_plan_target(
        "wall", session.hovered_wall
    ):
        return
    selected_kind, _selected_obj = session.selection.state.get_selected_plan_target()
    if selected_kind in ("wall", "opening", "region", "space"):
        return
    color = (0.64, 0.70, 0.84)
    width = session.viewport.scaled_line_width(1)
    for opening in session.openings.get_wall_hosted_openings(session.hovered_wall):
        overlay_openings.create_opening_overlay_trackers(
            session,
            opening,
            color=color,
            width=width,
            tracker_store=_wall_tracker_state(session).hovered_wall_opening_context_trackers,
        )


def clear_hovered_wall_opening_context_overlay(session):
    tracker_state = _wall_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.hovered_wall_opening_context_trackers)
    tracker_state.hovered_wall_opening_context_trackers = []


def create_wall_overlay_trackers(session, wall, color, width, tracker_store):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for polyline in overlay_geometry.get_wall_overlay_polylines(session, wall):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = overlay_manager.make_plan_line_tracker(
                DraftTrackers,
                "wall-overlay:{}".format(getattr(wall, "Name", "unknown")),
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            tracker_store.append(tracker)
