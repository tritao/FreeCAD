# SPDX-License-Identifier: LGPL-2.1-or-later

"""Hover target routing for BIM Plan Edit."""

import time

from bimplan.providers import runtime as plan_provider_runtime
from bimplan.selection import target_dispatch as plan_target_dispatch

_HOVER_PICK_INTERVAL_MS = 80


def get_hovered_plan_target(session):
    return plan_target_dispatch.get_hovered_target(session)


def queue_prime_hover_pick_caches(session):
    if session._tearing_down or session._plan_hover_pick_cache_queued or not session.doc:
        return
    try:
        from PySide import QtCore
    except ImportError:
        return
    session._plan_hover_pick_cache_queued = True
    QtCore.QTimer.singleShot(0, session.selection.prime_hover_pick_caches)


def prime_hover_pick_caches(session):
    session._plan_hover_pick_cache_queued = False
    if session._tearing_down or not session.doc:
        return
    with session.performance.plan_perf_trace_event("prime_hover_pick_caches"):
        with session.performance.plan_perf_trace_span("prime_hover_pick_symbol_instances"):
            symbols = tuple(session.overlays.get_plan_symbol_instances())
        for symbol in symbols:
            session.performance.plan_perf_count("prime_hover_pick_symbols")
            with session.performance.plan_perf_trace_span("prime_hover_pick_symbol_geometry"):
                session.overlays.get_symbol_overlay_segments(symbol)
                session.overlays.get_symbol_overlay_screen_polylines(symbol)

        for obj in getattr(session.doc, "Objects", []) or []:
            if session._is_hosted_opening_object(obj):
                session.performance.plan_perf_count("prime_hover_pick_openings")
                with session.performance.plan_perf_trace_span("prime_hover_pick_opening_geometry"):
                    session.overlays.get_opening_overlay_polylines(obj)
                    session.overlays.get_opening_overlay_segments(obj)
                    session.overlays.get_opening_overlay_screen_polylines(obj)
            if session._is_plan_space_object(obj):
                session.performance.plan_perf_count("prime_hover_pick_spaces")
                with session.performance.plan_perf_trace_span("prime_hover_pick_space_geometry"):
                    session.overlays.get_space_footprint_faces(obj)
                    session.overlays.get_space_overlay_polylines(obj)
                    session.overlays.get_space_overlay_segments(obj)
            if session._is_plan_region_object(obj):
                session.performance.plan_perf_count("prime_hover_pick_regions")
                with session.performance.plan_perf_trace_span("prime_hover_pick_region_geometry"):
                    session.overlays.get_region_footprint_faces(obj)
                    session.overlays.get_region_overlay_polylines(obj)
                    session.overlays.get_region_overlay_segments(obj)

        with session.performance.plan_perf_trace_span("prime_hover_pick_provider_contributions"):
            with session._plan_provider_refresh_cache_scope():
                tuple(session.get_plan_provider_overlays())
                tuple(session.get_plan_provider_targets())


def should_skip_hover_pick(session, mouse_pos, force=False):
    if force or mouse_pos is None:
        return False
    try:
        now = time.monotonic()
    except Exception:
        return False
    elapsed_ms = (now - float(session._hover_pick_last_time or 0.0)) * 1000.0
    if elapsed_ms >= _HOVER_PICK_INTERVAL_MS:
        session._hover_pick_last_time = now
        session._hover_pick_last_mouse_pos = (float(mouse_pos[0]), float(mouse_pos[1]))
        return False
    session._hover_pick_dirty = True
    session._hover_pick_last_mouse_pos = (float(mouse_pos[0]), float(mouse_pos[1]))
    session.performance.plan_perf_count("hover_pick_skipped")
    return True


def clear_hovered_plan_targets(session, kinds=None):
    return plan_target_dispatch.clear_hovered_targets(session, kinds=kinds)


def update_hovered_plan_target(session, mouse_pos, force=False):
    if session.current_tool == "Join":
        if session.selection.should_skip_hover_pick(mouse_pos, force=force):
            return False
        session.performance.plan_perf_count("hover_pick_resolved")
        with session.performance.plan_perf_trace_span("hover_pick_resolve"):
            target_kind, target_obj = session.selection.get_plan_target_at_position(mouse_pos)
        session._hover_pick_dirty = False
        if target_kind == "wall" and not session._is_selected_plan_target("wall", target_obj):
            plan_target_dispatch.set_only_hovered_target(session, target_kind, target_obj)
        else:
            plan_target_dispatch.set_only_hovered_target(session, None, None)
        return True
    if session.current_tool != "Select":
        session._hover_pick_dirty = False
        clear_hovered_plan_targets(session)
        return True
    if session.selection.should_skip_hover_pick(mouse_pos, force=force):
        return False
    session.performance.plan_perf_count("hover_pick_resolved")
    overlay_mode = session.get_plan_provider_overlay_mode()
    include_space_fallback = not plan_provider_runtime.is_focused_provider_overlay_pick_mode(
        overlay_mode
    )
    with session.performance.plan_perf_trace_span("hover_pick_resolve"):
        target_kind, target_obj = session.selection.get_plan_target_at_position(
            mouse_pos,
            include_space_fallback=include_space_fallback,
        )
    session._hover_pick_dirty = False
    plan_target_dispatch.set_only_hovered_target(session, target_kind, target_obj)
    return True
