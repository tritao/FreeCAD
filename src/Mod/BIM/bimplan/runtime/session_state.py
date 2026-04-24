# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Initial mutable state for BIM Plan Edit sessions."""

from dataclasses import dataclass, field

import FreeCAD
import FreeCADGui
from bimplan.providers import runtime as plan_provider_runtime


class PlanInteractionAPI:
    """Owned session surface for Plan Edit interaction-state reads."""

    __slots__ = ("_session",)

    _MODAL_TOOLS = frozenset(
        ("Move Opening", "Move Symbol", "Rotate Symbol", "Set Space Text", "Window")
    )

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def is_modal_plan_interaction_active(self):
        return bool(
            self.session.wall_edit.is_wall_edit_modal_active()
            or self.session.current_tool in self._MODAL_TOOLS
        )


@dataclass
class PlanTaskPanelState:
    relation_status_message: str | None = None
    space_region_candidates: list = field(default_factory=list)
    hovered_space_region_candidate: object = None
    plan_region_parent_space: object = None


@dataclass
class PlanProviderOverlayReadState:
    mode: str = plan_provider_runtime.PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE
    visibility: dict = field(default_factory=dict)
    render_state: object = None


@dataclass
class PlanInteractionState:
    embedded_host: object = None
    embedded_tool: object = None
    embedded_tool_name: str | None = None
    provider_point_tool: object = None
    edit_opening: object = None
    edit_opening_handle_index: object = None
    edit_symbol: object = None
    edit_symbol_handle_role: object = None
    edit_provider: object = None
    edit_provider_handle_index: object = None
    edit_provider_handle: object = None
    edit_space: object = None


@dataclass
class PlanSelectionState:
    selected_plan_target_kind: str | None = None
    selected_plan_target_obj: object = None
    hovered_wall: object = None
    hovered_opening: object = None
    hovered_symbol: object = None
    hovered_provider: object = None
    hovered_space: object = None
    hovered_region: object = None
    pending_selected_plan_target: object = None
    secondary_selected_plan_targets_state: list = field(default_factory=list)


@dataclass
class PlanWallEditState:
    wall_edit_modal_active: bool = False
    edit_wall: object = None
    edit_endpoint: object = None
    edit_endpoints: object = None
    wall_edit_opening_clearances: dict = field(default_factory=dict)
    wall_edit_opening_clearances_queued: bool = False
    wall_edit_task_panel_refresh_queued: bool = False
    preview_points: object = None
    preview_line_tracker: object = None
    preview_footprint_trackers: list = field(default_factory=list)
    preview_grip_trackers: list = field(default_factory=list)
    wall_edit_readout_trackers: list = field(default_factory=list)
    wall_edit_opening_preview_trackers: list = field(default_factory=list)
    wall_edit_active_readout_tracker: object = None
    wall_edit_active_readout_mode: object = None
    wall_edit_length_edit_queued: bool = False
    edit_wall_visibility: object = None


@dataclass
class PlanHoverPickState:
    dirty: bool = False
    last_time: float = 0.0
    last_mouse_pos: object = None
    cache_queued: bool = False


@dataclass
class PlanSelectionSyncState:
    selection_refresh_queued: bool = False
    gui_selection_sync_queued: bool = False
    gui_selection_sync_generation: int = 0
    queued_gui_selection_object: object = None


@dataclass
class PlanInputEventState:
    mouse_moved_cb: object = None
    mouse_wheel_cb: object = None
    mouse_wheel_event_type: object = None
    mouse_pressed_cb: object = None
    key_pressed_cb: object = None
    consume_left_button_release: bool = False


@dataclass
class PlanOverlayRefreshState:
    overlay_refresh_queued: bool = False
    view_scale_overlay_refresh_queued: bool = False
    dirty_plan_visuals: set = field(default_factory=set)


@dataclass
class PlanWallGripState:
    state: object = None
    sync_queued: bool = False
    sync_generation: int = 0


@dataclass
class PlanViewportState:
    status_chip: object = None
    saved_camera: object = None
    saved_camera_type: object = None
    saved_navigation_style: object = None
    saved_navigation_state: dict = field(default_factory=dict)
    saved_view_action_state: dict = field(default_factory=dict)
    saved_preselection_state: object = None
    plan_preselection_forced: bool = False
    saved_object_view_state: dict = field(default_factory=dict)
    working_plane: object = None
    interaction_plane: object = None


@dataclass
class PlanDocumentVisualState:
    pending_created_plan_objects: dict = field(default_factory=dict)
    created_plan_objects_flush_queued: bool = False
    created_plan_objects_flush_deferred: bool = False
    document_visual_update_defer_depth: int = 0
    document_visual_refresh_deferred: bool = False


@dataclass
class PlanProviderTransientState:
    selected_provider_overlay_render_state: object = None
    provider_handle_trackers: list = field(default_factory=list)
    selected_provider_handle_render_state: object = None
    provider_selected_objects: list = field(default_factory=list)
    provider_point_host_target: object = None
    provider_point_host_source: str = ""
    provider_point_preview_trackers: list = field(default_factory=list)
    provider_point_preview_render_state: object = None
    provider_point_preview_style_state: object = None
    provider_point_preview_source_point: object = None
    provider_point_preview_point: object = None
    provider_point_preview_host_target: object = None
    provider_point_preview_host_source: str = ""


@dataclass
class PlanOpeningTransientState:
    opening_handle_trackers: list = field(default_factory=list)
    opening_handle_tracker_pool: list = field(default_factory=list)
    opening_handle_tracker_pool_queued: bool = False
    selected_opening_handle_render_state: object = None
    selected_opening_hard_refresh_queued: bool = False
    opening_host_recompute_queued: bool = False
    opening_host_recompute_running: bool = False
    opening_move_preview_trackers: list = field(default_factory=list)
    symbol_edit_preview_trackers: list = field(default_factory=list)
    opening_move_snap_profile_pushed: bool = False
    edit_opening_move_anchor: str = "center"
    edit_opening_move_raw_point: object = None


@dataclass
class PlanOverlayTrackerState:
    grip_trackers: list = field(default_factory=list)
    wall_hover_trackers: list = field(default_factory=list)
    wall_overlay_trackers: list = field(default_factory=list)
    junction_node_trackers: list = field(default_factory=list)
    hovered_wall_opening_context_trackers: list = field(default_factory=list)
    opening_hover_trackers: list = field(default_factory=list)
    symbol_hover_trackers: list = field(default_factory=list)
    provider_hover_trackers: list = field(default_factory=list)
    provider_selected_trackers: list = field(default_factory=list)
    space_hover_trackers: list = field(default_factory=list)
    region_hover_trackers: list = field(default_factory=list)
    opening_overlay_trackers: list = field(default_factory=list)
    symbol_overlay_trackers: list = field(default_factory=list)
    space_overlay_trackers: list = field(default_factory=list)
    region_overlay_trackers: list = field(default_factory=list)
    provider_overlay_trackers: list = field(default_factory=list)
    secondary_selection_trackers: list = field(default_factory=list)
    space_region_pick_trackers: list = field(default_factory=list)
    selected_wall_opening_context_trackers: list = field(default_factory=list)
    symbol_handle_trackers: list = field(default_factory=list)


@dataclass
class PlanOverlayCacheState:
    plan_overlay_geometry_cache: dict = field(
        default_factory=lambda: {
            "opening": {},
            "space": {},
            "region": {},
        }
    )
    plan_semantic_object_cache: dict = field(default_factory=dict)
    plan_object_storeys_cache: dict = field(default_factory=dict)
    plan_symbol_instances_cache: object = None
    plan_space_instances_cache: object = None
    plan_region_instances_cache: object = None
    plan_opening_instances_cache: object = None
    wall_hosted_openings_cache: object = None
    wall_hosted_openings_cache_queued: bool = False
    opening_overlay_screen_cache: dict = field(default_factory=dict)
    opening_overlay_screen_cache_projection_key: object = None
    symbol_overlay_screen_cache: dict = field(default_factory=dict)


@dataclass
class PlanOverlayTransientState:
    hovered_opening_overlay_dirty: bool = False
    hovered_opening_overlay_render_state: object = None
    selected_opening_overlay_dirty: bool = False
    selected_opening_overlay_render_state: object = None
    selected_space_overlay_dirty: bool = True
    selected_space_overlay_geometry_key: object = None
    selected_space_overlay_segments: tuple = ()
    selected_space_overlay_render_state: object = None


@dataclass
class PlanCreationPreviewState:
    rect_wall_start: object = None
    rect_wall_params: object = None
    rect_wall_preview_trackers: list = field(default_factory=list)
    space_separator_start: object = None
    space_separator_height: object = None
    space_separator_preview_trackers: list = field(default_factory=list)
    window_host_wall: object = None
    window_preview_trackers: list = field(default_factory=list)
    plan_region_points: list = field(default_factory=list)
    plan_region_preview_trackers: list = field(default_factory=list)


def _coerce_identity(value):
    return value


def _coerce_bool(value):
    return bool(value)


def _coerce_int(value):
    return int(value or 0)


def _coerce_float(value):
    return float(value or 0.0)


def _coerce_list(value):
    return list(value or [])


def _coerce_dict(value):
    return dict(value or {})


def _coerce_set(value):
    return set(value or ())


def _coerce_tuple(value):
    return tuple(value or ())


def _make_str_coercer(default=""):
    def _coerce(value):
        return str(value or default)

    return _coerce


def _coerce_optional_nonempty_str(value):
    return str(value or "") or None


def _coerce_overlay_geometry_cache(value):
    default_cache = {"opening": {}, "space": {}, "region": {}}
    return dict(value or default_cache)


def _make_state_backed_property(ensure_method_name, field_name, coerce=_coerce_identity):
    def _getter(self):
        return getattr(getattr(self, ensure_method_name)(), field_name)

    def _setter(self, value):
        setattr(getattr(self, ensure_method_name)(), field_name, coerce(value))

    return property(_getter, _setter)


def _make_ensure_state_method(slot_name, state_factory):
    def _ensure_state(self):
        state = self.__dict__.get(slot_name)
        if state is None:
            state = state_factory()
            self.__dict__[slot_name] = state
        return state

    return _ensure_state


_PLAN_EDIT_SESSION_STATE_ENSURERS = (
    ("_ensure_task_panel_state", "task_panel_state", PlanTaskPanelState),
    (
        "_ensure_provider_overlay_read_state",
        "provider_overlay_read_state",
        PlanProviderOverlayReadState,
    ),
    ("_ensure_interaction_state", "interaction_state", PlanInteractionState),
    ("_ensure_selection_state", "selection_state", PlanSelectionState),
    ("_ensure_wall_edit_state", "wall_edit_state", PlanWallEditState),
    ("_ensure_hover_pick_state", "hover_pick_state", PlanHoverPickState),
    ("_ensure_selection_sync_state", "selection_sync_state", PlanSelectionSyncState),
    ("_ensure_input_event_state", "input_event_state", PlanInputEventState),
    ("_ensure_overlay_refresh_state", "overlay_refresh_state", PlanOverlayRefreshState),
    ("_ensure_wall_grip_runtime_state", "wall_grip_state", PlanWallGripState),
    ("_ensure_viewport_state", "viewport_state", PlanViewportState),
    ("_ensure_document_visual_state", "document_visual_state", PlanDocumentVisualState),
    ("_ensure_provider_transient_state", "provider_transient_state", PlanProviderTransientState),
    ("_ensure_opening_transient_state", "opening_transient_state", PlanOpeningTransientState),
    ("_ensure_overlay_tracker_state", "overlay_tracker_state", PlanOverlayTrackerState),
    ("_ensure_overlay_cache_state", "overlay_cache_state", PlanOverlayCacheState),
    ("_ensure_overlay_transient_state", "overlay_transient_state", PlanOverlayTransientState),
    ("_ensure_creation_preview_state", "creation_preview_state", PlanCreationPreviewState),
)


_PLAN_EDIT_SESSION_STATE_PROPERTIES = (
    (
        "_ensure_task_panel_state",
        (
            ("_plan_relation_status_message", "relation_status_message", _coerce_identity),
            ("_space_region_candidates", "space_region_candidates", _coerce_list),
            ("_hovered_space_region_candidate", "hovered_space_region_candidate", _coerce_identity),
            ("_plan_region_parent_space", "plan_region_parent_space", _coerce_identity),
        ),
    ),
    (
        "_ensure_provider_overlay_read_state",
        (
            ("_provider_overlay_mode", "mode", _make_str_coercer("architecture")),
            ("_provider_overlay_visibility", "visibility", _coerce_dict),
            ("_provider_overlay_state", "render_state", _coerce_identity),
        ),
    ),
    (
        "_ensure_selection_state",
        (
            ("_selected_plan_target_kind", "selected_plan_target_kind", _coerce_identity),
            ("_selected_plan_target_obj", "selected_plan_target_obj", _coerce_identity),
            ("hovered_wall", "hovered_wall", _coerce_identity),
            ("hovered_opening", "hovered_opening", _coerce_identity),
            ("hovered_symbol", "hovered_symbol", _coerce_identity),
            ("hovered_provider", "hovered_provider", _coerce_identity),
            ("hovered_space", "hovered_space", _coerce_identity),
            ("hovered_region", "hovered_region", _coerce_identity),
            ("_pending_selected_plan_target", "pending_selected_plan_target", _coerce_identity),
            (
                "_secondary_selected_plan_targets_state",
                "secondary_selected_plan_targets_state",
                _coerce_list,
            ),
        ),
    ),
    (
        "_ensure_wall_edit_state",
        (
            ("_wall_edit_modal_active", "wall_edit_modal_active", _coerce_bool),
            ("_edit_wall", "edit_wall", _coerce_identity),
            ("_edit_endpoint", "edit_endpoint", _coerce_identity),
            ("_edit_endpoints", "edit_endpoints", _coerce_identity),
            ("_wall_edit_opening_clearances", "wall_edit_opening_clearances", _coerce_dict),
            (
                "_wall_edit_opening_clearances_queued",
                "wall_edit_opening_clearances_queued",
                _coerce_bool,
            ),
            (
                "_wall_edit_task_panel_refresh_queued",
                "wall_edit_task_panel_refresh_queued",
                _coerce_bool,
            ),
            ("_preview_points", "preview_points", _coerce_identity),
            ("_preview_line_tracker", "preview_line_tracker", _coerce_identity),
            ("_preview_footprint_trackers", "preview_footprint_trackers", _coerce_list),
            ("_preview_grip_trackers", "preview_grip_trackers", _coerce_list),
            ("_wall_edit_readout_trackers", "wall_edit_readout_trackers", _coerce_list),
            (
                "_wall_edit_opening_preview_trackers",
                "wall_edit_opening_preview_trackers",
                _coerce_list,
            ),
            (
                "_wall_edit_active_readout_tracker",
                "wall_edit_active_readout_tracker",
                _coerce_identity,
            ),
            ("_wall_edit_active_readout_mode", "wall_edit_active_readout_mode", _coerce_identity),
            ("_wall_edit_length_edit_queued", "wall_edit_length_edit_queued", _coerce_bool),
            ("_edit_wall_visibility", "edit_wall_visibility", _coerce_identity),
        ),
    ),
    (
        "_ensure_interaction_state",
        (
            ("_embedded_host", "embedded_host", _coerce_identity),
            ("_embedded_tool", "embedded_tool", _coerce_identity),
            ("_embedded_tool_name", "embedded_tool_name", _coerce_optional_nonempty_str),
            ("_provider_point_tool", "provider_point_tool", _coerce_identity),
            ("_edit_opening", "edit_opening", _coerce_identity),
            ("_edit_opening_handle_index", "edit_opening_handle_index", _coerce_identity),
            ("_edit_symbol", "edit_symbol", _coerce_identity),
            ("_edit_symbol_handle_role", "edit_symbol_handle_role", _coerce_identity),
            ("_edit_provider", "edit_provider", _coerce_identity),
            ("_edit_provider_handle_index", "edit_provider_handle_index", _coerce_identity),
            ("_edit_provider_handle", "edit_provider_handle", _coerce_identity),
            ("_edit_space", "edit_space", _coerce_identity),
        ),
    ),
    (
        "_ensure_hover_pick_state",
        (
            ("_hover_pick_dirty", "dirty", _coerce_bool),
            ("_hover_pick_last_time", "last_time", _coerce_float),
            ("_hover_pick_last_mouse_pos", "last_mouse_pos", _coerce_identity),
            ("_plan_hover_pick_cache_queued", "cache_queued", _coerce_bool),
        ),
    ),
    (
        "_ensure_selection_sync_state",
        (
            ("_selection_refresh_queued", "selection_refresh_queued", _coerce_bool),
            ("_gui_selection_sync_queued", "gui_selection_sync_queued", _coerce_bool),
            ("_gui_selection_sync_generation", "gui_selection_sync_generation", _coerce_int),
            ("_queued_gui_selection_object", "queued_gui_selection_object", _coerce_identity),
        ),
    ),
    (
        "_ensure_input_event_state",
        (
            ("_mouse_moved_cb", "mouse_moved_cb", _coerce_identity),
            ("_mouse_wheel_cb", "mouse_wheel_cb", _coerce_identity),
            ("_mouse_wheel_event_type", "mouse_wheel_event_type", _coerce_identity),
            ("_mouse_pressed_cb", "mouse_pressed_cb", _coerce_identity),
            ("_key_pressed_cb", "key_pressed_cb", _coerce_identity),
            ("_consume_left_button_release", "consume_left_button_release", _coerce_bool),
        ),
    ),
    (
        "_ensure_overlay_refresh_state",
        (
            ("_overlay_refresh_queued", "overlay_refresh_queued", _coerce_bool),
            (
                "_view_scale_overlay_refresh_queued",
                "view_scale_overlay_refresh_queued",
                _coerce_bool,
            ),
            ("_dirty_plan_visuals", "dirty_plan_visuals", _coerce_set),
        ),
    ),
    (
        "_ensure_wall_grip_runtime_state",
        (
            ("_wall_grip_state", "state", _coerce_identity),
            ("_wall_grip_sync_queued", "sync_queued", _coerce_bool),
            ("_wall_grip_sync_generation", "sync_generation", _coerce_int),
        ),
    ),
    (
        "_ensure_viewport_state",
        (
            ("_viewport_status_chip", "status_chip", _coerce_identity),
            ("_saved_camera", "saved_camera", _coerce_identity),
            ("_saved_camera_type", "saved_camera_type", _coerce_identity),
            ("_saved_navigation_style", "saved_navigation_style", _coerce_identity),
            ("_saved_navigation_state", "saved_navigation_state", _coerce_dict),
            ("_saved_view_action_state", "saved_view_action_state", _coerce_dict),
            ("_saved_preselection_state", "saved_preselection_state", _coerce_identity),
            ("_plan_preselection_forced", "plan_preselection_forced", _coerce_bool),
            ("_saved_object_view_state", "saved_object_view_state", _coerce_dict),
            ("_working_plane", "working_plane", _coerce_identity),
            ("_interaction_plane", "interaction_plane", _coerce_identity),
        ),
    ),
    (
        "_ensure_document_visual_state",
        (
            ("_pending_created_plan_objects", "pending_created_plan_objects", _coerce_dict),
            (
                "_created_plan_objects_flush_queued",
                "created_plan_objects_flush_queued",
                _coerce_bool,
            ),
            (
                "_created_plan_objects_flush_deferred",
                "created_plan_objects_flush_deferred",
                _coerce_bool,
            ),
            (
                "_document_visual_update_defer_depth",
                "document_visual_update_defer_depth",
                _coerce_int,
            ),
            ("_document_visual_refresh_deferred", "document_visual_refresh_deferred", _coerce_bool),
        ),
    ),
    (
        "_ensure_provider_transient_state",
        (
            (
                "_selected_provider_overlay_render_state",
                "selected_provider_overlay_render_state",
                _coerce_identity,
            ),
            ("_provider_handle_trackers", "provider_handle_trackers", _coerce_list),
            (
                "_selected_provider_handle_render_state",
                "selected_provider_handle_render_state",
                _coerce_identity,
            ),
            ("_provider_selected_objects", "provider_selected_objects", _coerce_list),
            ("_provider_point_host_target", "provider_point_host_target", _coerce_identity),
            ("_provider_point_host_source", "provider_point_host_source", _make_str_coercer("")),
            ("_provider_point_preview_trackers", "provider_point_preview_trackers", _coerce_list),
            (
                "_provider_point_preview_render_state",
                "provider_point_preview_render_state",
                _coerce_identity,
            ),
            (
                "_provider_point_preview_style_state",
                "provider_point_preview_style_state",
                _coerce_identity,
            ),
            (
                "_provider_point_preview_source_point",
                "provider_point_preview_source_point",
                _coerce_identity,
            ),
            ("_provider_point_preview_point", "provider_point_preview_point", _coerce_identity),
            (
                "_provider_point_preview_host_target",
                "provider_point_preview_host_target",
                _coerce_identity,
            ),
            (
                "_provider_point_preview_host_source",
                "provider_point_preview_host_source",
                _make_str_coercer(""),
            ),
        ),
    ),
    (
        "_ensure_opening_transient_state",
        (
            ("_opening_handle_trackers", "opening_handle_trackers", _coerce_list),
            ("_opening_handle_tracker_pool", "opening_handle_tracker_pool", _coerce_list),
            (
                "_opening_handle_tracker_pool_queued",
                "opening_handle_tracker_pool_queued",
                _coerce_bool,
            ),
            (
                "_selected_opening_handle_render_state",
                "selected_opening_handle_render_state",
                _coerce_identity,
            ),
            (
                "_selected_opening_hard_refresh_queued",
                "selected_opening_hard_refresh_queued",
                _coerce_bool,
            ),
            ("_opening_host_recompute_queued", "opening_host_recompute_queued", _coerce_bool),
            ("_opening_host_recompute_running", "opening_host_recompute_running", _coerce_bool),
            ("_opening_move_preview_trackers", "opening_move_preview_trackers", _coerce_list),
            ("_symbol_edit_preview_trackers", "symbol_edit_preview_trackers", _coerce_list),
            ("_opening_move_snap_profile_pushed", "opening_move_snap_profile_pushed", _coerce_bool),
            ("_edit_opening_move_anchor", "edit_opening_move_anchor", _make_str_coercer("center")),
            ("_edit_opening_move_raw_point", "edit_opening_move_raw_point", _coerce_identity),
        ),
    ),
    (
        "_ensure_overlay_tracker_state",
        (
            ("_grip_trackers", "grip_trackers", _coerce_list),
            ("_wall_hover_trackers", "wall_hover_trackers", _coerce_list),
            ("_wall_overlay_trackers", "wall_overlay_trackers", _coerce_list),
            ("_junction_node_trackers", "junction_node_trackers", _coerce_list),
            (
                "_hovered_wall_opening_context_trackers",
                "hovered_wall_opening_context_trackers",
                _coerce_list,
            ),
            ("_opening_hover_trackers", "opening_hover_trackers", _coerce_list),
            ("_symbol_hover_trackers", "symbol_hover_trackers", _coerce_list),
            ("_provider_hover_trackers", "provider_hover_trackers", _coerce_list),
            ("_provider_selected_trackers", "provider_selected_trackers", _coerce_list),
            ("_space_hover_trackers", "space_hover_trackers", _coerce_list),
            ("_region_hover_trackers", "region_hover_trackers", _coerce_list),
            ("_opening_overlay_trackers", "opening_overlay_trackers", _coerce_list),
            ("_symbol_overlay_trackers", "symbol_overlay_trackers", _coerce_list),
            ("_space_overlay_trackers", "space_overlay_trackers", _coerce_list),
            ("_region_overlay_trackers", "region_overlay_trackers", _coerce_list),
            ("_provider_overlay_trackers", "provider_overlay_trackers", _coerce_list),
            ("_secondary_selection_trackers", "secondary_selection_trackers", _coerce_list),
            ("_space_region_pick_trackers", "space_region_pick_trackers", _coerce_list),
            (
                "_selected_wall_opening_context_trackers",
                "selected_wall_opening_context_trackers",
                _coerce_list,
            ),
            ("_symbol_handle_trackers", "symbol_handle_trackers", _coerce_list),
        ),
    ),
    (
        "_ensure_overlay_cache_state",
        (),
    ),
    (
        "_ensure_overlay_transient_state",
        (
            ("_hovered_opening_overlay_dirty", "hovered_opening_overlay_dirty", _coerce_bool),
            (
                "_hovered_opening_overlay_render_state",
                "hovered_opening_overlay_render_state",
                _coerce_identity,
            ),
            ("_selected_opening_overlay_dirty", "selected_opening_overlay_dirty", _coerce_bool),
            (
                "_selected_opening_overlay_render_state",
                "selected_opening_overlay_render_state",
                _coerce_identity,
            ),
            ("_selected_space_overlay_dirty", "selected_space_overlay_dirty", _coerce_bool),
            (
                "_selected_space_overlay_geometry_key",
                "selected_space_overlay_geometry_key",
                _coerce_identity,
            ),
            ("_selected_space_overlay_segments", "selected_space_overlay_segments", _coerce_tuple),
            (
                "_selected_space_overlay_render_state",
                "selected_space_overlay_render_state",
                _coerce_identity,
            ),
        ),
    ),
    (
        "_ensure_creation_preview_state",
        (
            ("_rect_wall_start", "rect_wall_start", _coerce_identity),
            ("_rect_wall_params", "rect_wall_params", _coerce_identity),
            ("_rect_wall_preview_trackers", "rect_wall_preview_trackers", _coerce_list),
            ("_space_separator_start", "space_separator_start", _coerce_identity),
            ("_space_separator_height", "space_separator_height", _coerce_identity),
            (
                "_space_separator_preview_trackers",
                "space_separator_preview_trackers",
                _coerce_list,
            ),
            ("_window_host_wall", "window_host_wall", _coerce_identity),
            ("_window_preview_trackers", "window_preview_trackers", _coerce_list),
            ("_plan_region_points", "plan_region_points", _coerce_list),
            ("_plan_region_preview_trackers", "plan_region_preview_trackers", _coerce_list),
        ),
    ),
)


def bind_session_state_accessors(session_class):
    for ensure_method_name, slot_name, state_factory in _PLAN_EDIT_SESSION_STATE_ENSURERS:
        setattr(
            session_class,
            ensure_method_name,
            _make_ensure_state_method(slot_name, state_factory),
        )
    for ensure_method_name, property_specs in _PLAN_EDIT_SESSION_STATE_PROPERTIES:
        for property_name, field_name, coerce in property_specs:
            setattr(
                session_class,
                property_name,
                _make_state_backed_property(ensure_method_name, field_name, coerce),
            )


def initialize_session_read_state(session):
    for _ensure_method_name, slot_name, state_factory in _PLAN_EDIT_SESSION_STATE_ENSURERS:
        setattr(session, slot_name, state_factory())


def initialize_session_state(session):
    """Populate the runtime state owned by a PlanEditSession instance."""
    from PySide import QtGui

    session.doc = FreeCAD.ActiveDocument
    session.gui_doc = FreeCADGui.ActiveDocument
    session.view = None
    session.viewer = None
    session.task_panel = None
    session._aux_task_panels = []
    initialize_session_read_state(session)
    session.current_tool = "Select"
    session._plan_join_type = "Miter"
    session.storeys = []
    session.active_storey = None
    session._space_region_pick_boundaries = []
    session._space_region_pick_seed_space = None
    session._selection_observer_added = False
    session._document_observer_added = False
    session._pending_selected_wall_reset = False
    session._edit_symbol_start_placement = None
    session._edit_symbol_reference_point = None
    session._ignore_selection_changes = False
    session._render_manager = None
    session._finishing = False
    session._tearing_down = False
    session._teardown_signal_sources = []
    session._plan_edit_params = FreeCAD.ParamGet(
        "User parameter:BaseApp/Preferences/Mod/BIM/PlanEdit"
    )
    session._plan_perf_log_path = session._resolve_plan_perf_log_path()
    session._plan_pick_debug_log_path = session._resolve_plan_pick_debug_log_path()
    session._plan_perf_current_event = None
    session._plan_perf_sequence = 0
    session._plan_pick_debug_sequence = 0
    session._plan_pick_debug_scope_depth = 0
    session._plan_pick_debug_scope_name = ""
    session._plan_provider_refresh_cache = None
    session._plan_provider_document_cache = {}
    session._plan_provider_target_collection_depth = 0
    session._connect_teardown_signals(QtGui)
