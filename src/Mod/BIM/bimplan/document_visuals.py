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
PLAN_VISUAL_HOVERED_WALL = "hovered_wall"
PLAN_VISUAL_HOVERED_OPENING = "hovered_opening"
PLAN_VISUAL_HOVERED_SYMBOL = "hovered_symbol"
PLAN_VISUAL_HOVERED_PROVIDER = "hovered_provider"
PLAN_VISUAL_HOVERED_SPACE = "hovered_space"
PLAN_VISUAL_HOVERED_REGION = "hovered_region"
PLAN_VISUAL_SELECTED_WALL = "selected_wall"
PLAN_VISUAL_SELECTED_PROVIDER = "selected_provider"
PLAN_VISUAL_SELECTED_OPENING = "selected_opening"
PLAN_VISUAL_SELECTED_SYMBOL = "selected_symbol"
PLAN_VISUAL_SELECTED_SPACE = "selected_space"
PLAN_VISUAL_SELECTED_REGION = "selected_region"
PLAN_VISUAL_SECONDARY_SELECTION = "secondary_selection"
PLAN_VISUAL_SPACE_REGION_PICK = "space_region_pick"
PLAN_VISUAL_WALL_GRIPS = "wall_grips"
PLAN_VISUAL_WALL_EDIT_PREVIEW = "wall_edit_preview"
PLAN_VISUAL_PROVIDER_OVERLAYS = "provider_overlays"
PLAN_VISUAL_VIEW_SCALE = "view_scale"
PLAN_VISUAL_ALL = "all"
_PLAN_VISUAL_HOVERED_WALL = PLAN_VISUAL_HOVERED_WALL
_PLAN_VISUAL_HOVERED_OPENING = PLAN_VISUAL_HOVERED_OPENING
_PLAN_VISUAL_HOVERED_SYMBOL = PLAN_VISUAL_HOVERED_SYMBOL
_PLAN_VISUAL_HOVERED_PROVIDER = PLAN_VISUAL_HOVERED_PROVIDER
_PLAN_VISUAL_HOVERED_SPACE = PLAN_VISUAL_HOVERED_SPACE
_PLAN_VISUAL_HOVERED_REGION = PLAN_VISUAL_HOVERED_REGION
_PLAN_VISUAL_SELECTED_WALL = PLAN_VISUAL_SELECTED_WALL
_PLAN_VISUAL_SELECTED_PROVIDER = PLAN_VISUAL_SELECTED_PROVIDER
_PLAN_VISUAL_SELECTED_OPENING = PLAN_VISUAL_SELECTED_OPENING
_PLAN_VISUAL_SELECTED_SYMBOL = PLAN_VISUAL_SELECTED_SYMBOL
_PLAN_VISUAL_SELECTED_SPACE = PLAN_VISUAL_SELECTED_SPACE
_PLAN_VISUAL_SELECTED_REGION = PLAN_VISUAL_SELECTED_REGION
_PLAN_VISUAL_SECONDARY_SELECTION = PLAN_VISUAL_SECONDARY_SELECTION
_PLAN_VISUAL_WALL_GRIPS = PLAN_VISUAL_WALL_GRIPS
_PLAN_VISUAL_PROVIDER_OVERLAYS = PLAN_VISUAL_PROVIDER_OVERLAYS
_FOOTPRINT_TARGET_KINDS = ("symbol", "region", "space")
_OPENING_TARGET_KIND = "opening"


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
    if session.lifecycle_state.tearing_down or not obj or not session.doc:
        return False
    try:
        if getattr(obj, "Document", None) != session.doc:
            return False
        if is_hidden_library_definition_object(obj):
            return False
        return session.visibility.is_supported_plan_object(obj)
    except ReferenceError:
        return False


def queue_created_plan_object(session, obj):
    if not obj or not getattr(obj, "Name", None):
        return
    session._pending_created_plan_objects[obj.Name] = obj
    if are_document_visual_updates_deferred(session):
        session._created_plan_objects_flush_deferred = True
        return
    if session._created_plan_objects_flush_queued:
        return
    session._created_plan_objects_flush_queued = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, lambda: flush_created_plan_objects(session))
    except Exception:
        flush_created_plan_objects(session)


def flush_created_plan_objects(session, force=False):
    session._created_plan_objects_flush_queued = False
    if are_document_visual_updates_deferred(session) and not force:
        session._created_plan_objects_flush_deferred = True
        return
    session._created_plan_objects_flush_deferred = False
    pending = list(session._pending_created_plan_objects.values())
    session._pending_created_plan_objects.clear()
    eligible = []
    for obj in pending:
        if not should_register_created_plan_object(session, obj):
            continue
        eligible.append(obj)
    session.visibility.register_plan_objects(eligible)


def are_document_visual_updates_deferred(session):
    return session._document_visual_update_defer_depth > 0


def defer_document_visual_refresh(session):
    session._document_visual_refresh_deferred = True


def document_is_alive(session):
    doc = session.doc
    if doc is None:
        return False
    try:
        _ = doc.Name
        return True
    except Exception:
        session.doc = None
        return False


def attach_document_observer(session):
    if session._document_observer_added:
        return
    try:
        import FreeCAD

        FreeCAD.addDocumentObserver(session)
        session._document_observer_added = True
    except Exception:
        pass


def detach_document_observer(session):
    if not session._document_observer_added:
        return
    try:
        import FreeCAD

        FreeCAD.removeDocumentObserver(session)
    except Exception:
        pass
    session._document_observer_added = False


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
        if session._document_visual_update_defer_depth or session.lifecycle_state.tearing_down:
            return
        if session._created_plan_objects_flush_deferred or session._pending_created_plan_objects:
            session._created_plan_objects_flush_deferred = False
            session._document_visual_update_defer_depth = 1
            try:
                flush_created_plan_objects(session, force=True)
            finally:
                session._document_visual_update_defer_depth = 0
        if session._document_visual_refresh_deferred:
            session._document_visual_refresh_deferred = False
            if not document_is_alive(session):
                return
            invalidate_document_dependent_plan_visuals(session)
            session.selection.refresh_primary_selected_plan_target()
            session.task_panels.refresh_task_panel_status(reason="selection")


def is_opening_visual_dependency(opening, obj):
    if not opening or not obj:
        return False
    if obj == opening:
        return True
    if obj == getattr(opening, "Base", None):
        return True
    return obj in (getattr(opening, "Hosts", None) or [])


def refresh_selected_opening_visuals(session):
    session.overlays.sync_selected_opening_overlay()
    session.overlays.sync_selected_opening_handles()
    session.overlays.sync_selected_wall_opening_context_overlay()
    session.viewport.request_view_redraw()


def is_symbol_visual_dependency(session, symbol, obj):
    if not session.visibility.is_plan_symbol_instance(symbol) or not obj:
        return False
    if obj == symbol:
        return True
    semantic_obj = session.visibility.get_plan_semantic_object(symbol)
    if obj == semantic_obj:
        return True
    if obj == getattr(semantic_obj, "Base", None):
        return True
    return obj in (getattr(semantic_obj, "PlanSymbols", None) or [])


def refresh_plan_object_footprint_display(session, obj, *, request_redraw=True):
    if not session.visibility.is_supported_plan_object(obj):
        return
    session.overlays.invalidate_plan_overlay_geometry_cache(obj)
    semantic_obj = session.visibility.get_plan_semantic_object(obj)
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
        refresh_proxy = _get_footprint_refresh_proxy(view_object)
        if refresh_proxy is None:
            continue
        try:
            _refresh_footprint_proxy(refresh_proxy, view_object)
            _update_view_object(view_object)
            refreshed = True
        except TypeError:
            try:
                _refresh_footprint_proxy(refresh_proxy, view_object, pass_view_object=True)
                _update_view_object(view_object)
                refreshed = True
            except Exception:
                continue
        except Exception:
            continue

    view_object = getattr(obj, "ViewObject", None)
    _update_view_object(view_object)
    if not refreshed:
        return
    if request_redraw:
        session.viewport.request_view_redraw()


def refresh_opening_footprint_display(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return
    refresh_plan_object_footprint_display(session, opening)


def refresh_wall_footprint_display(session, wall):
    if not wall:
        return
    refresh_plan_object_footprint_display(session, wall)


def _get_footprint_refresh_proxy(view_object):
    if not view_object:
        return None
    proxy = getattr(view_object, "Proxy", None)
    if proxy is None:
        return None
    if any(
        callable(getattr(proxy, method_name, None))
        for method_name in ("ensureFootprintGroup", "updateFootprint", "refreshFootprint")
    ):
        return proxy
    return None


def _refresh_footprint_proxy(proxy, view_object, *, pass_view_object=False):
    refresh_footprint = getattr(proxy, "refreshFootprint", None)
    if callable(refresh_footprint):
        if pass_view_object:
            refresh_footprint(view_object)
        else:
            refresh_footprint()
        return
    ensure_group = getattr(proxy, "ensureFootprintGroup", None)
    if callable(ensure_group):
        ensure_group(view_object)
    update_footprint = getattr(proxy, "updateFootprint", None)
    if callable(update_footprint):
        update_footprint()


def _update_view_object(view_object):
    if view_object is None:
        return
    update = getattr(view_object, "update", None)
    if not callable(update):
        return
    try:
        update()
    except Exception:
        pass


def refresh_opening_host_footprint_displays(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return
    for host in getattr(opening, "Hosts", None) or []:
        refresh_wall_footprint_display(session, host)


def queue_recompute_opening_hosts(session, *openings):
    if (
        session.lifecycle_state.tearing_down
        or session._opening_host_recompute_queued
        or session._opening_host_recompute_running
    ):
        return
    hosts = []
    for opening in openings:
        if not session.openings.is_hosted_opening_object(opening):
            continue
        hosts.extend(getattr(opening, "Hosts", None) or [])
    hosts = [host for host in dict.fromkeys(hosts) if host]
    if not hosts:
        return
    session._opening_host_recompute_queued = True
    flush_recompute_opening_hosts(session, hosts)


def flush_recompute_opening_hosts(session, hosts):
    session._opening_host_recompute_queued = False
    if (
        session.lifecycle_state.tearing_down
        or session._opening_host_recompute_running
        or not session.doc
    ):
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
    if session.lifecycle_state.tearing_down or session._selected_opening_hard_refresh_queued:
        return
    session._selected_opening_hard_refresh_queued = True
    session.overlays.clear_selected_opening_overlay()
    session.overlays.clear_selected_opening_handles()
    session.viewport.request_view_redraw()
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(
            0,
            lambda: flush_hard_refresh_selected_opening_visuals(session),
        )
    except Exception:
        flush_hard_refresh_selected_opening_visuals(session)


def flush_hard_refresh_selected_opening_visuals(session):
    session._selected_opening_hard_refresh_queued = False
    if session.lifecycle_state.tearing_down or session.current_tool != "Select":
        return
    opening = session.selection.get_selected_plan_target_object("opening")
    if not session.openings.is_hosted_opening_object(opening):
        return
    session.overlays.sync_selected_opening_overlay()
    session.overlays.sync_selected_opening_handles()
    session.viewport.request_view_redraw()


def slot_created_object(session, obj):
    if session.lifecycle_state.tearing_down:
        return
    session.providers.invalidate_plan_provider_document_cache()
    session._provider_overlay_state = None
    session.visibility.invalidate_plan_classification_cache()
    session.openings.invalidate_wall_hosted_openings_cache()
    queue_created_plan_object(session, obj)


def _refresh_region_or_space_visuals(session, obj, prop, selected_region, selected_space):
    if selected_region and obj == selected_region and prop in _REGION_VISUAL_PROPERTIES:
        refresh_plan_object_footprint_display(session, selected_region)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_REGION)
        session.task_panels.refresh_task_panel_status()
        return True
    if (
        session.hovered_region
        and not session.selection.is_selected_plan_target("region", session.hovered_region)
        and obj == session.hovered_region
        and prop in _REGION_VISUAL_PROPERTIES
    ):
        refresh_plan_object_footprint_display(session, session.hovered_region)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_REGION)
        return True
    if selected_space and obj == selected_space and prop in _SPACE_VISUAL_PROPERTIES:
        refresh_plan_object_footprint_display(session, selected_space)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SPACE)
        session.task_panels.refresh_task_panel_status()
        return True
    if (
        session.hovered_space
        and not session.selection.is_selected_plan_target("space", session.hovered_space)
        and obj == session.hovered_space
        and prop in _SPACE_VISUAL_PROPERTIES
    ):
        refresh_plan_object_footprint_display(session, session.hovered_space)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SPACE)
        return True
    return False


def _refresh_secondary_selection_visuals(session, obj, prop):
    secondary_overlay_refresh = False
    for target_ref in session.selection.get_secondary_selected_plan_targets():
        if (
            target_ref.kind == "region"
            and obj == target_ref.obj
            and prop in _REGION_VISUAL_PROPERTIES
        ):
            refresh_plan_object_footprint_display(session, target_ref.obj)
            secondary_overlay_refresh = True
        elif (
            target_ref.kind == "space"
            and obj == target_ref.obj
            and prop in _SPACE_VISUAL_PROPERTIES
        ):
            refresh_plan_object_footprint_display(session, target_ref.obj)
            secondary_overlay_refresh = True
        elif (
            target_ref.kind == "symbol"
            and is_symbol_visual_dependency(session, target_ref.obj, obj)
            and prop in _SYMBOL_VISUAL_PROPERTIES
        ):
            refresh_plan_object_footprint_display(session, target_ref.obj)
            secondary_overlay_refresh = True
        elif (
            target_ref.kind == "opening"
            and is_opening_visual_dependency(target_ref.obj, obj)
            and prop in _OPENING_VISUAL_PROPERTIES
        ):
            refresh_opening_footprint_display(session, target_ref.obj)
            refresh_opening_host_footprint_displays(session, target_ref.obj)
            secondary_overlay_refresh = True
        elif (
            target_ref.kind == "wall" and obj == target_ref.obj and prop in _WALL_VISUAL_PROPERTIES
        ):
            secondary_overlay_refresh = True
    if not secondary_overlay_refresh:
        return False
    session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SECONDARY_SELECTION)
    return True


def _refresh_symbol_or_opening_dependency_visuals(
    session, obj, prop, selected_opening, selected_symbol
):
    if (
        is_symbol_visual_dependency(session, selected_symbol, obj)
        and prop in _SYMBOL_VISUAL_PROPERTIES
    ):
        refresh_plan_object_footprint_display(session, selected_symbol)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_SELECTED_SYMBOL)
        return True
    if (
        is_symbol_visual_dependency(session, session.hovered_symbol, obj)
        and prop in _SYMBOL_VISUAL_PROPERTIES
    ):
        refresh_plan_object_footprint_display(session, session.hovered_symbol)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_SYMBOL)
        return True
    if is_opening_visual_dependency(selected_opening, obj) and prop in _OPENING_VISUAL_PROPERTIES:
        refresh_opening_footprint_display(session, selected_opening)
        refresh_opening_host_footprint_displays(session, selected_opening)
        session.overlays.queue_plan_overlay_visual_refresh(
            _PLAN_VISUAL_SELECTED_OPENING,
            _PLAN_VISUAL_HOVERED_OPENING,
        )
        return True
    if (
        is_opening_visual_dependency(session.hovered_opening, obj)
        and prop in _OPENING_VISUAL_PROPERTIES
    ):
        refresh_opening_footprint_display(session, session.hovered_opening)
        refresh_opening_host_footprint_displays(session, session.hovered_opening)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_OPENING)
        return True
    return False


def _refresh_wall_related_visuals(session, obj, prop, selected_wall):
    if (
        session.hovered_wall
        and obj in session.openings.get_wall_hosted_openings(session.hovered_wall)
        and prop in _OPENING_VISUAL_PROPERTIES
    ):
        refresh_opening_footprint_display(session, obj)
        refresh_opening_host_footprint_displays(session, obj)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
        return True
    if (
        selected_wall
        and obj in session.openings.get_wall_hosted_openings(selected_wall)
        and prop in _OPENING_VISUAL_PROPERTIES
    ):
        refresh_opening_footprint_display(session, obj)
        refresh_opening_host_footprint_displays(session, obj)
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_WALL_GRIPS)
        return True
    if obj == session.hovered_wall and prop in _WALL_VISUAL_PROPERTIES:
        session.overlays.queue_plan_overlay_visual_refresh(_PLAN_VISUAL_HOVERED_WALL)
        return True
    if obj != selected_wall or prop not in _WALL_VISUAL_PROPERTIES:
        return False
    session.openings.refresh_wall_hosted_opening_footprints(obj)
    session.selection.schedule_selected_wall_reset(prop, obj)
    return True


def slot_changed_object(session, obj, prop):
    if session.lifecycle_state.tearing_down:
        return
    session.providers.invalidate_plan_provider_document_cache()
    session._provider_overlay_state = None
    session.visibility.invalidate_plan_classification_cache()
    session.openings.invalidate_wall_hosted_openings_cache()
    if are_document_visual_updates_deferred(session):
        defer_document_visual_refresh(session)
        return
    if session.current_tool != "Select":
        return
    session.selection.sanitize_plan_target_references()
    selected_wall = session.selection.get_selected_plan_target_object("wall")
    selected_opening = session.selection.get_selected_plan_target_object("opening")
    selected_symbol = session.selection.get_selected_plan_target_object("symbol")
    selected_region = session.selection.get_selected_plan_target_object("region")
    selected_space = session.selection.get_selected_plan_target_object("space")
    if _refresh_region_or_space_visuals(session, obj, prop, selected_region, selected_space):
        return
    if _refresh_secondary_selection_visuals(session, obj, prop):
        return
    if _refresh_symbol_or_opening_dependency_visuals(
        session, obj, prop, selected_opening, selected_symbol
    ):
        return
    if _refresh_wall_related_visuals(session, obj, prop, selected_wall):
        return


def slot_deleted_object(session, obj):
    if session.lifecycle_state.tearing_down:
        return
    session.providers.invalidate_plan_provider_document_cache()
    session._provider_overlay_state = None
    session.visibility.invalidate_plan_classification_cache()
    session.openings.invalidate_wall_hosted_openings_cache()
    session.overlays.invalidate_plan_overlay_geometry_cache(obj)
    if are_document_visual_updates_deferred(session):
        defer_document_visual_refresh(session)
        return
    if obj == session.hovered_wall:
        session.hovered_wall = None
        session.overlays.clear_hovered_wall_overlay()
    if obj == session.hovered_opening:
        session.hovered_opening = None
        session.overlays.clear_hovered_opening_overlay()
    if obj == session.hovered_symbol:
        session.hovered_symbol = None
        session.overlays.clear_hovered_symbol_overlay()
    if obj == session.hovered_provider:
        session.hovered_provider = None
        session.overlays.clear_hovered_provider_overlay()
    if obj == session.hovered_space:
        session.hovered_space = None
        session.overlays.clear_hovered_space_overlay()
    if obj == session.hovered_region:
        session.hovered_region = None
        session.overlays.clear_hovered_region_overlay()
    if session.selection.clear_selected_plan_target_if_matches("opening", obj):
        refresh_selected_opening_visuals(session)
        return
    if session.selection.clear_selected_plan_target_if_matches("symbol", obj):
        session.overlays.refresh_selected_symbol_visuals()
        return
    if session.selection.clear_selected_plan_target_if_matches("region", obj):
        session.spaces.refresh_selected_region_visuals()
        session.task_panels.refresh_task_panel_status()
        return
    if session.selection.clear_selected_plan_target_if_matches("space", obj):
        session.spaces.refresh_selected_space_visuals()
        session.task_panels.refresh_task_panel_status()
        return
    if not session.selection.is_selected_plan_target("wall", obj):
        return
    session.selection.schedule_selected_wall_reset("Deleted", obj)


def invalidate_document_dependent_plan_visuals(session, recompute_opening_hosts=False):
    if (
        session.lifecycle_state.tearing_down
        or session.lifecycle_state.finishing
        or not document_is_alive(session)
    ):
        return
    session.providers.invalidate_plan_provider_document_cache()
    session.visibility.invalidate_plan_classification_cache()
    session.openings.invalidate_wall_hosted_openings_cache()
    session.overlays.invalidate_plan_overlay_geometry_cache()
    session.selection.sanitize_plan_target_references()
    selected_symbol = session.selection.get_selected_plan_target_object("symbol")
    selected_region = session.selection.get_selected_plan_target_object("region")
    selected_space = session.selection.get_selected_plan_target_object("space")
    selected_opening = session.selection.get_selected_plan_target_object("opening")
    selected_provider = session.selection.get_selected_plan_target_object("provider")
    if selected_symbol:
        refresh_plan_object_footprint_display(session, selected_symbol)
    if session.hovered_symbol and not session.selection.is_selected_plan_target(
        "symbol", session.hovered_symbol
    ):
        refresh_plan_object_footprint_display(session, session.hovered_symbol)
    if selected_region:
        refresh_plan_object_footprint_display(session, selected_region)
    if session.hovered_region and not session.selection.is_selected_plan_target(
        "region", session.hovered_region
    ):
        refresh_plan_object_footprint_display(session, session.hovered_region)
    if selected_space:
        refresh_plan_object_footprint_display(session, selected_space)
    if session.hovered_space and not session.selection.is_selected_plan_target(
        "space", session.hovered_space
    ):
        refresh_plan_object_footprint_display(session, session.hovered_space)
    secondary_targets = session.selection.get_secondary_selected_plan_targets()
    for target_kind, target_obj in secondary_targets:
        if target_kind in _FOOTPRINT_TARGET_KINDS:
            refresh_plan_object_footprint_display(session, target_obj)
        elif target_kind == _OPENING_TARGET_KIND:
            refresh_opening_footprint_display(session, target_obj)
            refresh_opening_host_footprint_displays(session, target_obj)
    if selected_opening:
        refresh_opening_footprint_display(session, selected_opening)
        refresh_opening_host_footprint_displays(session, selected_opening)
        queue_hard_refresh_selected_opening_visuals(session)
    if session.hovered_opening and not session.selection.is_selected_plan_target(
        "opening", session.hovered_opening
    ):
        refresh_opening_footprint_display(session, session.hovered_opening)
        refresh_opening_host_footprint_displays(session, session.hovered_opening)
    if recompute_opening_hosts:
        queue_recompute_opening_hosts(
            session,
            selected_opening,
            session.hovered_opening,
        )
    visual_args = [
        _PLAN_VISUAL_SELECTED_SYMBOL,
        _PLAN_VISUAL_HOVERED_SYMBOL,
        _PLAN_VISUAL_HOVERED_PROVIDER,
        _PLAN_VISUAL_HOVERED_OPENING,
        _PLAN_VISUAL_HOVERED_WALL,
        _PLAN_VISUAL_PROVIDER_OVERLAYS,
    ]
    if session.selection.is_selected_plan_target("wall"):
        visual_args.append(_PLAN_VISUAL_SELECTED_WALL)
        visual_args.append(_PLAN_VISUAL_WALL_GRIPS)
    if selected_region:
        visual_args.append(_PLAN_VISUAL_SELECTED_REGION)
    if session.hovered_region and not session.selection.is_selected_plan_target(
        "region", session.hovered_region
    ):
        visual_args.append(_PLAN_VISUAL_HOVERED_REGION)
    if selected_space:
        visual_args.append(_PLAN_VISUAL_SELECTED_SPACE)
    if session.hovered_space and not session.selection.is_selected_plan_target(
        "space", session.hovered_space
    ):
        visual_args.append(_PLAN_VISUAL_HOVERED_SPACE)
    if selected_opening:
        visual_args.append(_PLAN_VISUAL_SELECTED_OPENING)
    if selected_provider or session.status_text.get_provider_selected_objects():
        visual_args.append(_PLAN_VISUAL_SELECTED_PROVIDER)
    if secondary_targets:
        visual_args.append(_PLAN_VISUAL_SECONDARY_SELECTION)
    session.overlays.queue_plan_overlay_visual_refresh(*visual_args)


def slot_undo_document(session, doc):
    del doc
    invalidate_document_dependent_plan_visuals(session, recompute_opening_hosts=True)
    session.selection.sanitize_plan_target_references()
    session.selection.refresh_primary_selected_plan_target(force_wall_visual_resync=True)
    session.task_panels.refresh_task_panel_status(reason="selection")


def slot_redo_document(session, doc):
    del doc
    invalidate_document_dependent_plan_visuals(session, recompute_opening_hosts=True)
    session.selection.sanitize_plan_target_references()
    session.selection.refresh_primary_selected_plan_target(force_wall_visual_resync=True)
    session.task_panels.refresh_task_panel_status(reason="selection")


def slot_recomputed_document(session, doc):
    del doc
    if are_document_visual_updates_deferred(session):
        defer_document_visual_refresh(session)
        return
    invalidate_document_dependent_plan_visuals(session)


def slot_deleted_document(session, doc):
    del doc
    if session.lifecycle_state.tearing_down:
        return
    session.begin_teardown()
    session.shutdown(close_dialog=False, teardown=True)


class PlanDocumentVisualsAPI:
    """Owned session surface for Plan Edit document-driven visual refresh."""

    __slots__ = ("_session", "__dict__")

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def is_hidden_library_definition_object(self, *args, **kwargs):
        return is_hidden_library_definition_object(*args, **kwargs)

    def should_register_created_plan_object(self, *args, **kwargs):
        return should_register_created_plan_object(self.session, *args, **kwargs)

    def queue_created_plan_object(self, *args, **kwargs):
        return queue_created_plan_object(self.session, *args, **kwargs)

    def flush_created_plan_objects(self, *args, **kwargs):
        return flush_created_plan_objects(self.session, *args, **kwargs)

    def are_document_visual_updates_deferred(self, *args, **kwargs):
        return are_document_visual_updates_deferred(self.session, *args, **kwargs)

    def defer_document_visual_refresh(self, *args, **kwargs):
        return defer_document_visual_refresh(self.session, *args, **kwargs)

    def document_is_alive(self, *args, **kwargs):
        return document_is_alive(self.session, *args, **kwargs)

    def attach_document_observer(self, *args, **kwargs):
        return attach_document_observer(self.session, *args, **kwargs)

    def detach_document_observer(self, *args, **kwargs):
        return detach_document_observer(self.session, *args, **kwargs)

    def is_opening_visual_dependency(self, *args, **kwargs):
        return is_opening_visual_dependency(self.session, *args, **kwargs)

    def refresh_selected_opening_visuals(self, *args, **kwargs):
        return refresh_selected_opening_visuals(self.session, *args, **kwargs)

    def is_symbol_visual_dependency(self, *args, **kwargs):
        return is_symbol_visual_dependency(self.session, *args, **kwargs)

    def refresh_plan_object_footprint_display(self, *args, **kwargs):
        return refresh_plan_object_footprint_display(self.session, *args, **kwargs)

    def refresh_opening_footprint_display(self, *args, **kwargs):
        return refresh_opening_footprint_display(self.session, *args, **kwargs)

    def refresh_wall_footprint_display(self, *args, **kwargs):
        return refresh_wall_footprint_display(self.session, *args, **kwargs)

    def refresh_opening_host_footprint_displays(self, *args, **kwargs):
        return refresh_opening_host_footprint_displays(self.session, *args, **kwargs)

    def queue_recompute_opening_hosts(self, *args, **kwargs):
        return queue_recompute_opening_hosts(self.session, *args, **kwargs)

    def flush_recompute_opening_hosts(self, *args, **kwargs):
        return flush_recompute_opening_hosts(self.session, *args, **kwargs)

    def queue_hard_refresh_selected_opening_visuals(self, *args, **kwargs):
        return queue_hard_refresh_selected_opening_visuals(self.session, *args, **kwargs)

    def flush_hard_refresh_selected_opening_visuals(self, *args, **kwargs):
        return flush_hard_refresh_selected_opening_visuals(self.session, *args, **kwargs)

    def invalidate_document_dependent_plan_visuals(self, *args, **kwargs):
        return invalidate_document_dependent_plan_visuals(self.session, *args, **kwargs)

    def slot_created_object(self, *args, **kwargs):
        return slot_created_object(self.session, *args, **kwargs)

    def slot_changed_object(self, *args, **kwargs):
        return slot_changed_object(self.session, *args, **kwargs)

    def slot_deleted_object(self, *args, **kwargs):
        return slot_deleted_object(self.session, *args, **kwargs)

    def slot_undo_document(self, *args, **kwargs):
        return slot_undo_document(self.session, *args, **kwargs)

    def slot_redo_document(self, *args, **kwargs):
        return slot_redo_document(self.session, *args, **kwargs)

    def slot_recomputed_document(self, *args, **kwargs):
        return slot_recomputed_document(self.session, *args, **kwargs)

    def slot_deleted_document(self, *args, **kwargs):
        return slot_deleted_document(self.session, *args, **kwargs)
