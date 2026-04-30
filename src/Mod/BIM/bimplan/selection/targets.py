# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target records, resolution, and policy dispatch for BIM Plan Edit."""

from dataclasses import dataclass
from typing import Any, Callable

import FreeCAD

from bimplan.providers.targets import (
    is_plan_provider_target_object,
    is_plan_provider_target_visible_for_mode,
    resolve_plan_provider_target_display_fields,
)
from bimplan.runtime import capabilities as runtime_capabilities
from . import kinds as plan_target_kinds
from .common import _SessionAPI, get_plan_target_state_key


def _provider_runtime_api(session):
    providers = getattr(session, "providers", None)
    return getattr(providers, "runtime", providers)


@dataclass(frozen=True)
class PlanTarget:
    kind: str
    document_name: str = ""
    object_name: str = ""
    label: str = ""
    provider_id: str = ""
    target_key: str = ""
    category: str = ""
    role: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    semantic_label: str = ""
    is_selected: bool = False
    is_primary: bool = False


def _coerce_plan_target_ref(target):
    return plan_target_kinds.coerce_plan_target_ref(target)


def _call_component_method(session, component_name, method_name, *args, default=None):
    component = getattr(session, component_name, None)
    method = runtime_capabilities.get_callable(component, method_name)
    if method is None:
        method = runtime_capabilities.get_callable(session, method_name)
    if method is None:
        return default
    return method(*args)


def _get_plan_semantic_object(session, obj):
    semantic_obj = _call_component_method(
        session,
        "visibility",
        "get_plan_semantic_object",
        obj,
        default=None,
    )
    return obj if semantic_obj is None else semantic_obj


def get_plan_target_kind_for_object(session, obj):
    if _call_component_method(session, "openings", "is_hosted_opening_object", obj, default=False):
        return plan_target_kinds.PLAN_TARGET_OPENING
    if _call_component_method(session, "visibility", "is_plan_symbol_instance", obj, default=False):
        return plan_target_kinds.PLAN_TARGET_SYMBOL
    if (
        _call_component_method(
            session, "providers", "is_plan_provider_target_object", obj, default=False
        )
        or _call_component_method(
            session, "providers", "get_plan_provider_target_for_object", obj, default=None
        )
        or is_plan_provider_target_object(session, obj)
    ):
        return plan_target_kinds.PLAN_TARGET_PROVIDER
    if is_plan_region_object(session, obj):
        return plan_target_kinds.PLAN_TARGET_REGION
    if is_plan_selectable_wall(session, obj):
        return plan_target_kinds.PLAN_TARGET_WALL
    if is_plan_space_object(session, obj):
        return plan_target_kinds.PLAN_TARGET_SPACE
    return None


def get_plan_target_for_object(session, obj, parent_obj=None):
    seen = set()
    for candidate in (obj, parent_obj):
        if not candidate:
            continue
        name = getattr(candidate, "Name", None)
        if name and name in seen:
            continue
        if name:
            seen.add(name)
        target_kind = get_plan_target_kind_for_object(session, candidate)
        if target_kind:
            return plan_target_kinds.make_plan_target_ref(target_kind, candidate)

    semantic_obj = _get_plan_semantic_object(session, obj)
    semantic_name = getattr(semantic_obj, "Name", None)
    if semantic_obj and semantic_name not in seen:
        target_kind = get_plan_target_kind_for_object(session, semantic_obj)
        if target_kind:
            return plan_target_kinds.make_plan_target_ref(target_kind, semantic_obj)

    return plan_target_kinds.make_plan_target_ref()


def get_plan_pick_target_for_object(session, obj, parent_obj=None):
    seen = set()
    for candidate in (obj, parent_obj):
        if not candidate:
            continue
        name = getattr(candidate, "Name", None)
        if name and name in seen:
            continue
        if name:
            seen.add(name)
        target_kind = get_plan_target_kind_for_object(session, candidate)
        if (
            target_kind == plan_target_kinds.PLAN_TARGET_PROVIDER
            and not is_plan_provider_target_visible_for_mode(session, candidate)
        ):
            continue
        if target_kind:
            return plan_target_kinds.make_plan_target_ref(target_kind, candidate)

    semantic_obj = _get_plan_semantic_object(session, obj)
    semantic_name = getattr(semantic_obj, "Name", None)
    if semantic_obj and semantic_name not in seen:
        target_kind = get_plan_target_kind_for_object(session, semantic_obj)
        if (
            target_kind == plan_target_kinds.PLAN_TARGET_PROVIDER
            and not is_plan_provider_target_visible_for_mode(session, semantic_obj)
        ):
            return plan_target_kinds.make_plan_target_ref()
        if target_kind:
            return plan_target_kinds.make_plan_target_ref(target_kind, semantic_obj)

    return plan_target_kinds.make_plan_target_ref()


def is_plan_selectable_wall(session, obj):
    if not obj:
        return False
    obj = _get_plan_semantic_object(session, obj)
    try:
        import Draft

        return Draft.getType(obj) == "Wall"
    except Exception:
        return False


def is_plan_space_object(session, obj):
    if not obj:
        return False
    obj = _get_plan_semantic_object(session, obj)
    try:
        import Draft

        if Draft.getType(obj) == "Space":
            return True
    except Exception:
        pass
    return getattr(obj, "IfcType", "") == "Space"


def is_plan_custom_pick_only_object(session, obj):
    if not obj:
        return False
    obj = _get_plan_semantic_object(session, obj)
    return (
        _call_component_method(session, "openings", "is_hosted_opening_object", obj, default=False)
        or is_plan_space_object(session, obj)
        or is_plan_region_object(session, obj)
    )


def is_plan_space_separator_object(session, obj):
    if not obj:
        return False
    obj = _get_plan_semantic_object(session, obj)
    try:
        import Draft

        return Draft.getType(obj) == "SpaceSeparator"
    except Exception:
        return False


def is_plan_region_object(session, obj):
    if not obj:
        return False
    obj = _get_plan_semantic_object(session, obj)
    try:
        import Draft

        return Draft.getType(obj) == "PlanRegion"
    except Exception:
        return False


def get_plan_text_property(obj, property_names, default=""):
    if obj is None:
        return str(default or "")
    for property_name in property_names or ():
        if not property_name:
            continue
        try:
            value = getattr(obj, property_name)
        except Exception:
            continue
        text = str(value or "").strip()
        if text:
            return text
    return str(default or "")


def get_plan_float_property(obj, property_names):
    if obj is None:
        return None
    for property_name in property_names or ():
        if not property_name:
            continue
        try:
            value = getattr(obj, property_name)
        except Exception:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def normalize_plan_requirement_tags(value):
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(item or "").strip() for item in value]
    else:
        parts = [str(value or "").strip()]
    normalized = []
    seen = set()
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        normalized.append(part)
    return tuple(normalized)


def get_plan_host_ref(session, obj):
    if obj is None:
        return ""
    host_ref = session.visibility.get_plan_text_property(obj, ("HostRef",))
    if host_ref:
        return host_ref
    hosts = getattr(obj, "Hosts", None) or ()
    for host in hosts:
        name = str(getattr(host, "Name", "") or "").strip()
        if name:
            return name
    return ""


def make_plan_target_record(session, kind, obj, selected_keys=None, primary_key=None):
    if not kind or obj is None:
        return None
    provider_target = (
        _provider_runtime_api(session).get_plan_provider_target_for_object(obj)
        if kind == plan_target_kinds.PLAN_TARGET_PROVIDER
        else None
    )
    semantic_obj = session.visibility.get_plan_semantic_object(obj)
    doc = getattr(obj, "Document", None)
    state_key = get_plan_target_state_key(kind, obj)
    fields = resolve_plan_provider_target_display_fields(
        session,
        semantic_obj,
        provider_target,
        getattr(obj, "Label", getattr(obj, "Name", "")),
    )
    return PlanTarget(
        kind=str(kind or ""),
        document_name=str(getattr(doc, "Name", "") or ""),
        object_name=str(getattr(obj, "Name", "") or ""),
        label=fields.label,
        provider_id=fields.provider_id,
        target_key=fields.target_key,
        category=fields.category,
        role=fields.role,
        semantic_document_name=fields.semantic_document_name,
        semantic_object_name=fields.semantic_object_name,
        semantic_label=fields.semantic_label,
        is_selected=bool(selected_keys and state_key in selected_keys),
        is_primary=bool(primary_key is not None and state_key == primary_key),
    )


def get_plan_targets(session, selected_only=False):
    selected_targets = tuple(
        _coerce_plan_target_ref(target)
        for target in session.selection.state.get_selected_plan_targets()
    )
    selected_keys = {
        get_plan_target_state_key(target.kind, target.obj) for target in selected_targets
    }
    selected_keys.discard(None)
    primary_key = None
    primary_target = _coerce_plan_target_ref(session.selection.state.get_selected_plan_target())
    if primary_target.kind and primary_target.obj:
        primary_key = get_plan_target_state_key(
            primary_target.kind,
            primary_target.obj,
        )

    if selected_only:
        source_targets = selected_targets
    else:
        source_targets = []
        seen = set()
        active_storey_name = getattr(session.active_storey, "Name", None)
        provider_refresh_scope = _provider_runtime_api(session).plan_provider_refresh_cache_scope()
        with provider_refresh_scope:
            for obj in getattr(session.doc, "Objects", []) or []:
                target = _coerce_plan_target_ref(get_plan_target_for_object(session, obj))
                target_kind = target.kind
                target_obj = target.obj
                if not target_kind or not target_obj:
                    continue
                state_key = get_plan_target_state_key(
                    target_kind,
                    target_obj,
                )
                if state_key is None or state_key in seen:
                    continue
                semantic_obj = session.visibility.get_plan_semantic_object(target_obj)
                if active_storey_name is not None:
                    storeys = session.visibility.get_object_storeys(semantic_obj or target_obj)
                    if storeys and not any(parent.Name == active_storey_name for parent in storeys):
                        continue
                seen.add(state_key)
                source_targets.append(target)

    records = []
    for target in source_targets:
        target_record = make_plan_target_record(
            session,
            target.kind,
            target.obj,
            selected_keys=selected_keys,
            primary_key=primary_key,
        )
        if target_record is not None:
            records.append(target_record)
    return tuple(records)


def resolve_plan_target_object(session, target):
    if target is None:
        return None
    document_name = str(getattr(target, "document_name", "") or "").strip()
    object_name = str(getattr(target, "object_name", "") or "").strip()
    if not object_name:
        return None
    doc = None
    if document_name and getattr(session.doc, "Name", None) == document_name:
        doc = session.doc
    elif document_name:
        try:
            doc = FreeCAD.getDocument(document_name)
        except Exception:
            doc = None
    else:
        doc = session.doc
    if doc is None:
        return None
    try:
        return doc.getObject(object_name)
    except Exception:
        return None


def resolve_plan_semantic_object(session, target):
    if target is None:
        return None
    semantic_document_name = str(getattr(target, "semantic_document_name", "") or "").strip()
    semantic_object_name = str(getattr(target, "semantic_object_name", "") or "").strip()
    if semantic_document_name and semantic_object_name:
        doc = None
        if getattr(session.doc, "Name", None) == semantic_document_name:
            doc = session.doc
        else:
            try:
                doc = FreeCAD.getDocument(semantic_document_name)
            except Exception:
                doc = None
        if doc is not None:
            try:
                resolved = doc.getObject(semantic_object_name)
            except Exception:
                resolved = None
            if resolved is not None:
                return resolved
    return session.visibility.get_plan_semantic_object(resolve_plan_target_object(session, target))


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
    return is_plan_selectable_wall(session, obj)


def _validate_plan_provider_target_object(session, obj):
    return is_plan_provider_target_object(session, obj)


def _validate_plan_space_object(session, obj):
    return is_plan_space_object(session, obj)


def _validate_plan_region_object(session, obj):
    return is_plan_region_object(session, obj)


_TARGET_KIND_POLICIES = {
    plan_target_kinds.PLAN_TARGET_WALL: TargetKindPolicy(
        validate=_validate_plan_selectable_wall,
        get_hovered=_get_hovered_wall,
        set_hovered=_set_hovered_wall_state,
        hovered_visual_clearers=(
            lambda session: session.overlays.walls.clear_hovered_wall_overlay(),
        ),
        selected_visual_clearers=(
            lambda session: session.overlays.walls.clear_selected_wall_overlay(),
        ),
        selected_visual_label="wall_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_wall_overlay",
                lambda session: session.overlays.walls.sync_selected_wall_overlay(),
            ),
        ),
        hovered_visual_label="wall_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_wall_overlay",
                lambda session: session.overlays.walls.sync_hovered_wall_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_junction_node_overlays",
                lambda session: session.overlays.walls.sync_junction_node_overlays(),
            ),
            (
                "sync_hovered_wall_overlay",
                lambda session: session.overlays.walls.sync_hovered_wall_overlay(),
            ),
            (
                "sync_hovered_wall_opening_context_overlay",
                lambda session: session.overlays.walls.sync_hovered_wall_opening_context_overlay(),
            ),
            (
                "refresh_task_panel_status",
                lambda session: (
                    session.task_panels.refresh_task_panel_status(reason="full")
                    if session.current_tool == "Join"
                    else None
                ),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_OPENING: TargetKindPolicy(
        validate=lambda session, obj: session.openings.is_hosted_opening_object(obj),
        queue_restore=lambda session, obj: session.openings.queue_restore_selected_opening(obj),
        get_hovered=_get_hovered_opening,
        set_hovered=_set_hovered_opening_state,
        hovered_visual_clearers=(
            lambda session: session.overlays.openings.clear_hovered_opening_overlay(),
        ),
        selected_visual_clearers=(
            lambda session: session.overlays.openings.clear_selected_opening_overlay(),
        ),
        selected_handle_clearers=(
            lambda session: session.overlays.openings.clear_selected_opening_handles(),
        ),
        selected_visual_label="opening_overlay",
        selected_visual_sync=(
            SyncSpec(
                "sync_selected_opening_overlay",
                lambda session: session.overlays.openings.sync_selected_opening_overlay(),
            ),
            SyncSpec(
                "sync_selected_opening_handles",
                lambda session: session.overlays.openings.sync_selected_opening_handles(),
            ),
        ),
        hovered_visual_label="opening_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_opening_overlay",
                lambda session: session.overlays.openings.sync_hovered_opening_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_selected_wall_opening_context_overlay",
                lambda session: session.overlays.openings.sync_selected_wall_opening_context_overlay(),
            ),
            (
                "sync_hovered_opening_overlay",
                lambda session: session.overlays.openings.sync_hovered_opening_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_SYMBOL: TargetKindPolicy(
        validate=lambda session, obj: session.visibility.is_plan_symbol_instance(obj),
        queue_restore=lambda session, obj: session.symbols.queue_restore_selected_symbol(obj),
        get_hovered=_get_hovered_symbol,
        set_hovered=_set_hovered_symbol_state,
        hovered_visual_clearers=(
            lambda session: session.overlays.symbols.clear_hovered_symbol_overlay(),
        ),
        selected_visual_clearers=(
            lambda session: session.overlays.symbols.clear_selected_symbol_overlay(),
        ),
        selected_handle_clearers=(
            lambda session: session.overlays.symbols.clear_selected_symbol_handles(),
        ),
        selected_visual_label="symbol_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_symbol_overlay",
                lambda session: session.overlays.symbols.sync_selected_symbol_overlay(),
            ),
            (
                "sync_selected_symbol_handles",
                lambda session: session.overlays.symbols.sync_selected_symbol_handles(),
            ),
        ),
        hovered_visual_label="symbol_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_symbol_overlay",
                lambda session: session.overlays.symbols.sync_hovered_symbol_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_symbol_overlay",
                lambda session: session.overlays.symbols.sync_hovered_symbol_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_PROVIDER: TargetKindPolicy(
        validate=_validate_plan_provider_target_object,
        get_hovered=_get_hovered_provider,
        set_hovered=_set_hovered_provider_state,
        hovered_visual_clearers=(
            lambda session: session.overlays.providers.clear_hovered_provider_overlay(),
        ),
        selected_visual_clearers=(
            lambda session: session.overlays.providers.clear_selected_provider_overlay(),
        ),
        selected_handle_clearers=(
            lambda session: session.overlays.providers.clear_selected_provider_handles(),
        ),
        selected_visual_label="provider_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_provider_overlay",
                lambda session: session.overlays.providers.sync_selected_provider_overlay(),
            ),
            (
                "sync_selected_provider_handles",
                lambda session: session.overlays.providers.sync_selected_provider_handles(),
            ),
        ),
        hovered_visual_label="provider_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_provider_overlay",
                lambda session: session.overlays.providers.sync_hovered_provider_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_provider_overlay",
                lambda session: session.overlays.providers.sync_hovered_provider_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_SPACE: TargetKindPolicy(
        validate=_validate_plan_space_object,
        queue_restore=lambda session, obj: session.spaces.queue_restore_selected_space(obj),
        get_hovered=_get_hovered_space,
        set_hovered=_set_hovered_space_state,
        hovered_visual_clearers=(
            lambda session: session.overlays.spaces.clear_hovered_space_overlay(),
        ),
        selected_visual_clearers=(
            lambda session: session.overlays.spaces.clear_selected_space_overlay(),
        ),
        selected_visual_label="space_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_space_overlay",
                lambda session: session.overlays.spaces.sync_selected_space_overlay(),
            ),
        ),
        hovered_visual_label="space_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_space_overlay",
                lambda session: session.overlays.spaces.sync_hovered_space_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_space_overlay",
                lambda session: session.overlays.spaces.sync_hovered_space_overlay(),
            ),
        ),
    ),
    plan_target_kinds.PLAN_TARGET_REGION: TargetKindPolicy(
        validate=_validate_plan_region_object,
        queue_restore=lambda session, obj: session.spaces.queue_restore_selected_region(obj),
        get_hovered=_get_hovered_region,
        set_hovered=_set_hovered_region_state,
        hovered_visual_clearers=(
            lambda session: session.overlays.spaces.clear_hovered_region_overlay(),
        ),
        selected_visual_clearers=(
            lambda session: session.overlays.spaces.clear_selected_region_overlay(),
        ),
        selected_visual_label="region_overlay",
        selected_visual_sync=_sync_specs(
            (
                "sync_selected_region_overlay",
                lambda session: session.overlays.spaces.sync_selected_region_overlay(),
            ),
        ),
        hovered_visual_label="region_overlay",
        hovered_visual_sync=_sync_specs(
            (
                "sync_hovered_region_overlay",
                lambda session: session.overlays.spaces.sync_hovered_region_overlay(),
            ),
        ),
        hover_set_sync=_sync_specs(
            (
                "sync_hovered_region_overlay",
                lambda session: session.overlays.spaces.sync_hovered_region_overlay(),
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
        policy = _get_target_kind_policy(kind)
        if not policy.set_hovered:
            continue
        set_hovered_target(session, kind, None)


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
    set_hovered_target(session, target_kind, target_obj)


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
    for kind in kinds or plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS:
        policy = _get_target_kind_policy(kind)
        if not policy.selected_visual_sync:
            continue
        if (
            not force
            and session.current_tool == "Select"
            and not session.selection.state.selected_plan_target_changed(
                previous_kind, previous_obj, kind
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
    policy = _get_target_kind_policy(kind)
    if not policy.hover_set_sync or not policy.get_hovered or not policy.set_hovered:
        return False
    if session.selection.state.is_selected_plan_target(kind, obj):
        obj = None
    if policy.get_hovered(session) == obj:
        return False
    policy.set_hovered(session, obj)
    _call_sync_specs(session, policy.hover_set_sync)
    return True


class PlanSelectionTargetService(_SessionAPI):
    normalize_plan_requirement_tags = staticmethod(normalize_plan_requirement_tags)

    def get_plan_target_kind_for_object(self, obj):
        return get_plan_target_kind_for_object(self.session, obj)

    def get_plan_target_for_object(self, obj, parent_obj=None):
        return get_plan_target_for_object(self.session, obj, parent_obj)

    def is_plan_selectable_wall(self, obj):
        return is_plan_selectable_wall(self.session, obj)

    def is_plan_space_object(self, obj):
        return is_plan_space_object(self.session, obj)

    def is_plan_custom_pick_only_object(self, obj):
        if not obj:
            return False
        obj = _get_plan_semantic_object(self.session, obj)
        return (
            _call_component_method(
                self.session,
                "openings",
                "is_hosted_opening_object",
                obj,
                default=False,
            )
            or self.is_plan_space_object(obj)
            or self.is_plan_region_object(obj)
        )

    def is_plan_space_separator_object(self, obj):
        return is_plan_space_separator_object(self.session, obj)

    def is_plan_region_object(self, obj):
        return is_plan_region_object(self.session, obj)

    def get_plan_host_ref(self, obj):
        return get_plan_host_ref(self.session, obj)

    def make_plan_target_record(self, kind, obj, selected_keys=None, primary_key=None):
        return make_plan_target_record(
            self.session,
            kind,
            obj,
            selected_keys=selected_keys,
            primary_key=primary_key,
        )

    def get_plan_targets(self, selected_only=False):
        return get_plan_targets(self.session, selected_only=selected_only)

    def resolve_plan_target_object(self, target):
        return resolve_plan_target_object(self.session, target)

    def resolve_plan_semantic_object(self, target):
        return resolve_plan_semantic_object(self.session, target)
