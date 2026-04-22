# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider edit interaction helpers for BIM Plan Edit."""

from contextlib import nullcontext

import FreeCAD
import FreeCADGui
from bimplan.providers import PlanEditHandleSpec, PlanOverlayMarkerKind, PlanToolInteraction

translate = FreeCAD.Qt.translate


def get_selected_provider_edit_handles(session, provider_obj):
    if provider_obj is None:
        return []
    selected_provider = session._get_selected_plan_target_object("provider")
    editing_provider = getattr(session, "_edit_provider", None)
    if provider_obj != selected_provider and provider_obj != editing_provider:
        return []
    provider_target = session._get_plan_provider_target_for_object(provider_obj)
    if provider_target is None:
        return []
    provider_id = str(getattr(provider_target, "provider_id", "") or "").strip()
    target_key = str(getattr(provider_target, "key", "") or "").strip()
    handles = []
    for handle in tuple(session.get_plan_provider_edit_handles() or ()):
        if str(getattr(handle, "provider_id", "") or "").strip() != provider_id:
            continue
        handle_target_key = str(getattr(handle, "target_key", "") or "").strip()
        if handle_target_key and handle_target_key != target_key:
            continue
        handles.append(handle)
    if handles:
        return handles
    fallback = _make_builtin_provider_move_handle(session, provider_obj, provider_target)
    return [fallback] if fallback is not None else []


def can_move_provider_target_by_placement(session, provider_obj):
    if provider_obj is None or not session._is_plan_provider_target_object(provider_obj):
        return False
    if _has_provider_coordinate_properties(provider_obj):
        return True
    placement = getattr(provider_obj, "Placement", None)
    if placement is None:
        return False
    try:
        local_placement = session._copy_placement(placement)
        global_placement = session._get_plan_object_global_placement(provider_obj)
    except Exception:
        return False
    try:
        if local_placement.Base.sub(global_placement.Base).Length > 1e-6:
            return False
        local_axis = local_placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
        global_axis = global_placement.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
        if local_axis.sub(global_axis).Length > 1e-6:
            return False
    except Exception:
        return False
    return True


def activate_provider_handle(session, provider_obj, handle_index):
    try:
        from PySide import QtCore
    except ImportError:
        session._activate_provider_handle_now(provider_obj, handle_index)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda: session._activate_provider_handle_now(provider_obj, handle_index),
    )


def activate_provider_handle_now(session, provider_obj, handle_index):
    if session._tearing_down or provider_obj is None:
        return
    handles = session._get_selected_provider_edit_handles(provider_obj)
    if handle_index < 0 or handle_index >= len(handles):
        return
    handle = handles[handle_index]
    session._set_selected_plan_target("provider", provider_obj)
    session._set_gui_selection_object(provider_obj)
    session._clear_wall_grips()
    if handle.interaction == PlanToolInteraction.POINT:
        session._start_provider_handle_point_pick(provider_obj, handle_index, handle)
        return
    payload = _build_provider_handle_payload(
        session,
        provider_obj,
        handle,
        point=_get_handle_point_vector(handle),
        raw_point=_get_handle_point_vector(handle),
    )
    handled = False
    if str(getattr(handle, "action_key", "") or "").strip():
        handled = session.execute_plan_provider_action(
            str(getattr(handle, "provider_id", "") or ""),
            str(getattr(handle, "action_key", "") or ""),
            transaction_label=str(getattr(handle, "transaction_label", "") or ""),
            payload=payload,
        )
    if handled:
        session._queue_restore_selected_provider(provider_obj)
        return
    session._restore_selected_provider(provider_obj)


def start_provider_handle_point_pick(session, provider_obj, handle_index, handle):
    if provider_obj is None:
        return
    start_point = _get_handle_point_vector(handle)
    if start_point is None:
        return
    session.current_tool = "Move Provider"
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    session._set_hovered_space(None)
    session._set_hovered_region(None)
    session._sync_secondary_selected_overlays()
    session._edit_provider = provider_obj
    session._edit_provider_handle_index = handle_index
    session._edit_provider_handle = handle
    session._clear_selected_provider_overlay()
    session._clear_selected_provider_handles()
    session._refresh_task_panel_status()
    FreeCAD.activeDraftCommand = session
    session._set_draft_point_focus_suppressed(True)
    FreeCADGui.Snapper.getPoint(
        last=start_point,
        callback=session._finish_provider_handle_point_pick,
        movecallback=session._update_provider_handle_point_pick,
        title=_get_provider_handle_prompt(handle),
        noTracker=True,
    )
    session._queue_focus_plan_view()


def update_provider_handle_point_pick(session, point=None, snap_info=None):
    del point, snap_info


def finish_provider_handle_point_pick(session, point=None, obj=None):
    del obj
    provider_obj = session._edit_provider
    handle = session._edit_provider_handle
    session._edit_provider = None
    session._edit_provider_handle_index = None
    session._edit_provider_handle = None
    FreeCAD.activeDraftCommand = None

    if point is None or provider_obj is None:
        session.current_tool = "Select"
        session._restore_selected_provider(provider_obj)
        return

    if handle is None:
        session.current_tool = "Select"
        session._restore_selected_provider(provider_obj)
        return
    target_point = _resolve_provider_handle_target_point(session, provider_obj, point)
    if target_point is None:
        session.current_tool = "Select"
        session._restore_selected_provider(provider_obj)
        return

    action_key = str(getattr(handle, "action_key", "") or "").strip()
    provider_id = str(getattr(handle, "provider_id", "") or "").strip()
    session.current_tool = "Select"
    if action_key and provider_id:
        payload = _build_provider_handle_payload(
            session,
            provider_obj,
            handle,
            point=target_point,
            raw_point=point,
        )
        if session.execute_plan_provider_action(
            provider_id,
            action_key,
            transaction_label=str(getattr(handle, "transaction_label", "") or ""),
            payload=payload,
        ):
            session._queue_restore_selected_provider(provider_obj)
            return
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Plan Edit provider handle '{handle}' was not handled.\n",
            ).format(handle=str(getattr(handle, "key", "") or ""))
        )
        session._restore_selected_provider(provider_obj)
        return

    defer_updates = getattr(session, "defer_document_visual_updates", None)
    visual_update_context = defer_updates() if callable(defer_updates) else nullcontext()
    try:
        with visual_update_context:
            session.doc.openTransaction(
                str(getattr(handle, "transaction_label", "") or "")
                or translate("BIM_PlanEdit", "Move Provider")
            )
            if not _apply_provider_placement_move(session, provider_obj, target_point):
                raise RuntimeError("Unable to move provider target")
            session.doc.commitTransaction()
            session.doc.recompute()
    except Exception as exc:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        FreeCAD.Console.PrintError(
            translate(
                "BIM_PlanEdit",
                "Plan Edit could not move the selected integration target: {error}\n",
            ).format(error=exc)
        )
        session._restore_selected_provider(provider_obj)
        return

    session._queue_restore_selected_provider(provider_obj)


def cancel_provider_handle_point_pick(session):
    provider_obj = session._edit_provider
    session._edit_provider = None
    session._edit_provider_handle_index = None
    session._edit_provider_handle = None
    session._stop_snapper()
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if provider_obj is not None:
        session._restore_selected_provider(provider_obj)
        return
    session._set_gui_selection([])
    session._refresh_primary_selected_plan_target()


def restore_selected_provider(session, provider_obj):
    session.current_tool = "Select"
    if provider_obj is not None and session._is_plan_provider_target_object(provider_obj):
        session._set_gui_selection_object(provider_obj)
    else:
        session._set_gui_selection([])
    session._refresh_primary_selected_plan_target()


def queue_restore_selected_provider(session, provider_obj):
    try:
        from PySide import QtCore
    except ImportError:
        session._restore_selected_provider(provider_obj)
        return
    QtCore.QTimer.singleShot(0, lambda: session._restore_selected_provider(provider_obj))


def _make_builtin_provider_move_handle(session, provider_obj, provider_target):
    if not can_move_provider_target_by_placement(session, provider_obj):
        return None
    point = _get_provider_move_point(session, provider_obj)
    if point is None:
        return None
    return PlanEditHandleSpec(
        key="move",
        point=(point.x, point.y, point.z),
        label=translate("BIM_PlanEdit", "Move"),
        provider_id=str(getattr(provider_target, "provider_id", "") or "").strip(),
        target_key=str(getattr(provider_target, "key", "") or "").strip(),
        prompt=translate("BIM_PlanEdit", "Pick new integration position"),
        role="move",
        interaction=PlanToolInteraction.POINT,
        marker_kind=PlanOverlayMarkerKind.DIAMOND,
    )


def _get_provider_handle_prompt(handle):
    prompt = str(getattr(handle, "prompt", "") or "").strip()
    if prompt:
        return prompt
    role = str(getattr(handle, "role", "") or "").strip().lower()
    if role == "move":
        return translate("BIM_PlanEdit", "Pick new integration position")
    return translate("BIM_PlanEdit", "Pick integration target point")


def _get_handle_point_vector(handle):
    point = getattr(handle, "point", None)
    if point is None:
        return None
    if isinstance(point, FreeCAD.Vector):
        return FreeCAD.Vector(point)
    try:
        return FreeCAD.Vector(float(point[0]), float(point[1]), float(point[2]))
    except Exception:
        return None


def _get_provider_move_point(session, provider_obj):
    coordinate_point = _get_provider_coordinate_point(provider_obj)
    if coordinate_point is not None:
        return coordinate_point
    try:
        placement = session._get_plan_object_global_placement(provider_obj)
    except Exception:
        placement = getattr(provider_obj, "Placement", None)
    if placement is None:
        return None
    try:
        return FreeCAD.Vector(placement.Base)
    except Exception:
        return None


def _resolve_provider_handle_target_point(session, provider_obj, point):
    target_point = FreeCAD.Vector(point) if point is not None else None
    if target_point is None:
        return None
    start_point = _get_provider_move_point(session, provider_obj)
    if start_point is None:
        return target_point
    return FreeCAD.Vector(target_point.x, target_point.y, start_point.z)


def _build_provider_handle_payload(session, provider_obj, handle, *, point, raw_point):
    provider_target = session._get_plan_provider_target_for_object(provider_obj)
    return {
        "handle": handle,
        "handle_key": str(getattr(handle, "key", "") or "").strip(),
        "handle_role": str(getattr(handle, "role", "") or "").strip(),
        "point": FreeCAD.Vector(point) if point is not None else None,
        "placement_point": FreeCAD.Vector(point) if point is not None else None,
        "raw_point": FreeCAD.Vector(raw_point) if raw_point is not None else None,
        "target_object": provider_obj,
        "provider_target": provider_target,
        "target_key": str(getattr(provider_target, "key", "") or "").strip(),
        "target_provider_id": str(getattr(provider_target, "provider_id", "") or "").strip(),
        "selected_target": session._get_selected_plan_target(),
        "selected_targets": session._get_selected_plan_targets(),
    }


def _apply_provider_placement_move(session, provider_obj, point):
    if point is None:
        return False
    if _has_provider_coordinate_properties(provider_obj):
        provider_obj.X = float(point.x)
        provider_obj.Y = float(point.y)
        if hasattr(provider_obj, "Z"):
            provider_obj.Z = float(point.z)
        return True
    placement = session._copy_placement(getattr(provider_obj, "Placement", None))
    if placement is None:
        return False
    placement.Base = FreeCAD.Vector(float(point.x), float(point.y), float(placement.Base.z))
    provider_obj.Placement = placement
    return True


def _has_provider_coordinate_properties(provider_obj):
    return hasattr(provider_obj, "X") and hasattr(provider_obj, "Y")


def _get_provider_coordinate_point(provider_obj):
    if not _has_provider_coordinate_properties(provider_obj):
        return None
    try:
        x_value = float(getattr(provider_obj, "X"))
        y_value = float(getattr(provider_obj, "Y"))
        z_value = float(getattr(provider_obj, "Z", 0.0) or 0.0)
    except Exception:
        return None
    return FreeCAD.Vector(x_value, y_value, z_value)
