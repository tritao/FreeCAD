# SPDX-License-Identifier: LGPL-2.1-or-later

"""Document-driven visual refresh helpers for BIM Plan Edit."""

from contextlib import contextmanager


def _provider_runtime_api(session):
    providers = getattr(session, "providers", None)
    return getattr(providers, "runtime", providers)


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


def _document_visual_state(session):
    return session.document_visual_state


def _provider_overlay_state(session):
    return session.provider_overlay_read_state


def has_direct_true_property(obj, prop_name):
    if not obj:
        return False
    try:
        if prop_name not in (getattr(obj, "PropertiesList", []) or []):
            return False
        return bool(getattr(obj, prop_name))
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
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
    visual_state = _document_visual_state(session)
    if not obj or not getattr(obj, "Name", None):
        return
    visual_state.pending_created_plan_objects[obj.Name] = obj
    if are_document_visual_updates_deferred(session):
        visual_state.created_plan_objects_flush_deferred = True
        return
    if visual_state.created_plan_objects_flush_queued:
        return
    visual_state.created_plan_objects_flush_queued = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, lambda: flush_created_plan_objects(session))
    except ImportError:
        flush_created_plan_objects(session)


def flush_created_plan_objects(session, force=False):
    visual_state = _document_visual_state(session)
    visual_state.created_plan_objects_flush_queued = False
    if are_document_visual_updates_deferred(session) and not force:
        visual_state.created_plan_objects_flush_deferred = True
        return
    visual_state.created_plan_objects_flush_deferred = False
    pending = list(visual_state.pending_created_plan_objects.values())
    visual_state.pending_created_plan_objects.clear()
    eligible = []
    for obj in pending:
        if not should_register_created_plan_object(session, obj):
            continue
        eligible.append(obj)
    session.visibility.register_plan_objects(eligible)


def are_document_visual_updates_deferred(session):
    return _document_visual_state(session).document_visual_update_defer_depth > 0


def defer_document_visual_refresh(session):
    _document_visual_state(session).document_visual_refresh_deferred = True


_DEFERRED_SELECTION_EFFECT_SUSPEND_SELECTED_WALL = "suspend_selected_wall"


def queue_deferred_selection_effect(session, effect_kind, obj=None):
    effect = (str(effect_kind or ""), obj)
    effects = _document_visual_state(session).deferred_selection_effects
    if effect not in effects:
        effects.append(effect)


def _take_deferred_selection_effects(session):
    visual_state = _document_visual_state(session)
    effects = list(visual_state.deferred_selection_effects)
    visual_state.deferred_selection_effects.clear()
    return effects


def _apply_deferred_selection_effects(session, effects):
    if not effects:
        return
    for effect_kind, obj in effects:
        if effect_kind == _DEFERRED_SELECTION_EFFECT_SUSPEND_SELECTED_WALL:
            if session.current_tool != "Select":
                continue
            session.selection.refresh.suspend_selected_wall_state(wall=obj)


def document_is_alive(session):
    doc = session.doc
    if doc is None:
        return False
    try:
        _ = doc.Name
        return True
    except (AttributeError, ReferenceError, RuntimeError):
        session.doc = None
        return False


def attach_document_observer(session):
    visual_state = _document_visual_state(session)
    if visual_state.document_observer_added:
        return
    try:
        import FreeCAD

        FreeCAD.addDocumentObserver(session)
        visual_state.document_observer_added = True
    except (ImportError, AttributeError, RuntimeError):
        pass


def detach_document_observer(session):
    visual_state = _document_visual_state(session)
    if not visual_state.document_observer_added:
        return
    try:
        import FreeCAD

        FreeCAD.removeDocumentObserver(session)
    except (ImportError, AttributeError, RuntimeError):
        pass
    visual_state.document_observer_added = False


@contextmanager
def defer_document_visual_updates(session):
    """Batch document observer visual work while an external command mutates the model."""

    visual_state = _document_visual_state(session)
    visual_state.document_visual_update_defer_depth += 1
    try:
        yield
    finally:
        visual_state.document_visual_update_defer_depth = max(
            0,
            visual_state.document_visual_update_defer_depth - 1,
        )
        if visual_state.document_visual_update_defer_depth or session.lifecycle_state.tearing_down:
            return
        if (
            visual_state.created_plan_objects_flush_deferred
            or visual_state.pending_created_plan_objects
        ):
            visual_state.created_plan_objects_flush_deferred = False
            visual_state.document_visual_update_defer_depth = 1
            try:
                flush_created_plan_objects(session, force=True)
            finally:
                visual_state.document_visual_update_defer_depth = 0
        if visual_state.document_visual_refresh_deferred or visual_state.deferred_selection_effects:
            effects = _take_deferred_selection_effects(session)
            visual_state.document_visual_refresh_deferred = False
            _apply_deferred_selection_effects(session, effects)
            if not document_is_alive(session):
                return
            invalidate_document_dependent_plan_visuals(session)
            session.selection.refresh.refresh_primary_selected_plan_target()
            session.task_panels.refresh_task_panel_status(reason="selection")


def refresh_plan_object_footprint_display(session, obj, *, request_redraw=True):
    if not session.visibility.is_supported_plan_object(obj):
        return
    session.overlays.geometry.invalidate_plan_overlay_geometry_cache(obj)
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
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                continue
        except (AttributeError, ReferenceError, RuntimeError):
            continue

    view_object = getattr(obj, "ViewObject", None)
    _update_view_object(view_object)
    if not refreshed:
        return
    if request_redraw:
        session.viewport.request_view_redraw()


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
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def _invalidate_document_visual_dependency_caches(session):
    _provider_runtime_api(session).invalidate_plan_provider_document_cache()
    _provider_overlay_state(session).render_state = None
    session.visibility.invalidate_plan_classification_cache()
    session.openings.invalidate_wall_hosted_openings_cache()


def slot_created_object(session, obj):
    if session.lifecycle_state.tearing_down:
        return
    _invalidate_document_visual_dependency_caches(session)
    queue_created_plan_object(session, obj)


def _refresh_wall_related_visuals(session, obj, prop, selected_wall):
    if session.openings.handle_wall_related_document_visual_change(obj, prop, selected_wall):
        return True
    return session.selection.refresh.handle_wall_document_visual_change(
        obj,
        prop,
        selected_wall,
    )


def _maybe_queue_deferred_selected_wall_suspension(session, obj, prop, selected_wall):
    if obj != selected_wall or prop not in _WALL_VISUAL_PROPERTIES:
        return False
    queue_deferred_selection_effect(
        session,
        _DEFERRED_SELECTION_EFFECT_SUSPEND_SELECTED_WALL,
        selected_wall,
    )
    return True


def slot_changed_object(session, obj, prop):
    if session.lifecycle_state.tearing_down:
        return
    _invalidate_document_visual_dependency_caches(session)
    selected_wall = session.selection.state.get_selected_plan_target_object("wall")
    if are_document_visual_updates_deferred(session):
        _maybe_queue_deferred_selected_wall_suspension(session, obj, prop, selected_wall)
        defer_document_visual_refresh(session)
        return
    if session.current_tool != "Select":
        return
    session.selection.refresh.sanitize_plan_target_references()
    if session.spaces.handle_document_visual_change(obj, prop):
        return
    if session.selection.refresh.handle_secondary_selection_document_visual_change(obj, prop):
        return
    if session.overlays.symbols.handle_document_visual_dependency_change(obj, prop):
        return
    if session.openings.handle_document_visual_dependency_change(obj, prop):
        return
    if _refresh_wall_related_visuals(session, obj, prop, selected_wall):
        return


def slot_deleted_object(session, obj):
    if session.lifecycle_state.tearing_down:
        return
    _invalidate_document_visual_dependency_caches(session)
    session.overlays.geometry.invalidate_plan_overlay_geometry_cache(obj)
    if are_document_visual_updates_deferred(session):
        if session.selection.state.is_selected_plan_target("wall", obj):
            queue_deferred_selection_effect(
                session,
                _DEFERRED_SELECTION_EFFECT_SUSPEND_SELECTED_WALL,
                obj,
            )
        defer_document_visual_refresh(session)
        return
    if obj == session.hovered_wall:
        session.hovered_wall = None
        session.overlays.walls.clear_hovered_wall_overlay()
    if obj == session.hovered_provider:
        session.hovered_provider = None
        session.overlays.providers.clear_hovered_provider_overlay()
    if session.openings.handle_deleted_visual_target(obj):
        return
    if session.overlays.symbols.handle_deleted_visual_target(obj):
        return
    if session.spaces.handle_deleted_visual_target(obj):
        return
    if not session.selection.state.is_selected_plan_target("wall", obj):
        return
    session.selection.refresh.schedule_selected_wall_reset("Deleted", obj)


def invalidate_document_dependent_plan_visuals(session, recompute_opening_hosts=False):
    if (
        session.lifecycle_state.tearing_down
        or session.lifecycle_state.finishing
        or not document_is_alive(session)
    ):
        return
    _provider_runtime_api(session).invalidate_plan_provider_document_cache()
    session.visibility.invalidate_plan_classification_cache()
    session.openings.invalidate_wall_hosted_openings_cache()
    session.overlays.geometry.invalidate_plan_overlay_geometry_cache()
    session.selection.refresh.sanitize_plan_target_references()
    selected_provider = session.selection.state.get_selected_plan_target_object("provider")
    secondary_targets = session.selection.state.get_secondary_selected_plan_targets()
    symbol_visuals = list(session.overlays.symbols.refresh_document_dependent_visuals())
    space_visuals = list(session.spaces.refresh_document_dependent_visuals())
    session.selection.refresh.refresh_document_dependent_secondary_selection_visuals()
    opening_visuals = list(
        session.openings.refresh_document_dependent_visuals(recompute_hosts=recompute_opening_hosts)
    )
    visual_args = [
        _PLAN_VISUAL_HOVERED_PROVIDER,
        _PLAN_VISUAL_HOVERED_WALL,
        _PLAN_VISUAL_PROVIDER_OVERLAYS,
    ]
    visual_args.extend(symbol_visuals)
    visual_args.extend(space_visuals)
    visual_args.extend(opening_visuals)
    if session.selection.state.is_selected_plan_target("wall"):
        visual_args.append(_PLAN_VISUAL_SELECTED_WALL)
        visual_args.append(_PLAN_VISUAL_WALL_GRIPS)
    if selected_provider or session.status_text.get_provider_selected_objects():
        visual_args.append(_PLAN_VISUAL_SELECTED_PROVIDER)
    if secondary_targets:
        visual_args.append(_PLAN_VISUAL_SECONDARY_SELECTION)
    session.overlays.queue_plan_overlay_visual_refresh(*visual_args)


def slot_undo_document(session, doc):
    del doc
    invalidate_document_dependent_plan_visuals(session, recompute_opening_hosts=True)
    session.selection.refresh.sanitize_plan_target_references()
    session.selection.refresh.refresh_primary_selected_plan_target(force_wall_visual_resync=True)
    session.task_panels.refresh_task_panel_status(reason="selection")


def slot_redo_document(session, doc):
    del doc
    invalidate_document_dependent_plan_visuals(session, recompute_opening_hosts=True)
    session.selection.refresh.sanitize_plan_target_references()
    session.selection.refresh.refresh_primary_selected_plan_target(force_wall_visual_resync=True)
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

    is_hidden_library_definition_object = staticmethod(is_hidden_library_definition_object)

    def should_register_created_plan_object(self, obj):
        return should_register_created_plan_object(self.session, obj)

    def queue_created_plan_object(self, obj):
        return queue_created_plan_object(self.session, obj)

    def flush_created_plan_objects(self, force=False):
        return flush_created_plan_objects(self.session, force=force)

    def are_document_visual_updates_deferred(self):
        return are_document_visual_updates_deferred(self.session)

    def defer_document_visual_refresh(self):
        return defer_document_visual_refresh(self.session)

    def defer_document_visual_updates(self):
        return defer_document_visual_updates(self.session)

    def document_is_alive(self):
        return document_is_alive(self.session)

    def attach_document_observer(self):
        return attach_document_observer(self.session)

    def detach_document_observer(self):
        return detach_document_observer(self.session)

    def refresh_plan_object_footprint_display(self, obj, *, request_redraw=True):
        return refresh_plan_object_footprint_display(
            self.session,
            obj,
            request_redraw=request_redraw,
        )

    def invalidate_document_dependent_plan_visuals(self, recompute_opening_hosts=False):
        return invalidate_document_dependent_plan_visuals(
            self.session,
            recompute_opening_hosts=recompute_opening_hosts,
        )

    def slot_created_object(self, obj):
        return slot_created_object(self.session, obj)

    def slot_changed_object(self, obj, prop):
        return slot_changed_object(self.session, obj, prop)

    def slot_deleted_object(self, obj):
        return slot_deleted_object(self.session, obj)

    def slot_undo_document(self, doc):
        return slot_undo_document(self.session, doc)

    def slot_redo_document(self, doc):
        return slot_redo_document(self.session, doc)

    def slot_recomputed_document(self, doc):
        return slot_recomputed_document(self.session, doc)

    def slot_deleted_document(self, doc):
        return slot_deleted_document(self.session, doc)
