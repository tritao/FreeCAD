# SPDX-License-Identifier: LGPL-2.1-or-later

"""Read-only query surface for Plan Edit task-panel view models."""

from __future__ import annotations

from . import selection_access as plan_selection_access

_TASK_PANEL_CONTEXT_METHODS = (
    "get_current_tool",
    "get_selected_plan_target",
    "get_selected_plan_targets",
)


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
        return self.session._get_provider_point_tool_label()

    def get_provider_point_tool_prompt(self):
        return self.session._get_provider_point_tool_prompt()

    def get_plan_provider_display_name(self, provider_id):
        return self.session.get_plan_provider_display_name(provider_id)

    def get_plan_provider_overlay_category(self, overlay):
        return self.session.get_plan_provider_overlay_category(overlay)

    def is_plan_provider_overlay_enabled(self, overlay):
        return bool(self.session.is_plan_provider_overlay_enabled(overlay))

    def get_plan_provider_overlay_mode(self):
        return str(self.session.get_plan_provider_overlay_mode() or "architecture")

    def format_plan_target_selection_state(self, target_kind, target_obj):
        return self.session._format_plan_target_selection_state(target_kind, target_obj)

    def format_provider_selected_object_state(self):
        return self.session._format_provider_selected_object_state()

    def get_plan_join_candidate_state(self):
        return self.session._get_plan_join_candidate_state()

    def get_plan_target_display_label(self, obj):
        return self.session._get_plan_target_display_label(obj)

    def get_plan_join_type_label(self):
        return self.session.get_plan_join_type_label()

    def get_plan_join_mode_action_text(self, target_wall, joint):
        return self.session._get_plan_join_mode_action_text(target_wall, joint)

    def summarize_plan_targets(self, targets):
        return self.session._summarize_plan_targets(targets)

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
        return self.session._format_opening_selection_help(obj)

    def symbol_rotation_snap_enabled(self):
        return bool(self.session._symbol_rotation_snap_enabled())

    def format_symbol_rotation_snap_label(self):
        return self.session._format_symbol_rotation_snap_label()

    def format_provider_target_help(self, obj):
        return self.session._format_provider_target_help(obj)

    def is_selected_wall_endpoint_editable(self):
        return bool(self.session.is_selected_wall_endpoint_editable())

    def format_provider_selected_object_help(self):
        return self.session._format_provider_selected_object_help()

    def get_plan_selection_summary_text(self):
        return self.session._get_plan_selection_summary_text()

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
