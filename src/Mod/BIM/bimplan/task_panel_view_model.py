# SPDX-License-Identifier: LGPL-2.1-or-later

"""Read-side view models for the Plan Edit task panel."""

from __future__ import annotations

from dataclasses import dataclass

import FreeCAD

from bimplan import selection as plan_selection
from bimplan.providers import (
    PlanContextPanelState,
    PlanContextSubjectKind,
)

translate = FreeCAD.Qt.translate

_MISSING = object()
_TASK_PANEL_CONTEXT_METHODS = (
    "get_current_tool",
    "get_selected_plan_target",
    "get_selected_plan_targets",
)


def _read_component(session, component_name, method_name, *args, default=None):
    component = getattr(session, component_name, None)
    method = getattr(component, method_name, None)
    if callable(method):
        return method(*args)
    return default


class PlanTaskPanelContext:
    """Thin read-only adapter around the live Plan Edit session."""

    def __init__(self, session):
        self.session = session

    def get_current_tool(self):
        return str(self.session.current_tool or "")

    def get_selected_plan_target(self):
        return plan_selection.get_selected_plan_target(self.session)

    def get_selected_plan_targets(self):
        return plan_selection.get_selected_plan_targets(self.session)

    def is_modal_plan_interaction_active(self):
        return bool(
            _read_component(
                self.session,
                "interaction",
                "is_modal_plan_interaction_active",
                default=False,
            )
        )

    def can_place_plan_window(self):
        return bool(
            _read_component(
                self.session,
                "windows",
                "can_place_window",
                default=False,
            )
        )

    def has_plan_candidate_joint(self):
        return (
            _read_component(
                self.session,
                "wall_relations",
                "get_plan_candidate_joint",
            )
            is not None
        )

    def get_provider_point_tool_label(self):
        return _read_component(
            self.session,
            "providers",
            "get_provider_point_tool_label",
            default="",
        )

    def get_provider_point_tool_prompt(self):
        return _read_component(
            self.session,
            "providers",
            "get_provider_point_tool_prompt",
            default="",
        )

    def get_plan_provider_display_name(self, provider_id):
        return _read_component(
            self.session,
            "providers",
            "get_plan_provider_display_name",
            provider_id,
            default=str(provider_id or "").strip(),
        )

    def get_plan_provider_overlay_category(self, overlay):
        return _read_component(
            self.session,
            "providers",
            "get_plan_provider_overlay_category",
            overlay,
            default="architecture",
        )

    def is_plan_provider_overlay_enabled(self, overlay):
        return bool(
            _read_component(
                self.session,
                "providers",
                "is_plan_provider_overlay_enabled",
                overlay,
                default=True,
            )
        )

    def get_plan_provider_overlay_mode(self):
        return str(
            _read_component(
                self.session,
                "providers",
                "get_plan_provider_overlay_mode",
                default="architecture",
            )
            or "architecture"
        )

    def format_plan_target_selection_state(self, target_kind, target_obj):
        return _read_component(
            self.session,
            "status_text",
            "format_plan_target_selection_state",
            target_kind,
            target_obj,
            default="",
        )

    def format_provider_selected_object_state(self):
        return _read_component(
            self.session,
            "status_text",
            "format_provider_selected_object_state",
            default="",
        )

    def get_plan_join_candidate_state(self):
        return _read_component(
            self.session,
            "wall_relations",
            "get_plan_join_candidate_state",
            default=(None, None, ""),
        )

    def get_plan_target_display_label(self, obj):
        return _read_component(
            self.session,
            "status_text",
            "get_plan_target_display_label",
            obj,
            default=str(getattr(obj, "Label", "") or getattr(obj, "Name", "") or "").strip(),
        )

    def get_plan_join_type_label(self):
        return _read_component(
            self.session,
            "wall_relations",
            "get_plan_join_type_label",
            default="",
        )

    def get_plan_join_mode_action_text(self, target_wall, joint):
        return _read_component(
            self.session,
            "wall_relations",
            "get_plan_join_mode_action_text",
            target_wall,
            joint,
            default="",
        )

    def summarize_plan_targets(self, targets):
        return _read_component(
            self.session,
            "status_text",
            "summarize_plan_targets",
            targets,
            default="",
        )

    def get_space_region_candidate_count(self):
        value = _read_component(
            self.session,
            "spaces",
            "get_space_region_candidate_count",
            default=_MISSING,
        )
        if value is _MISSING:
            value = len(getattr(self.session, "_space_region_candidates", ()) or ())
        return int(value or 0)

    def get_hovered_space_region_candidate(self):
        value = _read_component(
            self.session,
            "spaces",
            "get_hovered_space_region_candidate",
        )
        if value is not None:
            return value
        return getattr(self.session, "_hovered_space_region_candidate", None)

    def format_space_region_candidate_area(self, candidate):
        return _read_component(
            self.session,
            "spaces",
            "format_space_region_candidate_area",
            candidate,
            default="",
        )

    def get_plan_region_parent_space(self):
        value = _read_component(
            self.session,
            "spaces",
            "get_plan_region_parent_space",
        )
        if value is not None:
            return value
        return getattr(self.session, "_plan_region_parent_space", None)

    def is_plan_space_object(self, obj):
        return bool(
            _read_component(
                self.session,
                "spaces",
                "is_plan_space_object",
                obj,
                default=False,
            )
        )

    def format_opening_selection_help(self, obj):
        return _read_component(
            self.session,
            "status_text",
            "format_opening_selection_help",
            obj,
            default="",
        )

    def symbol_rotation_snap_enabled(self):
        return bool(
            _read_component(
                self.session,
                "symbols",
                "symbol_rotation_snap_enabled",
                default=False,
            )
        )

    def format_symbol_rotation_snap_label(self):
        return _read_component(
            self.session,
            "symbols",
            "format_symbol_rotation_snap_label",
            default="",
        )

    def format_provider_target_help(self, obj):
        return _read_component(
            self.session,
            "status_text",
            "format_provider_target_help",
            obj,
            default="",
        )

    def is_selected_wall_endpoint_editable(self):
        return bool(
            _read_component(
                self.session,
                "wall_edit",
                "is_selected_wall_endpoint_editable",
                default=False,
            )
        )

    def format_provider_selected_object_help(self):
        return _read_component(
            self.session,
            "status_text",
            "format_provider_selected_object_help",
            default="",
        )

    def get_plan_selection_summary_text(self):
        return _read_component(
            self.session,
            "status_text",
            "get_plan_selection_summary_text",
            default="",
        )

    def get_plan_relation_status_message(self):
        value = _read_component(
            self.session,
            "wall_relations",
            "get_plan_relation_status_message",
        )
        if value is None:
            value = getattr(self.session, "_plan_relation_status_message", "")
        return str(value or "").strip()

    def get_window_style_preset_options(self):
        return tuple(
            _read_component(
                self.session,
                "windows",
                "get_window_style_preset_options",
                default=(),
            )
            or ()
        )

    def can_edit_window_width(self, obj):
        return bool(
            _read_component(
                self.session,
                "windows",
                "can_edit_window_width",
                obj,
                default=False,
            )
        )

    def can_edit_window_height(self, obj):
        return bool(
            _read_component(
                self.session,
                "windows",
                "can_edit_window_height",
                obj,
                default=False,
            )
        )

    def can_apply_window_style_preset(self, obj):
        return bool(
            _read_component(
                self.session,
                "windows",
                "can_apply_window_style_preset",
                obj,
                default=False,
            )
        )

    def get_selected_window_style_preset(self):
        return str(
            _read_component(
                self.session,
                "windows",
                "get_selected_window_style_preset",
                default="",
            )
            or ""
        )

    def get_selected_window_width_text(self):
        return str(
            _read_component(
                self.session,
                "windows",
                "get_selected_window_width_text",
                default="",
            )
            or ""
        )

    def get_selected_window_height_text(self):
        return str(
            _read_component(
                self.session,
                "windows",
                "get_selected_window_height_text",
                default="",
            )
            or ""
        )


def as_task_panel_context(session_or_context):
    if isinstance(session_or_context, PlanTaskPanelContext) or all(
        hasattr(session_or_context, method_name) for method_name in _TASK_PANEL_CONTEXT_METHODS
    ):
        return session_or_context
    return PlanTaskPanelContext(session_or_context)


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


@dataclass(frozen=True)
class PlanStatusTextViewModel:
    """Derived status/guidance text for the task panel."""

    text: str = ""


@dataclass(frozen=True)
class PlanSpaceEditorViewModel:
    """Derived visibility/target state for the space editor."""

    show_editor: bool = False
    space: object | None = None


@dataclass(frozen=True)
class PlanRegionEditorViewModel:
    """Derived visibility/target state for the region editor."""

    show_editor: bool = False
    region: object | None = None


@dataclass(frozen=True)
class PlanWindowEditorViewModel:
    """Derived visibility/state for the window editor."""

    show_editor: bool = False
    window: object | None = None
    state_key: tuple = ()
    combo_items: tuple = ()
    current_style: str = ""
    current_width_text: str = ""
    current_height_text: str = ""
    note_text: str = ""
    can_edit_width: bool = False
    can_edit_height: bool = False
    can_apply_style: bool = False


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


def build_provider_overlay_legend_items(session_or_context, overlays):
    context = as_task_panel_context(session_or_context)
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
        provider_label = context.get_plan_provider_display_name(provider_id)
        if provider_label:
            label = translate("BIM_PlanEdit", "{provider}: {label}").format(
                provider=provider_label,
                label=label,
            )
        category = context.get_plan_provider_overlay_category(overlay)
        items.append(
            (
                provider_id,
                overlay_key,
                label,
                tuple(getattr(overlay, "color", ()) or ()),
                context.is_plan_provider_overlay_enabled(overlay),
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


def build_integration_panel_view_model(session_or_context, snapshot):
    context = as_task_panel_context(session_or_context)
    tools = sort_provider_tools(getattr(snapshot, "tools", ()))
    overlay_items = build_provider_overlay_legend_items(context, getattr(snapshot, "overlays", ()))
    overlay_mode = context.get_plan_provider_overlay_mode()
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


def build_action_context_view_model(session_or_context, modal_active=None):
    context = as_task_panel_context(session_or_context)
    if modal_active is None:
        modal_active = context.is_modal_plan_interaction_active()
    selected_kind, selected_obj = context.get_selected_plan_target()
    current_tool = context.get_current_tool()
    has_wall = selected_kind == "wall" and selected_obj is not None
    can_place_window = context.can_place_plan_window()
    in_join_mode = current_tool == "Join"
    join_candidate = context.has_plan_candidate_joint() if in_join_mode else False
    enabled = not bool(modal_active)
    mode_label = (
        context.get_provider_point_tool_label()
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


def get_editor_object_key(obj):
    if obj is None:
        return None
    return (
        getattr(getattr(obj, "Document", None), "Name", None),
        getattr(obj, "Name", None),
    )


def _append_status_help_line(text, line):
    line = str(line or "").strip()
    if not line:
        return text
    if not text:
        return line
    return "{}\n{}".format(text, line)


def build_status_text_view_model(session_or_context):
    context = as_task_panel_context(session_or_context)
    tool = context.get_current_tool()
    selected_kind, selected_obj = context.get_selected_plan_target()
    selected_state = context.format_plan_target_selection_state(
        selected_kind,
        selected_obj,
    )
    provider_state = context.format_provider_selected_object_state()
    if tool == "Join" and selected_kind == "wall" and selected_obj is not None:
        target_wall, joint, detail = context.get_plan_join_candidate_state()
        selection_state = translate("BIM_PlanEdit", "Source wall: {label}").format(
            label=context.get_plan_target_display_label(selected_obj)
        )
        selection_help = translate(
            "BIM_PlanEdit",
            "Join type: {joint_type}\n{pair_state}\n{action}",
        ).format(
            joint_type=context.get_plan_join_type_label(),
            pair_state=detail or translate("BIM_PlanEdit", "Candidate wall: none"),
            action=context.get_plan_join_mode_action_text(target_wall, joint),
        )
    elif tool == "Pick Space Region":
        selection_state = translate("BIM_PlanEdit", "Space creation: pick region")
        selection_help = translate(
            "BIM_PlanEdit",
            "Multiple enclosed regions were found. Hover a dashed outline, then click to create that space.",
        )
        targets = context.get_selected_plan_targets()
        if targets:
            selection_help = _append_status_help_line(
                selection_help,
                translate("BIM_PlanEdit", "Boundary candidates: {summary}").format(
                    summary=context.summarize_plan_targets(targets)
                ),
            )
        candidate_count = context.get_space_region_candidate_count()
        if candidate_count:
            selection_help = _append_status_help_line(
                selection_help,
                translate("BIM_PlanEdit", "{count} enclosed regions are available.").format(
                    count=candidate_count
                ),
            )
        hovered_candidate = context.get_hovered_space_region_candidate()
        if hovered_candidate:
            selection_help = _append_status_help_line(
                selection_help,
                translate("BIM_PlanEdit", "Hovered region area: {area}").format(
                    area=context.format_space_region_candidate_area(hovered_candidate)
                ),
            )
    elif tool == "Region":
        selection_state = translate("BIM_PlanEdit", "Region: draw polygon")
        selection_help = translate(
            "BIM_PlanEdit",
            "Click polygon points to define a semantic plan region. Press Enter to finish, or click near the first point to close.",
        )
        parent_space = context.get_plan_region_parent_space()
        if context.is_plan_space_object(parent_space):
            selection_help = _append_status_help_line(
                selection_help,
                translate("BIM_PlanEdit", "Parent space: {label}").format(label=parent_space.Label),
            )
    elif tool == "Separator":
        selection_state = translate("BIM_PlanEdit", "Separator: place divider")
        selection_help = translate(
            "BIM_PlanEdit",
            "Click two points to place a room divider that can split Arch Spaces.",
        )
    elif tool == "Window":
        selection_state = translate("BIM_PlanEdit", "Window: place on wall")
        selection_help = translate(
            "BIM_PlanEdit",
            "Click along the selected or hovered wall to place a hosted window.",
        )
    elif tool == "Provider Point":
        selection_state = context.get_provider_point_tool_label()
        selection_help = context.get_provider_point_tool_prompt()
    elif selected_kind == "opening" and selected_obj is not None:
        selection_state = selected_state
        selection_help = context.format_opening_selection_help(selected_obj)
    elif selected_kind == "symbol" and selected_obj is not None:
        selection_state = selected_state
        if tool == "Rotate Symbol":
            if context.symbol_rotation_snap_enabled():
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use in-view handles to rotate the selected symbol instance. Rotation snaps to {snap} by default; hold Shift for free angle.",
                ).format(snap=context.format_symbol_rotation_snap_label())
            else:
                selection_help = translate(
                    "BIM_PlanEdit",
                    "Use in-view handles to rotate the selected symbol instance.",
                )
        else:
            selection_help = translate(
                "BIM_PlanEdit",
                "Use in-view handles to move or rotate the selected symbol instance.",
            )
    elif selected_kind == "region" and selected_obj is not None:
        selection_state = selected_state
        selection_help = translate(
            "BIM_PlanEdit",
            "Use the region controls below to edit label, scheme, type, and parent space.",
        )
    elif selected_kind == "space" and selected_obj is not None:
        selection_state = selected_state
        selection_help = translate(
            "BIM_PlanEdit",
            "Use the space controls below to edit label, type, boundaries, and text position.",
        )
    elif selected_kind == "provider" and selected_obj is not None:
        selection_state = selected_state
        selection_help = context.format_provider_target_help(selected_obj)
    elif selected_kind == "wall" and selected_obj is not None:
        selection_state = selected_state
        if context.is_selected_wall_endpoint_editable():
            selection_help = translate(
                "BIM_PlanEdit",
                "Use wall grips in the viewport to stretch or move the selected wall.",
            )
        else:
            selection_help = translate(
                "BIM_PlanEdit",
                "This wall can be reviewed in plan, but grip editing is unavailable.",
            )
    elif provider_state:
        selection_state = provider_state
        selection_help = context.format_provider_selected_object_help()
    else:
        selection_state = translate("BIM_PlanEdit", "No target selected")
        selection_help = translate(
            "BIM_PlanEdit",
            "Click a wall, opening, symbol, integration target, region, or space. Use create tools to add plan geometry.",
        )

    selection_summary = context.get_plan_selection_summary_text()
    if selection_summary:
        selection_help = _append_status_help_line(selection_help, selection_summary)
    if tool == "Select":
        selection_help = _append_status_help_line(
            selection_help,
            translate(
                "BIM_PlanEdit",
                "Ctrl-click adds or removes targets without replacing the current editor target.",
            ),
        )
    relation_status = context.get_plan_relation_status_message()
    if relation_status:
        selection_help = _append_status_help_line(selection_help, relation_status)
    return PlanStatusTextViewModel(
        text="{selection_state}\n{selection_help}".format(
            selection_state=selection_state,
            selection_help=selection_help,
        )
    )


def build_space_editor_view_model(session_or_context):
    context = as_task_panel_context(session_or_context)
    selected_kind, selected_obj = context.get_selected_plan_target()
    space = selected_obj if selected_kind == "space" else None
    return PlanSpaceEditorViewModel(
        show_editor=bool(space and context.get_current_tool() in ("Select", "Set Space Text")),
        space=space,
    )


def build_region_editor_view_model(session_or_context):
    context = as_task_panel_context(session_or_context)
    selected_kind, selected_obj = context.get_selected_plan_target()
    region = selected_obj if selected_kind == "region" else None
    return PlanRegionEditorViewModel(
        show_editor=bool(region and context.get_current_tool() == "Select"),
        region=region,
    )


def get_window_preset_combo_items(session_or_context, current_style):
    context = as_task_panel_context(session_or_context)
    items = []
    current_style = str(current_style or "").strip()
    if not current_style:
        items.append(("", translate("BIM_PlanEdit", "Custom / Current")))
    for preset in context.get_window_style_preset_options():
        items.append((str(preset or ""), str(preset or "")))
    return tuple(items)


def format_window_editor_note(
    current_style,
    current_width_text,
    current_height_text,
    can_edit_width,
    can_edit_height,
    can_apply_style,
):
    current_style = str(current_style or "").strip()
    style_text = (
        translate("BIM_PlanEdit", "Current style: {style}").format(style=current_style)
        if current_style
        else translate("BIM_PlanEdit", "Current style: Custom")
    )
    width_text = (
        translate("BIM_PlanEdit", "Current width: {width}").format(
            width=current_width_text,
        )
        if current_width_text
        else translate("BIM_PlanEdit", "Current width: unresolved")
    )
    height_text = (
        translate("BIM_PlanEdit", "Current height: {height}").format(
            height=current_height_text,
        )
        if current_height_text
        else translate("BIM_PlanEdit", "Current height: unresolved")
    )
    if can_edit_width and can_edit_height and can_apply_style:
        hint_text = translate(
            "BIM_PlanEdit",
            "Change the width or height directly or apply a built-in preset while keeping the hosted position.",
        )
    elif can_edit_width and can_apply_style:
        hint_text = translate(
            "BIM_PlanEdit",
            "Change the width directly or apply a built-in preset while keeping the hosted position.",
        )
    elif can_edit_height and can_apply_style:
        hint_text = translate(
            "BIM_PlanEdit",
            "Change the height directly or apply a built-in preset while keeping the hosted position.",
        )
    elif can_edit_width and can_edit_height:
        hint_text = translate(
            "BIM_PlanEdit",
            "Change the width or height directly while keeping the hosted position.",
        )
    elif can_edit_width:
        hint_text = translate(
            "BIM_PlanEdit",
            "Change the width directly while keeping the hosted position.",
        )
    elif can_edit_height:
        hint_text = translate(
            "BIM_PlanEdit",
            "Change the height directly while keeping the hosted position.",
        )
    elif can_apply_style:
        hint_text = translate(
            "BIM_PlanEdit",
            "Apply a built-in preset while keeping the hosted position, width, height, frame depth, and frame offset.",
        )
    else:
        hint_text = translate(
            "BIM_PlanEdit",
            "Window editing is unavailable for the current selection.",
        )
    return "{}\n{}\n{}\n{}".format(style_text, width_text, height_text, hint_text)


def get_window_editor_target(session_or_context):
    context = as_task_panel_context(session_or_context)
    selected_kind, selected_obj = context.get_selected_plan_target()
    if selected_kind != "opening" or selected_obj is None or context.get_current_tool() != "Select":
        return None
    if (
        context.can_edit_window_width(selected_obj)
        or context.can_edit_window_height(selected_obj)
        or context.can_apply_window_style_preset(selected_obj)
    ):
        return selected_obj
    return None


def build_window_editor_view_model(session_or_context):
    context = as_task_panel_context(session_or_context)
    window = get_window_editor_target(context)
    if window is None:
        return PlanWindowEditorViewModel()

    can_edit_width = context.can_edit_window_width(window)
    can_edit_height = context.can_edit_window_height(window)
    can_apply_style = context.can_apply_window_style_preset(window)
    current_style = context.get_selected_window_style_preset()
    current_width_text = context.get_selected_window_width_text()
    current_height_text = context.get_selected_window_height_text()
    combo_items = get_window_preset_combo_items(context, current_style)
    return PlanWindowEditorViewModel(
        show_editor=True,
        window=window,
        state_key=(
            get_editor_object_key(window),
            combo_items,
            current_style,
            current_width_text,
            current_height_text,
            can_edit_width,
            can_edit_height,
            can_apply_style,
        ),
        combo_items=combo_items,
        current_style=current_style,
        current_width_text=current_width_text,
        current_height_text=current_height_text,
        note_text=format_window_editor_note(
            current_style,
            current_width_text,
            current_height_text,
            can_edit_width,
            can_edit_height,
            can_apply_style,
        ),
        can_edit_width=can_edit_width,
        can_edit_height=can_edit_height,
        can_apply_style=can_apply_style,
    )
