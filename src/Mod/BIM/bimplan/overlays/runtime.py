# SPDX-License-Identifier: LGPL-2.1-or-later

"""Owned overlay API surface for BIM Plan Edit."""

from bimplan.overlays.manager import PlanOverlayManagerService


class PlanOverlaysAPI:
    """Own the reusable Plan overlay manager for one editing session."""

    def __init__(self, session):
        self._session = session
        self.manager = PlanOverlayManagerService(
            session,
            refresh_callback=self._refresh_plan_overlay_visuals,
        )

    @property
    def session(self):
        return self._session

    def queue_plan_overlay_visual_refresh(self, *visuals):
        return self.manager.queue_plan_overlay_visual_refresh(visuals)

    def _refresh_plan_overlay_visuals(self, dirty):
        callback = getattr(self.session, "refresh_plan_overlay_visuals", None)
        if callable(callback):
            return callback(dirty)
        return None

    def close(self):
        self.manager.close()
