# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared lifecycle helpers for BIM Plan Edit."""

import FreeCAD
from bimplan.runtime import command_gate as plan_command_gate
from bimplan.selection import targets as plan_targets
from bimplan.selection import kinds as plan_target_kinds

translate = FreeCAD.Qt.translate


def _provider_point_api(session):
    providers = getattr(session, "providers", None)
    return getattr(providers, "point", providers)


def _overlay_runtime_api(session):
    overlays = getattr(session, "overlays", None)
    return getattr(overlays, "runtime", overlays)


def _cancel_provider_point_tool(session, refresh=True):
    cancel = getattr(_provider_point_api(session), "cancel_provider_point_tool", None)
    if callable(cancel):
        return bool(cancel(refresh=refresh))
    return False


def _has_active_provider_point_tool(session):
    has_active = getattr(_provider_point_api(session), "has_active_provider_point_tool", None)
    if callable(has_active):
        return bool(has_active())
    return False


def _cancel_provider_point_for_select(session):
    cancel_for_select = getattr(_provider_point_api(session), "cancel_for_select", None)
    if callable(cancel_for_select):
        return bool(cancel_for_select())
    if not _has_active_provider_point_tool(session):
        return False
    return _cancel_provider_point_tool(session)


class PlanLifecycleAPI:
    """Owned session surface for Plan Edit lifecycle helpers."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def connect_teardown_signal(self, signal):
        return connect_teardown_signal(self.session, signal)

    def connect_teardown_signals(self, QtGui):
        return connect_teardown_signals(self.session, QtGui)

    def disconnect_teardown_signals(self):
        return disconnect_teardown_signals(self.session)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def activate_select_tool(self):
        return activate_select_tool(self.session)

    def cancel_pending_edit(self, *args, **kwargs):
        return cancel_pending_edit(self.session, *args, **kwargs)


def connect_teardown_signal(session, signal):
    try:
        signal.connect(session.begin_teardown)
    except (AttributeError, RuntimeError, TypeError):
        return
    session.lifecycle_state.teardown_signal_sources.append(signal)


def connect_teardown_signals(session, QtGui):
    app = QtGui.QApplication.instance()
    if app:
        connect_teardown_signal(session, app.aboutToQuit)
    main_window = session.viewport.get_main_window()
    if main_window:
        try:
            signal = main_window.mainWindowClosed
        except AttributeError:
            signal = None
        if signal is not None:
            connect_teardown_signal(session, signal)


def disconnect_teardown_signals(session):
    lifecycle_state = session.lifecycle_state
    for signal in lifecycle_state.teardown_signal_sources:
        try:
            signal.disconnect(session.begin_teardown)
        except (TypeError, RuntimeError):
            pass
    lifecycle_state.teardown_signal_sources = []


def discard_runtime_references(session):
    session.viewport.discard_runtime_references()
    session.selection.state.discard_runtime_references()
    session.providers.runtime.discard_runtime_references()
    session.spaces.discard_runtime_references()
    session.wall_edit.discard_runtime_references()
    session.openings.discard_runtime_references()
    session.symbols.discard_runtime_references()
    _overlay_runtime_api(session).discard_runtime_references()
    session.wall_create.discard_runtime_references()
    session.embedded_tools.discard_runtime_references()


def detach_runtime_observers(session):
    session.selection.sync.detach_selection_observer()
    session.document_visuals.detach_document_observer()
    session.viewport.unregister_edit_callbacks()


def _cancel_current_tool_for_finish(session):
    return (
        _provider_point_api(session).cancel_active_tool_for_finish()
        or session.openings.cancel_active_tool_for_finish()
        or session.symbols.cancel_active_tool_for_finish()
        or session.spaces.cancel_active_tool_for_finish()
        or session.windows.cancel_active_tool_for_finish()
    )


def _cancel_finish_fallback(session):
    if _has_active_provider_point_tool(session):
        _cancel_provider_point_tool(session)
        return True
    if session.embedded_tools.has_active():
        session.embedded_tools.cancel()
        return True
    if session.wall_create.has_active_rect_wall_tool():
        session.wall_create.cancel_rect_wall_tool()
        return True
    if session.wall_edit.has_active_wall_edit():
        session.wall_edit.cancel_wall_edit()
        return True
    return False


def _cancel_current_tool_for_begin_teardown(session):
    return (
        _provider_point_api(session).cancel_active_tool_for_teardown()
        or session.openings.cancel_active_tool_for_teardown()
        or session.symbols.cancel_active_tool_for_teardown()
        or session.spaces.cancel_active_tool_for_teardown()
    )


def _cancel_current_tool_for_shutdown(session):
    return (
        _provider_point_api(session).cancel_active_tool_for_shutdown()
        or session.openings.cancel_active_tool_for_shutdown()
        or session.symbols.cancel_active_tool_for_shutdown()
        or session.spaces.cancel_active_tool_for_shutdown()
        or session.windows.cancel_active_tool_for_shutdown()
    )


def _cleanup_begin_teardown(session):
    session.viewport.clear_viewport_status_chip()
    session.status_text.clear_input_hints()
    session.embedded_tools.cancel()
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.windows.cancel_window_tool(refresh=False)
    session.spaces.cancel_plan_region_tool(refresh=False)
    _cancel_provider_point_tool(session, refresh=False)
    session.wall_edit.cancel_wall_edit(restore=False, refresh=False)
    cancel_pending_edit(session, restore_wall_visibility=False)
    _cancel_current_tool_for_begin_teardown(session)
    _overlay_runtime_api(session).clear_begin_teardown_visuals()
    detach_runtime_observers(session)


def _cleanup_shutdown(session, *, teardown=False):
    session.viewport.clear_viewport_status_chip()
    session.status_text.clear_input_hints()
    session.embedded_tools.cancel()
    session.wall_create.cancel_rect_wall_tool(refresh=False)
    session.spaces.cancel_space_separator_tool(refresh=False)
    session.wall_edit.cancel_wall_edit(restore=not teardown, refresh=False)
    cancel_pending_edit(session, restore_wall_visibility=not teardown)
    _cancel_current_tool_for_shutdown(session)
    _overlay_runtime_api(session).clear_shutdown_visuals()
    detach_runtime_observers(session)


def finish(session, close_dialog=True):
    if _cancel_current_tool_for_finish(session):
        return True
    if _cancel_finish_fallback(session):
        return True
    return session.shutdown(close_dialog=close_dialog)


def begin_teardown(session):
    if session.lifecycle_state.tearing_down:
        return
    session.lifecycle_state.tearing_down = True
    disconnect_teardown_signals(session)
    plan_command_gate.uninstall(session)
    _cleanup_begin_teardown(session)


def _call_task_panel_method(panel, method_name):
    try:
        method = getattr(panel, method_name, None)
        if callable(method):
            method()
    except (AttributeError, RuntimeError, TypeError):
        pass


def _close_or_detach_task_panel(panel, *, close_dialog, teardown):
    if not panel:
        return
    _call_task_panel_method(panel, "mark_closed")
    if close_dialog and not teardown:
        _call_task_panel_method(panel, "close")
    else:
        _call_task_panel_method(panel, "detach")


def shutdown(session, close_dialog=True, teardown=False):
    plan_command_gate.uninstall(session)
    if not session.document_visuals.document_is_alive():
        session.begin_teardown()
    teardown = teardown or session.lifecycle_state.tearing_down
    panel = session.task_panel
    session.task_panel = None
    _cleanup_shutdown(session, teardown=teardown)
    _close_or_detach_task_panel(panel, close_dialog=close_dialog, teardown=teardown)
    if not teardown:
        session.viewport.restore_state()
        if session.doc:
            try:
                session.doc.recompute()
            except ReferenceError:
                session.doc = None
            except RuntimeError:
                session.doc = None
        FreeCAD.Console.PrintMessage(translate("BIM_PlanEdit", "Exited BIM Plan Edit mode.\n"))
    return True


def activate_select_tool(session):
    if session.symbols.cancel_active_tool_for_select():
        return
    if session.spaces.cancel_active_tool_for_select():
        return
    if _cancel_provider_point_for_select(session):
        return
    session.embedded_tools.cancel_for_select()
    session.wall_create.cancel_for_select()
    session.windows.cancel_for_select()
    session.spaces.cancel_secondary_tools_for_select()
    session.wall_edit.cancel_for_select()
    session.wall_relations.cancel_for_select()


def _reset_pending_edit_state(
    session,
    *,
    clear_opening_edit=False,
    restore_wall_visibility=True,
):
    session.wall_edit.reset_pending_edit_state(restore_wall_visibility=restore_wall_visibility)
    session.openings.reset_pending_edit_state(clear_edit=clear_opening_edit)
    session.embedded_tools.clear_state()
    session.lifecycle_state.ignore_selection_changes = False


def cancel_pending_edit(session, *, restore_wall_visibility=True):
    if session.lifecycle_state.tearing_down:
        _reset_pending_edit_state(
            session,
            restore_wall_visibility=restore_wall_visibility,
        )
        session.wall_relations.clear_plan_relation_status()
        return
    session.snap.stop_snapper()
    session.snap.pop_opening_move_snap_profile()
    session.snap.clear_active_draft_command()
    _reset_pending_edit_state(
        session,
        clear_opening_edit=True,
        restore_wall_visibility=restore_wall_visibility,
    )
    session.wall_relations.clear_plan_relation_status()
    session.overlays.walls.sync_wall_grips()
    plan_targets.sync_selected_target_visuals(
        session,
        kinds=plan_target_kinds.PENDING_EDIT_VISUAL_SYNC_KINDS,
        force=True,
    )
