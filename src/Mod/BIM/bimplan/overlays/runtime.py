# SPDX-License-Identifier: LGPL-2.1-or-later

"""Owned overlay API surface for BIM Plan Edit."""

from functools import wraps

from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import manager as overlay_manager
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import providers as provider_overlays
from bimplan.overlays import spaces as space_overlays
from bimplan.overlays import symbols as symbol_overlays
from bimplan.overlays import walls as wall_overlays


def _bind_overlay_call(func):
    @wraps(func)
    def method(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    return method


def _bind_session_overlay_compat(api_method_name):
    def method(self, *args, **kwargs):
        overlay_method = getattr(self.overlays, api_method_name)
        return overlay_method(*args, **kwargs)

    return method


_PLAN_OVERLAYS_API_MODULES = (
    (
        overlay_manager,
        (
            "finalize_trackers",
            "make_plan_line_tracker",
            "set_plan_line_tracker_width",
        ),
    ),
    (
        overlay_geometry,
        (
            "get_space_footprint_faces",
            "get_space_overlay_polylines",
            "get_space_overlay_segments",
            "get_region_footprint_faces",
            "get_region_overlay_polylines",
            "get_region_overlay_segments",
            "get_opening_overlay_polylines",
            "get_opening_overlay_screen_polylines",
            "get_opening_overlay_segments",
        ),
    ),
    (
        space_overlays,
        (
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
        ),
    ),
    (
        wall_overlays,
        (
            "sync_wall_grips",
            "schedule_wall_grip_sync",
            "run_scheduled_wall_grip_sync",
            "clear_wall_grips",
            "sync_hovered_wall_overlay",
            "clear_hovered_wall_overlay",
            "sync_selected_wall_overlay",
            "clear_selected_wall_overlay",
            "get_plan_context_junctions",
            "create_junction_node_trackers",
            "sync_junction_node_overlays",
            "clear_junction_node_overlays",
            "sync_hovered_wall_opening_context_overlay",
            "clear_hovered_wall_opening_context_overlay",
            "create_wall_overlay_trackers",
        ),
    ),
    (
        provider_overlays,
        (
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
        ),
    ),
    (
        opening_overlays,
        (
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
        ),
    ),
    (
        symbol_overlays,
        (
            "get_plan_symbol_instances",
            "get_symbol_global_placement",
            "get_symbol_parent_global_placement",
            "get_symbol_plan_proxy",
            "get_symbol_semantic_proxy",
            "get_symbol_overlay_polylines",
            "get_symbol_overlay_segments",
            "get_symbol_overlay_screen_polylines",
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
            "sync_selected_symbol_handles",
            "clear_selected_symbol_handles",
            "pick_selected_symbol_handle",
            "get_symbol_local_anchor",
            "get_symbol_local_facing",
        ),
    ),
)

_PLAN_OVERLAYS_API_BOUND_METHODS = {}
for _module, _method_names in _PLAN_OVERLAYS_API_MODULES:
    for _method_name in _method_names:
        _PLAN_OVERLAYS_API_BOUND_METHODS[_method_name] = getattr(_module, _method_name)

_PLAN_SESSION_OVERLAY_COMPAT_METHODS = (
    "_prime_opening_handle_tracker_pool",
    "_schedule_wall_grip_sync",
    "_run_scheduled_wall_grip_sync",
    "_clear_wall_grips",
    "_clear_space_region_pick_overlays",
    "_invalidate_selected_space_overlay_cache",
    "_sync_selected_space_overlay",
    "_sync_selected_region_overlay",
    "_get_selected_provider_handle_specs",
    "_clear_selected_provider_handles",
    "_clear_provider_point_preview",
    "_sync_hovered_opening_overlay",
    "_get_opening_overlay_segments",
    "_sync_selected_wall_opening_context_overlay",
)


class PlanOverlaysAPI:
    """Owned session surface for Plan Edit overlay behavior."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


for _method_name, _method in _PLAN_OVERLAYS_API_BOUND_METHODS.items():
    setattr(PlanOverlaysAPI, _method_name, _bind_overlay_call(_method))


def bind_session_overlay_compat(session_class):
    for compat_method_name in _PLAN_SESSION_OVERLAY_COMPAT_METHODS:
        setattr(
            session_class,
            compat_method_name,
            _bind_session_overlay_compat(compat_method_name.removeprefix("_")),
        )
