# SPDX-License-Identifier: LGPL-2.1-or-later

"""Owned overlay API surface for BIM Plan Edit."""

from functools import wraps

from bimplan.overlays import geometry as overlay_geometry
from bimplan.overlays import symbols as symbol_overlays


def _bind_overlay_call(func):
    @wraps(func)
    def method(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    return method


_PLAN_OVERLAYS_API_BOUND_METHODS = (
    "get_space_footprint_faces",
    "get_space_overlay_polylines",
    "get_space_overlay_segments",
    "get_region_footprint_faces",
    "get_region_overlay_polylines",
    "get_region_overlay_segments",
    "get_opening_overlay_polylines",
    "get_opening_overlay_screen_polylines",
    "get_opening_overlay_segments",
    "get_plan_symbol_instances",
    "get_symbol_overlay_segments",
    "get_symbol_overlay_screen_polylines",
)


class PlanOverlaysAPI:
    """Owned session surface for Plan Edit overlay reads."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


for _method_name in _PLAN_OVERLAYS_API_BOUND_METHODS:
    if hasattr(overlay_geometry, _method_name):
        _method = getattr(overlay_geometry, _method_name)
    else:
        _method = getattr(symbol_overlays, _method_name)
    setattr(PlanOverlaysAPI, _method_name, _bind_overlay_call(_method))
