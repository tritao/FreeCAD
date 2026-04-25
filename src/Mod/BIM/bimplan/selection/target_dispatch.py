# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target-kind dispatch helpers for BIM Plan Edit."""

from dataclasses import dataclass
from typing import Any, Callable

from bimplan.selection import target_kinds as plan_target_kinds


@dataclass(frozen=True)
class SyncSpec:
    trace_name: str
    sync: Callable[[Any], None]


@dataclass(frozen=True)
class TargetKindPolicy:
    validate: Callable[[Any, Any], bool] | None = None
    queue_restore: Callable[[Any, Any], None] | None = None
    get_hovered: Callable[[Any], Any] | None = None
    set_hovered: Callable[[Any, Any], None] | None = None
    hovered_visual_clearers: tuple[Callable[[Any], None], ...] = ()
    selected_visual_clearers: tuple[Callable[[Any], None], ...] = ()
    selected_handle_clearers: tuple[Callable[[Any], None], ...] = ()
    selected_visual_label: str | None = None
    selected_visual_sync: tuple[SyncSpec, ...] = ()
    hovered_visual_label: str | None = None
    hovered_visual_sync: tuple[SyncSpec, ...] = ()
    hover_set_sync: tuple[SyncSpec, ...] = ()


def _sync_specs(*pairs):
    return tuple(SyncSpec(trace_name, sync) for trace_name, sync in pairs)


def _get_hovered_wall(session):
    return session.hovered_wall


def _set_hovered_wall_state(session, obj):
    session.hovered_wall = obj


def _get_hovered_opening(session):
    return session.hovered_opening


def _set_hovered_opening_state(session, obj):
    session.hovered_opening = obj


def _get_hovered_symbol(session):
    return session.hovered_symbol


def _set_hovered_symbol_state(session, obj):
    session.hovered_symbol = obj


def _get_hovered_provider(session):
    return session.hovered_provider


def _set_hovered_provider_state(session, obj):
    session.hovered_provider = obj


def _get_hovered_space(session):
    return session.hovered_space


def _set_hovered_space_state(session, obj):
    session.hovered_space = obj


def _get_hovered_region(session):
    return session.hovered_region


def _set_hovered_region_state(session, obj):
    session.hovered_region = obj


def _validate_plan_selectable_wall(session, obj):
    from . import targets as plan_targets

    return plan_targets.is_plan_selectable_wall(session, obj)


def _validate_plan_provider_target_object(session, obj):
    from bimplan.providers import runtime as plan_provider_runtime

    return plan_provider_runtime.is_plan_provider_target_object(session, obj)


def _validate_plan_space_object(session, obj):
    from . import targets as plan_targets

    return plan_targets.is_plan_space_object(session, obj)


def _validate_plan_region_object(session, obj):
    from . import targets as plan_targets

    return plan_targets.is_plan_region_object(session, obj)


_TARGET_KIND_POLICIES = {
    plan_target_kinds.PLAN_TARGET_WALL: TargetKindPolicy(
        validate=_validate_plan_selectable_wall,
        get_hovered=_get_hovered_wall,
        set_hovered=_set_hovered_wall_state,
        hovered_visual_clearers=(lambda session: session.overlays.clear_hovered_wall_overlay(),),
        selected_visual_clearers=(lambda session: session.overlays.clear_selected_wall_overlay(),),
        selected_visual_label="wall_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_wall_overlay",
                lambda session: session.overlays.sync_selected_wall_overlay(),
            ),
        ),
        hovered_visual_label="wall_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_wall_overlay",
                lambda session: session.overlays.sync_hovered_wall_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_OPENING: TargetKindPolicy(
        validate=lambda session, obj: session.openings.is_hosted_opening_object(obj),
        queue_restore=lambda session, obj: session.openings.queue_restore_selected_opening(obj),
        get_hovered=_get_hovered_opening,
        set_hovered=_set_hovered_opening_state,
        hovered_visual_clearers=(lambda session: session.overlays.clear_hovered_opening_overlay(),),
        selected_visual_clearers=(
            lambda session: session.overlays.clear_selected_opening_overlay(),
        ),
        selected_handle_clearers=(
            lambda session: session.overlays.clear_selected_opening_handles(),
        ),
        selected_visual_label="opening_overlay",
        selected_visual_sync=(
            SyncSpec(
                "sync_selected_opening_overlay",
                lambda session: session.overlays.sync_selected_opening_overlay(),
            ),
            SyncSpec(
                "sync_selected_opening_handles",
                lambda session: session.overlays.sync_selected_opening_handles(),
            ),
        ),
        hovered_visual_label="opening_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_opening_overlay",
                lambda session: session.overlays.sync_hovered_opening_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_selected_wall_opening_context_overlay",
                lambda session: session.overlays.sync_selected_wall_opening_context_overlay(),
            ),
            (
                "sync_hovered_opening_overlay",
                lambda session: session.overlays.sync_hovered_opening_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_SYMBOL: TargetKindPolicy(
        validate=lambda session, obj: session.visibility.is_plan_symbol_instance(obj),
        queue_restore=lambda session, obj: session.symbols.queue_restore_selected_symbol(obj),
        get_hovered=_get_hovered_symbol,
        set_hovered=_set_hovered_symbol_state,
        hovered_visual_clearers=(lambda session: session.overlays.clear_hovered_symbol_overlay(),),
        selected_visual_clearers=(
            lambda session: session.overlays.clear_selected_symbol_overlay(),
        ),
        selected_handle_clearers=(
            lambda session: session.overlays.clear_selected_symbol_handles(),
        ),
        selected_visual_label="symbol_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_symbol_overlay",
                lambda session: session.overlays.sync_selected_symbol_overlay(),
            ),
            (
                "sync_selected_symbol_handles",
                lambda session: session.overlays.sync_selected_symbol_handles(),
            ),
        ),
        hovered_visual_label="symbol_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_symbol_overlay",
                lambda session: session.overlays.sync_hovered_symbol_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_symbol_overlay",
                lambda session: session.overlays.sync_hovered_symbol_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_PROVIDER: TargetKindPolicy(
        validate=_validate_plan_provider_target_object,
        get_hovered=_get_hovered_provider,
        set_hovered=_set_hovered_provider_state,
        hovered_visual_clearers=(
            lambda session: session.overlays.clear_hovered_provider_overlay(),
        ),
        selected_visual_clearers=(
            lambda session: session.overlays.clear_selected_provider_overlay(),
        ),
        selected_handle_clearers=(
            lambda session: session.overlays.clear_selected_provider_handles(),
        ),
        selected_visual_label="provider_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_provider_overlay",
                lambda session: session.overlays.sync_selected_provider_overlay(),
            ),
            (
                "sync_selected_provider_handles",
                lambda session: session.overlays.sync_selected_provider_handles(),
            ),
        ),
        hovered_visual_label="provider_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_provider_overlay",
                lambda session: session.overlays.sync_hovered_provider_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_provider_overlay",
                lambda session: session.overlays.sync_hovered_provider_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_SPACE: TargetKindPolicy(
        validate=_validate_plan_space_object,
        queue_restore=lambda session, obj: session.spaces.queue_restore_selected_space(obj),
        get_hovered=_get_hovered_space,
        set_hovered=_set_hovered_space_state,
        hovered_visual_clearers=(lambda session: session.overlays.clear_hovered_space_overlay(),),
        selected_visual_clearers=(lambda session: session.overlays.clear_selected_space_overlay(),),
        selected_visual_label="space_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_space_overlay",
                lambda session: session.overlays.sync_selected_space_overlay(),
            ),
        ),
        hovered_visual_label="space_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_space_overlay",
                lambda session: session.overlays.sync_hovered_space_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_space_overlay",
                lambda session: session.overlays.sync_hovered_space_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_REGION: TargetKindPolicy(
        validate=_validate_plan_region_object,
        queue_restore=lambda session, obj: session.spaces.queue_restore_selected_region(obj),
        get_hovered=_get_hovered_region,
        set_hovered=_set_hovered_region_state,
        hovered_visual_clearers=(lambda session: session.overlays.clear_hovered_region_overlay(),),
        selected_visual_clearers=(
            lambda session: session.overlays.clear_selected_region_overlay(),
        ),
        selected_visual_label="region_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_region_overlay",
                lambda session: session.overlays.sync_selected_region_overlay(),
            ),
        ),
        hovered_visual_label="region_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_region_overlay",
                lambda session: session.overlays.sync_hovered_region_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_region_overlay",
                lambda session: session.overlays.sync_hovered_region_overlay(),
            ),
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


def _call_sync(session, sync, trace_name=None):
    if not callable(sync):
        return
    if trace_name:
        with session.performance.plan_perf_trace_span(trace_name):
            sync(session)
        return
    sync(session)


def _call_methods(session, methods):
    for method in methods or ():
        if callable(method):
            method(session)


def _call_sync_specs(session, sync_specs, trace_style=None, trace_prefix=None, trace_label=None):
    if not sync_specs:
        return
    if trace_style == "by_kind":
        trace_name = None
        if trace_prefix and trace_label:
            trace_name = "{}_{}".format(trace_prefix, trace_label)
        if trace_name:
            with session.performance.plan_perf_trace_span(trace_name):
                for sync_spec in sync_specs:
                    _call_sync(session, sync_spec.sync)
            return
    for sync_spec in sync_specs:
        _call_sync(
            session,
            sync_spec.sync,
            trace_name=sync_spec.trace_name if trace_style == "by_method" else None,
        )


def get_hovered_target(session):
    for kind in _GET_HOVERED_TARGET_ORDER:
        get_hovered = _get_target_kind_policy(kind).get_hovered
        if not get_hovered:
            continue
        obj = get_hovered(session)
        if obj is not None:
            return plan_target_kinds.make_plan_target_ref(kind, obj)
    return plan_target_kinds.make_plan_target_ref()


def clear_hovered_targets(session, kinds=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        setter = _get_target_kind_policy(kind).set_hovered
        if not setter:
            continue
        setter(session, None)


def set_only_hovered_target(session, target_kind, target_obj):
    policy = _get_target_kind_policy(target_kind)
    if not policy.set_hovered:
        clear_hovered_targets(session)
        return
    clear_hovered_targets(
        session,
        kinds=tuple(
            kind for kind in plan_target_kinds.HOVERED_PLAN_TARGET_KINDS if kind != target_kind
        ),
    )
    policy.set_hovered(session, target_obj)


def clear_hovered_target_visuals(session, kinds=None):
    for kind in kinds or plan_target_kinds.HOVERED_PLAN_TARGET_KINDS:
        _call_methods(session, _get_target_kind_policy(kind).hovered_visual_clearers)


def clear_selected_target_visuals(session, kinds=None, clear_handle_kinds=None):
    handle_kind_set = set(clear_handle_kinds or ())
    for kind in kinds or plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS:
        policy = _get_target_kind_policy(kind)
        _call_methods(session, policy.selected_visual_clearers)
        if kind in handle_kind_set:
            _call_methods(session, policy.selected_handle_clearers)


def validate_plan_target(session, kind, obj):
    validate = _get_target_kind_policy(kind).validate
    if not validate:
        return False
    return bool(validate(session, obj))


def queue_restore_selected_target(session, kind, obj):
    if not obj:
        return False
    queue_restore = _get_target_kind_policy(kind).queue_restore
    if not queue_restore:
        return False
    queue_restore(session, obj)
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
    from . import selection as plan_selection_runtime

    for kind in kinds or plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS:
        policy = _get_target_kind_policy(kind)
        if not policy.selected_visual_sync:
            continue
        if (
            not force
            and session.current_tool == "Select"
            and not plan_selection_runtime.selected_plan_target_changed(
                session, previous_kind, previous_obj, kind
            )
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
    from . import selection as plan_selection_runtime

    policy = _get_target_kind_policy(kind)
    if not policy.hover_set_sync or not policy.get_hovered or not policy.set_hovered:
        return False
    if plan_selection_runtime.is_selected_plan_target(session, kind, obj):
        obj = None
    if policy.get_hovered(session) == obj:
        return False
    policy.set_hovered(session, obj)
    _call_sync_specs(session, policy.hover_set_sync)
    return True
