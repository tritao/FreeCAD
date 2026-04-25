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


class PlanOverlaysAPI:
    """Owned session surface for Plan Edit overlay behavior."""

    __slots__ = ("_session", "__dict__")

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def queue_plan_overlay_visual_refresh(self, *visuals):
        return overlay_manager.queue_plan_overlay_visual_refresh(
            self.session,
            visuals,
            plan_document_visuals.PLAN_VISUAL_ALL,
            plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE,
        )

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

    def flush_plan_overlay_visual_refresh(self):
        return overlay_manager.flush_plan_overlay_visual_refresh(self.session)

    def flush_view_scale_overlay_refresh(self):
        return overlay_manager.flush_view_scale_overlay_refresh(self.session)

    def refresh_plan_overlay_view_scale(self):
        return overlay_manager.refresh_plan_overlay_view_scale(self.session)

    def refresh_plan_overlay_visuals(self, dirty=None):
        return overlay_manager.refresh_plan_overlay_visuals(self.session, dirty=dirty)

    def finalize_trackers(self, *args, **kwargs):
        return overlay_manager.finalize_trackers(*args, **kwargs)

    def make_plan_line_tracker(self, *args, **kwargs):
        return overlay_manager.make_plan_line_tracker(*args, **kwargs)

    def set_plan_line_tracker_width(self, *args, **kwargs):
        return overlay_manager.set_plan_line_tracker_width(*args, **kwargs)

    def get_footprint_overlay_polylines(self, *args, **kwargs):
        return overlay_geometry.get_footprint_overlay_polylines(self.session, *args, **kwargs)

    def build_overlay_segments_from_polylines(self, *args, **kwargs):
        return overlay_geometry.build_overlay_segments_from_polylines(self.session, *args, **kwargs)

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

    def get_opening_overlay_segments(self, *args, **kwargs):
        return overlay_geometry.get_opening_overlay_segments(self.session, *args, **kwargs)

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
