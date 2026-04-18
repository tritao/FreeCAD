# SPDX-License-Identifier: LGPL-2.1-or-later

"""Draft snap profile helpers for BIM Plan Edit."""

import FreeCADGui


def _get_snapper():
    return getattr(FreeCADGui, "Snapper", None)


def apply_plan_snap_profile(snap_modes):
    snapper = _get_snapper()
    if not snapper or not hasattr(snapper, "push_snap_modes"):
        return
    try:
        snapper.push_snap_modes(snap_modes)
    except Exception:
        pass


def restore_snap_profile():
    snapper = _get_snapper()
    if not snapper or not hasattr(snapper, "pop_snap_modes"):
        return
    try:
        snapper.pop_snap_modes()
    except Exception:
        pass


def push_opening_move_snap_profile(session, snap_modes):
    snapper = _get_snapper()
    if (
        session._opening_move_snap_profile_pushed
        or not snapper
        or not hasattr(snapper, "push_snap_modes")
    ):
        return
    try:
        snapper.push_snap_modes(snap_modes)
        session._opening_move_snap_profile_pushed = True
    except Exception:
        pass


def pop_opening_move_snap_profile(session):
    snapper = _get_snapper()
    if (
        not session._opening_move_snap_profile_pushed
        or not snapper
        or not hasattr(snapper, "pop_snap_modes")
    ):
        return
    try:
        snapper.pop_snap_modes()
    except Exception:
        pass
    session._opening_move_snap_profile_pushed = False
