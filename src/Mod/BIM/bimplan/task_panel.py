# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task panel ownership, refresh helpers, and viewport chip for BIM Plan Edit."""

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


class _PlanEditViewportStatusChip:
    def __new__(cls, session, host_widget):
        from PySide import QtCore, QtGui

        class _Chip(QtGui.QFrame):
            def __init__(self, plan_session, parent_widget):
                super().__init__(parent_widget)
                self.session = plan_session
                self.host_widget = parent_widget
                self.setObjectName("BIMPlanEditViewportStatusChip")
                self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                self.setFocusPolicy(QtCore.Qt.NoFocus)
                self.setFrameShape(QtGui.QFrame.NoFrame)
                self.setStyleSheet("""
                    QFrame#BIMPlanEditViewportStatusChip {
                        background: rgba(250, 250, 248, 230);
                        border: 1px solid rgba(24, 40, 56, 60);
                        border-radius: 10px;
                    }
                    QLabel#BIMPlanEditViewportStatusTitle {
                        color: rgb(25, 32, 38);
                        font-weight: 600;
                    }
                    QLabel#BIMPlanEditViewportStatusBody {
                        color: rgb(60, 68, 76);
                    }
                    """)

                layout = QtGui.QVBoxLayout(self)
                layout.setContentsMargins(12, 10, 12, 10)
                layout.setSpacing(2)

                self.title_label = QtGui.QLabel(self)
                self.title_label.setObjectName("BIMPlanEditViewportStatusTitle")
                self.body_label = QtGui.QLabel(self)
                self.body_label.setObjectName("BIMPlanEditViewportStatusBody")
                self.body_label.setWordWrap(True)
                self.body_label.setMaximumWidth(300)

                layout.addWidget(self.title_label)
                layout.addWidget(self.body_label)

                try:
                    self.host_widget.installEventFilter(self)
                except Exception:
                    pass

            def set_texts(self, title, body):
                self.title_label.setText(title)
                self.body_label.setText(body)
                self.adjustSize()
                self._reposition()
                self.show()
                self.raise_()

            def _reposition(self):
                host = self.host_widget
                if host is None:
                    return
                margin = 14
                max_width = max(180, host.width() - (margin * 2))
                self.setMaximumWidth(max_width)
                self.body_label.setMaximumWidth(max_width - 24)
                self.adjustSize()
                self.move(margin, margin)

            def eventFilter(self, watched, event):
                if watched is self.host_widget and event.type() in (
                    QtCore.QEvent.Resize,
                    QtCore.QEvent.Move,
                    QtCore.QEvent.Show,
                ):
                    self._reposition()
                return QtGui.QFrame.eventFilter(self, watched, event)

            def close_chip(self):
                host = self.host_widget
                if host is not None:
                    try:
                        host.removeEventFilter(self)
                    except Exception:
                        pass
                self.host_widget = None
                self.hide()
                try:
                    self.setParent(None)
                except Exception:
                    pass
                self.deleteLater()

        return _Chip(session, host_widget)


def attach_task_panel(session, panel):
    if session.task_panel is panel:
        return
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
        session.selection.sanitize_plan_target_references()
        session.status_text.update_input_hints()
        session.viewport.refresh_viewport_status_chip()
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
