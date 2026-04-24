# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider edit interaction helpers for BIM Plan Edit."""

from contextlib import nullcontext

import FreeCAD
import FreeCADGui
from bimplan.providers import PlanEditHandleSpec, PlanOverlayMarkerKind, PlanToolInteraction
from bimplan import selection as plan_selection

translate = FreeCAD.Qt.translate


def get_selected_provider_edit_handles(session, provider_obj):
    if provider_obj is None:
        return []
    selected_provider = plan_selection.get_selected_plan_target_object(session, "provider")
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
    return _get_builtin_provider_edit_handles(session, provider_obj, provider_target)


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


def can_rehost_provider_target(session, provider_obj, host_obj=None):
    if provider_obj is None or not session._is_plan_provider_target_object(provider_obj):
        return False
    try:
        import Arch
    except Exception:
        return False
    try:
        return bool(Arch.canRehostObject(provider_obj, host_obj))
    except Exception:
        return False


def activate_provider_handle(session, provider_obj, handle_index):
    try:
        from PySide import QtCore
    except ImportError:
        session.providers.activate_provider_handle_now(provider_obj, handle_index)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda: session.providers.activate_provider_handle_now(provider_obj, handle_index),
    )


def activate_provider_handle_now(session, provider_obj, handle_index):
    if session._tearing_down or provider_obj is None:
        return
    handles = session.providers.get_selected_provider_edit_handles(provider_obj)
    if handle_index < 0 or handle_index >= len(handles):
        return
    handle = handles[handle_index]
    session._set_selected_plan_target("provider", provider_obj)
    session._set_gui_selection_object(provider_obj)
    session.overlays.clear_wall_grips()
    if handle.interaction == PlanToolInteraction.POINT:
        session.providers.start_provider_handle_point_pick(provider_obj, handle_index, handle)
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
        session.providers.queue_restore_selected_provider(provider_obj)
        return
    session.providers.restore_selected_provider(provider_obj)


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
    session.overlays.sync_secondary_selected_overlays()
    session._edit_provider = provider_obj
    session._edit_provider_handle_index = handle_index
    session._edit_provider_handle = handle
    session.overlays.clear_selected_provider_overlay()
    session.overlays.clear_selected_provider_handles()
    session._refresh_task_panel_status()
    FreeCAD.activeDraftCommand = session
    session._set_draft_point_focus_suppressed(True)
    FreeCADGui.Snapper.getPoint(
        last=start_point,
        callback=session.providers.finish_provider_handle_point_pick,
        movecallback=session.providers.update_provider_handle_point_pick,
        title=_get_provider_handle_prompt(handle),
        noTracker=True,
    )
    session.viewport.queue_focus_plan_view()


def update_provider_handle_point_pick(session, point=None, snap_info=None):
    del point, snap_info


def finish_provider_handle_point_pick(session, point=None, obj=None):
    provider_obj = session._edit_provider
    handle = session._edit_provider_handle
    session._edit_provider = None
    session._edit_provider_handle_index = None
    session._edit_provider_handle = None
    FreeCAD.activeDraftCommand = None

    if point is None or provider_obj is None:
        session.current_tool = "Select"
        session.providers.restore_selected_provider(provider_obj)
        return

    if handle is None:
        session.current_tool = "Select"
        session.providers.restore_selected_provider(provider_obj)
        return
    target_point = _resolve_provider_handle_target_point(session, provider_obj, point)
    if target_point is None:
        session.current_tool = "Select"
        session.providers.restore_selected_provider(provider_obj)
        return

    action_key = str(getattr(handle, "action_key", "") or "").strip()
    provider_id = str(getattr(handle, "provider_id", "") or "").strip()
    session.current_tool = "Select"
    payload = _build_provider_handle_payload(
        session,
        provider_obj,
        handle,
        point=target_point,
        raw_point=point,
        snap_object=obj,
    )
    if action_key and provider_id:
        if session.execute_plan_provider_action(
            provider_id,
            action_key,
            transaction_label=str(getattr(handle, "transaction_label", "") or ""),
            payload=payload,
        ):
            session.providers.queue_restore_selected_provider(provider_obj)
            return
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Plan Edit provider handle '{handle}' was not handled.\n",
            ).format(handle=str(getattr(handle, "key", "") or ""))
        )
        session.providers.restore_selected_provider(provider_obj)
        return

    defer_updates = getattr(session, "defer_document_visual_updates", None)
    visual_update_context = defer_updates() if callable(defer_updates) else nullcontext()
    try:
        with visual_update_context:
            session.doc.openTransaction(_get_provider_handle_transaction_label(handle))
            if not _apply_builtin_provider_handle_action(
                session,
                provider_obj,
                handle,
                payload,
            ):
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
        session.providers.restore_selected_provider(provider_obj)
        return

    session.providers.queue_restore_selected_provider(provider_obj)


def cancel_provider_handle_point_pick(session):
    provider_obj = session._edit_provider
    session._edit_provider = None
    session._edit_provider_handle_index = None
    session._edit_provider_handle = None
    session._stop_snapper()
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if provider_obj is not None:
        session.providers.restore_selected_provider(provider_obj)
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
        session.providers.restore_selected_provider(provider_obj)
        return
    QtCore.QTimer.singleShot(0, lambda: session.providers.restore_selected_provider(provider_obj))


def _get_builtin_provider_edit_handles(session, provider_obj, provider_target):
    handles = []
    move_handle = _make_builtin_provider_move_handle(session, provider_obj, provider_target)
    if move_handle is not None:
        handles.append(move_handle)
    rehost_handle = _make_builtin_provider_rehost_handle(session, provider_obj, provider_target)
    if rehost_handle is not None:
        handles.append(rehost_handle)
    return handles


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


def _make_builtin_provider_rehost_handle(session, provider_obj, provider_target):
    if not can_rehost_provider_target(session, provider_obj):
        return None
    point = _get_provider_rehost_point(session, provider_obj)
    if point is None:
        return None
    return PlanEditHandleSpec(
        key="rehost",
        point=(point.x, point.y, point.z),
        label=translate("BIM_PlanEdit", "Rehost"),
        provider_id=str(getattr(provider_target, "provider_id", "") or "").strip(),
        target_key=str(getattr(provider_target, "key", "") or "").strip(),
        prompt=translate("BIM_PlanEdit", "Pick new host wall"),
        transaction_label=translate("BIM_PlanEdit", "Rehost Provider"),
        role="rehost",
        interaction=PlanToolInteraction.POINT,
        marker_kind=PlanOverlayMarkerKind.SQUARE,
    )


def _get_provider_handle_transaction_label(handle):
    transaction_label = str(getattr(handle, "transaction_label", "") or "").strip()
    if transaction_label:
        return transaction_label
    role = _get_provider_handle_role(handle)
    if role == "rehost":
        return translate("BIM_PlanEdit", "Rehost Provider")
    return translate("BIM_PlanEdit", "Move Provider")


def _get_provider_handle_prompt(handle):
    prompt = str(getattr(handle, "prompt", "") or "").strip()
    if prompt:
        return prompt
    role = _get_provider_handle_role(handle)
    if role == "move":
        return translate("BIM_PlanEdit", "Pick new integration position")
    if role == "rehost":
        return translate("BIM_PlanEdit", "Pick new host wall")
    return translate("BIM_PlanEdit", "Pick integration target point")


def _get_provider_handle_role(handle):
    return str(getattr(handle, "role", "") or "").strip().lower()


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


def _get_provider_rehost_point(session, provider_obj):
    point = _get_provider_move_point(session, provider_obj)
    if point is None:
        return None
    offset = 150.0
    if session.viewport is not None:
        try:
            units_per_pixel = float(session.viewport.get_plan_view_units_per_pixel() or 0.0)
        except Exception:
            units_per_pixel = 0.0
        if units_per_pixel > 0.0:
            offset = max(75.0, units_per_pixel * 16.0)
    return FreeCAD.Vector(point.x, point.y + offset, point.z)


def _resolve_provider_handle_target_point(session, provider_obj, point):
    target_point = FreeCAD.Vector(point) if point is not None else None
    if target_point is None:
        return None
    start_point = _get_provider_move_point(session, provider_obj)
    if start_point is None:
        return target_point
    return FreeCAD.Vector(target_point.x, target_point.y, start_point.z)


def _build_provider_handle_payload(
    session, provider_obj, handle, *, point, raw_point, snap_object=None
):
    provider_target = session._get_plan_provider_target_for_object(provider_obj)
    get_snap_info = getattr(session.providers, "get_provider_point_snap_info", None)
    snap_info = get_snap_info() if callable(get_snap_info) else {}
    if not isinstance(snap_info, dict):
        snap_info = {}
    resolve_snap_object = getattr(session.providers, "resolve_provider_point_snap_object", None)
    if callable(resolve_snap_object):
        try:
            snap_object = resolve_snap_object(snap_object, snap_info)
        except Exception:
            pass
    snap_target = (None, None)
    get_plan_target = getattr(session, "_get_plan_target_for_object", None)
    if callable(get_plan_target) and snap_object is not None:
        try:
            snap_target = get_plan_target(snap_object)
        except Exception:
            snap_target = (None, None)
    snap_component = str(snap_info.get("Component", "") or "").strip()
    snap_subname = str(snap_info.get("SubName", "") or snap_component).strip()
    snap_document_name = str(snap_info.get("Document", "") or "").strip()
    if not snap_document_name and snap_object is not None:
        snap_document_name = str(getattr(getattr(snap_object, "Document", None), "Name", "") or "")
    snap_object_name = str(snap_info.get("Object", "") or "").strip()
    if not snap_object_name and snap_object is not None:
        snap_object_name = str(getattr(snap_object, "Name", "") or "")
    selected_target = session.selection.get_selected_plan_target()
    selected_targets = session.selection.get_selected_plan_targets()
    hovered_target = session._get_hovered_plan_target()
    host_kind, host_obj, host_source = _get_provider_handle_payload_host_target(
        session,
        handle,
        snap_target=snap_target,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
    )
    placement_point = (
        session.providers.project_provider_point_to_host(point, host_obj)
        if host_kind == "wall" and point is not None
        else None
    )
    if placement_point is None and point is not None:
        placement_point = FreeCAD.Vector(point)
    return {
        "handle": handle,
        "handle_key": str(getattr(handle, "key", "") or "").strip(),
        "handle_role": str(getattr(handle, "role", "") or "").strip(),
        "point": FreeCAD.Vector(point) if point is not None else None,
        "placement_point": placement_point,
        "raw_point": FreeCAD.Vector(raw_point) if raw_point is not None else None,
        "snap_info": snap_info,
        "snap_object": snap_object,
        "snap_target": snap_target,
        "snap_document_name": snap_document_name,
        "snap_object_name": snap_object_name,
        "snap_component": snap_component,
        "snap_subname": snap_subname,
        "target_object": provider_obj,
        "provider_target": provider_target,
        "target_key": str(getattr(provider_target, "key", "") or "").strip(),
        "target_provider_id": str(getattr(provider_target, "provider_id", "") or "").strip(),
        "selected_target": selected_target,
        "selected_targets": selected_targets,
        "hovered_target": hovered_target,
        "host_target": (host_kind, host_obj),
        "host_source": host_source,
    }


def _get_provider_handle_payload_host_target(
    session,
    handle,
    *,
    snap_target,
    selected_target,
    selected_targets,
    hovered_target,
):
    role = _get_provider_handle_role(handle)
    normalize_host_target = getattr(session.providers, "normalize_provider_point_host_target", None)
    if not callable(normalize_host_target):
        return (None, None, "")
    if role == "rehost":
        snap_kind, snap_obj = normalize_host_target(snap_target)
        if snap_obj is not None:
            return snap_kind, snap_obj, "snap"
        hovered_kind, hovered_obj = normalize_host_target(hovered_target)
        if hovered_obj is not None:
            return hovered_kind, hovered_obj, "hovered"
        selected_walls = []
        for target in selected_targets or ():
            target_kind, target_obj = normalize_host_target(target)
            if target_obj is not None and target_obj not in selected_walls:
                selected_walls.append(target_obj)
        if len(selected_walls) == 1:
            return "wall", selected_walls[0], "selected"
        selected_kind, selected_obj = normalize_host_target(selected_target)
        if selected_obj is not None:
            return selected_kind, selected_obj, "selected"
        return (None, None, "")
    get_payload_host_target = getattr(
        session.providers,
        "get_provider_point_payload_host_target",
        None,
    )
    if not callable(get_payload_host_target):
        return (None, None, "")
    return get_payload_host_target(
        snap_target=snap_target,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
    )


def _apply_builtin_provider_handle_action(session, provider_obj, handle, payload):
    role = _get_provider_handle_role(handle)
    if role == "rehost":
        return _apply_provider_rehost(session, provider_obj, payload)
    return _apply_provider_placement_move(session, provider_obj, payload.get("point"))


def _apply_provider_rehost(session, provider_obj, payload):
    host_kind, host_obj = payload.get("host_target") or (None, None)
    if host_kind != "wall" or host_obj is None:
        return False
    try:
        import Arch
    except Exception:
        return False
    if not Arch.rehostObject(
        provider_obj,
        host_obj,
        preserve_world_position=True,
        raise_on_error=False,
    ):
        return False
    placement_point = payload.get("placement_point")
    if placement_point is not None and not _apply_provider_placement_move(
        session,
        provider_obj,
        placement_point,
    ):
        return False
    return True


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
