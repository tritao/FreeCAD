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
