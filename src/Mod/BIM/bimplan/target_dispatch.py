# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target-kind dispatch helpers for BIM Plan Edit."""

from bimplan import target_kinds as plan_target_kinds

_TARGET_VALIDATOR_NAMES = {
    plan_target_kinds.PLAN_TARGET_WALL: "_is_plan_selectable_wall",
    plan_target_kinds.PLAN_TARGET_OPENING: "_is_hosted_opening_object",
    plan_target_kinds.PLAN_TARGET_SYMBOL: "_is_plan_symbol_instance",
    plan_target_kinds.PLAN_TARGET_PROVIDER: "_is_plan_provider_target_object",
    plan_target_kinds.PLAN_TARGET_SPACE: "_is_plan_space_object",
    plan_target_kinds.PLAN_TARGET_REGION: "_is_plan_region_object",
}

_QUEUE_RESTORE_METHOD_NAMES = {
    plan_target_kinds.PLAN_TARGET_OPENING: "_queue_restore_selected_opening",
    plan_target_kinds.PLAN_TARGET_SYMBOL: "_queue_restore_selected_symbol",
    plan_target_kinds.PLAN_TARGET_SPACE: "_queue_restore_selected_space",
    plan_target_kinds.PLAN_TARGET_REGION: "_queue_restore_selected_region",
}

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

_SELECTED_VISUAL_SYNC_SPECS = {
    plan_target_kinds.PLAN_TARGET_WALL: {
        "label": "wall_overlay",
        "methods": (("sync_selected_wall_overlay", "_sync_selected_wall_overlay"),),
    },
    plan_target_kinds.PLAN_TARGET_OPENING: {
        "label": "opening_overlay",
        "methods": (
            ("sync_selected_opening_overlay", "_sync_selected_opening_overlay"),
            ("sync_selected_opening_handles", "_sync_selected_opening_handles"),
        ),
    },
    plan_target_kinds.PLAN_TARGET_SYMBOL: {
        "label": "symbol_overlay",
        "methods": (
            ("sync_selected_symbol_overlay", "_sync_selected_symbol_overlay"),
            ("sync_selected_symbol_handles", "_sync_selected_symbol_handles"),
        ),
    },
    plan_target_kinds.PLAN_TARGET_PROVIDER: {
        "label": "provider_overlay",
        "methods": (
            ("sync_selected_provider_overlay", "_sync_selected_provider_overlay"),
            ("sync_selected_provider_handles", "_sync_selected_provider_handles"),
        ),
    },
    plan_target_kinds.PLAN_TARGET_SPACE: {
        "label": "space_overlay",
        "methods": (("sync_selected_space_overlay", "_sync_selected_space_overlay"),),
    },
    plan_target_kinds.PLAN_TARGET_REGION: {
        "label": "region_overlay",
        "methods": (("sync_selected_region_overlay", "_sync_selected_region_overlay"),),
    },
}

_HOVER_VISUAL_SYNC_SPECS = {
    plan_target_kinds.PLAN_TARGET_WALL: {
        "label": "wall_overlay",
        "methods": (("sync_hovered_wall_overlay", "_sync_hovered_wall_overlay"),),
    },
    plan_target_kinds.PLAN_TARGET_OPENING: {
        "label": "opening_overlay",
        "methods": (("sync_hovered_opening_overlay", "_sync_hovered_opening_overlay"),),
    },
    plan_target_kinds.PLAN_TARGET_SYMBOL: {
        "label": "symbol_overlay",
        "methods": (("sync_hovered_symbol_overlay", "_sync_hovered_symbol_overlay"),),
    },
    plan_target_kinds.PLAN_TARGET_PROVIDER: {
        "label": "provider_overlay",
        "methods": (("sync_hovered_provider_overlay", "_sync_hovered_provider_overlay"),),
    },
    plan_target_kinds.PLAN_TARGET_SPACE: {
        "label": "space_overlay",
        "methods": (("sync_hovered_space_overlay", "_sync_hovered_space_overlay"),),
    },
    plan_target_kinds.PLAN_TARGET_REGION: {
        "label": "region_overlay",
        "methods": (("sync_hovered_region_overlay", "_sync_hovered_region_overlay"),),
    },
}

_HOVER_TARGET_SET_SYNC_SPECS = {
    plan_target_kinds.PLAN_TARGET_OPENING: (
        (
            "sync_selected_wall_opening_context_overlay",
            "_sync_selected_wall_opening_context_overlay",
        ),
        ("sync_hovered_opening_overlay", "_sync_hovered_opening_overlay"),
    ),
    plan_target_kinds.PLAN_TARGET_SYMBOL: (
        ("sync_hovered_symbol_overlay", "_sync_hovered_symbol_overlay"),
    ),
    plan_target_kinds.PLAN_TARGET_PROVIDER: (
        ("sync_hovered_provider_overlay", "_sync_hovered_provider_overlay"),
    ),
    plan_target_kinds.PLAN_TARGET_SPACE: (
        ("sync_hovered_space_overlay", "_sync_hovered_space_overlay"),
    ),
    plan_target_kinds.PLAN_TARGET_REGION: (
        ("sync_hovered_region_overlay", "_sync_hovered_region_overlay"),
    ),
}

_GET_HOVERED_TARGET_ORDER = (
    plan_target_kinds.PLAN_TARGET_OPENING,
    plan_target_kinds.PLAN_TARGET_PROVIDER,
    plan_target_kinds.PLAN_TARGET_SYMBOL,
    plan_target_kinds.PLAN_TARGET_WALL,
    plan_target_kinds.PLAN_TARGET_REGION,
    plan_target_kinds.PLAN_TARGET_SPACE,
)


def _call_named_method(session, method_name, trace_name=None):
    method = getattr(session, method_name, None)
    if not callable(method):
        return
    if trace_name:
        with session._plan_perf_trace_span(trace_name):
            method()
        return
    method()


def _call_named_methods(session, method_names):
    for method_name in method_names or ():
        _call_named_method(session, method_name)


def _call_sync_specs(session, sync_specs, trace_style=None, trace_prefix=None, trace_label=None):
    if not sync_specs:
        return
    if trace_style == "by_kind":
        trace_name = None
        if trace_prefix and trace_label:
            trace_name = "{}_{}".format(trace_prefix, trace_label)
        if trace_name:
            with session._plan_perf_trace_span(trace_name):
                for _default_trace_name, method_name in sync_specs:
                    _call_named_method(session, method_name)
            return
    for default_trace_name, method_name in sync_specs:
        _call_named_method(
            session,
            method_name,
            trace_name=default_trace_name if trace_style == "by_method" else None,
        )


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


def validate_plan_target(session, kind, obj):
    validator_name = _TARGET_VALIDATOR_NAMES.get(kind)
    if not validator_name:
        return False
    validator = getattr(session, validator_name, None)
    return bool(callable(validator) and validator(obj))


def queue_restore_selected_target(session, kind, obj):
    if not obj:
        return False
    method_name = _QUEUE_RESTORE_METHOD_NAMES.get(kind)
    if not method_name:
        return False
    method = getattr(session, method_name, None)
    if not callable(method):
        return False
    method(obj)
    return True


def sync_selected_target_visuals(
    session,
    kinds=None,
    *,
    previous_kind=None,
    previous_obj=None,
    force=False,
    trace_style=None,
    trace_prefix=None,
):
    for kind in kinds or plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS:
        spec = _SELECTED_VISUAL_SYNC_SPECS.get(kind)
        if not spec:
            continue
        if (
            not force
            and session.current_tool == "Select"
            and not session._selected_plan_target_changed(previous_kind, previous_obj, kind)
        ):
            continue
        _call_sync_specs(
            session,
            spec.get("methods"),
            trace_style=trace_style,
            trace_prefix=trace_prefix,
            trace_label=spec.get("label"),
        )


def sync_hovered_target_visuals(session, kinds=None, *, trace_style=None, trace_prefix=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        spec = _HOVER_VISUAL_SYNC_SPECS.get(kind)
        if not spec:
            continue
        _call_sync_specs(
            session,
            spec.get("methods"),
            trace_style=trace_style,
            trace_prefix=trace_prefix,
            trace_label=spec.get("label"),
        )


def set_hovered_target(session, kind, obj):
    if kind not in _HOVER_TARGET_SET_SYNC_SPECS:
        return False
    attr_name = _HOVER_TARGET_ATTR_NAMES.get(kind)
    if not attr_name:
        return False
    if session._is_selected_plan_target(kind, obj):
        obj = None
    if getattr(session, attr_name, None) == obj:
        return False
    setattr(session, attr_name, obj)
    _call_sync_specs(session, _HOVER_TARGET_SET_SYNC_SPECS.get(kind))
    return True
