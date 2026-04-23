# SPDX-License-Identifier: LGPL-2.1-or-later

"""Document-driven visual refresh helpers for BIM Plan Edit."""


def is_opening_visual_dependency(opening, obj):
    if not opening or not obj:
        return False
    if obj == opening:
        return True
    if obj == getattr(opening, "Base", None):
        return True
    return obj in (getattr(opening, "Hosts", None) or [])


def refresh_selected_opening_visuals(session):
    session._sync_selected_opening_overlay()
    session._sync_selected_opening_handles()
    session._sync_selected_wall_opening_context_overlay()
    session._request_view_redraw()


def is_symbol_visual_dependency(session, symbol, obj):
    if not session._is_plan_symbol_instance(symbol) or not obj:
        return False
    if obj == symbol:
        return True
    semantic_obj = session._get_plan_semantic_object(symbol)
    if obj == semantic_obj:
        return True
    if obj == getattr(semantic_obj, "Base", None):
        return True
    return obj in (getattr(semantic_obj, "PlanSymbols", None) or [])


def refresh_plan_object_footprint_display(session, obj, *, request_redraw=True):
    if not session._is_supported_plan_object(obj):
        return
    session._invalidate_plan_overlay_geometry_cache(obj)
    semantic_obj = session._get_plan_semantic_object(obj)
    refresh_targets = []
    for candidate in (semantic_obj, obj):
        if not candidate:
            continue
        name = getattr(candidate, "Name", None)
        if not name or any(getattr(target, "Name", None) == name for target in refresh_targets):
            continue
        refresh_targets.append(candidate)

    refreshed = False
    for candidate in refresh_targets:
        view_object = getattr(candidate, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object else None
        if not proxy:
            continue
        if (
            not hasattr(proxy, "ensureFootprintGroup")
            and not hasattr(proxy, "updateFootprint")
            and not hasattr(proxy, "refreshFootprint")
        ):
            continue
        try:
            if hasattr(proxy, "refreshFootprint"):
                proxy.refreshFootprint()
            else:
                if hasattr(proxy, "ensureFootprintGroup"):
                    proxy.ensureFootprintGroup(view_object)
                if hasattr(proxy, "updateFootprint"):
                    proxy.updateFootprint()
            if hasattr(view_object, "update"):
                view_object.update()
            refreshed = True
        except TypeError:
            try:
                if hasattr(proxy, "refreshFootprint"):
                    proxy.refreshFootprint(view_object)
                else:
                    if hasattr(proxy, "ensureFootprintGroup"):
                        proxy.ensureFootprintGroup(view_object)
                    if hasattr(proxy, "updateFootprint"):
                        proxy.updateFootprint()
                if hasattr(view_object, "update"):
                    view_object.update()
                refreshed = True
            except Exception:
                continue
        except Exception:
            continue

    view_object = getattr(obj, "ViewObject", None)
    if view_object and hasattr(view_object, "update"):
        try:
            view_object.update()
        except Exception:
            pass
    if not refreshed:
        return
    if request_redraw:
        session._request_view_redraw()


def refresh_opening_footprint_display(session, opening):
    if not session._is_hosted_opening_object(opening):
        return
    session._refresh_plan_object_footprint_display(opening)


def refresh_wall_footprint_display(session, wall):
    if not wall:
        return
    session._refresh_plan_object_footprint_display(wall)


def refresh_opening_host_footprint_displays(session, opening):
    if not session._is_hosted_opening_object(opening):
        return
    for host in getattr(opening, "Hosts", None) or []:
        session._refresh_wall_footprint_display(host)


def queue_recompute_opening_hosts(session, *openings):
    if (
        session._tearing_down
        or session._opening_host_recompute_queued
        or session._opening_host_recompute_running
    ):
        return
    hosts = []
    for opening in openings:
        if not session._is_hosted_opening_object(opening):
            continue
        hosts.extend(getattr(opening, "Hosts", None) or [])
    hosts = [host for host in dict.fromkeys(hosts) if host]
    if not hosts:
        return
    session._opening_host_recompute_queued = True
    session._flush_recompute_opening_hosts(hosts)


def flush_recompute_opening_hosts(session, hosts):
    session._opening_host_recompute_queued = False
    if session._tearing_down or session._opening_host_recompute_running or not session.doc:
        return
    session._opening_host_recompute_running = True
    try:
        for host in hosts:
            try:
                host.touch()
            except Exception:
                continue
        session.doc.recompute()
    finally:
        session._opening_host_recompute_running = False


def queue_hard_refresh_selected_opening_visuals(session):
    if session._tearing_down or session._selected_opening_hard_refresh_queued:
        return
    session._selected_opening_hard_refresh_queued = True
    session._clear_selected_opening_overlay()
    session._clear_selected_opening_handles()
    session._request_view_redraw()
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, session._flush_hard_refresh_selected_opening_visuals)
    except Exception:
        session._flush_hard_refresh_selected_opening_visuals()


def flush_hard_refresh_selected_opening_visuals(session):
    session._selected_opening_hard_refresh_queued = False
    if session._tearing_down or session.current_tool != "Select":
        return
    opening = session._get_selected_plan_target_object("opening")
    if not session._is_hosted_opening_object(opening):
        return
    session._sync_selected_opening_overlay()
    session._sync_selected_opening_handles()
    session._request_view_redraw()
