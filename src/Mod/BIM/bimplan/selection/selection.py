# SPDX-License-Identifier: LGPL-2.1-or-later

"""Selection state helpers for BIM Plan Edit."""

from contextlib import contextmanager

from bimplan.runtime import tools as plan_runtime_tools
from . import activation as plan_selection_activation
from . import gui_sync as plan_selection_gui_sync
from . import picking as plan_selection_picking
from . import state_refresh as plan_selection_state_refresh
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds
from . import targets as plan_targets

SelectionRefreshResult = plan_selection_state_refresh.SelectionRefreshResult
GuiSelectionResolutionState = plan_selection_state_refresh.GuiSelectionResolutionState


def _make_set_hovered_target_function(kind):
    def _set_hovered_target(session, obj):
        return plan_target_dispatch.set_hovered_target(session, kind, obj)

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


def _get_gui_preselection_object(session):
    try:
        import bimplan.selection as plan_selection_pkg
    except Exception:
        plan_selection_pkg = None
    exported = (
        getattr(plan_selection_pkg, "_get_gui_preselection_object", None)
        if plan_selection_pkg is not None
        else None
    )
    if callable(exported) and exported is not _get_gui_preselection_object:
        return exported(session)
    return plan_selection_gui_sync.get_gui_preselection_object(session)


def _clear_gui_preselection():
    return plan_selection_gui_sync.clear_gui_preselection()


def sanitize_plan_target_references(session):
    return plan_selection_state_refresh.sanitize_plan_target_references(session)


def refresh_selected_plan_target(session, *, force_wall_visual_resync=False):
    return plan_selection_state_refresh.refresh_selected_plan_target(
        session,
        force_wall_visual_resync=force_wall_visual_resync,
    )


def get_selected_target_for_kind(session, kind):
    if getattr(session, "_selected_plan_target_kind", None) == kind:
        return getattr(session, "_selected_plan_target_obj", None)
    return None


def set_selected_target_for_kind(session, kind, obj):
    if obj is None:
        if getattr(session, "_selected_plan_target_kind", None) == kind:
            session._selected_plan_target_kind = None
            session._selected_plan_target_obj = None
        return
    session._selected_plan_target_kind = kind
    session._selected_plan_target_obj = obj


def get_selected_plan_target_state(session, primary_kinds):
    kind = getattr(session, "_selected_plan_target_kind", None)
    obj = getattr(session, "_selected_plan_target_obj", None)
    if kind not in primary_kinds or obj is None:
        return plan_target_kinds.make_plan_target_ref()
    return plan_target_kinds.make_plan_target_ref(kind, obj)


def set_selected_plan_target_state(session, primary_kinds, kind=None, obj=None):
    if kind not in primary_kinds or obj is None:
        kind = None
        obj = None
    session._selected_plan_target_kind = kind
    session._selected_plan_target_obj = obj


def _get_native_selected_plan_target(session):
    sanitize_plan_target_references(session)
    kind, obj = get_selected_plan_target_state(session, plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS)
    if is_valid_plan_target(session, kind, obj):
        return plan_target_kinds.make_plan_target_ref(kind, obj)
    if kind is not None or obj is not None:
        set_selected_plan_target_state(session, plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS)
    return plan_target_kinds.make_plan_target_ref()


def _get_current_selected_plan_target(session):
    return _get_native_selected_plan_target(session)


def _get_current_secondary_selected_plan_targets(session):
    primary_target_ref = _get_native_selected_plan_target(session)
    set_secondary_selected_plan_targets(
        session,
        getattr(session, "_secondary_selected_plan_targets_state", []),
        primary_kind=primary_target_ref.kind,
        primary_obj=primary_target_ref.obj,
    )
    return list(getattr(session, "_secondary_selected_plan_targets_state", []))


def get_selected_plan_target_object(session, kind=None):
    selected_target_ref = _get_native_selected_plan_target(session)
    if kind is not None and selected_target_ref.kind != kind:
        return None
    return selected_target_ref.obj


def is_selected_plan_target(session, kind, obj=None):
    selection_api = getattr(session, "selection", None)
    predicate = getattr(selection_api, "is_selected_plan_target", None)
    if callable(predicate) and not isinstance(selection_api, PlanSelectionAPI):
        return bool(predicate(kind, obj))
    selected_target_ref = get_selected_plan_target(session)
    if selected_target_ref.kind != kind:
        return False
    if obj is None:
        return selected_target_ref.obj is not None
    return selected_target_ref.obj == obj


def clear_selected_plan_target_if_matches(session, kind, obj):
    if not is_selected_plan_target(session, kind, obj):
        return False
    set_selected_plan_target_state(session, plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS)
    return True


def is_valid_plan_target(session, kind, obj):
    validate = getattr(session, "_is_valid_plan_target", None)
    if callable(validate):
        return bool(validate(kind, obj))
    return plan_target_dispatch.validate_plan_target(session, kind, obj)


def set_pending_selected_plan_target(session, kind=None, obj=None):
    if obj is None and kind is not None:
        target_ref = plan_target_kinds.coerce_plan_target_ref(kind)
        kind = target_ref.kind
        obj = target_ref.obj
    if is_valid_plan_target(session, kind, obj):
        session._pending_selected_plan_target = plan_target_kinds.make_plan_target_ref(kind, obj)
        return
    session._pending_selected_plan_target = None


def consume_pending_selected_plan_target(session):
    pending_target = plan_target_kinds.coerce_plan_target_ref(session._pending_selected_plan_target)
    session._pending_selected_plan_target = None
    if is_valid_plan_target(session, pending_target.kind, pending_target.obj):
        return pending_target
    return plan_target_kinds.make_plan_target_ref()


def get_selected_plan_target(session):
    selection_api = getattr(session, "selection", None)
    getter = getattr(selection_api, "get_selected_plan_target", None)
    if callable(getter) and not isinstance(selection_api, PlanSelectionAPI):
        return plan_target_kinds.coerce_plan_target_ref(getter())
    return _get_current_selected_plan_target(session)


def get_first_plan_target_from_selection(session, selection):
    for selected in selection or []:
        target_ref = plan_targets.get_plan_target_for_object(session, selected)
        if target_ref.kind and target_ref.obj:
            return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)
    return plan_target_kinds.make_plan_target_ref()


def get_plan_target_state_key(kind, obj):
    if not kind or not obj:
        return None
    return (
        kind,
        getattr(getattr(obj, "Document", None), "Name", None),
        getattr(obj, "Name", None),
    )


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
    return list(_iter_normalized_plan_targets(session, targets))


def normalize_plan_targets_from_selection(session, selection):
    return normalize_plan_target_list(
        session,
        [
            target_ref
            for target_ref in (
                plan_targets.get_plan_target_for_object(session, selected)
                for selected in (selection or [])
            )
            if target_ref.kind and target_ref.obj
        ],
    )


def set_secondary_selected_plan_targets(session, targets, primary_kind=None, primary_obj=None):
    if primary_kind is None and primary_obj is None:
        primary_target_ref = get_selected_plan_target(session)
        primary_kind = primary_target_ref.kind
        primary_obj = primary_target_ref.obj
    session._secondary_selected_plan_targets_state = list(
        _filter_secondary_selected_plan_targets(
            _iter_normalized_plan_targets(session, targets),
            primary_kind,
            primary_obj,
        )
    )


def sync_secondary_selected_plan_targets_from_selection(
    session, selection, primary_kind=None, primary_obj=None
):
    set_secondary_selected_plan_targets(
        session,
        normalize_plan_targets_from_selection(session, selection),
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )


def sync_secondary_selected_plan_targets_from_gui_selection(
    session, primary_kind=None, primary_obj=None
):
    sync_secondary_selected_plan_targets_from_selection(
        session,
        plan_selection_gui_sync.get_gui_selection(),
        primary_kind=primary_kind,
        primary_obj=primary_obj,
    )


def get_secondary_selected_plan_targets(session):
    return _get_current_secondary_selected_plan_targets(session)


def get_selected_plan_targets(session):
    selection_api = getattr(session, "selection", None)
    getter = getattr(selection_api, "get_selected_plan_targets", None)
    if callable(getter) and not isinstance(selection_api, PlanSelectionAPI):
        return tuple(
            plan_target_kinds.coerce_plan_target_ref(target) for target in (getter() or ())
        )
    primary_target_ref = _get_native_selected_plan_target(session)
    targets = []
    if primary_target_ref.kind and primary_target_ref.obj:
        targets.append(
            plan_target_kinds.make_plan_target_ref(primary_target_ref.kind, primary_target_ref.obj)
        )
    targets.extend(
        _filter_secondary_selected_plan_targets(
            _iter_normalized_plan_targets(
                session,
                _get_current_secondary_selected_plan_targets(session),
            ),
            primary_target_ref.kind,
            primary_target_ref.obj,
        )
    )
    return targets


def normalize_gui_object_selection(session, selection):
    del session
    normalized_selection = []
    seen = set()
    for selected in selection or ():
        if not selected:
            continue
        key = (
            getattr(getattr(selected, "Document", None), "Name", None),
            getattr(selected, "Name", None),
        )
        if key in seen:
            continue
        seen.add(key)
        normalized_selection.append(selected)
    return normalized_selection


def get_plan_target_object_from_state(state_kind, state_obj, kind):
    if state_kind == kind:
        return state_obj
    return None


def selected_plan_target_changed(session, previous_kind, previous_obj, kind=None):
    current_kind, current_obj = get_selected_plan_target(session)
    if kind is None:
        return previous_kind != current_kind or previous_obj != current_obj
    previous_target = get_plan_target_object_from_state(
        previous_kind,
        previous_obj,
        kind,
    )
    current_target = get_plan_target_object_from_state(
        current_kind,
        current_obj,
        kind,
    )
    return previous_target != current_target


def set_selected_plan_target(
    session,
    kind=None,
    obj=None,
    pending_restore=False,
    preserve_hovered_symbol_overlay=False,
):
    if is_valid_plan_target(session, kind, obj):
        set_selected_plan_target_state(
            session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
            kind,
            obj,
        )
    else:
        set_selected_plan_target_state(session, plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS)
        kind = None
        obj = None
    sync_secondary_selected_plan_targets_from_gui_selection(
        session,
        primary_kind=kind,
        primary_obj=obj,
    )
    session.wall_relations.clear_plan_relation_status()
    session.viewport.sync_active_plan_target_object()
    if pending_restore:
        set_pending_selected_plan_target(session, kind, obj)
    else:
        set_pending_selected_plan_target(session)
    if not session.lifecycle_state.tearing_down:
        session.overlays.sync_junction_node_overlays()
        session.overlays.sync_selected_wall_opening_context_overlay()
        session.overlays.sync_hovered_wall_opening_context_overlay()
        plan_target_dispatch.sync_hovered_target_visuals(
            session,
            kinds=(plan_target_kinds.PLAN_TARGET_OPENING,),
        )
        if not preserve_hovered_symbol_overlay:
            plan_target_dispatch.sync_hovered_target_visuals(
                session,
                kinds=(plan_target_kinds.PLAN_TARGET_SYMBOL,),
            )
        plan_target_dispatch.sync_hovered_target_visuals(
            session,
            kinds=(
                plan_target_kinds.PLAN_TARGET_SPACE,
                plan_target_kinds.PLAN_TARGET_REGION,
            ),
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
    session.overlays.sync_junction_node_overlays()
    session.overlays.sync_hovered_wall_overlay()
    session.overlays.sync_hovered_wall_opening_context_overlay()
    if session.current_tool == plan_runtime_tools.PlanTool.JOIN:
        session.task_panels.refresh_task_panel_status(
            selection_only=session.current_tool == plan_runtime_tools.PlanTool.SELECT
            and is_selected_plan_target(session, "wall")
        )


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


def _should_preserve_provider_selected_target(session, kind, obj, selected):
    if kind != "provider" or obj is None or selected != obj:
        return False
    if not is_valid_plan_target(session, kind, obj):
        return False
    return plan_selection_gui_sync.is_visible_provider_target_object(session, obj)


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class PlanSelectionAPI(_SessionAPI):
    """Owned session surface for Plan Edit selection behavior."""

    __slots__ = ("__dict__",)

    get_plan_target_object_from_state = staticmethod(get_plan_target_object_from_state)
    get_plan_target_state_key = staticmethod(get_plan_target_state_key)

    def get_selected_plan_target_state(self):
        return get_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
        )

    def set_selected_plan_target_state(self, kind=None, obj=None):
        return set_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
            kind=kind,
            obj=obj,
        )

    def sanitize_plan_target_references(self, *args, **kwargs):
        return sanitize_plan_target_references(self.session, *args, **kwargs)

    def get_selected_target_for_kind(self, *args, **kwargs):
        return get_selected_target_for_kind(self.session, *args, **kwargs)

    def set_selected_target_for_kind(self, *args, **kwargs):
        return set_selected_target_for_kind(self.session, *args, **kwargs)

    def get_selected_plan_target_object(self, *args, **kwargs):
        return get_selected_plan_target_object(self.session, *args, **kwargs)

    def is_selected_plan_target(self, *args, **kwargs):
        return is_selected_plan_target(self.session, *args, **kwargs)

    def clear_selected_plan_target_if_matches(self, *args, **kwargs):
        return clear_selected_plan_target_if_matches(self.session, *args, **kwargs)

    def clear_hidden_provider_preselection(self, *args, **kwargs):
        return clear_hidden_provider_preselection(self.session, *args, **kwargs)

    def selected_plan_target_changed(self, *args, **kwargs):
        return selected_plan_target_changed(self.session, *args, **kwargs)

    def set_pending_selected_plan_target(self, *args, **kwargs):
        return set_pending_selected_plan_target(self.session, *args, **kwargs)

    def consume_pending_selected_plan_target(self, *args, **kwargs):
        return consume_pending_selected_plan_target(self.session, *args, **kwargs)

    def get_selected_plan_target(self, *args, **kwargs):
        return get_selected_plan_target(self.session, *args, **kwargs)

    def get_first_plan_target_from_selection(self, *args, **kwargs):
        return get_first_plan_target_from_selection(self.session, *args, **kwargs)

    def is_valid_plan_target(self, *args, **kwargs):
        return is_valid_plan_target(self.session, *args, **kwargs)

    def normalize_plan_target_list(self, *args, **kwargs):
        return normalize_plan_target_list(self.session, *args, **kwargs)

    def normalize_plan_targets_from_selection(self, *args, **kwargs):
        return normalize_plan_targets_from_selection(self.session, *args, **kwargs)

    def set_secondary_selected_plan_targets(self, *args, **kwargs):
        return set_secondary_selected_plan_targets(self.session, *args, **kwargs)

    def sync_secondary_selected_plan_targets_from_selection(self, *args, **kwargs):
        return sync_secondary_selected_plan_targets_from_selection(self.session, *args, **kwargs)

    def sync_secondary_selected_plan_targets_from_gui_selection(self, *args, **kwargs):
        return sync_secondary_selected_plan_targets_from_gui_selection(
            self.session, *args, **kwargs
        )

    def get_secondary_selected_plan_targets(self, *args, **kwargs):
        return get_secondary_selected_plan_targets(self.session, *args, **kwargs)

    def get_selected_plan_targets(self, *args, **kwargs):
        return get_selected_plan_targets(self.session, *args, **kwargs)

    def set_selected_plan_target(self, *args, **kwargs):
        return set_selected_plan_target(self.session, *args, **kwargs)

    def schedule_selected_wall_reset(self, *args, **kwargs):
        return schedule_selected_wall_reset(self.session, *args, **kwargs)

    def reset_selected_wall_after_change(self, *args, **kwargs):
        return reset_selected_wall_after_change(self.session, *args, **kwargs)

    def suspend_selected_wall_state(self, *args, **kwargs):
        return suspend_selected_wall_state(self.session, *args, **kwargs)

    def sync_primary_selected_plan_target_visuals(self, *args, **kwargs):
        return sync_primary_selected_plan_target_visuals(self.session, *args, **kwargs)

    def refresh_selected_plan_target(self, *args, **kwargs):
        return refresh_selected_plan_target(self.session, *args, **kwargs)

    def refresh_primary_selected_plan_target(self, *args, **kwargs):
        return refresh_primary_selected_plan_target(self.session, *args, **kwargs)

    def set_hovered_wall(self, *args, **kwargs):
        return set_hovered_wall(self.session, *args, **kwargs)

    def set_hovered_opening(self, *args, **kwargs):
        return set_hovered_opening(self.session, *args, **kwargs)

    def set_hovered_symbol(self, *args, **kwargs):
        return set_hovered_symbol(self.session, *args, **kwargs)

    def set_hovered_provider(self, *args, **kwargs):
        return set_hovered_provider(self.session, *args, **kwargs)

    def set_hovered_space(self, *args, **kwargs):
        return set_hovered_space(self.session, *args, **kwargs)

    def set_hovered_region(self, *args, **kwargs):
        return set_hovered_region(self.session, *args, **kwargs)

    def queue_restore_selected_plan_target(self, *args, **kwargs):
        return queue_restore_selected_plan_target(self.session, *args, **kwargs)

    def select_plan_target_for_plan_edit(self, *args, **kwargs):
        return select_plan_target_for_plan_edit(self.session, *args, **kwargs)

    def select_opening_for_plan_edit(self, *args, **kwargs):
        return select_opening_for_plan_edit(self.session, *args, **kwargs)

    def select_symbol_for_plan_edit(self, *args, **kwargs):
        return select_symbol_for_plan_edit(self.session, *args, **kwargs)

    def select_region_for_plan_edit(self, *args, **kwargs):
        return select_region_for_plan_edit(self.session, *args, **kwargs)

    def select_space_for_plan_edit(self, *args, **kwargs):
        return select_space_for_plan_edit(self.session, *args, **kwargs)

    def select_wall_for_plan_edit(self, *args, **kwargs):
        return select_wall_for_plan_edit(self.session, *args, **kwargs)

    def activate_plan_target_for_kind(self, *args, **kwargs):
        return activate_plan_target_for_kind(self.session, *args, **kwargs)

    def activate_plan_target(self, *args, **kwargs):
        return activate_plan_target(self.session, *args, **kwargs)

    def activate_semantic_plan_target(self, *args, **kwargs):
        return activate_semantic_plan_target(self.session, *args, **kwargs)

    def activate_opening_target(self, *args, **kwargs):
        return activate_opening_target(self.session, *args, **kwargs)

    def activate_symbol_target(self, *args, **kwargs):
        return activate_symbol_target(self.session, *args, **kwargs)

    def activate_region_target(self, *args, **kwargs):
        return activate_region_target(self.session, *args, **kwargs)

    def activate_space_target(self, *args, **kwargs):
        return activate_space_target(self.session, *args, **kwargs)

    def activate_wall_target(self, *args, **kwargs):
        return activate_wall_target(self.session, *args, **kwargs)

    def clear_plan_selection_state(self, *args, **kwargs):
        return clear_plan_selection_state(self.session, *args, **kwargs)

    def normalize_gui_object_selection(self, *args, **kwargs):
        return normalize_gui_object_selection(self.session, *args, **kwargs)

    def activate_provider_overlay_target_node(self, *args, **kwargs):
        return activate_provider_overlay_target_node(self.session, *args, **kwargs)

    def toggle_raw_plan_object_selection(self, *args, **kwargs):
        return toggle_raw_plan_object_selection(self.session, *args, **kwargs)

    def toggle_plan_target_selection_at_position(self, *args, **kwargs):
        return toggle_plan_target_selection_at_position(self.session, *args, **kwargs)

    def attach_selection_observer(self, *args, **kwargs):
        return plan_selection_gui_sync.attach_selection_observer(self.session, *args, **kwargs)

    def detach_selection_observer(self, *args, **kwargs):
        return plan_selection_gui_sync.detach_selection_observer(self.session, *args, **kwargs)

    def schedule_selection_refresh(self, *args, **kwargs):
        return plan_selection_gui_sync.schedule_selection_refresh(self.session, *args, **kwargs)

    def run_scheduled_selection_refresh(self, *args, **kwargs):
        return plan_selection_gui_sync.run_scheduled_selection_refresh(
            self.session, *args, **kwargs
        )

    def schedule_clear_plan_selection_state(self, *args, **kwargs):
        return plan_selection_gui_sync.schedule_clear_plan_selection_state(
            self.session, *args, **kwargs
        )

    def run_scheduled_clear_plan_selection_state(self, *args, **kwargs):
        return plan_selection_gui_sync.run_scheduled_clear_plan_selection_state(
            self.session, *args, **kwargs
        )

    def set_gui_selection(self, *args, **kwargs):
        return plan_selection_gui_sync.set_gui_selection(self.session, *args, **kwargs)

    def set_gui_selection_object(self, *args, **kwargs):
        return plan_selection_gui_sync.set_gui_selection_object(self.session, *args, **kwargs)

    def schedule_gui_selection_object(self, *args, **kwargs):
        return plan_selection_gui_sync.schedule_gui_selection_object(self.session, *args, **kwargs)

    def run_scheduled_gui_selection_sync(self, *args, **kwargs):
        return plan_selection_gui_sync.run_scheduled_gui_selection_sync(
            self.session, *args, **kwargs
        )

    def get_plan_target_kind_for_object(self, *args, **kwargs):
        return plan_targets.get_plan_target_kind_for_object(self.session, *args, **kwargs)

    def get_plan_target_for_object(self, *args, **kwargs):
        return plan_targets.get_plan_target_for_object(self.session, *args, **kwargs)

    def get_plan_target_at_position(self, *args, **kwargs):
        return plan_selection_picking.get_plan_target_at_position(self.session, *args, **kwargs)

    def get_plan_space_instances(self, *args, **kwargs):
        return plan_selection_picking.get_plan_space_instances(self.session, *args, **kwargs)

    def get_plan_region_instances(self, *args, **kwargs):
        return plan_selection_picking.get_plan_region_instances(self.session, *args, **kwargs)

    def get_plan_target_from_edit_node(self, *args, **kwargs):
        return plan_selection_picking.get_plan_target_from_edit_node(
            self.session,
            *args,
            **kwargs,
        )

    def get_provider_overlay_target_from_edit_node(self, *args, **kwargs):
        return plan_selection_picking.get_provider_overlay_target_from_edit_node(
            self.session,
            *args,
            **kwargs,
        )

    def get_hovered_plan_target(self, *args, **kwargs):
        return plan_selection_picking.get_hovered_plan_target(self.session, *args, **kwargs)

    def clear_hovered_plan_targets(self, *args, **kwargs):
        return plan_selection_picking.clear_hovered_plan_targets(self.session, *args, **kwargs)

    def queue_prime_hover_pick_caches(self, *args, **kwargs):
        return plan_selection_picking.queue_prime_hover_pick_caches(self.session, *args, **kwargs)

    def prime_hover_pick_caches(self, *args, **kwargs):
        return plan_selection_picking.prime_hover_pick_caches(self.session, *args, **kwargs)

    def should_skip_hover_pick(self, *args, **kwargs):
        return plan_selection_picking.should_skip_hover_pick(self.session, *args, **kwargs)

    def update_hovered_plan_target(self, *args, **kwargs):
        return plan_selection_picking.update_hovered_plan_target(self.session, *args, **kwargs)

    def addSelection(self, doc, obj, sub, point):
        return plan_selection_gui_sync.selection_observer_add(self.session, doc, obj, sub, point)

    def removeSelection(self, doc, obj, sub):
        return plan_selection_gui_sync.selection_observer_remove(self.session, doc, obj, sub)

    def setSelection(self, doc):
        return plan_selection_gui_sync.selection_observer_set(self.session, doc)

    def clearSelection(self, doc):
        return plan_selection_gui_sync.selection_observer_clear(self.session, doc)

    def setPreselection(self, doc, obj, sub):
        return plan_selection_gui_sync.selection_observer_set_preselection(
            self.session, doc, obj, sub
        )

    def removePreselection(self, doc, obj, sub):
        return plan_selection_gui_sync.selection_observer_remove_preselection(
            self.session, doc, obj, sub
        )

    @contextmanager
    def selection_changes_suppressed(self):
        with plan_selection_gui_sync.selection_changes_suppressed(self.session):
            yield

    def xy_polygon_area(self, polyline):
        from . import picking as plan_picking

        del self
        return plan_picking.xy_polygon_area(polyline)

    def xy_point_in_polygon(self, point, polyline, tolerance=1e-9):
        from . import picking as plan_picking

        del self
        return plan_picking.xy_point_in_polygon(point, polyline, tolerance=tolerance)

    def get_screen_distance_sq_to_segment(self, mouse_pos, start, end):
        from . import picking as plan_picking

        return plan_picking.get_screen_distance_sq_to_segment(
            self.session,
            mouse_pos,
            start,
            end,
        )

    def get_screen_distance_sq_to_projected_segment(self, cursor_xy, start_xy, end_xy):
        from . import picking as plan_picking

        del self
        return plan_picking.get_screen_distance_sq_to_projected_segment(
            cursor_xy,
            start_xy,
            end_xy,
        )

    def pick_plan_symbol_target_from_overlays(self, mouse_pos, radius_px=10):
        from . import picking as plan_picking

        return plan_picking.pick_plan_symbol_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def pick_plan_opening_target_from_overlays(self, mouse_pos, radius_px=10, candidates=None):
        from . import picking as plan_picking

        return plan_picking.pick_plan_opening_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
            candidates=candidates,
        )

    def pick_provider_overlay_target_from_overlays(self, mouse_pos, radius_px=12):
        from . import picking as plan_picking

        return plan_picking.pick_provider_overlay_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def pick_provider_overlay_target_from_objects_info(self, mouse_pos):
        from . import picking as plan_picking

        return plan_picking.pick_provider_overlay_target_from_objects_info(self.session, mouse_pos)

    def pick_plan_space_target_from_overlays(self, mouse_pos, radius_px=10):
        from . import picking as plan_picking

        return plan_picking.pick_plan_space_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def pick_plan_region_target_from_overlays(self, mouse_pos, radius_px=10):
        from . import picking as plan_picking

        return plan_picking.pick_plan_region_target_from_overlays(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def get_region_pick_polylines(self, region):
        from . import picking as plan_picking

        return plan_picking.get_region_pick_polylines(self.session, region)

    def pick_plan_region_target_from_polylines(self, mouse_pos):
        from . import picking as plan_picking

        return plan_picking.pick_plan_region_target_from_polylines(self.session, mouse_pos)

    def pick_plan_target_from_footprint_faces(
        self,
        mouse_pos,
        is_target,
        get_faces,
        target_label="target",
    ):
        from . import picking as plan_picking

        return plan_picking.pick_plan_target_from_footprint_faces(
            self.session,
            mouse_pos,
            is_target,
            get_faces,
            target_label=target_label,
        )

    def pick_plan_space_target_from_footprints(self, mouse_pos):
        from . import picking as plan_picking

        return plan_picking.pick_plan_space_target_from_footprints(self.session, mouse_pos)

    def pick_plan_region_target_from_footprints(self, mouse_pos):
        from . import picking as plan_picking

        return plan_picking.pick_plan_region_target_from_footprints(self.session, mouse_pos)

    def get_edit_node(self, mouse_pos):
        from . import picking as plan_picking

        return plan_picking.get_edit_node(self.session, mouse_pos)

    def pick_selected_opening_handle(self, mouse_pos, radius_px=10):
        from . import picking as plan_picking

        return plan_picking.pick_selected_opening_handle(
            self.session,
            mouse_pos,
            radius_px=radius_px,
        )

    def is_plan_selectable_wall(self, obj):
        from . import targets as plan_targets

        return plan_targets.is_plan_selectable_wall(self.session, obj)

    def is_plan_space_object(self, obj):
        from . import targets as plan_targets

        return plan_targets.is_plan_space_object(self.session, obj)

    def is_plan_custom_pick_only_object(self, obj):
        from . import targets as plan_targets

        return plan_targets.is_plan_custom_pick_only_object(self.session, obj)

    def is_plan_space_separator_object(self, obj):
        from . import targets as plan_targets

        return plan_targets.is_plan_space_separator_object(self.session, obj)

    def is_plan_region_object(self, obj):
        from . import targets as plan_targets

        return plan_targets.is_plan_region_object(self.session, obj)

    def get_gui_selection_ex(self):
        return plan_selection_gui_sync.get_gui_selection_ex()

    def get_gui_selection(self):
        return plan_selection_gui_sync.get_gui_selection()

    def add_gui_selection_object(self, obj):
        return plan_selection_gui_sync.add_gui_selection_object(obj)

    def is_plan_additive_selection_active(self):
        return is_plan_additive_selection_active(self.session)

    def normalize_plan_requirement_tags(self, value):
        from . import targets as plan_targets

        del self
        return plan_targets.normalize_plan_requirement_tags(value)

    def get_plan_host_ref(self, obj):
        from . import targets as plan_targets

        return plan_targets.get_plan_host_ref(self.session, obj)

    def make_plan_target_record(self, kind, obj, selected_keys=None, primary_key=None):
        from . import targets as plan_targets

        return plan_targets.make_plan_target_record(
            self.session,
            kind,
            obj,
            selected_keys=selected_keys,
            primary_key=primary_key,
        )

    def get_plan_targets(self, selected_only=False):
        from . import targets as plan_targets

        return plan_targets.get_plan_targets(self.session, selected_only=selected_only)

    def get_selected_objects(self):
        return tuple(
            self.normalize_gui_object_selection(
                tuple(self.get_gui_selection()) + tuple(self.session._provider_selected_objects)
            )
        )

    def resolve_plan_target_object(self, target):
        from . import targets as plan_targets

        return plan_targets.resolve_plan_target_object(self.session, target)

    def resolve_plan_semantic_object(self, target):
        from . import targets as plan_targets

        return plan_targets.resolve_plan_semantic_object(self.session, target)
