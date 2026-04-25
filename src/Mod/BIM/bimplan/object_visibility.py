# SPDX-License-Identifier: LGPL-2.1-or-later

"""Object classification and visibility helpers for BIM Plan Edit."""

from __future__ import annotations


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _perf_describe_object(session, obj):
    return session.performance.plan_perf_describe_object(obj)


def is_live_document_object(_session, obj):
    if obj is None:
        return False
    try:
        _ = obj.Name
        return True
    except (AttributeError, ReferenceError, RuntimeError):
        return False


def get_document_object_key(_session, obj):
    if obj is None:
        return None
    try:
        return (
            getattr(getattr(obj, "Document", None), "Name", None),
            getattr(obj, "Name", None),
        )
    except Exception:
        return None


def safe_plan_object_name(_session, obj):
    if obj is None:
        return ""
    try:
        return str(getattr(obj, "Name", "") or "")
    except Exception:
        return ""


def copy_placement(_session, placement):
    if placement is None:
        return FreeCAD.Placement()
    try:
        return placement.copy()
    except Exception:
        return FreeCAD.Placement(placement)


def get_plan_object_global_placement(session, obj):
    if not obj:
        return FreeCAD.Placement()
    if hasattr(obj, "getGlobalPlacement"):
        try:
            placement = obj.getGlobalPlacement()
            if placement is not None:
                return placement
        except Exception:
            pass
    return getattr(obj, "Placement", FreeCAD.Placement())


def invalidate_plan_classification_cache(session):
    cache_state = session.overlay_cache_state
    cache_state.plan_semantic_object_cache.clear()
    cache_state.plan_object_storeys_cache.clear()
    cache_state.plan_symbol_instances_cache = None
    cache_state.plan_space_instances_cache = None
    cache_state.plan_region_instances_cache = None
    cache_state.symbol_overlay_screen_cache.clear()


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
    obj = get_plan_semantic_object(session, obj)
    if getattr(obj, "IfcType", "") == "Slab":
        return True
    try:
        import Draft

        return Draft.getType(obj) == "Structure" and getattr(obj, "IfcType", "") == "Slab"
    except Exception:
        return False


def is_direct_plan_equipment_object(_session, obj):
    if not obj:
        return False
    try:
        import Draft

        if Draft.getType(obj) == "Equipment":
            return True
    except Exception:
        pass
    proxy = getattr(obj, "Proxy", None)
    return getattr(proxy, "Type", None) == "Equipment"


def get_direct_plan_symbol_owner(session, obj):
    if not obj:
        return None
    for parent in getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []):
        if not is_direct_plan_equipment_object(session, parent):
            continue
        if obj == getattr(parent, "Base", None):
            return parent
        if obj in (getattr(parent, "PlanSymbols", None) or []):
            return parent
    return None


def get_plan_semantic_object(session, obj):
    key = get_document_object_key(session, obj)
    semantic_cache = session.overlay_cache_state.plan_semantic_object_cache
    if key is not None and key in semantic_cache:
        session.performance.plan_perf_count("semantic_object_cache_hits")
        return semantic_cache[key]

    current = obj
    seen = set()
    while current:
        if not is_live_document_object(session, current):
            current = None
            break
        name = getattr(current, "Name", None)
        if name in seen:
            break
        if name:
            seen.add(name)
        if getattr(current, "TypeId", "") != "App::Link":
            break
        linked = getattr(current, "LinkedObject", None)
        if linked is None and hasattr(current, "getLinkedObject"):
            try:
                linked = current.getLinkedObject(True)
            except TypeError:
                try:
                    linked = current.getLinkedObject()
                except Exception:
                    linked = None
            except Exception:
                linked = None
        if not linked or linked == current:
            break
        current = linked
    owner = get_direct_plan_symbol_owner(session, current)
    result = owner or current or obj
    if key is not None:
        semantic_cache[key] = result
    return result


def get_plan_text_property(_session, obj, property_names, default=""):
    from bimplan.selection import targets as plan_targets

    return plan_targets.get_plan_text_property(obj, property_names, default=default)


def get_plan_float_property(_session, obj, property_names):
    from bimplan.selection import targets as plan_targets

    return plan_targets.get_plan_float_property(obj, property_names)


def is_plan_equipment_object(session, obj):
    if not obj:
        return False
    return is_direct_plan_equipment_object(session, get_plan_semantic_object(session, obj))


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
    if session.document_visuals.is_hidden_library_definition_object(obj):
        return False
    if not is_plan_equipment_object(session, obj):
        return False
    if getattr(obj, "TypeId", "") == "App::Link":
        return True
    semantic_obj = get_plan_semantic_object(session, obj)
    return obj == semantic_obj and has_direct_plan_symbols(semantic_obj)


def is_plan_context_only_object(session, obj):
    if not obj:
        return False
    if is_plan_symbol_instance(session, obj):
        return False
    return (
        is_plan_container_object(obj)
        or is_plan_background_object(session, obj)
        or is_plan_equipment_object(session, obj)
        or is_cabinetry_plan_context_object(obj)
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
    if is_plan_symbol_instance(session, obj):
        return True
    if session.selection.is_plan_region_object(obj):
        return True
    if session.selection.is_plan_space_separator_object(obj):
        return True
    if is_plan_context_only_object(session, obj):
        return True
    semantic_obj = get_plan_semantic_object(session, obj)
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
    key = get_document_object_key(session, obj)
    cache = session.overlay_cache_state.plan_object_storeys_cache
    if key is not None and key in cache:
        _perf_count(session, "object_storeys_cache_hits")
        return list(cache[key])

    storeys = []
    seen = set()
    parents = list(getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []))
    if is_storey_object(obj):
        parents.insert(0, obj)
    for parent in parents:
        if not parent or parent.Name in seen:
            continue
        seen.add(parent.Name)
        if is_storey_object(parent):
            storeys.append(parent)
    if key is not None:
        cache[key] = tuple(storeys)
    return storeys


def capture_object_view_state(session):
    session._saved_object_view_state = {}
    if not session.doc:
        return
    with _perf_trace_span(session, "capture_object_view_state_objects"):
        for obj in session.doc.Objects:
            _perf_count(session, "capture_view_state_objects_scanned")
            register_object_view_state(session, obj)


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
    register_plan_objects(session, (obj,))


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
        add_object_to_active_storey(session, obj)
        register_object_view_state(session, obj)
        registered.append(obj)
    if not registered:
        return
    apply_storey_visibility(session)
    for obj in registered:
        session.document_visuals.refresh_plan_object_footprint_display(obj, request_redraw=False)
    session.viewport.request_view_redraw()


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


def get_supported_plan_visibility(session, obj, state):
    if is_component_addition_object(obj):
        return False
    visibility = state.get("Visibility", True)
    # Hosted openings are commonly hidden in the regular 3D workflow while
    # their wall cuts carry the main visual meaning. In Plan Edit we want
    # their committed footprint symbols to be visible whenever they are a
    # supported plan object.
    if session.openings.is_hosted_opening_object(obj):
        return True
    return visibility


def apply_context_object_selectability(session, obj, view_object):
    if not view_object or not hasattr(view_object, "Selectable"):
        return
    semantic_obj = get_plan_semantic_object(session, obj)
    if semantic_obj is not None and session.document_visuals.is_symbol_visual_dependency(
        semantic_obj,
        obj,
    ):
        try:
            view_object.Selectable = True
        except Exception:
            pass
        return
    # Openings, spaces, and plan regions are selected through Plan Edit's
    # semantic picking paths. Leaving their native 3D view objects
    # selectable lets the viewer replace the intended target with
    # overlapping native hits on button release.
    if session.selection.is_plan_custom_pick_only_object(semantic_obj or obj):
        try:
            view_object.Selectable = False
        except Exception:
            pass
        return
    if not is_plan_context_only_object(session, obj):
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


def _restore_view_object_state(view_object, state):
    for prop, value in state.items():
        if hasattr(view_object, prop):
            try:
                setattr(view_object, prop, value)
            except Exception:
                pass


def _apply_supported_object_view_state(session, obj, view_object, state):
    _perf_count(session, "storey_visibility_supported")
    _restore_view_object_state(view_object, state)
    if hasattr(view_object, "Visibility"):
        try:
            view_object.Visibility = get_supported_plan_visibility(session, obj, state)
        except Exception:
            pass
    apply_context_object_selectability(session, obj, view_object)


def _apply_global_plan_visibility(session):
    with _perf_trace_span(session, "restore_object_view_state_for_global_plan"):
        restore_object_view_state(session)
    for obj in session.doc.Objects:
        _perf_count(session, "storey_visibility_objects_scanned")
        view_object = getattr(obj, "ViewObject", None)
        state = session._saved_object_view_state.get(obj.Name, {})
        if not is_supported_plan_object(session, obj):
            _perf_count(session, "storey_visibility_hidden_unsupported")
            apply_hidden_object_state(view_object)
            continue
        if view_object and hasattr(view_object, "Visibility"):
            try:
                view_object.Visibility = get_supported_plan_visibility(session, obj, state)
            except Exception:
                pass
        apply_context_object_selectability(session, obj, view_object)


def _apply_storey_visibility_for_global_object(session, obj, view_object, state):
    _perf_count(session, "storey_visibility_global_objects")
    if not is_supported_plan_object(session, obj):
        _perf_count(session, "storey_visibility_hidden_unsupported")
        apply_hidden_object_state(view_object)
        return
    _apply_supported_object_view_state(session, obj, view_object, state)


def _apply_storey_visibility_for_active_storey_object(session, obj, view_object, state):
    _perf_count(session, "storey_visibility_active_storey_objects")
    if not is_supported_plan_object(session, obj):
        _perf_count(session, "storey_visibility_hidden_unsupported")
        apply_hidden_object_state(view_object)
        return
    _apply_supported_object_view_state(session, obj, view_object, state)


def _apply_storey_visibility_for_other_storey_object(session, obj, view_object, state):
    _perf_count(session, "storey_visibility_other_storey_objects")
    if hasattr(view_object, "Visibility"):
        try:
            view_object.Visibility = get_supported_plan_visibility(session, obj, state)
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


def apply_storey_visibility(session):
    with _perf_trace_span(
        session,
        "apply_storey_visibility",
        active_storey=_perf_describe_object(session, session.active_storey),
    ):
        if not session.doc or not session._saved_object_view_state:
            return

        active_storey_name = getattr(session.active_storey, "Name", None)

        if active_storey_name is None:
            _apply_global_plan_visibility(session)
            return

        for obj in session.doc.Objects:
            _perf_count(session, "storey_visibility_objects_scanned")
            view_object = getattr(obj, "ViewObject", None)
            state = session._saved_object_view_state.get(obj.Name)
            if not view_object or not state:
                _perf_count(session, "storey_visibility_objects_skipped_no_view_state")
                continue

            storeys = get_object_storeys(session, obj)
            if not storeys:
                _apply_storey_visibility_for_global_object(session, obj, view_object, state)
                continue

            belongs_to_active = any(parent.Name == active_storey_name for parent in storeys)
            if belongs_to_active:
                _apply_storey_visibility_for_active_storey_object(session, obj, view_object, state)
                continue

            _apply_storey_visibility_for_other_storey_object(session, obj, view_object, state)


class PlanVisibilityAPI:
    """Owned session surface for Plan Edit object visibility and classification."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def invalidate_plan_classification_cache(self, *args, **kwargs):
        return invalidate_plan_classification_cache(self.session, *args, **kwargs)

    def is_live_document_object(self, *args, **kwargs):
        return is_live_document_object(self.session, *args, **kwargs)

    def get_document_object_key(self, *args, **kwargs):
        return get_document_object_key(self.session, *args, **kwargs)

    def safe_plan_object_name(self, *args, **kwargs):
        return safe_plan_object_name(self.session, *args, **kwargs)

    def copy_placement(self, *args, **kwargs):
        return copy_placement(self.session, *args, **kwargs)

    def get_plan_object_global_placement(self, *args, **kwargs):
        return get_plan_object_global_placement(self.session, *args, **kwargs)

    def capture_object_view_state(self, *args, **kwargs):
        return capture_object_view_state(self.session, *args, **kwargs)

    def register_object_view_state(self, *args, **kwargs):
        return register_object_view_state(self.session, *args, **kwargs)

    def add_object_to_active_storey(self, *args, **kwargs):
        return add_object_to_active_storey(self.session, *args, **kwargs)

    def register_plan_object(self, *args, **kwargs):
        return register_plan_object(self.session, *args, **kwargs)

    def register_plan_objects(self, *args, **kwargs):
        return register_plan_objects(self.session, *args, **kwargs)

    def restore_object_view_state(self, *args, **kwargs):
        return restore_object_view_state(self.session, *args, **kwargs)

    def is_storey_object(self, *args, **kwargs):
        return is_storey_object(self.session, *args, **kwargs)

    def is_plan_container_object(self, *args, **kwargs):
        return is_plan_container_object(self.session, *args, **kwargs)

    def is_plan_background_object(self, *args, **kwargs):
        return is_plan_background_object(self.session, *args, **kwargs)

    def is_direct_plan_equipment_object(self, *args, **kwargs):
        return is_direct_plan_equipment_object(self.session, *args, **kwargs)

    def get_direct_plan_symbol_owner(self, *args, **kwargs):
        return get_direct_plan_symbol_owner(self.session, *args, **kwargs)

    def get_plan_semantic_object(self, *args, **kwargs):
        return get_plan_semantic_object(self.session, *args, **kwargs)

    def get_plan_text_property(self, *args, **kwargs):
        return get_plan_text_property(self.session, *args, **kwargs)

    def get_plan_float_property(self, *args, **kwargs):
        return get_plan_float_property(self.session, *args, **kwargs)

    def is_plan_equipment_object(self, *args, **kwargs):
        return is_plan_equipment_object(self.session, *args, **kwargs)

    def is_cabinetry_plan_context_object(self, *args, **kwargs):
        return is_cabinetry_plan_context_object(self.session, *args, **kwargs)

    def has_direct_plan_symbols(self, *args, **kwargs):
        return has_direct_plan_symbols(self.session, *args, **kwargs)

    def is_plan_symbol_instance(self, *args, **kwargs):
        return is_plan_symbol_instance(self.session, *args, **kwargs)

    def is_plan_context_only_object(self, *args, **kwargs):
        return is_plan_context_only_object(self.session, *args, **kwargs)

    def is_component_addition_object(self, *args, **kwargs):
        return is_component_addition_object(self.session, *args, **kwargs)

    def is_supported_plan_object(self, *args, **kwargs):
        return is_supported_plan_object(self.session, *args, **kwargs)

    def get_supported_plan_visibility(self, *args, **kwargs):
        return get_supported_plan_visibility(self.session, *args, **kwargs)

    def apply_context_object_selectability(self, *args, **kwargs):
        return apply_context_object_selectability(self.session, *args, **kwargs)

    def apply_hidden_object_state(self, *args, **kwargs):
        return apply_hidden_object_state(self.session, *args, **kwargs)

    def get_object_storeys(self, *args, **kwargs):
        return get_object_storeys(self.session, *args, **kwargs)

    def apply_storey_visibility(self, *args, **kwargs):
        return apply_storey_visibility(self.session, *args, **kwargs)
