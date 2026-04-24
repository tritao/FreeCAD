# SPDX-License-Identifier: LGPL-2.1-or-later

"""Overlay geometry and cache helpers for BIM Plan Edit."""

import ArchPlanGeometry


def get_plan_overlay_geometry_kinds_for_object(session, obj):
    semantic_obj = session._get_plan_semantic_object(obj)
    if session._is_hosted_opening_object(semantic_obj):
        return ("opening",)
    if session._is_plan_space_object(semantic_obj):
        return ("space",)
    if session._is_plan_region_object(semantic_obj):
        return ("region",)
    return ()


def get_plan_overlay_geometry_cache_entry(session, kind, obj, create=False):
    cache = session.overlay_cache_state.plan_overlay_geometry_cache.get(str(kind or ""))
    semantic_obj = session._get_plan_semantic_object(obj)
    if cache is None or semantic_obj is None:
        return (None, None, None)
    key = session._get_document_object_key(semantic_obj)
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
            target_kinds = session._get_plan_overlay_geometry_kinds_for_object(obj)
    if not target_kinds:
        return
    if obj is None:
        for kind in target_kinds:
            cache = session.overlay_cache_state.plan_overlay_geometry_cache.get(kind)
            if cache is not None:
                cache.clear()
        session._invalidate_opening_overlay_screen_cache()
        session._invalidate_hovered_opening_overlay_cache()
        session._invalidate_selected_opening_overlay_cache()
        session._invalidate_selected_space_overlay_cache()
        return
    semantic_obj, key, _entry = session._get_plan_overlay_geometry_cache_entry(
        target_kinds[0], obj, create=False
    )
    if key is None:
        return
    for kind in target_kinds:
        cache = session.overlay_cache_state.plan_overlay_geometry_cache.get(kind)
        if cache is not None:
            cache.pop(key, None)
    if "opening" in target_kinds:
        session._invalidate_opening_overlay_screen_cache()
    if session.hovered_opening == semantic_obj:
        session._invalidate_hovered_opening_overlay_cache()
    if session._is_selected_plan_target("opening", semantic_obj):
        session._invalidate_selected_opening_overlay_cache()
    if session._is_selected_plan_target("space", semantic_obj):
        session._invalidate_selected_space_overlay_cache()


def get_cached_plan_overlay_geometry(session, kind, obj, field_name, compute):
    semantic_obj, _key, entry = session._get_plan_overlay_geometry_cache_entry(
        kind, obj, create=True
    )
    if semantic_obj is None or entry is None:
        return ()
    if field_name in entry:
        session._plan_perf_count(f"{kind}_{field_name}_cache_hits")
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
    if not proxy or not hasattr(proxy, "getFootprint"):
        return []
    try:
        faces = proxy.getFootprint(wall) or []
    except Exception:
        return []
    return session._get_footprint_overlay_polylines(faces)


def get_space_footprint_faces(session, space):
    if not session._is_plan_space_object(space):
        return ()

    def compute(space_obj):
        proxy = getattr(space_obj, "Proxy", None)
        if not proxy or not hasattr(proxy, "getFootprint"):
            return ()
        try:
            return proxy.getFootprint(space_obj) or ()
        except Exception:
            return ()

    return session._get_cached_plan_overlay_geometry(
        "space",
        space,
        "footprint_faces",
        compute,
    )


def get_space_overlay_polylines(session, space):
    if not session._is_plan_space_object(space):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "space",
        space,
        "overlay_polylines",
        lambda space_obj: session._get_footprint_overlay_polylines(
            session._get_space_footprint_faces(space_obj)
        ),
    )


def get_region_footprint_faces(session, region):
    if not session._is_plan_region_object(region):
        return ()

    def compute(region_obj):
        proxy = getattr(region_obj, "Proxy", None)
        if not proxy or not hasattr(proxy, "getFootprint"):
            return ()
        try:
            return proxy.getFootprint(region_obj) or ()
        except Exception:
            return ()

    return session._get_cached_plan_overlay_geometry(
        "region",
        region,
        "footprint_faces",
        compute,
    )


def get_region_overlay_polylines(session, region):
    if not session._is_plan_region_object(region):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "region",
        region,
        "overlay_polylines",
        lambda region_obj: session._get_footprint_overlay_polylines(
            session._get_region_footprint_faces(region_obj)
        ),
    )


def _compute_opening_overlay_geometry(opening_obj):
    view_object = getattr(opening_obj, "ViewObject", None)
    proxy = getattr(view_object, "Proxy", None)
    if not proxy:
        return {"symbol_polylines": (), "guide_polylines": ()}
    try:
        if hasattr(proxy, "get_plan_overlay_geometry"):
            return proxy.get_plan_overlay_geometry() or {}
        if hasattr(proxy, "get_plan_overlay_polylines"):
            return {
                "symbol_polylines": proxy.get_plan_overlay_polylines() or (),
                "guide_polylines": (),
            }
    except Exception:
        return {"symbol_polylines": (), "guide_polylines": ()}
    return {"symbol_polylines": (), "guide_polylines": ()}


def get_opening_overlay_polylines(session, opening):
    if not session._is_hosted_opening_object(opening):
        return ()

    geometry = session._get_cached_plan_overlay_geometry(
        "opening",
        opening,
        "overlay_geometry",
        _compute_opening_overlay_geometry,
    )
    return tuple(geometry.get("symbol_polylines", ()))


def get_opening_guide_polylines(session, opening):
    if not session._is_hosted_opening_object(opening):
        return ()

    return session._get_cached_plan_overlay_geometry(
        "opening",
        opening,
        "guide_overlay_polylines",
        lambda opening_obj: session._get_cached_plan_overlay_geometry(
            "opening",
            opening_obj,
            "overlay_geometry",
            _compute_opening_overlay_geometry,
        ).get("guide_polylines", ()),
    )


def get_opening_overlay_screen_polylines(session, opening):
    if not session._is_hosted_opening_object(opening) or not session.view:
        return ()
    projection_key = session.viewport.get_plan_projection_cache_key()
    if projection_key is None:
        return ()
    cache_state = session.overlay_cache_state
    if projection_key != cache_state.opening_overlay_screen_cache_projection_key:
        cache_state.opening_overlay_screen_cache = {}
        cache_state.opening_overlay_screen_cache_projection_key = projection_key
    opening_key = session._get_document_object_key(opening)
    if opening_key is None:
        return ()
    cached = cache_state.opening_overlay_screen_cache.get(opening_key)
    if cached is not None:
        session._plan_perf_count("opening_overlay_screen_polylines_cache_hits")
        return cached

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
    cache_state.opening_overlay_screen_cache[opening_key] = result
    return result


def get_region_overlay_segments(session, region):
    if not session._is_plan_region_object(region):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "region",
        region,
        "overlay_segments",
        lambda region_obj: session._build_overlay_segments_from_polylines(
            get_region_overlay_polylines(session, region_obj)
        ),
    )


def get_space_overlay_segments(session, space):
    if not session._is_plan_space_object(space):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "space",
        space,
        "overlay_segments",
        lambda space_obj: session._build_overlay_segments_from_polylines(
            get_space_overlay_polylines(session, space_obj)
        ),
    )


def get_opening_overlay_segments(session, opening):
    if not session._is_hosted_opening_object(opening):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "opening",
        opening,
        "symbol_overlay_segments",
        lambda opening_obj: session._build_overlay_segments_from_polylines(
            session._get_opening_overlay_polylines(opening_obj)
        ),
    )


def get_opening_combined_overlay_polylines(session, opening):
    if not session._is_hosted_opening_object(opening):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "opening",
        opening,
        "combined_overlay_polylines",
        lambda opening_obj: tuple(session._get_opening_overlay_polylines(opening_obj))
        + tuple(get_opening_guide_polylines(session, opening_obj)),
    )


def get_opening_combined_overlay_segments(session, opening):
    if not session._is_hosted_opening_object(opening):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "opening",
        opening,
        "combined_overlay_segments",
        lambda opening_obj: session._build_overlay_segments_from_polylines(
            get_opening_combined_overlay_polylines(session, opening_obj)
        ),
    )


def get_opening_pick_polylines(session, opening):
    if not session._is_hosted_opening_object(opening):
        return ()
    return session._get_cached_plan_overlay_geometry(
        "opening",
        opening,
        "pick_overlay_polylines",
        lambda opening_obj: get_opening_combined_overlay_polylines(session, opening_obj),
    )
