# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wall creation tools for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from bimplan.tools.hosted_openings import _PlanEditWallHost

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = 10.0


def activate_wall_tool(session):
    from bimcommands import BimWall

    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session._cancel_rect_wall_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)
    session.wall_edit.cancel_wall_edit()
    session.lifecycle.cancel_pending_edit()
    session._clear_plan_relation_status()
    session._set_selected_plan_target()
    session.overlays.clear_wall_grips()
    session.overlays.clear_selected_wall_overlay()
    session.overlays.clear_selected_wall_opening_context_overlay()
    session.overlays.clear_selected_space_overlay()
    session.overlays.clear_secondary_selected_overlays()
    session.selection.set_gui_selection([])
    session.lifecycle.start_embedded_tool(
        "Wall",
        BimWall.Arch_Wall(),
        host_class=_PlanEditWallHost,
    )


def activate_rect_wall_tool(session):
    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.providers.cancel_provider_point_tool(refresh=False)
    session.lifecycle.cancel_embedded_tool()
    session.wall_edit.cancel_wall_edit()
    session.lifecycle.cancel_pending_edit()
    session._clear_plan_relation_status()
    session._set_selected_plan_target()
    session.overlays.clear_wall_grips()
    session.overlays.clear_selected_wall_overlay()
    session.overlays.clear_selected_wall_opening_context_overlay()
    session.overlays.clear_selected_space_overlay()
    session.overlays.clear_secondary_selected_overlays()
    session._clear_rect_wall_preview()
    session._rect_wall_start = None
    session._rect_wall_params = get_wall_defaults(session)
    session.current_tool = "Rect Wall"
    FreeCAD.activeDraftCommand = session
    FreeCADGui.Snapper.getPoint(
        callback=session._handle_rect_wall_point,
        title=translate("BIM_PlanEdit", "First rectangle corner"),
    )
    session.task_panels.refresh_task_panel_status()


def get_wall_defaults(session):
    del session

    from draftutils import params

    return {
        "align": ["Center", "Left", "Right"][params.get_param_arch("WallAlignment")],
        "width": params.get_param_arch("WallWidth"),
        "height": params.get_param_arch("WallHeight"),
        "offset": params.get_param_arch("WallOffset"),
    }


def has_active_rect_wall_tool(session):
    return session._rect_wall_start is not None or session.current_tool == "Rect Wall"


def clear_rect_wall_preview(session):
    for tracker in session._rect_wall_preview_trackers:
        try:
            tracker.finalize()
        except Exception:
            pass
    session._rect_wall_preview_trackers = []


def cancel_rect_wall_tool(session, refresh=True):
    if not session._has_active_rect_wall_tool():
        return False
    session.lifecycle.stop_snapper()
    session._clear_rect_wall_preview()
    session._rect_wall_start = None
    session._rect_wall_params = None
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if refresh:
        session.task_panels.refresh_task_panel_status()
    session.overlays.sync_selected_opening_overlay()
    session.overlays.sync_selected_opening_handles()
    session.overlays.sync_selected_space_overlay()
    session.overlays.sync_selected_provider_overlay()
    session.overlays.sync_selected_provider_handles()
    return True


def get_rect_wall_corners(session, point):
    start = session._rect_wall_start
    if start is None or point is None:
        return None
    end = session.viewport.project_plan_point(point)
    if end is None:
        return None
    x1, y1 = start.x, start.y
    x2, y2 = end.x, end.y
    z = start.z
    if abs(x2 - x1) < _MIN_WALL_LENGTH or abs(y2 - y1) < _MIN_WALL_LENGTH:
        return None
    return [
        FreeCAD.Vector(x1, y1, z),
        FreeCAD.Vector(x2, y1, z),
        FreeCAD.Vector(x2, y2, z),
        FreeCAD.Vector(x1, y2, z),
    ]


def update_rect_wall_preview(session, point, info):
    del info
    corners = session._get_rect_wall_corners(point)
    if not corners:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return

    segments = list(zip(corners, corners[1:] + corners[:1]))
    if not session._rect_wall_preview_trackers:
        for start, end in segments:
            tracker = DraftTrackers.rectangleTracker(face=True)
            session._rect_wall_preview_trackers.append(tracker)
    for tracker, (start, end) in zip(session._rect_wall_preview_trackers, segments):
        footprint = session._get_preview_footprint(
            [start, end],
            width=session._rect_wall_params["width"],
            align=session._rect_wall_params["align"],
        )
        if not footprint:
            continue
        axis = end.sub(start)
        if axis.Length < _MIN_WALL_LENGTH:
            continue
        axis.normalize()
        rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), axis)
        perp = rotation.multVec(FreeCAD.Vector(0, 1, 0))
        tracker.setPlane(axis, perp)
        tracker.setorigin(footprint[0])
        tracker.update(footprint[2])
        tracker.on()


def create_rect_wall_run(session, corners):
    from bimcommands import BimWall

    walls = []
    session.doc.openTransaction(translate("BIM_PlanEdit", "Create Rectangular Wall Run"))
    try:
        walls = BimWall.create_wall_run_from_points(
            corners,
            width=session._rect_wall_params["width"],
            height=session._rect_wall_params["height"],
            align=session._rect_wall_params["align"],
            offset=session._rect_wall_params["offset"],
            closed=True,
            on_created=session._register_plan_object,
        )
        BimWall.autojoin_wall_run(walls, closed=True)
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        raise
    return walls


def handle_rect_wall_point(session, point=None, obj=None):
    del obj
    if point is None:
        session._cancel_rect_wall_tool()
        return

    point = session.viewport.project_plan_point(point)
    if session._rect_wall_start is None:
        session._rect_wall_start = point
        FreeCADGui.Snapper.getPoint(
            callback=session._handle_rect_wall_point,
            movecallback=session._update_rect_wall_preview,
            last=point,
            title=translate("BIM_PlanEdit", "Opposite rectangle corner"),
            mode="line",
        )
        return

    corners = session._get_rect_wall_corners(point)
    if not corners:
        session._cancel_rect_wall_tool()
        return

    try:
        walls = session._create_rect_wall_run(corners)
    except Exception:
        session._cancel_rect_wall_tool()
        FreeCAD.Console.PrintError(
            translate("BIM_PlanEdit", "Failed to create the rectangular wall run.\n")
        )
        return

    try:
        session.selection.set_gui_selection(walls)
    except Exception:
        pass

    session._cancel_rect_wall_tool(refresh=False)
    session.current_tool = "Select"
    session._refresh_primary_selected_plan_target()
    session.task_panels.refresh_task_panel_status()
