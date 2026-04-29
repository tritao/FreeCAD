# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft snap profile helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui


def _get_snapper():
    return getattr(FreeCADGui, "Snapper", None)


def _get_snapper_method(method_name):
    snapper = _get_snapper()
    if not snapper:
        return None
    method = getattr(snapper, method_name, None)
    return method if callable(method) else None


def apply_plan_snap_profile(snap_modes):
    push_snap_modes = _get_snapper_method("push_snap_modes")
    if push_snap_modes is None:
        return
    try:
        push_snap_modes(snap_modes)
    except Exception:
        pass


def restore_snap_profile():
    pop_snap_modes = _get_snapper_method("pop_snap_modes")
    if pop_snap_modes is None:
        return
    try:
        pop_snap_modes()
    except Exception:
        pass


def push_opening_move_snap_profile(session, snap_modes):
    if session.opening_transient_state.opening_move_snap_profile_pushed:
        return
    push_snap_modes = _get_snapper_method("push_snap_modes")
    if push_snap_modes is None:
        return
    try:
        push_snap_modes(snap_modes)
        session.opening_transient_state.opening_move_snap_profile_pushed = True
    except Exception:
        pass


def pop_opening_move_snap_profile(session):
    if not session.opening_transient_state.opening_move_snap_profile_pushed:
        return
    pop_snap_modes = _get_snapper_method("pop_snap_modes")
    if pop_snap_modes is None:
        return
    try:
        pop_snap_modes()
    except Exception:
        pass
    session.opening_transient_state.opening_move_snap_profile_pushed = False


def set_active_draft_command(command):
    FreeCAD.activeDraftCommand = command


def clear_active_draft_command():
    FreeCAD.activeDraftCommand = None


def stop_snapper():
    snapper = _get_snapper()
    if not snapper:
        return
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    _set_toolbar_point_focus_suppressed(toolbar, False)
    try:
        snapper.getPoint()
        snapper.off()
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def set_point_focus_suppressed(suppressed):
    toolbar = getattr(FreeCADGui, "draftToolBar", None)
    if not toolbar:
        return
    _set_toolbar_point_focus_suppressed(toolbar, bool(suppressed))


def _set_toolbar_point_focus_suppressed(toolbar, suppressed):
    if toolbar is None:
        return
    set_focus_suppressed = getattr(toolbar, "setPointFocusSuppressed", None)
    if callable(set_focus_suppressed):
        try:
            set_focus_suppressed(bool(suppressed))
        except (AttributeError, RuntimeError, TypeError):
            pass
        return
    if getattr(toolbar, "suppress_point_focus", None) is not None:
        try:
            toolbar.suppress_point_focus = bool(suppressed)
        except (AttributeError, RuntimeError, TypeError):
            pass


class PlanSnapAPI:
    """Owned session surface for Plan Edit snap-profile behavior."""

    __slots__ = ("_session", "_plan_snap_modes", "_opening_move_snap_modes")

    def __init__(self, session, plan_snap_modes, opening_move_snap_modes):
        self._session = session
        self._plan_snap_modes = tuple(plan_snap_modes or ())
        self._opening_move_snap_modes = tuple(opening_move_snap_modes or ())

    @property
    def session(self):
        return self._session

    def apply_plan_snap_profile(self):
        return apply_plan_snap_profile(self._plan_snap_modes)

    def restore_snap_profile(self):
        return restore_snap_profile()

    def push_opening_move_snap_profile(self):
        return push_opening_move_snap_profile(self.session, self._opening_move_snap_modes)

    def pop_opening_move_snap_profile(self):
        return pop_opening_move_snap_profile(self.session)

    def set_active_draft_command(self):
        return set_active_draft_command(self.session)

    def clear_active_draft_command(self):
        return clear_active_draft_command()

    def stop_snapper(self):
        return stop_snapper()

    def set_point_focus_suppressed(self, suppressed):
        return set_point_focus_suppressed(suppressed)
