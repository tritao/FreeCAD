# SPDX-License-Identifier: LGPL-2.1-or-later

"""Owned overlay API surface for BIM Plan Edit."""

from bimplan import document_visuals as plan_document_visuals
from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import manager as overlay_manager
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import providers as provider_overlays
from bimplan.overlays import spaces as space_overlays
from bimplan.overlays import symbols as symbol_overlays
from bimplan.overlays import walls as wall_overlays

_PLAN_VIEW_SCALE_REFRESH_DELAY_MS = 40


def _queue_plan_overlay_visual_refresh(session, *visuals):
    return overlay_manager.queue_plan_overlay_visual_refresh(
        session,
        visuals,
        plan_document_visuals.PLAN_VISUAL_ALL,
        plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE,
    )


class _OverlayService:
    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class PlanOverlayManagerService(_OverlayService):
    finalize_trackers = staticmethod(overlay_manager.finalize_trackers)
    make_plan_line_tracker = staticmethod(overlay_manager.make_plan_line_tracker)
    set_plan_line_tracker_width = staticmethod(overlay_manager.set_plan_line_tracker_width)

    def flush_plan_overlay_visual_refresh(self, *args, **kwargs):
        return overlay_manager.flush_plan_overlay_visual_refresh(self.session, *args, **kwargs)

    def flush_view_scale_overlay_refresh(self, *args, **kwargs):
        return overlay_manager.flush_view_scale_overlay_refresh(self.session, *args, **kwargs)

    def refresh_plan_overlay_view_scale(self, *args, **kwargs):
        return overlay_manager.refresh_plan_overlay_view_scale(self.session, *args, **kwargs)

    def refresh_plan_overlay_visuals(self, *args, **kwargs):
        return overlay_manager.refresh_plan_overlay_visuals(self.session, *args, **kwargs)


class PlanOverlayGeometryService(_OverlayService):
    get_footprint_overlay_polylines = staticmethod(overlay_geometry.get_footprint_overlay_polylines)
    build_overlay_segments_from_polylines = staticmethod(
        overlay_geometry.build_overlay_segments_from_polylines
    )

    def get_plan_overlay_geometry_kinds_for_object(self, *args, **kwargs):
        return overlay_geometry.get_plan_overlay_geometry_kinds_for_object(
            self.session, *args, **kwargs
        )

    def get_plan_overlay_geometry_cache_entry(self, *args, **kwargs):
        return overlay_geometry.get_plan_overlay_geometry_cache_entry(self.session, *args, **kwargs)

    def invalidate_plan_overlay_geometry_cache(self, *args, **kwargs):
        return overlay_geometry.invalidate_plan_overlay_geometry_cache(
            self.session, *args, **kwargs
        )

    def get_cached_plan_overlay_geometry(self, *args, **kwargs):
        return overlay_geometry.get_cached_plan_overlay_geometry(self.session, *args, **kwargs)

    def get_wall_overlay_polylines(self, *args, **kwargs):
        return overlay_geometry.get_wall_overlay_polylines(self.session, *args, **kwargs)

    def get_space_footprint_faces(self, *args, **kwargs):
        return overlay_geometry.get_space_footprint_faces(self.session, *args, **kwargs)

    def get_space_overlay_polylines(self, *args, **kwargs):
        return overlay_geometry.get_space_overlay_polylines(self.session, *args, **kwargs)

    def get_space_overlay_segments(self, *args, **kwargs):
        return overlay_geometry.get_space_overlay_segments(self.session, *args, **kwargs)

    def get_region_footprint_faces(self, *args, **kwargs):
        return overlay_geometry.get_region_footprint_faces(self.session, *args, **kwargs)

    def get_region_overlay_polylines(self, *args, **kwargs):
        return overlay_geometry.get_region_overlay_polylines(self.session, *args, **kwargs)

    def get_region_overlay_segments(self, *args, **kwargs):
        return overlay_geometry.get_region_overlay_segments(self.session, *args, **kwargs)

    def get_opening_overlay_polylines(self, *args, **kwargs):
        return overlay_geometry.get_opening_overlay_polylines(self.session, *args, **kwargs)

    def get_opening_overlay_screen_polylines(self, *args, **kwargs):
        return overlay_geometry.get_opening_overlay_screen_polylines(self.session, *args, **kwargs)

    def get_opening_overlay_screen_bounds(self, *args, **kwargs):
        return overlay_geometry.get_opening_overlay_screen_bounds(self.session, *args, **kwargs)

    def get_opening_pick_bounds(self, *args, **kwargs):
        return overlay_geometry.get_opening_pick_bounds(self.session, *args, **kwargs)

    def get_opening_overlay_segments(self, *args, **kwargs):
        return overlay_geometry.get_opening_overlay_segments(self.session, *args, **kwargs)


class PlanSpaceOverlayService(_OverlayService):
    def sync_secondary_selected_overlays(self, *args, **kwargs):
        return space_overlays.sync_secondary_selected_overlays(self.session, *args, **kwargs)

    def clear_secondary_selected_overlays(self, *args, **kwargs):
        return space_overlays.clear_secondary_selected_overlays(self.session, *args, **kwargs)

    def sync_space_region_pick_overlays(self, *args, **kwargs):
        return space_overlays.sync_space_region_pick_overlays(self.session, *args, **kwargs)

    def clear_space_region_pick_overlays(self, *args, **kwargs):
        return space_overlays.clear_space_region_pick_overlays(self.session, *args, **kwargs)

    def create_space_overlay_trackers(self, *args, **kwargs):
        return space_overlays.create_space_overlay_trackers(self.session, *args, **kwargs)

    def create_region_overlay_trackers(self, *args, **kwargs):
        return space_overlays.create_region_overlay_trackers(self.session, *args, **kwargs)

    def sync_hovered_space_overlay(self, *args, **kwargs):
        return space_overlays.sync_hovered_space_overlay(self.session, *args, **kwargs)

    def clear_hovered_space_overlay(self, *args, **kwargs):
        return space_overlays.clear_hovered_space_overlay(self.session, *args, **kwargs)

    def sync_hovered_region_overlay(self, *args, **kwargs):
        return space_overlays.sync_hovered_region_overlay(self.session, *args, **kwargs)

    def clear_hovered_region_overlay(self, *args, **kwargs):
        return space_overlays.clear_hovered_region_overlay(self.session, *args, **kwargs)

    def invalidate_selected_space_overlay_cache(self, *args, **kwargs):
        return space_overlays.invalidate_selected_space_overlay_cache(self.session, *args, **kwargs)

    def sync_selected_space_overlay(self, *args, **kwargs):
        return space_overlays.sync_selected_space_overlay(self.session, *args, **kwargs)

    def clear_selected_space_overlay(self, *args, **kwargs):
        return space_overlays.clear_selected_space_overlay(self.session, *args, **kwargs)

    def sync_selected_region_overlay(self, *args, **kwargs):
        return space_overlays.sync_selected_region_overlay(self.session, *args, **kwargs)

    def clear_selected_region_overlay(self, *args, **kwargs):
        return space_overlays.clear_selected_region_overlay(self.session, *args, **kwargs)


class PlanWallOverlayService(_OverlayService):
    def retarget_edit_tracker(self, *args, **kwargs):
        return wall_overlays.retarget_edit_tracker(self.session, *args, **kwargs)

    def sync_wall_grips(self, *args, **kwargs):
        return wall_overlays.sync_wall_grips(self.session, *args, **kwargs)

    def schedule_wall_grip_sync(self, *args, **kwargs):
        return wall_overlays.schedule_wall_grip_sync(self.session, *args, **kwargs)

    def run_scheduled_wall_grip_sync(self, *args, **kwargs):
        return wall_overlays.run_scheduled_wall_grip_sync(self.session, *args, **kwargs)

    def clear_wall_grips(self, *args, **kwargs):
        return wall_overlays.clear_wall_grips(self.session, *args, **kwargs)

    def sync_hovered_wall_overlay(self, *args, **kwargs):
        return wall_overlays.sync_hovered_wall_overlay(self.session, *args, **kwargs)

    def clear_hovered_wall_overlay(self, *args, **kwargs):
        return wall_overlays.clear_hovered_wall_overlay(self.session, *args, **kwargs)

    def sync_selected_wall_overlay(self, *args, **kwargs):
        return wall_overlays.sync_selected_wall_overlay(self.session, *args, **kwargs)

    def clear_selected_wall_overlay(self, *args, **kwargs):
        return wall_overlays.clear_selected_wall_overlay(self.session, *args, **kwargs)

    def apply_selected_wall_selection_feedback(self, *args, **kwargs):
        return wall_overlays.apply_selected_wall_selection_feedback(self.session, *args, **kwargs)

    def get_plan_context_junctions(self, *args, **kwargs):
        return wall_overlays.get_plan_context_junctions(self.session, *args, **kwargs)

    def create_junction_node_trackers(self, *args, **kwargs):
        return wall_overlays.create_junction_node_trackers(self.session, *args, **kwargs)

    def sync_junction_node_overlays(self, *args, **kwargs):
        return wall_overlays.sync_junction_node_overlays(self.session, *args, **kwargs)

    def clear_junction_node_overlays(self, *args, **kwargs):
        return wall_overlays.clear_junction_node_overlays(self.session, *args, **kwargs)

    def sync_hovered_wall_opening_context_overlay(self, *args, **kwargs):
        return wall_overlays.sync_hovered_wall_opening_context_overlay(
            self.session, *args, **kwargs
        )

    def clear_hovered_wall_opening_context_overlay(self, *args, **kwargs):
        return wall_overlays.clear_hovered_wall_opening_context_overlay(
            self.session, *args, **kwargs
        )

    def create_wall_overlay_trackers(self, *args, **kwargs):
        return wall_overlays.create_wall_overlay_trackers(self.session, *args, **kwargs)


class PlanProviderOverlayService(_OverlayService):
    def sync_provider_overlays(self, *args, **kwargs):
        return provider_overlays.sync_provider_overlays(self.session, *args, **kwargs)

    def clear_provider_overlays(self, *args, **kwargs):
        return provider_overlays.clear_provider_overlays(self.session, *args, **kwargs)

    def sync_hovered_provider_overlay(self, *args, **kwargs):
        return provider_overlays.sync_hovered_provider_overlay(self.session, *args, **kwargs)

    def clear_hovered_provider_overlay(self, *args, **kwargs):
        return provider_overlays.clear_hovered_provider_overlay(self.session, *args, **kwargs)

    def sync_selected_provider_overlay(self, *args, **kwargs):
        return provider_overlays.sync_selected_provider_overlay(self.session, *args, **kwargs)

    def clear_selected_provider_overlay(self, *args, **kwargs):
        return provider_overlays.clear_selected_provider_overlay(self.session, *args, **kwargs)

    def get_selected_provider_handle_specs(self, *args, **kwargs):
        return provider_overlays.get_selected_provider_handle_specs(self.session, *args, **kwargs)

    def sync_selected_provider_handles(self, *args, **kwargs):
        return provider_overlays.sync_selected_provider_handles(self.session, *args, **kwargs)

    def clear_selected_provider_handles(self, *args, **kwargs):
        return provider_overlays.clear_selected_provider_handles(self.session, *args, **kwargs)

    def pick_selected_provider_handle(self, *args, **kwargs):
        return provider_overlays.pick_selected_provider_handle(self.session, *args, **kwargs)

    def sync_provider_point_preview(self, *args, **kwargs):
        return provider_overlays.sync_provider_point_preview(self.session, *args, **kwargs)

    def clear_provider_point_preview(self, *args, **kwargs):
        return provider_overlays.clear_provider_point_preview(self.session, *args, **kwargs)


class PlanOpeningOverlayService(_OverlayService):
    def get_opening_handle_markers(self, *args, **kwargs):
        return opening_overlays.get_opening_handle_markers(self.session, *args, **kwargs)

    def set_opening_handle_tracker_marker(self, *args, **kwargs):
        return opening_overlays.set_opening_handle_tracker_marker(self.session, *args, **kwargs)

    def discard_opening_handle_tracker_pool(self, *args, **kwargs):
        return opening_overlays.discard_opening_handle_tracker_pool(self.session, *args, **kwargs)

    def queue_prime_opening_handle_tracker_pool(self, *args, **kwargs):
        return opening_overlays.queue_prime_opening_handle_tracker_pool(
            self.session, *args, **kwargs
        )

    def prime_opening_handle_tracker_pool(self, *args, **kwargs):
        return opening_overlays.prime_opening_handle_tracker_pool(self.session, *args, **kwargs)

    def sync_hovered_opening_overlay(self, *args, **kwargs):
        return opening_overlays.sync_hovered_opening_overlay(self.session, *args, **kwargs)

    def clear_hovered_opening_overlay(self, *args, **kwargs):
        return opening_overlays.clear_hovered_opening_overlay(self.session, *args, **kwargs)

    def invalidate_hovered_opening_overlay_cache(self, *args, **kwargs):
        return opening_overlays.invalidate_hovered_opening_overlay_cache(
            self.session, *args, **kwargs
        )

    def create_opening_overlay_trackers(self, *args, **kwargs):
        return opening_overlays.create_opening_overlay_trackers(self.session, *args, **kwargs)

    def sync_selected_opening_overlay(self, *args, **kwargs):
        return opening_overlays.sync_selected_opening_overlay(self.session, *args, **kwargs)

    def clear_selected_opening_overlay(self, *args, **kwargs):
        return opening_overlays.clear_selected_opening_overlay(self.session, *args, **kwargs)

    def invalidate_selected_opening_overlay_cache(self, *args, **kwargs):
        return opening_overlays.invalidate_selected_opening_overlay_cache(
            self.session, *args, **kwargs
        )

    def sync_selected_wall_opening_context_overlay(self, *args, **kwargs):
        return opening_overlays.sync_selected_wall_opening_context_overlay(
            self.session, *args, **kwargs
        )

    def clear_selected_wall_opening_context_overlay(self, *args, **kwargs):
        return opening_overlays.clear_selected_wall_opening_context_overlay(
            self.session, *args, **kwargs
        )

    def get_selected_opening_handle_specs(self, *args, **kwargs):
        return opening_overlays.get_selected_opening_handle_specs(self.session, *args, **kwargs)

    def sync_selected_opening_handles(self, *args, **kwargs):
        return opening_overlays.sync_selected_opening_handles(self.session, *args, **kwargs)

    def clear_selected_opening_handles(self, *args, **kwargs):
        return opening_overlays.clear_selected_opening_handles(self.session, *args, **kwargs)


class PlanSymbolOverlayService(_OverlayService):
    def clear_symbol_edit_preview(self, *args, **kwargs):
        return symbol_overlays.clear_symbol_edit_preview(self.session, *args, **kwargs)

    def get_plan_symbol_instances(self, *args, **kwargs):
        return symbol_overlays.get_plan_symbol_instances(self.session, *args, **kwargs)

    def get_symbol_global_placement(self, *args, **kwargs):
        return symbol_overlays.get_symbol_global_placement(self.session, *args, **kwargs)

    def get_symbol_parent_global_placement(self, *args, **kwargs):
        return symbol_overlays.get_symbol_parent_global_placement(self.session, *args, **kwargs)

    def get_symbol_plan_proxy(self, *args, **kwargs):
        return symbol_overlays.get_symbol_plan_proxy(self.session, *args, **kwargs)

    def get_symbol_semantic_proxy(self, *args, **kwargs):
        return symbol_overlays.get_symbol_semantic_proxy(self.session, *args, **kwargs)

    def get_symbol_overlay_polylines(self, *args, **kwargs):
        return symbol_overlays.get_symbol_overlay_polylines(self.session, *args, **kwargs)

    def get_symbol_overlay_segments(self, *args, **kwargs):
        return symbol_overlays.get_symbol_overlay_segments(self.session, *args, **kwargs)

    def get_symbol_overlay_screen_polylines(self, *args, **kwargs):
        return symbol_overlays.get_symbol_overlay_screen_polylines(self.session, *args, **kwargs)

    def get_symbol_overlay_screen_bounds(self, *args, **kwargs):
        return symbol_overlays.get_symbol_overlay_screen_bounds(self.session, *args, **kwargs)

    def refresh_selected_symbol_visuals(self, *args, **kwargs):
        return symbol_overlays.refresh_selected_symbol_visuals(self.session, *args, **kwargs)

    def create_symbol_overlay_trackers(self, *args, **kwargs):
        return symbol_overlays.create_symbol_overlay_trackers(self.session, *args, **kwargs)

    def sync_hovered_symbol_overlay(self, *args, **kwargs):
        return symbol_overlays.sync_hovered_symbol_overlay(self.session, *args, **kwargs)

    def clear_hovered_symbol_overlay(self, *args, **kwargs):
        return symbol_overlays.clear_hovered_symbol_overlay(self.session, *args, **kwargs)

    def sync_selected_symbol_overlay(self, *args, **kwargs):
        return symbol_overlays.sync_selected_symbol_overlay(self.session, *args, **kwargs)

    def clear_selected_symbol_overlay(self, *args, **kwargs):
        return symbol_overlays.clear_selected_symbol_overlay(self.session, *args, **kwargs)

    def get_symbol_rotation_snap_increment_degrees(self, *args, **kwargs):
        return symbol_overlays.get_symbol_rotation_snap_increment_degrees(
            self.session, *args, **kwargs
        )

    def get_symbol_rotation_snap_step_radians(self, *args, **kwargs):
        return symbol_overlays.get_symbol_rotation_snap_step_radians(self.session, *args, **kwargs)

    def symbol_rotation_free_angle_override_active(self, *args, **kwargs):
        return symbol_overlays.symbol_rotation_free_angle_override_active(
            self.session, *args, **kwargs
        )

    def resolve_symbol_handle_target_point(self, *args, **kwargs):
        return symbol_overlays.resolve_symbol_handle_target_point(self.session, *args, **kwargs)

    def get_symbol_handle_radius(self, *args, **kwargs):
        return symbol_overlays.get_symbol_handle_radius(self.session, *args, **kwargs)

    def get_selected_symbol_handle_specs(self, *args, **kwargs):
        return symbol_overlays.get_selected_symbol_handle_specs(self.session, *args, **kwargs)

    def get_symbol_anchor_point(self, *args, **kwargs):
        return symbol_overlays.get_symbol_anchor_point(self.session, *args, **kwargs)

    def get_symbol_facing_vector(self, *args, **kwargs):
        return symbol_overlays.get_symbol_facing_vector(self.session, *args, **kwargs)

    def sync_selected_symbol_handles(self, *args, **kwargs):
        return symbol_overlays.sync_selected_symbol_handles(self.session, *args, **kwargs)

    def clear_selected_symbol_handles(self, *args, **kwargs):
        return symbol_overlays.clear_selected_symbol_handles(self.session, *args, **kwargs)

    def sync_symbol_edit_preview(self, *args, **kwargs):
        return symbol_overlays.sync_symbol_edit_preview(self.session, *args, **kwargs)

    def pick_selected_symbol_handle(self, *args, **kwargs):
        return symbol_overlays.pick_selected_symbol_handle(self.session, *args, **kwargs)

    def get_symbol_local_anchor(self, *args, **kwargs):
        return symbol_overlays.get_symbol_local_anchor(self.session, *args, **kwargs)

    def get_symbol_local_facing(self, *args, **kwargs):
        return symbol_overlays.get_symbol_local_facing(self.session, *args, **kwargs)

    def is_symbol_visual_dependency(self, symbol, obj):
        if not self.session.visibility.is_plan_symbol_instance(symbol) or not obj:
            return False
        if obj == symbol:
            return True
        semantic_obj = self.session.visibility.get_plan_semantic_object(symbol)
        if obj == semantic_obj:
            return True
        if obj == getattr(semantic_obj, "Base", None):
            return True
        return obj in (getattr(semantic_obj, "PlanSymbols", None) or [])

    def refresh_target_document_visual_dependency(self, symbol, obj, prop):
        if not (
            self.is_symbol_visual_dependency(symbol, obj)
            and prop in plan_document_visuals.SYMBOL_VISUAL_PROPERTIES
        ):
            return False
        plan_document_visuals.refresh_plan_object_footprint_display(self.session, symbol)
        return True

    def refresh_symbol_visual_footprint(self, symbol):
        if symbol is None:
            return False
        plan_document_visuals.refresh_plan_object_footprint_display(self.session, symbol)
        return True

    def handle_document_visual_dependency_change(self, obj, prop):
        selected_symbol = self.session.selection.state.get_selected_plan_target_object("symbol")
        if self.refresh_target_document_visual_dependency(selected_symbol, obj, prop):
            _queue_plan_overlay_visual_refresh(
                self.session, plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL
            )
            return True
        hovered_symbol = self.session.hovered_symbol
        if (
            hovered_symbol
            and not self.session.selection.state.is_selected_plan_target("symbol", hovered_symbol)
            and self.refresh_target_document_visual_dependency(hovered_symbol, obj, prop)
        ):
            _queue_plan_overlay_visual_refresh(
                self.session, plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL
            )
            return True
        return False

    def handle_deleted_visual_target(self, obj):
        if obj == self.session.hovered_symbol:
            self.session.hovered_symbol = None
            self.clear_hovered_symbol_overlay()
        if self.session.selection.refresh.clear_selected_plan_target_if_matches("symbol", obj):
            self.refresh_selected_symbol_visuals()
            return True
        return False

    def refresh_document_dependent_visuals(self):
        visuals = []
        selected_symbol = self.session.selection.state.get_selected_plan_target_object("symbol")
        if self.refresh_symbol_visual_footprint(selected_symbol):
            visuals.append(plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL)
        hovered_symbol = self.session.hovered_symbol
        if (
            hovered_symbol
            and not self.session.selection.state.is_selected_plan_target("symbol", hovered_symbol)
            and self.refresh_symbol_visual_footprint(hovered_symbol)
        ):
            visuals.append(plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL)
        return tuple(visuals)


class PlanOverlaysAPI:
    """Owned session surface for BIM Plan Edit overlay behavior."""

    def __init__(self, session):
        self._session = session
        self.manager = PlanOverlayManagerService(session)
        self.geometry = PlanOverlayGeometryService(session)
        self.spaces = PlanSpaceOverlayService(session)
        self.walls = PlanWallOverlayService(session)
        self.providers = PlanProviderOverlayService(session)
        self.openings = PlanOpeningOverlayService(session)
        self.symbols = PlanSymbolOverlayService(session)

    @property
    def session(self):
        return self._session

    def queue_plan_overlay_visual_refresh(self, *visuals):
        return _queue_plan_overlay_visual_refresh(self.session, *visuals)

    def discard_runtime_references(self):
        tracker_state = self.session.overlay_tracker_state
        tracker_state.junction_node_trackers = []
        tracker_state.space_region_pick_trackers = []

    def queue_plan_overlay_view_scale_refresh(
        self,
        delay_ms=_PLAN_VIEW_SCALE_REFRESH_DELAY_MS,
    ):
        return overlay_manager.queue_plan_overlay_view_scale_refresh(
            self.session,
            plan_document_visuals.PLAN_VISUAL_VIEW_SCALE,
            delay_ms,
        )

    def consume_dirty_plan_visuals(self, default_all=True):
        return overlay_manager.consume_dirty_plan_visuals(
            self.session,
            plan_document_visuals.PLAN_VISUAL_ALL,
            default_all=default_all,
        )
