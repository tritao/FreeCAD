# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider edit interaction helpers for BIM Plan Edit."""

from contextlib import nullcontext

import FreeCAD
import FreeCADGui
from bimplan.providers import host_targets as plan_host_targets
from bimplan.providers import payloads as plan_provider_payloads
from bimplan.providers import PlanEditHandleSpec, PlanOverlayMarkerKind, PlanToolInteraction
from bimplan.providers import point as plan_provider_point
from bimplan.providers import runtime as plan_provider_runtime
from bimplan import selection as plan_selection
from bimplan.selection import target_kinds as plan_target_kinds

translate = FreeCAD.Qt.translate


def get_selected_provider_edit_handles(session, provider_obj):
    if provider_obj is None:
        return []
    selected_provider = plan_selection.get_selected_plan_target_object(session, "provider")
    editing_provider = session.interaction_state.edit_provider
    if provider_obj != selected_provider and provider_obj != editing_provider:
        return []
    provider_target = plan_provider_runtime.get_plan_provider_target_for_object(
        session, provider_obj
    )
    if provider_target is None:
        return []
    provider_id = str(getattr(provider_target, "provider_id", "") or "").strip()
    target_key = str(getattr(provider_target, "key", "") or "").strip()
    handles = []
    for handle in tuple(plan_provider_runtime.get_plan_provider_edit_handles(session) or ()):
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
    if provider_obj is None or not plan_provider_runtime.is_plan_provider_target_object(
        session, provider_obj
    ):
        return False
    if _has_provider_coordinate_properties(provider_obj):
        return True
    placement = getattr(provider_obj, "Placement", None)
    if placement is None:
        return False
    try:
        local_placement = session.visibility.copy_placement(placement)
        global_placement = session.visibility.get_plan_object_global_placement(provider_obj)
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
    if provider_obj is None or not plan_provider_runtime.is_plan_provider_target_object(
        session, provider_obj
    ):
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
        activate_provider_handle_now(session, provider_obj, handle_index)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda: activate_provider_handle_now(session, provider_obj, handle_index),
    )


def activate_provider_handle_now(session, provider_obj, handle_index):
    if session.lifecycle_state.tearing_down or provider_obj is None:
        return
    handles = get_selected_provider_edit_handles(session, provider_obj)
    if handle_index < 0 or handle_index >= len(handles):
        return
    handle = handles[handle_index]
    session.selection.state.set_selected_plan_target("provider", provider_obj)
    session.selection.sync.set_gui_selection_object(provider_obj)
    session.overlays.walls.clear_wall_grips()
    if handle.interaction == PlanToolInteraction.POINT:
        start_provider_handle_point_pick(session, provider_obj, handle_index, handle)
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
        handled = plan_provider_runtime.execute_plan_provider_action(
            session,
            str(getattr(handle, "provider_id", "") or ""),
            str(getattr(handle, "action_key", "") or ""),
            transaction_label=str(getattr(handle, "transaction_label", "") or ""),
            payload=payload,
        )
    if handled:
        queue_restore_selected_provider(session, provider_obj)
        return
    restore_selected_provider(session, provider_obj)


def start_provider_handle_point_pick(session, provider_obj, handle_index, handle):
    if provider_obj is None:
        return
    start_point = _get_handle_point_vector(handle)
    if start_point is None:
        return
    session.current_tool = "Move Provider"
    session.selection.hover.set_hovered_wall(None)
    session.selection.hover.set_hovered_opening(None)
    session.selection.hover.set_hovered_symbol(None)
    session.selection.hover.set_hovered_provider(None)
    session.selection.hover.set_hovered_space(None)
    session.selection.hover.set_hovered_region(None)
    session.overlays.spaces.sync_secondary_selected_overlays()
    interaction_state = session.interaction_state
    interaction_state.edit_provider = provider_obj
    interaction_state.edit_provider_handle_index = handle_index
    interaction_state.edit_provider_handle = handle
    session.overlays.providers.clear_selected_provider_overlay()
    session.overlays.providers.clear_selected_provider_handles()
    session.task_panels.refresh_task_panel_status()
    FreeCAD.activeDraftCommand = session
    session.lifecycle.set_draft_point_focus_suppressed(True)
    FreeCADGui.Snapper.getPoint(
        last=start_point,
        callback=finish_provider_handle_point_pick,
        movecallback=update_provider_handle_point_pick,
        title=_get_provider_handle_prompt(handle),
        noTracker=True,
    )
    session.viewport.queue_focus_plan_view()


def update_provider_handle_point_pick(session, point=None, snap_info=None):
    del point, snap_info


def finish_provider_handle_point_pick(session, point=None, obj=None):
    interaction_state = session.interaction_state
    provider_obj = interaction_state.edit_provider
    handle = interaction_state.edit_provider_handle
    interaction_state.edit_provider = None
    interaction_state.edit_provider_handle_index = None
    interaction_state.edit_provider_handle = None
    FreeCAD.activeDraftCommand = None

    if point is None or provider_obj is None:
        session.current_tool = "Select"
        restore_selected_provider(session, provider_obj)
        return

    if handle is None:
        session.current_tool = "Select"
        restore_selected_provider(session, provider_obj)
        return
    target_point = _resolve_provider_handle_target_point(session, provider_obj, point)
    if target_point is None:
        session.current_tool = "Select"
        restore_selected_provider(session, provider_obj)
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
        if plan_provider_runtime.execute_plan_provider_action(
            session,
            provider_id,
            action_key,
            transaction_label=str(getattr(handle, "transaction_label", "") or ""),
            payload=payload,
        ):
            queue_restore_selected_provider(session, provider_obj)
            return
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Plan Edit provider handle '{handle}' was not handled.\n",
            ).format(handle=str(getattr(handle, "key", "") or ""))
        )
        restore_selected_provider(session, provider_obj)
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
        restore_selected_provider(session, provider_obj)
        return

    queue_restore_selected_provider(session, provider_obj)


def cancel_provider_handle_point_pick(session):
    interaction_state = session.interaction_state
    provider_obj = interaction_state.edit_provider
    interaction_state.edit_provider = None
    interaction_state.edit_provider_handle_index = None
    interaction_state.edit_provider_handle = None
    session.lifecycle.stop_snapper()
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if provider_obj is not None:
        restore_selected_provider(session, provider_obj)
        return
    session.selection.sync.set_gui_selection([])
    session.selection.refresh.refresh_primary_selected_plan_target()


def restore_selected_provider(session, provider_obj):
    session.current_tool = "Select"
    if provider_obj is not None and plan_provider_runtime.is_plan_provider_target_object(
        session, provider_obj
    ):
        session.selection.sync.set_gui_selection_object(provider_obj)
    else:
        session.selection.sync.set_gui_selection([])
    session.selection.refresh.refresh_primary_selected_plan_target()


def queue_restore_selected_provider(session, provider_obj):
    try:
        from PySide import QtCore
    except ImportError:
        restore_selected_provider(session, provider_obj)
        return
    QtCore.QTimer.singleShot(0, lambda: restore_selected_provider(session, provider_obj))


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
        placement = session.visibility.get_plan_object_global_placement(provider_obj)
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
    provider_target = plan_provider_runtime.get_plan_provider_target_for_object(
        session, provider_obj
    )
    snap_info = plan_provider_point.get_provider_point_snap_info()
    if not isinstance(snap_info, dict):
        snap_info = {}
    try:
        snap_object = plan_provider_point.resolve_provider_point_snap_object(
            session, snap_object, snap_info
        )
    except Exception:
        pass
    snap_target = plan_target_kinds.make_plan_target_ref()
    if snap_object is not None:
        try:
            snap_target = session.selection.targets.get_plan_target_for_object(snap_object)
        except Exception:
            snap_target = plan_target_kinds.make_plan_target_ref()
    snap_component = str(snap_info.get("Component", "") or "").strip()
    snap_subname = str(snap_info.get("SubName", "") or snap_component).strip()
    snap_document_name = str(snap_info.get("Document", "") or "").strip()
    if not snap_document_name and snap_object is not None:
        snap_document_name = str(getattr(getattr(snap_object, "Document", None), "Name", "") or "")
    snap_object_name = str(snap_info.get("Object", "") or "").strip()
    if not snap_object_name and snap_object is not None:
        snap_object_name = str(getattr(snap_object, "Name", "") or "")
    selected_target = session.selection.state.get_selected_plan_target()
    selected_targets = session.selection.state.get_selected_plan_targets()
    hovered_target = session.selection.hover.get_hovered_plan_target()
    host_target, host_source = _get_provider_handle_payload_host_target(
        session,
        handle,
        snap_target=snap_target,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
    )
    host_kind, host_obj = plan_host_targets.unpack_provider_host_target_ref(host_target)
    placement_point = (
        plan_provider_point.project_provider_point_to_host(point, host_obj)
        if host_kind == "wall" and point is not None
        else None
    )
    if placement_point is None and point is not None:
        placement_point = FreeCAD.Vector(point)
    return plan_provider_payloads.ProviderHandleActionPayload(
        handle=handle,
        handle_key=str(getattr(handle, "key", "") or "").strip(),
        handle_role=str(getattr(handle, "role", "") or "").strip(),
        point=FreeCAD.Vector(point) if point is not None else None,
        placement_point=placement_point,
        raw_point=FreeCAD.Vector(raw_point) if raw_point is not None else None,
        snap_info=snap_info,
        snap_object=snap_object,
        snap_target=snap_target,
        snap_document_name=snap_document_name,
        snap_object_name=snap_object_name,
        snap_component=snap_component,
        snap_subname=snap_subname,
        target_object=provider_obj,
        provider_target=provider_target,
        target_key=str(getattr(provider_target, "key", "") or "").strip(),
        target_provider_id=str(getattr(provider_target, "provider_id", "") or "").strip(),
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
        host_target=host_target,
        host_source=host_source,
    )


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
    if role == "rehost":
        snap_target_ref = plan_provider_point.normalize_provider_point_host_target(
            session, snap_target
        )
        if snap_target_ref.obj is not None:
            return snap_target_ref, "snap"
        hovered_target_ref = plan_provider_point.normalize_provider_point_host_target(
            session, hovered_target
        )
        if hovered_target_ref.obj is not None:
            return hovered_target_ref, "hovered"
        selected_walls = []
        for target in selected_targets or ():
            target_ref = plan_provider_point.normalize_provider_point_host_target(session, target)
            if target_ref.obj is not None and target_ref.obj not in selected_walls:
                selected_walls.append(target_ref.obj)
        if len(selected_walls) == 1:
            return (
                plan_host_targets.make_provider_host_target_ref("wall", selected_walls[0]),
                "selected",
            )
        selected_target_ref = plan_provider_point.normalize_provider_point_host_target(
            session,
            selected_target,
        )
        if selected_target_ref.obj is not None:
            return selected_target_ref, "selected"
        return plan_host_targets.make_provider_host_target_ref(), ""
    return plan_provider_point.get_provider_point_payload_host_target(
        session,
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
    host_kind, host_obj = plan_host_targets.unpack_provider_host_target_ref(
        payload.get("host_target")
    )
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
        if getattr(provider_obj, "Z", None) is not None:
            provider_obj.Z = float(point.z)
        return True
    placement = session.visibility.copy_placement(getattr(provider_obj, "Placement", None))
    if placement is None:
        return False
    placement.Base = FreeCAD.Vector(float(point.x), float(point.y), float(placement.Base.z))
    provider_obj.Placement = placement
    return True


def _has_provider_coordinate_properties(provider_obj):
    return (
        getattr(provider_obj, "X", None) is not None
        and getattr(provider_obj, "Y", None) is not None
    )


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
