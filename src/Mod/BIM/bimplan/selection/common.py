# SPDX-License-Identifier: LGPL-2.1-or-later

"""Shared helpers for BIM Plan Edit selection services."""

from . import gui_sync as plan_selection_gui_sync


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


def get_plan_target_state_key(kind, obj):
    if not kind or not obj:
        return None
    return (
        kind,
        getattr(getattr(obj, "Document", None), "Name", None),
        getattr(obj, "Name", None),
    )


def get_plan_target_object_from_state(state_kind, state_obj, kind):
    if state_kind == kind:
        return state_obj
    return None


def normalize_gui_object_selection(selection):
    normalized_selection = []
    seen = set()
    for selected in selection or ():
        if not selected:
            continue
        key = (
            getattr(getattr(selected, "Document", None), "Name", None),
            getattr(selected, "Name", None),
        )
        if key in seen:
            continue
        seen.add(key)
        normalized_selection.append(selected)
    return normalized_selection


def _get_gui_preselection_object(session):
    try:
        import bimplan.selection as plan_selection_pkg
    except Exception:
        plan_selection_pkg = None
    exported = (
        getattr(plan_selection_pkg, "_get_gui_preselection_object", None)
        if plan_selection_pkg is not None
        else None
    )
    if callable(exported) and exported is not _get_gui_preselection_object:
        return exported(session)
    return plan_selection_gui_sync.get_gui_preselection_object(session)


def _clear_gui_preselection():
    return plan_selection_gui_sync.clear_gui_preselection()
