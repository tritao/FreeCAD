# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task panel ownership and refresh helpers for BIM Plan Edit."""

TASK_PANEL_REFRESH_FULL = "full"
TASK_PANEL_REFRESH_SELECTION = "selection"
TASK_PANEL_REFRESH_PROVIDER_OVERLAY_MODE = "provider_overlay_mode"
_TASK_PANEL_REFRESH_REASONS = (
    TASK_PANEL_REFRESH_FULL,
    TASK_PANEL_REFRESH_SELECTION,
    TASK_PANEL_REFRESH_PROVIDER_OVERLAY_MODE,
)


class PlanTaskPanelsAPI:
    """Owned session surface for Plan Edit task-panel wiring and refresh."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def attach_task_panel(self, *args, **kwargs):
        return attach_task_panel(self.session, *args, **kwargs)

    def attach_aux_task_panel(self, *args, **kwargs):
        return attach_aux_task_panel(self.session, *args, **kwargs)

    def detach_aux_task_panel(self, *args, **kwargs):
        return detach_aux_task_panel(self.session, *args, **kwargs)

    def detach_task_panel(self, *args, **kwargs):
        return detach_task_panel(self.session, *args, **kwargs)

    def on_panel_closed(self, *args, **kwargs):
        return on_panel_closed(self.session, *args, **kwargs)

    def refresh_task_panel_status(self, *args, **kwargs):
        return refresh_task_panel_status(self.session, *args, **kwargs)

    def refresh_task_panels(self, *args, **kwargs):
        return refresh_task_panels(self.session, *args, **kwargs)

    def refresh_provider_overlay_mode_panels(self, *args, **kwargs):
        return refresh_provider_overlay_mode_panels(self.session, *args, **kwargs)


def attach_task_panel(session, panel):
    if session.task_panel is panel:
        return
    import FreeCADGui

    gui_document = session.gui_doc
    if FreeCADGui.Control.activeDialog(gui_document):
        raise RuntimeError("Plan Edit cannot start while another task dialog is active")
    panel._task_dialog_document_name = session.doc.Name
    panel._task_dialog_handle = FreeCADGui.Control.showDialog(panel, gui_document)
    session.task_panel = panel


def _get_aux_task_panels(session):
    return session.task_panel_state.aux_task_panels


def attach_aux_task_panel(session, panel):
    aux_panels = _get_aux_task_panels(session)
    if panel is None or panel in aux_panels:
        return
    aux_panels.append(panel)
    try:
        panel.refresh()
    except (AttributeError, RuntimeError):
        session.task_panels.detach_aux_task_panel(panel)


def detach_aux_task_panel(session, panel):
    if panel is None:
        return
    session.task_panel_state.aux_task_panels = [
        item for item in _get_aux_task_panels(session) if item is not panel
    ]


def detach_task_panel(session):
    panel = session.task_panel
    session.task_panel = None
    if panel:
        try:
            mark_closed = getattr(panel, "mark_closed", None)
            if callable(mark_closed):
                mark_closed()
        except Exception:
            pass
        try:
            detach = getattr(panel, "detach", None)
            if callable(detach):
                detach()
            else:
                dispose = getattr(panel, "dispose", None)
                if callable(dispose):
                    dispose()
        except Exception:
            pass
    return panel


def on_panel_closed(session, panel):
    if session.task_panel is panel:
        session.task_panel = None
        if not session.lifecycle_state.finishing:
            session.shutdown(
                close_dialog=False,
                teardown=session.lifecycle_state.tearing_down,
            )
        return
    try:
        mark_closed = getattr(panel, "mark_closed", None)
        if callable(mark_closed):
            mark_closed()
    except Exception:
        pass
    try:
        detach = getattr(panel, "detach", None)
        if callable(detach):
            detach()
        else:
            dispose = getattr(panel, "dispose", None)
            if callable(dispose):
                dispose()
    except Exception:
        pass


def _normalize_task_panel_refresh_reason(reason=None):
    if reason is None:
        return TASK_PANEL_REFRESH_FULL
    normalized_reason = str(reason or "").strip().lower()
    if normalized_reason in _TASK_PANEL_REFRESH_REASONS:
        return normalized_reason
    raise ValueError("Unknown Plan Edit task panel refresh reason: {}".format(reason))


def _refresh_task_panel_instance(panel, reason):
    refresh = getattr(panel, "refresh_for_session", None)
    if callable(refresh):
        refresh(reason)
        return
    if reason == TASK_PANEL_REFRESH_SELECTION:
        refresh = getattr(panel, "refresh_selection_from_session", None)
        if callable(refresh):
            refresh()
            return
    elif reason == TASK_PANEL_REFRESH_PROVIDER_OVERLAY_MODE:
        refresh = getattr(panel, "refresh_provider_overlay_mode_from_session", None)
        if callable(refresh):
            refresh()
            return
    refresh = getattr(panel, "refresh_from_session", None)
    if callable(refresh):
        refresh()


def _refresh_task_panels(session, reason):
    if session.lifecycle_state.tearing_down or not session.document_visuals.document_is_alive():
        return
    if reason != TASK_PANEL_REFRESH_PROVIDER_OVERLAY_MODE:
        session.selection.refresh.sanitize_plan_target_references()
        session.status_text.update_input_hints()
    panel = session.task_panel
    if panel:
        try:
            _refresh_task_panel_instance(panel, reason)
        except (AttributeError, RuntimeError):
            session.task_panels.on_panel_closed(panel)
    stale_panels = []
    for extra_panel in list(_get_aux_task_panels(session)):
        if extra_panel is panel:
            continue
        try:
            _refresh_task_panel_instance(extra_panel, reason)
        except (AttributeError, RuntimeError):
            stale_panels.append(extra_panel)
    for extra_panel in stale_panels:
        session.task_panels.detach_aux_task_panel(extra_panel)


def refresh_task_panels(session, reason=None):
    normalized_reason = _normalize_task_panel_refresh_reason(reason=reason)
    with session.performance.plan_perf_trace_span(
        "refresh_task_panels",
        reason=normalized_reason,
    ):
        _refresh_task_panels(session, normalized_reason)


def refresh_task_panel_status(session, reason=None):
    normalized_reason = _normalize_task_panel_refresh_reason(reason=reason)
    with session.performance.plan_perf_trace_span(
        "refresh_task_panel_status",
        reason=normalized_reason,
    ):
        _refresh_task_panels(session, normalized_reason)


def refresh_provider_overlay_mode_panels(session):
    with session.performance.plan_perf_trace_span("refresh_provider_overlay_mode_panels"):
        _refresh_task_panels(session, TASK_PANEL_REFRESH_PROVIDER_OVERLAY_MODE)
