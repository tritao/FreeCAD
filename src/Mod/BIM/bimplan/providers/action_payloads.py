# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared provider action payload context helpers."""

from __future__ import annotations

from dataclasses import dataclass

import FreeCAD
import FreeCADGui

from bimplan.providers import payloads as plan_provider_payloads
from bimplan.selection import target_kinds as plan_target_kinds


@dataclass(frozen=True)
class ProviderActionPayloadContext:
    snap_info: dict
    snap_object: object
    snap_target: object
    snap_document_name: str
    snap_object_name: str
    snap_component: str
    snap_subname: str
    selected_target: object
    selected_targets: object
    hovered_target: object


def get_provider_snap_info():
    snapper = getattr(FreeCADGui, "Snapper", None)
    if snapper is None:
        return {}
    snap_info = getattr(snapper, "snapInfo", None)
    if isinstance(snap_info, dict):
        return dict(snap_info)
    return {}


def resolve_provider_snap_object(session, snap_object, snap_info):
    if snap_object is not None:
        return snap_object
    object_name = str(snap_info.get("Object", "") or "").strip()
    if not object_name:
        return None
    doc = session.doc
    document_name = str(snap_info.get("Document", "") or "").strip()
    if document_name:
        try:
            doc = FreeCAD.getDocument(document_name)
        except Exception:
            doc = session.doc
    if doc is None:
        return None
    try:
        return doc.getObject(object_name)
    except Exception:
        return None


def build_provider_action_payload_context(
    session,
    *,
    snap_object=None,
    snap_info=None,
):
    if not isinstance(snap_info, dict):
        snap_info = {}
    snap_object = resolve_provider_snap_object(session, snap_object, snap_info)
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
    return ProviderActionPayloadContext(
        snap_info=snap_info,
        snap_object=snap_object,
        snap_target=snap_target,
        snap_document_name=snap_document_name,
        snap_object_name=snap_object_name,
        snap_component=snap_component,
        snap_subname=snap_subname,
        selected_target=session.selection.state.get_selected_plan_target(),
        selected_targets=session.selection.state.get_selected_plan_targets(),
        hovered_target=session.selection.hover.get_hovered_plan_target(),
    )


def normalize_provider_wall_host_target(session, target):
    if not target:
        return plan_provider_payloads.make_provider_host_target_ref()
    target_ref = plan_target_kinds.coerce_plan_target_ref(target)
    if target_ref.kind == "wall" and session.selection.targets.is_plan_selectable_wall(
        target_ref.obj
    ):
        return plan_provider_payloads.make_provider_host_target_ref("wall", target_ref.obj)
    return plan_provider_payloads.make_provider_host_target_ref()


def get_selected_wall_host_target(session, selected_targets):
    selected_walls = []
    for target in selected_targets or ():
        target_ref = normalize_provider_wall_host_target(session, target)
        if target_ref.obj is not None and target_ref.obj not in selected_walls:
            selected_walls.append(target_ref.obj)
    if len(selected_walls) != 1:
        return plan_provider_payloads.make_provider_host_target_ref()
    return plan_provider_payloads.make_provider_host_target_ref("wall", selected_walls[0])


def get_provider_context_host_state(session, *, selected_target, hovered_target):
    selected_target_ref = normalize_provider_wall_host_target(session, selected_target)
    if selected_target_ref.obj is not None:
        return selected_target_ref, "selected"
    hovered_target_ref = normalize_provider_wall_host_target(session, hovered_target)
    if hovered_target_ref.obj is not None:
        return hovered_target_ref, "hovered"
    return plan_provider_payloads.make_provider_host_target_ref(), ""


def get_provider_point_host_target(
    session,
    *,
    snap_target,
    selected_target,
    selected_targets,
    hovered_target,
    stored_target=None,
    stored_source="",
):
    selected_target_ref = normalize_provider_wall_host_target(session, selected_target)
    if selected_target_ref.obj is not None:
        return selected_target_ref, "selected"
    selected_wall_ref = get_selected_wall_host_target(session, selected_targets)
    if selected_wall_ref.obj is not None:
        return selected_wall_ref, "selected"
    snap_target_ref = normalize_provider_wall_host_target(session, snap_target)
    if snap_target_ref.obj is not None:
        return snap_target_ref, "snap"
    stored_target_ref = normalize_provider_wall_host_target(session, stored_target)
    if stored_target_ref.obj is not None:
        return stored_target_ref, stored_source or "stored"
    hovered_target_ref = normalize_provider_wall_host_target(session, hovered_target)
    if hovered_target_ref.obj is not None:
        return hovered_target_ref, "hovered"
    return plan_provider_payloads.make_provider_host_target_ref(), ""


def get_provider_rehost_host_target(
    session,
    *,
    snap_target,
    selected_target,
    selected_targets,
    hovered_target,
):
    snap_target_ref = normalize_provider_wall_host_target(session, snap_target)
    if snap_target_ref.obj is not None:
        return snap_target_ref, "snap"
    hovered_target_ref = normalize_provider_wall_host_target(session, hovered_target)
    if hovered_target_ref.obj is not None:
        return hovered_target_ref, "hovered"
    selected_wall_ref = get_selected_wall_host_target(session, selected_targets)
    if selected_wall_ref.obj is not None:
        return selected_wall_ref, "selected"
    selected_target_ref = normalize_provider_wall_host_target(session, selected_target)
    if selected_target_ref.obj is not None:
        return selected_target_ref, "selected"
    return plan_provider_payloads.make_provider_host_target_ref(), ""


def project_provider_point_to_host(point, host_wall):
    if point is None or host_wall is None:
        return None
    proxy = getattr(host_wall, "Proxy", None)
    calc_endpoints = getattr(proxy, "calc_endpoints", None)
    if not callable(calc_endpoints):
        return None
    try:
        endpoints = calc_endpoints(host_wall)
        start = FreeCAD.Vector(endpoints[0])
        end = FreeCAD.Vector(endpoints[1])
        source = FreeCAD.Vector(point)
    except Exception:
        return None
    axis = end.sub(start)
    axis.z = 0.0
    length_sq = axis.dot(axis)
    if length_sq <= 1e-9:
        return None
    offset = source.sub(start)
    offset.z = 0.0
    factor = max(0.0, min(1.0, offset.dot(axis) / length_sq))
    projected = start.add(axis.multiply(factor))
    projected.z = getattr(source, "z", 0.0)
    return projected
