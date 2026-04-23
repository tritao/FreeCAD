# SPDX-License-Identifier: LGPL-2.1-or-later

"""Document-driven visual refresh helpers for BIM Plan Edit."""

from contextlib import contextmanager

_OPENING_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Base",
    "Hosts",
    "WindowParts",
    "IfcType",
}
_WALL_VISUAL_PROPERTIES = {"Shape", "Additions", "Subtractions", "Hosts"}
_SYMBOL_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Base",
    "PlanSymbols",
    "LinkedObject",
}
_SPACE_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Label",
    "Boundaries",
}
_REGION_VISUAL_PROPERTIES = {
    "Shape",
    "Placement",
    "Label",
    "Points",
    "Scheme",
    "RegionType",
    "ParentSpace",
}
OPENING_VISUAL_PROPERTIES = _OPENING_VISUAL_PROPERTIES
WALL_VISUAL_PROPERTIES = _WALL_VISUAL_PROPERTIES
SYMBOL_VISUAL_PROPERTIES = _SYMBOL_VISUAL_PROPERTIES
SPACE_VISUAL_PROPERTIES = _SPACE_VISUAL_PROPERTIES
REGION_VISUAL_PROPERTIES = _REGION_VISUAL_PROPERTIES
_PLAN_VISUAL_HOVERED_WALL = "hovered_wall"
_PLAN_VISUAL_HOVERED_OPENING = "hovered_opening"
_PLAN_VISUAL_HOVERED_SYMBOL = "hovered_symbol"
_PLAN_VISUAL_HOVERED_PROVIDER = "hovered_provider"
_PLAN_VISUAL_HOVERED_SPACE = "hovered_space"
_PLAN_VISUAL_HOVERED_REGION = "hovered_region"
_PLAN_VISUAL_SELECTED_PROVIDER = "selected_provider"
_PLAN_VISUAL_SELECTED_OPENING = "selected_opening"
_PLAN_VISUAL_SELECTED_SYMBOL = "selected_symbol"
_PLAN_VISUAL_SELECTED_SPACE = "selected_space"
_PLAN_VISUAL_SELECTED_REGION = "selected_region"
_PLAN_VISUAL_SECONDARY_SELECTION = "secondary_selection"
_PLAN_VISUAL_WALL_GRIPS = "wall_grips"
_PLAN_VISUAL_PROVIDER_OVERLAYS = "provider_overlays"


def has_direct_true_property(obj, prop_name):
    if not obj:
        return False
    try:
        if prop_name not in (getattr(obj, "PropertiesList", []) or []):
            return False
        return bool(getattr(obj, prop_name))
    except Exception:
        return False


def is_hidden_library_definition_object(obj):
    if not obj:
        return False
    if has_direct_true_property(obj, "IsLibraryDefinition"):
        return True
    for parent in getattr(obj, "InListRecursive", []) or getattr(obj, "InList", []):
        if has_direct_true_property(parent, "IsLibraryDefinition"):
            return True
    return False


def should_register_created_plan_object(session, obj):
    if session._tearing_down or not obj or not session.doc:
        return False
    try:
        if getattr(obj, "Document", None) != session.doc:
            return False
        if session._is_hidden_library_definition_object(obj):
            return False
        return session._is_supported_plan_object(obj)
    except ReferenceError:
        return False


def queue_created_plan_object(session, obj):
    if not obj or not getattr(obj, "Name", None):
        return
    session._pending_created_plan_objects[obj.Name] = obj
    if session._are_document_visual_updates_deferred():
        session._created_plan_objects_flush_deferred = True
        return
    if session._created_plan_objects_flush_queued:
        return
    session._created_plan_objects_flush_queued = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, session._flush_created_plan_objects)
    except Exception:
        session._flush_created_plan_objects()


def flush_created_plan_objects(session, force=False):
    session._created_plan_objects_flush_queued = False
    if session._are_document_visual_updates_deferred() and not force:
        session._created_plan_objects_flush_deferred = True
        return
    session._created_plan_objects_flush_deferred = False
    pending = list(session._pending_created_plan_objects.values())
    session._pending_created_plan_objects.clear()
    eligible = []
    for obj in pending:
        if not session._should_register_created_plan_object(obj):
            continue
        eligible.append(obj)
    session._register_plan_objects(eligible)


def are_document_visual_updates_deferred(session):
    return session._document_visual_update_defer_depth > 0


def defer_document_visual_refresh(session):
    session._document_visual_refresh_deferred = True


@contextmanager
def defer_document_visual_updates(session):
    """Batch document observer visual work while an external command mutates the model."""

    session._document_visual_update_defer_depth += 1
    try:
        yield
    finally:
        session._document_visual_update_defer_depth = max(
            0,
            session._document_visual_update_defer_depth - 1,
        )
        if session._document_visual_update_defer_depth or session._tearing_down:
            return
        if session._created_plan_objects_flush_deferred or session._pending_created_plan_objects:
            session._created_plan_objects_flush_deferred = False
            session._document_visual_update_defer_depth = 1
            try:
                session._flush_created_plan_objects(force=True)
            finally:
                session._document_visual_update_defer_depth = 0
        if session._document_visual_refresh_deferred:
            session._document_visual_refresh_deferred = False
            if not session._document_is_alive():
                return
            session._invalidate_document_dependent_plan_visuals()
            session._refresh_primary_selected_plan_target()
            session._refresh_task_panel_status(selection_only=True)


def is_opening_visual_dependency(opening, obj):
    if not opening or not obj:
        return False
    if obj == opening:
        return True
    if obj == getattr(opening, "Base", None):
        return True
    return obj in (getattr(opening, "Hosts", None) or [])


def refresh_selected_opening_visuals(session):
    session._sync_selected_opening_overlay()
    session._sync_selected_opening_handles()
    session._sync_selected_wall_opening_context_overlay()
    session._request_view_redraw()


def is_symbol_visual_dependency(session, symbol, obj):
    if not session._is_plan_symbol_instance(symbol) or not obj:
        return False
    if obj == symbol:
        return True
    semantic_obj = session._get_plan_semantic_object(symbol)
    if obj == semantic_obj:
        return True
    if obj == getattr(semantic_obj, "Base", None):
        return True
    return obj in (getattr(semantic_obj, "PlanSymbols", None) or [])


def refresh_plan_object_footprint_display(session, obj, *, request_redraw=True):
    if not session._is_supported_plan_object(obj):
        return
    session._invalidate_plan_overlay_geometry_cache(obj)
    semantic_obj = session._get_plan_semantic_object(obj)
    refresh_targets = []
    for candidate in (semantic_obj, obj):
        if not candidate:
            continue
        name = getattr(candidate, "Name", None)
        if not name or any(getattr(target, "Name", None) == name for target in refresh_targets):
            continue
        refresh_targets.append(candidate)

    refreshed = False
    for candidate in refresh_targets:
        view_object = getattr(candidate, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object else None
        if not proxy:
            continue
        if (
            not hasattr(proxy, "ensureFootprintGroup")
            and not hasattr(proxy, "updateFootprint")
            and not hasattr(proxy, "refreshFootprint")
        ):
            continue
        try:
            if hasattr(proxy, "refreshFootprint"):
                proxy.refreshFootprint()
            else:
                if hasattr(proxy, "ensureFootprintGroup"):
                    proxy.ensureFootprintGroup(view_object)
                if hasattr(proxy, "updateFootprint"):
                    proxy.updateFootprint()
            if hasattr(view_object, "update"):
                view_object.update()
            refreshed = True
        except TypeError:
            try:
                if hasattr(proxy, "refreshFootprint"):
                    proxy.refreshFootprint(view_object)
                else:
                    if hasattr(proxy, "ensureFootprintGroup"):
                        proxy.ensureFootprintGroup(view_object)
                    if hasattr(proxy, "updateFootprint"):
                        proxy.updateFootprint()
                if hasattr(view_object, "update"):
                    view_object.update()
                refreshed = True
            except Exception:
                continue
        except Exception:
            continue

    view_object = getattr(obj, "ViewObject", None)
    if view_object and hasattr(view_object, "update"):
        try:
            view_object.update()
        except Exception:
            pass
    if not refreshed:
        return
    if request_redraw:
        session._request_view_redraw()


def refresh_opening_footprint_display(session, opening):
    if not session._is_hosted_opening_object(opening):
        return
    session._refresh_plan_object_footprint_display(opening)


def refresh_wall_footprint_display(session, wall):
    if not wall:
        return
    session._refresh_plan_object_footprint_display(wall)


def refresh_opening_host_footprint_displays(session, opening):
    if not session._is_hosted_opening_object(opening):
        return
    for host in getattr(opening, "Hosts", None) or []:
        session._refresh_wall_footprint_display(host)


def queue_recompute_opening_hosts(session, *openings):
    if (
        session._tearing_down
        or session._opening_host_recompute_queued
        or session._opening_host_recompute_running
    ):
        return
    hosts = []
    for opening in openings:
        if not session._is_hosted_opening_object(opening):
            continue
        hosts.extend(getattr(opening, "Hosts", None) or [])
    hosts = [host for host in dict.fromkeys(hosts) if host]
    if not hosts:
        return
    session._opening_host_recompute_queued = True
    session._flush_recompute_opening_hosts(hosts)


def flush_recompute_opening_hosts(session, hosts):
    session._opening_host_recompute_queued = False
    if session._tearing_down or session._opening_host_recompute_running or not session.doc:
        return
    session._opening_host_recompute_running = True
    try:
        for host in hosts:
            try:
                host.touch()
            except Exception:
                continue
        session.doc.recompute()
    finally:
        session._opening_host_recompute_running = False


def queue_hard_refresh_selected_opening_visuals(session):
    if session._tearing_down or session._selected_opening_hard_refresh_queued:
        return
    session._selected_opening_hard_refresh_queued = True
    session._clear_selected_opening_overlay()
    session._clear_selected_opening_handles()
    session._request_view_redraw()
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, session._flush_hard_refresh_selected_opening_visuals)
    except Exception:
        session._flush_hard_refresh_selected_opening_visuals()


def flush_hard_refresh_selected_opening_visuals(session):
    session._selected_opening_hard_refresh_queued = False
    if session._tearing_down or session.current_tool != "Select":
        return
    opening = session._get_selected_plan_target_object("opening")
    if not session._is_hosted_opening_object(opening):
        return
    session._sync_selected_opening_overlay()
    session._sync_selected_opening_handles()
    session._request_view_redraw()


def slot_created_object(session, obj):
    if session._tearing_down:
        return
    session._invalidate_plan_provider_document_cache()
    session._provider_overlay_state = None
    session._invalidate_plan_classification_cache()
    session._invalidate_wall_hosted_openings_cache()
    session._queue_created_plan_object(obj)


def slot_changed_object(session, obj, prop):
    if session._tearing_down:
        return
    session._invalidate_plan_provider_document_cache()
    session._provider_overlay_state = None
    session._invalidate_plan_classification_cache()
    session._invalidate_wall_hosted_openings_cache()
    if session._are_document_visual_updates_deferred():
        session._defer_document_visual_refresh()
        return
    if session.current_tool != "Select":
        return
    session._sanitize_plan_target_references()
    selected_wall = session._get_selected_plan_target_object("wall")
    selected_opening = session._get_selected_plan_target_object("opening")
    selected_symbol = session._get_selected_plan_target_object("symbol")
    selected_region = session._get_selected_plan_target_object("region")
    selected_space = session._get_selected_plan_target_object("space")
    if selected_region and obj == selected_region and prop in _REGION_VISUAL_PROPERTIES:
        session._refresh_plan_object_footprint_display(selected_region)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_REGION)
        session._refresh_task_panel_status()
        return
    if (
        session.hovered_region
        and not session._is_selected_plan_target("region", session.hovered_region)
        and obj == session.hovered_region
        and prop in _REGION_VISUAL_PROPERTIES
    ):
        session._refresh_plan_object_footprint_display(session.hovered_region)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_REGION)
        return
    if selected_space and obj == selected_space and prop in _SPACE_VISUAL_PROPERTIES:
        session._refresh_plan_object_footprint_display(selected_space)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SPACE)
        session._refresh_task_panel_status()
        return
    if (
        session.hovered_space
        and not session._is_selected_plan_target("space", session.hovered_space)
        and obj == session.hovered_space
        and prop in _SPACE_VISUAL_PROPERTIES
    ):
        session._refresh_plan_object_footprint_display(session.hovered_space)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SPACE)
        return
    secondary_overlay_refresh = False
    for target_kind, target_obj in session._get_secondary_selected_plan_targets():
        if target_kind == "region" and obj == target_obj and prop in _REGION_VISUAL_PROPERTIES:
            session._refresh_plan_object_footprint_display(target_obj)
            secondary_overlay_refresh = True
        elif target_kind == "space" and obj == target_obj and prop in _SPACE_VISUAL_PROPERTIES:
            session._refresh_plan_object_footprint_display(target_obj)
            secondary_overlay_refresh = True
        elif (
            target_kind == "symbol"
            and session._is_symbol_visual_dependency(target_obj, obj)
            and prop in _SYMBOL_VISUAL_PROPERTIES
        ):
            session._refresh_plan_object_footprint_display(target_obj)
            secondary_overlay_refresh = True
        elif (
            target_kind == "opening"
            and session._is_opening_visual_dependency(target_obj, obj)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            session._refresh_opening_footprint_display(target_obj)
            session._refresh_opening_host_footprint_displays(target_obj)
            secondary_overlay_refresh = True
        elif target_kind == "wall" and obj == target_obj and prop in _WALL_VISUAL_PROPERTIES:
            secondary_overlay_refresh = True
    if secondary_overlay_refresh:
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SECONDARY_SELECTION)
        return
    if (
        session._is_symbol_visual_dependency(selected_symbol, obj)
        and prop in _SYMBOL_VISUAL_PROPERTIES
    ):
        session._refresh_plan_object_footprint_display(selected_symbol)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SYMBOL)
        return
    if (
        session._is_symbol_visual_dependency(session.hovered_symbol, obj)
        and prop in _SYMBOL_VISUAL_PROPERTIES
    ):
        session._refresh_plan_object_footprint_display(session.hovered_symbol)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SYMBOL)
        return
    if (
        session._is_opening_visual_dependency(selected_opening, obj)
        and prop in _OPENING_VISUAL_PROPERTIES
    ):
        session._refresh_opening_footprint_display(selected_opening)
        session._refresh_opening_host_footprint_displays(selected_opening)
        session._queue_plan_overlay_visual_refresh(
            _PLAN_VISUAL_SELECTED_OPENING,
            _PLAN_VISUAL_HOVERED_OPENING,
        )
        return
    if (
        session._is_opening_visual_dependency(session.hovered_opening, obj)
        and prop in _OPENING_VISUAL_PROPERTIES
    ):
        session._refresh_opening_footprint_display(session.hovered_opening)
        session._refresh_opening_host_footprint_displays(session.hovered_opening)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_OPENING)
        return
    if (
        session.hovered_wall
        and obj in session._get_wall_hosted_openings(session.hovered_wall)
        and prop in _OPENING_VISUAL_PROPERTIES
    ):
        session._refresh_opening_footprint_display(obj)
        session._refresh_opening_host_footprint_displays(obj)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
        return
    if (
        selected_wall
        and obj in session._get_wall_hosted_openings(selected_wall)
        and prop in _OPENING_VISUAL_PROPERTIES
    ):
        session._refresh_opening_footprint_display(obj)
        session._refresh_opening_host_footprint_displays(obj)
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_WALL_GRIPS)
        return
    if obj == session.hovered_wall and prop in _WALL_VISUAL_PROPERTIES:
        session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
        return
    if obj != selected_wall:
        return
    if prop not in _WALL_VISUAL_PROPERTIES:
        return
    session._refresh_wall_hosted_opening_footprints(obj)
    session._schedule_selected_wall_reset(prop, obj)


def slot_deleted_object(session, obj):
    if session._tearing_down:
        return
    session._invalidate_plan_provider_document_cache()
    session._provider_overlay_state = None
    session._invalidate_plan_classification_cache()
    session._invalidate_wall_hosted_openings_cache()
    session._invalidate_plan_overlay_geometry_cache(obj)
    if session._are_document_visual_updates_deferred():
        session._defer_document_visual_refresh()
        return
    if obj == session.hovered_wall:
        session.hovered_wall = None
        session._clear_hovered_wall_overlay()
    if obj == session.hovered_opening:
        session.hovered_opening = None
        session._clear_hovered_opening_overlay()
    if obj == session.hovered_symbol:
        session.hovered_symbol = None
        session._clear_hovered_symbol_overlay()
    if obj == session.hovered_provider:
        session.hovered_provider = None
        session._clear_hovered_provider_overlay()
    if obj == session.hovered_space:
        session.hovered_space = None
        session._clear_hovered_space_overlay()
    if obj == session.hovered_region:
        session.hovered_region = None
        session._clear_hovered_region_overlay()
    if session._clear_selected_plan_target_if_matches("opening", obj):
        session._refresh_selected_opening_visuals()
        return
    if session._clear_selected_plan_target_if_matches("symbol", obj):
        session._refresh_selected_symbol_visuals()
        return
    if session._clear_selected_plan_target_if_matches("region", obj):
        session._refresh_selected_region_visuals()
        session._refresh_task_panel_status()
        return
    if session._clear_selected_plan_target_if_matches("space", obj):
        session._refresh_selected_space_visuals()
        session._refresh_task_panel_status()
        return
    if not session._is_selected_plan_target("wall", obj):
        return
    session._schedule_selected_wall_reset("Deleted", obj)


def invalidate_document_dependent_plan_visuals(session, recompute_opening_hosts=False):
    if session._tearing_down or session._finishing or not session._document_is_alive():
        return
    session._invalidate_plan_provider_document_cache()
    session._invalidate_plan_classification_cache()
    session._invalidate_wall_hosted_openings_cache()
    session._invalidate_plan_overlay_geometry_cache()
    session._sanitize_plan_target_references()
    selected_symbol = session._get_selected_plan_target_object("symbol")
    selected_region = session._get_selected_plan_target_object("region")
    selected_space = session._get_selected_plan_target_object("space")
    selected_opening = session._get_selected_plan_target_object("opening")
    selected_provider = session._get_selected_plan_target_object("provider")
    if selected_symbol:
        session._refresh_plan_object_footprint_display(selected_symbol)
    if session.hovered_symbol and not session._is_selected_plan_target(
        "symbol", session.hovered_symbol
    ):
        session._refresh_plan_object_footprint_display(session.hovered_symbol)
    if selected_region:
        session._refresh_plan_object_footprint_display(selected_region)
    if session.hovered_region and not session._is_selected_plan_target(
        "region", session.hovered_region
    ):
        session._refresh_plan_object_footprint_display(session.hovered_region)
    if selected_space:
        session._refresh_plan_object_footprint_display(selected_space)
    if session.hovered_space and not session._is_selected_plan_target(
        "space", session.hovered_space
    ):
        session._refresh_plan_object_footprint_display(session.hovered_space)
    secondary_targets = session._get_secondary_selected_plan_targets()
    for target_kind, target_obj in secondary_targets:
        if target_kind in ("symbol", "region", "space"):
            session._refresh_plan_object_footprint_display(target_obj)
        elif target_kind == "opening":
            session._refresh_opening_footprint_display(target_obj)
            session._refresh_opening_host_footprint_displays(target_obj)
    if selected_opening:
        session._refresh_opening_footprint_display(selected_opening)
        session._refresh_opening_host_footprint_displays(selected_opening)
        session._queue_hard_refresh_selected_opening_visuals()
    if session.hovered_opening and not session._is_selected_plan_target(
        "opening", session.hovered_opening
    ):
        session._refresh_opening_footprint_display(session.hovered_opening)
        session._refresh_opening_host_footprint_displays(session.hovered_opening)
    if recompute_opening_hosts:
        session._queue_recompute_opening_hosts(selected_opening, session.hovered_opening)
    visual_args = [
        _PLAN_VISUAL_SELECTED_SYMBOL,
        _PLAN_VISUAL_HOVERED_SYMBOL,
        _PLAN_VISUAL_HOVERED_PROVIDER,
        _PLAN_VISUAL_HOVERED_OPENING,
        _PLAN_VISUAL_HOVERED_WALL,
        _PLAN_VISUAL_WALL_GRIPS,
        _PLAN_VISUAL_PROVIDER_OVERLAYS,
    ]
    if selected_region:
        visual_args.append(_PLAN_VISUAL_SELECTED_REGION)
    if session.hovered_region and not session._is_selected_plan_target(
        "region", session.hovered_region
    ):
        visual_args.append(_PLAN_VISUAL_HOVERED_REGION)
    if selected_space:
        visual_args.append(_PLAN_VISUAL_SELECTED_SPACE)
    if session.hovered_space and not session._is_selected_plan_target(
        "space", session.hovered_space
    ):
        visual_args.append(_PLAN_VISUAL_HOVERED_SPACE)
    if selected_opening:
        visual_args.append(_PLAN_VISUAL_SELECTED_OPENING)
    if selected_provider or session._get_provider_selected_objects():
        visual_args.append(_PLAN_VISUAL_SELECTED_PROVIDER)
    if secondary_targets:
        visual_args.append(_PLAN_VISUAL_SECONDARY_SELECTION)
    session._queue_plan_overlay_visual_refresh(*visual_args)


def slot_undo_document(session, doc):
    del doc
    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)


def slot_redo_document(session, doc):
    del doc
    session._invalidate_document_dependent_plan_visuals(recompute_opening_hosts=True)


def slot_recomputed_document(session, doc):
    del doc
    if session._are_document_visual_updates_deferred():
        session._defer_document_visual_refresh()
        return
    session._invalidate_document_dependent_plan_visuals()


def slot_deleted_document(session, doc):
    del doc
    if session._tearing_down:
        return
    session.begin_teardown()
    session.shutdown(close_dialog=False, teardown=True)
