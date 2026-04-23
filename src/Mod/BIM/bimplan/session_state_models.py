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
