# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider point tool helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from bimplan import visual_keys as plan_visual_keys

translate = FreeCAD.Qt.translate

_PLAN_VISUAL_ALL = plan_visual_keys.PLAN_VISUAL_ALL


def has_active_provider_point_tool(session):
    return session.current_tool == "Provider Point" and session._provider_point_tool is not None


def get_provider_point_tool_label(session):
    tool = session._provider_point_tool
    if tool is None:
        return translate("BIM_PlanEdit", "Provider Point")
    label = str(getattr(tool, "label", "") or "").strip()
    if label:
        return label
    return str(getattr(tool, "key", "") or "").strip() or translate(
        "BIM_PlanEdit",
        "Provider Point",
    )


def get_provider_point_tool_prompt(session):
    tool = session._provider_point_tool
    if tool is None:
        return translate("BIM_PlanEdit", "Click a plan point")
    prompt = str(getattr(tool, "prompt", "") or "").strip()
    if prompt:
        return prompt
    return translate("BIM_PlanEdit", "Click a plan point for {tool}").format(
        tool=get_provider_point_tool_label(session)
    )


def arm_provider_point_tool(session):
    if not session._has_active_provider_point_tool():
        return False
    snapper = getattr(FreeCADGui, "Snapper", None)
    if snapper is None:
        return False
    FreeCAD.activeDraftCommand = session
    try:
        snapper.setSelectMode(False)
    except Exception:
        pass
    session._set_draft_point_focus_suppressed(True)
    try:
        snapper.getPoint(
            callback=session._handle_provider_point_tool_point,
            movecallback=session._update_provider_point_tool_preview,
            title=get_provider_point_tool_prompt(session),
            noTracker=True,
        )
    except Exception:
        session._set_draft_point_focus_suppressed(False)
        return False
    session.viewport.queue_focus_plan_view()
    return True


def cancel_provider_point_tool(session, refresh=True):
    if not session._has_active_provider_point_tool():
        session._clear_provider_point_preview()
        return False
    session._stop_snapper()
    session._provider_point_tool = None
    session._provider_point_host_target = None
    session._provider_point_host_source = ""
    session._clear_provider_point_preview()
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if refresh:
        session._refresh_task_panel_status()
    session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_ALL)
    return True


def start_plan_provider_point_tool(session, tool):
    if tool is None:
        return False
    if session._plan_provider_integrations_disabled():
        return False
    session._cancel_space_region_pick(refresh=False)
    session._cancel_plan_region_tool(refresh=False)
    session._cancel_rect_wall_tool(refresh=False)
    session._cancel_space_separator_tool(refresh=False)
    if session.current_tool == "Set Space Text":
        session._cancel_space_text_position_pick()
    if session.current_tool in ("Move Symbol", "Rotate Symbol"):
        session._cancel_symbol_handle_point_pick()
    if session._has_active_embedded_tool():
        session._cancel_embedded_tool()
    session._cancel_wall_edit(refresh=False)
    session._cancel_pending_edit()
    session._clear_plan_relation_status()
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_provider(None)
    session._set_hovered_space(None)
    session._set_hovered_region(None)
    session._clear_wall_grips()
    session._clear_selected_wall_overlay()
    session._clear_selected_wall_opening_context_overlay()
    session._clear_selected_opening_handles()
    session._clear_selected_symbol_handles()
    session._clear_provider_point_preview()
    host_kind, host_obj, host_source = session._get_provider_point_context_host_state()
    if host_obj is None:
        host_kind, host_obj = session._normalize_provider_point_host_target(
            getattr(tool, "default_host_target", ())
        )
        if host_obj is not None:
            host_source = "tool"
    session._provider_point_host_target = (host_kind, host_obj)
    session._provider_point_host_source = host_source
    session._provider_point_tool = tool
    session.current_tool = "Provider Point"
    session._refresh_task_panel_status()
    session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_ALL)
    if session._arm_provider_point_tool():
        return True
    session._provider_point_tool = None
    session._provider_point_host_target = None
    session._provider_point_host_source = ""
    session.current_tool = "Select"
    session._refresh_task_panel_status()
    return False


def handle_provider_point_tool_point(session, point=None, obj=None):
    if not session._has_active_provider_point_tool():
        return
    if point is None:
        session._cancel_provider_point_tool()
        return
    plan_point = session._project_plan_point(point)
    if plan_point is None:
        session._clear_provider_point_preview()
        session._arm_provider_point_tool()
        return
    tool = session._provider_point_tool
    snap_info = session._get_provider_point_snap_info()
    snap_object = session._resolve_provider_point_snap_object(obj, snap_info)
    payload = session._build_provider_point_tool_payload(
        tool,
        raw_point=point,
        plan_point=plan_point,
        snap_object=snap_object,
        snap_info=snap_info,
    )
    session.execute_plan_provider_action(
        getattr(tool, "provider_id", ""),
        getattr(tool, "key", ""),
        transaction_label=getattr(tool, "transaction_label", ""),
        payload=payload,
    )
    session._clear_provider_point_preview()
    if session._has_active_provider_point_tool():
        session._arm_provider_point_tool()


def update_provider_point_tool_preview(session, point=None, obj=None):
    if not session._has_active_provider_point_tool():
        session._clear_provider_point_preview()
        return
    if point is None:
        session._clear_provider_point_preview()
        return
    plan_point = session._project_plan_point(point)
    if plan_point is None:
        session._clear_provider_point_preview()
        return
    snap_info = session._get_provider_point_snap_info()
    snap_object = session._resolve_provider_point_snap_object(obj, snap_info)
    snap_target = (None, None)
    if snap_object is not None:
        snap_target = session._get_plan_target_for_object(snap_object)
    host_kind, host_obj, host_source = session._get_provider_point_payload_host_target(
        snap_target=snap_target,
        selected_target=session._get_selected_plan_target(),
        selected_targets=session._get_selected_plan_targets(),
        hovered_target=session._get_hovered_plan_target(),
    )
    placement_point = (
        session._project_provider_point_to_host(plan_point, host_obj)
        if host_kind == "wall"
        else None
    )
    if placement_point is None:
        placement_point = plan_point
    session._provider_point_preview_source_point = plan_point
    session._provider_point_preview_point = placement_point
    session._provider_point_preview_host_target = (host_kind, host_obj)
    session._provider_point_preview_host_source = host_source
    session._sync_provider_point_preview()


def get_provider_point_snap_info():
    snapper = getattr(FreeCADGui, "Snapper", None)
    if snapper is None:
        return {}
    snap_info = getattr(snapper, "snapInfo", None)
    if isinstance(snap_info, dict):
        return dict(snap_info)
    return {}


def resolve_provider_point_snap_object(session, snap_object, snap_info):
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


def normalize_provider_point_host_target(session, target):
    if not target:
        return (None, None)
    try:
        target_kind, target_obj = target
    except Exception:
        return (None, None)
    if target_kind == "wall" and session._is_plan_selectable_wall(target_obj):
        return ("wall", target_obj)
    return (None, None)


def get_provider_point_context_host_state(session):
    selected_kind, selected_obj = session._normalize_provider_point_host_target(
        session._get_selected_plan_target()
    )
    if selected_obj is not None:
        return selected_kind, selected_obj, "selected"
    hovered_kind, hovered_obj = session._normalize_provider_point_host_target(
        session._get_hovered_plan_target()
    )
    if hovered_obj is not None:
        return hovered_kind, hovered_obj, "hovered"
    return None, None, ""


def get_provider_point_payload_host_target(
    session,
    *,
    snap_target,
    selected_target,
    selected_targets,
    hovered_target,
):
    selected_kind, selected_obj = session._normalize_provider_point_host_target(selected_target)
    if selected_obj is not None:
        return selected_kind, selected_obj, "selected"
    selected_walls = []
    for target in selected_targets or ():
        target_kind, target_obj = session._normalize_provider_point_host_target(target)
        if target_obj is not None and target_obj not in selected_walls:
            selected_walls.append(target_obj)
    if len(selected_walls) == 1:
        return "wall", selected_walls[0], "selected"
    snap_kind, snap_obj = session._normalize_provider_point_host_target(snap_target)
    if snap_obj is not None:
        return snap_kind, snap_obj, "snap"
    stored_kind, stored_obj = session._normalize_provider_point_host_target(
        session._provider_point_host_target
    )
    if stored_obj is not None:
        return stored_kind, stored_obj, session._provider_point_host_source or "stored"
    hovered_kind, hovered_obj = session._normalize_provider_point_host_target(hovered_target)
    if hovered_obj is not None:
        return hovered_kind, hovered_obj, "hovered"
    return None, None, ""


def project_provider_point_to_host(point, host_wall):
    if point is None or host_wall is None:
        return None
    proxy = getattr(host_wall, "Proxy", None)
    if proxy is None or not hasattr(proxy, "calc_endpoints"):
        return None
    try:
        endpoints = proxy.calc_endpoints(host_wall)
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


def build_provider_point_tool_payload(
    session,
    tool,
    *,
    raw_point,
    plan_point,
    snap_object,
    snap_info,
):
    snap_target = (None, None)
    if snap_object is not None:
        snap_target = session._get_plan_target_for_object(snap_object)
    snap_component = str(snap_info.get("Component", "") or "").strip()
    snap_subname = str(snap_info.get("SubName", "") or snap_component).strip()
    snap_document_name = str(snap_info.get("Document", "") or "").strip()
    if not snap_document_name and snap_object is not None:
        snap_document_name = str(getattr(getattr(snap_object, "Document", None), "Name", "") or "")
    snap_object_name = str(snap_info.get("Object", "") or "").strip()
    if not snap_object_name and snap_object is not None:
        snap_object_name = str(getattr(snap_object, "Name", "") or "")
    selected_target = session._get_selected_plan_target()
    selected_targets = session._get_selected_plan_targets()
    hovered_target = session._get_hovered_plan_target()
    host_kind, host_obj, host_source = session._get_provider_point_payload_host_target(
        snap_target=snap_target,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
    )
    placement_point = (
        session._project_provider_point_to_host(plan_point, host_obj)
        if host_kind == "wall"
        else None
    )
    if placement_point is None:
        placement_point = plan_point
    return {
        "tool": tool,
        "point": plan_point,
        "placement_point": placement_point,
        "raw_point": raw_point,
        "snap_info": snap_info,
        "snap_object": snap_object,
        "snap_target": snap_target,
        "snap_document_name": snap_document_name,
        "snap_object_name": snap_object_name,
        "snap_component": snap_component,
        "snap_subname": snap_subname,
        "selected_target": selected_target,
        "selected_targets": selected_targets,
        "hovered_target": hovered_target,
        "host_target": (host_kind, host_obj),
        "host_source": host_source,
    }
