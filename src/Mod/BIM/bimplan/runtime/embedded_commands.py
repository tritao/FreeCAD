# SPDX-License-Identifier: LGPL-2.1-or-later

"""Embedded Draft command lifetime for BIM Plan Edit."""

from draftguitools import gui_base

from bimplan.selection import target_dispatch as plan_target_dispatch
from bimplan.selection import target_kinds as plan_target_kinds


class PlanEmbeddedToolsAPI:
    """Owned session surface for embedded Draft-style command lifetime."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def on_command_started(self, tool_name, command=None):
        return on_command_started(self.session, tool_name, command=command)

    def on_command_finished(self, tool_name, command=None):
        return on_command_finished(self.session, tool_name, command=command)

    def start(self, tool_name, command, host_class=None):
        return start(self.session, tool_name, command, host_class=host_class)

    def has_active(self):
        return has_active(self.session)

    def cancel(self, tool_name=None):
        return cancel(self.session, tool_name=tool_name)

    def clear_state(self):
        return clear_state(self.session)

    def discard_runtime_references(self):
        return clear_state(self.session)


class _PlanEditWallHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for wall creation inside Plan Edit."""

    def __init__(self, session, command=None):
        super().__init__(command)
        self.session = session

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session.embedded_tools.on_command_started("Wall", command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session.embedded_tools.on_command_finished("Wall", command or self.command)

    def get_working_plane(self):
        return self.session.viewport.get_interaction_plane()

    def get_interaction_plane(self):
        return self.session.viewport.get_interaction_plane()

    def request_point(
        self,
        callback,
        move_callback=None,
        last=None,
        title=None,
        mode=None,
        extra_widget=None,
        hints=None,
        modifier_resolver=None,
    ):
        del extra_widget
        super().request_point(
            callback=callback,
            move_callback=move_callback,
            last=last,
            title=title,
            mode=mode,
            extra_widget=None,
            hints=hints,
            modifier_resolver=modifier_resolver,
        )

    def clear_ui_state(self):
        return

    def reset_edit(self):
        return

    def show_continue(self):
        return

    def continue_mode_enabled(self):
        return False

    def continue_wall_chain_enabled(self):
        return True

    def supports_extra_widget(self):
        return False

    def resolve_point_request_modifiers(self, ctrl, shift, alt):
        del alt
        return ctrl, False

    def default_ortho_enabled(self):
        return True

    def free_angle_override_active(self):
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ShiftModifier)
        except Exception:
            return False

    def on_created_object(self, obj):
        self.session.visibility.register_plan_object(obj)


class _PlanEditCommandHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for modifiers used inside Plan Edit."""

    def __init__(self, session, tool_name, command=None):
        super().__init__(command)
        self.session = session
        self.tool_name = tool_name

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session.embedded_tools.on_command_started(self.tool_name, command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session.embedded_tools.on_command_finished(self.tool_name, command or self.command)

    def continue_mode_enabled(self):
        return False


def on_command_started(session, tool_name, command=None):
    if session.lifecycle_state.tearing_down:
        return
    session.interaction_state.embedded_tool_name = tool_name
    if command is not None:
        session.interaction_state.embedded_tool = command
    session.current_tool = tool_name
    session.overlays.openings.sync_selected_wall_opening_context_overlay()
    session.task_panels.refresh_task_panel_status()


def on_command_finished(session, tool_name, command=None):
    if session.lifecycle_state.tearing_down:
        return
    interaction_state = session.interaction_state
    if command is None or interaction_state.embedded_tool is command:
        interaction_state.embedded_host = None
        interaction_state.embedded_tool = None
        interaction_state.embedded_tool_name = None
    if session.current_tool == tool_name:
        from bimplan.runtime import tools as plan_runtime_tools

        session.current_tool = plan_runtime_tools.PlanTool.SELECT
        session.overlays.openings.sync_selected_wall_opening_context_overlay()
        session.task_panels.refresh_task_panel_status()


def start(session, tool_name, command, host_class=None):
    interaction_state = session.interaction_state
    session.current_tool = tool_name
    plan_target_dispatch.clear_hovered_targets(
        session,
        kinds=plan_target_kinds.EMBEDDED_TOOL_CLEAR_HOVERED_KINDS,
    )
    session.overlays.spaces.sync_secondary_selected_overlays()
    session.task_panels.refresh_task_panel_status()
    interaction_state.embedded_tool = command
    interaction_state.embedded_tool_name = tool_name
    host_class = _PlanEditCommandHost if host_class is None else host_class
    if host_class is _PlanEditWallHost:
        interaction_state.embedded_host = host_class(session, command)
    else:
        interaction_state.embedded_host = host_class(session, tool_name, command)
    command.Activated(host=interaction_state.embedded_host)


def cancel(session, tool_name=None):
    interaction_state = session.interaction_state
    if session.lifecycle_state.tearing_down or interaction_state.embedded_tool is None:
        return
    if tool_name is not None and interaction_state.embedded_tool_name != tool_name:
        return
    tool = interaction_state.embedded_tool
    cancel_interactive = getattr(tool, "cancel_interactive", None)
    if callable(cancel_interactive):
        try:
            cancel_interactive()
            return
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass
    finish = getattr(tool, "finish", None)
    if callable(finish):
        try:
            finish(cont=False)
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass


def has_active(session):
    return session.interaction_state.embedded_tool is not None


def clear_state(session):
    interaction_state = session.interaction_state
    interaction_state.embedded_host = None
    interaction_state.embedded_tool = None
    interaction_state.embedded_tool_name = None
