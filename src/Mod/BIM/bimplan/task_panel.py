# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task panel ownership, refresh helpers, and viewport chip for BIM Plan Edit."""


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
                self.deleteLater()

        return _Chip(session, host_widget)


def attach_task_panel(session, panel):
    if session.task_panel is panel:
        return
    session.task_panel = panel


def attach_aux_task_panel(session, panel):
    if panel is None or panel in session._aux_task_panels:
        return
    session._aux_task_panels.append(panel)
    try:
        panel.refresh()
    except (AttributeError, RuntimeError):
        session.detach_aux_task_panel(panel)


def detach_aux_task_panel(session, panel):
    if panel is None:
        return
    session._aux_task_panels = [item for item in session._aux_task_panels if item is not panel]


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
        if not session._finishing:
            session.shutdown(close_dialog=False, teardown=session._tearing_down)
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


def refresh_task_panel_status(session, selection_only=False):
    with session.performance.plan_perf_trace_span(
        "refresh_task_panel_status",
        selection_only=bool(selection_only),
    ):
        if session._tearing_down or not session._document_is_alive():
            return
        session._sanitize_plan_target_references()
        session.status_text.update_input_hints()
        session.viewport.refresh_viewport_status_chip()
        panel = session.task_panel
        if panel:
            try:
                refresh = None
                if selection_only:
                    refresh = getattr(panel, "refresh_selection_from_session", None)
                if not callable(refresh):
                    refresh = getattr(panel, "refresh_from_session", None)
                if callable(refresh):
                    refresh()
            except (AttributeError, RuntimeError):
                session.on_panel_closed(panel)
        stale_panels = []
        for extra_panel in list(session._aux_task_panels):
            if extra_panel is panel:
                continue
            try:
                refresh = None
                if selection_only:
                    refresh = getattr(extra_panel, "refresh_selection_from_session", None)
                if not callable(refresh):
                    refresh = getattr(extra_panel, "refresh_from_session", None)
                if callable(refresh):
                    refresh()
            except (AttributeError, RuntimeError):
                stale_panels.append(extra_panel)
        for extra_panel in stale_panels:
            session.detach_aux_task_panel(extra_panel)


def refresh_provider_overlay_mode_panels(session):
    with session.performance.plan_perf_trace_span("refresh_provider_overlay_mode_panels"):
        if session._tearing_down or not session._document_is_alive():
            return
        panel = session.task_panel
        if panel:
            try:
                refresh = getattr(panel, "refresh_provider_overlay_mode_from_session", None)
                if not callable(refresh):
                    refresh = getattr(panel, "refresh_from_session", None)
                if callable(refresh):
                    refresh()
            except (AttributeError, RuntimeError):
                session.on_panel_closed(panel)
        stale_panels = []
        for extra_panel in list(session._aux_task_panels):
            if extra_panel is panel:
                continue
            try:
                refresh = getattr(
                    extra_panel,
                    "refresh_provider_overlay_mode_from_session",
                    None,
                )
                if not callable(refresh):
                    refresh = getattr(extra_panel, "refresh_from_session", None)
                if callable(refresh):
                    refresh()
            except (AttributeError, RuntimeError):
                stale_panels.append(extra_panel)
        for extra_panel in stale_panels:
            session.detach_aux_task_panel(extra_panel)
