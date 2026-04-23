# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task panel ownership and refresh helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui

translate = FreeCAD.Qt.translate


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


def clear_input_hints():
    hint_manager = getattr(FreeCADGui, "HintManager", None)
    if not hint_manager or not hasattr(hint_manager, "hide"):
        return
    try:
        hint_manager.hide()
    except Exception:
        pass


def make_input_hint(message, *sequences):
    if not hasattr(FreeCADGui, "InputHint"):
        return None
    if message is None:
        return None
    raw_message = str(message)
    if not raw_message.strip():
        return None
    try:
        return FreeCADGui.InputHint(raw_message, *sequences)
    except Exception:
        return None


def get_input_hint_specs(session):
    ui = FreeCADGui.UserInput
    selected_kind, _selected_obj = session._get_selected_plan_target()

    if session.current_tool == "Select":
        additive_hint = (
            translate("BIM_PlanEdit", "%1 add or remove from selection"),
            (ui.KeyControl, ui.MouseLeft),
        )
        if selected_kind == "opening":
            return (
                (
                    translate("BIM_PlanEdit", "%1 pick opening handle"),
                    ui.MouseLeft,
                ),
                additive_hint,
            )
        if selected_kind == "symbol":
            return (
                (
                    translate("BIM_PlanEdit", "%1 pick symbol handle"),
                    ui.MouseLeft,
                ),
                additive_hint,
            )
        if selected_kind == "wall":
            return (
                (
                    translate("BIM_PlanEdit", "%1 pick wall grip"),
                    ui.MouseLeft,
                ),
                additive_hint,
            )
        if selected_kind == "region":
            return (
                (
                    translate("BIM_PlanEdit", "%1 select another target"),
                    ui.MouseLeft,
                ),
                additive_hint,
            )
        if selected_kind == "space":
            return (
                (
                    translate("BIM_PlanEdit", "%1 select space boundary target"),
                    ui.MouseLeft,
                ),
                additive_hint,
            )
        if selected_kind == "provider":
            provider_handles = tuple(
                session._get_selected_provider_edit_handles(_selected_obj) or ()
            )
            return (
                (
                    translate(
                        "BIM_PlanEdit",
                        (
                            "%1 pick integration handle"
                            if provider_handles
                            else "%1 select another integration target"
                        ),
                    ),
                    ui.MouseLeft,
                ),
                additive_hint,
            )
        return (
            (
                translate(
                    "BIM_PlanEdit",
                    "%1 select wall, opening, symbol, integration target, region, or space",
                ),
                ui.MouseLeft,
            ),
            additive_hint,
        )

    if session.current_tool == "Join":
        hints = [
            (
                translate("BIM_PlanEdit", "%1 pick wall to join"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cycle join type ({joint_type})").format(
                    joint_type=session.get_plan_join_type_label()
                ),
                ui.KeyTab,
            ),
        ]
        if session._get_plan_candidate_joint() is not None:
            hints.append(
                (
                    translate("BIM_PlanEdit", "%1 unjoin pair"),
                    ui.KeyDelete,
                )
            )
        hints.append(
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            )
        )
        return tuple(hints)

    if session.current_tool.startswith("Stretch "):
        return (
            (
                translate("BIM_PlanEdit", "%1 place endpoint"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 edit length"),
                ui.KeyReturn,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        )

    if session.current_tool == "Provider Point":
        return (
            (
                translate("BIM_PlanEdit", "%1 place point for {tool}").format(
                    tool=session._get_provider_point_tool_label()
                ),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        )

    if session.current_tool == "Move Provider":
        return (
            (
                translate("BIM_PlanEdit", "%1 place target"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        )

    return {
        "Window": (
            (
                translate("BIM_PlanEdit", "%1 place window"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
        "Move Opening": (
            (
                translate("BIM_PlanEdit", "%1 place opening"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cycle move anchor"),
                ui.KeyA,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
        "Move Symbol": (
            (
                translate("BIM_PlanEdit", "%1 place symbol"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
        "Rotate Symbol": (
            (
                translate("BIM_PlanEdit", "%1 place rotation"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
        "Move Wall": (
            (
                translate("BIM_PlanEdit", "%1 place wall"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 edit current offset"),
                ui.KeyReturn,
            ),
            (
                translate("BIM_PlanEdit", "%1 cycle X/Y offset"),
                ui.KeyTab,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
        "Set Space Text": (
            (
                translate("BIM_PlanEdit", "%1 place text"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
        "Region": (
            (
                translate("BIM_PlanEdit", "%1 place region point"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 finish region"),
                ui.KeyReturn,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
        "Separator": (
            (
                translate("BIM_PlanEdit", "%1 place separator"),
                ui.MouseLeft,
            ),
            (
                translate("BIM_PlanEdit", "%1 cancel"),
                ui.KeyEscape,
            ),
        ),
    }.get(session.current_tool, ())


def get_input_hints(session):
    return [
        session._make_input_hint(message, *sequences)
        for message, *sequences in session._get_input_hint_specs()
    ]


def update_input_hints(session):
    hint_manager = getattr(FreeCADGui, "HintManager", None)
    if not hint_manager or not hasattr(hint_manager, "show"):
        return
    hints = [hint for hint in session._get_input_hints() if hint is not None]
    if not hints:
        session._clear_input_hints()
        return
    try:
        hint_manager.show(*hints)
    except Exception:
        pass
