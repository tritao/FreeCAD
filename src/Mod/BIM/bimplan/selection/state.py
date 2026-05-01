# SPDX-License-Identifier: LGPL-2.1-or-later

"""Primary BIM Plan Edit selection services."""

from dataclasses import dataclass, field

import FreeCADGui

from bimplan.runtime import tools as plan_runtime_tools

from . import gui_sync as plan_selection_gui_sync
from . import targets as plan_targets
from . import kinds as plan_target_kinds
from .common import (
    _SessionAPI,
    _clear_gui_preselection,
    _get_gui_preselection_object,
    get_plan_target_object_from_state,
    get_plan_target_state_key,
)

_PRIMARY_SELECTED_TARGET_PRIORITY = {
    kind: index
    for index, kind in enumerate(plan_target_kinds.PRIMARY_SELECTED_TARGET_PRIORITY_KINDS)
}
_GUI_SELECTION_TOOL_NAMES = (
    plan_runtime_tools.PlanTool.SELECT,
    plan_runtime_tools.PlanTool.PICK_SPACE_REGION,
)
_PENDING_TARGET_UNCHANGED = object()
_WALL_GRIP_NONE = "none"
_WALL_GRIP_CLEAR = "clear"
_WALL_GRIP_SYNC = "sync"
_MISSING = object()


def _provider_runtime_api(session):
    providers = getattr(session, "providers", None)
    return getattr(providers, "runtime", providers)


def _overlay_runtime_api(session):
    overlays = getattr(session, "overlays", None)
    return getattr(overlays, "runtime", overlays)


@dataclass(frozen=True)
class SelectionRefreshResult:
    primary_target_ref: object = field(default_factory=plan_target_kinds.make_plan_target_ref)
    secondary_targets: tuple = ()
    pending_target: object = _PENDING_TARGET_UNCHANGED
    wall_grip_action: str = _WALL_GRIP_NONE

    @property
    def primary_kind(self):
        return self.primary_target_ref.kind

    @property
    def primary_obj(self):
        return self.primary_target_ref.obj


@dataclass(frozen=True)
class GuiSelectionResolutionState:
    pending_target_ref: object = None
    preserved_target_ref: object = None


class PlanSelectionStateService(_SessionAPI):
    get_plan_target_object_from_state = staticmethod(get_plan_target_object_from_state)
    get_plan_target_state_key = staticmethod(get_plan_target_state_key)

    def discard_runtime_references(self):
        selection_state = self.session.selection_state
        self.set_selected_plan_target_state()
        selection_state.secondary_selected_plan_targets_state = []
        self.session.hovered_wall = None
        self.session.hovered_opening = None
        self.session.hovered_symbol = None
        self.session.hovered_provider = None
        self.session.hovered_space = None
        self.session.hovered_region = None
        selection_state.pending_selected_plan_target = None

    def get_selected_target_for_kind(self, kind):
        selection_state = self.session.selection_state
        if selection_state.selected_plan_target_kind == kind:
            return selection_state.selected_plan_target_obj
        return None

    def set_selected_target_for_kind(self, kind, obj):
        selection_state = self.session.selection_state
        if obj is None:
            if selection_state.selected_plan_target_kind == kind:
                selection_state.selected_plan_target_kind = None
                selection_state.selected_plan_target_obj = None
            return
        selection_state.selected_plan_target_kind = kind
        selection_state.selected_plan_target_obj = obj

    def get_selected_plan_target_state(self):
        selection_state = self.session.selection_state
        kind = selection_state.selected_plan_target_kind
        obj = selection_state.selected_plan_target_obj
        if kind not in plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS or obj is None:
            return plan_target_kinds.make_plan_target_ref()
        return plan_target_kinds.make_plan_target_ref(kind, obj)

    def set_selected_plan_target_state(self, kind=None, obj=None):
        if kind not in plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS or obj is None:
            kind = None
            obj = None
        selection_state = self.session.selection_state
        selection_state.selected_plan_target_kind = kind
        selection_state.selected_plan_target_obj = obj

    def _get_native_selected_plan_target(self):
        self.session.selection.refresh.sanitize_plan_target_references()
        target_ref = self.get_selected_plan_target_state()
        if self.is_valid_plan_target(target_ref.kind, target_ref.obj):
            return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)
        if target_ref.kind is not None or target_ref.obj is not None:
            self.set_selected_plan_target_state()
        return plan_target_kinds.make_plan_target_ref()

    def _iter_normalized_plan_targets(self, targets):
        seen = set()
        for target in targets or []:
            target_ref = plan_target_kinds.coerce_plan_target_ref(target)
            if not self.is_valid_plan_target(target_ref.kind, target_ref.obj):
                continue
            key = self.get_plan_target_state_key(target_ref.kind, target_ref.obj)
            if key is None or key in seen:
                continue
            seen.add(key)
            yield plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)

    def _filter_secondary_selected_plan_targets(self, targets, primary_kind, primary_obj):
        for target_ref in targets:
            if target_ref.kind == primary_kind and target_ref.obj == primary_obj:
                continue
            yield plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)

    def _get_current_secondary_selected_plan_targets(self):
        primary_target_ref = self._get_native_selected_plan_target()
        selection_state = self.session.selection_state
        self.set_secondary_selected_plan_targets(
            selection_state.secondary_selected_plan_targets_state,
            primary_kind=primary_target_ref.kind,
            primary_obj=primary_target_ref.obj,
        )
        return list(selection_state.secondary_selected_plan_targets_state)

    def get_selected_plan_target_object(self, kind=None):
        selected_target_ref = self._get_native_selected_plan_target()
        if kind is not None and selected_target_ref.kind != kind:
            return None
        return selected_target_ref.obj

    def is_selected_plan_target(self, kind, obj=None):
        selected_target_ref = self.get_selected_plan_target()
        if selected_target_ref.kind != kind:
            return False
        if obj is None:
            return selected_target_ref.obj is not None
        return selected_target_ref.obj == obj

    def clear_selected_plan_target_if_matches(self, kind, obj):
        if not self.is_selected_plan_target(kind, obj):
            return False
        self.set_selected_plan_target_state()
        return True

    def selected_plan_target_changed(self, previous_kind, previous_obj, kind=None):
        current_target_ref = self.get_selected_plan_target()
        if kind is None:
            return (
                previous_kind != current_target_ref.kind or previous_obj != current_target_ref.obj
            )
        previous_target = self.get_plan_target_object_from_state(
            previous_kind,
            previous_obj,
            kind,
        )
        current_target = self.get_plan_target_object_from_state(
            current_target_ref.kind,
            current_target_ref.obj,
            kind,
        )
        return previous_target != current_target

    def set_pending_selected_plan_target(self, kind=None, obj=None):
        selection_state = self.session.selection_state
        if obj is None and kind is not None:
            target_ref = plan_target_kinds.coerce_plan_target_ref(kind)
            kind = target_ref.kind
            obj = target_ref.obj
        if self.is_valid_plan_target(kind, obj):
            selection_state.pending_selected_plan_target = plan_target_kinds.make_plan_target_ref(
                kind, obj
            )
            return
        selection_state.pending_selected_plan_target = None

    def consume_pending_selected_plan_target(self):
        selection_state = self.session.selection_state
        pending_target = plan_target_kinds.coerce_plan_target_ref(
            selection_state.pending_selected_plan_target
        )
        selection_state.pending_selected_plan_target = None
        if self.is_valid_plan_target(pending_target.kind, pending_target.obj):
            return pending_target
        return plan_target_kinds.make_plan_target_ref()

    def get_selected_plan_target(self):
        return self._get_native_selected_plan_target()

    def get_first_plan_target_from_selection(self, selection):
        for selected in selection or []:
            target_ref = self.session.selection.targets.get_plan_target_for_object(selected)
            if target_ref.kind and target_ref.obj:
                return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)
        return plan_target_kinds.make_plan_target_ref()

    def is_valid_plan_target(self, kind, obj):
        validate = getattr(self.session, "_is_valid_plan_target", None)
        if callable(validate):
            return bool(validate(kind, obj))
        return plan_targets.validate_plan_target(self.session, kind, obj)

    def normalize_plan_target_list(self, targets):
        return list(self._iter_normalized_plan_targets(targets))

    def normalize_plan_targets_from_selection(self, selection):
        return self.normalize_plan_target_list(
            [
                target_ref
                for target_ref in (
                    self.session.selection.targets.get_plan_target_for_object(selected)
                    for selected in (selection or [])
                )
                if target_ref.kind and target_ref.obj
            ],
        )

    def set_secondary_selected_plan_targets(self, targets, primary_kind=None, primary_obj=None):
        if primary_kind is None and primary_obj is None:
            primary_target_ref = self.get_selected_plan_target()
            primary_kind = primary_target_ref.kind
            primary_obj = primary_target_ref.obj
        self.session.selection_state.secondary_selected_plan_targets_state = list(
            self._filter_secondary_selected_plan_targets(
                self._iter_normalized_plan_targets(targets),
                primary_kind,
                primary_obj,
            )
        )

    def sync_secondary_selected_plan_targets_from_selection(
        self, selection, primary_kind=None, primary_obj=None
    ):
        self.set_secondary_selected_plan_targets(
            self.normalize_plan_targets_from_selection(selection),
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    def sync_secondary_selected_plan_targets_from_gui_selection(
        self, primary_kind=None, primary_obj=None
    ):
        self.sync_secondary_selected_plan_targets_from_selection(
            plan_selection_gui_sync.get_gui_selection(),
            primary_kind=primary_kind,
            primary_obj=primary_obj,
        )

    def get_secondary_selected_plan_targets(self):
        return self._get_current_secondary_selected_plan_targets()

    def get_selected_plan_targets(self):
        primary_target_ref = self._get_native_selected_plan_target()
        targets = []
        if primary_target_ref.kind and primary_target_ref.obj:
            targets.append(
                plan_target_kinds.make_plan_target_ref(
                    primary_target_ref.kind, primary_target_ref.obj
                )
            )
        targets.extend(
            self._filter_secondary_selected_plan_targets(
                self._iter_normalized_plan_targets(
                    self._get_current_secondary_selected_plan_targets()
                ),
                primary_target_ref.kind,
                primary_target_ref.obj,
            )
        )
        return targets

    def set_selected_plan_target(
        self,
        kind=None,
        obj=None,
        pending_restore=False,
        preserve_hovered_symbol_overlay=False,
    ):
        if self.is_valid_plan_target(kind, obj):
            self.set_selected_plan_target_state(kind, obj)
        else:
            self.set_selected_plan_target_state()
            kind = None
            obj = None
        self.sync_secondary_selected_plan_targets_from_gui_selection(
            primary_kind=kind,
            primary_obj=obj,
        )
        self.session.wall_relations.clear_plan_relation_status()
        self.session.viewport.sync_active_plan_target_object()
        if pending_restore:
            self.set_pending_selected_plan_target(kind, obj)
        else:
            self.set_pending_selected_plan_target()
        if not self.session.lifecycle_state.tearing_down:
            self.session.overlays.walls.sync_junction_node_overlays()
            self.session.overlays.openings.sync_selected_wall_opening_context_overlay()
            self.session.overlays.walls.sync_hovered_wall_opening_context_overlay()
            plan_targets.sync_hovered_target_visuals(
                self.session,
                kinds=(plan_target_kinds.PLAN_TARGET_OPENING,),
            )
            if not preserve_hovered_symbol_overlay:
                plan_targets.sync_hovered_target_visuals(
                    self.session,
                    kinds=(plan_target_kinds.PLAN_TARGET_SYMBOL,),
                )
            plan_targets.sync_hovered_target_visuals(
                self.session,
                kinds=(
                    plan_target_kinds.PLAN_TARGET_SPACE,
                    plan_target_kinds.PLAN_TARGET_REGION,
                ),
            )


class PlanSelectionRefreshService(_SessionAPI):
    def _is_valid_plan_target(self, kind, obj):
        return self.session.selection.state.is_valid_plan_target(kind, obj)

    def _should_preserve_provider_selected_target(self, kind, obj, selected):
        if kind != "provider" or obj is None or selected != obj:
            return False
        if not self._is_valid_plan_target(kind, obj):
            return False
        return plan_selection_gui_sync.is_visible_provider_target_object(self.session, obj)

    def resolve_selected_target_for_gui_object(
        self,
        selected,
        *,
        pending_target_ref=None,
        preserved_target_ref=None,
        pending_kind=None,
        pending_target=None,
        preserved_kind=None,
        preserved_target=None,
    ):
        if selected is None:
            return plan_target_kinds.make_plan_target_ref()
        if pending_target_ref is None and (pending_kind is not None or pending_target is not None):
            pending_target_ref = plan_target_kinds.make_plan_target_ref(
                pending_kind, pending_target
            )
        pending_target_ref = plan_target_kinds.coerce_plan_target_ref(pending_target_ref)
        if selected == pending_target_ref.obj and self._is_valid_plan_target(
            pending_target_ref.kind, pending_target_ref.obj
        ):
            return plan_target_kinds.make_plan_target_ref(
                pending_target_ref.kind, pending_target_ref.obj
            )
        if preserved_target_ref is None and (
            preserved_kind is not None or preserved_target is not None
        ):
            preserved_target_ref = plan_target_kinds.make_plan_target_ref(
                preserved_kind,
                preserved_target,
            )
        preserved_target_ref = plan_target_kinds.coerce_plan_target_ref(preserved_target_ref)
        if self._should_preserve_provider_selected_target(
            preserved_target_ref.kind,
            preserved_target_ref.obj,
            selected,
        ):
            return plan_target_kinds.make_plan_target_ref(
                preserved_target_ref.kind, preserved_target_ref.obj
            )
        return self.session.selection.targets.get_plan_target_for_object(selected)

    def _get_gui_selection_resolution_state(self, previous_kind, previous_obj):
        pending_target_ref = plan_target_kinds.coerce_plan_target_ref(
            self.session.selection_state.pending_selected_plan_target
        )
        preserved_target_ref = plan_target_kinds.make_plan_target_ref()
        if previous_kind == plan_target_kinds.PLAN_TARGET_PROVIDER:
            preserved_target_ref = plan_target_kinds.make_plan_target_ref(
                previous_kind, previous_obj
            )
        return GuiSelectionResolutionState(
            pending_target_ref=pending_target_ref,
            preserved_target_ref=preserved_target_ref,
        )

    def _resolve_gui_selection_target(self, selected, resolution_state):
        return self.resolve_selected_target_for_gui_object(
            selected,
            pending_target_ref=resolution_state.pending_target_ref,
            preserved_target_ref=resolution_state.preserved_target_ref,
        )

    def _choose_primary_selected_target(self, selected_targets, pending_target_ref=None):
        pending_target_ref = plan_target_kinds.coerce_plan_target_ref(pending_target_ref)
        if pending_target_ref.kind is not None and pending_target_ref.obj is not None:
            for target_ref in selected_targets:
                if (
                    target_ref.kind == pending_target_ref.kind
                    and target_ref.obj == pending_target_ref.obj
                ):
                    return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)
        if not selected_targets:
            return plan_target_kinds.make_plan_target_ref()
        primary_target_ref = min(
            selected_targets,
            key=lambda target_ref: _PRIMARY_SELECTED_TARGET_PRIORITY.get(
                target_ref.kind, len(_PRIMARY_SELECTED_TARGET_PRIORITY)
            ),
        )
        return plan_target_kinds.make_plan_target_ref(
            primary_target_ref.kind, primary_target_ref.obj
        )

    def _apply_selection_refresh_result(self, refresh_result):
        primary_target_ref = plan_target_kinds.coerce_plan_target_ref(
            refresh_result.primary_target_ref
        )
        self.session.selection.state.set_selected_plan_target_state(
            primary_target_ref.kind,
            primary_target_ref.obj,
        )
        self.session.selection.state.set_secondary_selected_plan_targets(
            refresh_result.secondary_targets,
            primary_kind=primary_target_ref.kind,
            primary_obj=primary_target_ref.obj,
        )
        if refresh_result.pending_target is not _PENDING_TARGET_UNCHANGED:
            if refresh_result.pending_target is None:
                self.session.selection.state.set_pending_selected_plan_target()
            else:
                self.session.selection.state.set_pending_selected_plan_target(
                    refresh_result.pending_target
                )
        if refresh_result.wall_grip_action == _WALL_GRIP_CLEAR:
            self.session.overlays.walls.clear_wall_grips()
        elif refresh_result.wall_grip_action == _WALL_GRIP_SYNC:
            self.session.overlays.walls.sync_wall_grips()

    def _get_selection_refresh_baseline(self):
        previous_target_ref = self.session.selection.state.get_selected_plan_target()
        self.session.performance.plan_perf_set_fields(
            selected_before=self.session.performance.plan_perf_describe_target(
                previous_target_ref.kind, previous_target_ref.obj
            ),
            selected_before_kind=previous_target_ref.kind or "none",
        )
        previous_wall = self.session.selection.state.get_plan_target_object_from_state(
            previous_target_ref.kind,
            previous_target_ref.obj,
            plan_target_kinds.PLAN_TARGET_WALL,
        )
        return previous_target_ref.kind, previous_target_ref.obj, previous_wall

    def _resolve_direct_selection_refresh_result(self, previous_wall):
        if self.session.wall_edit.is_wall_edit_modal_active():
            interaction_state = self.session.interaction_state
            return SelectionRefreshResult(
                primary_target_ref=plan_target_kinds.make_plan_target_ref(
                    plan_target_kinds.PLAN_TARGET_WALL,
                    interaction_state.edit_wall,
                ),
                wall_grip_action=_WALL_GRIP_SYNC,
            )
        if self.session.current_tool == plan_runtime_tools.PlanTool.SET_SPACE_TEXT:
            interaction_state = self.session.interaction_state
            return SelectionRefreshResult(
                primary_target_ref=plan_target_kinds.make_plan_target_ref(
                    plan_target_kinds.PLAN_TARGET_SPACE,
                    (
                        interaction_state.edit_space
                        if self.session.selection.targets.is_plan_space_object(
                            interaction_state.edit_space
                        )
                        else None
                    ),
                ),
                wall_grip_action=_WALL_GRIP_CLEAR,
            )
        if self.session.current_tool == plan_runtime_tools.PlanTool.JOIN:
            wall = previous_wall
            if not self.session.selection.targets.is_plan_selectable_wall(wall):
                self.session.current_tool = plan_runtime_tools.PlanTool.SELECT
                wall = None
            return SelectionRefreshResult(
                primary_target_ref=plan_target_kinds.make_plan_target_ref(
                    plan_target_kinds.PLAN_TARGET_WALL,
                    wall,
                ),
                wall_grip_action=_WALL_GRIP_CLEAR,
            )
        if self.session.current_tool not in _GUI_SELECTION_TOOL_NAMES:
            return SelectionRefreshResult(pending_target=None)
        return None

    def _get_gui_selection(self):
        try:
            return FreeCADGui.Selection.getSelection()
        except (ReferenceError, RuntimeError):
            return _MISSING

    def _collect_selected_targets_from_gui_selection(self, selection, previous_kind, previous_obj):
        selected_targets = []
        resolution_state = self._get_gui_selection_resolution_state(previous_kind, previous_obj)
        provider_refresh_scope = _provider_runtime_api(
            self.session
        ).plan_provider_refresh_cache_scope()
        with provider_refresh_scope:
            for selected in selection:
                target_ref = self._resolve_gui_selection_target(selected, resolution_state)
                if target_ref.kind:
                    selected_targets.append(target_ref)
        self.session.performance.plan_perf_count(
            "selected_targets_considered", len(selected_targets)
        )
        return selected_targets, resolution_state.pending_target_ref

    def _resolve_gui_selection_refresh_result(self, selection, previous_kind, previous_obj):
        if not selection:
            pending_target_ref = self.session.selection.state.consume_pending_selected_plan_target()
            return SelectionRefreshResult(
                primary_target_ref=plan_target_kinds.coerce_plan_target_ref(pending_target_ref),
            )

        selected_targets, pending_target_ref = self._collect_selected_targets_from_gui_selection(
            selection,
            previous_kind,
            previous_obj,
        )
        primary_target_ref = self._choose_primary_selected_target(
            selected_targets,
            pending_target_ref=pending_target_ref,
        )
        if primary_target_ref.kind is None:
            return SelectionRefreshResult(pending_target=None)
        pending_selection = primary_target_ref
        if len(selection) == 1 and primary_target_ref.kind not in (
            plan_target_kinds.PLAN_TARGET_SPACE,
            plan_target_kinds.PLAN_TARGET_REGION,
        ):
            pending_selection = None
        return SelectionRefreshResult(
            primary_target_ref=primary_target_ref,
            secondary_targets=tuple(selected_targets),
            pending_target=pending_selection,
        )

    def _resolve_selection_refresh_result(self, previous_kind, previous_obj, previous_wall):
        refresh_result = self._resolve_direct_selection_refresh_result(previous_wall)
        if refresh_result is not None:
            return refresh_result
        selection = self._get_gui_selection()
        if selection is _MISSING:
            self.session.selection.state.set_selected_plan_target_state()
            return None
        self.session.performance.plan_perf_count("gui_selection_size", len(selection or []))
        return self._resolve_gui_selection_refresh_result(
            selection,
            previous_kind,
            previous_obj,
        )

    def _sync_wall_grips_after_selection_refresh(
        self,
        refresh_result,
        previous_kind,
        previous_obj,
        *,
        force_wall_visual_resync=False,
    ):
        if refresh_result.wall_grip_action != _WALL_GRIP_NONE:
            return
        wall_target_changed = self.session.selection.state.selected_plan_target_changed(
            previous_kind,
            previous_obj,
            plan_target_kinds.PLAN_TARGET_WALL,
        )
        if not wall_target_changed and not force_wall_visual_resync:
            return
        if self.session.selection.state.get_selected_plan_target_object(
            plan_target_kinds.PLAN_TARGET_WALL
        ):
            self.session.overlays.walls.schedule_wall_grip_sync()
        else:
            self.session.overlays.walls.clear_wall_grips()

    def _record_selection_refresh_result(self, previous_kind):
        selected_kind, selected_obj = self.session.selection.state.get_selected_plan_target()
        self.session.performance.plan_perf_set_fields(
            selected_after=self.session.performance.plan_perf_describe_target(
                selected_kind, selected_obj
            ),
            selected_after_kind=selected_kind or "none",
            selection_refresh_cleared_target=bool(previous_kind and not selected_kind),
        )

    def clear_selected_visuals(
        self,
        kinds=None,
        *,
        clear_handle_kinds=None,
        include_wall_grips=False,
        include_selected_wall_opening_context=False,
        include_secondary_selection=False,
    ):
        if include_wall_grips:
            self.session.overlays.walls.clear_wall_grips()
        plan_targets.clear_selected_target_visuals(
            self.session,
            kinds=kinds,
            clear_handle_kinds=clear_handle_kinds,
        )
        if include_selected_wall_opening_context:
            self.session.overlays.openings.clear_selected_wall_opening_context_overlay()
        if include_secondary_selection:
            self.session.overlays.spaces.clear_secondary_selected_overlays()

    def restore_selected_wall_visuals(self, *, defer_grips=False):
        if not self.session.selection.state.is_selected_plan_target("wall"):
            self.session.overlays.walls.clear_wall_grips()
            self.session.overlays.walls.clear_selected_wall_overlay()
            self.session.overlays.openings.clear_selected_wall_opening_context_overlay()
            return False
        self.session.overlays.walls.apply_selected_wall_selection_feedback(defer_grips=defer_grips)
        self.session.overlays.openings.sync_selected_wall_opening_context_overlay()
        return True

    def clear_hidden_provider_preselection(self):
        if self.session.lifecycle_state.tearing_down:
            return False
        preselected_obj = _get_gui_preselection_object(self.session)
        if preselected_obj is None:
            return False
        if not plan_selection_gui_sync.should_filter_hidden_provider_preselection_for_object(
            self.session, preselected_obj
        ):
            return False
        self.session.performance.plan_perf_count("provider_preselection_cleared_for_mode")
        return _clear_gui_preselection()

    def sanitize_plan_target_references(self):
        visibility = getattr(self.session, "visibility", None)
        is_live_document_object = getattr(visibility, "is_live_document_object", None)
        if not callable(is_live_document_object):
            return False
        changed = False
        for kind in ("wall", "opening", "symbol", "region", "space"):
            obj = self.session.selection.state.get_selected_target_for_kind(kind)
            if obj is None or is_live_document_object(obj):
                continue
            self.session.selection.state.set_selected_target_for_kind(kind, None)
            changed = True
        for attr in (
            "hovered_wall",
            "hovered_opening",
            "hovered_symbol",
            "hovered_provider",
            "hovered_region",
            "hovered_space",
        ):
            obj = getattr(self.session, attr, None)
            if obj is None or is_live_document_object(obj):
                continue
            setattr(self.session, attr, None)
            changed = True
        selection_state = self.session.selection_state
        normalized_secondary = self.session.selection.state.normalize_plan_target_list(
            selection_state.secondary_selected_plan_targets_state
        )
        if normalized_secondary != selection_state.secondary_selected_plan_targets_state:
            selection_state.secondary_selected_plan_targets_state = normalized_secondary
            changed = True
        return changed

    def clear_selected_plan_target_if_matches(self, kind, obj):
        return self.session.selection.state.clear_selected_plan_target_if_matches(kind, obj)

    def handle_secondary_selection_document_visual_change(self, obj, prop):
        from bimplan import document_visuals as plan_document_visuals

        secondary_overlay_refresh = False
        for target_ref in self.session.selection.state.get_secondary_selected_plan_targets():
            if target_ref.kind in ("region", "space"):
                handled = self.session.spaces.refresh_target_document_visual_change(
                    target_ref.kind, target_ref.obj, obj, prop
                )
            elif target_ref.kind == "symbol":
                handled = self.session.overlays.symbols.refresh_target_document_visual_dependency(
                    target_ref.obj, obj, prop
                )
            elif target_ref.kind == "opening":
                handled = self.session.openings.refresh_target_document_visual_dependency(
                    target_ref.obj, obj, prop
                )
            elif (
                target_ref.kind == "wall"
                and obj == target_ref.obj
                and prop in plan_document_visuals.WALL_VISUAL_PROPERTIES
            ):
                handled = True
            else:
                handled = False
            if handled:
                secondary_overlay_refresh = True
        if not secondary_overlay_refresh:
            return False
        _overlay_runtime_api(self.session).queue_plan_overlay_visual_refresh(
            plan_document_visuals.PLAN_VISUAL_SECONDARY_SELECTION
        )
        return True

    def refresh_document_dependent_secondary_selection_visuals(self):
        for target_ref in self.session.selection.state.get_secondary_selected_plan_targets():
            if target_ref.kind in ("region", "space"):
                self.session.spaces.refresh_plan_target_footprint(
                    target_ref.kind,
                    target_ref.obj,
                )
            elif target_ref.kind == "symbol":
                self.session.overlays.symbols.refresh_symbol_visual_footprint(target_ref.obj)
            elif target_ref.kind == "opening":
                self.session.openings.refresh_opening_visual_footprints(target_ref.obj)

    def handle_wall_document_visual_change(self, obj, prop, selected_wall):
        from bimplan import document_visuals as plan_document_visuals

        if (
            obj == self.session.hovered_wall
            and prop in plan_document_visuals.WALL_VISUAL_PROPERTIES
        ):
            _overlay_runtime_api(self.session).queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_HOVERED_WALL
            )
            return True
        if obj != selected_wall or prop not in plan_document_visuals.WALL_VISUAL_PROPERTIES:
            return False
        self.session.openings.refresh_wall_hosted_opening_footprints(obj)
        self.schedule_selected_wall_reset(prop, obj)
        return True

    def schedule_selected_wall_reset(self, reason, obj):
        del reason, obj
        selection_sync_state = self.session.selection_sync_state
        if (
            selection_sync_state.pending_selected_wall_reset
            or self.session.lifecycle_state.tearing_down
        ):
            return
        selection_sync_state.pending_selected_wall_reset = True
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, lambda: self.reset_selected_wall_after_change())
        except ImportError:
            self.reset_selected_wall_after_change()

    def reset_selected_wall_after_change(self):
        self.session.selection_sync_state.pending_selected_wall_reset = False
        if (
            self.session.lifecycle_state.tearing_down
            or self.session.current_tool != plan_runtime_tools.PlanTool.SELECT
        ):
            return
        wall = self.session.selection.state.get_selected_plan_target_object("wall")
        if not wall:
            return
        self.session.overlays.walls.clear_wall_grips()
        self.session.overlays.walls.clear_selected_wall_overlay()
        self.clear_selected_plan_target_if_matches("wall", wall)
        plan_selection_gui_sync.set_gui_selection(self.session, [])
        self.session.task_panels.refresh_task_panel_status()

    def suspend_selected_wall_state(self, wall=None, clear_gui_selection=True):
        if self.session.lifecycle_state.tearing_down:
            return
        if wall is None:
            wall = self.session.selection.state.get_selected_plan_target_object("wall")
        if wall is None:
            return
        if not self.session.selection.state.is_selected_plan_target("wall", wall):
            return
        self.session.selection_sync_state.pending_selected_wall_reset = False
        self.session.overlays.walls.clear_wall_grips()
        self.session.overlays.walls.clear_selected_wall_overlay()
        self.clear_selected_plan_target_if_matches("wall", wall)
        if clear_gui_selection:
            plan_selection_gui_sync.set_gui_selection(self.session, [])
        self.session.task_panels.refresh_task_panel_status(reason="selection")

    def sync_primary_selected_plan_target_visuals(
        self,
        previous_kind=None,
        previous_obj=None,
        *,
        force_wall_visual_resync=False,
    ):
        with self.session.performance.plan_perf_trace_span(
            "sync_primary_selected_plan_target_visuals"
        ):
            if (
                self.session.current_tool != plan_runtime_tools.PlanTool.SELECT
                or force_wall_visual_resync
                or self.session.selection.state.selected_plan_target_changed(
                    previous_kind,
                    previous_obj,
                    plan_target_kinds.PLAN_TARGET_WALL,
                )
            ):
                with self.session.performance.plan_perf_trace_span("sync_selected_wall_overlay"):
                    self.session.overlays.walls.sync_selected_wall_overlay()
            with self.session.performance.plan_perf_trace_span(
                "sync_selected_wall_opening_context_overlay"
            ):
                self.session.overlays.openings.sync_selected_wall_opening_context_overlay()
            with self.session.performance.plan_perf_trace_span("sync_hovered_wall_overlay"):
                self.session.overlays.walls.sync_hovered_wall_overlay()
            with self.session.performance.plan_perf_trace_span(
                "sync_hovered_wall_opening_context_overlay"
            ):
                self.session.overlays.walls.sync_hovered_wall_opening_context_overlay()
            plan_targets.sync_selected_target_visuals(
                self.session,
                kinds=plan_target_kinds.PRIMARY_SELECTED_VISUAL_SYNC_KINDS,
                previous_kind=previous_kind,
                previous_obj=previous_obj,
                trace_style="by_method",
            )
            plan_targets.sync_hovered_target_visuals(
                self.session,
                kinds=(
                    plan_target_kinds.PLAN_TARGET_SYMBOL,
                    plan_target_kinds.PLAN_TARGET_PROVIDER,
                ),
                trace_style="by_method",
            )
            plan_targets.sync_selected_target_visuals(
                self.session,
                kinds=(plan_target_kinds.PLAN_TARGET_PROVIDER,),
                force=True,
                trace_style="by_method",
            )
            plan_targets.sync_hovered_target_visuals(
                self.session,
                kinds=(
                    plan_target_kinds.PLAN_TARGET_OPENING,
                    plan_target_kinds.PLAN_TARGET_SPACE,
                    plan_target_kinds.PLAN_TARGET_REGION,
                ),
                trace_style="by_method",
            )
            with self.session.performance.plan_perf_trace_span("sync_secondary_selected_overlays"):
                self.session.overlays.spaces.sync_secondary_selected_overlays()
            with self.session.performance.plan_perf_trace_span("sync_active_plan_target_object"):
                self.session.viewport.sync_active_plan_target_object()
            self.session.task_panels.refresh_task_panel_status(
                reason=(
                    "selection"
                    if self.session.current_tool == plan_runtime_tools.PlanTool.SELECT
                    else "full"
                )
            )

    def refresh_selected_plan_target(self, *, force_wall_visual_resync=False):
        with self.session.performance.plan_perf_trace_span("refresh_selected_plan_target"):
            self.session.performance.plan_perf_count("selection_refreshes")
            if self.session.lifecycle_state.tearing_down:
                return
            if self.session.lifecycle_state.ignore_selection_changes:
                return

            previous_kind, previous_obj, previous_wall = self._get_selection_refresh_baseline()
            refresh_result = self._resolve_selection_refresh_result(
                previous_kind,
                previous_obj,
                previous_wall,
            )
            self._apply_selection_refresh_result(refresh_result)
            self._sync_wall_grips_after_selection_refresh(
                refresh_result,
                previous_kind,
                previous_obj,
                force_wall_visual_resync=force_wall_visual_resync,
            )
            self.sync_primary_selected_plan_target_visuals(
                previous_kind,
                previous_obj,
                force_wall_visual_resync=force_wall_visual_resync,
            )
            self._record_selection_refresh_result(previous_kind)

    def refresh_primary_selected_plan_target(self, *, force_wall_visual_resync=False):
        self.refresh_selected_plan_target(force_wall_visual_resync=force_wall_visual_resync)
