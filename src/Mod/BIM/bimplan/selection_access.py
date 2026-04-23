# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection access helpers with component-first fallback."""


def _get_selection_api(session):
    return getattr(session, "selection", None)


def get_selected_plan_target(session):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_selected_plan_target()
    return session._get_selected_plan_target()


def get_selected_plan_targets(session):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_selected_plan_targets()
    return session._get_selected_plan_targets()


def get_selected_plan_target_object(session, kind=None):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_selected_plan_target_object(kind)
    return session._get_selected_plan_target_object(kind)


def get_secondary_selected_plan_targets(session):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.get_secondary_selected_plan_targets()
    return session._get_secondary_selected_plan_targets()


def normalize_gui_object_selection(session, selection):
    selection_api = _get_selection_api(session)
    if selection_api is not None:
        return selection_api.normalize_gui_object_selection(selection)
    return session._normalize_gui_object_selection(selection)
