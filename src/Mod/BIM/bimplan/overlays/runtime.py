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


def _make_overlay_session_forwarder(func):
    def _forward(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    _forward.__name__ = func.__name__
    _forward.__qualname__ = "PlanOverlaysAPI.{}".format(func.__name__)
    _forward.__doc__ = func.__doc__
    return _forward


def _make_overlay_static_forwarder(func):
    def _forward(*args, **kwargs):
        return func(*args, **kwargs)

    _forward.__name__ = func.__name__
    _forward.__qualname__ = "PlanOverlaysAPI.{}".format(func.__name__)
    _forward.__doc__ = func.__doc__
    return staticmethod(_forward)


_PLAN_OVERLAY_STATIC_FORWARDERS = (
    overlay_manager.finalize_trackers,
    overlay_manager.make_plan_line_tracker,
    overlay_manager.set_plan_line_tracker_width,
    overlay_geometry.get_footprint_overlay_polylines,
    overlay_geometry.build_overlay_segments_from_polylines,
)

_PLAN_OVERLAY_SESSION_FORWARDERS = (
    overlay_manager.flush_plan_overlay_visual_refresh,
    overlay_manager.flush_view_scale_overlay_refresh,
    overlay_manager.refresh_plan_overlay_view_scale,
    overlay_manager.refresh_plan_overlay_visuals,
    overlay_geometry.get_plan_overlay_geometry_kinds_for_object,
    overlay_geometry.get_plan_overlay_geometry_cache_entry,
    overlay_geometry.invalidate_plan_overlay_geometry_cache,
    overlay_geometry.get_cached_plan_overlay_geometry,
    overlay_geometry.get_wall_overlay_polylines,
    overlay_geometry.get_space_footprint_faces,
    overlay_geometry.get_space_overlay_polylines,
    overlay_geometry.get_space_overlay_segments,
    overlay_geometry.get_region_footprint_faces,
    overlay_geometry.get_region_overlay_polylines,
    overlay_geometry.get_region_overlay_segments,
    overlay_geometry.get_opening_overlay_polylines,
    overlay_geometry.get_opening_overlay_screen_polylines,
    overlay_geometry.get_opening_overlay_screen_bounds,
    overlay_geometry.get_opening_pick_bounds,
    overlay_geometry.get_opening_overlay_segments,
    space_overlays.sync_secondary_selected_overlays,
    space_overlays.clear_secondary_selected_overlays,
    space_overlays.sync_space_region_pick_overlays,
    space_overlays.clear_space_region_pick_overlays,
    space_overlays.create_space_overlay_trackers,
    space_overlays.create_region_overlay_trackers,
    space_overlays.sync_hovered_space_overlay,
    space_overlays.clear_hovered_space_overlay,
    space_overlays.sync_hovered_region_overlay,
    space_overlays.clear_hovered_region_overlay,
    space_overlays.invalidate_selected_space_overlay_cache,
    space_overlays.sync_selected_space_overlay,
    space_overlays.clear_selected_space_overlay,
    space_overlays.sync_selected_region_overlay,
    space_overlays.clear_selected_region_overlay,
    wall_overlays.retarget_edit_tracker,
    wall_overlays.sync_wall_grips,
    wall_overlays.schedule_wall_grip_sync,
    wall_overlays.run_scheduled_wall_grip_sync,
    wall_overlays.clear_wall_grips,
    wall_overlays.sync_hovered_wall_overlay,
    wall_overlays.clear_hovered_wall_overlay,
    wall_overlays.sync_selected_wall_overlay,
    wall_overlays.clear_selected_wall_overlay,
    wall_overlays.apply_selected_wall_selection_feedback,
    wall_overlays.get_plan_context_junctions,
    wall_overlays.create_junction_node_trackers,
    wall_overlays.sync_junction_node_overlays,
    wall_overlays.clear_junction_node_overlays,
    wall_overlays.sync_hovered_wall_opening_context_overlay,
    wall_overlays.clear_hovered_wall_opening_context_overlay,
    wall_overlays.create_wall_overlay_trackers,
    provider_overlays.sync_provider_overlays,
    provider_overlays.clear_provider_overlays,
    provider_overlays.sync_hovered_provider_overlay,
    provider_overlays.clear_hovered_provider_overlay,
    provider_overlays.sync_selected_provider_overlay,
    provider_overlays.clear_selected_provider_overlay,
    provider_overlays.get_selected_provider_handle_specs,
    provider_overlays.sync_selected_provider_handles,
    provider_overlays.clear_selected_provider_handles,
    provider_overlays.pick_selected_provider_handle,
    provider_overlays.sync_provider_point_preview,
    provider_overlays.clear_provider_point_preview,
    opening_overlays.get_opening_handle_markers,
    opening_overlays.set_opening_handle_tracker_marker,
    opening_overlays.discard_opening_handle_tracker_pool,
    opening_overlays.queue_prime_opening_handle_tracker_pool,
    opening_overlays.prime_opening_handle_tracker_pool,
    opening_overlays.sync_hovered_opening_overlay,
    opening_overlays.clear_hovered_opening_overlay,
    opening_overlays.invalidate_hovered_opening_overlay_cache,
    opening_overlays.create_opening_overlay_trackers,
    opening_overlays.sync_selected_opening_overlay,
    opening_overlays.clear_selected_opening_overlay,
    opening_overlays.invalidate_selected_opening_overlay_cache,
    opening_overlays.sync_selected_wall_opening_context_overlay,
    opening_overlays.clear_selected_wall_opening_context_overlay,
    opening_overlays.get_selected_opening_handle_specs,
    opening_overlays.sync_selected_opening_handles,
    opening_overlays.clear_selected_opening_handles,
    symbol_overlays.clear_symbol_edit_preview,
    symbol_overlays.get_plan_symbol_instances,
    symbol_overlays.get_symbol_global_placement,
    symbol_overlays.get_symbol_parent_global_placement,
    symbol_overlays.get_symbol_plan_proxy,
    symbol_overlays.get_symbol_semantic_proxy,
    symbol_overlays.get_symbol_overlay_polylines,
    symbol_overlays.get_symbol_overlay_segments,
    symbol_overlays.get_symbol_overlay_screen_polylines,
    symbol_overlays.get_symbol_overlay_screen_bounds,
    symbol_overlays.refresh_selected_symbol_visuals,
    symbol_overlays.create_symbol_overlay_trackers,
    symbol_overlays.sync_hovered_symbol_overlay,
    symbol_overlays.clear_hovered_symbol_overlay,
    symbol_overlays.sync_selected_symbol_overlay,
    symbol_overlays.clear_selected_symbol_overlay,
    symbol_overlays.get_symbol_rotation_snap_increment_degrees,
    symbol_overlays.get_symbol_rotation_snap_step_radians,
    symbol_overlays.symbol_rotation_free_angle_override_active,
    symbol_overlays.resolve_symbol_handle_target_point,
    symbol_overlays.get_symbol_handle_radius,
    symbol_overlays.get_selected_symbol_handle_specs,
    symbol_overlays.get_symbol_anchor_point,
    symbol_overlays.get_symbol_facing_vector,
    symbol_overlays.sync_selected_symbol_handles,
    symbol_overlays.clear_selected_symbol_handles,
    symbol_overlays.sync_symbol_edit_preview,
    symbol_overlays.pick_selected_symbol_handle,
    symbol_overlays.get_symbol_local_anchor,
    symbol_overlays.get_symbol_local_facing,
)

for _overlay_func in _PLAN_OVERLAY_STATIC_FORWARDERS:
    setattr(PlanOverlaysAPI, _overlay_func.__name__, _make_overlay_static_forwarder(_overlay_func))

for _overlay_func in _PLAN_OVERLAY_SESSION_FORWARDERS:
    setattr(
        PlanOverlaysAPI,
        _overlay_func.__name__,
        _make_overlay_session_forwarder(_overlay_func),
    )

del _overlay_func
