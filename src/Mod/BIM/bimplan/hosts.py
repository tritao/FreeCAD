# SPDX-License-Identifier: LGPL-2.1-or-later

"""Embedded command hosts for BIM Plan Edit."""

from draftguitools import gui_base


class _PlanEditWallHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for wall creation inside Plan Edit.

    This host overrides the generic interaction policy hooks from
    `DraftInteractionHost` so plan wall creation can:
    - avoid task widgets
    - keep ortho on by default
    - use `Shift` as a temporary free-angle override
    - continue chained wall runs from the last endpoint
    """

    def __init__(self, session, command=None):
        super().__init__(command)
        self.session = session

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session._on_embedded_command_started("Wall", command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session._on_embedded_command_finished("Wall", command or self.command)

    def get_working_plane(self):
        return self.session.get_interaction_plane()

    def get_interaction_plane(self):
        return self.session.get_interaction_plane()

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
        self.session._register_plan_object(obj)


class _PlanEditCommandHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for modifiers used inside Plan Edit."""

    def __init__(self, session, tool_name, command=None):
        super().__init__(command)
        self.session = session
        self.tool_name = tool_name

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session._on_embedded_command_started(self.tool_name, command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session._on_embedded_command_finished(self.tool_name, command or self.command)

    def continue_mode_enabled(self):
        return False
