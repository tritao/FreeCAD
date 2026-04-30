# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opening edit interaction helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimplan.runtime import capabilities as runtime_capabilities
from bimplan.runtime import tools as plan_runtime_tools

translate = FreeCAD.Qt.translate

OPENING_MOVE_ANCHORS = ("center", "left", "right")


def _overlay_runtime_api(session):
    overlays = getattr(session, "overlays", None)
    return getattr(overlays, "runtime", overlays)


def _get_callable_attr(obj, attr_name):
    return runtime_capabilities.get_callable(obj, attr_name)


def _proxy_supports(proxy, attrs):
    return proxy is not None and all(_get_callable_attr(proxy, attr) is not None for attr in attrs)


def get_selected_opening_edit_handles(session, opening):
    proxy = session.openings.get_opening_view_proxy(opening, "get_plan_edit_handles")
    if not proxy:
        return []
    return list(proxy.get_plan_edit_handles() or [])


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


def project_opening_handle_point(session, opening, handle, point):
    if point is None or not opening or getattr(handle, "role", None) != "move":
        return point
    proxy = session.openings.get_opening_plan_proxy(opening, "project_point_to_host_axis")
    if not proxy:
        return point
    return proxy.project_point_to_host_axis(
        point,
        anchor=session.opening_transient_state.edit_opening_move_anchor,
    )


def get_opening_move_anchor_modes(session, opening):
    proxy = session.openings.get_opening_plan_proxy(opening, "get_plan_move_anchor_modes")
    if not proxy:
        return OPENING_MOVE_ANCHORS
    modes = tuple(proxy.get_plan_move_anchor_modes() or ())
    return modes or OPENING_MOVE_ANCHORS


def execute_opening_handle(session, opening, handle_index, point=None):
    proxy = session.openings.get_opening_view_proxy(opening, "execute_plan_edit_handle")
    if not proxy:
        return False
    return bool(
        proxy.execute_plan_edit_handle(
            handle_index,
            point,
            anchor=session.opening_transient_state.edit_opening_move_anchor,
        )
    )


def get_opening_move_preview_state(session, opening, point):
    if not opening or point is None:
        return None
    proxy = session.openings.get_opening_view_proxy(opening, "get_plan_move_preview_state")
    if not proxy:
        return None
    return proxy.get_plan_move_preview_state(
        point,
        anchor=session.opening_transient_state.edit_opening_move_anchor,
    )


def sync_opening_move_preview(session, opening, point):
    session.openings.clear_opening_move_preview()
    if session.current_tool != "Move Opening" or not opening or point is None:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    preview_state = session.openings.get_opening_move_preview_state(opening, point)
    if not preview_state:
        return

    preview_color = (0.12, 0.38, 0.95)
    for polyline in preview_state.get("polylines", []):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = session.overlays.manager.make_plan_line_tracker(
                DraftTrackers,
                "opening-move-preview:{}".format(getattr(opening, "Name", "unknown")),
                scolor=preview_color,
                swidth=session.viewport.scaled_line_width(3),
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            session.opening_transient_state.opening_move_preview_trackers.append(tracker)

    guide_start = preview_state.get("guide_start")
    guide_end = preview_state.get("guide_end")
    if guide_start is None or guide_end is None:
        return

    guide = session.overlays.manager.make_plan_line_tracker(
        DraftTrackers,
        "opening-move-guide:{}".format(getattr(opening, "Name", "unknown")),
        dotted=True,
        scolor=preview_color,
        swidth=session.viewport.scaled_line_width(1),
        ontop=True,
    )
    guide.p1(guide_start)
    guide.p2(guide_end)
    guide.on()
    session.opening_transient_state.opening_move_preview_trackers.append(guide)

    try:
        dim = DraftTrackers.archDimTracker(mode=1)
    except Exception:
        return
    dim.dimnode.textColor.setValue(preview_color)
    dim.offset = session.wall_edit.get_opening_move_readout_offset(opening)
    dim.p1(guide_start)
    dim.p2(guide_end)
    dim.on()
    session.opening_transient_state.opening_move_preview_trackers.append(dim)


def clear_opening_move_preview(session):
    opening_transient_state = session.opening_transient_state
    session.overlays.manager.finalize_trackers(
        opening_transient_state.opening_move_preview_trackers
    )
    opening_transient_state.opening_move_preview_trackers = []


def cycle_opening_move_anchor(session):
    if session.current_tool != "Move Opening":
        return False
    interaction_state = session.interaction_state
    opening_transient_state = session.opening_transient_state
    anchor_modes = session.openings.get_opening_move_anchor_modes(interaction_state.edit_opening)
    try:
        current_index = anchor_modes.index(opening_transient_state.edit_opening_move_anchor)
    except ValueError:
        current_index = 0
    opening_transient_state.edit_opening_move_anchor = anchor_modes[
        (current_index + 1) % len(anchor_modes)
    ]
    return True


def refresh_opening_move_preview_from_raw_point(session):
    interaction_state = session.interaction_state
    opening_transient_state = session.opening_transient_state
    opening = interaction_state.edit_opening
    handle_index = interaction_state.edit_opening_handle_index
    if not opening or handle_index is None:
        return
    handles = session.openings.get_selected_opening_edit_handles(opening)
    if handle_index < 0 or handle_index >= len(handles):
        return
    handle = handles[handle_index]
    raw_point = opening_transient_state.edit_opening_move_raw_point
    if raw_point is None:
        raw_point = handle.point
    point = session.openings.project_opening_handle_point(opening, handle, raw_point)
    session.openings.sync_opening_move_preview(opening, point)


def queue_opening_move_initial_preview(session, opening, point):
    def run_preview():
        with session.performance.plan_perf_trace_event("queued_opening_move_initial_preview"):
            session.openings.sync_opening_move_preview(opening, point)

    try:
        from PySide import QtCore
    except ImportError:
        run_preview()
        return
    QtCore.QTimer.singleShot(0, run_preview)


def activate_opening_handle(session, opening, handle_index):
    try:
        from PySide import QtCore
    except ImportError:
        session.openings.activate_opening_handle_now(opening, handle_index)
        return

    QtCore.QTimer.singleShot(
        0,
        lambda: session.openings.activate_opening_handle_now(opening, handle_index),
    )


def activate_opening_handle_now(session, opening, handle_index):
    with session.performance.plan_perf_trace_span("activate_opening_handle_now"):
        if session.lifecycle_state.tearing_down or not opening:
            return
        with session.performance.plan_perf_trace_span("activate_opening_handle_set_target"):
            session.selection.state.set_selected_plan_target("opening", opening)
            session.overlays.walls.clear_wall_grips()
        with session.performance.plan_perf_trace_span("activate_opening_handle_get_handles"):
            handles = session.openings.get_selected_opening_edit_handles(opening)
        if handle_index < 0 or handle_index >= len(handles):
            return
        handle = handles[handle_index]
        if handle.interaction == "point_pick":
            with session.performance.plan_perf_trace_span(
                "activate_opening_handle_start_point_pick"
            ):
                session.openings.start_opening_handle_point_pick(opening, handle_index, handle)
        else:
            with session.performance.plan_perf_trace_span("activate_opening_handle_execute"):
                session.openings.execute_selected_opening_handle(opening, handle_index, handle)


def start_opening_handle_point_pick(session, opening, handle_index, handle):
    with session.performance.plan_perf_trace_span("start_opening_handle_point_pick"):
        if not opening:
            return
        with session.performance.plan_perf_trace_span("start_opening_handle_state"):
            session.current_tool = "Move Opening"
            session.selection.hover.set_hovered_wall(None)
            session.selection.hover.set_hovered_opening(None)
            session.overlays.spaces.sync_secondary_selected_overlays()
            interaction_state = session.interaction_state
            opening_transient_state = session.opening_transient_state
            opening_transient_state.opening_edit_generation += 1
            interaction_state.edit_opening = opening
            interaction_state.edit_opening_handle_index = handle_index
            opening_transient_state.edit_opening_move_anchor = "center"
            opening_transient_state.edit_opening_move_raw_point = FreeCAD.Vector(handle.point)
            session.overlays.openings.clear_selected_opening_overlay()
            session.overlays.openings.clear_selected_opening_handles()
        with session.performance.plan_perf_trace_span("start_opening_handle_preview"):
            queue_opening_move_initial_preview(session, opening, handle.point)
        session.task_panels.refresh_task_panel_status(reason="selection")
        session.snap.set_active_draft_command()
        with session.performance.plan_perf_trace_span("opening_handle_push_snap_profile"):
            session.snap.push_opening_move_snap_profile()
        with session.performance.plan_perf_trace_span("opening_handle_focus_suppression"):
            session.snap.set_point_focus_suppressed(True)
        with session.performance.plan_perf_trace_span("opening_handle_snapper_get_point"):
            FreeCADGui.Snapper.getPoint(
                last=handle.point,
                callback=session.openings.finish_opening_handle_point_pick,
                movecallback=session.openings.update_opening_handle_point_pick,
                title=handle.title or translate("BIM_PlanEdit", "Pick new opening position"),
                noTracker=True,
            )
        with session.performance.plan_perf_trace_span("opening_handle_queue_focus_plan_view"):
            session.viewport.queue_focus_plan_view()


def update_opening_handle_point_pick(session, point=None, snap_info=None):
    del snap_info
    interaction_state = session.interaction_state
    opening_transient_state = session.opening_transient_state
    opening = interaction_state.edit_opening
    handle_index = interaction_state.edit_opening_handle_index
    if not opening or handle_index is None:
        session.openings.clear_opening_move_preview()
        return
    handles = session.openings.get_selected_opening_edit_handles(opening)
    if handle_index < 0 or handle_index >= len(handles):
        session.openings.clear_opening_move_preview()
        return
    handle = handles[handle_index]
    opening_transient_state.edit_opening_move_raw_point = (
        FreeCAD.Vector(point) if point is not None else None
    )
    point = session.openings.project_opening_handle_point(opening, handle, point)
    session.openings.sync_opening_move_preview(opening, point)


def finish_opening_handle_point_pick(session, point=None, obj=None):
    del obj
    interaction_state = session.interaction_state
    opening_transient_state = session.opening_transient_state
    opening = interaction_state.edit_opening
    handle_index = interaction_state.edit_opening_handle_index
    interaction_state.edit_opening = None
    interaction_state.edit_opening_handle_index = None
    session.snap.pop_opening_move_snap_profile()
    session.snap.clear_active_draft_command()
    session.openings.clear_opening_move_preview()
    opening_transient_state.edit_opening_move_raw_point = None

    if point is None or not opening:
        session.current_tool = "Select"
        opening_transient_state.edit_opening_move_anchor = "center"
        session.overlays.openings.sync_selected_opening_overlay()
        session.overlays.openings.sync_selected_opening_handles()
        session.task_panels.refresh_task_panel_status()
        return

    handles = session.openings.get_selected_opening_edit_handles(opening)
    if handle_index is None or handle_index < 0 or handle_index >= len(handles):
        session.current_tool = "Select"
        opening_transient_state.edit_opening_move_anchor = "center"
        session.task_panels.refresh_task_panel_status()
        return
    handle = handles[handle_index]
    point = session.openings.project_opening_handle_point(opening, handle, point)

    try:
        session.doc.openTransaction(handle.transaction or translate("BIM_PlanEdit", "Edit Opening"))
        moved = session.openings.execute_opening_handle(opening, handle_index, point)
        if not moved:
            raise RuntimeError("Unable to execute opening handle")
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except (ReferenceError, RuntimeError):
            pass
        opening_transient_state.edit_opening_move_anchor = "center"
        session.openings.restore_selected_opening(opening)
        return

    opening_transient_state.edit_opening_move_anchor = "center"
    session.current_tool = "Select"
    session.task_panels.refresh_task_panel_status()
    session.openings.queue_restore_selected_opening(opening)


def cancel_opening_handle_point_pick(session):
    interaction_state = session.interaction_state
    opening_transient_state = session.opening_transient_state
    opening_transient_state.opening_edit_generation += 1
    opening = interaction_state.edit_opening
    interaction_state.edit_opening = None
    interaction_state.edit_opening_handle_index = None
    session.snap.stop_snapper()
    session.snap.pop_opening_move_snap_profile()
    session.snap.clear_active_draft_command()
    session.openings.clear_opening_move_preview()
    opening_transient_state.edit_opening_move_anchor = "center"
    opening_transient_state.edit_opening_move_raw_point = None
    session.current_tool = "Select"
    if opening:
        session.selection.state.set_selected_plan_target("opening", opening, pending_restore=True)
    session.overlays.openings.sync_selected_opening_overlay()
    session.overlays.openings.sync_selected_opening_handles()
    session.task_panels.refresh_task_panel_status()


def reset_pending_edit_state(session, *, clear_edit=False):
    interaction_state = session.interaction_state
    opening_transient_state = session.opening_transient_state
    opening_transient_state.opening_edit_generation += 1
    opening_transient_state.edit_opening_move_anchor = "center"
    opening_transient_state.edit_opening_move_raw_point = None
    if clear_edit:
        interaction_state.edit_opening = None
        interaction_state.edit_opening_handle_index = None


def discard_runtime_references(session):
    reset_pending_edit_state(session, clear_edit=True)


def restore_selected_opening(session, opening):
    session.current_tool = "Select"
    if opening:
        session.selection.state.set_selected_plan_target("opening", opening, pending_restore=True)
    else:
        session.selection.state.set_selected_plan_target()
    if not opening:
        session.overlays.openings.sync_selected_opening_overlay()
        session.overlays.openings.sync_selected_opening_handles()
        session.task_panels.refresh_task_panel_status()
        return
    session.selection.sync.set_gui_selection_object(opening)
    session.overlays.openings.sync_selected_opening_overlay()
    session.overlays.openings.sync_selected_opening_handles()
    session.task_panels.refresh_task_panel_status()


def _run_queued_restore_selected_opening(session, opening, restore_generation):
    opening_transient_state = session.opening_transient_state
    if session.lifecycle_state.tearing_down or session.lifecycle_state.finishing:
        return
    if opening_transient_state.opening_edit_generation != restore_generation:
        return
    session.openings.restore_selected_opening(opening)


def queue_restore_selected_opening(session, opening):
    restore_generation = session.opening_transient_state.opening_edit_generation
    try:
        from PySide import QtCore
    except ImportError:
        _run_queued_restore_selected_opening(session, opening, restore_generation)
        return
    QtCore.QTimer.singleShot(
        0,
        lambda: _run_queued_restore_selected_opening(
            session,
            opening,
            restore_generation,
        ),
    )


def execute_selected_opening_handle(session, opening, handle_index, handle):
    try:
        session.doc.openTransaction(handle.transaction or translate("BIM_PlanEdit", "Edit Opening"))
        executed = session.openings.execute_opening_handle(opening, handle_index)
        if not executed:
            raise RuntimeError("Unable to execute opening handle")
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except (ReferenceError, RuntimeError):
            pass
        return
    session.selection.state.set_selected_plan_target("opening", opening, pending_restore=True)
    session.overlays.openings.sync_selected_opening_overlay()
    session.overlays.openings.sync_selected_opening_handles()


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


class OpeningMoveTool(plan_runtime_tools.PlanToolHandler):
    """Keyboard behavior for active opening move point-pick edits."""

    tool_id = plan_runtime_tools.PlanTool.MOVE_OPENING

    def on_key(self, key, event_callback, coin):
        del event_callback
        session = self.session
        if key == coin.SoKeyboardEvent.A:
            if session.openings.cycle_opening_move_anchor():
                session.openings.refresh_opening_move_preview_from_raw_point()
                session.task_panels.refresh_task_panel_status()
            return True
        if key == coin.SoKeyboardEvent.ESCAPE:
            session.openings.cancel_opening_handle_point_pick()
            return True
        return False


class PlanOpeningsAPI(_SessionAPI):
    """Owned session surface for Plan Edit opening behavior."""

    __slots__ = ("__dict__",)

    def get_selected_opening_edit_handles(self, *args, **kwargs):
        return get_selected_opening_edit_handles(self.session, *args, **kwargs)

    def get_opening_plan_proxy(self, *args, **kwargs):
        return get_opening_plan_proxy(self.session, *args, **kwargs)

    def get_opening_view_proxy(self, *args, **kwargs):
        return get_opening_view_proxy(self.session, *args, **kwargs)

    def project_opening_handle_point(self, *args, **kwargs):
        return project_opening_handle_point(self.session, *args, **kwargs)

    def get_opening_move_anchor_modes(self, *args, **kwargs):
        return get_opening_move_anchor_modes(self.session, *args, **kwargs)

    def execute_opening_handle(self, *args, **kwargs):
        return execute_opening_handle(self.session, *args, **kwargs)

    def get_opening_move_preview_state(self, *args, **kwargs):
        return get_opening_move_preview_state(self.session, *args, **kwargs)

    def sync_opening_move_preview(self, *args, **kwargs):
        return sync_opening_move_preview(self.session, *args, **kwargs)

    def clear_opening_move_preview(self, *args, **kwargs):
        return clear_opening_move_preview(self.session, *args, **kwargs)

    def cycle_opening_move_anchor(self, *args, **kwargs):
        return cycle_opening_move_anchor(self.session, *args, **kwargs)

    def refresh_opening_move_preview_from_raw_point(self, *args, **kwargs):
        return refresh_opening_move_preview_from_raw_point(self.session, *args, **kwargs)

    def activate_opening_handle(self, *args, **kwargs):
        return activate_opening_handle(self.session, *args, **kwargs)

    def activate_opening_handle_now(self, *args, **kwargs):
        return activate_opening_handle_now(self.session, *args, **kwargs)

    def start_opening_handle_point_pick(self, *args, **kwargs):
        return start_opening_handle_point_pick(self.session, *args, **kwargs)

    def update_opening_handle_point_pick(self, *args, **kwargs):
        return update_opening_handle_point_pick(self.session, *args, **kwargs)

    def finish_opening_handle_point_pick(self, *args, **kwargs):
        return finish_opening_handle_point_pick(self.session, *args, **kwargs)

    def cancel_opening_handle_point_pick(self, *args, **kwargs):
        return cancel_opening_handle_point_pick(self.session, *args, **kwargs)

    def cancel_active_tool_for_finish(self):
        if self.session.current_tool != plan_runtime_tools.PlanTool.MOVE_OPENING:
            return False
        self.cancel_opening_handle_point_pick()
        return True

    def cancel_active_tool_for_teardown(self):
        if self.session.current_tool != plan_runtime_tools.PlanTool.MOVE_OPENING:
            return False
        self.cancel_opening_handle_point_pick()
        return True

    def cancel_active_tool_for_shutdown(self):
        return self.cancel_active_tool_for_teardown()

    def reset_pending_edit_state(self, *args, **kwargs):
        return reset_pending_edit_state(self.session, *args, **kwargs)

    def discard_runtime_references(self):
        return discard_runtime_references(self.session)

    def restore_selected_opening(self, *args, **kwargs):
        return restore_selected_opening(self.session, *args, **kwargs)

    def queue_restore_selected_opening(self, *args, **kwargs):
        return queue_restore_selected_opening(self.session, *args, **kwargs)

    def execute_selected_opening_handle(self, *args, **kwargs):
        return execute_selected_opening_handle(self.session, *args, **kwargs)

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
            _overlay_runtime_api(self.session).queue_plan_overlay_visual_refresh(
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
            _overlay_runtime_api(self.session).queue_plan_overlay_visual_refresh(
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
            _overlay_runtime_api(self.session).queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_HOVERED_WALL
            )
            return True
        if selected_wall and obj in self.get_wall_hosted_openings(selected_wall):
            self.refresh_opening_footprint_display(obj)
            self.refresh_opening_host_footprint_displays(obj)
            _overlay_runtime_api(self.session).queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_WALL_GRIPS
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
    session.overlays.openings.sync_selected_opening_handles()
    session.overlays.openings.sync_selected_wall_opening_context_overlay()
    session.viewport.request_view_redraw()


def queue_hard_refresh_selected_opening_visuals(session):
    opening_state = session.opening_transient_state
    if session.lifecycle_state.tearing_down or opening_state.selected_opening_hard_refresh_queued:
        return
    opening_state.selected_opening_hard_refresh_queued = True
    session.overlays.openings.clear_selected_opening_overlay()
    session.overlays.openings.clear_selected_opening_handles()
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
