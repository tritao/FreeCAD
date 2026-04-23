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


def _read_component_or_session(
    session,
    component_name,
    component_method_name,
    *args,
    session_method_name=None,
    default=None,
):
    value = _call_component_method(session, component_name, component_method_name, *args)
    if value is not _MISSING:
        return value
    if session_method_name:
        value = _call_session_method(session, session_method_name, *args)
        if value is not _MISSING:
            return value
    return default


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
        return bool(
            _read_component_or_session(
                self.session,
                "windows",
                "can_place_window",
                session_method_name="can_place_plan_window",
                default=False,
            )
        )

    def has_plan_candidate_joint(self):
        return (
            _read_component_or_session(
                self.session,
                "wall_relations",
                "get_plan_candidate_joint",
                session_method_name="_get_plan_candidate_joint",
            )
            is not None
        )

    def get_provider_point_tool_label(self):
        return _read_component_or_session(
            self.session,
            "providers",
            "get_provider_point_tool_label",
            session_method_name="_get_provider_point_tool_label",
            default="",
        )

    def get_provider_point_tool_prompt(self):
        return _read_component_or_session(
            self.session,
            "providers",
            "get_provider_point_tool_prompt",
            session_method_name="_get_provider_point_tool_prompt",
            default="",
        )

    def get_plan_provider_display_name(self, provider_id):
        return _read_component_or_session(
            self.session,
            "providers",
            "get_plan_provider_display_name",
            provider_id,
            session_method_name="get_plan_provider_display_name",
            default=str(provider_id or "").strip(),
        )

    def get_plan_provider_overlay_category(self, overlay):
        return _read_component_or_session(
            self.session,
            "providers",
            "get_plan_provider_overlay_category",
            overlay,
            session_method_name="get_plan_provider_overlay_category",
            default="architecture",
        )

    def is_plan_provider_overlay_enabled(self, overlay):
        return bool(
            _read_component_or_session(
                self.session,
                "providers",
                "is_plan_provider_overlay_enabled",
                overlay,
                session_method_name="is_plan_provider_overlay_enabled",
                default=True,
            )
        )

    def get_plan_provider_overlay_mode(self):
        return str(
            _read_component_or_session(
                self.session,
                "providers",
                "get_plan_provider_overlay_mode",
                session_method_name="get_plan_provider_overlay_mode",
                default="architecture",
            )
            or "architecture"
        )

    def format_plan_target_selection_state(self, target_kind, target_obj):
        return _read_component_or_session(
            self.session,
            "status_text",
            "format_plan_target_selection_state",
            target_kind,
            target_obj,
            session_method_name="_format_plan_target_selection_state",
            default="",
        )

    def format_provider_selected_object_state(self):
        return _read_component_or_session(
            self.session,
            "status_text",
            "format_provider_selected_object_state",
            session_method_name="_format_provider_selected_object_state",
            default="",
        )

    def get_plan_join_candidate_state(self):
        return _read_component_or_session(
            self.session,
            "wall_relations",
            "get_plan_join_candidate_state",
            session_method_name="_get_plan_join_candidate_state",
            default=(None, None, ""),
        )

    def get_plan_target_display_label(self, obj):
        return _read_component_or_session(
            self.session,
            "status_text",
            "get_plan_target_display_label",
            obj,
            session_method_name="_get_plan_target_display_label",
            default=str(getattr(obj, "Label", "") or getattr(obj, "Name", "") or "").strip(),
        )

    def get_plan_join_type_label(self):
        return _read_component_or_session(
            self.session,
            "wall_relations",
            "get_plan_join_type_label",
            session_method_name="get_plan_join_type_label",
            default="",
        )

    def get_plan_join_mode_action_text(self, target_wall, joint):
        return _read_component_or_session(
            self.session,
            "wall_relations",
            "get_plan_join_mode_action_text",
            target_wall,
            joint,
            session_method_name="_get_plan_join_mode_action_text",
            default="",
        )

    def summarize_plan_targets(self, targets):
        return _read_component_or_session(
            self.session,
            "status_text",
            "summarize_plan_targets",
            targets,
            session_method_name="_summarize_plan_targets",
            default="",
        )

    def get_space_region_candidate_count(self):
        return int(
            _read_component_or_session(
                self.session,
                "spaces",
                "get_space_region_candidate_count",
                default=len(getattr(self.session, "_space_region_candidates", ()) or ()),
            )
            or 0
        )

    def get_hovered_space_region_candidate(self):
        return _read_component_or_session(
            self.session,
            "spaces",
            "get_hovered_space_region_candidate",
            default=getattr(self.session, "_hovered_space_region_candidate", None),
        )

    def format_space_region_candidate_area(self, candidate):
        return _read_component_or_session(
            self.session,
            "spaces",
            "format_space_region_candidate_area",
            candidate,
            session_method_name="_format_space_region_candidate_area",
            default="",
        )

    def get_plan_region_parent_space(self):
        return _read_component_or_session(
            self.session,
            "spaces",
            "get_plan_region_parent_space",
            default=getattr(self.session, "_plan_region_parent_space", None),
        )

    def is_plan_space_object(self, obj):
        return bool(
            _read_component_or_session(
                self.session,
                "spaces",
                "is_plan_space_object",
                obj,
                session_method_name="_is_plan_space_object",
                default=False,
            )
        )

    def format_opening_selection_help(self, obj):
        return _read_component_or_session(
            self.session,
            "status_text",
            "format_opening_selection_help",
            obj,
            session_method_name="_format_opening_selection_help",
            default="",
        )

    def symbol_rotation_snap_enabled(self):
        return bool(self.session._symbol_rotation_snap_enabled())

    def format_symbol_rotation_snap_label(self):
        return self.session._format_symbol_rotation_snap_label()

    def format_provider_target_help(self, obj):
        return _read_component_or_session(
            self.session,
            "status_text",
            "format_provider_target_help",
            obj,
            session_method_name="_format_provider_target_help",
            default="",
        )

    def is_selected_wall_endpoint_editable(self):
        return bool(
            _read_component_or_session(
                self.session,
                "wall_edit",
                "is_selected_wall_endpoint_editable",
                session_method_name="is_selected_wall_endpoint_editable",
                default=False,
            )
        )

    def format_provider_selected_object_help(self):
        return _read_component_or_session(
            self.session,
            "status_text",
            "format_provider_selected_object_help",
            session_method_name="_format_provider_selected_object_help",
            default="",
        )

    def get_plan_selection_summary_text(self):
        return _read_component_or_session(
            self.session,
            "status_text",
            "get_plan_selection_summary_text",
            session_method_name="_get_plan_selection_summary_text",
            default="",
        )

    def get_plan_relation_status_message(self):
        return str(getattr(self.session, "_plan_relation_status_message", "") or "").strip()

    def get_window_style_preset_options(self):
        return tuple(
            _read_component_or_session(
                self.session,
                "windows",
                "get_window_style_preset_options",
                session_method_name="_get_window_style_preset_options",
                default=(),
            )
            or ()
        )

    def can_edit_window_width(self, obj):
        return bool(
            _read_component_or_session(
                self.session,
                "windows",
                "can_edit_window_width",
                obj,
                session_method_name="_can_edit_window_width",
                default=False,
            )
        )

    def can_edit_window_height(self, obj):
        return bool(
            _read_component_or_session(
                self.session,
                "windows",
                "can_edit_window_height",
                obj,
                session_method_name="_can_edit_window_height",
                default=False,
            )
        )

    def can_apply_window_style_preset(self, obj):
        return bool(
            _read_component_or_session(
                self.session,
                "windows",
                "can_apply_window_style_preset",
                obj,
                session_method_name="_can_apply_window_style_preset",
                default=False,
            )
        )

    def get_selected_window_style_preset(self):
        return str(
            _read_component_or_session(
                self.session,
                "windows",
                "get_selected_window_style_preset",
                session_method_name="_get_selected_window_style_preset",
                default="",
            )
            or ""
        )

    def get_selected_window_width_text(self):
        return str(
            _read_component_or_session(
                self.session,
                "windows",
                "get_selected_window_width_text",
                session_method_name="_get_selected_window_width_text",
                default="",
            )
            or ""
        )

    def get_selected_window_height_text(self):
        return str(
            _read_component_or_session(
                self.session,
                "windows",
                "get_selected_window_height_text",
                session_method_name="_get_selected_window_height_text",
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
