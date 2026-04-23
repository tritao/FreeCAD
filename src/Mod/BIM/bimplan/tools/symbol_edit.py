# SPDX-License-Identifier: LGPL-2.1-or-later

"""Symbol edit interaction helpers for BIM Plan Edit."""

import math

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate


class PlanSymbolsAPI:
    """Owned session surface for Plan Edit symbol read helpers."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def symbol_rotation_snap_enabled(self):
        return symbol_rotation_snap_enabled(self.session)

    def format_symbol_rotation_snap_label(self):
        return format_symbol_rotation_snap_label(self.session)


def get_symbol_handle_placement(session, symbol, handle_role, point):
    if not session._is_plan_symbol_instance(symbol) or point is None or not handle_role:
        return None
    start_placement = session._edit_symbol_start_placement
    if start_placement is None:
        start_placement = session._copy_placement(getattr(symbol, "Placement", None))
    point = session._resolve_symbol_handle_target_point(
        symbol, handle_role, point, placement=start_placement
    )
    if point is None:
        return None
    placement = session._copy_placement(start_placement)
    parent_global = session._get_symbol_parent_global_placement(symbol, placement=start_placement)
    anchor_global = session._get_symbol_anchor_point(symbol, placement=start_placement)
    local_anchor = session._get_symbol_local_anchor(symbol)
    if handle_role == "move":
        point_global = FreeCAD.Vector(point.x, point.y, anchor_global.z)
        try:
            anchor_parent = parent_global.inverse().multVec(point_global)
            placement.Base = anchor_parent.sub(placement.Rotation.multVec(local_anchor))
        except Exception:
            placement.Base = FreeCAD.Vector(
                point.x - local_anchor.x,
                point.y - local_anchor.y,
                start_placement.Base.z,
            )
        return placement
    if handle_role != "rotate":
        return None

    anchor = FreeCAD.Vector(anchor_global.x, anchor_global.y, anchor_global.z)
    reference_point = session._edit_symbol_reference_point
    if reference_point is None:
        specs = dict(
            (role, handle_point)
            for role, handle_point, _marker in session._get_selected_symbol_handle_specs(symbol)
        )
        reference_point = specs.get("rotate")
    if reference_point is None:
        return None

    reference_vector = FreeCAD.Vector(
        reference_point.x - anchor.x,
        reference_point.y - anchor.y,
        0,
    )
    new_vector = FreeCAD.Vector(point.x - anchor.x, point.y - anchor.y, 0)
    if reference_vector.Length < 0.001 or new_vector.Length < 0.001:
        return None

    reference_angle = math.atan2(reference_vector.y, reference_vector.x)
    target_angle = math.atan2(new_vector.y, new_vector.x)
    delta_rotation = FreeCAD.Rotation(
        FreeCAD.Vector(0, 0, 1), math.degrees(target_angle - reference_angle)
    )
    current_global = session._get_symbol_global_placement(symbol, placement=start_placement)
    try:
        global_rotation = delta_rotation.multiply(current_global.Rotation)
        placement.Rotation = parent_global.Rotation.inverse().multiply(global_rotation)
    except Exception:
        placement.Rotation = delta_rotation.multiply(start_placement.Rotation)
    try:
        anchor_parent = parent_global.inverse().multVec(anchor)
        placement.Base = anchor_parent.sub(placement.Rotation.multVec(local_anchor))
    except Exception:
        placement.Base = FreeCAD.Vector(
            anchor.x - local_anchor.x,
            anchor.y - local_anchor.y,
            start_placement.Base.z,
        )
    return placement


def activate_symbol_handle(session, symbol, handle_role):
    try:
        from PySide import QtCore
    except ImportError:
        session._activate_symbol_handle_now(symbol, handle_role)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda: session._activate_symbol_handle_now(symbol, handle_role),
    )


def activate_symbol_handle_now(session, symbol, handle_role):
    with session._plan_perf_trace_span("activate_symbol_handle_now"):
        if session._tearing_down or not session._is_plan_symbol_instance(symbol):
            return
        if handle_role not in {"move", "rotate"}:
            return
        with session._plan_perf_trace_span("activate_symbol_handle_set_target"):
            session._set_selected_plan_target("symbol", symbol)
            session._clear_wall_grips()
        with session._plan_perf_trace_span("activate_symbol_handle_start_point_pick"):
            session._start_symbol_handle_point_pick(symbol, handle_role)


def start_symbol_handle_point_pick(session, symbol, handle_role):
    with session._plan_perf_trace_span("start_symbol_handle_point_pick"):
        if not session._is_plan_symbol_instance(symbol):
            return
        with session._plan_perf_trace_span("start_symbol_handle_get_handles"):
            handle_points = {
                role: point
                for role, point, _marker in session._get_selected_symbol_handle_specs(symbol)
            }
            start_point = handle_points.get(handle_role)
        if start_point is None:
            return
        with session._plan_perf_trace_span("start_symbol_handle_state"):
            session.current_tool = "Move Symbol" if handle_role == "move" else "Rotate Symbol"
            session._set_hovered_wall(None)
            session._set_hovered_opening(None)
            session._set_hovered_symbol(None)
            session._sync_secondary_selected_overlays()
            session._edit_symbol = symbol
            session._edit_symbol_handle_role = handle_role
            session._edit_symbol_start_placement = session._copy_placement(
                getattr(symbol, "Placement", None)
            )
            session._edit_symbol_reference_point = FreeCAD.Vector(start_point)
            session._clear_selected_symbol_overlay()
            session._clear_selected_symbol_handles()
        with session._plan_perf_trace_span("start_symbol_handle_preview"):
            anchor = session._get_symbol_anchor_point(
                symbol, placement=session._edit_symbol_start_placement
            )
            session._sync_symbol_edit_preview(
                symbol,
                session._edit_symbol_start_placement,
                guide_start=anchor,
                guide_end=start_point,
            )
        session._refresh_task_panel_status(selection_only=True)
        FreeCAD.activeDraftCommand = session
        with session._plan_perf_trace_span("symbol_handle_focus_suppression"):
            session._set_draft_point_focus_suppressed(True)
        with session._plan_perf_trace_span("symbol_handle_snapper_get_point"):
            FreeCADGui.Snapper.getPoint(
                last=start_point,
                callback=session._finish_symbol_handle_point_pick,
                movecallback=session._update_symbol_handle_point_pick,
                title=(
                    translate("BIM_PlanEdit", "Pick new symbol position")
                    if handle_role == "move"
                    else translate("BIM_PlanEdit", "Pick new symbol rotation")
                ),
                noTracker=True,
            )
        with session._plan_perf_trace_span("symbol_handle_queue_focus_plan_view"):
            session.viewport.queue_focus_plan_view()


def update_symbol_handle_point_pick(session, point=None, snap_info=None):
    del snap_info
    symbol = session._edit_symbol
    handle_role = session._edit_symbol_handle_role
    if not symbol or not handle_role:
        session._clear_symbol_edit_preview()
        return
    target_point = session._resolve_symbol_handle_target_point(
        symbol, handle_role, point, placement=session._edit_symbol_start_placement
    )
    if target_point is None:
        session._clear_symbol_edit_preview()
        return
    placement = session._get_symbol_handle_placement(symbol, handle_role, point)
    if placement is None:
        session._clear_symbol_edit_preview()
        return
    guide_start = session._get_symbol_anchor_point(
        symbol, placement=session._edit_symbol_start_placement
    )
    guide_end = (
        session._get_symbol_anchor_point(symbol, placement=placement)
        if handle_role == "move"
        else target_point
    )
    session._sync_symbol_edit_preview(
        symbol, placement, guide_start=guide_start, guide_end=guide_end
    )


def finish_symbol_handle_point_pick(session, point=None, obj=None):
    del obj
    symbol = session._edit_symbol
    handle_role = session._edit_symbol_handle_role
    start_placement = session._edit_symbol_start_placement
    reference_point = session._edit_symbol_reference_point
    session._edit_symbol = None
    session._edit_symbol_handle_role = None
    session._edit_symbol_start_placement = None
    session._edit_symbol_reference_point = None
    FreeCAD.activeDraftCommand = None
    session._clear_symbol_edit_preview()

    if point is None or not symbol or not handle_role:
        session.current_tool = "Select"
        session._restore_selected_symbol(symbol)
        return

    session._edit_symbol_start_placement = start_placement
    session._edit_symbol_reference_point = reference_point
    placement = session._get_symbol_handle_placement(symbol, handle_role, point)
    session._edit_symbol_start_placement = None
    session._edit_symbol_reference_point = None
    if placement is None:
        session.current_tool = "Select"
        session._restore_selected_symbol(symbol)
        return

    try:
        session.doc.openTransaction(
            translate(
                "BIM_PlanEdit",
                "Move Symbol" if handle_role == "move" else "Rotate Symbol",
            )
        )
        symbol.Placement = placement
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        session.current_tool = "Select"
        session._restore_selected_symbol(symbol)
        return

    session.current_tool = "Select"
    session._queue_restore_selected_symbol(symbol)


def cancel_symbol_handle_point_pick(session):
    symbol = session._edit_symbol
    session._edit_symbol = None
    session._edit_symbol_handle_role = None
    session._edit_symbol_start_placement = None
    session._edit_symbol_reference_point = None
    session._stop_snapper()
    FreeCAD.activeDraftCommand = None
    session._clear_symbol_edit_preview()
    session.current_tool = "Select"
    if symbol:
        session._set_selected_plan_target("symbol", symbol, pending_restore=True)
    session._sync_selected_opening_overlay()
    session._sync_selected_opening_handles()
    session._sync_selected_symbol_overlay()
    session._sync_selected_symbol_handles()
    session._refresh_task_panel_status()


def restore_selected_symbol(session, symbol):
    session.current_tool = "Select"
    if symbol:
        session._set_selected_plan_target("symbol", symbol, pending_restore=True)
    else:
        session._set_selected_plan_target()
    if not symbol:
        session._sync_selected_opening_overlay()
        session._sync_selected_opening_handles()
        session._sync_selected_symbol_overlay()
        session._sync_selected_symbol_handles()
        session._refresh_task_panel_status()
        return
    session._set_gui_selection_object(symbol)
    session._sync_selected_opening_overlay()
    session._sync_selected_opening_handles()
    session._sync_selected_symbol_overlay()
    session._sync_selected_symbol_handles()
    session._refresh_task_panel_status()


def queue_restore_selected_symbol(session, symbol):
    try:
        from PySide import QtCore
    except ImportError:
        session._restore_selected_symbol(symbol)
        return
    QtCore.QTimer.singleShot(0, lambda: session._restore_selected_symbol(symbol))
