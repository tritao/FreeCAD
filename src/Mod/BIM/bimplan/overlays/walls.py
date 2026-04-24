# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall overlay and grip tracker helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from . import manager as overlay_manager
from .. import selection as plan_selection


def retarget_edit_tracker(tracker, obj, index):
    selnode = getattr(tracker, "selnode", None)
    if selnode is None:
        return
    doc_name = getattr(getattr(obj, "Document", None), "Name", None)
    obj_name = getattr(obj, "Name", None)
    try:
        if hasattr(selnode, "useNewSelection"):
            selnode.useNewSelection = False
        if doc_name and hasattr(selnode, "documentName"):
            selnode.documentName.setValue(doc_name)
        if obj_name and hasattr(selnode, "objectName"):
            selnode.objectName.setValue(obj_name)
        if hasattr(selnode, "subElementName"):
            selnode.subElementName.setValue(f"EditNode{index}")
    except Exception:
        pass


def sync_wall_grips(session):
    with session._plan_perf_trace_span("sync_wall_grips"):
        session._wall_grip_sync_queued = False
        session._wall_grip_sync_generation += 1
        if not session.is_selected_wall_endpoint_editable():
            session.overlays.clear_wall_grips()
            return

        with session._plan_perf_trace_span("wall_grips_import_trackers"):
            try:
                import draftguitools.gui_trackers as DraftTrackers
                from draftutils import params
            except Exception:
                session.overlays.clear_wall_grips()
                return

        wall = plan_selection.get_selected_plan_target_object(session, "wall")
        proxy = getattr(wall, "Proxy", None)
        if not proxy or not hasattr(proxy, "calc_endpoints"):
            session.overlays.clear_wall_grips()
            return

        with session._plan_perf_trace_span("wall_grips_calc_endpoints"):
            endpoints = proxy.calc_endpoints(wall)
        if len(endpoints) != 2:
            session.overlays.clear_wall_grips()
            return

        with session._plan_perf_trace_span("wall_grips_calc_positions"):
            if hasattr(proxy, "calc_edit_grip_positions"):
                grip_positions = proxy.calc_edit_grip_positions(wall)
            else:
                grip_positions = endpoints + [(endpoints[0] + endpoints[1]) * 0.5]
        if len(grip_positions) != 3:
            session.overlays.clear_wall_grips()
            return

        with session._plan_perf_trace_span("wall_grips_marker_lookup"):
            marker_size = session.viewport.scaled_marker_size(params.get_param_view("MarkerSize"))
            midpoint_marker = FreeCADGui.getMarkerIndex("DIAMOND_FILLED", marker_size)
        wall_state = (
            marker_size,
            midpoint_marker,
            getattr(getattr(wall, "Document", None), "Name", None),
            getattr(wall, "Name", None),
            tuple(
                (float(position.x), float(position.y), float(position.z))
                for position in grip_positions
            ),
        )
        previous_state = session._wall_grip_state
        reuse_allowed = (
            len(session._grip_trackers) == 3
            and previous_state is not None
            and previous_state[:2] == wall_state[:2]
        )
        if reuse_allowed:
            try:
                with session._plan_perf_trace_span("wall_grips_retarget_trackers"):
                    for index, tracker in enumerate(session._grip_trackers):
                        session._retarget_edit_tracker(tracker, wall, index)
                with session._plan_perf_trace_span("wall_grips_position_trackers"):
                    for tracker, position in zip(session._grip_trackers, grip_positions):
                        tracker.set(position)
                with session._plan_perf_trace_span("wall_grips_show_trackers"):
                    for tracker in session._grip_trackers:
                        if not getattr(tracker, "Visible", False):
                            tracker.on()
                if previous_state == wall_state:
                    session._plan_perf_count("wall_grip_cache_hits")
                else:
                    session._plan_perf_count("wall_grip_tracker_reuses")
                session._wall_grip_state = wall_state
                return
            except Exception:
                session.overlays.clear_wall_grips()

        grip_start, grip_end, midpoint = grip_positions
        with session._plan_perf_trace_span("wall_grips_create_trackers"):
            session._grip_trackers = [
                DraftTrackers.editTracker(pos=grip_start, name=wall.Name, idx=0),
                DraftTrackers.editTracker(pos=grip_end, name=wall.Name, idx=1),
                DraftTrackers.editTracker(
                    pos=midpoint,
                    name=wall.Name,
                    idx=2,
                    marker=midpoint_marker,
                ),
            ]
        session._wall_grip_state = wall_state


def hide_wall_grips(session):
    for tracker in session._grip_trackers:
        try:
            tracker.off()
        except Exception:
            pass


def schedule_wall_grip_sync(session, delay_ms=120):
    if session._tearing_down:
        return
    hide_wall_grips(session)
    session._wall_grip_sync_queued = True
    session._wall_grip_sync_generation += 1
    generation = session._wall_grip_sync_generation
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(
            delay_ms,
            lambda generation=generation: session._run_scheduled_wall_grip_sync(generation),
        )
    except Exception:
        session._run_scheduled_wall_grip_sync(generation)


def run_scheduled_wall_grip_sync(session, generation=None):
    if not session._wall_grip_sync_queued:
        return
    if generation is not None and generation != session._wall_grip_sync_generation:
        return
    session._wall_grip_sync_queued = False
    with session._plan_perf_trace_event("scheduled_wall_grip_sync"):
        if session._tearing_down:
            return
        sync_wall_grips(session)
        session.viewport.request_view_redraw()


def clear_wall_grips(session):
    session._wall_grip_sync_queued = False
    session._wall_grip_sync_generation += 1
    session.overlays.finalize_trackers(session._grip_trackers)
    session._grip_trackers = []
    session._wall_grip_state = None


def sync_hovered_wall_overlay(session):
    clear_hovered_wall_overlay(session)
    if session.current_tool not in ("Select", "Join"):
        return
    if not session.hovered_wall or session._is_selected_plan_target("wall", session.hovered_wall):
        return
    create_wall_overlay_trackers(
        session,
        session.hovered_wall,
        color=(0.42, 0.62, 0.9),
        width=session.viewport.scaled_line_width(2),
        tracker_store=session._wall_hover_trackers,
    )


def clear_hovered_wall_overlay(session):
    session.overlays.finalize_trackers(session._wall_hover_trackers)
    session._wall_hover_trackers = []


def sync_selected_wall_overlay(session):
    with session._plan_perf_trace_span("sync_selected_wall_overlay"):
        wall = plan_selection.get_selected_plan_target_object(session, "wall")
        if session.current_tool != "Select" or not session._is_plan_selectable_wall(wall):
            clear_selected_wall_overlay(session)
            return
        width = session.viewport.scaled_line_width(4)
        color = (0.12, 0.38, 0.95)
        segments = session._build_overlay_segments_from_polylines(
            session._get_wall_overlay_polylines(wall)
        )
        session._plan_perf_count("selected_wall_overlay_segments", len(segments))
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_wall_overlay(session)
            return
        (
            session._wall_overlay_trackers,
            session._wall_hover_trackers,
            _,
        ) = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=session._wall_overlay_trackers,
            hover_trackers=session._wall_hover_trackers,
            segments=segments,
            label="selected-wall-overlay:{}".format(getattr(wall, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_wall_overlay(session),
            transfer_perf_key="selected_wall_overlay_tracker_transfers",
        )


def clear_selected_wall_overlay(session):
    session.overlays.finalize_trackers(session._wall_overlay_trackers)
    session._wall_overlay_trackers = []


def get_plan_context_junctions(session):
    if session.current_tool not in ("Select", "Join"):
        return []

    import ArchWallJoinUtils

    junctions = []
    seen = set()
    selected_wall = plan_selection.get_selected_plan_target_object(session, "wall")
    for wall in (selected_wall, session.hovered_wall):
        if not session._is_plan_selectable_wall(wall):
            continue
        for relation in ArchWallJoinUtils.iter_wall_relations(wall):
            if not ArchWallJoinUtils.is_wall_junction(relation):
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
        tracker = session.overlays.make_plan_line_tracker(
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
    selected_wall = plan_selection.get_selected_plan_target_object(session, "wall")
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
            tracker_store=session._junction_node_trackers,
        )


def clear_junction_node_overlays(session):
    session.overlays.finalize_trackers(session._junction_node_trackers)
    session._junction_node_trackers = []


def sync_hovered_wall_opening_context_overlay(session):
    clear_hovered_wall_opening_context_overlay(session)
    if session.current_tool != "Select":
        return
    if not session.hovered_wall or session._is_selected_plan_target("wall", session.hovered_wall):
        return
    selected_kind, _selected_obj = session.selection.get_selected_plan_target()
    if selected_kind in ("wall", "opening", "region", "space"):
        return
    color = (0.64, 0.70, 0.84)
    width = session.viewport.scaled_line_width(1)
    for opening in session._get_wall_hosted_openings(session.hovered_wall):
        session.overlays.create_opening_overlay_trackers(
            opening,
            color=color,
            width=width,
            tracker_store=session._hovered_wall_opening_context_trackers,
        )


def clear_hovered_wall_opening_context_overlay(session):
    session.overlays.finalize_trackers(session._hovered_wall_opening_context_trackers)
    session._hovered_wall_opening_context_trackers = []


def create_wall_overlay_trackers(session, wall, color, width, tracker_store):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    for polyline in session._get_wall_overlay_polylines(wall):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = session.overlays.make_plan_line_tracker(
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
