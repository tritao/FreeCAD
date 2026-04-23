# SPDX-License-Identifier: LGPL-2.1-or-later

"""Typed mutable state buckets for BIM Plan Edit sessions."""

from __future__ import annotations

from dataclasses import dataclass, field


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
