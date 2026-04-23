# SPDX-License-Identifier: LGPL-2.1-or-later

"""Object visibility and plan-object classification helpers for BIM Plan Edit."""

from __future__ import annotations


def capture_object_view_state(session):
    session._saved_object_view_state = {}
    if not session.doc:
        return
    with session._plan_perf_trace_span("capture_object_view_state_objects"):
        for obj in session.doc.Objects:
            session._plan_perf_count("capture_view_state_objects_scanned")
            session._register_object_view_state(obj)


def register_object_view_state(session, obj):
    if not obj:
        return
    view_object = getattr(obj, "ViewObject", None)
    if not view_object:
        return
    state = {}
    for prop in ("Visibility", "Transparency", "Selectable"):
        if hasattr(view_object, prop):
            try:
                state[prop] = getattr(view_object, prop)
            except Exception:
                pass
    if state:
        session._saved_object_view_state[obj.Name] = state


def add_object_to_active_storey(session, obj):
    storey = session.active_storey
    if not storey or not obj:
        return False
    if obj is storey or obj in getattr(storey, "InListRecursive", []):
        return True
    try:
        if hasattr(storey, "addObject"):
            storey.addObject(obj)
            return True
    except Exception:
        pass
    group = getattr(storey, "Group", None)
    if group is None:
        return False
    try:
        if obj not in group:
            storey.Group = list(group) + [obj]
        return True
    except Exception:
        return False


def register_plan_object(session, obj):
    session._register_plan_objects((obj,))


def register_plan_objects(session, objects):
    registered = []
    seen_names = set()
    for obj in tuple(objects or ()):
        if not obj:
            continue
        name = getattr(obj, "Name", None)
        if name and name in seen_names:
            continue
        if name:
            seen_names.add(name)
        session._add_object_to_active_storey(obj)
        session._register_object_view_state(obj)
        registered.append(obj)
    if not registered:
        return
    session._apply_storey_visibility()
    for obj in registered:
        session._refresh_plan_object_footprint_display(obj, request_redraw=False)
    session._request_view_redraw()


def restore_object_view_state(session):
    if not session.doc or not session._saved_object_view_state:
        return
    try:
        doc = session.doc
        _ = doc.Name
    except Exception:
        session.doc = None
        return
    for obj_name, state in session._saved_object_view_state.items():
        try:
            obj = doc.getObject(obj_name)
        except Exception:
            session.doc = None
            return
        if not obj:
            continue
        view_object = getattr(obj, "ViewObject", None)
        if not view_object:
            continue
        for prop, value in state.items():
            if hasattr(view_object, prop):
                try:
                    setattr(view_object, prop, value)
                except Exception:
                    pass


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


def get_supported_plan_visibility(session, obj, state):
    if session._is_component_addition_object(obj):
        return False
    visibility = state.get("Visibility", True)
    # Hosted openings are commonly hidden in the regular 3D workflow while
    # their wall cuts carry the main visual meaning. In Plan Edit we want
    # their committed footprint symbols to be visible whenever they are a
    # supported plan object.
    if session._is_hosted_opening_object(obj):
        return True
    return visibility


def apply_context_object_selectability(session, obj, view_object):
    if not view_object or not hasattr(view_object, "Selectable"):
        return
    semantic_obj = session._get_plan_semantic_object(obj)
    if semantic_obj is not None and session._is_symbol_visual_dependency(semantic_obj, obj):
        try:
            view_object.Selectable = True
        except Exception:
            pass
        return
    # Openings, spaces, and plan regions are selected through Plan Edit's
    # semantic picking paths. Leaving their native 3D view objects
    # selectable lets the viewer replace the intended target with
    # overlapping native hits on button release.
    if session._is_plan_custom_pick_only_object(semantic_obj or obj):
        try:
            view_object.Selectable = False
        except Exception:
            pass
        return
    if not session._is_plan_context_only_object(obj):
        return
    try:
        view_object.Selectable = False
    except Exception:
        pass


def apply_hidden_object_state(view_object):
    if not view_object:
        return
    if hasattr(view_object, "Visibility"):
        try:
            view_object.Visibility = False
        except Exception:
            pass
    if hasattr(view_object, "Selectable"):
        try:
            view_object.Selectable = False
        except Exception:
            pass


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


def apply_storey_visibility(session):
    with session._plan_perf_trace_span(
        "apply_storey_visibility",
        active_storey=session._plan_perf_describe_object(session.active_storey),
    ):
        if not session.doc or not session._saved_object_view_state:
            return

        active_storey_name = getattr(session.active_storey, "Name", None)

        if active_storey_name is None:
            with session._plan_perf_trace_span("restore_object_view_state_for_global_plan"):
                session._restore_object_view_state()
            for obj in session.doc.Objects:
                session._plan_perf_count("storey_visibility_objects_scanned")
                view_object = getattr(obj, "ViewObject", None)
                state = session._saved_object_view_state.get(obj.Name, {})
                if not session._is_supported_plan_object(obj):
                    session._plan_perf_count("storey_visibility_hidden_unsupported")
                    session._apply_hidden_object_state(view_object)
                    continue
                session._plan_perf_count("storey_visibility_supported")
                if view_object and hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = session._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                session._apply_context_object_selectability(obj, view_object)
            return

        for obj in session.doc.Objects:
            session._plan_perf_count("storey_visibility_objects_scanned")
            view_object = getattr(obj, "ViewObject", None)
            state = session._saved_object_view_state.get(obj.Name)
            if not view_object or not state:
                session._plan_perf_count("storey_visibility_objects_skipped_no_view_state")
                continue

            storeys = session._get_object_storeys(obj)
            if not storeys:
                session._plan_perf_count("storey_visibility_global_objects")
                if not session._is_supported_plan_object(obj):
                    session._plan_perf_count("storey_visibility_hidden_unsupported")
                    session._apply_hidden_object_state(view_object)
                    continue
                session._plan_perf_count("storey_visibility_supported")
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                if hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = session._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                session._apply_context_object_selectability(obj, view_object)
                continue

            belongs_to_active = any(parent.Name == active_storey_name for parent in storeys)
            if belongs_to_active:
                session._plan_perf_count("storey_visibility_active_storey_objects")
                for prop, value in state.items():
                    if hasattr(view_object, prop):
                        try:
                            setattr(view_object, prop, value)
                        except Exception:
                            pass
                if not session._is_supported_plan_object(obj):
                    session._plan_perf_count("storey_visibility_hidden_unsupported")
                    session._apply_hidden_object_state(view_object)
                    continue
                session._plan_perf_count("storey_visibility_supported")
                if hasattr(view_object, "Visibility"):
                    try:
                        view_object.Visibility = session._get_supported_plan_visibility(obj, state)
                    except Exception:
                        pass
                session._apply_context_object_selectability(obj, view_object)
                continue

            session._plan_perf_count("storey_visibility_other_storey_objects")
            if hasattr(view_object, "Visibility"):
                try:
                    view_object.Visibility = session._get_supported_plan_visibility(obj, state)
                except Exception:
                    pass
            if hasattr(view_object, "Transparency"):
                try:
                    view_object.Transparency = max(int(state.get("Transparency", 0)), 85)
                except Exception:
                    pass
            if hasattr(view_object, "Selectable"):
                try:
                    view_object.Selectable = False
                except Exception:
                    pass
