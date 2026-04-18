# SPDX-License-Identifier: LGPL-2.1-or-later

"""Target records exposed by BIM Plan Edit integrations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanTarget:
    kind: str
    document_name: str = ""
    object_name: str = ""
    label: str = ""
    semantic_document_name: str = ""
    semantic_object_name: str = ""
    semantic_label: str = ""
    is_selected: bool = False
    is_primary: bool = False


def get_plan_target_kind_for_object(session, obj):
    if session._is_hosted_opening_object(obj):
        return "opening"
    if session._is_plan_symbol_instance(obj):
        return "symbol"
    if session._is_plan_region_object(obj):
        return "region"
    if session._is_plan_selectable_wall(obj):
        return "wall"
    if session._is_plan_space_object(obj):
        return "space"
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
        target_kind = session._get_plan_target_kind_for_object(candidate)
        if target_kind:
            return (target_kind, candidate)

    semantic_obj = session._get_plan_semantic_object(obj)
    semantic_name = getattr(semantic_obj, "Name", None)
    if semantic_obj and semantic_name not in seen:
        target_kind = session._get_plan_target_kind_for_object(semantic_obj)
        if target_kind:
            return (target_kind, semantic_obj)

    return (None, None)
