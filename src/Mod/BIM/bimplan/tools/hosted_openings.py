# SPDX-License-Identifier: LGPL-2.1-or-later

"""Hosting and hosted opening helpers for BIM Plan Edit."""

from contextlib import nullcontext

from draftguitools import gui_base

from bimplan.transactions import PlanEditTransaction


class _PlanEditWallHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for wall creation inside Plan Edit."""

    def __init__(self, session, command=None):
        super().__init__(command)
        self.session = session

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session.lifecycle.on_embedded_command_started("Wall", command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session.lifecycle.on_embedded_command_finished("Wall", command or self.command)

    def get_working_plane(self):
        return self.session.viewport.get_interaction_plane()

    def get_interaction_plane(self):
        return self.session.viewport.get_interaction_plane()

    def request_point(
        self,
        callback,
        move_callback=None,
        last=None,
        title=None,
        mode=None,
        extra_widget=None,
        hints=None,
        modifier_resolver=None,
    ):
        del extra_widget
        super().request_point(
            callback=callback,
            move_callback=move_callback,
            last=last,
            title=title,
            mode=mode,
            extra_widget=None,
            hints=hints,
            modifier_resolver=modifier_resolver,
        )

    def clear_ui_state(self):
        return

    def reset_edit(self):
        return

    def show_continue(self):
        return

    def continue_mode_enabled(self):
        return False

    def continue_wall_chain_enabled(self):
        return True

    def supports_extra_widget(self):
        return False

    def resolve_point_request_modifiers(self, ctrl, shift, alt):
        del alt
        return ctrl, False

    def default_ortho_enabled(self):
        return True

    def free_angle_override_active(self):
        try:
            from PySide import QtCore, QtGui

            modifiers = QtGui.QApplication.keyboardModifiers()
            return bool(modifiers & QtCore.Qt.ShiftModifier)
        except Exception:
            return False

    def on_created_object(self, obj):
        self.session.visibility.register_plan_object(obj)


class _PlanEditCommandHost(gui_base.DraftInteractionHost):
    """Embedded Draft-style host for modifiers used inside Plan Edit."""

    def __init__(self, session, tool_name, command=None):
        super().__init__(command)
        self.session = session
        self.tool_name = tool_name

    def activate_command(self, command=None):
        super().activate_command(command)
        self.session.lifecycle.on_embedded_command_started(self.tool_name, command or self.command)

    def deactivate_command(self, command=None):
        super().deactivate_command(command)
        self.session.lifecycle.on_embedded_command_finished(self.tool_name, command or self.command)

    def continue_mode_enabled(self):
        return False


def has_built_opening_shape(opening):
    """Return True when an opening has a usable shape before it is hosted."""

    shape = getattr(opening, "Shape", None)
    if not shape:
        return False
    try:
        return not shape.isNull()
    except Exception:
        return False


def is_hosted_opening_object(session, obj):
    if not obj:
        return False
    semantic_obj = session.visibility.get_plan_semantic_object(obj)
    if not getattr(semantic_obj, "Hosts", None):
        return False

    if getattr(semantic_obj, "IfcType", "") in {"Window", "Door"}:
        return True

    try:
        import Draft

        return Draft.getType(semantic_obj) == "Window"
    except Exception:
        return False


def invalidate_wall_hosted_openings_cache(session):
    cache_state = session.overlay_cache_state
    cache_state.wall_hosted_openings_cache = None
    cache_state.plan_opening_instances_cache = None
    cache_state.wall_hosted_openings_cache_queued = False


def queue_prime_wall_hosted_openings_cache(session):
    cache_state = session.overlay_cache_state
    if (
        session._tearing_down
        or cache_state.wall_hosted_openings_cache is not None
        or cache_state.wall_hosted_openings_cache_queued
        or not session.doc
    ):
        return
    try:
        from PySide import QtCore
    except ImportError:
        return
    cache_state.wall_hosted_openings_cache_queued = True
    QtCore.QTimer.singleShot(0, session.openings.prime_wall_hosted_openings_cache)


def prime_wall_hosted_openings_cache(session):
    cache_state = session.overlay_cache_state
    cache_state.wall_hosted_openings_cache_queued = False
    if (
        session._tearing_down
        or cache_state.wall_hosted_openings_cache is not None
        or not session.doc
    ):
        return
    doc_name = getattr(session.doc, "Name", None)
    cache = session.openings.build_wall_hosted_openings_cache()
    cache_state.wall_hosted_openings_cache = (doc_name, cache)
    cache_state.plan_opening_instances_cache = (
        doc_name,
        session.openings.collect_opening_instances_from_host_cache(cache),
    )


def build_wall_hosted_openings_cache(session):
    cache = {}
    if not session.doc:
        return cache
    with session.performance.plan_perf_trace_span("build_wall_hosted_openings_cache"):
        for obj in getattr(session.doc, "Objects", []) or []:
            if not session._is_hosted_opening_object(obj):
                continue
            for host in getattr(obj, "Hosts", None) or []:
                host_key = session._get_document_object_key(host)
                if host_key is None:
                    continue
                cache.setdefault(host_key, []).append(obj)
    return cache


def collect_opening_instances_from_host_cache(session, host_cache):
    openings = []
    seen = set()
    for hosted_openings in (host_cache or {}).values():
        for opening in hosted_openings:
            opening_key = session._get_document_object_key(opening)
            if opening_key is None or opening_key in seen:
                continue
            seen.add(opening_key)
            openings.append(opening)
    return tuple(openings)


def get_plan_opening_instances(session):
    if not session.doc:
        return ()
    doc_name = getattr(session.doc, "Name", None)
    cache_state = session.overlay_cache_state
    cache_record = cache_state.plan_opening_instances_cache
    if cache_record is not None and cache_record[0] == doc_name:
        session.performance.plan_perf_count("plan_opening_instances_cache_hits")
        return cache_record[1]

    wall_cache_record = cache_state.wall_hosted_openings_cache
    if wall_cache_record is None or wall_cache_record[0] != doc_name:
        host_cache = session.openings.build_wall_hosted_openings_cache()
        cache_state.wall_hosted_openings_cache = (doc_name, host_cache)
    else:
        session.performance.plan_perf_count("wall_hosted_openings_cache_hits")
        host_cache = wall_cache_record[1]

    openings = session.openings.collect_opening_instances_from_host_cache(host_cache)
    cache_state.plan_opening_instances_cache = (doc_name, openings)
    return openings


def get_wall_hosted_openings(session, wall):
    if not wall or not session.doc:
        return []
    wall_key = session._get_document_object_key(wall)
    if wall_key is None:
        return []
    doc_name = getattr(session.doc, "Name", None)
    cache_state = session.overlay_cache_state
    cache_record = cache_state.wall_hosted_openings_cache
    if cache_record is None or cache_record[0] != doc_name:
        host_cache = session.openings.build_wall_hosted_openings_cache()
        cache_record = (doc_name, host_cache)
        cache_state.wall_hosted_openings_cache = cache_record
        cache_state.plan_opening_instances_cache = (
            doc_name,
            session.openings.collect_opening_instances_from_host_cache(host_cache),
        )
    else:
        session.performance.plan_perf_count("wall_hosted_openings_cache_hits")
    return list(cache_record[1].get(wall_key, ()))


def _host_opening(opening, host):
    import Arch

    Arch.addComponents(opening, host)
    return opening


def create_hosted_opening(
    session,
    host,
    build_opening,
    transaction_label,
    add_to_active_storey=True,
):
    """Create, build, host, and recompute an opening in the safe Plan Edit order.

    Hosted Arch windows touch their hosts when their shape changes. Build the
    opening before assigning its host so creation does not schedule a second
    host/opening recompute pass.
    """

    doc = getattr(session, "doc", None)
    if doc is None:
        return None

    opening = None
    defer_updates = getattr(session, "defer_document_visual_updates", None)
    update_scope = defer_updates() if defer_updates else nullcontext()
    with update_scope:
        with PlanEditTransaction(doc, transaction_label):
            opening = build_opening()
            if opening is None:
                raise RuntimeError("Unable to create opening")

            doc.recompute()
            if not has_built_opening_shape(opening):
                raise RuntimeError("Opening did not build before hosting")

            _host_opening(opening, host)
            if add_to_active_storey and hasattr(session, "visibility"):
                session.visibility.add_object_to_active_storey(opening)
            doc.recompute()

            if host not in (getattr(opening, "Hosts", None) or ()):
                raise RuntimeError("Opening was not hosted")

    return opening
