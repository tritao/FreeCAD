# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target-kind dispatch helpers for BIM Plan Edit."""

from dataclasses import dataclass

from bimplan.selection import target_kinds as plan_target_kinds


@dataclass(frozen=True)
class SyncSpec:
    trace_name: str
    method_name: str


@dataclass(frozen=True)
class TargetKindPolicy:
    validator_name: str | None = None
    queue_restore_method_name: str | None = None
    hovered_attr_name: str | None = None
    hovered_setter_name: str | None = None
    hovered_visual_clearers: tuple[str, ...] = ()
    selected_visual_clearers: tuple[str, ...] = ()
    selected_handle_clearers: tuple[str, ...] = ()
    selected_visual_label: str | None = None
    selected_visual_sync: tuple[SyncSpec, ...] = ()
    hovered_visual_label: str | None = None
    hovered_visual_sync: tuple[SyncSpec, ...] = ()
    hover_set_sync: tuple[SyncSpec, ...] = ()


def _sync_specs(*pairs):
    return tuple(SyncSpec(trace_name, method_name) for trace_name, method_name in pairs)


_TARGET_KIND_POLICIES = {
    plan_target_kinds.PLAN_TARGET_WALL: TargetKindPolicy(
        validator_name="_is_plan_selectable_wall",
        hovered_attr_name="hovered_wall",
        hovered_setter_name="_set_hovered_wall",
        hovered_visual_clearers=("_clear_hovered_wall_overlay",),
        selected_visual_clearers=("_clear_selected_wall_overlay",),
        selected_visual_label="wall_overlay",
        selected_visual_sync=_sync_specs(
            ("sync_selected_wall_overlay", "_sync_selected_wall_overlay"),
        ),
        hovered_visual_label="wall_overlay",
        hovered_visual_sync=_sync_specs(
            ("sync_hovered_wall_overlay", "_sync_hovered_wall_overlay"),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_OPENING: TargetKindPolicy(
        validator_name="_is_hosted_opening_object",
        queue_restore_method_name="_queue_restore_selected_opening",
        hovered_attr_name="hovered_opening",
        hovered_setter_name="_set_hovered_opening",
        hovered_visual_clearers=("_clear_hovered_opening_overlay",),
        selected_visual_clearers=("_clear_selected_opening_overlay",),
        selected_handle_clearers=("_clear_selected_opening_handles",),
        selected_visual_label="opening_overlay",
        selected_visual_sync=_sync_specs(
            ("sync_selected_opening_overlay", "_sync_selected_opening_overlay"),
            ("sync_selected_opening_handles", "_sync_selected_opening_handles"),
        ),
        hovered_visual_label="opening_overlay",
        hovered_visual_sync=_sync_specs(
            ("sync_hovered_opening_overlay", "_sync_hovered_opening_overlay"),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_selected_wall_opening_context_overlay",
                "_sync_selected_wall_opening_context_overlay",
            ),
            ("sync_hovered_opening_overlay", "_sync_hovered_opening_overlay"),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_SYMBOL: TargetKindPolicy(
        validator_name="_is_plan_symbol_instance",
        queue_restore_method_name="_queue_restore_selected_symbol",
        hovered_attr_name="hovered_symbol",
        hovered_setter_name="_set_hovered_symbol",
        hovered_visual_clearers=("_clear_hovered_symbol_overlay",),
        selected_visual_clearers=("_clear_selected_symbol_overlay",),
        selected_handle_clearers=("_clear_selected_symbol_handles",),
        selected_visual_label="symbol_overlay",
        selected_visual_sync=_sync_specs(
            ("sync_selected_symbol_overlay", "_sync_selected_symbol_overlay"),
            ("sync_selected_symbol_handles", "_sync_selected_symbol_handles"),
        ),
        hovered_visual_label="symbol_overlay",
        hovered_visual_sync=_sync_specs(
            ("sync_hovered_symbol_overlay", "_sync_hovered_symbol_overlay"),
        ),
        hover_set_sync=_sync_specs(
            ("sync_hovered_symbol_overlay", "_sync_hovered_symbol_overlay"),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_PROVIDER: TargetKindPolicy(
        validator_name="_is_plan_provider_target_object",
        hovered_attr_name="hovered_provider",
        hovered_setter_name="_set_hovered_provider",
        hovered_visual_clearers=("_clear_hovered_provider_overlay",),
        selected_visual_clearers=("_clear_selected_provider_overlay",),
        selected_handle_clearers=("_clear_selected_provider_handles",),
        selected_visual_label="provider_overlay",
        selected_visual_sync=_sync_specs(
            ("sync_selected_provider_overlay", "_sync_selected_provider_overlay"),
            ("sync_selected_provider_handles", "_sync_selected_provider_handles"),
        ),
        hovered_visual_label="provider_overlay",
        hovered_visual_sync=_sync_specs(
            ("sync_hovered_provider_overlay", "_sync_hovered_provider_overlay"),
        ),
        hover_set_sync=_sync_specs(
            ("sync_hovered_provider_overlay", "_sync_hovered_provider_overlay"),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_SPACE: TargetKindPolicy(
        validator_name="_is_plan_space_object",
        queue_restore_method_name="_queue_restore_selected_space",
        hovered_attr_name="hovered_space",
        hovered_setter_name="_set_hovered_space",
        hovered_visual_clearers=("_clear_hovered_space_overlay",),
        selected_visual_clearers=("_clear_selected_space_overlay",),
        selected_visual_label="space_overlay",
        selected_visual_sync=_sync_specs(
            ("sync_selected_space_overlay", "_sync_selected_space_overlay"),
        ),
        hovered_visual_label="space_overlay",
        hovered_visual_sync=_sync_specs(
            ("sync_hovered_space_overlay", "_sync_hovered_space_overlay"),
        ),
        hover_set_sync=_sync_specs(
            ("sync_hovered_space_overlay", "_sync_hovered_space_overlay"),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_REGION: TargetKindPolicy(
        validator_name="_is_plan_region_object",
        queue_restore_method_name="_queue_restore_selected_region",
        hovered_attr_name="hovered_region",
        hovered_setter_name="_set_hovered_region",
        hovered_visual_clearers=("_clear_hovered_region_overlay",),
        selected_visual_clearers=("_clear_selected_region_overlay",),
        selected_visual_label="region_overlay",
        selected_visual_sync=_sync_specs(
            ("sync_selected_region_overlay", "_sync_selected_region_overlay"),
        ),
        hovered_visual_label="region_overlay",
        hovered_visual_sync=_sync_specs(
            ("sync_hovered_region_overlay", "_sync_hovered_region_overlay"),
        ),
        hover_set_sync=_sync_specs(
            ("sync_hovered_region_overlay", "_sync_hovered_region_overlay"),
        ),
    ),
}

_EMPTY_TARGET_KIND_POLICY = TargetKindPolicy()

_GET_HOVERED_TARGET_ORDER = (
    plan_target_kinds.PLAN_TARGET_OPENING,
    plan_target_kinds.PLAN_TARGET_PROVIDER,
    plan_target_kinds.PLAN_TARGET_SYMBOL,
    plan_target_kinds.PLAN_TARGET_WALL,
    plan_target_kinds.PLAN_TARGET_REGION,
    plan_target_kinds.PLAN_TARGET_SPACE,
)


def _get_target_kind_policy(kind):
    return _TARGET_KIND_POLICIES.get(kind, _EMPTY_TARGET_KIND_POLICY)


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
                for sync_spec in sync_specs:
                    _call_named_method(session, sync_spec.method_name)
            return
    for sync_spec in sync_specs:
        _call_named_method(
            session,
            sync_spec.method_name,
            trace_name=sync_spec.trace_name if trace_style == "by_method" else None,
        )


def get_hovered_target(session):
    for kind in _GET_HOVERED_TARGET_ORDER:
        attr_name = _get_target_kind_policy(kind).hovered_attr_name
        if not attr_name:
            continue
        obj = getattr(session, attr_name, None)
        if obj is not None:
            return (kind, obj)
    return (None, None)


def clear_hovered_targets(session, kinds=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        setter_name = _get_target_kind_policy(kind).hovered_setter_name
        if not setter_name:
            continue
        setter = getattr(session, setter_name, None)
        if callable(setter):
            setter(None)


def set_only_hovered_target(session, target_kind, target_obj):
    policy = _get_target_kind_policy(target_kind)
    if not policy.hovered_setter_name:
        clear_hovered_targets(session)
        return
    clear_hovered_targets(
        session,
        kinds=tuple(
            kind for kind in plan_target_kinds.HOVERED_PLAN_TARGET_KINDS if kind != target_kind
        ),
    )
    setter = getattr(session, policy.hovered_setter_name, None)
    if callable(setter):
        setter(target_obj)


def clear_hovered_target_visuals(session, kinds=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        _call_named_methods(session, _get_target_kind_policy(kind).hovered_visual_clearers)


def clear_selected_target_visuals(session, kinds=None, clear_handle_kinds=None):
    handle_kind_set = set(clear_handle_kinds or ())
    for kind in kinds or plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS:
        policy = _get_target_kind_policy(kind)
        _call_named_methods(session, policy.selected_visual_clearers)
        if kind in handle_kind_set:
            _call_named_methods(session, policy.selected_handle_clearers)


def validate_plan_target(session, kind, obj):
    validator_name = _get_target_kind_policy(kind).validator_name
    if not validator_name:
        return False
    validator = getattr(session, validator_name, None)
    return bool(callable(validator) and validator(obj))


def queue_restore_selected_target(session, kind, obj):
    if not obj:
        return False
    method_name = _get_target_kind_policy(kind).queue_restore_method_name
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
        policy = _get_target_kind_policy(kind)
        if not policy.selected_visual_sync:
            continue
        if (
            not force
            and session.current_tool == "Select"
            and not session._selected_plan_target_changed(previous_kind, previous_obj, kind)
        ):
            continue
        _call_sync_specs(
            session,
            policy.selected_visual_sync,
            trace_style=trace_style,
            trace_prefix=trace_prefix,
            trace_label=policy.selected_visual_label,
        )


def sync_hovered_target_visuals(session, kinds=None, *, trace_style=None, trace_prefix=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        policy = _get_target_kind_policy(kind)
        if not policy.hovered_visual_sync:
            continue
        _call_sync_specs(
            session,
            policy.hovered_visual_sync,
            trace_style=trace_style,
            trace_prefix=trace_prefix,
            trace_label=policy.hovered_visual_label,
        )


def set_hovered_target(session, kind, obj):
    policy = _get_target_kind_policy(kind)
    if not policy.hover_set_sync or not policy.hovered_attr_name:
        return False
    if session._is_selected_plan_target(kind, obj):
        obj = None
    if getattr(session, policy.hovered_attr_name, None) == obj:
        return False
    setattr(session, policy.hovered_attr_name, obj)
    _call_sync_specs(session, policy.hover_set_sync)
    return True
