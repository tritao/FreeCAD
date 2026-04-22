# SPDX-License-Identifier: LGPL-2.1-or-later

"""Helpers for provider-defined Plan Edit targets."""

from __future__ import annotations

from dataclasses import replace
from typing import TypedDict

import FreeCAD

from bimplan.providers import PlanProviderTargetSpec

translate = FreeCAD.Qt.translate


class _PlanProviderTargetDisplayFields(TypedDict):
    label: str
    provider_id: str
    target_key: str
    category: str
    role: str
    semantic_document_name: str
    semantic_object_name: str
    semantic_label: str


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
    depth = int(getattr(session, "_plan_provider_target_collection_depth", 0) or 0)
    if depth > 0:
        return ()
    session._plan_provider_target_collection_depth = depth + 1
    try:
        return session._collect_plan_provider_contributions(
            "get_targets",
            session._normalize_plan_provider_target,
        )
    finally:
        session._plan_provider_target_collection_depth = depth


def get_plan_provider_target_for_object(session, obj) -> PlanProviderTargetSpec | None:
    if obj is None:
        return None
    object_key = _make_plan_provider_target_object_key(
        getattr(getattr(obj, "Document", None), "Name", "")
        or _get_default_plan_provider_target_document_name(session),
        getattr(obj, "Name", ""),
    )
    if object_key is None:
        return None
    return _get_plan_provider_target_lookup(session).get(object_key)


def is_plan_provider_target_object(session, obj) -> bool:
    return get_plan_provider_target_for_object(session, obj) is not None


def is_plan_provider_target_visible_for_mode(session, obj, mode=None) -> bool:
    target = get_plan_provider_target_for_object(session, obj)
    if target is None:
        return False
    return bool(session.is_plan_provider_overlay_visible_for_mode(target, mode=mode))


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
    if not is_plan_provider_target_object(session, obj):
        return ""
    role = get_plan_provider_target_role_key(session, obj).replace("_", " ").lower()
    get_handles = getattr(session, "_get_selected_provider_edit_handles", None)
    has_handles = False
    if callable(get_handles) and getattr(session, "_is_selected_plan_target", None):
        try:
            has_handles = bool(session._is_selected_plan_target("provider", obj)) and bool(
                tuple(get_handles(obj) or ())
            )
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


def resolve_plan_provider_target_display_fields(
    session,
    semantic_obj,
    provider_target: PlanProviderTargetSpec | None,
    fallback_label,
) -> _PlanProviderTargetDisplayFields:
    semantic_resolved = None
    if provider_target is not None:
        semantic_resolved = session.resolve_plan_semantic_object(provider_target)
        if semantic_resolved is not None:
            semantic_obj = semantic_resolved

    semantic_doc = getattr(semantic_obj, "Document", None)
    fields = {
        "label": str(fallback_label or ""),
        "provider_id": "",
        "target_key": "",
        "category": "",
        "role": "",
        "semantic_document_name": str(getattr(semantic_doc, "Name", "") or ""),
        "semantic_object_name": str(getattr(semantic_obj, "Name", "") or ""),
        "semantic_label": str(
            getattr(semantic_obj, "Label", getattr(semantic_obj, "Name", "")) or ""
        ),
    }
    if provider_target is None:
        return fields

    provider_label = str(provider_target.label or "").strip()
    if provider_label:
        fields["label"] = provider_label
    fields["provider_id"] = str(provider_target.provider_id or "").strip()
    fields["target_key"] = str(provider_target.key or "").strip()
    fields["category"] = str(provider_target.category or "").strip()
    fields["role"] = str(provider_target.role or "").strip()
    fields["semantic_document_name"] = str(
        provider_target.semantic_document_name or fields["semantic_document_name"]
    ).strip()
    fields["semantic_object_name"] = str(
        provider_target.semantic_object_name or fields["semantic_object_name"]
    ).strip()
    if semantic_resolved is not None:
        fields["semantic_label"] = str(
            getattr(semantic_resolved, "Label", getattr(semantic_resolved, "Name", "")) or ""
        )
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
    refresh_cache = getattr(session, "_plan_provider_refresh_cache", None)
    cache_key = ("provider_targets", "by_object")
    if isinstance(refresh_cache, dict) and cache_key in refresh_cache:
        return refresh_cache[cache_key]

    default_document_name = _get_default_plan_provider_target_document_name(session)
    targets_by_object = {}
    for target in tuple(session.get_plan_provider_targets() or ()):
        target_key = _make_plan_provider_target_object_key(
            target.document_name or default_document_name,
            target.object_name,
        )
        if target_key is None or target_key in targets_by_object:
            continue
        targets_by_object[target_key] = target

    if isinstance(refresh_cache, dict):
        refresh_cache[cache_key] = targets_by_object
    return targets_by_object
