# SPDX-License-Identifier: LGPL-2.1-or-later

"""Read-side view models for the Plan Edit task panel."""

from __future__ import annotations

from dataclasses import dataclass

import FreeCAD

from bimplan.providers import (
    PlanContextPanelState,
    PlanContextSubjectKind,
)

translate = FreeCAD.Qt.translate


@dataclass(frozen=True)
class PlanIntegrationPanelViewModel:
    """Derived task-panel state for provider integrations."""

    state_key: object = None
    has_content: bool = False
    tools: tuple = ()
    overlay_items: tuple = ()
    active_overlay_items: tuple = ()
    overlay_mode: str = "architecture"
    grouped_issue_sets: tuple = ()
    summary_sections: tuple = ()
    regular_sections: tuple = ()
    detail_sections: tuple = ()
    context_panel: object | None = None
    context_panel_heading: str = ""
    context_panel_actions: tuple = ()
    has_context_primary: bool = False
    promoted_action_ids: tuple = ()
    hidden_tool_action_labels: tuple = ()
    summary_text: str = ""


@dataclass(frozen=True)
class PlanActionContextViewModel:
    """Derived task-panel state for mode/action controls."""

    mode_label: str = ""
    show_join_options: bool = False
    join_button_enabled: bool = False
    join_button_tooltip: str = ""
    join_type_enabled: bool = False
    join_type_tooltip: str = ""
    unjoin_button_enabled: bool = False
    unjoin_button_tooltip: str = ""
    show_window_button: bool = False
    window_button_enabled: bool = False
    window_button_tooltip: str = ""


def get_action_identity(action):
    return (
        str(getattr(action, "provider_id", "") or "").strip(),
        str(getattr(action, "key", "") or "").strip(),
        str(getattr(action, "label", "") or "").strip(),
    )


def collect_action_identities(actions):
    identities = []
    seen = set()
    for action in tuple(actions or ()):
        identity = get_action_identity(action)
        if identity in seen:
            continue
        seen.add(identity)
        identities.append(identity)
    return tuple(identities)


def collect_action_labels(actions):
    labels = []
    seen = set()
    for action in tuple(actions or ()):
        label = str(getattr(action, "label", "") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return tuple(labels)


def filter_integration_actions(actions, hidden_action_ids=(), hidden_action_labels=()):
    hidden = set(tuple(hidden_action_ids or ()))
    hidden_labels = {str(label or "").strip() for label in tuple(hidden_action_labels or ())}
    visible = []
    for action in tuple(actions or ()):
        if get_action_identity(action) in hidden:
            continue
        if str(getattr(action, "label", "") or "").strip() in hidden_labels:
            continue
        visible.append(action)
    return tuple(visible)


def collect_provider_issue_group_actions(issues):
    actions = []
    seen = set()
    for issue in tuple(issues or ()):
        for action in tuple(getattr(issue, "actions", ()) or ()):
            identity = get_action_identity(action)
            if identity in seen:
                continue
            seen.add(identity)
            actions.append(action)
    return tuple(actions)


def group_provider_issues(issues):
    grouped = []
    groups_by_key = {}
    for issue in tuple(issues or ()):
        group_key = str(getattr(issue, "group_key", "") or "").strip()
        if not group_key:
            grouped.append([issue])
            continue
        group = groups_by_key.get(group_key)
        if group is None:
            group = []
            groups_by_key[group_key] = group
            grouped.append(group)
        group.append(issue)
    return tuple(tuple(group) for group in grouped if group)


def partition_provider_sections(sections):
    summary_sections = []
    detail_sections = []
    regular_sections = []
    for section in tuple(sections or ()):
        role = str(getattr(section, "role", "") or "").strip().lower()
        if role == "summary":
            summary_sections.append(section)
        elif role == "details":
            detail_sections.append(section)
        else:
            regular_sections.append(section)
    return (
        tuple(summary_sections),
        tuple(regular_sections),
        tuple(detail_sections),
    )


def get_provider_context_panel_state_rank(panel):
    return {
        PlanContextPanelState.ACTIVE_TOOL: 0,
        PlanContextPanelState.GEOMETRY_REVIEW: 1,
        PlanContextPanelState.SINGLE_OBJECT: 2,
        PlanContextPanelState.MULTI_SELECTION: 3,
        PlanContextPanelState.EMPTY: 4,
    }.get(getattr(panel, "state", None), 5)


def resolve_provider_context_panel(panels):
    ranked = []
    for index, panel in enumerate(tuple(panels or ())):
        if not panel:
            continue
        ranked.append((get_provider_context_panel_state_rank(panel), index, panel))
    if not ranked:
        return None
    ranked.sort(key=lambda entry: (entry[0], entry[1]))
    return ranked[0][2]


def get_provider_context_panel_heading(panel):
    state = getattr(panel, "state", None)
    subject_kind = getattr(panel, "subject_kind", None)
    if (
        state == PlanContextPanelState.ACTIVE_TOOL
        or subject_kind == PlanContextSubjectKind.INTERACTION
    ):
        return translate("BIM_PlanEdit", "Current Tool")
    if (
        state == PlanContextPanelState.GEOMETRY_REVIEW
        or subject_kind == PlanContextSubjectKind.GEOMETRY
    ):
        return translate("BIM_PlanEdit", "Geometry")
    if state in (
        PlanContextPanelState.SINGLE_OBJECT,
        PlanContextPanelState.MULTI_SELECTION,
    ) or subject_kind in (
        PlanContextSubjectKind.ENDPOINT,
        PlanContextSubjectKind.NETWORK,
        PlanContextSubjectKind.DISTRIBUTION,
    ):
        return translate("BIM_PlanEdit", "Selection")
    return translate("BIM_PlanEdit", "Context")


def collect_provider_context_panel_actions(panel):
    actions = []
    seen = set()
    primary_action = getattr(panel, "primary_action", None)
    has_primary = bool(primary_action and getattr(primary_action, "enabled", False))
    if has_primary:
        identity = get_action_identity(primary_action)
        seen.add(identity)
        actions.append(primary_action)
    for action in tuple(getattr(panel, "secondary_actions", ()) or ()):
        if not bool(getattr(action, "enabled", False)):
            continue
        identity = get_action_identity(action)
        if identity in seen:
            continue
        seen.add(identity)
        actions.append(action)
    return tuple(actions), has_primary


def sort_provider_tools(tools):
    return tuple(
        sorted(
            tuple(tools or ()),
            key=lambda tool: (
                str(getattr(tool, "group", "") or ""),
                int(getattr(tool, "priority", 0) or 0),
                str(getattr(tool, "label", "") or ""),
                str(getattr(tool, "key", "") or ""),
            ),
        )
    )


def build_provider_overlay_legend_items(session, overlays):
    items = []
    seen = set()
    for overlay in tuple(overlays or ()):
        if not bool(getattr(overlay, "visible", True)):
            continue
        provider_id = str(getattr(overlay, "provider_id", "") or "").strip()
        overlay_key = str(getattr(overlay, "key", "") or "").strip()
        if not provider_id or not overlay_key:
            continue
        identity = (provider_id, overlay_key)
        if identity in seen:
            continue
        seen.add(identity)
        label = str(getattr(overlay, "label", "") or "").strip() or overlay_key
        provider_label = session.get_plan_provider_display_name(provider_id)
        if provider_label:
            label = translate("BIM_PlanEdit", "{provider}: {label}").format(
                provider=provider_label,
                label=label,
            )
        category = session.get_plan_provider_overlay_category(overlay)
        items.append(
            (
                provider_id,
                overlay_key,
                label,
                tuple(getattr(overlay, "color", ()) or ()),
                session.is_plan_provider_overlay_enabled(overlay),
                category,
            )
        )
    return tuple(items)


def filter_provider_overlay_legend_items_for_mode(items, active_mode="architecture"):
    mode_key = str(active_mode or "architecture").strip().lower()
    if mode_key == "all":
        return tuple(items or ())
    return tuple(
        item for item in tuple(items or ()) if len(item) > 5 and str(item[5] or "") == mode_key
    )


def build_integration_panel_summary_text(
    issues,
    sections,
    tools=(),
    overlay_items=(),
    summary_sections=(),
    context_panel=None,
):
    if tuple(summary_sections or ()) or context_panel is not None:
        return ""
    parts = []
    issue_count = len(issues or ())
    section_count = len(sections or ())
    tool_count = len(tools or ())
    overlay_count = len(overlay_items or ())
    if issue_count:
        parts.append(translate("BIM_PlanEdit", "{count} issue(s)").format(count=issue_count))
    if tool_count:
        parts.append(translate("BIM_PlanEdit", "{count} tool(s)").format(count=tool_count))
    if overlay_count:
        parts.append(translate("BIM_PlanEdit", "{count} overlay(s)").format(count=overlay_count))
    if section_count:
        parts.append(translate("BIM_PlanEdit", "{count} section(s)").format(count=section_count))
    if not parts:
        return ""
    return translate("BIM_PlanEdit", "Plan guidance: {details}.").format(details=", ".join(parts))


def build_integration_panel_view_model(session, snapshot):
    tools = sort_provider_tools(getattr(snapshot, "tools", ()))
    overlay_items = build_provider_overlay_legend_items(session, getattr(snapshot, "overlays", ()))
    overlay_mode = str(session.get_plan_provider_overlay_mode() or "architecture")
    active_overlay_items = filter_provider_overlay_legend_items_for_mode(
        overlay_items,
        active_mode=overlay_mode,
    )
    summary_sections, regular_sections, detail_sections = partition_provider_sections(
        getattr(snapshot, "inspector_sections", ())
    )
    context_panel = resolve_provider_context_panel(getattr(snapshot, "context_panels", ()))
    context_panel_actions, has_context_primary = (
        collect_provider_context_panel_actions(context_panel)
        if context_panel is not None
        else ((), False)
    )
    grouped_issue_sets = group_provider_issues(getattr(snapshot, "issues", ()))
    promoted_action_ids = collect_action_identities(
        action
        for section in summary_sections
        for action in tuple(getattr(section, "actions", ()) or ())
    )
    hidden_tool_action_labels = collect_action_labels(
        tuple(
            action
            for section in summary_sections
            for action in tuple(getattr(section, "actions", ()) or ())
        )
        + tuple(
            action
            for issue_group in grouped_issue_sets
            for action in filter_integration_actions(
                collect_provider_issue_group_actions(issue_group),
                hidden_action_ids=promoted_action_ids,
            )
        )
        + tuple(
            action
            for section in regular_sections
            for action in tuple(getattr(section, "actions", ()) or ())
        )
        + tuple(context_panel_actions)
    )
    summary_text = build_integration_panel_summary_text(
        getattr(snapshot, "issues", ()),
        getattr(snapshot, "inspector_sections", ()),
        tools=tools,
        overlay_items=active_overlay_items,
        summary_sections=summary_sections,
        context_panel=context_panel,
    )
    return PlanIntegrationPanelViewModel(
        state_key=snapshot,
        has_content=not bool(getattr(snapshot, "is_empty", lambda: True)()),
        tools=tools,
        overlay_items=overlay_items,
        active_overlay_items=active_overlay_items,
        overlay_mode=overlay_mode,
        grouped_issue_sets=grouped_issue_sets,
        summary_sections=summary_sections,
        regular_sections=regular_sections,
        detail_sections=detail_sections,
        context_panel=context_panel,
        context_panel_heading=(
            get_provider_context_panel_heading(context_panel) if context_panel is not None else ""
        ),
        context_panel_actions=context_panel_actions,
        has_context_primary=has_context_primary,
        promoted_action_ids=promoted_action_ids,
        hidden_tool_action_labels=hidden_tool_action_labels,
        summary_text=summary_text,
    )


def build_action_context_view_model(session, modal_active=None):
    if modal_active is None:
        modal_active = session._is_modal_plan_interaction_active()
    selected_kind, selected_obj = session.selection.get_selected_plan_target()
    current_tool = str(session.current_tool or "")
    has_wall = selected_kind == "wall" and selected_obj is not None
    can_place_window = session.can_place_plan_window()
    in_join_mode = current_tool == "Join"
    join_candidate = session._get_plan_candidate_joint() is not None if in_join_mode else False
    enabled = not bool(modal_active)
    mode_label = (
        session._get_provider_point_tool_label()
        if current_tool == "Provider Point"
        else current_tool
    )
    join_button_tooltip = (
        translate("BIM_PlanEdit", "Join the selected wall to another wall.")
        if has_wall
        else translate("BIM_PlanEdit", "Select a wall before using Join.")
    )
    if not in_join_mode:
        unjoin_tooltip = translate(
            "BIM_PlanEdit",
            "Start Join mode and hover an existing joined wall pair.",
        )
    elif not join_candidate:
        unjoin_tooltip = translate(
            "BIM_PlanEdit",
            "Hover an existing joined wall pair before using Unjoin.",
        )
    else:
        unjoin_tooltip = translate(
            "BIM_PlanEdit",
            "Remove the hovered existing wall joint.",
        )
    window_button_tooltip = (
        translate(
            "BIM_PlanEdit",
            "Place a hosted window on the selected or hovered wall.",
        )
        if can_place_window
        else translate(
            "BIM_PlanEdit",
            "Select or hover a wall before placing a window.",
        )
    )
    show_join_options = has_wall or in_join_mode
    return PlanActionContextViewModel(
        mode_label=mode_label,
        show_join_options=show_join_options,
        join_button_enabled=enabled and has_wall,
        join_button_tooltip=join_button_tooltip,
        join_type_enabled=enabled and show_join_options,
        join_type_tooltip=translate(
            "BIM_PlanEdit",
            "Joint type used when joining wall pairs.",
        ),
        unjoin_button_enabled=enabled and in_join_mode and join_candidate,
        unjoin_button_tooltip=unjoin_tooltip,
        show_window_button=can_place_window or current_tool == "Window",
        window_button_enabled=enabled and can_place_window,
        window_button_tooltip=window_button_tooltip,
    )
