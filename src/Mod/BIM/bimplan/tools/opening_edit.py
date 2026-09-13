# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opening selection, host-cache, and visual helpers for BIM Plan Edit."""

from bimplan.runtime import capabilities as runtime_capabilities


def _get_callable_attr(obj, attr_name):
    return runtime_capabilities.get_callable(obj, attr_name)


def _proxy_supports(proxy, attrs):
    return proxy is not None and all(_get_callable_attr(proxy, attr) is not None for attr in attrs)


def get_opening_plan_proxy(session, opening, *attrs):
    if not opening:
        return None
    proxy = getattr(opening, "Proxy", None)
    if _proxy_supports(proxy, attrs):
        return proxy
    return session.openings.get_opening_view_proxy(opening, *attrs)


def get_opening_view_proxy(session, opening, *attrs):
    if not opening:
        return None
    view_object = getattr(opening, "ViewObject", None)
    proxy = getattr(view_object, "Proxy", None)
    return proxy if _proxy_supports(proxy, attrs) else None


def restore_selected_opening(session, opening):
    session.current_tool = "Select"
    if opening:
        session.selection.state.set_selected_plan_target("opening", opening, pending_restore=True)
    else:
        session.selection.state.set_selected_plan_target()
    if not opening:
        session.overlays.openings.sync_selected_opening_overlay()
        session.task_panels.refresh_task_panel_status()
        return
    session.selection.sync.set_gui_selection_object(opening)
    session.overlays.openings.sync_selected_opening_overlay()
    session.task_panels.refresh_task_panel_status()


def queue_restore_selected_opening(session, opening):
    try:
        from PySide import QtCore
    except ImportError:
        restore_selected_opening(session, opening)
        return
    QtCore.QTimer.singleShot(
        0,
        lambda: _run_queued_restore_selected_opening(session, opening),
    )


def _run_queued_restore_selected_opening(session, opening):
    if session.lifecycle_state.tearing_down or session.lifecycle_state.finishing:
        return
    session.openings.restore_selected_opening(opening)


def invalidate_wall_hosted_openings_cache(session):
    from bimplan.tools import hosted_openings as plan_hosted_openings

    return plan_hosted_openings.invalidate_wall_hosted_openings_cache(session)


def queue_prime_wall_hosted_openings_cache(session):
    from bimplan.tools import hosted_openings as plan_hosted_openings

    return plan_hosted_openings.queue_prime_wall_hosted_openings_cache(session)


def prime_wall_hosted_openings_cache(session):
    from bimplan.tools import hosted_openings as plan_hosted_openings

    return plan_hosted_openings.prime_wall_hosted_openings_cache(session)


def build_wall_hosted_openings_cache(session):
    from bimplan.tools import hosted_openings as plan_hosted_openings

    return plan_hosted_openings.build_wall_hosted_openings_cache(session)


def collect_opening_instances_from_host_cache(session, host_cache):
    from bimplan.tools import hosted_openings as plan_hosted_openings

    return plan_hosted_openings.collect_opening_instances_from_host_cache(session, host_cache)


def get_plan_opening_instances(session):
    from bimplan.tools import hosted_openings as plan_hosted_openings

    return plan_hosted_openings.get_plan_opening_instances(session)


def get_wall_hosted_openings(session, wall):
    from bimplan.tools import hosted_openings as plan_hosted_openings

    return plan_hosted_openings.get_wall_hosted_openings(session, wall)


def refresh_wall_hosted_opening_footprints(session, wall):
    from bimplan.tools import wall_edit

    return wall_edit.refresh_wall_hosted_opening_footprints(session, wall)


def compute_wall_hosted_opening_layout(session, wall, endpoints):
    from bimplan.tools import wall_edit

    return wall_edit.compute_wall_hosted_opening_layout(session, wall, endpoints)


def resolve_wall_hosted_opening_layout(session, wall):
    from bimplan.tools import wall_edit

    return wall_edit.resolve_wall_hosted_opening_layout(session, wall)


def is_opening_visual_dependency(opening, obj):
    if not opening or not obj:
        return False
    if obj == opening:
        return True
    if obj == getattr(opening, "Base", None):
        return True
    return obj in (getattr(opening, "Hosts", None) or [])


def refresh_opening_footprint_display(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return
    session.document_visuals.refresh_plan_object_footprint_display(opening)


def refresh_opening_host_footprint_displays(session, opening):
    if not session.openings.is_hosted_opening_object(opening):
        return
    for host in getattr(opening, "Hosts", None) or []:
        if host:
            session.document_visuals.refresh_plan_object_footprint_display(host)


def queue_recompute_opening_hosts(session, *openings):
    opening_state = session.opening_transient_state
    if (
        session.lifecycle_state.tearing_down
        or opening_state.opening_host_recompute_queued
        or opening_state.opening_host_recompute_running
    ):
        return
    hosts = []
    for opening in openings:
        if not session.openings.is_hosted_opening_object(opening):
            continue
        hosts.extend(getattr(opening, "Hosts", None) or [])
    hosts = [host for host in dict.fromkeys(hosts) if host]
    if not hosts:
        return
    opening_state.opening_host_recompute_queued = True
    flush_recompute_opening_hosts(session, hosts)


def flush_recompute_opening_hosts(session, hosts):
    opening_state = session.opening_transient_state
    opening_state.opening_host_recompute_queued = False
    if (
        session.lifecycle_state.tearing_down
        or opening_state.opening_host_recompute_running
        or not session.doc
    ):
        return
    opening_state.opening_host_recompute_running = True
    try:
        for host in hosts:
            try:
                host.touch()
            except (AttributeError, ReferenceError, RuntimeError):
                continue
        session.doc.recompute()
    finally:
        opening_state.opening_host_recompute_running = False


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class PlanOpeningsAPI(_SessionAPI):
    """Owned session surface for Plan Edit opening behavior."""

    __slots__ = ("__dict__",)

    def get_opening_plan_proxy(self, *args, **kwargs):
        return get_opening_plan_proxy(self.session, *args, **kwargs)

    def get_opening_view_proxy(self, *args, **kwargs):
        return get_opening_view_proxy(self.session, *args, **kwargs)

    def restore_selected_opening(self, *args, **kwargs):
        return restore_selected_opening(self.session, *args, **kwargs)

    def queue_restore_selected_opening(self, *args, **kwargs):
        return queue_restore_selected_opening(self.session, *args, **kwargs)

    def invalidate_wall_hosted_openings_cache(self, *args, **kwargs):
        return invalidate_wall_hosted_openings_cache(self.session, *args, **kwargs)

    def queue_prime_wall_hosted_openings_cache(self, *args, **kwargs):
        return queue_prime_wall_hosted_openings_cache(self.session, *args, **kwargs)

    def prime_wall_hosted_openings_cache(self, *args, **kwargs):
        return prime_wall_hosted_openings_cache(self.session, *args, **kwargs)

    def build_wall_hosted_openings_cache(self, *args, **kwargs):
        return build_wall_hosted_openings_cache(self.session, *args, **kwargs)

    def collect_opening_instances_from_host_cache(self, *args, **kwargs):
        return collect_opening_instances_from_host_cache(self.session, *args, **kwargs)

    def get_plan_opening_instances(self, *args, **kwargs):
        return get_plan_opening_instances(self.session, *args, **kwargs)

    def get_wall_hosted_openings(self, *args, **kwargs):
        return get_wall_hosted_openings(self.session, *args, **kwargs)

    def refresh_wall_hosted_opening_footprints(self, *args, **kwargs):
        return refresh_wall_hosted_opening_footprints(self.session, *args, **kwargs)

    def compute_wall_hosted_opening_layout(self, *args, **kwargs):
        return compute_wall_hosted_opening_layout(self.session, *args, **kwargs)

    def resolve_wall_hosted_opening_layout(self, *args, **kwargs):
        return resolve_wall_hosted_opening_layout(self.session, *args, **kwargs)

    def is_opening_visual_dependency(self, *args, **kwargs):
        return is_opening_visual_dependency(*args, **kwargs)

    def refresh_opening_footprint_display(self, *args, **kwargs):
        return refresh_opening_footprint_display(self.session, *args, **kwargs)

    def refresh_opening_host_footprint_displays(self, *args, **kwargs):
        return refresh_opening_host_footprint_displays(self.session, *args, **kwargs)

    def queue_recompute_opening_hosts(self, *args, **kwargs):
        return queue_recompute_opening_hosts(self.session, *args, **kwargs)

    def flush_recompute_opening_hosts(self, *args, **kwargs):
        return flush_recompute_opening_hosts(self.session, *args, **kwargs)

    def refresh_selected_opening_visuals(self):
        return refresh_selected_opening_visuals(self.session)

    def queue_hard_refresh_selected_opening_visuals(self):
        return queue_hard_refresh_selected_opening_visuals(self.session)

    def flush_hard_refresh_selected_opening_visuals(self):
        return flush_hard_refresh_selected_opening_visuals(self.session)

    def refresh_target_document_visual_dependency(self, opening, obj, prop):
        from bimplan import document_visuals as plan_document_visuals

        if not (
            self.is_opening_visual_dependency(opening, obj)
            and prop in plan_document_visuals.OPENING_VISUAL_PROPERTIES
        ):
            return False
        self.refresh_opening_footprint_display(opening)
        self.refresh_opening_host_footprint_displays(opening)
        return True

    def refresh_opening_visual_footprints(self, opening):
        if opening is None:
            return False
        self.refresh_opening_footprint_display(opening)
        self.refresh_opening_host_footprint_displays(opening)
        return True

    def handle_document_visual_dependency_change(self, obj, prop):
        from bimplan import document_visuals as plan_document_visuals

        selected_opening = self.session.selection.state.get_selected_plan_target_object("opening")
        if self.refresh_target_document_visual_dependency(selected_opening, obj, prop):
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_SELECTED_OPENING,
                plan_document_visuals.PLAN_VISUAL_HOVERED_OPENING,
            )
            return True
        hovered_opening = self.session.hovered_opening
        if (
            hovered_opening
            and not self.session.selection.state.is_selected_plan_target("opening", hovered_opening)
            and self.refresh_target_document_visual_dependency(hovered_opening, obj, prop)
        ):
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_HOVERED_OPENING
            )
            return True
        return False

    def handle_wall_related_document_visual_change(self, obj, prop, selected_wall):
        from bimplan import document_visuals as plan_document_visuals

        if prop not in plan_document_visuals.OPENING_VISUAL_PROPERTIES:
            return False
        hovered_wall = self.session.hovered_wall
        if hovered_wall and obj in self.get_wall_hosted_openings(hovered_wall):
            self.refresh_opening_footprint_display(obj)
            self.refresh_opening_host_footprint_displays(obj)
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_HOVERED_WALL
            )
            return True
        if selected_wall and obj in self.get_wall_hosted_openings(selected_wall):
            self.refresh_opening_footprint_display(obj)
            self.refresh_opening_host_footprint_displays(obj)
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_SELECTED_WALL
            )
            return True
        return False

    def handle_deleted_visual_target(self, obj):
        if obj == self.session.hovered_opening:
            self.session.hovered_opening = None
            self.session.overlays.openings.clear_hovered_opening_overlay()
        if self.session.selection.refresh.clear_selected_plan_target_if_matches("opening", obj):
            self.refresh_selected_opening_visuals()
            return True
        return False

    def refresh_document_dependent_visuals(self, *, recompute_hosts=False):
        from bimplan import document_visuals as plan_document_visuals

        visuals = []
        selected_opening = self.session.selection.state.get_selected_plan_target_object("opening")
        if self.refresh_opening_visual_footprints(selected_opening):
            self.queue_hard_refresh_selected_opening_visuals()
            visuals.append(plan_document_visuals.PLAN_VISUAL_SELECTED_OPENING)
        hovered_opening = self.session.hovered_opening
        if (
            hovered_opening
            and not self.session.selection.state.is_selected_plan_target("opening", hovered_opening)
            and self.refresh_opening_visual_footprints(hovered_opening)
        ):
            visuals.append(plan_document_visuals.PLAN_VISUAL_HOVERED_OPENING)
        if recompute_hosts:
            self.queue_recompute_opening_hosts(
                selected_opening,
                hovered_opening,
            )
        return tuple(visuals)

    def is_hosted_opening_object(self, obj):
        from bimplan.tools import hosted_openings as plan_hosted_openings

        return plan_hosted_openings.is_hosted_opening_object(self.session, obj)


def refresh_selected_opening_visuals(session):
    session.overlays.openings.sync_selected_opening_overlay()
    session.overlays.openings.sync_selected_wall_opening_context_overlay()
    session.viewport.request_view_redraw()


def queue_hard_refresh_selected_opening_visuals(session):
    opening_state = session.opening_transient_state
    if session.lifecycle_state.tearing_down or opening_state.selected_opening_hard_refresh_queued:
        return
    opening_state.selected_opening_hard_refresh_queued = True
    session.overlays.openings.clear_selected_opening_overlay()
    session.viewport.request_view_redraw()
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(
            0,
            lambda: flush_hard_refresh_selected_opening_visuals(session),
        )
    except ImportError:
        flush_hard_refresh_selected_opening_visuals(session)


def flush_hard_refresh_selected_opening_visuals(session):
    session.opening_transient_state.selected_opening_hard_refresh_queued = False
    if session.lifecycle_state.tearing_down or session.current_tool != "Select":
        return
    opening = session.selection.state.get_selected_plan_target_object("opening")
    if not session.openings.is_hosted_opening_object(opening):
        return
    session.openings.refresh_selected_opening_visuals()
