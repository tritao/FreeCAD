# SPDX-License-Identifier: LGPL-2.1-or-later

"""Plan-object classification helpers for BIM Plan Edit."""

from __future__ import annotations


def is_storey_object(obj):
    if not obj:
        return False
    if getattr(obj, "IfcType", "") == "Building Storey":
        return True
    try:
        import Draft

        return Draft.getType(obj) == "Floor"
    except Exception:
        return False


def is_plan_container_object(obj):
    if not obj:
        return False
    if getattr(obj, "IfcType", "") in {"Site", "Building", "Building Storey"}:
        return True
    if hasattr(obj, "isDerivedFrom") and obj.isDerivedFrom("App::DocumentObjectGroup"):
        return True
    if hasattr(obj, "hasExtension") and obj.hasExtension("App::GroupExtension"):
        return True
    try:
        import Draft

        return Draft.getType(obj) in {
            "Site",
            "Building",
            "Floor",
            "BuildingPart",
            "Group",
        }
    except Exception:
        return False


def is_plan_background_object(session, obj):
    if not obj:
        return False
    obj = session._get_plan_semantic_object(obj)
    if getattr(obj, "IfcType", "") == "Slab":
        return True
    try:
        import Draft

        return Draft.getType(obj) == "Structure" and getattr(obj, "IfcType", "") == "Slab"
    except Exception:
        return False


def is_plan_equipment_object(session, obj):
    if not obj:
        return False
    return session._is_direct_plan_equipment_object(session._get_plan_semantic_object(obj))


def is_cabinetry_plan_context_object(obj):
    if not obj:
        return False
    proxy_type = str(getattr(getattr(obj, "Proxy", None), "Type", "") or "")
    return proxy_type in {
        "CabinetryApplianceTower",
        "CabinetryBaseCabinet",
        "CabinetryBlindCornerBaseCabinet",
        "CabinetryFridgeSurround",
        "CabinetryProject",
        "CabinetryRunAccessories",
        "CabinetryRunApplianceRepresentation",
        "CabinetryRunGuide",
        "CabinetryRunProfileRepresentation",
        "CabinetryRunReservation",
        "CabinetryRunReservationRepresentation",
        "CabinetryTallCabinet",
        "CabinetryVanityBase",
        "CabinetryWallCabinet",
        "CabinetZone",
        "CabinetRun",
        "CabinetRunJunction",
    }


def has_direct_plan_symbols(obj):
    if not obj:
        return False
    try:
        if "PlanSymbols" not in (getattr(obj, "PropertiesList", []) or []):
            return False
        return any(symbol is not None for symbol in (getattr(obj, "PlanSymbols", []) or []))
    except Exception:
        return False


def is_plan_symbol_instance(session, obj):
    if not obj:
        return False
    if session._is_hidden_library_definition_object(obj):
        return False
    if not session._is_plan_equipment_object(obj):
        return False
    if getattr(obj, "TypeId", "") == "App::Link":
        return True
    semantic_obj = session._get_plan_semantic_object(obj)
    return obj == semantic_obj and session._has_direct_plan_symbols(semantic_obj)


def is_plan_context_only_object(session, obj):
    if not obj:
        return False
    if session._is_plan_symbol_instance(obj):
        return False
    return (
        session._is_plan_container_object(obj)
        or session._is_plan_background_object(obj)
        or session._is_plan_equipment_object(obj)
        or session._is_cabinetry_plan_context_object(obj)
    )


def is_component_addition_object(obj):
    if not obj:
        return False
    for parent in getattr(obj, "InList", []) or []:
        try:
            if obj in getattr(parent, "Additions", []):
                return True
        except Exception:
            pass
    return False


def is_supported_plan_object(session, obj):
    if not obj:
        return False
    if session._is_plan_symbol_instance(obj):
        return True
    if session._is_plan_region_object(obj):
        return True
    if session._is_plan_space_separator_object(obj):
        return True
    if session._is_plan_context_only_object(obj):
        return True
    semantic_obj = session._get_plan_semantic_object(obj)
    try:
        import Draft

        obj_type = Draft.getType(semantic_obj)
    except Exception:
        obj_type = ""

    if obj_type in {"Wall", "Window", "Space", "Axis", "AxisSystem"}:
        return True

    if getattr(semantic_obj, "IfcType", "") in {
        "Wall",
        "Window",
        "Door",
        "Space",
        "Column",
        "Grid",
        "Stair",
        "Curtain Wall",
    }:
        return True

    return False


def get_object_storeys(session, obj):
    if not obj:
        return []
    key = session._get_document_object_key(obj)
    if key is not None and key in session._plan_object_storeys_cache:
        session._plan_perf_count("object_storeys_cache_hits")
        return list(session._plan_object_storeys_cache[key])

    storeys = []
    seen = set()
    parents = list(getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []))
    if session._is_storey_object(obj):
        parents.insert(0, obj)
    for parent in parents:
        if not parent or parent.Name in seen:
            continue
        seen.add(parent.Name)
        if session._is_storey_object(parent):
            storeys.append(parent)
    if key is not None:
        session._plan_object_storeys_cache[key] = tuple(storeys)
    return storeys
