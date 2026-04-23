# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task panel ownership and refresh helpers for BIM Plan Edit."""


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
    with session._plan_perf_trace_span(
        "refresh_task_panel_status",
        selection_only=bool(selection_only),
    ):
        if session._tearing_down or not session._document_is_alive():
            return
        session._sanitize_plan_target_references()
        session._update_input_hints()
        session._refresh_viewport_status_chip()
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
    with session._plan_perf_trace_span("refresh_provider_overlay_mode_panels"):
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
