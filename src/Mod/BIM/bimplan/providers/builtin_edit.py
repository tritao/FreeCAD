# SPDX-License-Identifier: LGPL-2.1-or-later

"""Built-in provider edit handles for BIM Plan Edit."""

import FreeCAD

from bimplan.providers import payloads as plan_provider_payloads
from bimplan.providers.contracts import (
    PlanEditHandleSpec,
    PlanOverlayMarkerKind,
    PlanToolInteraction,
)
from bimplan.providers import runtime as plan_provider_runtime

translate = FreeCAD.Qt.translate


def get_builtin_provider_edit_handles(session, provider_obj, provider_target):
    handles = []
    move_handle = _make_builtin_provider_move_handle(session, provider_obj, provider_target)
    if move_handle is not None:
        handles.append(move_handle)
    rehost_handle = _make_builtin_provider_rehost_handle(session, provider_obj, provider_target)
    if rehost_handle is not None:
        handles.append(rehost_handle)
    return handles


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


def get_provider_move_point(session, provider_obj):
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


def apply_builtin_provider_handle_action(session, provider_obj, handle, payload):
    role = _get_provider_handle_role(handle)
    if role == "rehost":
        return _apply_provider_rehost(session, provider_obj, payload)
    return _apply_provider_placement_move(session, provider_obj, payload.get("point"))


def _make_builtin_provider_move_handle(session, provider_obj, provider_target):
    if not can_move_provider_target_by_placement(session, provider_obj):
        return None
    point = get_provider_move_point(session, provider_obj)
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


def _get_provider_rehost_point(session, provider_obj):
    point = get_provider_move_point(session, provider_obj)
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


def _apply_provider_rehost(session, provider_obj, payload):
    host_kind, host_obj = plan_provider_payloads.unpack_provider_host_target_ref(
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


def _get_provider_handle_role(handle):
    return str(getattr(handle, "role", "") or "").strip().lower()
