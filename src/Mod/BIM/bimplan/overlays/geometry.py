# SPDX-License-Identifier: LGPL-2.1-or-later

"""Overlay geometry and cache helpers for BIM Plan Edit."""

import ArchPlanGeometry
from bimplan.overlays import openings as opening_overlays
from bimplan.overlays import spaces as space_overlays


class PlanOverlayGeometryService:
    """Owned session surface for overlay geometry queries."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def get_footprint_overlay_polylines(self, *args, **kwargs):
        return get_footprint_overlay_polylines(*args, **kwargs)

    def build_overlay_segments_from_polylines(self, *args, **kwargs):
        return build_overlay_segments_from_polylines(*args, **kwargs)

    def get_plan_overlay_geometry_kinds_for_object(self, *args, **kwargs):
        return get_plan_overlay_geometry_kinds_for_object(self.session, *args, **kwargs)

    def get_plan_overlay_geometry_cache_entry(self, *args, **kwargs):
        return get_plan_overlay_geometry_cache_entry(self.session, *args, **kwargs)

    def invalidate_plan_overlay_geometry_cache(self, *args, **kwargs):
        return invalidate_plan_overlay_geometry_cache(self.session, *args, **kwargs)

    def get_cached_plan_overlay_geometry(self, *args, **kwargs):
        return get_cached_plan_overlay_geometry(self.session, *args, **kwargs)

    def get_wall_overlay_polylines(self, *args, **kwargs):
        return get_wall_overlay_polylines(self.session, *args, **kwargs)

    def get_wall_overlay_segments(self, *args, **kwargs):
        return get_wall_overlay_segments(self.session, *args, **kwargs)

    def get_space_footprint_faces(self, *args, **kwargs):
        return get_space_footprint_faces(self.session, *args, **kwargs)

    def get_space_overlay_polylines(self, *args, **kwargs):
        return get_space_overlay_polylines(self.session, *args, **kwargs)

    def get_space_overlay_segments(self, *args, **kwargs):
        return get_space_overlay_segments(self.session, *args, **kwargs)

    def get_region_footprint_faces(self, *args, **kwargs):
        return get_region_footprint_faces(self.session, *args, **kwargs)

    def get_region_overlay_polylines(self, *args, **kwargs):
        return get_region_overlay_polylines(self.session, *args, **kwargs)

    def get_region_overlay_segments(self, *args, **kwargs):
        return get_region_overlay_segments(self.session, *args, **kwargs)

    def get_opening_overlay_polylines(self, *args, **kwargs):
        return get_opening_overlay_polylines(self.session, *args, **kwargs)

    def get_opening_overlay_screen_polylines(self, *args, **kwargs):
        return get_opening_overlay_screen_polylines(self.session, *args, **kwargs)

    def get_opening_overlay_screen_bounds(self, *args, **kwargs):
        return get_opening_overlay_screen_bounds(self.session, *args, **kwargs)

    def get_opening_pick_bounds(self, *args, **kwargs):
        return get_opening_pick_bounds(self.session, *args, **kwargs)

    def get_opening_overlay_segments(self, *args, **kwargs):
        return get_opening_overlay_segments(self.session, *args, **kwargs)


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def get_plan_overlay_geometry_kinds_for_object(session, obj):
    semantic_obj = session.visibility.get_plan_semantic_object(obj)
    if session.selection.targets.is_plan_selectable_wall(semantic_obj):
        return ("wall",)
    if session.openings.is_hosted_opening_object(semantic_obj):
        return ("opening",)
    if session.selection.targets.is_plan_space_object(semantic_obj):
        return ("space",)
    if session.selection.targets.is_plan_region_object(semantic_obj):
        return ("region",)
    return ()


def get_plan_overlay_geometry_cache_entry(session, kind, obj, create=False):
    cache = session.overlay_cache_state.plan_overlay_geometry_cache.get(str(kind or ""))
    semantic_obj = session.visibility.get_plan_semantic_object(obj)
    if cache is None or semantic_obj is None:
        return (None, None, None)
    key = session.visibility.get_document_object_key(semantic_obj)
    if key is None:
        return (semantic_obj, None, None)
    entry = cache.get(key)
    if entry is None and create:
        entry = {}
        cache[key] = entry
    return (semantic_obj, key, entry)


def invalidate_plan_overlay_geometry_cache(session, obj=None, kinds=None):
    target_kinds = tuple(kinds or ())
    if not target_kinds:
        if obj is None:
            target_kinds = tuple(session.overlay_cache_state.plan_overlay_geometry_cache.keys())
        else:
            target_kinds = get_plan_overlay_geometry_kinds_for_object(session, obj)
    if not target_kinds:
        return
    if obj is None:
        for kind in target_kinds:
            cache = session.overlay_cache_state.plan_overlay_geometry_cache.get(kind)
            if cache is not None:
                cache.clear()
        invalidate_opening_overlay_screen_cache(session)
        opening_overlays.invalidate_hovered_opening_overlay_cache(session)
        opening_overlays.invalidate_selected_opening_overlay_cache(session)
        space_overlays.invalidate_selected_space_overlay_cache(session)
        return
    semantic_obj, key, _entry = get_plan_overlay_geometry_cache_entry(
        session, target_kinds[0], obj, create=False
    )
    if key is None:
        return
    for kind in target_kinds:
        cache = session.overlay_cache_state.plan_overlay_geometry_cache.get(kind)
        if cache is not None:
            cache.pop(key, None)
    if "opening" in target_kinds:
        invalidate_opening_overlay_screen_cache(session)
    if session.hovered_opening == semantic_obj:
        opening_overlays.invalidate_hovered_opening_overlay_cache(session)
    if session.selection.state.is_selected_plan_target("opening", semantic_obj):
        opening_overlays.invalidate_selected_opening_overlay_cache(session)
    if session.selection.state.is_selected_plan_target("space", semantic_obj):
        space_overlays.invalidate_selected_space_overlay_cache(session)


def get_cached_plan_overlay_geometry(session, kind, obj, field_name, compute):
    semantic_obj, _key, entry = get_plan_overlay_geometry_cache_entry(
        session, kind, obj, create=True
    )
    if semantic_obj is None or entry is None:
        return ()
    if field_name in entry:
        _perf_count(session, f"{kind}_{field_name}_cache_hits")
        return entry[field_name]
    value = compute(semantic_obj)
    if field_name == "footprint_faces":
        value = tuple(value or ())
    elif field_name.endswith("overlay_polylines"):
        value = tuple(tuple(polyline or ()) for polyline in (value or ()))
    elif field_name == "overlay_geometry":
        value = {
            "symbol_polylines": tuple(
                tuple(polyline or ()) for polyline in ((value or {}).get("symbol_polylines") or ())
            ),
            "guide_polylines": tuple(
                tuple(polyline or ()) for polyline in ((value or {}).get("guide_polylines") or ())
            ),
        }
    elif field_name.endswith("overlay_segments"):
        value = tuple(value or ())
    entry[field_name] = value
    return value


def invalidate_opening_overlay_screen_cache(session):
    state = session.overlay_cache_state
    state.opening_overlay_screen_cache = {}
    state.opening_overlay_screen_cache_projection_key = None


def _get_projected_polyline_bounds(projected_polylines):
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    for polyline in projected_polylines or ():
        for point in polyline or ():
            try:
                point_x = float(point[0])
                point_y = float(point[1])
            except Exception:
                continue
            min_x = point_x if min_x is None else min(min_x, point_x)
            min_y = point_y if min_y is None else min(min_y, point_y)
            max_x = point_x if max_x is None else max(max_x, point_x)
            max_y = point_y if max_y is None else max(max_y, point_y)
    if min_x is None:
        return None
    return (min_x, min_y, max_x, max_y)


def _get_plan_polyline_bounds(polylines):
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    for polyline in polylines or ():
        for point in polyline or ():
            try:
                point_x = float(point.x)
                point_y = float(point.y)
            except Exception:
                continue
            min_x = point_x if min_x is None else min(min_x, point_x)
            min_y = point_y if min_y is None else min(min_y, point_y)
            max_x = point_x if max_x is None else max(max_x, point_x)
            max_y = point_y if max_y is None else max(max_y, point_y)
    if min_x is None:
        return None
    return (min_x, min_y, max_x, max_y)


def _get_proxy_method(proxy, method_name):
    method = getattr(proxy, method_name, None)
    return method if callable(method) else None


def _get_proxy_footprint(proxy, obj):
    get_footprint = _get_proxy_method(proxy, "getFootprint")
    if get_footprint is None:
        return ()
    try:
        return get_footprint(obj) or ()
    except Exception:
        return ()


def get_footprint_overlay_polylines(faces):
    return ArchPlanGeometry.get_face_wire_polylines(faces)


def build_overlay_segments_from_polylines(polylines):
    segments = []
    for polyline in polylines or ():
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            segments.append((start, end))
    return tuple(segments)


def get_wall_overlay_polylines(session, wall):
    if not wall:
        return []
    proxy = getattr(wall, "Proxy", None)
    faces = _get_proxy_footprint(proxy, wall)
    if not faces:
        return []
    return get_footprint_overlay_polylines(faces)


def get_wall_overlay_segments(session, wall):
    if not session.selection.targets.is_plan_selectable_wall(wall):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "wall",
        wall,
        "overlay_segments",
        lambda wall_obj: build_overlay_segments_from_polylines(
            get_wall_overlay_polylines(session, wall_obj)
        ),
    )


def get_space_footprint_faces(session, space):
    if not session.selection.targets.is_plan_space_object(space):
        return ()

    def compute(space_obj):
        proxy = getattr(space_obj, "Proxy", None)
        return _get_proxy_footprint(proxy, space_obj)

    return get_cached_plan_overlay_geometry(
        session,
        "space",
        space,
        "footprint_faces",
        compute,
    )


def get_space_overlay_polylines(session, space):
    if not session.selection.targets.is_plan_space_object(space):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "space",
        space,
        "overlay_polylines",
        lambda space_obj: get_footprint_overlay_polylines(
            get_space_footprint_faces(session, space_obj)
        ),
    )


def get_region_footprint_faces(session, region):
    if not session.selection.targets.is_plan_region_object(region):
        return ()

    def compute(region_obj):
        proxy = getattr(region_obj, "Proxy", None)
        return _get_proxy_footprint(proxy, region_obj)

    return get_cached_plan_overlay_geometry(
        session,
        "region",
        region,
        "footprint_faces",
        compute,
    )


def get_region_overlay_polylines(session, region):
    if not session.selection.targets.is_plan_region_object(region):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "region",
        region,
        "overlay_polylines",
        lambda region_obj: get_footprint_overlay_polylines(
            get_region_footprint_faces(session, region_obj)
        ),
    )


def _compute_opening_overlay_geometry(opening_obj):
    view_object = getattr(opening_obj, "ViewObject", None)
    proxy = getattr(view_object, "Proxy", None)
    if not proxy:
        return {"symbol_polylines": (), "guide_polylines": ()}
    try:
        get_plan_overlay_geometry = _get_proxy_method(proxy, "get_plan_overlay_geometry")
        if get_plan_overlay_geometry is not None:
            return get_plan_overlay_geometry() or {}
        get_plan_overlay_polylines = _get_proxy_method(proxy, "get_plan_overlay_polylines")
        if get_plan_overlay_polylines is not None:
            return {
                "symbol_polylines": get_plan_overlay_polylines() or (),
                "guide_polylines": (),
            }
    except Exception:
        return {"symbol_polylines": (), "guide_polylines": ()}
    return {"symbol_polylines": (), "guide_polylines": ()}


def get_opening_overlay_polylines(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return ()

    geometry = get_cached_plan_overlay_geometry(
        session,
        "opening",
        opening,
        "overlay_geometry",
        _compute_opening_overlay_geometry,
    )
    return tuple(geometry.get("symbol_polylines", ()))


def get_opening_guide_polylines(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return ()

    return get_cached_plan_overlay_geometry(
        session,
        "opening",
        opening,
        "guide_overlay_polylines",
        lambda opening_obj: get_cached_plan_overlay_geometry(
            session,
            "opening",
            opening_obj,
            "overlay_geometry",
            _compute_opening_overlay_geometry,
        ).get("guide_polylines", ()),
    )


def get_opening_overlay_screen_polylines(session, opening):
    if not session.openings.is_hosted_opening_object(opening) or not session.view:
        return ()
    projection_key = session.viewport.get_plan_projection_cache_key()
    if projection_key is None:
        return ()
    cache_state = session.overlay_cache_state
    if projection_key != cache_state.opening_overlay_screen_cache_projection_key:
        cache_state.opening_overlay_screen_cache = {}
        cache_state.opening_overlay_screen_cache_projection_key = projection_key
    opening_key = session.visibility.get_document_object_key(opening)
    if opening_key is None:
        return ()
    cached = cache_state.opening_overlay_screen_cache.get(opening_key)
    if cached is not None:
        _perf_count(session, "opening_overlay_screen_polylines_cache_hits")
        return cached[0]

    projected_polylines = []
    for polyline in get_opening_pick_polylines(session, opening):
        if len(polyline) < 2:
            continue
        projected = []
        try:
            for poly_point in polyline:
                screen_point = session.view.getPointOnScreen(poly_point)
                projected.append((float(screen_point[0]), float(screen_point[1])))
        except Exception:
            projected = []
        if len(projected) >= 2:
            projected_polylines.append(tuple(projected))
    result = tuple(projected_polylines)
    cache_state.opening_overlay_screen_cache[opening_key] = (
        result,
        _get_projected_polyline_bounds(result),
    )
    return result


def get_opening_overlay_screen_bounds(session, opening):
    if not session.openings.is_hosted_opening_object(opening) or not session.view:
        return None
    projection_key = session.viewport.get_plan_projection_cache_key()
    if projection_key is None:
        return None
    cache_state = session.overlay_cache_state
    if projection_key != cache_state.opening_overlay_screen_cache_projection_key:
        cache_state.opening_overlay_screen_cache = {}
        cache_state.opening_overlay_screen_cache_projection_key = projection_key
    opening_key = session.visibility.get_document_object_key(opening)
    if opening_key is None:
        return None
    cached = cache_state.opening_overlay_screen_cache.get(opening_key)
    if cached is None:
        get_opening_overlay_screen_polylines(session, opening)
        cached = cache_state.opening_overlay_screen_cache.get(opening_key)
    if cached is None:
        return None
    return cached[1]


def get_region_overlay_segments(session, region):
    if not session.selection.targets.is_plan_region_object(region):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "region",
        region,
        "overlay_segments",
        lambda region_obj: build_overlay_segments_from_polylines(
            get_region_overlay_polylines(session, region_obj)
        ),
    )


def get_space_overlay_segments(session, space):
    if not session.selection.targets.is_plan_space_object(space):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "space",
        space,
        "overlay_segments",
        lambda space_obj: build_overlay_segments_from_polylines(
            get_space_overlay_polylines(session, space_obj)
        ),
    )


def get_opening_overlay_segments(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "opening",
        opening,
        "symbol_overlay_segments",
        lambda opening_obj: build_overlay_segments_from_polylines(
            get_opening_overlay_polylines(session, opening_obj)
        ),
    )


def get_opening_combined_overlay_polylines(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "opening",
        opening,
        "combined_overlay_polylines",
        lambda opening_obj: tuple(get_opening_overlay_polylines(session, opening_obj))
        + tuple(get_opening_guide_polylines(session, opening_obj)),
    )


def get_opening_combined_overlay_segments(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "opening",
        opening,
        "combined_overlay_segments",
        lambda opening_obj: build_overlay_segments_from_polylines(
            get_opening_combined_overlay_polylines(session, opening_obj)
        ),
    )


def get_opening_pick_polylines(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return ()
    return get_cached_plan_overlay_geometry(
        session,
        "opening",
        opening,
        "pick_overlay_polylines",
        lambda opening_obj: get_opening_combined_overlay_polylines(session, opening_obj),
    )


def get_opening_pick_bounds(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return None
    return get_cached_plan_overlay_geometry(
        session,
        "opening",
        opening,
        "pick_overlay_bounds",
        lambda opening_obj: _get_plan_polyline_bounds(
            get_opening_pick_polylines(session, opening_obj)
        ),
    )
