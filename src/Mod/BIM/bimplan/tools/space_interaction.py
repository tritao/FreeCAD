# SPDX-License-Identifier: LGPL-2.1-or-later

"""Interactive space editing tools for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from bimplan import selection as plan_selection
from bimplan.selection import target_dispatch as plan_target_dispatch
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.tools import space_boundaries as plan_space_boundaries
from bimplan.tools import space_editing as plan_space_editing

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = 10.0


def has_active_space_separator_tool(session):
    return session._space_separator_start is not None or session.current_tool == "Separator"


def has_active_plan_region_tool(session):
    return bool(session._plan_region_points) or session.current_tool == "Region"


def clear_plan_region_preview(session):
    session.overlays.finalize_trackers(session._plan_region_preview_trackers)
    session._plan_region_preview_trackers = []


def set_plan_region_tool_state(session, points=None, parent_space=None):
    session._plan_region_points = list(points or [])
    set_plan_region_parent_space(session, parent_space)


def get_plan_region_parent_space(session):
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        return getattr(state, "plan_region_parent_space", None)
    return getattr(session, "_plan_region_parent_space", None)


def set_plan_region_parent_space(session, parent_space):
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        state.plan_region_parent_space = parent_space
    else:
        session._plan_region_parent_space = parent_space


def reset_plan_region_tool_state(session, clear_preview=True):
    set_plan_region_tool_state(session)
    if clear_preview:
        clear_plan_region_preview(session)


def prepare_plan_region_tool_state(session, parent_space=None):
    reset_plan_region_tool_state(session)
    set_plan_region_parent_space(session, parent_space)


def _cancel_snap_tool(session, *, is_active, clear_preview, reset_state, sync_kinds, refresh=True):
    if not is_active():
        return False
    session.lifecycle.stop_snapper()
    clear_preview()
    reset_state()
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if refresh:
        session.task_panels.refresh_task_panel_status()
    plan_target_dispatch.sync_selected_target_visuals(
        session,
        kinds=sync_kinds,
        force=True,
    )
    return True


def cancel_plan_region_tool(session, refresh=True):
    return _cancel_snap_tool(
        session,
        is_active=lambda: has_active_plan_region_tool(session),
        clear_preview=lambda: clear_plan_region_preview(session),
        reset_state=lambda: reset_plan_region_tool_state(session, clear_preview=False),
        sync_kinds=plan_target_kinds.PLAN_REGION_CANCEL_VISUAL_KINDS,
        refresh=refresh,
    )


def get_plan_region_close_tolerance(session):
    units_per_pixel = session.viewport.get_plan_view_units_per_pixel()
    if units_per_pixel is None:
        return 120.0
    return max(120.0, float(units_per_pixel) * 12.0)


def get_plan_region_preview_segments(session, point=None):
    points = _get_plan_region_points(session)
    if point is not None:
        point = session.viewport.project_plan_point(point)
        if point is not None and (not points or point.distanceToPoint(points[-1]) > 0.000001):
            points.append(point)
    segments = []
    for start, end in zip(points, points[1:]):
        if start.distanceToPoint(end) <= 0.000001:
            continue
        segments.append((start, end, False))
    if len(points) >= 3 and points[-1].distanceToPoint(points[0]) > 0.000001:
        segments.append((points[-1], points[0], True))
    return segments


def _get_plan_region_points(session):
    return [FreeCAD.Vector(item) for item in (session._plan_region_points or [])]


def _request_next_plan_region_point(session, last_point, *, title):
    FreeCADGui.Snapper.getPoint(
        callback=lambda point=None, obj=None: handle_plan_region_point(session, point, obj),
        movecallback=lambda point=None, info=None: update_plan_region_preview(session, point, info),
        last=last_point,
        title=title,
        mode="line",
    )


def _coerce_next_plan_region_point(session, point):
    if point is None:
        return None
    return session.viewport.project_plan_point(point)


def _should_finalize_plan_region(session, point, points):
    return len(points) >= 3 and point.distanceToPoint(points[0]) <= get_plan_region_close_tolerance(
        session
    )


def _should_ignore_duplicate_plan_region_point(point, points):
    return bool(points) and point.distanceToPoint(points[-1]) <= 0.000001


def _append_plan_region_point(session, point):
    session._plan_region_points.append(point)
    update_plan_region_preview(session, None, None)
    _request_next_plan_region_point(
        session,
        point,
        title=translate("BIM_PlanEdit", "Next region point"),
    )


def update_plan_region_preview(session, point, info):
    del info
    segments = get_plan_region_preview_segments(session, point)
    clear_plan_region_preview(session)
    if not segments:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return

    color = (0.86, 0.48, 0.12)
    width = session.viewport.scaled_line_width(2)
    for index, (start, end, dotted) in enumerate(segments):
        tracker = session.overlays.make_plan_line_tracker(
            DraftTrackers,
            "plan_region_preview:{}".format(index),
            dotted=dotted,
            scolor=color,
            swidth=width,
            ontop=True,
        )
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()
        session._plan_region_preview_trackers.append(tracker)


def create_plan_region(session, points):
    import Arch

    region = None
    session.doc.openTransaction(translate("BIM_PlanEdit", "Create Plan Region"))
    try:
        region = Arch.makePlanRegion(
            points=points,
            parent_space=get_plan_region_parent_space(session),
        )
        if not region:
            raise RuntimeError("Unable to create plan region")
        session.visibility.add_object_to_active_storey(region)
        session.doc.recompute()
        if not session.overlays.get_region_footprint_faces(region):
            raise RuntimeError("Plan region has no valid footprint")
        session.doc.commitTransaction()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        raise
    return region


def finalize_plan_region(session):
    points = _get_plan_region_points(session)
    if len(points) < 3:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Place at least three points before finishing the region.\n",
            )
        )
        return False
    try:
        region = create_plan_region(session, points)
    except Exception:
        FreeCAD.Console.PrintError(translate("BIM_PlanEdit", "Failed to create the plan region.\n"))
        return False

    session.visibility.register_plan_object(region)
    cancel_plan_region_tool(session, refresh=False)
    plan_space_editing.restore_selected_region(session, region)
    return True


def handle_plan_region_point(session, point=None, obj=None):
    del obj
    if point is None:
        cancel_plan_region_tool(session)
        return

    point = _coerce_next_plan_region_point(session, point)
    if point is None:
        cancel_plan_region_tool(session)
        return

    points = _get_plan_region_points(session)
    if points:
        if _should_ignore_duplicate_plan_region_point(point, points):
            _request_next_plan_region_point(
                session,
                points[-1],
                title=translate("BIM_PlanEdit", "Next region point"),
            )
            return
        if _should_finalize_plan_region(session, point, points):
            finalize_plan_region(session)
            return

    _append_plan_region_point(session, point)


def clear_space_separator_preview(session):
    session.overlays.finalize_trackers(session._space_separator_preview_trackers)
    session._space_separator_preview_trackers = []


def set_space_separator_tool_state(session, start=None, height=None):
    session._space_separator_start = start
    session._space_separator_height = height


def reset_space_separator_tool_state(session, clear_preview=True):
    set_space_separator_tool_state(session)
    if clear_preview:
        clear_space_separator_preview(session)


def prepare_space_separator_tool_state(session, height=None):
    reset_space_separator_tool_state(session)
    session._space_separator_height = height


def cancel_space_separator_tool(session, refresh=True):
    return _cancel_snap_tool(
        session,
        is_active=lambda: has_active_space_separator_tool(session),
        clear_preview=lambda: clear_space_separator_preview(session),
        reset_state=lambda: reset_space_separator_tool_state(session, clear_preview=False),
        sync_kinds=plan_target_kinds.SPACE_SEPARATOR_CANCEL_VISUAL_KINDS,
        refresh=refresh,
    )


def update_space_separator_preview(session, point, info):
    del info
    start = _get_space_separator_start(session)
    end = _coerce_space_separator_point(session, point)
    if start is None or end is None or not _is_valid_space_separator_length(start, end):
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return

    tracker = _get_or_create_space_separator_preview_tracker(session, DraftTrackers)
    tracker.p1(start)
    tracker.p2(end)
    tracker.on()


def _get_space_separator_start(session):
    return getattr(session, "_space_separator_start", None)


def _coerce_space_separator_point(session, point):
    if point is None:
        return None
    return session.viewport.project_plan_point(point)


def _is_valid_space_separator_length(start, end):
    return end.sub(start).Length >= _MIN_WALL_LENGTH


def _get_or_create_space_separator_preview_tracker(session, DraftTrackers):
    if not session._space_separator_preview_trackers:
        tracker = session.overlays.make_plan_line_tracker(
            DraftTrackers,
            "space_separator_preview",
            dotted=True,
            ontop=True,
        )
        session._space_separator_preview_trackers.append(tracker)
    return session._space_separator_preview_trackers[0]


def _request_space_separator_end_point(session, start):
    FreeCADGui.Snapper.getPoint(
        callback=lambda point=None, obj=None: handle_space_separator_point(session, point, obj),
        movecallback=lambda point=None, info=None: update_space_separator_preview(
            session, point, info
        ),
        last=start,
        title=translate("BIM_PlanEdit", "Separator end point"),
        mode="line",
    )


def _finish_space_separator(session, separator):
    session.visibility.register_plan_object(separator)
    cancel_space_separator_tool(session, refresh=False)
    session.current_tool = "Select"
    session.selection.refresh_primary_selected_plan_target()
    session.task_panels.refresh_task_panel_status()


def create_space_separator(session, start, end):
    import Arch

    separator = None
    session.doc.openTransaction(translate("BIM_PlanEdit", "Create Space Separator"))
    try:
        separator = Arch.makeSpaceSeparator(
            start=start,
            end=end,
            height=session._space_separator_height,
        )
        if not separator:
            raise RuntimeError("Unable to create space separator")
        session.visibility.add_object_to_active_storey(separator)
        session.doc.recompute()
        session.doc.commitTransaction()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        raise
    return separator


def handle_space_separator_point(session, point=None, obj=None):
    del obj
    if point is None:
        cancel_space_separator_tool(session)
        return

    point = _coerce_space_separator_point(session, point)
    if point is None:
        cancel_space_separator_tool(session)
        return

    start = _get_space_separator_start(session)
    if start is None:
        session._space_separator_start = point
        _request_space_separator_end_point(session, point)
        return

    if not _is_valid_space_separator_length(start, point):
        cancel_space_separator_tool(session)
        return

    try:
        separator = create_space_separator(session, start, point)
    except Exception:
        cancel_space_separator_tool(session)
        FreeCAD.Console.PrintError(
            translate("BIM_PlanEdit", "Failed to create the space separator.\n")
        )
        return

    _finish_space_separator(session, separator)


def set_space_text_pick_state(session, space=None):
    session._edit_space = space


def reset_space_text_pick_state(session):
    set_space_text_pick_state(session)


def start_space_text_position_pick(session):
    space = _get_selected_space_text_target(session)
    if not session.selection.is_plan_space_object(space):
        return False

    _begin_space_text_position_pick(session, space)
    FreeCADGui.Snapper.getPoint(
        callback=lambda point=None, obj=None: finish_space_text_position_pick(session, point, obj),
        last=plan_space_boundaries.get_space_reference_point(session, space),
        title=translate("BIM_PlanEdit", "Pick space text position"),
        noTracker=True,
    )
    session.viewport.queue_focus_plan_view()
    return True


def _get_selected_space_text_target(session):
    return plan_selection.get_selected_plan_target_object(session, "space")


def _begin_space_text_position_pick(session, space):
    session.current_tool = "Set Space Text"
    set_space_text_pick_state(session, space)
    session.selection.clear_hovered_plan_targets(
        kinds=plan_target_kinds.SPACE_EDIT_CLEAR_HOVERED_KINDS
    )
    session.overlays.sync_secondary_selected_overlays()
    session.task_panels.refresh_task_panel_status()
    FreeCAD.activeDraftCommand = session
    session.lifecycle.set_draft_point_focus_suppressed(True)


def _end_space_text_position_pick(session):
    reset_space_text_pick_state(session)
    FreeCAD.activeDraftCommand = None
    session.lifecycle.set_draft_point_focus_suppressed(False)


def _apply_space_text_position(session, space, point):
    point = session.viewport.project_plan_point(point)
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Set Space Text Position"))
        space.ViewObject.TextPosition = space.Placement.inverse().multVec(point)
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    return True


def finish_space_text_position_pick(session, point=None, obj=None):
    del obj
    space = session._edit_space
    _end_space_text_position_pick(session)

    if point is None or not session.selection.is_plan_space_object(space):
        session.current_tool = "Select"
        session.task_panels.refresh_task_panel_status()
        return

    if not _apply_space_text_position(session, space, point):
        plan_space_editing.restore_selected_space(session, space)
        return

    session.current_tool = "Select"
    plan_space_editing.queue_restore_selected_space(session, space)


def cancel_space_text_position_pick(session):
    space = session._edit_space or _get_selected_space_text_target(session)
    _end_space_text_position_pick(session)
    session.lifecycle.stop_snapper()
    session.current_tool = "Select"
    if space:
        session.selection.set_selected_plan_target("space", space, pending_restore=True)
    session.overlays.sync_selected_space_overlay()
    session.task_panels.refresh_task_panel_status()
