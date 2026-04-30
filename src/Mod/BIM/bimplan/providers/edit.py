# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider edit interaction helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimplan.providers import action_payloads as plan_provider_action_payloads
from bimplan.providers.actions import execute_plan_provider_action
from bimplan.providers import builtin_edit as plan_provider_builtin_edit
from bimplan.providers import payloads as plan_provider_payloads
from bimplan.providers import PlanToolInteraction
from bimplan.providers.runtime import get_plan_provider_edit_handles
from bimplan.providers.targets import (
    get_plan_provider_target_for_object,
    is_plan_provider_target_object,
)
from bimplan.runtime import tools as plan_runtime_tools

translate = FreeCAD.Qt.translate


class ProviderMoveTool(plan_runtime_tools.PlanToolHandler):
    """Keyboard behavior for active provider handle movement."""

    tool_id = plan_runtime_tools.PlanTool.MOVE_PROVIDER

    def on_key(self, key, event_callback, coin):
        del event_callback
        if key != coin.SoKeyboardEvent.ESCAPE:
            return False
        return self.cancel()

    def cancel(self):
        cancel_provider_handle_point_pick(self.session)
        return True


class PlanProviderEditingAPI:
    """Owned provider edit surface for Plan Edit interaction code."""

    __slots__ = ("_session", "__dict__")

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def get_selected_provider_edit_handles(self, provider_obj):
        return get_selected_provider_edit_handles(self.session, provider_obj)

    def activate_provider_handle(self, provider_obj, handle_index):
        return activate_provider_handle(self.session, provider_obj, handle_index)

    def activate_provider_handle_now(self, provider_obj, handle_index):
        return activate_provider_handle_now(self.session, provider_obj, handle_index)

    def finish_provider_handle_point_pick(self, point=None, obj=None):
        return finish_provider_handle_point_pick(self.session, point=point, obj=obj)

    def cancel_provider_handle_point_pick(self):
        return cancel_provider_handle_point_pick(self.session)


def get_selected_provider_edit_handles(session, provider_obj):
    if provider_obj is None:
        return []
    selected_provider = session.selection.state.get_selected_plan_target_object("provider")
    editing_provider = session.interaction_state.edit_provider
    if provider_obj != selected_provider and provider_obj != editing_provider:
        return []
    provider_target = get_plan_provider_target_for_object(session, provider_obj)
    if provider_target is None:
        return []
    provider_id = str(getattr(provider_target, "provider_id", "") or "").strip()
    target_key = str(getattr(provider_target, "key", "") or "").strip()
    handles = []
    for handle in tuple(get_plan_provider_edit_handles(session) or ()):
        if str(getattr(handle, "provider_id", "") or "").strip() != provider_id:
            continue
        handle_target_key = str(getattr(handle, "target_key", "") or "").strip()
        if handle_target_key and handle_target_key != target_key:
            continue
        handles.append(handle)
    if handles:
        return handles
    return plan_provider_builtin_edit.get_builtin_provider_edit_handles(
        session,
        provider_obj,
        provider_target,
    )


def can_move_provider_target_by_placement(session, provider_obj):
    return plan_provider_builtin_edit.can_move_provider_target_by_placement(
        session,
        provider_obj,
    )


def can_rehost_provider_target(session, provider_obj, host_obj=None):
    return plan_provider_builtin_edit.can_rehost_provider_target(
        session,
        provider_obj,
        host_obj=host_obj,
    )


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
        handled = execute_plan_provider_action(
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
    session.current_tool = plan_runtime_tools.PlanTool.MOVE_PROVIDER
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
    session.snap.set_active_draft_command()
    session.snap.set_point_focus_suppressed(True)
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
    session.snap.clear_active_draft_command()

    if point is None or provider_obj is None:
        session.current_tool = plan_runtime_tools.PlanTool.SELECT
        restore_selected_provider(session, provider_obj)
        return

    if handle is None:
        session.current_tool = plan_runtime_tools.PlanTool.SELECT
        restore_selected_provider(session, provider_obj)
        return
    target_point = _resolve_provider_handle_target_point(session, provider_obj, point)
    if target_point is None:
        session.current_tool = plan_runtime_tools.PlanTool.SELECT
        restore_selected_provider(session, provider_obj)
        return

    action_key = str(getattr(handle, "action_key", "") or "").strip()
    provider_id = str(getattr(handle, "provider_id", "") or "").strip()
    session.current_tool = plan_runtime_tools.PlanTool.SELECT
    payload = _build_provider_handle_payload(
        session,
        provider_obj,
        handle,
        point=target_point,
        raw_point=point,
        snap_object=obj,
    )
    if action_key and provider_id:
        if execute_plan_provider_action(
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

    try:
        with session.document_visuals.defer_document_visual_updates():
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
    session.snap.stop_snapper()
    session.snap.clear_active_draft_command()
    session.current_tool = plan_runtime_tools.PlanTool.SELECT
    if provider_obj is not None:
        restore_selected_provider(session, provider_obj)
        return
    session.selection.sync.set_gui_selection([])
    session.selection.refresh.refresh_primary_selected_plan_target()


def restore_selected_provider(session, provider_obj):
    session.current_tool = plan_runtime_tools.PlanTool.SELECT
    if provider_obj is not None and is_plan_provider_target_object(session, provider_obj):
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


def _resolve_provider_handle_target_point(session, provider_obj, point):
    target_point = FreeCAD.Vector(point) if point is not None else None
    if target_point is None:
        return None
    start_point = plan_provider_builtin_edit.get_provider_move_point(session, provider_obj)
    if start_point is None:
        return target_point
    return FreeCAD.Vector(target_point.x, target_point.y, start_point.z)


def _build_provider_handle_payload(
    session, provider_obj, handle, *, point, raw_point, snap_object=None
):
    provider_target = get_plan_provider_target_for_object(session, provider_obj)
    payload_context = plan_provider_action_payloads.build_provider_action_payload_context(
        session,
        snap_object=snap_object,
        snap_info=plan_provider_action_payloads.get_provider_snap_info(),
    )
    host_target, host_source = _get_provider_handle_payload_host_target(
        session,
        handle,
        snap_target=payload_context.snap_target,
        selected_target=payload_context.selected_target,
        selected_targets=payload_context.selected_targets,
        hovered_target=payload_context.hovered_target,
    )
    host_kind, host_obj = plan_provider_payloads.unpack_provider_host_target_ref(host_target)
    placement_point = (
        plan_provider_action_payloads.project_provider_point_to_host(point, host_obj)
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
        snap_info=payload_context.snap_info,
        snap_object=payload_context.snap_object,
        snap_target=payload_context.snap_target,
        snap_document_name=payload_context.snap_document_name,
        snap_object_name=payload_context.snap_object_name,
        snap_component=payload_context.snap_component,
        snap_subname=payload_context.snap_subname,
        target_object=provider_obj,
        provider_target=provider_target,
        target_key=str(getattr(provider_target, "key", "") or "").strip(),
        target_provider_id=str(getattr(provider_target, "provider_id", "") or "").strip(),
        selected_target=payload_context.selected_target,
        selected_targets=payload_context.selected_targets,
        hovered_target=payload_context.hovered_target,
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
        return plan_provider_action_payloads.get_provider_rehost_host_target(
            session,
            snap_target=snap_target,
            selected_target=selected_target,
            selected_targets=selected_targets,
            hovered_target=hovered_target,
        )
    state = getattr(session, "provider_point_state", None)
    return plan_provider_action_payloads.get_provider_point_host_target(
        session,
        snap_target=snap_target,
        selected_target=selected_target,
        selected_targets=selected_targets,
        hovered_target=hovered_target,
        stored_target=getattr(state, "provider_point_host_target", None),
        stored_source=getattr(state, "provider_point_host_source", ""),
    )


def _apply_builtin_provider_handle_action(session, provider_obj, handle, payload):
    return plan_provider_builtin_edit.apply_builtin_provider_handle_action(
        session,
        provider_obj,
        handle,
        payload,
    )
