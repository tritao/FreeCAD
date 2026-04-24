# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target records exposed by BIM Plan Edit integrations."""

from contextlib import nullcontext
from dataclasses import dataclass

import FreeCAD

from bimplan.providers import runtime as plan_provider_runtime
from . import target_kinds as plan_target_kinds
from bimplan.providers.runtime import resolve_plan_provider_target_display_fields


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


def get_plan_target_kind_for_object(session, obj):
    if session._is_hosted_opening_object(obj):
        return plan_target_kinds.PLAN_TARGET_OPENING
    if session.visibility.is_plan_symbol_instance(obj):
        return plan_target_kinds.PLAN_TARGET_SYMBOL
    if session._is_plan_provider_target_object(obj):
        return plan_target_kinds.PLAN_TARGET_PROVIDER
    if session._is_plan_region_object(obj):
        return plan_target_kinds.PLAN_TARGET_REGION
    if session._is_plan_selectable_wall(obj):
        return plan_target_kinds.PLAN_TARGET_WALL
    if session._is_plan_space_object(obj):
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
        target_kind = session.selection.get_plan_target_kind_for_object(candidate)
        if target_kind:
            return (target_kind, candidate)

    semantic_obj = session.visibility.get_plan_semantic_object(obj)
    semantic_name = getattr(semantic_obj, "Name", None)
    if semantic_obj and semantic_name not in seen:
        target_kind = session.selection.get_plan_target_kind_for_object(semantic_obj)
        if target_kind:
            return (target_kind, semantic_obj)

    return (None, None)


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
        target_kind = session.selection.get_plan_target_kind_for_object(candidate)
        if (
            target_kind == plan_target_kinds.PLAN_TARGET_PROVIDER
            and not plan_provider_runtime.is_plan_provider_target_visible_for_mode(
                session,
                candidate,
            )
        ):
            continue
        if target_kind:
            return (target_kind, candidate)

    semantic_obj = session.visibility.get_plan_semantic_object(obj)
    semantic_name = getattr(semantic_obj, "Name", None)
    if semantic_obj and semantic_name not in seen:
        target_kind = session.selection.get_plan_target_kind_for_object(semantic_obj)
        if (
            target_kind == plan_target_kinds.PLAN_TARGET_PROVIDER
            and not plan_provider_runtime.is_plan_provider_target_visible_for_mode(
                session,
                semantic_obj,
            )
        ):
            return (None, None)
        if target_kind:
            return (target_kind, semantic_obj)

    return (None, None)


def is_plan_selectable_wall(session, obj):
    if not obj:
        return False
    obj = session.visibility.get_plan_semantic_object(obj)
    try:
        import Draft

        return Draft.getType(obj) == "Wall"
    except Exception:
        return False


def is_plan_space_object(session, obj):
    if not obj:
        return False
    obj = session.visibility.get_plan_semantic_object(obj)
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
    obj = session.visibility.get_plan_semantic_object(obj)
    return (
        session._is_hosted_opening_object(obj)
        or session._is_plan_space_object(obj)
        or session._is_plan_region_object(obj)
    )


def is_plan_space_separator_object(session, obj):
    if not obj:
        return False
    obj = session.visibility.get_plan_semantic_object(obj)
    try:
        import Draft

        return Draft.getType(obj) == "SpaceSeparator"
    except Exception:
        return False


def is_plan_region_object(session, obj):
    if not obj:
        return False
    obj = session.visibility.get_plan_semantic_object(obj)
    try:
        import Draft

        return Draft.getType(obj) == "PlanRegion"
    except Exception:
        return False


def get_plan_text_property(obj, property_names, default=""):
    if obj is None:
        return str(default or "")
    for property_name in property_names or ():
        if not property_name or not hasattr(obj, property_name):
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
        if not property_name or not hasattr(obj, property_name):
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
        session.providers.get_plan_provider_target_for_object(obj)
        if kind == plan_target_kinds.PLAN_TARGET_PROVIDER
        else None
    )
    semantic_obj = session.visibility.get_plan_semantic_object(obj)
    doc = getattr(obj, "Document", None)
    state_key = session.selection.get_plan_target_state_key(kind, obj)
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
        label=fields["label"],
        provider_id=fields["provider_id"],
        target_key=fields["target_key"],
        category=fields["category"],
        role=fields["role"],
        semantic_document_name=fields["semantic_document_name"],
        semantic_object_name=fields["semantic_object_name"],
        semantic_label=fields["semantic_label"],
        is_selected=bool(selected_keys and state_key in selected_keys),
        is_primary=bool(primary_key is not None and state_key == primary_key),
    )


def get_plan_targets(session, selected_only=False):
    selected_targets = session.selection.get_selected_plan_targets()
    selected_keys = {
        session.selection.get_plan_target_state_key(target_kind, target_obj)
        for target_kind, target_obj in selected_targets
    }
    selected_keys.discard(None)
    primary_key = None
    primary_kind, primary_obj = session.selection.get_selected_plan_target()
    if primary_kind and primary_obj:
        primary_key = session.selection.get_plan_target_state_key(primary_kind, primary_obj)

    if selected_only:
        source_targets = selected_targets
    else:
        source_targets = []
        seen = set()
        active_storey_name = getattr(session.active_storey, "Name", None)
        provider_refresh_scope = (
            session._plan_provider_refresh_cache_scope()
            if hasattr(session, "_plan_provider_refresh_cache_scope")
            else nullcontext()
        )
        with provider_refresh_scope:
            for obj in getattr(session.doc, "Objects", []) or []:
                target_kind, target_obj = session.selection.get_plan_target_for_object(obj)
                if not target_kind or not target_obj:
                    continue
                state_key = session.selection.get_plan_target_state_key(target_kind, target_obj)
                if state_key is None or state_key in seen:
                    continue
                semantic_obj = session.visibility.get_plan_semantic_object(target_obj)
                if active_storey_name is not None:
                    storeys = session.visibility.get_object_storeys(semantic_obj or target_obj)
                    if storeys and not any(parent.Name == active_storey_name for parent in storeys):
                        continue
                seen.add(state_key)
                source_targets.append((target_kind, target_obj))

    records = []
    for target_kind, target_obj in source_targets:
        target_record = session._make_plan_target_record(
            target_kind,
            target_obj,
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
    return session.visibility.get_plan_semantic_object(session.resolve_plan_target_object(target))
