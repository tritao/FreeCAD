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
from bimplan import provider_runtime as plan_provider_runtime


@dataclass
class PlanTaskPanelState:
    relation_status_message: str | None = None
    space_region_candidates: list = field(default_factory=list)
    hovered_space_region_candidate: object = None
    plan_region_parent_space: object = None


@dataclass
class PlanProviderOverlayReadState:
    mode: str = "architecture"
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


def initialize_session_read_state(session):
    session.task_panel_state = PlanTaskPanelState()
    session.provider_overlay_read_state = PlanProviderOverlayReadState(
        mode=plan_provider_runtime.PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE
    )
    session.interaction_state = PlanInteractionState()
    session.selection_state = PlanSelectionState()
    session.wall_edit_state = PlanWallEditState()


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
    session._viewport_status_chip = None
    session.current_tool = "Select"
    session._plan_join_type = "Miter"
    session.storeys = []
    session.active_storey = None
    session._hover_pick_dirty = False
    session._hover_pick_last_time = 0.0
    session._hover_pick_last_mouse_pos = None
    session._space_region_pick_boundaries = []
    session._space_region_pick_seed_space = None
    session._grip_trackers = []
    session._wall_grip_state = None
    session._wall_grip_sync_queued = False
    session._wall_grip_sync_generation = 0
    session._wall_hover_trackers = []
    session._wall_overlay_trackers = []
    session._junction_node_trackers = []
    session._hovered_wall_opening_context_trackers = []
    session._opening_hover_trackers = []
    session._symbol_hover_trackers = []
    session._provider_hover_trackers = []
    session._provider_selected_trackers = []
    session._space_hover_trackers = []
    session._region_hover_trackers = []
    session._plan_overlay_geometry_cache = {
        "opening": {},
        "space": {},
        "region": {},
    }
    session._plan_semantic_object_cache = {}
    session._plan_object_storeys_cache = {}
    session._plan_symbol_instances_cache = None
    session._plan_space_instances_cache = None
    session._plan_region_instances_cache = None
    session._plan_opening_instances_cache = None
    session._wall_hosted_openings_cache = None
    session._wall_hosted_openings_cache_queued = False
    session._plan_hover_pick_cache_queued = False
    session._opening_overlay_screen_cache = {}
    session._opening_overlay_screen_cache_projection_key = None
    session._symbol_overlay_screen_cache = {}
    session._opening_overlay_trackers = []
    session._hovered_opening_overlay_dirty = False
    session._hovered_opening_overlay_render_state = None
    session._selected_opening_overlay_dirty = False
    session._selected_opening_overlay_render_state = None
    session._symbol_overlay_trackers = []
    session._space_overlay_trackers = []
    session._selected_space_overlay_dirty = True
    session._selected_space_overlay_geometry_key = None
    session._selected_space_overlay_segments = ()
    session._selected_space_overlay_render_state = None
    session._region_overlay_trackers = []
    session._provider_overlay_trackers = []
    session._selected_provider_overlay_render_state = None
    session._provider_handle_trackers = []
    session._selected_provider_handle_render_state = None
    session._provider_selected_objects = []
    session._provider_point_host_target = None
    session._provider_point_host_source = ""
    session._provider_point_preview_trackers = []
    session._provider_point_preview_render_state = None
    session._provider_point_preview_style_state = None
    session._provider_point_preview_source_point = None
    session._provider_point_preview_point = None
    session._provider_point_preview_host_target = None
    session._provider_point_preview_host_source = ""
    session._secondary_selection_trackers = []
    session._space_region_pick_trackers = []
    session._selected_wall_opening_context_trackers = []
    session._opening_handle_trackers = []
    session._opening_handle_tracker_pool = []
    session._opening_handle_tracker_pool_queued = False
    session._selected_opening_handle_render_state = None
    session._symbol_handle_trackers = []
    session._selected_opening_hard_refresh_queued = False
    session._opening_host_recompute_queued = False
    session._opening_host_recompute_running = False
    session._opening_move_preview_trackers = []
    session._symbol_edit_preview_trackers = []
    session._opening_move_snap_profile_pushed = False
    session._edit_opening_move_anchor = "center"
    session._edit_opening_move_raw_point = None
    session._selection_observer_added = False
    session._selection_refresh_queued = False
    session._gui_selection_sync_queued = False
    session._gui_selection_sync_generation = 0
    session._queued_gui_selection_object = None
    session._document_observer_added = False
    session._pending_created_plan_objects = {}
    session._created_plan_objects_flush_queued = False
    session._created_plan_objects_flush_deferred = False
    session._document_visual_update_defer_depth = 0
    session._document_visual_refresh_deferred = False
    session._pending_selected_wall_reset = False
    session._rect_wall_start = None
    session._rect_wall_params = None
    session._rect_wall_preview_trackers = []
    session._space_separator_start = None
    session._space_separator_height = None
    session._space_separator_preview_trackers = []
    session._window_host_wall = None
    session._window_preview_trackers = []
    session._plan_region_points = []
    session._plan_region_preview_trackers = []
    session._edit_symbol_start_placement = None
    session._edit_symbol_reference_point = None
    session._ignore_selection_changes = False
    session._mouse_moved_cb = None
    session._mouse_wheel_cb = None
    session._mouse_wheel_event_type = None
    session._mouse_pressed_cb = None
    session._consume_left_button_release = False
    session._key_pressed_cb = None
    session._overlay_refresh_queued = False
    session._view_scale_overlay_refresh_queued = False
    session._dirty_plan_visuals = set()
    session._render_manager = None
    session._saved_camera = None
    session._saved_camera_type = None
    session._saved_navigation_style = None
    session._saved_navigation_state = {}
    session._saved_view_action_state = {}
    session._saved_preselection_state = None
    session._plan_preselection_forced = False
    session._saved_object_view_state = {}
    session._working_plane = None
    session._interaction_plane = None
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
