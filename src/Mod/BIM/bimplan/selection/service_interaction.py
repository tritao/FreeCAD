# SPDX-License-Identifier: LGPL-2.1-or-later

"""Interaction-facing BIM Plan Edit selection services."""

from bimplan.runtime import tools as plan_runtime_tools
from bimplan.picking import hover as plan_hover_picking

from . import activation as plan_selection_activation
from . import edit_nodes as plan_edit_nodes
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds
from . import targets as plan_targets
from .service_common import _SessionAPI, get_plan_target_state_key


class PlanSelectionTargetService(_SessionAPI):
    normalize_plan_requirement_tags = staticmethod(plan_targets.normalize_plan_requirement_tags)

    def get_plan_target_kind_for_object(self, obj):
        return plan_targets.get_plan_target_kind_for_object(self.session, obj)

    def get_plan_target_for_object(self, obj, parent_obj=None):
        return plan_targets.get_plan_target_for_object(self.session, obj, parent_obj)

    def is_plan_selectable_wall(self, obj):
        return plan_targets.is_plan_selectable_wall(self.session, obj)

    def is_plan_space_object(self, obj):
        return plan_targets.is_plan_space_object(self.session, obj)

    def is_plan_custom_pick_only_object(self, obj):
        if not obj:
            return False
        obj = plan_targets._get_plan_semantic_object(self.session, obj)
        return (
            plan_targets._call_component_method(
                self.session,
                "openings",
                "is_hosted_opening_object",
                obj,
                default=False,
            )
            or self.is_plan_space_object(obj)
            or self.is_plan_region_object(obj)
        )

    def is_plan_space_separator_object(self, obj):
        return plan_targets.is_plan_space_separator_object(self.session, obj)

    def is_plan_region_object(self, obj):
        return plan_targets.is_plan_region_object(self.session, obj)

    def get_plan_host_ref(self, obj):
        if obj is None:
            return ""
        host_ref = self.session.visibility.get_plan_text_property(obj, ("HostRef",))
        if host_ref:
            return host_ref
        hosts = getattr(obj, "Hosts", None) or ()
        for host in hosts:
            name = str(getattr(host, "Name", "") or "").strip()
            if name:
                return name
        return ""

    def make_plan_target_record(self, kind, obj, selected_keys=None, primary_key=None):
        if not kind or obj is None:
            return None
        provider_target = (
            self.session.providers.get_plan_provider_target_for_object(obj)
            if kind == plan_target_kinds.PLAN_TARGET_PROVIDER
            else None
        )
        semantic_obj = self.session.visibility.get_plan_semantic_object(obj)
        doc = getattr(obj, "Document", None)
        state_key = get_plan_target_state_key(kind, obj)
        fields = plan_targets.resolve_plan_provider_target_display_fields(
            self.session,
            semantic_obj,
            provider_target,
            getattr(obj, "Label", getattr(obj, "Name", "")),
        )
        return plan_targets.PlanTarget(
            kind=str(kind or ""),
            document_name=str(getattr(doc, "Name", "") or ""),
            object_name=str(getattr(obj, "Name", "") or ""),
            label=fields.label,
            provider_id=fields.provider_id,
            target_key=fields.target_key,
            category=fields.category,
            role=fields.role,
            semantic_document_name=fields.semantic_document_name,
            semantic_object_name=fields.semantic_object_name,
            semantic_label=fields.semantic_label,
            is_selected=bool(selected_keys and state_key in selected_keys),
            is_primary=bool(primary_key is not None and state_key == primary_key),
        )

    def get_plan_targets(self, selected_only=False):
        selected_targets = tuple(
            plan_target_kinds.coerce_plan_target_ref(target)
            for target in self.session.selection.state.get_selected_plan_targets()
        )
        selected_keys = {
            get_plan_target_state_key(target.kind, target.obj) for target in selected_targets
        }
        selected_keys.discard(None)
        primary_key = None
        primary_target = plan_target_kinds.coerce_plan_target_ref(
            self.session.selection.state.get_selected_plan_target()
        )
        if primary_target.kind and primary_target.obj:
            primary_key = get_plan_target_state_key(primary_target.kind, primary_target.obj)

        if selected_only:
            source_targets = selected_targets
        else:
            source_targets = []
            seen = set()
            active_storey_name = getattr(self.session.active_storey, "Name", None)
            provider_refresh_scope = self.session.providers.plan_provider_refresh_cache_scope()
            with provider_refresh_scope:
                for obj in getattr(self.session.doc, "Objects", []) or []:
                    target = plan_target_kinds.coerce_plan_target_ref(
                        self.get_plan_target_for_object(obj)
                    )
                    target_kind = target.kind
                    target_obj = target.obj
                    if not target_kind or not target_obj:
                        continue
                    state_key = get_plan_target_state_key(target_kind, target_obj)
                    if state_key is None or state_key in seen:
                        continue
                    semantic_obj = self.session.visibility.get_plan_semantic_object(target_obj)
                    if active_storey_name is not None:
                        storeys = self.session.visibility.get_object_storeys(
                            semantic_obj or target_obj
                        )
                        if storeys and not any(
                            parent.Name == active_storey_name for parent in storeys
                        ):
                            continue
                    seen.add(state_key)
                    source_targets.append(target)

        records = []
        for target in source_targets:
            target_record = self.make_plan_target_record(
                target.kind,
                target.obj,
                selected_keys=selected_keys,
                primary_key=primary_key,
            )
            if target_record is not None:
                records.append(target_record)
        return tuple(records)

    def resolve_plan_target_object(self, target):
        if target is None:
            return None
        document_name = str(getattr(target, "document_name", "") or "").strip()
        object_name = str(getattr(target, "object_name", "") or "").strip()
        if not object_name:
            return None
        doc = None
        if document_name and getattr(self.session.doc, "Name", None) == document_name:
            doc = self.session.doc
        elif document_name:
            try:
                import FreeCAD

                doc = FreeCAD.getDocument(document_name)
            except Exception:
                doc = None
        else:
            doc = self.session.doc
        if doc is None:
            return None
        try:
            return doc.getObject(object_name)
        except Exception:
            return None

    def resolve_plan_semantic_object(self, target):
        if target is None:
            return None
        semantic_document_name = str(getattr(target, "semantic_document_name", "") or "").strip()
        semantic_object_name = str(getattr(target, "semantic_object_name", "") or "").strip()
        if semantic_document_name and semantic_object_name:
            doc = None
            if getattr(self.session.doc, "Name", None) == semantic_document_name:
                doc = self.session.doc
            else:
                try:
                    import FreeCAD

                    doc = FreeCAD.getDocument(semantic_document_name)
                except Exception:
                    doc = None
            if doc is not None:
                try:
                    resolved = doc.getObject(semantic_object_name)
                except Exception:
                    resolved = None
                if resolved is not None:
                    return resolved
        return self.session.visibility.get_plan_semantic_object(
            self.resolve_plan_target_object(target)
        )


class PlanSelectionHoverService(_SessionAPI):
    def set_hovered_wall(self, wall):
        if self.session.selection.state.is_selected_plan_target("wall", wall):
            wall = None
        if self.session.hovered_wall == wall:
            return
        self.session.hovered_wall = wall
        self.session.overlays.walls.sync_junction_node_overlays()
        self.session.overlays.walls.sync_hovered_wall_overlay()
        self.session.overlays.walls.sync_hovered_wall_opening_context_overlay()
        if self.session.current_tool == plan_runtime_tools.PlanTool.JOIN:
            self.session.task_panels.refresh_task_panel_status(reason="full")

    def set_hovered_opening(self, obj):
        return plan_target_dispatch.set_hovered_target(
            self.session, plan_target_kinds.PLAN_TARGET_OPENING, obj
        )

    def set_hovered_symbol(self, obj):
        return plan_target_dispatch.set_hovered_target(
            self.session, plan_target_kinds.PLAN_TARGET_SYMBOL, obj
        )

    def set_hovered_provider(self, obj):
        return plan_target_dispatch.set_hovered_target(
            self.session, plan_target_kinds.PLAN_TARGET_PROVIDER, obj
        )

    def set_hovered_space(self, obj):
        return plan_target_dispatch.set_hovered_target(
            self.session, plan_target_kinds.PLAN_TARGET_SPACE, obj
        )

    def set_hovered_region(self, obj):
        return plan_target_dispatch.set_hovered_target(
            self.session, plan_target_kinds.PLAN_TARGET_REGION, obj
        )

    def get_hovered_plan_target(self):
        return plan_target_kinds.coerce_plan_target_ref(
            plan_hover_picking.get_hovered_plan_target(self.session)
        )

    def clear_hovered_plan_targets(self, *args, **kwargs):
        return plan_hover_picking.clear_hovered_plan_targets(self.session, *args, **kwargs)

    def queue_prime_hover_pick_caches(self, *args, **kwargs):
        return plan_hover_picking.queue_prime_hover_pick_caches(self.session, *args, **kwargs)

    def prime_hover_pick_caches(self, *args, **kwargs):
        return plan_hover_picking.prime_hover_pick_caches(self.session, *args, **kwargs)

    def should_skip_hover_pick(self, *args, **kwargs):
        return plan_hover_picking.should_skip_hover_pick(self.session, *args, **kwargs)


class PlanSelectionActivationService(_SessionAPI):
    def queue_restore_selected_plan_target(self, kind, obj):
        plan_target_dispatch.queue_restore_selected_target(self.session, kind, obj)

    def select_plan_target_for_plan_edit(
        self,
        kind,
        obj,
        queue_restore=False,
        sync_gui_selection=False,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        if not plan_target_dispatch.validate_plan_target(self.session, kind, obj):
            return False
        previous_kind, previous_obj = self.session.selection.state.get_selected_plan_target()
        self.session.current_tool = plan_runtime_tools.PlanTool.SELECT
        self.session.provider_transient_state.provider_selected_objects = []
        preserve_hovered_symbol_overlay = (
            kind == plan_target_kinds.PLAN_TARGET_SYMBOL
            and self.session.hovered_symbol == obj
            and bool(self.session.overlay_tracker_state.symbol_hover_trackers)
        )
        self.session.selection.state.set_selected_plan_target(
            kind,
            obj,
            pending_restore=queue_restore,
            preserve_hovered_symbol_overlay=preserve_hovered_symbol_overlay,
        )
        if sync_gui_selection:
            if defer_gui_selection:
                self.session.selection.sync.schedule_gui_selection_object(obj)
            else:
                self.session.selection.sync.set_gui_selection_object(obj)
        self.session.overlays.walls.apply_selected_wall_selection_feedback(
            defer_grips=kind == plan_target_kinds.PLAN_TARGET_WALL and defer_wall_grips
        )
        plan_target_dispatch.sync_selected_target_visuals(
            self.session,
            kinds=plan_target_kinds.CLEAR_PLAN_SELECTION_VISUAL_KINDS,
            previous_kind=previous_kind,
            previous_obj=previous_obj,
        )
        self.session.overlays.spaces.sync_secondary_selected_overlays()
        self.session.task_panels.refresh_task_panel_status(
            reason=(
                "selection"
                if self.session.current_tool == plan_runtime_tools.PlanTool.SELECT
                else "full"
            )
        )
        if queue_restore:
            self.queue_restore_selected_plan_target(kind, obj)
        return True

    def select_opening_for_plan_edit(self, *args, **kwargs):
        return self.select_plan_target_for_plan_edit(
            plan_target_kinds.PLAN_TARGET_OPENING, *args, **kwargs
        )

    def select_symbol_for_plan_edit(self, *args, **kwargs):
        return self.select_plan_target_for_plan_edit(
            plan_target_kinds.PLAN_TARGET_SYMBOL, *args, **kwargs
        )

    def select_region_for_plan_edit(self, *args, **kwargs):
        return self.select_plan_target_for_plan_edit(
            plan_target_kinds.PLAN_TARGET_REGION, *args, **kwargs
        )

    def select_space_for_plan_edit(self, *args, **kwargs):
        return self.select_plan_target_for_plan_edit(
            plan_target_kinds.PLAN_TARGET_SPACE, *args, **kwargs
        )

    def select_wall_for_plan_edit(self, *args, **kwargs):
        return self.select_plan_target_for_plan_edit(
            plan_target_kinds.PLAN_TARGET_WALL, *args, **kwargs
        )

    def activate_plan_target_for_kind(
        self,
        kind,
        mouse_pos,
        event_callback=None,
        resolved_target=None,
        *,
        defer_gui_selection=None,
        defer_wall_grips=None,
    ):
        return plan_selection_activation._activate_configured_plan_target(
            self.session,
            kind,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def activate_plan_target(
        self,
        kind,
        mouse_pos,
        event_callback=None,
        sync_gui_selection=False,
        clear_hovered_kinds=None,
        resolved_target=None,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        if resolved_target is None:
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.picking.pick(mouse_pos)
            )
        else:
            target_ref = plan_target_kinds.coerce_plan_target_ref(resolved_target)
        with self.session.performance.plan_perf_trace_span(
            f"activate_plan_target_{kind}", requested_kind=kind, mouse_pos=mouse_pos
        ):
            self.session.performance.plan_perf_count(f"activate_plan_target_attempts_{kind}")
            self.session.performance.plan_perf_set_fields(
                resolved_target=self.session.performance.plan_perf_describe_target(
                    target_ref.kind, target_ref.obj
                )
            )
            target_obj = target_ref.obj if target_ref.kind == kind else None
            behavior = plan_selection_activation._get_target_activation_behavior(kind)
            if behavior is None or not behavior.select_target(
                self.session,
                target_obj,
                queue_restore=True,
                sync_gui_selection=sync_gui_selection,
                defer_gui_selection=defer_gui_selection,
                defer_wall_grips=defer_wall_grips,
            ):
                self.session.performance.plan_perf_set_fields(activate_plan_target_result=False)
                return False
            self.session.selection.hover.clear_hovered_plan_targets(clear_hovered_kinds)
            self.session.input.claim_left_button_click(event_callback)
            self.session.performance.plan_perf_set_fields(
                activate_plan_target_result=True,
                activated_target=self.session.performance.plan_perf_describe_target(
                    kind, target_obj
                ),
            )
            return True

    def activate_semantic_plan_target(self, mouse_pos, event_callback=None):
        def _hover_pick_matches_mouse():
            last_mouse_pos = self.session.hover_pick_state.last_mouse_pos
            if mouse_pos is None or last_mouse_pos is None:
                return False
            try:
                return (
                    abs(float(last_mouse_pos[0]) - float(mouse_pos[0])) <= 1.0
                    and abs(float(last_mouse_pos[1]) - float(mouse_pos[1])) <= 1.0
                )
            except Exception:
                return False

        target_ref = self.session.selection.hover.get_hovered_plan_target()
        hover_pick_dirty = bool(self.session.hover_pick_state.dirty)
        reuse_hovered_target = (
            target_ref.kind == plan_target_kinds.PLAN_TARGET_WALL
            and target_ref.obj is not None
            and not hover_pick_dirty
            and _hover_pick_matches_mouse()
        )
        perf = getattr(self.session, "performance", None)
        if not reuse_hovered_target:
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.picking.pick(mouse_pos)
            )
            source = "picked_after_throttled_hover" if hover_pick_dirty else "picked"
            self.session.hover_pick_state.dirty = False
            if perf is not None:
                perf.plan_perf_count(f"semantic_target_source_{source}")
                perf.plan_perf_set_fields(semantic_target_source=source)
        else:
            if perf is not None:
                perf.plan_perf_count("semantic_target_source_hovered")
                perf.plan_perf_set_fields(
                    semantic_target_source="hovered",
                    hovered_target=perf.plan_perf_describe_target(target_ref.kind, target_ref.obj),
                )
        if plan_selection_activation._get_target_activation_behavior(target_ref.kind) is None:
            return False
        if target_ref.kind == plan_target_kinds.PLAN_TARGET_WALL:
            return plan_selection_activation._activate_configured_plan_target(
                self.session,
                target_ref.kind,
                mouse_pos,
                event_callback=event_callback,
                resolved_target=target_ref,
                defer_gui_selection=True,
                defer_wall_grips=True,
            )
        return plan_selection_activation._activate_configured_plan_target(
            self.session,
            target_ref.kind,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=target_ref,
        )

    def activate_opening_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_OPENING,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def activate_symbol_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_SYMBOL,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def activate_region_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_REGION,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def activate_space_target(self, mouse_pos, event_callback=None, resolved_target=None):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_SPACE,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def activate_wall_target(
        self,
        mouse_pos,
        event_callback=None,
        resolved_target=None,
        defer_gui_selection=False,
        defer_wall_grips=False,
    ):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_WALL,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
            defer_gui_selection=defer_gui_selection,
            defer_wall_grips=defer_wall_grips,
        )

    def clear_plan_selection_state(self):
        previous_kind, previous_obj = self.session.selection.state.get_selected_plan_target()
        with self.session.performance.plan_perf_trace_event(
            "clear_plan_selection_state",
            clear_selection_started_kind=previous_kind or "none",
            clear_selection_started_target=self.session.performance.plan_perf_describe_target(
                previous_kind, previous_obj
            ),
        ):
            with self.session.performance.plan_perf_trace_span(
                "clear_plan_selection_gui_selection"
            ):
                self.session.selection.sync.set_gui_selection([])
            with self.session.performance.plan_perf_trace_span("clear_plan_selection_target_state"):
                self.session.selection.state.set_selected_plan_target()
                self.session.provider_transient_state.provider_selected_objects = []
            with self.session.performance.plan_perf_trace_span("clear_plan_selection_hover_state"):
                plan_target_dispatch.clear_hovered_targets(self.session)
            with self.session.performance.plan_perf_trace_span("clear_plan_selection_wall_grips"):
                self.session.overlays.walls.clear_wall_grips()
                self.session.overlays.walls.clear_selected_wall_overlay()
            with self.session.performance.plan_perf_trace_span(
                "clear_plan_selection_secondary_overlays"
            ):
                self.session.overlays.spaces.sync_secondary_selected_overlays()
            plan_target_dispatch.sync_selected_target_visuals(
                self.session,
                kinds=plan_target_kinds.CLEAR_PLAN_SELECTION_VISUAL_KINDS,
                force=True,
                trace_style="by_kind",
                trace_prefix="clear_plan_selection",
            )
            with self.session.performance.plan_perf_trace_span("clear_plan_selection_task_status"):
                self.session.task_panels.refresh_task_panel_status(
                    reason=(
                        "selection"
                        if self.session.current_tool == plan_runtime_tools.PlanTool.SELECT
                        else "full"
                    )
                )
            selected_kind, selected_obj = self.session.selection.state.get_selected_plan_target()
            self.session.performance.plan_perf_set_fields(
                clear_selection_ended_kind=selected_kind or "none",
                clear_selection_ended_target=self.session.performance.plan_perf_describe_target(
                    selected_kind, selected_obj
                ),
                clear_selection_cleared_wall=bool(previous_kind == "wall" and not selected_kind),
            )

    def activate_provider_overlay_target_node(self, node, event_callback=None):
        target_ref = plan_target_kinds.coerce_plan_target_ref(
            self.session.picking.get_provider_overlay_target_from_edit_node(node)
        )
        if target_ref.obj is None:
            return False
        if self.session.selection.state.is_valid_plan_target(target_ref.kind, target_ref.obj):
            self.session.provider_transient_state.provider_selected_objects = []
            self.session.selection.state.set_pending_selected_plan_target(target_ref)
        else:
            self.session.provider_transient_state.provider_selected_objects = [target_ref.obj]
            self.session.selection.state.set_pending_selected_plan_target()
        plan_target_dispatch.clear_hovered_targets(self.session)
        self.session.selection.sync.set_gui_selection_object(target_ref.obj)
        self.session.selection.refresh.refresh_primary_selected_plan_target()
        self.session.input.claim_left_button_click(event_callback)
        return True

    def toggle_raw_plan_object_selection(self, obj, event_callback=None):
        if obj is None:
            return False

        primary_kind, primary_obj, selection = (
            plan_selection_activation._get_current_additive_gui_selection(self.session)
        )
        provider_selection = self.session.selection.sync.normalize_gui_object_selection(
            self.session.provider_transient_state.provider_selected_objects
        )
        if obj in provider_selection:
            provider_selection = [selected for selected in provider_selection if selected != obj]
        else:
            provider_selection.append(obj)
        self.session.provider_transient_state.provider_selected_objects = (
            self.session.selection.sync.normalize_gui_object_selection(provider_selection)
        )
        new_selection = self.session.selection.sync.normalize_gui_object_selection(
            [
                selected
                for selected in selection
                if self.session.selection.targets.get_plan_target_for_object(selected).kind
            ],
        )
        next_kind, next_obj = plan_selection_activation._resolve_next_selected_target(
            self.session,
            new_selection,
            primary_kind,
            primary_obj,
        )
        return plan_selection_activation._apply_additive_selection_update(
            self.session,
            new_selection,
            next_kind,
            next_obj,
            event_callback,
        )

    def toggle_plan_target_selection_at_position(self, mouse_pos, event_callback=None):
        node = self.session.picking.pick_edit_node(mouse_pos)
        if plan_edit_nodes.get_edit_node_kind(node) in (
            "provider_overlay_point",
            "provider_overlay_target",
        ):
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.picking.get_provider_overlay_target_from_edit_node(node)
            )
            if (
                target_ref.obj is not None
                and not self.session.selection.state.is_valid_plan_target(
                    target_ref.kind,
                    target_ref.obj,
                )
            ):
                return self.toggle_raw_plan_object_selection(target_ref.obj, event_callback)
        else:
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.picking.get_plan_target_from_edit_node(node)
            )
        if target_ref.kind is None:
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.picking.pick(mouse_pos)
            )
        if not target_ref.kind or not target_ref.obj:
            return False

        primary_kind, primary_obj, selection = (
            plan_selection_activation._get_current_additive_gui_selection(self.session)
        )

        was_selected = target_ref.obj in selection
        if was_selected:
            new_selection = [selected for selected in selection if selected != target_ref.obj]
            fallback_target = None if primary_obj == target_ref.obj else target_ref
            next_kind, next_obj = plan_selection_activation._resolve_next_selected_target(
                self.session,
                new_selection,
                primary_kind,
                primary_obj,
                fallback_target=fallback_target,
            )
        else:
            new_selection = list(selection)
            new_selection.append(target_ref.obj)
            next_kind, next_obj = plan_selection_activation._resolve_next_selected_target(
                self.session,
                new_selection,
                primary_kind,
                primary_obj,
                fallback_target=target_ref,
            )

        return plan_selection_activation._apply_additive_selection_update(
            self.session,
            new_selection,
            next_kind,
            next_obj,
            event_callback,
        )

    def is_plan_additive_selection_active(self):
        if self.session.current_tool != plan_runtime_tools.PlanTool.SELECT:
            return False
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ControlModifier)
        except Exception:
            return False
