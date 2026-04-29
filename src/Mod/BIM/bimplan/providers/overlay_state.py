# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider overlay mode and visibility state for BIM Plan Edit."""

from bimplan import document_visuals as plan_document_visuals


def _runtime():
    from bimplan.providers import runtime as provider_runtime

    return provider_runtime


PLAN_PROVIDER_OVERLAY_MODE_ALL = "all"
PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE = "architecture"
PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL = "electrical"
PLAN_PROVIDER_OVERLAY_MODE_PLUMBING = "plumbing"
FOCUSED_PROVIDER_OVERLAY_PICK_MODES = frozenset(
    (
        PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL,
        PLAN_PROVIDER_OVERLAY_MODE_PLUMBING,
    )
)


def normalize_plan_provider_overlay_mode(mode):
    normalized = str(mode or "").strip().lower()
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_ALL:
        return PLAN_PROVIDER_OVERLAY_MODE_ALL
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
        return PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
    if normalized == PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
        return PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
    return PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE


def _provider_overlay_read_state(session):
    return session.provider_overlay_read_state


def get_plan_provider_overlay_mode(session):
    provider_runtime = _runtime()
    external_mode = provider_runtime._call_provider_method(
        session, "get_plan_provider_overlay_mode", default=None
    )
    if external_mode is not None:
        return normalize_plan_provider_overlay_mode(external_mode)
    return normalize_plan_provider_overlay_mode(_provider_overlay_read_state(session).mode)


def is_focused_provider_overlay_pick_mode(mode):
    return normalize_plan_provider_overlay_mode(mode) in FOCUSED_PROVIDER_OVERLAY_PICK_MODES


def set_plan_provider_overlay_mode(session, mode):
    provider_runtime = _runtime()
    normalized = normalize_plan_provider_overlay_mode(mode)
    if normalized == get_plan_provider_overlay_mode(session):
        return False
    overlay_state = _provider_overlay_read_state(session)
    overlay_state.mode = normalized
    overlay_state.render_state = None
    provider_runtime.invalidate_plan_provider_document_cache(session)
    session.selection.refresh.clear_hidden_provider_preselection()
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )
    session.task_panels.refresh_provider_overlay_mode_panels()
    return True


def get_plan_provider_overlay_category(overlay):
    category = str(getattr(overlay, "category", "") or "").strip().lower()
    if category == PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL:
        return PLAN_PROVIDER_OVERLAY_MODE_ELECTRICAL
    if category == PLAN_PROVIDER_OVERLAY_MODE_PLUMBING:
        return PLAN_PROVIDER_OVERLAY_MODE_PLUMBING
    return PLAN_PROVIDER_OVERLAY_MODE_ARCHITECTURE


def is_plan_provider_overlay_enabled(session, overlay):
    provider_runtime = _runtime()
    key = provider_runtime.get_plan_provider_overlay_visibility_key(
        getattr(overlay, "provider_id", ""),
        getattr(overlay, "key", ""),
    )
    if key is None:
        return True
    return _provider_overlay_read_state(session).visibility.get(key, True)


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
    provider_runtime = _runtime()
    key = provider_runtime.get_plan_provider_overlay_visibility_key(provider_id, overlay_key)
    if key is None:
        return
    visible = bool(visible)
    overlay_state = _provider_overlay_read_state(session)
    if visible:
        overlay_state.visibility.pop(key, None)
    else:
        overlay_state.visibility[key] = False
    overlay_state.render_state = None
    provider_runtime.invalidate_plan_provider_document_cache(session)
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )


def queue_plan_provider_overlay_refresh(session):
    provider_runtime = _runtime()
    _provider_overlay_read_state(session).render_state = None
    provider_runtime.invalidate_plan_provider_document_cache(session)
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )


def queue_plan_provider_overlay_sync(session):
    session.overlays.queue_plan_overlay_visual_refresh(
        plan_document_visuals.PLAN_VISUAL_PROVIDER_OVERLAYS
    )
