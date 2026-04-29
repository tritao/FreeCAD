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
from bimplan.selection import target_dispatch as plan_target_dispatch
from bimplan.selection import target_kinds as plan_target_kinds

_PLAN_VIEW_SCALE_REFRESH_DELAY_MS = 40


def _queue_plan_overlay_visual_refresh(session, *visuals):
    return overlay_manager.queue_plan_overlay_visual_refresh(
        session,
        visuals,
        plan_document_visuals.PLAN_VISUAL_ALL,
        plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE,
    )


def discard_runtime_references(session):
    session.overlays.walls.discard_runtime_references()
    session.overlays.spaces.discard_runtime_references()


def clear_begin_teardown_visuals(session):
    session.overlays.walls.clear_junction_node_overlays()
    session.overlays.walls.clear_hovered_wall_opening_context_overlay()
    plan_target_dispatch.clear_hovered_target_visuals(session)
    session.overlays.walls.clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        clear_handle_kinds=(
            plan_target_kinds.PLAN_TARGET_PROVIDER,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
        ),
    )
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    session.overlays.spaces.clear_secondary_selected_overlays()
    session.overlays.providers.clear_provider_overlays()
    session.overlays.providers.clear_provider_point_preview()
    session.overlays.spaces.clear_space_region_pick_overlays()
    session.overlays.openings.discard_opening_handle_tracker_pool()
    session.openings.clear_opening_move_preview()
    session.symbols.clear_symbol_edit_preview()
    session.spaces.clear_plan_region_preview()


def clear_shutdown_visuals(session):
    session.overlays.walls.clear_junction_node_overlays()
    session.overlays.walls.clear_hovered_wall_opening_context_overlay()
    plan_target_dispatch.clear_hovered_target_visuals(
        session,
        kinds=(
            plan_target_kinds.PLAN_TARGET_WALL,
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
            plan_target_kinds.PLAN_TARGET_PROVIDER,
        ),
    )
    session.overlays.walls.clear_wall_grips()
    plan_target_dispatch.clear_selected_target_visuals(
        session,
        clear_handle_kinds=(
            plan_target_kinds.PLAN_TARGET_OPENING,
            plan_target_kinds.PLAN_TARGET_SYMBOL,
        ),
    )
    session.overlays.openings.clear_selected_wall_opening_context_overlay()
    session.overlays.providers.clear_provider_overlays()
    session.overlays.providers.clear_provider_point_preview()
    session.overlays.openings.discard_opening_handle_tracker_pool()
    session.openings.clear_opening_move_preview()
    session.symbols.clear_symbol_edit_preview()


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
    def discard_runtime_references(self):
        self.session.overlay_tracker_state.space_region_pick_trackers = []

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
    def discard_runtime_references(self):
        self.session.overlay_tracker_state.junction_node_trackers = []

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
        self.symbols = symbol_overlays.PlanSymbolOverlayService(session)

    @property
    def session(self):
        return self._session

    def queue_plan_overlay_visual_refresh(self, *visuals):
        return _queue_plan_overlay_visual_refresh(self.session, *visuals)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def clear_begin_teardown_visuals(self):
        return clear_begin_teardown_visuals(self.session)

    def clear_shutdown_visuals(self):
        return clear_shutdown_visuals(self.session)

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
