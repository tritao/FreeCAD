# SPDX-License-Identifier: LGPL-2.1-or-later

"""State owned by the BIM Plan Edit runtime."""

from dataclasses import dataclass, field


@dataclass
class PlanOverlayRefreshState:
    """Coalesced dirty state for Plan's viewer-local overlays."""

    overlay_refresh_queued: bool = False
    view_scale_overlay_refresh_queued: bool = False
    dirty_plan_visuals: set = field(default_factory=set)


def initialize_plan_overlay_state(session):
    session.overlay_refresh_state = PlanOverlayRefreshState()
