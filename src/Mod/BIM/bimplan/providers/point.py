# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider point tool helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from bimplan import document_visuals as plan_document_visuals
from bimplan.providers import host_targets as plan_host_targets
from bimplan.providers import payloads as plan_provider_payloads
from bimplan.providers import runtime as plan_provider_runtime
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.selection import target_kinds as plan_target_kinds

translate = FreeCAD.Qt.translate


class ProviderPointTool(plan_runtime_tools.PlanToolHandler):
    """Keyboard behavior for active provider point placement."""

    tool_id = plan_runtime_tools.PlanTool.PROVIDER_POINT

    def on_key(self, key, event_callback, coin):
        del event_callback
        if key != coin.SoKeyboardEvent.ESCAPE:
            return False
        return self.cancel()

    def cancel(self):
        cancel_provider_point_tool(self.session)
        return True


def _provider_point_state(session):
    return session.provider_point_state


def has_active_provider_point_tool(session):
    return (
        session.current_tool == plan_runtime_tools.PlanTool.PROVIDER_POINT
        and _provider_point_state(session).provider_point_tool is not None
    )


def get_provider_point_tool_label(session):
    tool = _provider_point_state(session).provider_point_tool
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
    tool = _provider_point_state(session).provider_point_tool
    if tool is None:
        return translate("BIM_PlanEdit", "Click a plan point")
    prompt = str(getattr(tool, "prompt", "") or "").strip()
    if prompt:
        return prompt
    return translate("BIM_PlanEdit", "Click a plan point for {tool}").format(
        tool=get_provider_point_tool_label(session)
    )


def arm_provider_point_tool(session):
    if not has_active_provider_point_tool(session):
        return False
    snapper = getattr(FreeCADGui, "Snapper", None)
    if snapper is None:
        return False
    session.snap.set_active_draft_command()
    try:
        snapper.setSelectMode(False)
    except Exception:
        pass
    session.snap.set_point_focus_suppressed(True)
    try:
        snapper.getPoint(
            callback=lambda point=None, obj=None: handle_provider_point_tool_point(
                session, point, obj
            ),
            movecallback=lambda point=None, obj=None: update_provider_point_tool_preview(
                session, point, obj
            ),
            title=get_provider_point_tool_prompt(session),
            noTracker=True,
        )
    except Exception:
        session.snap.set_point_focus_suppressed(False)
        return False
    session.viewport.queue_focus_plan_view()
    return True


def cancel_provider_point_tool(session, refresh=True):
    if not has_active_provider_point_tool(session):
        session.overlays.providers.clear_provider_point_preview()
        return False
    session.snap.stop_snapper()
    state = _provider_point_state(session)
    state.provider_point_tool = None
    state.provider_point_host_target = None
    state.provider_point_host_source = ""
    session.overlays.providers.clear_provider_point_preview()
    session.snap.clear_active_draft_command()
    session.current_tool = plan_runtime_tools.PlanTool.SELECT
    if refresh:
        session.task_panels.refresh_task_panel_status()
    session.overlays.queue_plan_overlay_visual_refresh(plan_document_visuals.PLAN_VISUAL_ALL)
    return True


def start_plan_provider_point_tool(session, tool):
    if tool is None:
        return False
    if plan_provider_runtime.plan_provider_integrations_disabled(session):
        return False
    session.spaces.cancel_space_region_pick(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    if session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
        session.spaces.cancel_space_text_position_pick()
    if session.current_tool in (
        plan_runtime_tools.PlanTool.MOVE_SYMBOL,
        plan_runtime_tools.PlanTool.ROTATE_SYMBOL,
    ):
        session.symbols.cancel_symbol_handle_point_pick()
    if session.embedded_tools.has_active():
        session.embedded_tools.cancel()
    session.wall_edit.cancel_wall_edit(refresh=False)
    session.lifecycle.cancel_pending_edit()
    session.wall_relations.clear_plan_relation_status()
    session.selection.hover.set_hovered_wall(None)
    session.selection.hover.set_hovered_opening(None)
    session.selection.hover.set_hovered_symbol(None)
    session.selection.hover.set_hovered_provider(None)
    session.selection.hover.set_hovered_space(None)
    session.selection.hover.set_hovered_region(None)
    session.overlays.walls.clear_wall_grips()
    session.overlays.walls.clear_selected_wall_overlay()
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    session.overlays.openings.clear_selected_opening_handles()
    session.overlays.symbols.clear_selected_symbol_handles()
    session.overlays.providers.clear_provider_point_preview()
    host_target, host_source = get_provider_point_context_host_state(session)
    host_kind, host_obj = plan_host_targets.unpack_provider_host_target_ref(host_target)
    if host_obj is None:
        host_target = normalize_provider_point_host_target(
            session, getattr(tool, "default_host_target", ())
        )
        host_kind, host_obj = plan_host_targets.unpack_provider_host_target_ref(host_target)
        if host_obj is not None:
            host_source = "tool"
    state = _provider_point_state(session)
    state.provider_point_host_target = host_target
    state.provider_point_host_source = host_source
    state.provider_point_tool = tool
    session.current_tool = plan_runtime_tools.PlanTool.PROVIDER_POINT
    session.task_panels.refresh_task_panel_status()
    session.overlays.queue_plan_overlay_visual_refresh(plan_document_visuals.PLAN_VISUAL_ALL)
    if arm_provider_point_tool(session):
        return True
    state.provider_point_tool = None
    state.provider_point_host_target = None
    state.provider_point_host_source = ""
    session.current_tool = plan_runtime_tools.PlanTool.SELECT
    session.task_panels.refresh_task_panel_status()
    return False


def handle_provider_point_tool_point(session, point=None, obj=None):
    if not has_active_provider_point_tool(session):
        return
    if point is None:
        cancel_provider_point_tool(session)
        return
    plan_point = session.viewport.project_plan_point(point)
    if plan_point is None:
        session.overlays.providers.clear_provider_point_preview()
        arm_provider_point_tool(session)
        return
    tool = _provider_point_state(session).provider_point_tool
    snap_info = get_provider_point_snap_info()
    snap_object = resolve_provider_point_snap_object(session, obj, snap_info)
    payload = build_provider_point_tool_payload(
        session,
        tool,
        raw_point=point,
        plan_point=plan_point,
        snap_object=snap_object,
        snap_info=snap_info,
    )
    session.providers.execute_plan_provider_action(
        getattr(tool, "provider_id", ""),
        getattr(tool, "key", ""),
        transaction_label=getattr(tool, "transaction_label", ""),
        payload=payload,
    )
    session.overlays.providers.clear_provider_point_preview()
    if has_active_provider_point_tool(session):
        arm_provider_point_tool(session)


def update_provider_point_tool_preview(session, point=None, obj=None):
    if not has_active_provider_point_tool(session):
        session.overlays.providers.clear_provider_point_preview()
        return
    if point is None:
        session.overlays.providers.clear_provider_point_preview()
        return
    plan_point = session.viewport.project_plan_point(point)
    if plan_point is None:
        session.overlays.providers.clear_provider_point_preview()
        return
    snap_info = get_provider_point_snap_info()
    snap_object = resolve_provider_point_snap_object(session, obj, snap_info)
    snap_target = plan_target_kinds.make_plan_target_ref()
    if snap_object is not None:
        snap_target = session.selection.targets.get_plan_target_for_object(snap_object)
    host_target, host_source = get_provider_point_payload_host_target(
        session,
        snap_target=snap_target,
        selected_target=session.selection.state.get_selected_plan_target(),
        selected_targets=session.selection.state.get_selected_plan_targets(),
        hovered_target=session.selection.hover.get_hovered_plan_target(),
    )
    host_kind, host_obj = plan_host_targets.unpack_provider_host_target_ref(host_target)
    placement_point = (
        project_provider_point_to_host(plan_point, host_obj) if host_kind == "wall" else None
    )
    if placement_point is None:
        placement_point = plan_point
    state = _provider_point_state(session)
    state.provider_point_preview_source_point = plan_point
    state.provider_point_preview_point = placement_point
    state.provider_point_preview_host_target = host_target
    state.provider_point_preview_host_source = host_source
    session.overlays.providers.sync_provider_point_preview()


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
        return plan_host_targets.make_provider_host_target_ref()
    target_ref = plan_target_kinds.coerce_plan_target_ref(target)
    if target_ref.kind == "wall" and session.selection.targets.is_plan_selectable_wall(
        target_ref.obj
    ):
        return plan_host_targets.make_provider_host_target_ref("wall", target_ref.obj)
    return plan_host_targets.make_provider_host_target_ref()


def get_provider_point_context_host_state(session):
    selected_target = normalize_provider_point_host_target(
        session, session.selection.state.get_selected_plan_target()
    )
    if selected_target.obj is not None:
        return selected_target, "selected"
    hovered_target = normalize_provider_point_host_target(
        session, session.selection.hover.get_hovered_plan_target()
    )
    if hovered_target.obj is not None:
        return hovered_target, "hovered"
    return plan_host_targets.make_provider_host_target_ref(), ""


def get_provider_point_payload_host_target(
    session,
    *,
    snap_target,
    selected_target,
    selected_targets,
    hovered_target,
):
    selected_target_ref = normalize_provider_point_host_target(session, selected_target)
    if selected_target_ref.obj is not None:
        return selected_target_ref, "selected"
    selected_walls = []
    for target in selected_targets or ():
        target_ref = normalize_provider_point_host_target(session, target)
        if target_ref.obj is not None and target_ref.obj not in selected_walls:
            selected_walls.append(target_ref.obj)
    if len(selected_walls) == 1:
        return (
            plan_host_targets.make_provider_host_target_ref("wall", selected_walls[0]),
            "selected",
        )
    snap_target_ref = normalize_provider_point_host_target(session, snap_target)
    if snap_target_ref.obj is not None:
        return snap_target_ref, "snap"
    stored_target_ref = normalize_provider_point_host_target(
        session,
        _provider_point_state(session).provider_point_host_target,
    )
    if stored_target_ref.obj is not None:
        return (
            stored_target_ref,
            _provider_point_state(session).provider_point_host_source or "stored",
        )
    hovered_target_ref = normalize_provider_point_host_target(session, hovered_target)
    if hovered_target_ref.obj is not None:
        return hovered_target_ref, "hovered"
    return plan_host_targets.make_provider_host_target_ref(), ""


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


def build_provider_point_tool_payload(
    session,
    tool,
    *,
    raw_point,
    plan_point,
    snap_object,
    snap_info,
):
    snap_target = plan_target_kinds.make_plan_target_ref()
    if snap_object is not None:
        snap_target = session.selection.targets.get_plan_target_for_object(snap_object)
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
    host_target, host_source = get_provider_point_payload_host_target(
        session,
        snap_target=snap_target,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
    )
    host_kind, host_obj = plan_host_targets.unpack_provider_host_target_ref(host_target)
    placement_point = (
        project_provider_point_to_host(plan_point, host_obj) if host_kind == "wall" else None
    )
    if placement_point is None:
        placement_point = plan_point
    return plan_provider_payloads.ProviderPointActionPayload(
        tool=tool,
        point=plan_point,
        placement_point=placement_point,
        raw_point=raw_point,
        snap_info=snap_info,
        snap_object=snap_object,
        snap_target=snap_target,
        snap_document_name=snap_document_name,
        snap_object_name=snap_object_name,
        snap_component=snap_component,
        snap_subname=snap_subname,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
        host_target=host_target,
        host_source=host_source,
    )
