# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider point tool helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

from bimplan import document_visuals as plan_document_visuals
from bimplan.providers import action_payloads as plan_provider_action_payloads
from bimplan.providers import payloads as plan_provider_payloads
from bimplan.runtime import tools as plan_runtime_tools

translate = FreeCAD.Qt.translate


def _provider_runtime_api(session):
    providers = getattr(session, "providers", None)
    return getattr(providers, "runtime", providers)


class PlanProviderPointAPI:
    """Owned provider point-tool surface for Plan Edit interaction code."""

    __slots__ = ("_session", "__dict__")

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def has_active_provider_point_tool(self):
        return has_active_provider_point_tool(self.session)

    def get_provider_point_tool_label(self):
        return get_provider_point_tool_label(self.session)

    def get_provider_point_tool_prompt(self):
        return get_provider_point_tool_prompt(self.session)

    def arm_provider_point_tool(self):
        return arm_provider_point_tool(self.session)

    def cancel_provider_point_tool(self, refresh=True):
        return cancel_provider_point_tool(self.session, refresh=refresh)

    def cancel_for_select(self):
        if not self.has_active_provider_point_tool():
            return False
        self.cancel_provider_point_tool()
        return True

    def start_plan_provider_point_tool(self, tool):
        return start_plan_provider_point_tool(self.session, tool)

    def handle_provider_point_tool_point(self, point=None, obj=None):
        return handle_provider_point_tool_point(self.session, point=point, obj=obj)

    def update_provider_point_tool_preview(self, point=None, obj=None):
        return update_provider_point_tool_preview(self.session, point=point, obj=obj)

    def get_provider_point_snap_info(self):
        return get_provider_point_snap_info()

    def resolve_provider_point_snap_object(self, snap_object, snap_info):
        return resolve_provider_point_snap_object(self.session, snap_object, snap_info)

    def project_provider_point_to_host(self, point, host_wall):
        return project_provider_point_to_host(point, host_wall)


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
    if _provider_runtime_api(session).plan_provider_integrations_disabled():
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
    host_kind, host_obj = plan_provider_payloads.unpack_provider_host_target_ref(host_target)
    if host_obj is None:
        host_target = normalize_provider_point_host_target(
            session, getattr(tool, "default_host_target", ())
        )
        host_kind, host_obj = plan_provider_payloads.unpack_provider_host_target_ref(host_target)
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
    payload = build_provider_point_tool_payload(
        session,
        tool,
        raw_point=point,
        plan_point=plan_point,
        snap_object=obj,
        snap_info=snap_info,
    )
    _provider_runtime_api(session).execute_plan_provider_action(
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
    payload_context = plan_provider_action_payloads.build_provider_action_payload_context(
        session,
        snap_object=obj,
        snap_info=snap_info,
    )
    host_target, host_source = get_provider_point_payload_host_target(
        session,
        snap_target=payload_context.snap_target,
        selected_target=payload_context.selected_target,
        selected_targets=payload_context.selected_targets,
        hovered_target=payload_context.hovered_target,
    )
    host_kind, host_obj = plan_provider_payloads.unpack_provider_host_target_ref(host_target)
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
    return plan_provider_action_payloads.get_provider_snap_info()


def resolve_provider_point_snap_object(session, snap_object, snap_info):
    return plan_provider_action_payloads.resolve_provider_snap_object(
        session,
        snap_object,
        snap_info,
    )


def normalize_provider_point_host_target(session, target):
    return plan_provider_action_payloads.normalize_provider_wall_host_target(session, target)


def get_provider_point_context_host_state(session):
    return plan_provider_action_payloads.get_provider_context_host_state(
        session,
        selected_target=session.selection.state.get_selected_plan_target(),
        hovered_target=session.selection.hover.get_hovered_plan_target(),
    )


def get_provider_point_payload_host_target(
    session,
    *,
    snap_target,
    selected_target,
    selected_targets,
    hovered_target,
):
    state = _provider_point_state(session)
    return plan_provider_action_payloads.get_provider_point_host_target(
        session,
        snap_target=snap_target,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
        stored_target=state.provider_point_host_target,
        stored_source=state.provider_point_host_source,
    )


def project_provider_point_to_host(point, host_wall):
    return plan_provider_action_payloads.project_provider_point_to_host(point, host_wall)


def build_provider_point_tool_payload(
    session,
    tool,
    *,
    raw_point,
    plan_point,
    snap_object,
    snap_info,
):
    payload_context = plan_provider_action_payloads.build_provider_action_payload_context(
        session,
        snap_object=snap_object,
        snap_info=snap_info,
    )
    host_target, host_source = get_provider_point_payload_host_target(
        session,
        snap_target=payload_context.snap_target,
        selected_target=payload_context.selected_target,
        selected_targets=payload_context.selected_targets,
        hovered_target=payload_context.hovered_target,
    )
    host_kind, host_obj = plan_provider_payloads.unpack_provider_host_target_ref(host_target)
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
        snap_info=payload_context.snap_info,
        snap_object=payload_context.snap_object,
        snap_target=payload_context.snap_target,
        snap_document_name=payload_context.snap_document_name,
        snap_object_name=payload_context.snap_object_name,
        snap_component=payload_context.snap_component,
        snap_subname=payload_context.snap_subname,
        selected_target=payload_context.selected_target,
        selected_targets=payload_context.selected_targets,
        hovered_target=payload_context.hovered_target,
        host_target=host_target,
        host_source=host_source,
    )
