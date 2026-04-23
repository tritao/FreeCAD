# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target-kind dispatch helpers for BIM Plan Edit."""

from bimplan import target_kinds as plan_target_kinds

_HOVER_TARGET_ATTR_NAMES = {
    plan_target_kinds.PLAN_TARGET_WALL: "hovered_wall",
    plan_target_kinds.PLAN_TARGET_OPENING: "hovered_opening",
    plan_target_kinds.PLAN_TARGET_SYMBOL: "hovered_symbol",
    plan_target_kinds.PLAN_TARGET_PROVIDER: "hovered_provider",
    plan_target_kinds.PLAN_TARGET_SPACE: "hovered_space",
    plan_target_kinds.PLAN_TARGET_REGION: "hovered_region",
}

_HOVER_TARGET_SETTER_NAMES = {
    plan_target_kinds.PLAN_TARGET_WALL: "_set_hovered_wall",
    plan_target_kinds.PLAN_TARGET_OPENING: "_set_hovered_opening",
    plan_target_kinds.PLAN_TARGET_SYMBOL: "_set_hovered_symbol",
    plan_target_kinds.PLAN_TARGET_PROVIDER: "_set_hovered_provider",
    plan_target_kinds.PLAN_TARGET_SPACE: "_set_hovered_space",
    plan_target_kinds.PLAN_TARGET_REGION: "_set_hovered_region",
}

_HOVER_VISUAL_CLEARER_NAMES = {
    plan_target_kinds.PLAN_TARGET_WALL: ("_clear_hovered_wall_overlay",),
    plan_target_kinds.PLAN_TARGET_OPENING: ("_clear_hovered_opening_overlay",),
    plan_target_kinds.PLAN_TARGET_SYMBOL: ("_clear_hovered_symbol_overlay",),
    plan_target_kinds.PLAN_TARGET_PROVIDER: ("_clear_hovered_provider_overlay",),
    plan_target_kinds.PLAN_TARGET_SPACE: ("_clear_hovered_space_overlay",),
    plan_target_kinds.PLAN_TARGET_REGION: ("_clear_hovered_region_overlay",),
}

_SELECTED_VISUAL_CLEARER_NAMES = {
    plan_target_kinds.PLAN_TARGET_WALL: ("_clear_selected_wall_overlay",),
    plan_target_kinds.PLAN_TARGET_OPENING: ("_clear_selected_opening_overlay",),
    plan_target_kinds.PLAN_TARGET_SYMBOL: ("_clear_selected_symbol_overlay",),
    plan_target_kinds.PLAN_TARGET_PROVIDER: ("_clear_selected_provider_overlay",),
    plan_target_kinds.PLAN_TARGET_REGION: ("_clear_selected_region_overlay",),
    plan_target_kinds.PLAN_TARGET_SPACE: ("_clear_selected_space_overlay",),
}

_SELECTED_HANDLE_CLEARER_NAMES = {
    plan_target_kinds.PLAN_TARGET_OPENING: ("_clear_selected_opening_handles",),
    plan_target_kinds.PLAN_TARGET_SYMBOL: ("_clear_selected_symbol_handles",),
    plan_target_kinds.PLAN_TARGET_PROVIDER: ("_clear_selected_provider_handles",),
}

_GET_HOVERED_TARGET_ORDER = (
    plan_target_kinds.PLAN_TARGET_OPENING,
    plan_target_kinds.PLAN_TARGET_PROVIDER,
    plan_target_kinds.PLAN_TARGET_SYMBOL,
    plan_target_kinds.PLAN_TARGET_WALL,
    plan_target_kinds.PLAN_TARGET_REGION,
    plan_target_kinds.PLAN_TARGET_SPACE,
)


def _call_named_methods(session, method_names):
    for method_name in method_names or ():
        method = getattr(session, method_name, None)
        if callable(method):
            method()


def get_hovered_target(session):
    for kind in _GET_HOVERED_TARGET_ORDER:
        attr_name = _HOVER_TARGET_ATTR_NAMES.get(kind)
        if not attr_name:
            continue
        obj = getattr(session, attr_name, None)
        if obj is not None:
            return (kind, obj)
    return (None, None)


def clear_hovered_targets(session, kinds=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        setter_name = _HOVER_TARGET_SETTER_NAMES.get(kind)
        if not setter_name:
            continue
        setter = getattr(session, setter_name, None)
        if callable(setter):
            setter(None)


def set_only_hovered_target(session, target_kind, target_obj):
    if target_kind not in _HOVER_TARGET_SETTER_NAMES:
        clear_hovered_targets(session)
        return
    clear_hovered_targets(
        session,
        kinds=tuple(
            kind for kind in plan_target_kinds.HOVERED_PLAN_TARGET_KINDS if kind != target_kind
        ),
    )
    setter = getattr(session, _HOVER_TARGET_SETTER_NAMES[target_kind], None)
    if callable(setter):
        setter(target_obj)


def clear_hovered_target_visuals(session, kinds=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        _call_named_methods(session, _HOVER_VISUAL_CLEARER_NAMES.get(kind))


def clear_selected_target_visuals(session, kinds=None, clear_handle_kinds=None):
    handle_kind_set = set(clear_handle_kinds or ())
    for kind in kinds or plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS:
        _call_named_methods(session, _SELECTED_VISUAL_CLEARER_NAMES.get(kind))
        if kind in handle_kind_set:
            _call_named_methods(session, _SELECTED_HANDLE_CLEARER_NAMES.get(kind))
