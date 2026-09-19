# SPDX-License-Identifier: LGPL-2.1-or-later

"""Opening overlay and handle tracker helpers for BIM Plan Edit."""

from bimplan.contextual_datums import ContextualDatumSpec

from . import geometry as overlay_geometry
from . import manager as overlay_manager


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _opening_tracker_state(session):
    return session.overlay_tracker_state


def _opening_overlay_state(session):
    return session.overlay_transient_state


class PlanOpeningOverlayService:
    """Owned session surface for opening overlays and handles."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def sync_hovered_opening_overlay(self, *args, **kwargs):
        return sync_hovered_opening_overlay(self.session, *args, **kwargs)

    def clear_hovered_opening_overlay(self, *args, **kwargs):
        return clear_hovered_opening_overlay(self.session, *args, **kwargs)

    def invalidate_hovered_opening_overlay_cache(self, *args, **kwargs):
        return invalidate_hovered_opening_overlay_cache(self.session, *args, **kwargs)

    def create_opening_overlay_trackers(self, *args, **kwargs):
        return create_opening_overlay_trackers(self.session, *args, **kwargs)

    def sync_selected_opening_overlay(self, *args, **kwargs):
        return sync_selected_opening_overlay(self.session, *args, **kwargs)

    def clear_selected_opening_overlay(self, *args, **kwargs):
        return clear_selected_opening_overlay(self.session, *args, **kwargs)

    def invalidate_selected_opening_overlay_cache(self, *args, **kwargs):
        return invalidate_selected_opening_overlay_cache(self.session, *args, **kwargs)

    def sync_selected_wall_opening_context_overlay(self, *args, **kwargs):
        return sync_selected_wall_opening_context_overlay(self.session, *args, **kwargs)

    def clear_selected_wall_opening_context_overlay(self, *args, **kwargs):
        return clear_selected_wall_opening_context_overlay(self.session, *args, **kwargs)

def sync_hovered_opening_overlay(session):
    with _perf_trace_span(session, "sync_hovered_opening_overlay"):
        tracker_state = _opening_tracker_state(session)
        overlay_state = _opening_overlay_state(session)
        opening = session.hovered_opening
        if session.current_tool != "Select":
            clear_hovered_opening_overlay(session)
            return
        if not session.openings.is_hosted_opening_object(opening):
            clear_hovered_opening_overlay(session)
            return
        if session.selection.state.is_selected_plan_target("opening", opening):
            clear_hovered_opening_overlay(session)
            return
        width = session.viewport.scaled_line_width(2)
        color = (0.38, 0.62, 0.96)
        render_state = (
            session.visibility.get_document_object_key(opening),
            round(float(width), 3),
            color,
        )
        if (
            not overlay_state.hovered_opening_overlay_dirty
            and overlay_state.hovered_opening_overlay_render_state == render_state
        ):
            for tracker in tracker_state.opening_hover_trackers:
                try:
                    raise_tracker = getattr(tracker, "raiseTracker", None)
                    if callable(raise_tracker):
                        raise_tracker()
                except Exception:
                    pass
            _perf_count(session, "hovered_opening_overlay_cache_hits")
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_hovered_opening_overlay(session)
            return
        segments = overlay_geometry.get_opening_overlay_segments(session, opening)
        _perf_count(session, "hovered_opening_overlay_segments", len(segments))
        if len(tracker_state.opening_hover_trackers) != len(segments):
            clear_hovered_opening_overlay(session)
            for _start, _end in segments:
                tracker = overlay_manager.make_plan_line_tracker(
                    DraftTrackers,
                    "opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
                    scolor=color,
                    swidth=width,
                    ontop=True,
                )
                tracker_state.opening_hover_trackers.append(tracker)
        for tracker, (start, end) in zip(tracker_state.opening_hover_trackers, segments):
            overlay_manager.set_plan_line_tracker_width(tracker, width)
            tracker.setColor(color)
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            try:
                raise_tracker = getattr(tracker, "raiseTracker", None)
                if callable(raise_tracker):
                    raise_tracker()
            except Exception:
                pass
        overlay_state.hovered_opening_overlay_render_state = render_state
        overlay_state.hovered_opening_overlay_dirty = False


def clear_hovered_opening_overlay(session):
    tracker_state = _opening_tracker_state(session)
    overlay_state = _opening_overlay_state(session)
    overlay_manager.finalize_trackers(tracker_state.opening_hover_trackers)
    tracker_state.opening_hover_trackers = []
    overlay_state.hovered_opening_overlay_dirty = False
    overlay_state.hovered_opening_overlay_render_state = None


def invalidate_hovered_opening_overlay_cache(session):
    _opening_overlay_state(session).hovered_opening_overlay_dirty = True


def create_opening_overlay_trackers(
    session, opening, color, width, tracker_store, include_guides=False
):
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except ImportError:
        return

    if include_guides:
        polylines = overlay_geometry.get_opening_combined_overlay_polylines(session, opening)
    else:
        polylines = overlay_geometry.get_opening_overlay_polylines(session, opening)

    for polyline in polylines:
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            tracker = overlay_manager.make_plan_line_tracker(
                DraftTrackers,
                "opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
                scolor=color,
                swidth=width,
                ontop=True,
            )
            tracker.p1(start)
            tracker.p2(end)
            tracker.on()
            tracker_store.append(tracker)


def sync_selected_opening_overlay(session):
    with _perf_trace_span(session, "sync_selected_opening_overlay"):
        tracker_state = _opening_tracker_state(session)
        overlay_state = _opening_overlay_state(session)
        opening = session.selection.state.get_selected_plan_target_object("opening")
        if session.current_tool != "Select" or not session.openings.is_hosted_opening_object(
            opening
        ):
            clear_selected_opening_overlay(session)
            return
        width = session.viewport.scaled_line_width(3)
        color = (0.12, 0.38, 0.95)
        render_state = (
            session.visibility.get_document_object_key(opening),
            round(float(width), 3),
            color,
        )
        if (
            not overlay_state.selected_opening_overlay_dirty
            and overlay_state.selected_opening_overlay_render_state == render_state
        ):
            _perf_count(session, "selected_opening_overlay_cache_hits")
            sync_selected_opening_width_datum(session)
            return
        try:
            import draftguitools.gui_trackers as DraftTrackers
        except ImportError:
            clear_selected_opening_overlay(session)
            return
        segments = overlay_geometry.get_opening_combined_overlay_segments(session, opening)
        _perf_count(session, "selected_opening_overlay_segments", len(segments))
        (
            tracker_state.opening_overlay_trackers,
            tracker_state.opening_hover_trackers,
            transferred_trackers,
        ) = overlay_manager.sync_segment_overlay_trackers(
            session,
            DraftTrackers,
            trackers=tracker_state.opening_overlay_trackers,
            hover_trackers=tracker_state.opening_hover_trackers,
            segments=segments,
            label="selected-opening-overlay:{}".format(getattr(opening, "Name", "unknown")),
            color=color,
            width=width,
            clear_fn=lambda: clear_selected_opening_overlay(session),
            transfer_perf_key="selected_opening_overlay_tracker_transfers",
        )
        if transferred_trackers:
            overlay_state.hovered_opening_overlay_render_state = None
        overlay_state.selected_opening_overlay_render_state = render_state
        overlay_state.selected_opening_overlay_dirty = False
        sync_selected_opening_width_datum(session)


def clear_selected_opening_overlay(session):
    tracker_state = _opening_tracker_state(session)
    overlay_state = _opening_overlay_state(session)
    overlay_manager.finalize_trackers(tracker_state.opening_overlay_trackers)
    tracker_state.opening_overlay_trackers = []
    overlay_state.selected_opening_overlay_dirty = False
    overlay_state.selected_opening_overlay_render_state = None
    clear_selected_opening_width_datum(session)


def invalidate_selected_opening_overlay_cache(session):
    _opening_overlay_state(session).selected_opening_overlay_dirty = True


def _selected_opening_width_datum_context(session):
    opening = session.selection.state.get_selected_plan_target_object("opening")
    if session.current_tool != "Select" or not session.openings.is_hosted_opening_object(opening):
        return None
    handles = session.contextual_rendering.edit_handles_for(opening)
    by_role = {handle.role: handle for handle in handles}
    left = by_role.get("OpeningLeftJamb")
    right = by_role.get("OpeningRightJamb")
    if left is None or right is None:
        return None
    try:
        import ArchWindow

        width = float(ArchWindow.getWindowWidthMm(opening) or 0.0)
    except (AttributeError, TypeError, ValueError):
        return None
    if width <= 0.0:
        return None
    return opening, left, right, width


def sync_selected_opening_width_datum(session):
    context = _selected_opening_width_datum_context(session)
    if context is None:
        clear_selected_opening_width_datum(session)
        return
    opening, left, right, width = context
    render_state = (
        session.visibility.get_document_object_key(opening),
        tuple(round(float(value), 6) for point in (left.point, right.point) for value in point),
        round(width, 6),
    )
    start_operation_value = float(right.operation.get_value(right.source))
    session.contextual_datums.sync(
        ContextualDatumSpec(
            key="opening.width",
            handle=right,
            points=(left.point, right.point),
            value=width,
            render_state=render_state,
            value_to_operation=lambda value: start_operation_value + float(value) - width,
            refresh_visuals=("selected_opening",),
        )
    )


def clear_selected_opening_width_datum(session):
    session.contextual_datums.clear("opening.width")


def sync_selected_wall_opening_context_overlay(session):
    clear_selected_wall_opening_context_overlay(session)
    wall = session.selection.state.get_selected_plan_target_object("wall")
    if (
        session.current_tool != "Select"
        or not wall
        or session.selection.state.is_selected_plan_target("opening")
    ):
        return
    color = (0.46, 0.58, 0.82)
    width = session.viewport.scaled_line_width(2)
    for opening in session.openings.get_wall_hosted_openings(wall):
        if opening == session.hovered_opening:
            continue
        create_opening_overlay_trackers(
            session,
            opening,
            color=color,
            width=width,
            tracker_store=_opening_tracker_state(session).selected_wall_opening_context_trackers,
        )


def clear_selected_wall_opening_context_overlay(session):
    tracker_state = _opening_tracker_state(session)
    overlay_manager.finalize_trackers(tracker_state.selected_wall_opening_context_trackers)
    tracker_state.selected_wall_opening_context_trackers = []
