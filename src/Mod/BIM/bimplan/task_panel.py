# SPDX-License-Identifier: LGPL-2.1-or-later

"""Task panel ownership and refresh helpers for BIM Plan Edit."""

import FreeCAD
import FreeCADGui
from bimplan import provider_targets as plan_provider_targets

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


def format_status_chip_action(message):
    if not message:
        return ""
    text = str(message)
    if text.startswith("%1 "):
        text = text[3:]
    elif text.startswith("%1"):
        text = text[2:]
    text = text.strip()
    if not text:
        return ""
    return text[0].upper() + text[1:]


def get_plan_target_display_label(obj):
    return getattr(obj, "Label", getattr(obj, "Name", ""))


def format_provider_target_role_label(session, obj):
    return plan_provider_targets.get_plan_provider_target_role_label(session, obj)


def format_provider_target_help(session, obj):
    return plan_provider_targets.format_plan_provider_target_help(session, obj)


def get_opening_display_kind_key(session, opening):
    if not opening:
        return "Opening"
    semantic_obj = session._get_plan_semantic_object(opening)
    ifc_type = getattr(semantic_obj, "IfcType", "") if semantic_obj else ""
    if ifc_type in {"Window", "Door"}:
        return ifc_type
    try:
        import Draft

        if Draft.getType(semantic_obj) == "Window":
            return "Window"
    except Exception:
        pass
    return "Opening"


def get_opening_display_kind(session, opening):
    return translate("BIM_PlanEdit", session._get_opening_display_kind_key(opening))


def format_opening_selection_help(session, opening):
    opening_kind = session._get_opening_display_kind_key(opening)
    if opening_kind == "Door":
        return translate(
            "BIM_PlanEdit",
            "Use in-view handles to move or flip the selected door.",
        )
    if opening_kind == "Window":
        help_text = translate(
            "BIM_PlanEdit",
            "Use the in-view handle to move the selected window along its host wall.",
        )
        can_edit_width = session._can_edit_window_width(opening)
        can_edit_height = session._can_edit_window_height(opening)
        can_apply_style = session._can_apply_window_style_preset(opening)
        if (can_edit_width or can_edit_height) and can_apply_style:
            help_text = "{} {}".format(
                help_text,
                translate(
                    "BIM_PlanEdit",
                    "Use the window controls below to change its width, height, or style.",
                ),
            )
        elif can_edit_width and can_edit_height:
            help_text = "{} {}".format(
                help_text,
                translate(
                    "BIM_PlanEdit",
                    "Use the window controls below to change its width or height.",
                ),
            )
        elif can_edit_width:
            help_text = "{} {}".format(
                help_text,
                translate(
                    "BIM_PlanEdit",
                    "Use the window controls below to change its width.",
                ),
            )
        elif can_edit_height:
            help_text = "{} {}".format(
                help_text,
                translate(
                    "BIM_PlanEdit",
                    "Use the window controls below to change its height.",
                ),
            )
        elif can_apply_style:
            help_text = "{} {}".format(
                help_text,
                translate(
                    "BIM_PlanEdit",
                    "Use the window controls below to change its style.",
                ),
            )
        return help_text
    return translate(
        "BIM_PlanEdit",
        "Use in-view handles to move or flip the selected opening.",
    )


def format_plan_target_selection_state(session, kind, obj):
    if not kind or not obj:
        return ""
    if kind == "opening":
        return translate("BIM_PlanEdit", "{kind}: {label}").format(
            kind=session._get_opening_display_kind(obj),
            label=session._get_plan_target_display_label(obj),
        )
    templates = {
        "symbol": translate("BIM_PlanEdit", "Symbol: {label}"),
        "region": translate("BIM_PlanEdit", "Region: {label}"),
        "space": translate("BIM_PlanEdit", "Space: {label}"),
        "wall": translate("BIM_PlanEdit", "Wall: {label}"),
    }
    if kind == "provider":
        return translate("BIM_PlanEdit", "{kind}: {label}").format(
            kind=session._format_provider_target_role_label(obj),
            label=session._get_plan_target_display_label(obj),
        )
    template = templates.get(kind)
    if not template:
        return ""
    return template.format(label=session._get_plan_target_display_label(obj))


def get_provider_selected_objects(session):
    return tuple(session._normalize_gui_object_selection(session._provider_selected_objects))


def format_provider_selected_object_state(session):
    objects = session._get_provider_selected_objects()
    if not objects:
        return ""
    if len(objects) == 1:
        return translate("BIM_PlanEdit", "Object: {label}").format(
            label=session._get_plan_target_display_label(objects[0])
        )
    return translate("BIM_PlanEdit", "{count} integration objects selected").format(
        count=len(objects)
    )


def format_provider_selected_object_help(session):
    if not session._get_provider_selected_objects():
        return ""
    return translate(
        "BIM_PlanEdit",
        "Use the integration details and actions below for the selected object.",
    )


def get_status_chip_text(session):
    title = translate("BIM_PlanEdit", "Plan Edit · {tool}").format(tool=session.current_tool)
    selected_kind, selected_obj = session._get_selected_plan_target()
    selected_context = session._format_plan_target_selection_state(selected_kind, selected_obj)
    provider_context = session._format_provider_selected_object_state()
    provider_action = session._format_provider_selected_object_help()

    if session.current_tool == "Provider Point":
        title = translate("BIM_PlanEdit", "Plan Edit · {tool}").format(
            tool=session._get_provider_point_tool_label()
        )
        return title, session._get_provider_point_tool_prompt()

    if session.current_tool == "Move Opening":
        context = (
            selected_context
            if selected_kind == "opening" and selected_obj is not None
            else translate("BIM_PlanEdit", "Opening move")
        )
        action = translate("BIM_PlanEdit", "Click target point")
        return title, "{}\n{}".format(context, action)

    if session.current_tool == "Move Symbol":
        context = (
            selected_context
            if selected_kind == "symbol" and selected_obj is not None
            else translate("BIM_PlanEdit", "Symbol move")
        )
        action = translate("BIM_PlanEdit", "Click target point")
        return title, "{}\n{}".format(context, action)

    if session.current_tool == "Move Provider":
        context = (
            selected_context
            if selected_kind == "provider" and selected_obj is not None
            else translate("BIM_PlanEdit", "Integration move")
        )
        action = translate("BIM_PlanEdit", "Click target point")
        return title, "{}\n{}".format(context, action)

    if session.current_tool == "Rotate Symbol":
        context = (
            selected_context
            if selected_kind == "symbol" and selected_obj is not None
            else translate("BIM_PlanEdit", "Symbol rotation")
        )
        if session._symbol_rotation_snap_enabled():
            action = translate(
                "BIM_PlanEdit", "Click target angle ({snap} snap, Shift = free)"
            ).format(snap=session._format_symbol_rotation_snap_label())
        else:
            action = translate("BIM_PlanEdit", "Click target angle")
        return title, "{}\n{}".format(context, action)

    if session.current_tool == "Move Wall":
        context = (
            selected_context
            if selected_kind == "wall" and selected_obj is not None
            else translate("BIM_PlanEdit", "Wall move")
        )
        action = translate("BIM_PlanEdit", "Click target point")
        return title, "{}\n{}".format(context, action)

    if session.current_tool == "Join":
        target_wall, joint, detail = session._get_plan_join_candidate_state()
        context = (
            translate("BIM_PlanEdit", "Source wall: {label}").format(
                label=session._get_plan_target_display_label(selected_obj)
            )
            if selected_kind == "wall" and selected_obj is not None
            else translate("BIM_PlanEdit", "Wall join")
        )
        action = session._get_plan_join_mode_action_text(target_wall, joint)
        if detail:
            return title, "{}\n{}\n{}".format(context, detail, action)
        return title, "{}\n{}".format(context, action)

    if session.current_tool.startswith("Stretch "):
        context = (
            selected_context
            if selected_kind == "wall" and selected_obj is not None
            else translate("BIM_PlanEdit", "Wall stretch")
        )
        action = translate("BIM_PlanEdit", "Click endpoint or press Enter to type a value")
        return title, "{}\n{}".format(context, action)

    if session.current_tool == "Region":
        context = (
            translate("BIM_PlanEdit", "Parent space: {label}").format(
                label=session._plan_region_parent_space.Label
            )
            if session._is_plan_space_object(session._plan_region_parent_space)
            else translate("BIM_PlanEdit", "Plan region")
        )
        action = translate(
            "BIM_PlanEdit",
            "Click polygon points, press Enter to finish, or click near the first point to close",
        )
        return title, "{}\n{}".format(context, action)

    if selected_context:
        context = selected_context
    elif provider_context:
        context = provider_context
    else:
        context = translate("BIM_PlanEdit", "Storey: {label}").format(
            label=session.get_storey_label(session.active_storey)
        )

    selection_summary = session._get_plan_selection_summary_text()
    if selection_summary:
        context = "{}\n{}".format(context, selection_summary)

    hints = session._get_input_hint_specs()
    action = session._format_status_chip_action(hints[0][0]) if hints else ""
    if selected_kind == "region" and session.current_tool == "Select":
        action = translate(
            "BIM_PlanEdit",
            "Edit label, scheme, type, and parent space in the task panel",
        )
    if (selected_kind == "provider" or provider_context) and session.current_tool == "Select":
        if selected_kind == "provider":
            action = session._format_provider_target_help(selected_obj)
        else:
            action = provider_action
    if session._plan_relation_status_message:
        action = session._plan_relation_status_message
    if not action:
        action = translate("BIM_PlanEdit", "Work directly in the viewport")
    return title, "{}\n{}".format(context, action)


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
