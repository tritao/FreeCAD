# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection access helpers with component-first fallback."""

from . import selection as plan_selection
from . import selection_additive as plan_selection_additive

_MISSING = object()


def _get_selection_api(session):
    return getattr(session, "selection", None)


def _call_legacy_selection_method(session, method_name, *args):
    legacy_method = getattr(session, method_name, None)
    if callable(legacy_method):
        return legacy_method(*args)
    return _MISSING


def get_selected_plan_target(session):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_selected_plan_target()
    legacy_target = _call_legacy_selection_method(session, "_get_selected_plan_target")
    if legacy_target is not _MISSING:
        return legacy_target
    return plan_selection.get_selected_plan_target(session)


def get_selected_plan_targets(session):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_selected_plan_targets()
    legacy_targets = _call_legacy_selection_method(session, "_get_selected_plan_targets")
    if legacy_targets is not _MISSING:
        return legacy_targets
    return plan_selection.get_selected_plan_targets(session)


def get_selected_plan_target_object(session, kind=None):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_selected_plan_target_object(kind)
    legacy_target_object = _call_legacy_selection_method(
        session,
        "_get_selected_plan_target_object",
        kind,
    )
    if legacy_target_object is not _MISSING:
        return legacy_target_object
    return plan_selection.get_selected_plan_target_object(session, kind)


def get_secondary_selected_plan_targets(session):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_secondary_selected_plan_targets()
    legacy_targets = _call_legacy_selection_method(
        session,
        "_get_secondary_selected_plan_targets",
    )
    if legacy_targets is not _MISSING:
        return legacy_targets
    return plan_selection.get_secondary_selected_plan_targets(session)


def normalize_gui_object_selection(session, selection):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.normalize_gui_object_selection(selection)
    del session
    return plan_selection_additive.normalize_gui_object_selection(selection)
