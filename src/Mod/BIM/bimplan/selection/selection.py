# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection state helpers for BIM Plan Edit."""

from contextlib import contextmanager

from bimplan.runtime import tools as plan_runtime_tools
from . import activation as plan_selection_activation
from . import gui_sync as plan_selection_gui_sync
from . import state_refresh as plan_selection_state_refresh
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds
from . import targets as plan_targets
from .service_common import (
    _SessionAPI,
    _clear_gui_preselection,
    _get_gui_preselection_object,
    get_plan_target_object_from_state,
    get_plan_target_state_key,
    normalize_gui_object_selection as _normalize_gui_object_selection,
)
from .service_interaction import (
    PlanSelectionActivationService,
    PlanSelectionHoverService,
    PlanSelectionTargetService,
)
from .service_primary import (
    PlanSelectionRefreshService,
    PlanSelectionStateService,
    PlanSelectionSyncService,
)


def _make_set_hovered_target_function(kind):
    def _set_hovered_target(session, obj):
        return plan_target_dispatch.set_hovered_target(session, kind, obj)

    _set_hovered_target.__name__ = "set_hovered_{}".format(kind)
    _set_hovered_target.__qualname__ = _set_hovered_target.__name__
    return _set_hovered_target


def clear_hidden_provider_preselection(session):
    if session.lifecycle_state.tearing_down:
        return False
    preselected_obj = _get_gui_preselection_object(session)
    if preselected_obj is None:
        return False
    if not plan_selection_gui_sync.should_filter_hidden_provider_preselection_for_object(
        session, preselected_obj
    ):
        return False
    session.performance.plan_perf_count("provider_preselection_cleared_for_mode")
    return _clear_gui_preselection()


def resolve_selected_target_for_gui_object(
    session,
    selected,
    *,
    pending_target_ref=None,
    preserved_target_ref=None,
    pending_kind=None,
    pending_target=None,
    preserved_kind=None,
    preserved_target=None,
):
    return plan_selection_state_refresh.resolve_selected_target_for_gui_object(
        session,
        selected,
        pending_target_ref=pending_target_ref,
        preserved_target_ref=preserved_target_ref,
        pending_kind=pending_kind,
        pending_target=pending_target,
        preserved_kind=preserved_kind,
        preserved_target=preserved_target,
    )


def sanitize_plan_target_references(session):
    return plan_selection_state_refresh.sanitize_plan_target_references(session)


def refresh_selected_plan_target(session, *, force_wall_visual_resync=False):
    return plan_selection_state_refresh.refresh_selected_plan_target(
        session,
        force_wall_visual_resync=force_wall_visual_resync,
    )


def get_selected_target_for_kind(session, kind):
    return session.selection.state.get_selected_target_for_kind(kind)


def set_selected_target_for_kind(session, kind, obj):
    return session.selection.state.set_selected_target_for_kind(kind, obj)


def get_selected_plan_target_state(session, primary_kinds):
    selection_state = session.selection_state
    kind = selection_state.selected_plan_target_kind
    obj = selection_state.selected_plan_target_obj
    if kind not in primary_kinds or obj is None:
        return plan_target_kinds.make_plan_target_ref()
    return plan_target_kinds.make_plan_target_ref(kind, obj)


def set_selected_plan_target_state(session, primary_kinds, kind=None, obj=None):
    if kind not in primary_kinds or obj is None:
        kind = None
        obj = None
    selection_state = session.selection_state
    selection_state.selected_plan_target_kind = kind
    selection_state.selected_plan_target_obj = obj


def _get_native_selected_plan_target(session):
    return session.selection.state._get_native_selected_plan_target()


def _get_current_selected_plan_target(session):
    return session.selection.state.get_selected_plan_target()


def _get_current_secondary_selected_plan_targets(session):
    return session.selection.state.get_secondary_selected_plan_targets()


def get_selected_plan_target_object(session, kind=None):
    return session.selection.state.get_selected_plan_target_object(kind)


def is_selected_plan_target(session, kind, obj=None):
    return session.selection.state.is_selected_plan_target(kind, obj)


def clear_selected_plan_target_if_matches(session, kind, obj):
    return session.selection.state.clear_selected_plan_target_if_matches(kind, obj)


def discard_runtime_references(session):
    selection_state = session.selection_state
    session.selection.state.set_selected_plan_target_state()
    selection_state.secondary_selected_plan_targets_state = []
    session.hovered_wall = None
    session.hovered_opening = None
    session.hovered_symbol = None
    session.hovered_provider = None
    session.hovered_space = None
    session.hovered_region = None
    selection_state.pending_selected_plan_target = None


def is_valid_plan_target(session, kind, obj):
    return session.selection.state.is_valid_plan_target(kind, obj)


def set_pending_selected_plan_target(session, kind=None, obj=None):
    return session.selection.state.set_pending_selected_plan_target(kind, obj)


def consume_pending_selected_plan_target(session):
    return session.selection.state.consume_pending_selected_plan_target()


def get_selected_plan_target(session):
    return session.selection.state.get_selected_plan_target()


def get_first_plan_target_from_selection(session, selection):
    return session.selection.state.get_first_plan_target_from_selection(selection)


def _iter_normalized_plan_targets(session, targets):
    seen = set()
    for target in targets or []:
        target_ref = plan_target_kinds.coerce_plan_target_ref(target)
        if not is_valid_plan_target(session, target_ref.kind, target_ref.obj):
            continue
        key = get_plan_target_state_key(target_ref.kind, target_ref.obj)
        if key is None or key in seen:
            continue
        seen.add(key)
        yield plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)


def _filter_secondary_selected_plan_targets(targets, primary_kind, primary_obj):
    for target_ref in targets:
        if target_ref.kind == primary_kind and target_ref.obj == primary_obj:
            continue
        yield plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)


def normalize_plan_target_list(session, targets):
    return session.selection.state.normalize_plan_target_list(targets)


def normalize_plan_targets_from_selection(session, selection):
    return session.selection.state.normalize_plan_targets_from_selection(selection)


def set_secondary_selected_plan_targets(session, targets, primary_kind=None, primary_obj=None):
    return session.selection.state.set_secondary_selected_plan_targets(
        targets,
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )


def sync_secondary_selected_plan_targets_from_selection(
    session, selection, primary_kind=None, primary_obj=None
):
    return session.selection.state.sync_secondary_selected_plan_targets_from_selection(
        selection,
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )


def sync_secondary_selected_plan_targets_from_gui_selection(
    session, primary_kind=None, primary_obj=None
):
    return session.selection.state.sync_secondary_selected_plan_targets_from_gui_selection(
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )


def get_secondary_selected_plan_targets(session):
    return session.selection.state.get_secondary_selected_plan_targets()


def get_selected_plan_targets(session):
    return session.selection.state.get_selected_plan_targets()


def normalize_gui_object_selection(session, selection):
    del session
    return _normalize_gui_object_selection(selection)


def selected_plan_target_changed(session, previous_kind, previous_obj, kind=None):
    return session.selection.state.selected_plan_target_changed(
        previous_kind,
        previous_obj,
        kind,
    )


def set_selected_plan_target(
    session,
    kind=None,
    obj=None,
    pending_restore=False,
    preserve_hovered_symbol_overlay=False,
):
    return session.selection.state.set_selected_plan_target(
        kind,
        obj,
        pending_restore=pending_restore,
        preserve_hovered_symbol_overlay=preserve_hovered_symbol_overlay,
    )


def schedule_selected_wall_reset(session, reason, obj):
    return plan_selection_state_refresh.schedule_selected_wall_reset(session, reason, obj)


def reset_selected_wall_after_change(session):
    return plan_selection_state_refresh.reset_selected_wall_after_change(session)


def suspend_selected_wall_state(session, wall=None, clear_gui_selection=True):
    return plan_selection_state_refresh.suspend_selected_wall_state(
        session,
        wall=wall,
        clear_gui_selection=clear_gui_selection,
    )


def sync_primary_selected_plan_target_visuals(
    session,
    previous_kind=None,
    previous_obj=None,
    *,
    force_wall_visual_resync=False,
):
    return plan_selection_state_refresh.sync_primary_selected_plan_target_visuals(
        session,
        previous_kind=previous_kind,
        previous_obj=previous_obj,
        force_wall_visual_resync=force_wall_visual_resync,
    )


def refresh_primary_selected_plan_target(session, *, force_wall_visual_resync=False):
    return plan_selection_state_refresh.refresh_primary_selected_plan_target(
        session,
        force_wall_visual_resync=force_wall_visual_resync,
    )


def set_hovered_wall(session, wall):
    if is_selected_plan_target(session, "wall", wall):
        wall = None
    if session.hovered_wall == wall:
        return
    session.hovered_wall = wall
    session.overlays.walls.sync_junction_node_overlays()
    session.overlays.walls.sync_hovered_wall_overlay()
    session.overlays.walls.sync_hovered_wall_opening_context_overlay()
    if session.current_tool == plan_runtime_tools.PlanTool.JOIN:
        session.task_panels.refresh_task_panel_status(reason="full")


set_hovered_opening = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_OPENING)


set_hovered_symbol = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_SYMBOL)


set_hovered_provider = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_PROVIDER)


set_hovered_space = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_SPACE)


set_hovered_region = _make_set_hovered_target_function(plan_target_kinds.PLAN_TARGET_REGION)


def queue_restore_selected_plan_target(session, kind, obj):
    plan_target_dispatch.queue_restore_selected_target(session, kind, obj)


def select_plan_target_for_plan_edit(
    session,
    kind,
    obj,
    queue_restore=False,
    sync_gui_selection=False,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return plan_selection_activation.select_plan_target_for_plan_edit(
        session,
        kind,
        obj,
        queue_restore=queue_restore,
        sync_gui_selection=sync_gui_selection,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def select_opening_for_plan_edit(session, *args, **kwargs):
    return plan_selection_activation.select_opening_for_plan_edit(session, *args, **kwargs)


def select_symbol_for_plan_edit(session, *args, **kwargs):
    return plan_selection_activation.select_symbol_for_plan_edit(session, *args, **kwargs)


def select_region_for_plan_edit(session, *args, **kwargs):
    return plan_selection_activation.select_region_for_plan_edit(session, *args, **kwargs)


def select_space_for_plan_edit(session, *args, **kwargs):
    return plan_selection_activation.select_space_for_plan_edit(session, *args, **kwargs)


def select_wall_for_plan_edit(session, *args, **kwargs):
    return plan_selection_activation.select_wall_for_plan_edit(session, *args, **kwargs)


def _activate_configured_plan_target(
    session,
    kind,
    mouse_pos,
    event_callback=None,
    resolved_target=None,
    *,
    defer_gui_selection=None,
    defer_wall_grips=None,
):
    return plan_selection_activation._activate_configured_plan_target(
        session,
        kind,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def activate_plan_target_for_kind(
    session,
    kind,
    mouse_pos,
    event_callback=None,
    resolved_target=None,
    *,
    defer_gui_selection=None,
    defer_wall_grips=None,
):
    return plan_selection_activation.activate_plan_target_for_kind(
        session,
        kind,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def activate_plan_target(
    session,
    kind,
    mouse_pos,
    event_callback=None,
    sync_gui_selection=False,
    clear_hovered_kinds=None,
    resolved_target=None,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return plan_selection_activation.activate_plan_target(
        session,
        kind,
        mouse_pos,
        event_callback=event_callback,
        sync_gui_selection=sync_gui_selection,
        clear_hovered_kinds=clear_hovered_kinds,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def activate_semantic_plan_target(session, mouse_pos, event_callback=None):
    return plan_selection_activation.activate_semantic_plan_target(
        session,
        mouse_pos,
        event_callback=event_callback,
    )


def activate_opening_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return plan_selection_activation.activate_opening_target(
        session,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_symbol_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return plan_selection_activation.activate_symbol_target(
        session,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_region_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return plan_selection_activation.activate_region_target(
        session,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_space_target(session, mouse_pos, event_callback=None, resolved_target=None):
    return plan_selection_activation.activate_space_target(
        session,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
    )


def activate_wall_target(
    session,
    mouse_pos,
    event_callback=None,
    resolved_target=None,
    defer_gui_selection=False,
    defer_wall_grips=False,
):
    return plan_selection_activation.activate_wall_target(
        session,
        mouse_pos,
        event_callback=event_callback,
        resolved_target=resolved_target,
        defer_gui_selection=defer_gui_selection,
        defer_wall_grips=defer_wall_grips,
    )


def clear_plan_selection_state(session):
    return plan_selection_activation.clear_plan_selection_state(session)


def is_plan_additive_selection_active(session):
    return plan_selection_activation.is_plan_additive_selection_active(session)


def activate_provider_overlay_target_node(session, node, event_callback=None):
    return plan_selection_activation.activate_provider_overlay_target_node(
        session,
        node,
        event_callback=event_callback,
    )


def toggle_raw_plan_object_selection(session, obj, event_callback=None):
    return plan_selection_activation.toggle_raw_plan_object_selection(
        session,
        obj,
        event_callback=event_callback,
    )


def toggle_plan_target_selection_at_position(session, mouse_pos, event_callback=None):
    return plan_selection_activation.toggle_plan_target_selection_at_position(
        session,
        mouse_pos,
        event_callback=event_callback,
    )


def clear_selected_visuals(
    session,
    kinds=None,
    *,
    clear_handle_kinds=None,
    include_wall_grips=False,
    include_selected_wall_opening_context=False,
    include_secondary_selection=False,
):
    if include_wall_grips:
        session.overlays.walls.clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        kinds=kinds,
        clear_handle_kinds=clear_handle_kinds,
    )
    if include_selected_wall_opening_context:
        session.overlays.openings.clear_selected_wall_opening_context_overlay()
    if include_secondary_selection:
        session.overlays.spaces.clear_secondary_selected_overlays()


def _should_preserve_provider_selected_target(session, kind, obj, selected):
    if kind != "provider" or obj is None or selected != obj:
        return False
    if not is_valid_plan_target(session, kind, obj):
        return False
    return plan_selection_gui_sync.is_visible_provider_target_object(session, obj)


class PlanSelectionAPI(_SessionAPI):
    """Owned session surface for BIM Plan Edit selection behavior."""

    def __init__(self, session):
        super().__init__(session)
        self.state = PlanSelectionStateService(session)
        self.refresh = PlanSelectionRefreshService(session)
        self.sync = PlanSelectionSyncService(session)
        self.targets = PlanSelectionTargetService(session)
        self.hover = PlanSelectionHoverService(session)
        self.activation = PlanSelectionActivationService(session)

    def addSelection(self, doc, obj, sub, point):
        return self.sync.selection_observer_add(doc, obj, sub, point)

    def removeSelection(self, doc, obj, sub):
        return self.sync.selection_observer_remove(doc, obj, sub)

    def setSelection(self, doc):
        return self.sync.selection_observer_set(doc)

    def clearSelection(self, doc):
        return self.sync.selection_observer_clear(doc)

    def clear_selected_visuals(self, *args, **kwargs):
        return clear_selected_visuals(self.session, *args, **kwargs)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def setPreselection(self, doc, obj, sub):
        return self.sync.selection_observer_set_preselection(doc, obj, sub)

    def removePreselection(self, doc, obj, sub):
        return self.sync.selection_observer_remove_preselection(doc, obj, sub)

    @contextmanager
    def selection_changes_suppressed(self):
        with self.sync.selection_changes_suppressed():
            yield

    def get_selected_objects(self):
        return tuple(
            self.sync.normalize_gui_object_selection(
                tuple(self.sync.get_gui_selection())
                + tuple(self.session.provider_transient_state.provider_selected_objects)
            )
        )
