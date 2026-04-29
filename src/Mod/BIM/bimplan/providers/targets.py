# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider target lookup helpers for BIM Plan Edit integrations."""

from dataclasses import dataclass, replace

import FreeCAD

from .contracts import PlanProviderTargetSpec

translate = FreeCAD.Qt.translate


def _runtime():
    from bimplan.providers import runtime as provider_runtime

    return provider_runtime


@dataclass
class _PlanProviderTargetDisplayFields:
    label: str = ""
    provider_id: str = ""
    target_key: str = ""
    category: str = ""
    role: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    semantic_label: str = ""


def _get_external_provider_targets(session):
    provider_runtime = _runtime()
    direct_targets = provider_runtime._call_provider_method(
        session,
        "get_plan_provider_targets",
        default=provider_runtime._MISSING,
    )
    if direct_targets is provider_runtime._MISSING:
        return provider_runtime._MISSING
    return tuple(direct_targets or ())


def _find_external_provider_target_for_object(session, object_key):
    provider_runtime = _runtime()
    external_targets = provider_runtime._get_external_provider_targets(session)
    if external_targets is provider_runtime._MISSING:
        return provider_runtime._MISSING
    default_document_name = provider_runtime._get_default_plan_provider_target_document_name(
        session
    )
    for target in external_targets:
        target_key = provider_runtime._make_plan_provider_target_object_key(
            getattr(target, "document_name", "") or default_document_name,
            getattr(target, "object_name", ""),
        )
        if target_key == object_key:
            return target
    return None


def normalize_plan_provider_target(
    provider_id: str,
    target: object,
) -> PlanProviderTargetSpec | None:
    if not isinstance(target, PlanProviderTargetSpec):
        return None
    key = _normalize_plan_provider_target_text(target.key)
    object_name = _normalize_plan_provider_target_text(target.object_name)
    if not key or not object_name:
        return None
    replacements = {}
    normalized_provider_id = _normalize_plan_provider_target_text(provider_id)
    if target.provider_id != normalized_provider_id:
        replacements["provider_id"] = normalized_provider_id
    label = _normalize_plan_provider_target_text(target.label)
    if label != target.label:
        replacements["label"] = label
    document_name = _normalize_plan_provider_target_text(target.document_name)
    if document_name != target.document_name:
        replacements["document_name"] = document_name
    if object_name != target.object_name:
        replacements["object_name"] = object_name
    semantic_document_name = _normalize_plan_provider_target_text(target.semantic_document_name)
    if semantic_document_name != target.semantic_document_name:
        replacements["semantic_document_name"] = semantic_document_name
    semantic_object_name = _normalize_plan_provider_target_text(target.semantic_object_name)
    if semantic_object_name != target.semantic_object_name:
        replacements["semantic_object_name"] = semantic_object_name
    category = _normalize_plan_provider_target_text(target.category)
    if category != target.category:
        replacements["category"] = category
    role = _normalize_plan_provider_target_text(target.role)
    if role != target.role:
        replacements["role"] = role
    if key != target.key:
        replacements["key"] = key
    if not replacements:
        return target
    return replace(target, **replacements)


def get_plan_provider_targets(session) -> tuple[PlanProviderTargetSpec, ...]:
    provider_runtime = _runtime()
    external_targets = provider_runtime._get_external_provider_targets(session)
    if external_targets is not provider_runtime._MISSING:
        return external_targets
    depth = provider_runtime._get_provider_target_collection_depth(session)
    if depth > 0:
        return ()
    provider_runtime._set_provider_target_collection_depth(session, depth + 1)
    try:
        return provider_runtime.collect_plan_provider_contributions(
            session,
            "get_targets",
            normalize_plan_provider_target,
        )
    finally:
        provider_runtime._set_provider_target_collection_depth(session, depth)


def get_plan_provider_target_for_object(session, obj) -> PlanProviderTargetSpec | None:
    provider_runtime = _runtime()
    if obj is None:
        return None
    object_key = provider_runtime._make_plan_provider_target_object_key(
        getattr(getattr(obj, "Document", None), "Name", "")
        or provider_runtime._get_default_plan_provider_target_document_name(session),
        getattr(obj, "Name", ""),
    )
    if object_key is None:
        return None
    external_target = provider_runtime._find_external_provider_target_for_object(
        session, object_key
    )
    if external_target is not provider_runtime._MISSING:
        return external_target
    return provider_runtime._get_plan_provider_target_lookup(session).get(object_key)


def is_plan_provider_target_object(session, obj) -> bool:
    return get_plan_provider_target_for_object(session, obj) is not None


def is_plan_provider_target_visible_for_mode(session, obj, mode=None) -> bool:
    provider_runtime = _runtime()
    target = get_plan_provider_target_for_object(session, obj)
    if target is None:
        return False
    return bool(
        provider_runtime.is_plan_provider_overlay_visible_for_mode(session, target, mode=mode)
    )


def get_plan_provider_target_role_key(session, obj) -> str:
    target = get_plan_provider_target_for_object(session, obj)
    if target is None:
        return ""
    return str(target.role or "").strip()


def get_plan_provider_target_role_label(session, obj) -> str:
    role = get_plan_provider_target_role_key(session, obj)
    if not role:
        return translate("BIM_PlanEdit", "Object")
    return role.replace("_", " ").title()


def format_plan_provider_target_help(session, obj) -> str:
    from bimplan.providers import edit as plan_provider_edit

    if not is_plan_provider_target_object(session, obj):
        return ""
    role = get_plan_provider_target_role_key(session, obj).replace("_", " ").lower()
    has_handles = False
    try:
        has_handles = bool(
            session.selection.state.is_selected_plan_target("provider", obj)
        ) and bool(tuple(plan_provider_edit.get_selected_provider_edit_handles(session, obj) or ()))
    except Exception:
        has_handles = False
    if role:
        if has_handles:
            return translate(
                "BIM_PlanEdit",
                "Use in-view handles or the integration details below for the selected {role}.",
            ).format(role=role)
        return translate(
            "BIM_PlanEdit",
            "Use the integration details and actions below for the selected {role}.",
        ).format(role=role)
    if has_handles:
        return translate(
            "BIM_PlanEdit",
            "Use in-view handles or the integration details below for the selected object.",
        )
    return translate(
        "BIM_PlanEdit",
        "Use the integration details and actions below for the selected object.",
    )


def _get_provider_target_semantic_resolution(session, semantic_obj, provider_target):
    semantic_resolved = None
    if provider_target is not None:
        semantic_resolved = session.selection.targets.resolve_plan_semantic_object(provider_target)
        if semantic_resolved is not None:
            semantic_obj = semantic_resolved
    return semantic_obj, semantic_resolved


def _build_provider_target_display_fields(semantic_obj, fallback_label):
    semantic_doc = getattr(semantic_obj, "Document", None)
    return _PlanProviderTargetDisplayFields(
        label=str(fallback_label or ""),
        semantic_document_name=str(getattr(semantic_doc, "Name", "") or ""),
        semantic_object_name=str(getattr(semantic_obj, "Name", "") or ""),
        semantic_label=str(getattr(semantic_obj, "Label", getattr(semantic_obj, "Name", "")) or ""),
    )


def _apply_provider_target_display_overrides(fields, provider_target, semantic_resolved):
    provider_label = str(provider_target.label or "").strip()
    if provider_label:
        fields.label = provider_label
    fields.provider_id = str(provider_target.provider_id or "").strip()
    fields.target_key = str(provider_target.key or "").strip()
    fields.category = str(provider_target.category or "").strip()
    fields.role = str(provider_target.role or "").strip()
    fields.semantic_document_name = str(
        provider_target.semantic_document_name or fields.semantic_document_name
    ).strip()
    fields.semantic_object_name = str(
        provider_target.semantic_object_name or fields.semantic_object_name
    ).strip()
    if semantic_resolved is not None:
        fields.semantic_label = str(
            getattr(semantic_resolved, "Label", getattr(semantic_resolved, "Name", "")) or ""
        )


def resolve_plan_provider_target_display_fields(
    session,
    semantic_obj,
    provider_target: PlanProviderTargetSpec | None,
    fallback_label,
) -> _PlanProviderTargetDisplayFields:
    semantic_obj, semantic_resolved = _get_provider_target_semantic_resolution(
        session,
        semantic_obj,
        provider_target,
    )
    fields = _build_provider_target_display_fields(semantic_obj, fallback_label)
    if provider_target is None:
        return fields
    _apply_provider_target_display_overrides(fields, provider_target, semantic_resolved)
    return fields


def _normalize_plan_provider_target_text(value: object) -> str:
    return str(value or "").strip()


def _get_default_plan_provider_target_document_name(session) -> str:
    return _normalize_plan_provider_target_text(getattr(getattr(session, "doc", None), "Name", ""))


def _make_plan_provider_target_object_key(
    document_name: object,
    object_name: object,
) -> tuple[str, str] | None:
    normalized_object_name = _normalize_plan_provider_target_text(object_name)
    if not normalized_object_name:
        return None
    return (
        _normalize_plan_provider_target_text(document_name),
        normalized_object_name,
    )


def _get_plan_provider_target_lookup(session) -> dict[tuple[str, str], PlanProviderTargetSpec]:
    provider_runtime = _runtime()
    refresh_cache = provider_runtime._get_provider_refresh_cache(session)
    cache_key = ("provider_targets", "by_object")
    if isinstance(refresh_cache, dict) and cache_key in refresh_cache:
        return refresh_cache[cache_key]

    context = provider_runtime._get_plan_edit_context_or_none(session)
    document_cache = provider_runtime._get_provider_document_cache(session)
    document_cache_key = None
    if context is not None and document_cache is not None:
        document_cache_key = (
            "provider_targets",
            "by_object",
        ) + provider_runtime._make_provider_target_context_cache_key(context)
        cached_lookup = document_cache.get(document_cache_key)
        if isinstance(cached_lookup, dict):
            if isinstance(refresh_cache, dict):
                refresh_cache[cache_key] = cached_lookup
            return cached_lookup

    default_document_name = provider_runtime._get_default_plan_provider_target_document_name(
        session
    )
    targets_by_object = {}
    for target in tuple(provider_runtime.get_plan_provider_targets(session) or ()):
        target_key = provider_runtime._make_plan_provider_target_object_key(
            target.document_name or default_document_name,
            target.object_name,
        )
        if target_key is None or target_key in targets_by_object:
            continue
        targets_by_object[target_key] = target

    if isinstance(refresh_cache, dict):
        refresh_cache[cache_key] = targets_by_object
    if document_cache_key is not None and document_cache is not None:
        document_cache[document_cache_key] = targets_by_object
    return targets_by_object
