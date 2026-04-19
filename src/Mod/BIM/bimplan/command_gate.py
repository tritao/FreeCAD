# SPDX-License-Identifier: LGPL-2.1-or-later

"""Command gating while BIM Plan Edit owns viewport interaction."""

import os

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate

ALLOW_EXTERNAL_COMMANDS_ENV = "FC_BIM_PLAN_EDIT_ALLOW_EXTERNAL_COMMANDS"

BLOCKED_COMMANDS = (
    "Arch_Window",
    "BIM_Door",
    "BIM_Windows",
    "Arch_Wall",
    "Arch_Space",
    "Draft_Edit",
    "Draft_Line",
    "Draft_Wire",
    "Draft_Rectangle",
    "Draft_Circle",
    "Draft_Arc",
    "Draft_Arc_3Points",
    "Draft_BSpline",
    "Draft_BezCurve",
    "Draft_CubicBezCurve",
    "Draft_Move",
    "Draft_Rotate",
    "Draft_Trimex",
    "Draft_Offset",
    "Draft_Stretch",
)

_active_session = None
_saved_action_states = {}
_disabled_action_callbacks = {}
_refresh_queued = False


def _external_commands_allowed():
    value = os.environ.get(ALLOW_EXTERNAL_COMMANDS_ENV, "")
    return value.lower() in {"1", "true", "yes", "on"}


def active_session():
    return _active_session


def blocked_commands():
    return BLOCKED_COMMANDS


def is_command_blocked(command_name):
    if _external_commands_allowed():
        return False
    return _active_session is not None and command_name in BLOCKED_COMMANDS


def warn_blocked(command_name):
    FreeCAD.Console.PrintWarning(
        translate(
            "BIM_PlanEdit",
            "{command} is disabled while BIM Plan Edit is active. "
            "Use the Plan Edit task-panel tools or leave Plan Edit first.\n",
        ).format(command=command_name)
    )


def install(session):
    global _active_session

    if _active_session is not None and _active_session is not session:
        uninstall(_active_session)
    _active_session = session
    if _external_commands_allowed():
        return
    refresh()
    refresh_later()


def refresh():
    if _active_session is None or _external_commands_allowed():
        return
    for command_name in BLOCKED_COMMANDS:
        for action in _find_command_actions(command_name):
            _disable_action(command_name, action)


def refresh_later():
    global _refresh_queued

    if _refresh_queued:
        return
    try:
        from PySide import QtCore
    except Exception:
        return

    _refresh_queued = True

    def _run_refresh():
        global _refresh_queued

        _refresh_queued = False
        refresh()

    for delay in (0, 50, 250):
        try:
            QtCore.QTimer.singleShot(delay, _run_refresh)
        except Exception:
            pass


def uninstall(session=None):
    global _active_session, _refresh_queued

    if session is not None and _active_session is not None and _active_session is not session:
        return
    _disconnect_actions()
    _restore_actions()
    _active_session = None
    _refresh_queued = False


def _main_window():
    try:
        return FreeCADGui.getMainWindow()
    except Exception:
        return None


def _find_command_actions(command_name):
    from PySide import QtGui

    actions = []
    try:
        command = FreeCADGui.Command.get(command_name)
    except Exception:
        command = None
    if command is not None:
        try:
            actions.extend(command.getAction())
        except Exception:
            pass

    main_window = _main_window()
    if main_window is None:
        return _unique_actions(actions)

    try:
        actions.extend(main_window.findChildren(QtGui.QAction, command_name))
    except Exception:
        pass
    if not actions:
        try:
            action = main_window.findChild(QtGui.QAction, command_name)
        except Exception:
            action = None
        if action is not None:
            actions.append(action)

    return _unique_actions(actions)


def _unique_actions(actions):
    seen = set()
    unique_actions = []
    for action in actions:
        action_key = id(action)
        if action_key in seen:
            continue
        seen.add(action_key)
        unique_actions.append(action)
    return tuple(unique_actions)


def _disable_action(command_name, action):
    action_key = id(action)
    if action_key not in _saved_action_states:
        try:
            _saved_action_states[action_key] = (action, bool(action.isEnabled()))
        except Exception:
            return
    if action_key not in _disabled_action_callbacks:
        _connect_action_guard(command_name, action)
    try:
        if action.isEnabled():
            action.setEnabled(False)
    except Exception:
        pass


def _connect_action_guard(command_name, action):
    action_key = id(action)

    def _reenforce_disabled_state():
        if not is_command_blocked(command_name):
            return
        try:
            if action.isEnabled():
                action.setEnabled(False)
        except Exception:
            pass

    def _discard_action_state():
        _saved_action_states.pop(action_key, None)
        _disabled_action_callbacks.pop(action_key, None)

    try:
        action.changed.connect(_reenforce_disabled_state)
    except Exception:
        return
    try:
        action.destroyed.connect(_discard_action_state)
    except Exception:
        pass
    _disabled_action_callbacks[action_key] = (
        action,
        _reenforce_disabled_state,
        _discard_action_state,
    )


def _disconnect_actions():
    global _disabled_action_callbacks

    callbacks = _disabled_action_callbacks
    _disabled_action_callbacks = {}
    for action, changed_callback, destroyed_callback in callbacks.values():
        try:
            action.changed.disconnect(changed_callback)
        except Exception:
            pass
        try:
            action.destroyed.disconnect(destroyed_callback)
        except Exception:
            pass


def _restore_actions():
    global _saved_action_states

    saved_states = _saved_action_states
    _saved_action_states = {}
    for action, enabled in saved_states.values():
        try:
            action.setEnabled(bool(enabled))
        except Exception:
            pass
