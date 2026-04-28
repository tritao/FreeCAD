# SPDX-License-Identifier: LGPL-2.1-or-later

"""Interaction-facing BIM Plan Edit selection services."""

from bimplan.runtime import tools as plan_runtime_tools

from . import activation as plan_selection_activation
from . import edit_nodes as plan_edit_nodes
from . import hover_picking as plan_hover_picking
from . import picking as plan_selection_picking
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds
from . import targets as plan_targets
from .service_common import _SessionAPI, get_plan_target_state_key


class PlanSelectionTargetService(_SessionAPI):
    normalize_plan_requirement_tags = staticmethod(
        plan_targets.normalize_plan_requirement_tags
    )

    def get_plan_target_kind_for_object(self, obj):
        if plan_targets._call_component_method(
            self.session,
            "openings",
            "is_hosted_opening_object",
            obj,
            default=False,
        ):
            return plan_target_kinds.PLAN_TARGET_OPENING
        if plan_targets._call_component_method(
            self.session,
            "visibility",
            "is_plan_symbol_instance",
            obj,
            default=False,
        ):
            return plan_target_kinds.PLAN_TARGET_SYMBOL
        if (
            plan_targets._call_component_method(
                self.session,
                "providers",
                "is_plan_provider_target_object",
                obj,
                default=False,
            )
            or plan_targets._call_component_method(
                self.session,
                "providers",
                "get_plan_provider_target_for_object",
                obj,
                default=None,
            )
            or plan_targets.plan_provider_runtime.is_plan_provider_target_object(
                self.session, obj
            )
        ):
            return plan_target_kinds.PLAN_TARGET_PROVIDER
        if self.is_plan_region_object(obj):
            return plan_target_kinds.PLAN_TARGET_REGION
        if self.is_plan_selectable_wall(obj):
            return plan_target_kinds.PLAN_TARGET_WALL
        if self.is_plan_space_object(obj):
            return plan_target_kinds.PLAN_TARGET_SPACE
        return None

    def get_plan_target_for_object(self, obj, parent_obj=None):
        seen = set()
        for candidate in (obj, parent_obj):
            if not candidate:
                continue
            name = getattr(candidate, "Name", None)
            if name and name in seen:
                continue
            if name:
                seen.add(name)
            target_kind = self.get_plan_target_kind_for_object(candidate)
            if target_kind:
                return plan_target_kinds.make_plan_target_ref(target_kind, candidate)

        semantic_obj = plan_targets._get_plan_semantic_object(self.session, obj)
        semantic_name = getattr(semantic_obj, "Name", None)
        if semantic_obj and semantic_name not in seen:
            target_kind = self.get_plan_target_kind_for_object(semantic_obj)
            if target_kind:
                return plan_target_kinds.make_plan_target_ref(target_kind, semantic_obj)

        return plan_target_kinds.make_plan_target_ref()

    def is_plan_selectable_wall(self, obj):
        if not obj:
            return False
        legacy = plan_targets.runtime_capabilities.get_callable(
            self.session, "_is_plan_selectable_wall"
        )
        if legacy is not None:
            return bool(legacy(obj))
        obj = plan_targets._get_plan_semantic_object(self.session, obj)
        try:
            import Draft

            return Draft.getType(obj) == "Wall"
        except Exception:
            return False

    def is_plan_space_object(self, obj):
        if not obj:
            return False
        legacy = plan_targets.runtime_capabilities.get_callable(
            self.session, "_is_plan_space_object"
        )
        if legacy is not None:
            return bool(legacy(obj))
        obj = plan_targets._get_plan_semantic_object(self.session, obj)
        try:
            import Draft

            if Draft.getType(obj) == "Space":
                return True
        except Exception:
            pass
        return getattr(obj, "IfcType", "") == "Space"

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
        if not obj:
            return False
        obj = plan_targets._get_plan_semantic_object(self.session, obj)
        try:
            import Draft

            return Draft.getType(obj) == "SpaceSeparator"
        except Exception:
            return False

    def is_plan_region_object(self, obj):
        if not obj:
            return False
        legacy = plan_targets.runtime_capabilities.get_callable(
            self.session, "_is_plan_region_object"
        )
        if legacy is not None:
            return bool(legacy(obj))
        obj = plan_targets._get_plan_semantic_object(self.session, obj)
        try:
            import Draft

            return Draft.getType(obj) == "PlanRegion"
        except Exception:
            return False

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
            get_plan_target_state_key(target.kind, target.obj)
            for target in selected_targets
        }
        selected_keys.discard(None)
        primary_key = None
        primary_target = plan_target_kinds.coerce_plan_target_ref(
            self.session.selection.state.get_selected_plan_target()
        )
        if primary_target.kind and primary_target.obj:
            primary_key = get_plan_target_state_key(
                primary_target.kind, primary_target.obj
            )

        if selected_only:
            source_targets = selected_targets
        else:
            source_targets = []
            seen = set()
            active_storey_name = getattr(self.session.active_storey, "Name", None)
            provider_refresh_scope = (
                self.session.providers.plan_provider_refresh_cache_scope()
            )
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
                    semantic_obj = self.session.visibility.get_plan_semantic_object(
                        target_obj
                    )
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
        semantic_document_name = str(
            getattr(target, "semantic_document_name", "") or ""
        ).strip()
        semantic_object_name = str(
            getattr(target, "semantic_object_name", "") or ""
        ).strip()
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
        return plan_hover_picking.clear_hovered_plan_targets(
            self.session, *args, **kwargs
        )

    def queue_prime_hover_pick_caches(self, *args, **kwargs):
        return plan_hover_picking.queue_prime_hover_pick_caches(
            self.session, *args, **kwargs
        )

    def prime_hover_pick_caches(self, *args, **kwargs):
        return plan_hover_picking.prime_hover_pick_caches(self.session, *args, **kwargs)

    def should_skip_hover_pick(self, *args, **kwargs):
        return plan_hover_picking.should_skip_hover_pick(self.session, *args, **kwargs)

    def update_hovered_plan_target(self, *args, **kwargs):
        return plan_hover_picking.update_hovered_plan_target(
            self.session, *args, **kwargs
        )


class PlanSelectionPickingService(_SessionAPI):
    xy_polygon_area = staticmethod(plan_selection_picking.xy_polygon_area)
    xy_point_in_polygon = staticmethod(plan_selection_picking.xy_point_in_polygon)
    get_screen_distance_sq_to_projected_segment = staticmethod(
        plan_selection_picking.get_screen_distance_sq_to_projected_segment
    )

    def get_plan_space_instances(self):
        return plan_selection_picking._get_cached_plan_instances(
            self.session,
            "plan_space_instances_cache",
            lambda obj: self.session.selection.targets.is_plan_space_object(obj),
            "plan_space_instance_objects_scanned",
            "build_plan_space_instances_cache",
        )

    def get_plan_region_instances(self):
        return plan_selection_picking._get_cached_plan_instances(
            self.session,
            "plan_region_instances_cache",
            lambda obj: self.session.selection.targets.is_plan_region_object(obj),
            "plan_region_instance_objects_scanned",
            "build_plan_region_instances_cache",
        )

    def get_plan_target_from_edit_node(self, node):
        if not node:
            return plan_target_kinds.make_plan_target_ref()
        node_kind = plan_edit_nodes.get_edit_node_kind(node)
        if node_kind in ("provider_overlay_point", "provider_overlay_target"):
            target_ref = self.get_provider_overlay_target_from_edit_node(node)
            if self.session.selection.state.is_valid_plan_target(
                target_ref.kind, target_ref.obj
            ):
                return plan_target_kinds.make_plan_target_ref(
                    target_ref.kind, target_ref.obj
                )
            fallback_target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.selection.targets.get_plan_target_for_object(
                    target_ref.obj
                )
            )
            return plan_target_kinds.make_plan_target_ref(
                fallback_target_ref.kind, fallback_target_ref.obj
            )
        if node_kind == "opening_handle":
            opening, _index = plan_edit_nodes.get_edit_node_payload(node)
            if self.session.openings.is_hosted_opening_object(opening):
                return plan_target_kinds.make_plan_target_ref("opening", opening)
            return plan_target_kinds.make_plan_target_ref()
        if node_kind == "symbol_handle":
            symbol, _role = plan_edit_nodes.get_edit_node_payload(node)
            if self.session.visibility.is_plan_symbol_instance(symbol):
                return plan_target_kinds.make_plan_target_ref("symbol", symbol)
            return plan_target_kinds.make_plan_target_ref()
        try:
            (point,) = plan_edit_nodes.get_edit_node_payload(node)
            doc = plan_selection_picking.FreeCAD.getDocument(
                str(point.documentName.getValue())
            )
            obj = doc.getObject(str(point.objectName.getValue()))
        except Exception:
            return plan_target_kinds.make_plan_target_ref()
        if self.session.openings.is_hosted_opening_object(obj):
            return plan_target_kinds.make_plan_target_ref("opening", obj)
        target_ref = plan_target_kinds.coerce_plan_target_ref(
            self.session.selection.targets.get_plan_target_for_object(obj)
        )
        return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)

    def get_provider_overlay_target_from_edit_node(self, node):
        if not node:
            return (None, None)
        node_kind = plan_edit_nodes.get_edit_node_kind(node)
        if node_kind == "provider_overlay_target":
            try:
                return plan_edit_nodes.get_edit_node_payload(node)
            except Exception:
                return (None, None)
        if node_kind != "provider_overlay_point":
            return (None, None)
        try:
            (point,) = plan_edit_nodes.get_edit_node_payload(node)
            document_name = str(point.documentName.getValue())
            object_name = str(point.objectName.getValue())
            subname = str(point.subElementName.getValue())
        except Exception:
            return (None, None)
        obj = plan_selection_picking._resolve_document_object(
            self.session,
            document_name,
            object_name,
        )
        if obj is None:
            return (None, None)
        target_kind = plan_selection_picking._parse_provider_overlay_target_kind(
            subname
        )
        if target_kind and self.session.selection.state.is_valid_plan_target(
            target_kind, obj
        ):
            return (target_kind, obj)
        inferred_kind, inferred_obj = (
            self.session.selection.targets.get_plan_target_for_object(obj)
        )
        if inferred_kind and inferred_obj:
            return (inferred_kind, inferred_obj)
        return (None, obj)

    def get_screen_distance_sq_to_segment(self, mouse_pos, start, end):
        return plan_selection_picking.get_screen_distance_sq_to_segment(
            self.session,
            mouse_pos,
            start,
            end,
        )

    def pick_plan_symbol_target_from_overlays(self, mouse_pos, radius_px=10):
        with plan_selection_picking._perf_trace_span(
            self.session,
            "pick_symbol_target_from_overlays",
            mouse_pos=mouse_pos,
            radius_px=radius_px,
        ):
            if not self.session.doc or not self.session.view or not mouse_pos:
                return None
            symbol_instances = tuple(
                self.session.overlays.symbols.get_plan_symbol_instances() or ()
            )
            filtered_symbols = []
            for symbol in symbol_instances:
                plan_selection_picking._perf_count(
                    self.session, "symbol_overlay_pick_objects_scanned"
                )
                bounds = self.session.overlays.symbols.get_symbol_overlay_screen_bounds(
                    symbol
                )
                if not plan_selection_picking._screen_bounds_intersects_pick_radius(
                    bounds, mouse_pos, radius_px
                ):
                    plan_selection_picking._perf_count(
                        self.session, "symbol_overlay_pick_bounds_skipped"
                    )
                    continue
                filtered_symbols.append(symbol)
            best_symbol = (
                plan_selection_picking._pick_best_target_from_projected_polylines(
                    self.session,
                    filtered_symbols,
                    self.session.overlays.symbols.get_symbol_overlay_screen_polylines,
                    mouse_pos,
                    radius_px,
                    candidate_count_name="symbol_overlay_pick_candidates",
                    segment_count_name="symbol_overlay_pick_segments_scanned",
                )
            )
            if best_symbol is None:
                best_symbol = (
                    plan_selection_picking._pick_best_target_from_overlay_segments(
                        self.session,
                        filtered_symbols,
                        self.session.overlays.symbols.get_symbol_overlay_segments,
                        mouse_pos,
                        radius_px,
                    )
                )
            plan_selection_picking._perf_set_fields(
                self.session,
                symbol_overlay_pick_result=plan_selection_picking._describe_pick_object(
                    self.session, best_symbol
                ),
            )
            return best_symbol

    def pick_plan_opening_target_from_overlays(
        self, mouse_pos, radius_px=10, candidates=None
    ):
        with plan_selection_picking._perf_trace_span(
            self.session,
            "pick_opening_target_from_overlays",
            mouse_pos=mouse_pos,
            radius_px=radius_px,
            candidate_mode="hosted" if candidates is not None else "document",
        ):
            if not self.session.doc or not self.session.view or not mouse_pos:
                return None
            plan_point = self.session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
            objects = (
                self.session.openings.get_plan_opening_instances()
                if candidates is None
                else candidates
            )
            filtered_objects = []
            seen_names = set()
            for obj in objects or ():
                plan_selection_picking._perf_count(
                    self.session, "opening_overlay_pick_objects_scanned"
                )
                if not self.session.openings.is_hosted_opening_object(obj):
                    continue
                name = getattr(obj, "Name", None)
                if not name or name in seen_names:
                    continue
                seen_names.add(name)
                if plan_selection_picking.should_skip_opening_by_plan_bounds(
                    self.session, obj, plan_point, radius_px
                ):
                    plan_selection_picking._perf_count(
                        self.session, "opening_overlay_pick_bounds_skipped"
                    )
                    continue
                screen_bounds = (
                    self.session.overlays.geometry.get_opening_overlay_screen_bounds(
                        obj
                    )
                )
                if not plan_selection_picking._screen_bounds_intersects_pick_radius(
                    screen_bounds, mouse_pos, radius_px
                ):
                    plan_selection_picking._perf_count(
                        self.session, "opening_overlay_pick_screen_bounds_skipped"
                    )
                    continue
                filtered_objects.append(obj)
            best_opening = (
                plan_selection_picking._pick_best_target_from_projected_polylines(
                    self.session,
                    filtered_objects,
                    self.session.overlays.geometry.get_opening_overlay_screen_polylines,
                    mouse_pos,
                    radius_px,
                    candidate_count_name="opening_overlay_pick_candidates",
                    segment_count_name="opening_overlay_pick_segments_scanned",
                )
            )
            plan_selection_picking._perf_set_fields(
                self.session,
                opening_overlay_pick_mode="screen",
                opening_overlay_pick_result=plan_selection_picking._describe_pick_object(
                    self.session, best_opening
                ),
            )
            return best_opening

    def pick_provider_overlay_target_from_overlays(
        self,
        mouse_pos,
        radius_px=plan_selection_picking._PROVIDER_OVERLAY_PICK_RADIUS_PX,
    ):
        with plan_selection_picking._perf_trace_span(
            self.session,
            "pick_provider_overlay_target_from_overlays",
            mouse_pos=mouse_pos,
            radius_px=radius_px,
        ):
            if not self.session.view or not mouse_pos:
                return plan_target_kinds.make_plan_target_ref()
            try:
                cursor_x = float(mouse_pos[0])
                cursor_y = float(mouse_pos[1])
            except Exception:
                return plan_target_kinds.make_plan_target_ref()

            overlays = plan_selection_picking._get_visible_provider_overlays(
                self.session
            )
            if overlays is None:
                return plan_target_kinds.make_plan_target_ref()

            best_distance_sq = None
            best_target_ref = plan_target_kinds.make_plan_target_ref()
            debug_candidates = []
            for overlay in overlays:
                points = tuple(getattr(overlay, "points", ()) or ())
                targets = tuple(getattr(overlay, "point_targets", ()) or ())
                for index, point in enumerate(points):
                    target = targets[index] if index < len(targets) else None
                    candidate, debug_candidate = (
                        plan_selection_picking._evaluate_provider_overlay_point_candidate(
                            self.session,
                            overlay,
                            target,
                            point,
                            point_index=index,
                            cursor_x=cursor_x,
                            cursor_y=cursor_y,
                            mouse_pos=mouse_pos,
                            fallback_radius_px=radius_px,
                        )
                    )
                    if debug_candidate is not None:
                        plan_selection_picking._append_pick_debug_item(
                            debug_candidates, debug_candidate.as_debug_dict()
                        )
                    if candidate is None:
                        continue
                    distance_sq = candidate.distance_sq
                    if best_distance_sq is None or distance_sq < best_distance_sq:
                        best_distance_sq = distance_sq
                        best_target_ref = candidate.target_ref
            plan_selection_picking._perf_set_fields(
                self.session,
                provider_overlay_pick_result=plan_selection_picking._describe_pick_object(
                    self.session, best_target_ref.obj
                ),
            )
            plan_selection_picking._emit_pick_debug(
                self.session,
                "pick_provider_overlay_target_from_overlays",
                mouse_pos=mouse_pos,
                fallback_radius_px=radius_px,
                candidates=debug_candidates,
                result=plan_selection_picking._describe_pick_target(
                    self.session,
                    best_target_ref.kind,
                    best_target_ref.obj,
                ),
            )
            return best_target_ref

    def pick_provider_overlay_target_from_objects_info(self, mouse_pos):
        with plan_selection_picking._perf_trace_span(
            self.session,
            "pick_provider_overlay_target_from_objects_info",
            mouse_pos=mouse_pos,
        ):
            if not self.session.view or not mouse_pos:
                return plan_target_kinds.make_plan_target_ref()
            try:
                infos = self.session.view.getObjectsInfo(
                    (int(mouse_pos[0]), int(mouse_pos[1]))
                )
            except (AttributeError, ReferenceError, RuntimeError):
                return plan_target_kinds.make_plan_target_ref()
            if not infos:
                return plan_target_kinds.make_plan_target_ref()

            visible_targets = (
                plan_selection_picking._collect_visible_provider_overlay_targets(
                    self.session
                )
            )
            if not visible_targets:
                plan_selection_picking._emit_pick_debug(
                    self.session,
                    "pick_provider_overlay_target_from_objects_info",
                    mouse_pos=mouse_pos,
                    objects_info=[
                        plan_selection_picking._describe_pick_info_entry(info)
                        for info in infos
                    ],
                    visible_targets=[],
                    result=None,
                )
                return plan_target_kinds.make_plan_target_ref()

            pick_result = (
                plan_selection_picking._pick_provider_overlay_target_from_infos(
                    self.session,
                    infos,
                    visible_targets,
                )
            )
            debug_visible_targets = (
                plan_selection_picking._describe_visible_provider_overlay_targets(
                    visible_targets
                )
            )
            if pick_result.target_ref.obj is not None:
                plan_selection_picking._perf_set_fields(
                    self.session,
                    provider_overlay_info_pick_result=plan_selection_picking._describe_pick_object(
                        self.session, pick_result.target_ref.obj
                    ),
                )
                plan_selection_picking._emit_pick_debug(
                    self.session,
                    "pick_provider_overlay_target_from_objects_info",
                    mouse_pos=mouse_pos,
                    objects_info=list(pick_result.debug_infos),
                    visible_targets=debug_visible_targets,
                    result=plan_selection_picking._describe_pick_target(
                        self.session,
                        pick_result.target_ref.kind,
                        pick_result.target_ref.obj,
                    ),
                )
                return pick_result.target_ref
            plan_selection_picking._emit_pick_debug(
                self.session,
                "pick_provider_overlay_target_from_objects_info",
                mouse_pos=mouse_pos,
                objects_info=list(pick_result.debug_infos),
                visible_targets=debug_visible_targets,
                result=None,
            )
            return plan_target_kinds.make_plan_target_ref()

    def pick_plan_space_target_from_overlays(self, mouse_pos, radius_px=10):
        if not self.session.doc or not self.session.view or not mouse_pos:
            return None
        return plan_selection_picking._pick_best_target_from_overlay_segments(
            self.session,
            (
                obj
                for obj in plan_selection_picking._iter_pick_objects(
                    self.get_plan_space_instances(),
                    unique_names=True,
                )
                if self.session.selection.targets.is_plan_space_object(obj)
            ),
            self.session.overlays.geometry.get_space_overlay_segments,
            mouse_pos,
            radius_px,
        )

    def pick_plan_region_target_from_overlays(self, mouse_pos, radius_px=10):
        if not self.session.doc or not self.session.view or not mouse_pos:
            return None
        return plan_selection_picking._pick_best_target_from_overlay_segments(
            self.session,
            (
                obj
                for obj in plan_selection_picking._iter_pick_objects(
                    self.get_plan_region_instances(),
                    unique_names=True,
                )
                if self.session.selection.targets.is_plan_region_object(obj)
            ),
            self.session.overlays.geometry.get_region_overlay_segments,
            mouse_pos,
            radius_px,
        )

    def get_region_pick_polylines(self, region):
        if not self.session.selection.targets.is_plan_region_object(region):
            return []

        polylines = self.session.overlays.geometry.get_region_overlay_polylines(region)
        if polylines:
            return polylines

        points = plan_selection_picking._get_region_local_points(region)
        if len(points) < 3:
            return []

        placement = getattr(region, "Placement", None)
        if placement is not None:
            try:
                points = [
                    placement.multVec(plan_selection_picking.FreeCAD.Vector(point))
                    for point in points
                ]
            except Exception:
                points = [
                    plan_selection_picking.FreeCAD.Vector(point) for point in points
                ]
        return [points + [points[0]]]

    def pick_plan_region_target_from_polylines(self, mouse_pos):
        with plan_selection_picking._perf_trace_span(
            self.session,
            "pick_region_target_from_polylines",
            mouse_pos=mouse_pos,
        ):
            if not self.session.doc or not mouse_pos:
                return None

            point = self.session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
            if point is None:
                return None

            best_region = None
            best_area = None
            seen = set()
            for obj in self.get_plan_region_instances():
                plan_selection_picking._perf_count(
                    self.session, "region_polyline_pick_objects_scanned"
                )
                if not self.session.selection.targets.is_plan_region_object(obj):
                    continue
                name = getattr(obj, "Name", None)
                if not name or name in seen:
                    continue
                seen.add(name)
                view_object = getattr(obj, "ViewObject", None)
                if not plan_selection_picking._is_pick_visible_view_object(view_object):
                    continue

                containing_area = None
                for polyline in self.get_region_pick_polylines(obj):
                    if not self.xy_point_in_polygon(point, polyline):
                        continue
                    area = self.xy_polygon_area(polyline)
                    if area <= 0.0:
                        continue
                    if containing_area is None or area < containing_area:
                        containing_area = area

                if containing_area is None:
                    continue
                if best_area is None or containing_area < best_area:
                    best_region = obj
                    best_area = containing_area

            return best_region

    def pick_plan_target_from_footprint_faces(
        self, mouse_pos, is_target, get_faces, target_label="target"
    ):
        span_name = f"pick_{target_label}_target_from_footprints"
        with plan_selection_picking._perf_trace_span(
            self.session,
            span_name,
            mouse_pos=mouse_pos,
        ):
            if not self.session.doc or not mouse_pos:
                return None

            point = self.session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
            if point is None:
                return None

            best_target = None
            best_area = None
            seen = set()
            objects = getattr(self.session.doc, "Objects", []) or []
            if target_label == "space":
                objects = self.get_plan_space_instances()
            elif target_label == "region":
                objects = self.get_plan_region_instances()

            for obj in objects or []:
                plan_selection_picking._perf_count(
                    self.session, f"{target_label}_objects_scanned"
                )
                if not is_target(obj):
                    continue
                name = getattr(obj, "Name", None)
                if not name or name in seen:
                    continue
                seen.add(name)
                view_object = getattr(obj, "ViewObject", None)
                if not plan_selection_picking._is_pick_visible_view_object(view_object):
                    continue
                plan_selection_picking._perf_count(
                    self.session, f"{target_label}_visible_candidates"
                )

                containing_area = None
                faces = list(get_faces(obj) or [])
                plan_selection_picking._perf_count(
                    self.session, f"{target_label}_footprint_faces_returned", len(faces)
                )
                for face in faces:
                    plan_selection_picking._perf_count(
                        self.session, f"{target_label}_footprint_faces_tested"
                    )
                    bound_box = getattr(face, "BoundBox", None)
                    if bound_box is None:
                        continue
                    test_point = plan_selection_picking.FreeCAD.Vector(
                        point.x,
                        point.y,
                        float(bound_box.ZMin),
                    )
                    try:
                        if not face.isInside(test_point, 0.001, True):
                            continue
                    except Exception:
                        continue
                    area = float(getattr(face, "Area", 0.0) or 0.0)
                    if containing_area is None or area < containing_area:
                        containing_area = area

                if containing_area is None:
                    continue
                plan_selection_picking._perf_count(
                    self.session, f"{target_label}_containing_candidates"
                )
                if best_area is None or containing_area < best_area:
                    best_target = obj
                    best_area = containing_area

            plan_selection_picking._perf_set_fields(
                self.session,
                **{
                    f"{target_label}_pick_result": plan_selection_picking._describe_pick_object(
                        self.session,
                        best_target,
                    )
                },
            )
            return best_target

    def pick_plan_space_target_from_footprints(self, mouse_pos):
        return self.pick_plan_target_from_footprint_faces(
            mouse_pos,
            lambda obj: self.session.selection.targets.is_plan_space_object(obj),
            self.session.overlays.geometry.get_space_footprint_faces,
            target_label="space",
        )

    def pick_plan_region_target_from_footprints(self, mouse_pos):
        return self.pick_plan_target_from_footprint_faces(
            mouse_pos,
            lambda obj: self.session.selection.targets.is_plan_region_object(obj),
            self.session.overlays.geometry.get_region_footprint_faces,
            target_label="region",
        )

    def get_plan_target_at_position(self, mouse_pos, *, include_space_fallback=True):
        with plan_selection_picking._perf_trace_span(
            self.session,
            "get_plan_target_at_position",
            mouse_pos=mouse_pos,
        ):
            if not self.session.view or not mouse_pos:
                return plan_target_kinds.make_plan_target_ref()
            prioritize_provider_targets = (
                plan_selection_picking._should_prioritize_provider_targets_for_mode(
                    self.session
                )
            )
            infos = plan_selection_picking._get_view_objects_info(
                self.session, mouse_pos
            )
            plan_selection_picking._perf_count(
                self.session, "objects_info_entries", len(infos)
            )

            stage_result = (
                plan_selection_picking._collect_pick_candidates_from_objects_info(
                    self.session,
                    infos,
                )
            )
            result = stage_result.direct_result
            candidates = stage_result.candidates
            debug_infos = list(stage_result.debug_infos)
            resolution_stage = "objects_info_direct" if result.kind is not None else ""
            if result.kind is None:
                resolution = self._resolve_pick_target_from_overlay_stages(
                    mouse_pos,
                    candidates,
                    prioritize_provider_targets=prioritize_provider_targets,
                    include_space_fallback=include_space_fallback,
                )
                result = resolution.target_ref
                resolution_stage = resolution.stage
            plan_selection_picking._perf_set_fields(
                self.session,
                picked_target=plan_selection_picking._describe_pick_target(
                    self.session,
                    result.kind,
                    result.obj,
                ),
            )
            plan_selection_picking._emit_pick_debug(
                self.session,
                "get_plan_target_at_position",
                mouse_pos=mouse_pos,
                overlay_mode=plan_selection_picking._get_plan_provider_overlay_pick_mode(
                    self.session
                ),
                prioritize_provider_targets=prioritize_provider_targets,
                include_space_fallback=bool(include_space_fallback),
                objects_info=debug_infos,
                candidates=candidates.as_debug_dict(self.session),
                resolution_stage=resolution_stage,
                result=plan_selection_picking._describe_pick_target(
                    self.session,
                    result.kind,
                    result.obj,
                ),
            )
            return plan_target_kinds.coerce_plan_target_ref(result)

    def _resolve_pick_target_from_overlay_stages(
        self,
        mouse_pos,
        candidates,
        *,
        prioritize_provider_targets,
        include_space_fallback,
    ):
        result = self._resolve_overlay_priority_target(
            mouse_pos,
            candidates,
            prioritize_provider_targets,
        )
        if result.target_ref.kind is not None:
            return result
        return self._resolve_region_or_space_fallback_target(
            mouse_pos,
            candidates,
            include_space_fallback=include_space_fallback,
        )

    def _resolve_overlay_priority_target(
        self,
        mouse_pos,
        candidates,
        prioritize_provider_targets,
    ):
        result = self._resolve_provider_overlay_priority_target(
            mouse_pos,
            candidates,
            prioritize_provider_targets,
        )
        if result.target_ref.kind is not None:
            return result
        return self._resolve_structural_overlay_priority_target(mouse_pos, candidates)

    def _resolve_provider_overlay_priority_target(
        self,
        mouse_pos,
        candidates,
        prioritize_provider_targets,
    ):
        if candidates.provider.obj is None:
            provider_overlay_target = (
                plan_selection_picking._call_external_selection_pick(
                    self.session,
                    "pick_provider_overlay_target_from_overlays",
                    mouse_pos,
                    radius_px=plan_selection_picking._PROVIDER_OVERLAY_PICK_RADIUS_PX,
                    default=plan_selection_picking._EXTERNAL_PICK_MISSING,
                )
            )
            if provider_overlay_target is plan_selection_picking._EXTERNAL_PICK_MISSING:
                provider_overlay_target = self.pick_provider_overlay_target_from_overlays(
                    mouse_pos,
                    radius_px=plan_selection_picking._PROVIDER_OVERLAY_PICK_RADIUS_PX,
                )
            provider_overlay_target = plan_target_kinds.coerce_plan_target_ref(
                provider_overlay_target
            )
            if (
                provider_overlay_target.kind == "provider"
                and provider_overlay_target.obj is not None
            ):
                candidates.provider = provider_overlay_target
        if prioritize_provider_targets and candidates.provider.obj is not None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "provider",
                    candidates.provider.obj,
                ),
                stage="provider_overlay_priority",
            )
        return plan_selection_picking._PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref()
        )

    def _resolve_structural_overlay_priority_target(self, mouse_pos, candidates):
        if candidates.symbol.obj is not None and candidates.wall.obj is None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "symbol", candidates.symbol.obj
                ),
                stage="symbol_priority_without_wall",
            )

        result = self._resolve_opening_overlay_priority_target(mouse_pos, candidates)
        if result.target_ref.kind is not None:
            return result
        return self._resolve_symbol_or_terminal_overlay_target(mouse_pos, candidates)

    def _resolve_opening_overlay_priority_target(self, mouse_pos, candidates):
        opening_candidates = None
        if candidates.wall.obj is not None:
            opening_candidates = self.session.openings.get_wall_hosted_openings(
                candidates.wall.obj
            )
        opening_candidate = plan_selection_picking._call_external_selection_pick(
            self.session,
            "pick_plan_opening_target_from_overlays",
            mouse_pos,
            candidates=opening_candidates,
            default=plan_selection_picking._EXTERNAL_PICK_MISSING,
        )
        if opening_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
            opening_candidate = self.pick_plan_opening_target_from_overlays(
                mouse_pos,
                candidates=opening_candidates,
            )
        if opening_candidate is None and opening_candidates is not None:
            opening_candidate = plan_selection_picking._call_external_selection_pick(
                self.session,
                "pick_plan_opening_target_from_overlays",
                mouse_pos,
                candidates=None,
                default=plan_selection_picking._EXTERNAL_PICK_MISSING,
            )
            if opening_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
                opening_candidate = self.pick_plan_opening_target_from_overlays(
                    mouse_pos
                )
        if opening_candidate is not None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "opening", opening_candidate
                ),
                stage="opening_overlay_priority",
            )
        return plan_selection_picking._PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref()
        )

    def _resolve_symbol_or_terminal_overlay_target(self, mouse_pos, candidates):
        if candidates.symbol.obj is None:
            symbol_candidate = plan_selection_picking._call_external_selection_pick(
                self.session,
                "pick_plan_symbol_target_from_overlays",
                mouse_pos,
                default=plan_selection_picking._EXTERNAL_PICK_MISSING,
            )
            if symbol_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
                symbol_candidate = self.pick_plan_symbol_target_from_overlays(mouse_pos)
            candidates.store_if_empty("symbol", symbol_candidate)
        if candidates.symbol.obj is not None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "symbol", candidates.symbol.obj
                ),
                stage="symbol_overlay_or_direct",
            )
        if candidates.wall.obj is not None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "wall", candidates.wall.obj
                ),
                stage="wall_terminal",
            )
        if candidates.provider.obj is not None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "provider",
                    candidates.provider.obj,
                ),
                stage="provider_terminal",
            )
        return plan_selection_picking._PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref()
        )

    def _resolve_region_or_space_fallback_target(
        self,
        mouse_pos,
        candidates,
        *,
        include_space_fallback,
    ):
        result = self._resolve_region_fallback_target(mouse_pos, candidates)
        if result.target_ref.kind is not None:
            return result
        return self._resolve_space_fallback_target(
            mouse_pos,
            candidates,
            include_space_fallback=include_space_fallback,
        )

    def _resolve_region_fallback_target(self, mouse_pos, candidates):
        if candidates.region.obj is None:
            region_candidate = plan_selection_picking._call_external_selection_pick(
                self.session,
                "pick_plan_region_target_from_polylines",
                mouse_pos,
                default=plan_selection_picking._EXTERNAL_PICK_MISSING,
            )
            if region_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
                region_candidate = self.pick_plan_region_target_from_polylines(
                    mouse_pos
                )
            candidates.store_if_empty("region", region_candidate)
        if candidates.region.obj is None:
            region_candidate = plan_selection_picking._call_external_selection_pick(
                self.session,
                "pick_plan_region_target_from_footprints",
                mouse_pos,
                default=plan_selection_picking._EXTERNAL_PICK_MISSING,
            )
            if region_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
                region_candidate = self.pick_plan_region_target_from_footprints(
                    mouse_pos
                )
            candidates.store_if_empty("region", region_candidate)
        if candidates.region.obj is None:
            region_candidate = plan_selection_picking._call_external_selection_pick(
                self.session,
                "pick_plan_region_target_from_overlays",
                mouse_pos,
                default=plan_selection_picking._EXTERNAL_PICK_MISSING,
            )
            if region_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
                region_candidate = self.pick_plan_region_target_from_overlays(mouse_pos)
            candidates.store_if_empty("region", region_candidate)
        if candidates.region.obj is not None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "region", candidates.region.obj
                ),
                stage="region_fallback",
            )
        return plan_selection_picking._PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref()
        )

    def _resolve_space_fallback_target(
        self,
        mouse_pos,
        candidates,
        *,
        include_space_fallback,
    ):
        if not include_space_fallback:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref()
            )
        if candidates.space.obj is None:
            space_candidate = plan_selection_picking._call_external_selection_pick(
                self.session,
                "pick_plan_space_target_from_footprints",
                mouse_pos,
                default=plan_selection_picking._EXTERNAL_PICK_MISSING,
            )
            if space_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
                space_candidate = self.pick_plan_space_target_from_footprints(mouse_pos)
            candidates.store_if_empty("space", space_candidate)
        if candidates.space.obj is None:
            space_candidate = plan_selection_picking._call_external_selection_pick(
                self.session,
                "pick_plan_space_target_from_overlays",
                mouse_pos,
                default=plan_selection_picking._EXTERNAL_PICK_MISSING,
            )
            if space_candidate is plan_selection_picking._EXTERNAL_PICK_MISSING:
                space_candidate = self.pick_plan_space_target_from_overlays(mouse_pos)
            candidates.store_if_empty("space", space_candidate)
        if candidates.space.obj is not None:
            return plan_selection_picking._PickResolutionResult(
                target_ref=plan_target_kinds.make_plan_target_ref(
                    "space", candidates.space.obj
                ),
                stage="space_fallback",
            )
        return plan_selection_picking._PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref()
        )

    def get_edit_node(self, mouse_pos):
        node = plan_selection_picking._get_selected_handle_edit_node(
            self.session, mouse_pos
        )
        if node is not None:
            return node
        node = plan_selection_picking._get_provider_overlay_edit_node(
            self.session, mouse_pos
        )
        if node is not None:
            return node
        return plan_selection_picking._get_ray_picked_edit_node(self.session, mouse_pos)

    def pick_selected_opening_handle(self, mouse_pos, radius_px=10):
        opening = self.session.selection.state.get_selected_plan_target_object(
            "opening"
        )
        if (
            not self.session.openings.is_hosted_opening_object(opening)
            or not self.session.view
        ):
            return None
        try:
            cursor_x = int(mouse_pos[0])
            cursor_y = int(mouse_pos[1])
        except Exception:
            return None
        best_index = None
        best_distance_sq = None
        for (
            idx,
            _role,
            point,
            _marker,
        ) in self.session.overlays.openings.get_selected_opening_handle_specs(opening):
            try:
                screen_x, screen_y = self.session.view.getPointOnScreen(point)
            except Exception:
                continue
            dx = float(screen_x) - float(cursor_x)
            dy = float(screen_y) - float(cursor_y)
            distance_sq = dx * dx + dy * dy
            if distance_sq > radius_px * radius_px:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_index = idx
                best_distance_sq = distance_sq
        return best_index


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
        previous_kind, previous_obj = (
            self.session.selection.state.get_selected_plan_target()
        )
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
                self.session.selection.picking.get_plan_target_at_position(mouse_pos)
            )
        else:
            target_ref = plan_target_kinds.coerce_plan_target_ref(resolved_target)
        with self.session.performance.plan_perf_trace_span(
            f"activate_plan_target_{kind}", requested_kind=kind, mouse_pos=mouse_pos
        ):
            self.session.performance.plan_perf_count(
                f"activate_plan_target_attempts_{kind}"
            )
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
                self.session.performance.plan_perf_set_fields(
                    activate_plan_target_result=False
                )
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
                self.session.selection.picking.get_plan_target_at_position(mouse_pos)
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
                    hovered_target=perf.plan_perf_describe_target(
                        target_ref.kind, target_ref.obj
                    ),
                )
        if (
            plan_selection_activation._get_target_activation_behavior(target_ref.kind)
            is None
        ):
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

    def activate_opening_target(
        self, mouse_pos, event_callback=None, resolved_target=None
    ):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_OPENING,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def activate_symbol_target(
        self, mouse_pos, event_callback=None, resolved_target=None
    ):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_SYMBOL,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def activate_region_target(
        self, mouse_pos, event_callback=None, resolved_target=None
    ):
        return self.activate_plan_target_for_kind(
            plan_target_kinds.PLAN_TARGET_REGION,
            mouse_pos,
            event_callback=event_callback,
            resolved_target=resolved_target,
        )

    def activate_space_target(
        self, mouse_pos, event_callback=None, resolved_target=None
    ):
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
        previous_kind, previous_obj = (
            self.session.selection.state.get_selected_plan_target()
        )
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
            with self.session.performance.plan_perf_trace_span(
                "clear_plan_selection_target_state"
            ):
                self.session.selection.state.set_selected_plan_target()
                self.session.provider_transient_state.provider_selected_objects = []
            with self.session.performance.plan_perf_trace_span(
                "clear_plan_selection_hover_state"
            ):
                plan_target_dispatch.clear_hovered_targets(self.session)
            with self.session.performance.plan_perf_trace_span(
                "clear_plan_selection_wall_grips"
            ):
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
            with self.session.performance.plan_perf_trace_span(
                "clear_plan_selection_task_status"
            ):
                self.session.task_panels.refresh_task_panel_status(
                    reason=(
                        "selection"
                        if self.session.current_tool
                        == plan_runtime_tools.PlanTool.SELECT
                        else "full"
                    )
                )
            selected_kind, selected_obj = (
                self.session.selection.state.get_selected_plan_target()
            )
            self.session.performance.plan_perf_set_fields(
                clear_selection_ended_kind=selected_kind or "none",
                clear_selection_ended_target=self.session.performance.plan_perf_describe_target(
                    selected_kind, selected_obj
                ),
                clear_selection_cleared_wall=bool(
                    previous_kind == "wall" and not selected_kind
                ),
            )

    def activate_provider_overlay_target_node(self, node, event_callback=None):
        target_ref = plan_target_kinds.coerce_plan_target_ref(
            self.session.selection.picking.get_provider_overlay_target_from_edit_node(
                node
            )
        )
        if target_ref.obj is None:
            return False
        if self.session.selection.state.is_valid_plan_target(
            target_ref.kind, target_ref.obj
        ):
            self.session.provider_transient_state.provider_selected_objects = []
            self.session.selection.state.set_pending_selected_plan_target(target_ref)
        else:
            self.session.provider_transient_state.provider_selected_objects = [
                target_ref.obj
            ]
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
            provider_selection = [
                selected for selected in provider_selection if selected != obj
            ]
        else:
            provider_selection.append(obj)
        self.session.provider_transient_state.provider_selected_objects = (
            self.session.selection.sync.normalize_gui_object_selection(
                provider_selection
            )
        )
        new_selection = self.session.selection.sync.normalize_gui_object_selection(
            [
                selected
                for selected in selection
                if self.session.selection.targets.get_plan_target_for_object(
                    selected
                ).kind
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
        node = self.session.selection.picking.get_edit_node(mouse_pos)
        if plan_edit_nodes.get_edit_node_kind(node) in (
            "provider_overlay_point",
            "provider_overlay_target",
        ):
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.selection.picking.get_provider_overlay_target_from_edit_node(
                    node
                )
            )
            if (
                target_ref.obj is not None
                and not self.session.selection.state.is_valid_plan_target(
                    target_ref.kind,
                    target_ref.obj,
                )
            ):
                return self.toggle_raw_plan_object_selection(
                    target_ref.obj, event_callback
                )
        else:
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.selection.picking.get_plan_target_from_edit_node(node)
            )
        if target_ref.kind is None:
            target_ref = plan_target_kinds.coerce_plan_target_ref(
                self.session.selection.picking.get_plan_target_at_position(mouse_pos)
            )
        if not target_ref.kind or not target_ref.obj:
            return False

        primary_kind, primary_obj, selection = (
            plan_selection_activation._get_current_additive_gui_selection(self.session)
        )

        was_selected = target_ref.obj in selection
        if was_selected:
            new_selection = [
                selected for selected in selection if selected != target_ref.obj
            ]
            fallback_target = None if primary_obj == target_ref.obj else target_ref
            next_kind, next_obj = (
                plan_selection_activation._resolve_next_selected_target(
                    self.session,
                    new_selection,
                    primary_kind,
                    primary_obj,
                    fallback_target=fallback_target,
                )
            )
        else:
            new_selection = list(selection)
            new_selection.append(target_ref.obj)
            next_kind, next_obj = (
                plan_selection_activation._resolve_next_selected_target(
                    self.session,
                    new_selection,
                    primary_kind,
                    primary_obj,
                    fallback_target=target_ref,
                )
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
