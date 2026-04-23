# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider overlay mode and visibility helpers for BIM Plan Edit."""

from __future__ import annotations

from . import selection as plan_selection
from . import visual_keys as plan_visual_keys

PLAN_PROVIDER_OVERLAY_MODE_ALL = "all"
PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE = "architecture"
PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL = "electrical"
PLAN_PROVIDER_OVERLAY_MODE_PLUMBING = "plumbing"
_PLAN_VISUAL_PROVIDER_OVERLAYS = plan_visual_keys.PLAN_VISUAL_PROVIDER_OVERLAYS


def get_plan_provider_overlay_visibility_key(provider_id, overlay_key):
    provider_id = str(provider_id or "").strip()
    overlay_key = str(overlay_key or "").strip()
    if not provider_id or not overlay_key:
        return None
    return (provider_id, overlay_key)


def normalize_plan_provider_overlay_mode(mode):
    normalized = str(mode or "").strip().lower()
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_ALL:
        return PLAN_PROVIDER_OVERLAY_MODE_ALL
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
        return PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
        return PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
    return PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE


def get_plan_provider_overlay_mode(session):
    return normalize_plan_provider_overlay_mode(
        getattr(session, "_provider_overlay_mode", PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE)
    )


def set_plan_provider_overlay_mode(session, mode):
    normalized = normalize_plan_provider_overlay_mode(mode)
    if normalized == get_plan_provider_overlay_mode(session):
        return False
    session._provider_overlay_mode = normalized
    session._provider_overlay_state = None
    plan_selection.clear_hidden_provider_preselection(session)
    session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)
    session._refresh_provider_overlay_mode_panels()
    return True


def get_plan_provider_overlay_category(overlay):
    category = str(getattr(overlay, "category", "") or "").strip().lower()
    if category == PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
        return PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
    if category == PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
        return PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
    return PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE


def is_plan_provider_overlay_enabled(session, overlay):
    key = get_plan_provider_overlay_visibility_key(
        getattr(overlay, "provider_id", ""),
        getattr(overlay, "key", ""),
    )
    if key is None:
        return True
    return getattr(session, "_provider_overlay_visibility", {}).get(key, True)


def is_plan_provider_overlay_visible_for_mode(session, overlay, mode=None):
    overlay_mode = normalize_plan_provider_overlay_mode(
        get_plan_provider_overlay_mode(session) if mode is None else mode
    )
    if overlay_mode == PLAN_PROVIDER_OVERLAY_MODE_ALL:
        return True
    return get_plan_provider_overlay_category(overlay) == overlay_mode


def is_plan_provider_overlay_visible(session, overlay):
    if not bool(getattr(overlay, "visible", True)):
        return False
    if not is_plan_provider_overlay_enabled(session, overlay):
        return False
    return is_plan_provider_overlay_visible_for_mode(session, overlay)


def set_plan_provider_overlay_visible(session, provider_id, overlay_key, visible):
    key = get_plan_provider_overlay_visibility_key(provider_id, overlay_key)
    if key is None:
        return
    visible = bool(visible)
    if visible:
        session._provider_overlay_visibility.pop(key, None)
    else:
        session._provider_overlay_visibility[key] = False
    session._provider_overlay_state = None
    session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)


def queue_plan_provider_overlay_refresh(session):
    session._provider_overlay_state = None
    session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)


def queue_plan_provider_overlay_sync(session):
    session._queue_plan_overlay_visual_refresh(_PLAN_VISUAL_PROVIDER_OVERLAYS)
