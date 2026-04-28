# SPDX-License-Identifier: LGPL-2.1-or-later

"""Owned overlay API surface for BIM Plan Edit."""

from functools import partial

from bimplan import document_visuals as plan_document_visuals
from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import manager as overlay_manager
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import providers as provider_overlays
from bimplan.overlays import spaces as space_overlays
from bimplan.overlays import symbols as symbol_overlays
from bimplan.overlays import walls as wall_overlays

_PLAN_VIEW_SCALE_REFRESH_DELAY_MS = 40


class _BoundOverlayService:
    MODULE = None
    SESSION_EXPORTS = ()
    STATIC_EXPORTS = ()

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def __getattr__(self, name):
        if name in self.SESSION_EXPORTS:
            bound = partial(getattr(self.MODULE, name), self._session)
        elif name in self.STATIC_EXPORTS:
            bound = getattr(self.MODULE, name)
        else:
            raise AttributeError("{} has no attribute {!r}".format(type(self).__name__, name))
        setattr(self, name, bound)
        return bound

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self.SESSION_EXPORTS) | set(self.STATIC_EXPORTS))


class PlanOverlayManagerService(_BoundOverlayService):
    MODULE = overlay_manager
    SESSION_EXPORTS = (
        "flush_plan_overlay_visual_refresh",
        "flush_view_scale_overlay_refresh",
        "refresh_plan_overlay_view_scale",
        "refresh_plan_overlay_visuals",
    )
    STATIC_EXPORTS = (
        "finalize_trackers",
        "make_plan_line_tracker",
        "set_plan_line_tracker_width",
    )


class PlanOverlayGeometryService(_BoundOverlayService):
    MODULE = overlay_geometry
    SESSION_EXPORTS = (
        "get_plan_overlay_geometry_kinds_for_object",
        "get_plan_overlay_geometry_cache_entry",
        "invalidate_plan_overlay_geometry_cache",
        "get_cached_plan_overlay_geometry",
        "get_wall_overlay_polylines",
        "get_space_footprint_faces",
        "get_space_overlay_polylines",
        "get_space_overlay_segments",
        "get_region_footprint_faces",
        "get_region_overlay_polylines",
        "get_region_overlay_segments",
        "get_opening_overlay_polylines",
        "get_opening_overlay_screen_polylines",
        "get_opening_overlay_screen_bounds",
        "get_opening_pick_bounds",
        "get_opening_overlay_segments",
    )
    STATIC_EXPORTS = (
        "get_footprint_overlay_polylines",
        "build_overlay_segments_from_polylines",
    )


class PlanSpaceOverlayService(_BoundOverlayService):
    MODULE = space_overlays
    SESSION_EXPORTS = (
        "sync_secondary_selected_overlays",
        "clear_secondary_selected_overlays",
        "sync_space_region_pick_overlays",
        "clear_space_region_pick_overlays",
        "create_space_overlay_trackers",
        "create_region_overlay_trackers",
        "sync_hovered_space_overlay",
        "clear_hovered_space_overlay",
        "sync_hovered_region_overlay",
        "clear_hovered_region_overlay",
        "invalidate_selected_space_overlay_cache",
        "sync_selected_space_overlay",
        "clear_selected_space_overlay",
        "sync_selected_region_overlay",
        "clear_selected_region_overlay",
    )


class PlanWallOverlayService(_BoundOverlayService):
    MODULE = wall_overlays
    SESSION_EXPORTS = (
        "retarget_edit_tracker",
        "sync_wall_grips",
        "schedule_wall_grip_sync",
        "run_scheduled_wall_grip_sync",
        "clear_wall_grips",
        "sync_hovered_wall_overlay",
        "clear_hovered_wall_overlay",
        "sync_selected_wall_overlay",
        "clear_selected_wall_overlay",
        "apply_selected_wall_selection_feedback",
        "get_plan_context_junctions",
        "create_junction_node_trackers",
        "sync_junction_node_overlays",
        "clear_junction_node_overlays",
        "sync_hovered_wall_opening_context_overlay",
        "clear_hovered_wall_opening_context_overlay",
        "create_wall_overlay_trackers",
    )


class PlanProviderOverlayService(_BoundOverlayService):
    MODULE = provider_overlays
    SESSION_EXPORTS = (
        "sync_provider_overlays",
        "clear_provider_overlays",
        "sync_hovered_provider_overlay",
        "clear_hovered_provider_overlay",
        "sync_selected_provider_overlay",
        "clear_selected_provider_overlay",
        "get_selected_provider_handle_specs",
        "sync_selected_provider_handles",
        "clear_selected_provider_handles",
        "pick_selected_provider_handle",
        "sync_provider_point_preview",
        "clear_provider_point_preview",
    )


class PlanOpeningOverlayService(_BoundOverlayService):
    MODULE = opening_overlays
    SESSION_EXPORTS = (
        "get_opening_handle_markers",
        "set_opening_handle_tracker_marker",
        "discard_opening_handle_tracker_pool",
        "queue_prime_opening_handle_tracker_pool",
        "prime_opening_handle_tracker_pool",
        "sync_hovered_opening_overlay",
        "clear_hovered_opening_overlay",
        "invalidate_hovered_opening_overlay_cache",
        "create_opening_overlay_trackers",
        "sync_selected_opening_overlay",
        "clear_selected_opening_overlay",
        "invalidate_selected_opening_overlay_cache",
        "sync_selected_wall_opening_context_overlay",
        "clear_selected_wall_opening_context_overlay",
        "get_selected_opening_handle_specs",
        "sync_selected_opening_handles",
        "clear_selected_opening_handles",
    )


class PlanSymbolOverlayService(_BoundOverlayService):
    MODULE = symbol_overlays
    SESSION_EXPORTS = (
        "clear_symbol_edit_preview",
        "get_plan_symbol_instances",
        "get_symbol_global_placement",
        "get_symbol_parent_global_placement",
        "get_symbol_plan_proxy",
        "get_symbol_semantic_proxy",
        "get_symbol_overlay_polylines",
        "get_symbol_overlay_segments",
        "get_symbol_overlay_screen_polylines",
        "get_symbol_overlay_screen_bounds",
        "refresh_selected_symbol_visuals",
        "create_symbol_overlay_trackers",
        "sync_hovered_symbol_overlay",
        "clear_hovered_symbol_overlay",
        "sync_selected_symbol_overlay",
        "clear_selected_symbol_overlay",
        "get_symbol_rotation_snap_increment_degrees",
        "get_symbol_rotation_snap_step_radians",
        "symbol_rotation_free_angle_override_active",
        "resolve_symbol_handle_target_point",
        "get_symbol_handle_radius",
        "get_selected_symbol_handle_specs",
        "get_symbol_anchor_point",
        "get_symbol_facing_vector",
        "sync_selected_symbol_handles",
        "clear_selected_symbol_handles",
        "sync_symbol_edit_preview",
        "pick_selected_symbol_handle",
        "get_symbol_local_anchor",
        "get_symbol_local_facing",
    )

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
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_SELECTED_SYMBOL
            )
            return True
        hovered_symbol = self.session.hovered_symbol
        if (
            hovered_symbol
            and not self.session.selection.state.is_selected_plan_target("symbol", hovered_symbol)
            and self.refresh_target_document_visual_dependency(hovered_symbol, obj, prop)
        ):
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_HOVERED_SYMBOL
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
