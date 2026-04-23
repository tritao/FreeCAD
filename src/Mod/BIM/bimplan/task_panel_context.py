# SPDX-License-Identifier: LGPL-2.1-or-later

"""Read-only query surface for Plan Edit task-panel view models."""

from __future__ import annotations

from . import selection_access as plan_selection_access

_MISSING = object()
_TASK_PANEL_CONTEXT_METHODS = (
    "get_current_tool",
    "get_selected_plan_target",
    "get_selected_plan_targets",
)


def _call_component_method(session, component_name, method_name, *args):
    component = getattr(session, component_name, None)
    method = getattr(component, method_name, None)
    if callable(method):
        return method(*args)
    return _MISSING


def _call_session_method(session, method_name, *args):
    method = getattr(session, method_name, None)
    if callable(method):
        return method(*args)
    return _MISSING


class PlanTaskPanelContext:
    """Thin read-only adapter around the live Plan Edit session."""

    def __init__(self, session):
        self.session = session

    def get_current_tool(self):
        return str(self.session.current_tool or "")

    def get_selected_plan_target(self):
        return plan_selection_access.get_selected_plan_target(self.session)

    def get_selected_plan_targets(self):
        return plan_selection_access.get_selected_plan_targets(self.session)

    def is_modal_plan_interaction_active(self):
        return bool(self.session._is_modal_plan_interaction_active())

    def can_place_plan_window(self):
        return bool(self.session.can_place_plan_window())

    def has_plan_candidate_joint(self):
        return self.session._get_plan_candidate_joint() is not None

    def get_provider_point_tool_label(self):
        label = _call_component_method(
            self.session,
            "providers",
            "get_provider_point_tool_label",
        )
        if label is not _MISSING:
            return label
        legacy_label = _call_session_method(self.session, "_get_provider_point_tool_label")
        if legacy_label is not _MISSING:
            return legacy_label
        return ""

    def get_provider_point_tool_prompt(self):
        prompt = _call_component_method(
            self.session,
            "providers",
            "get_provider_point_tool_prompt",
        )
        if prompt is not _MISSING:
            return prompt
        legacy_prompt = _call_session_method(self.session, "_get_provider_point_tool_prompt")
        if legacy_prompt is not _MISSING:
            return legacy_prompt
        return ""

    def get_plan_provider_display_name(self, provider_id):
        display_name = _call_component_method(
            self.session,
            "providers",
            "get_plan_provider_display_name",
            provider_id,
        )
        if display_name is not _MISSING:
            return display_name
        legacy_display_name = _call_session_method(
            self.session,
            "get_plan_provider_display_name",
            provider_id,
        )
        if legacy_display_name is not _MISSING:
            return legacy_display_name
        return str(provider_id or "").strip()

    def get_plan_provider_overlay_category(self, overlay):
        category = _call_component_method(
            self.session,
            "providers",
            "get_plan_provider_overlay_category",
            overlay,
        )
        if category is not _MISSING:
            return category
        legacy_category = _call_session_method(
            self.session,
            "get_plan_provider_overlay_category",
            overlay,
        )
        if legacy_category is not _MISSING:
            return legacy_category
        return "architecture"

    def is_plan_provider_overlay_enabled(self, overlay):
        enabled = _call_component_method(
            self.session,
            "providers",
            "is_plan_provider_overlay_enabled",
            overlay,
        )
        if enabled is not _MISSING:
            return bool(enabled)
        legacy_enabled = _call_session_method(
            self.session,
            "is_plan_provider_overlay_enabled",
            overlay,
        )
        if legacy_enabled is not _MISSING:
            return bool(legacy_enabled)
        return True

    def get_plan_provider_overlay_mode(self):
        overlay_mode = _call_component_method(
            self.session,
            "providers",
            "get_plan_provider_overlay_mode",
        )
        if overlay_mode is _MISSING:
            overlay_mode = _call_session_method(self.session, "get_plan_provider_overlay_mode")
        return str(overlay_mode or "architecture")

    def format_plan_target_selection_state(self, target_kind, target_obj):
        selection_state = _call_component_method(
            self.session,
            "status_text",
            "format_plan_target_selection_state",
            target_kind,
            target_obj,
        )
        if selection_state is not _MISSING:
            return selection_state
        legacy_selection_state = _call_session_method(
            self.session,
            "_format_plan_target_selection_state",
            target_kind,
            target_obj,
        )
        if legacy_selection_state is not _MISSING:
            return legacy_selection_state
        return ""

    def format_provider_selected_object_state(self):
        provider_state = _call_component_method(
            self.session,
            "status_text",
            "format_provider_selected_object_state",
        )
        if provider_state is not _MISSING:
            return provider_state
        legacy_provider_state = _call_session_method(
            self.session,
            "_format_provider_selected_object_state",
        )
        if legacy_provider_state is not _MISSING:
            return legacy_provider_state
        return ""

    def get_plan_join_candidate_state(self):
        return self.session._get_plan_join_candidate_state()

    def get_plan_target_display_label(self, obj):
        label = _call_component_method(
            self.session,
            "status_text",
            "get_plan_target_display_label",
            obj,
        )
        if label is not _MISSING:
            return label
        legacy_label = _call_session_method(self.session, "_get_plan_target_display_label", obj)
        if legacy_label is not _MISSING:
            return legacy_label
        return str(getattr(obj, "Label", "") or getattr(obj, "Name", "") or "").strip()

    def get_plan_join_type_label(self):
        return self.session.get_plan_join_type_label()

    def get_plan_join_mode_action_text(self, target_wall, joint):
        return self.session._get_plan_join_mode_action_text(target_wall, joint)

    def summarize_plan_targets(self, targets):
        summary = _call_component_method(
            self.session,
            "status_text",
            "summarize_plan_targets",
            targets,
        )
        if summary is not _MISSING:
            return summary
        legacy_summary = _call_session_method(self.session, "_summarize_plan_targets", targets)
        if legacy_summary is not _MISSING:
            return legacy_summary
        return ""

    def get_space_region_candidate_count(self):
        return len(getattr(self.session, "_space_region_candidates", ()) or ())

    def get_hovered_space_region_candidate(self):
        return getattr(self.session, "_hovered_space_region_candidate", None)

    def format_space_region_candidate_area(self, candidate):
        return self.session._format_space_region_candidate_area(candidate)

    def get_plan_region_parent_space(self):
        return getattr(self.session, "_plan_region_parent_space", None)

    def is_plan_space_object(self, obj):
        return bool(self.session._is_plan_space_object(obj))

    def format_opening_selection_help(self, obj):
        help_text = _call_component_method(
            self.session,
            "status_text",
            "format_opening_selection_help",
            obj,
        )
        if help_text is not _MISSING:
            return help_text
        legacy_help_text = _call_session_method(self.session, "_format_opening_selection_help", obj)
        if legacy_help_text is not _MISSING:
            return legacy_help_text
        return ""

    def symbol_rotation_snap_enabled(self):
        return bool(self.session._symbol_rotation_snap_enabled())

    def format_symbol_rotation_snap_label(self):
        return self.session._format_symbol_rotation_snap_label()

    def format_provider_target_help(self, obj):
        help_text = _call_component_method(
            self.session,
            "status_text",
            "format_provider_target_help",
            obj,
        )
        if help_text is not _MISSING:
            return help_text
        legacy_help_text = _call_session_method(self.session, "_format_provider_target_help", obj)
        if legacy_help_text is not _MISSING:
            return legacy_help_text
        return ""

    def is_selected_wall_endpoint_editable(self):
        return bool(self.session.is_selected_wall_endpoint_editable())

    def format_provider_selected_object_help(self):
        help_text = _call_component_method(
            self.session,
            "status_text",
            "format_provider_selected_object_help",
        )
        if help_text is not _MISSING:
            return help_text
        legacy_help_text = _call_session_method(
            self.session,
            "_format_provider_selected_object_help",
        )
        if legacy_help_text is not _MISSING:
            return legacy_help_text
        return ""

    def get_plan_selection_summary_text(self):
        summary = _call_component_method(
            self.session,
            "status_text",
            "get_plan_selection_summary_text",
        )
        if summary is not _MISSING:
            return summary
        legacy_summary = _call_session_method(self.session, "_get_plan_selection_summary_text")
        if legacy_summary is not _MISSING:
            return legacy_summary
        return ""

    def get_plan_relation_status_message(self):
        return str(getattr(self.session, "_plan_relation_status_message", "") or "").strip()

    def get_window_style_preset_options(self):
        return tuple(self.session._get_window_style_preset_options() or ())

    def can_edit_window_width(self, obj):
        return bool(self.session._can_edit_window_width(obj))

    def can_edit_window_height(self, obj):
        return bool(self.session._can_edit_window_height(obj))

    def can_apply_window_style_preset(self, obj):
        return bool(self.session._can_apply_window_style_preset(obj))

    def get_selected_window_style_preset(self):
        return str(self.session._get_selected_window_style_preset() or "")

    def get_selected_window_width_text(self):
        return str(self.session._get_selected_window_width_text() or "")

    def get_selected_window_height_text(self):
        return str(self.session._get_selected_window_height_text() or "")


def as_task_panel_context(session_or_context):
    if isinstance(session_or_context, PlanTaskPanelContext) or all(
        hasattr(session_or_context, method_name) for method_name in _TASK_PANEL_CONTEXT_METHODS
    ):
        return session_or_context
    return PlanTaskPanelContext(session_or_context)
