# SPDX-License-Identifier: LGPL-2.1-or-later

"""Primary BIM Plan Edit selection services."""

from contextlib import contextmanager

from bimplan.runtime import tools as plan_runtime_tools

from . import gui_sync as plan_selection_gui_sync
from . import state_refresh as plan_selection_state_refresh
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds
from .service_common import (
    _SessionAPI,
    _clear_gui_preselection,
    _get_gui_preselection_object,
    get_plan_target_object_from_state,
    get_plan_target_state_key,
    normalize_gui_object_selection,
)


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
        return plan_target_dispatch.validate_plan_target(self.session, kind, obj)

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
            plan_target_dispatch.sync_hovered_target_visuals(
                self.session,
                kinds=(plan_target_kinds.PLAN_TARGET_OPENING,),
            )
            if not preserve_hovered_symbol_overlay:
                plan_target_dispatch.sync_hovered_target_visuals(
                    self.session,
                    kinds=(plan_target_kinds.PLAN_TARGET_SYMBOL,),
                )
            plan_target_dispatch.sync_hovered_target_visuals(
                self.session,
                kinds=(
                    plan_target_kinds.PLAN_TARGET_SPACE,
                    plan_target_kinds.PLAN_TARGET_REGION,
                ),
            )


class PlanSelectionRefreshService(_SessionAPI):
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
        plan_target_dispatch.clear_selected_target_visuals(
            self.session,
            kinds=kinds,
            clear_handle_kinds=clear_handle_kinds,
        )
        if include_selected_wall_opening_context:
            self.session.overlays.openings.clear_selected_wall_opening_context_overlay()
        if include_secondary_selection:
            self.session.overlays.spaces.clear_secondary_selected_overlays()

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
        self.session.overlays.queue_plan_overlay_visual_refresh(
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
            self.session.overlays.queue_plan_overlay_visual_refresh(
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
            plan_target_dispatch.sync_selected_target_visuals(
                self.session,
                kinds=plan_target_kinds.PRIMARY_SELECTED_VISUAL_SYNC_KINDS,
                previous_kind=previous_kind,
                previous_obj=previous_obj,
                trace_style="by_method",
            )
            plan_target_dispatch.sync_hovered_target_visuals(
                self.session,
                kinds=(
                    plan_target_kinds.PLAN_TARGET_SYMBOL,
                    plan_target_kinds.PLAN_TARGET_PROVIDER,
                ),
                trace_style="by_method",
            )
            plan_target_dispatch.sync_selected_target_visuals(
                self.session,
                kinds=(plan_target_kinds.PLAN_TARGET_PROVIDER,),
                force=True,
                trace_style="by_method",
            )
            plan_target_dispatch.sync_hovered_target_visuals(
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

            previous_kind, previous_obj, previous_wall = (
                plan_selection_state_refresh._get_selection_refresh_baseline(self.session)
            )
            refresh_result = plan_selection_state_refresh._resolve_selection_refresh_result(
                self.session,
                previous_kind,
                previous_obj,
                previous_wall,
            )
            plan_selection_state_refresh._apply_selection_refresh_result(
                self.session, refresh_result
            )
            plan_selection_state_refresh._sync_wall_grips_after_selection_refresh(
                self.session,
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
            plan_selection_state_refresh._record_selection_refresh_result(
                self.session, previous_kind
            )

    def refresh_primary_selected_plan_target(self, *, force_wall_visual_resync=False):
        self.refresh_selected_plan_target(force_wall_visual_resync=force_wall_visual_resync)


class PlanSelectionSyncService(_SessionAPI):
    def get_gui_selection_ex(self):
        return plan_selection_gui_sync.get_gui_selection_ex()

    def get_gui_selection(self):
        return plan_selection_gui_sync.get_gui_selection()

    def add_gui_selection_object(self, obj):
        return plan_selection_gui_sync.add_gui_selection_object(obj)

    def attach_selection_observer(self):
        selection_sync_state = self.session.selection_sync_state
        if not selection_sync_state.selection_observer_added:
            import FreeCADGui

            FreeCADGui.Selection.addObserver(self.session)
            selection_sync_state.selection_observer_added = True

    def detach_selection_observer(self):
        selection_sync_state = self.session.selection_sync_state
        if selection_sync_state.selection_observer_added:
            import FreeCADGui

            FreeCADGui.Selection.removeObserver(self.session)
            selection_sync_state.selection_observer_added = False

    def schedule_selection_refresh(self):
        if (
            self.session.lifecycle_state.tearing_down
            or self.session.lifecycle_state.ignore_selection_changes
        ):
            return
        state = self.session.selection_sync_state
        if state.selection_refresh_queued:
            return
        state.selection_refresh_queued = True
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, lambda: self.run_scheduled_selection_refresh())
        except Exception:
            self.run_scheduled_selection_refresh()

    def run_scheduled_selection_refresh(self):
        state = self.session.selection_sync_state
        if not state.selection_refresh_queued:
            return
        state.selection_refresh_queued = False
        with self.session.performance.plan_perf_trace_event("selection_observer_refresh"):
            if (
                self.session.lifecycle_state.tearing_down
                or self.session.lifecycle_state.ignore_selection_changes
            ):
                return
            self.session.selection.refresh.refresh_primary_selected_plan_target()

    def schedule_clear_plan_selection_state(self):
        if (
            self.session.lifecycle_state.tearing_down
            or self.session.lifecycle_state.ignore_selection_changes
        ):
            return
        state = self.session.selection_sync_state
        if state.clear_plan_selection_state_queued:
            return
        state.clear_plan_selection_state_queued = True
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(0, lambda: self.run_scheduled_clear_plan_selection_state())
        except Exception:
            self.run_scheduled_clear_plan_selection_state()

    def run_scheduled_clear_plan_selection_state(self):
        state = self.session.selection_sync_state
        if not state.clear_plan_selection_state_queued:
            return
        state.clear_plan_selection_state_queued = False
        with self.session.performance.plan_perf_trace_event("scheduled_clear_plan_selection_state"):
            if (
                self.session.lifecycle_state.tearing_down
                or self.session.lifecycle_state.ignore_selection_changes
            ):
                return
            self.session.selection.activation.clear_plan_selection_state()

    def set_gui_selection(self, selection):
        plan_selection_gui_sync._reset_gui_selection_sync_state(self.session)
        plan_selection_gui_sync._apply_gui_selection(self.session, selection)

    def set_gui_selection_object(self, obj):
        if not obj:
            return
        self.set_gui_selection([obj])

    def schedule_gui_selection_object(self, obj, delay_ms=80):
        if self.session.lifecycle_state.tearing_down or not obj:
            return
        state = self.session.selection_sync_state
        state.gui_selection_sync_queued = True
        state.gui_selection_sync_generation += 1
        state.queued_gui_selection_object = obj
        generation = state.gui_selection_sync_generation
        try:
            from PySide import QtCore

            QtCore.QTimer.singleShot(
                delay_ms,
                lambda generation=generation: self.run_scheduled_gui_selection_sync(generation),
            )
        except Exception:
            self.run_scheduled_gui_selection_sync(generation)

    def run_scheduled_gui_selection_sync(self, generation=None):
        state = self.session.selection_sync_state
        if not state.gui_selection_sync_queued:
            return
        if generation is not None and generation != state.gui_selection_sync_generation:
            return
        obj = state.queued_gui_selection_object
        if obj is None:
            state.gui_selection_sync_queued = False
            return
        with self.session.performance.plan_perf_trace_event("scheduled_gui_selection_sync"):
            if self.session.lifecycle_state.tearing_down:
                state.gui_selection_sync_queued = False
                state.queued_gui_selection_object = None
                return
            state.gui_selection_sync_in_progress = True
            current_generation = state.gui_selection_sync_generation
            try:
                self.set_gui_selection_object(obj)
            finally:
                plan_selection_gui_sync._schedule_finish_gui_selection_sync(
                    self.session, current_generation
                )

    def normalize_gui_object_selection(self, selection):
        return normalize_gui_object_selection(selection)

    @contextmanager
    def selection_changes_suppressed(self):
        previous_ignore = self.session.lifecycle_state.ignore_selection_changes
        self.session.lifecycle_state.ignore_selection_changes = True
        try:
            yield
        finally:
            self.session.lifecycle_state.ignore_selection_changes = previous_ignore

    def selection_observer_add(self, doc, obj, sub, point):
        return plan_selection_gui_sync.selection_observer_add(self.session, doc, obj, sub, point)

    def selection_observer_remove(self, doc, obj, sub):
        return plan_selection_gui_sync.selection_observer_remove(self.session, doc, obj, sub)

    def selection_observer_set(self, doc):
        return plan_selection_gui_sync.selection_observer_set(self.session, doc)

    def selection_observer_clear(self, doc):
        return plan_selection_gui_sync.selection_observer_clear(self.session, doc)

    def selection_observer_set_preselection(self, doc, obj, sub):
        return plan_selection_gui_sync.selection_observer_set_preselection(
            self.session, doc, obj, sub
        )

    def selection_observer_remove_preselection(self, doc, obj, sub):
        return plan_selection_gui_sync.selection_observer_remove_preselection(
            self.session, doc, obj, sub
        )
