# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2026 FreeCAD Project Association                        *
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""Session-owned composition APIs for Plan Edit feature domains."""

from functools import wraps

from bimplan import selection as plan_selection
from bimplan import spaces as plan_spaces
from bimplan import target_kinds as plan_target_kinds
from bimplan import visual_keys as plan_visual_keys


def _bind_session_call(func):
    @wraps(func)
    def method(self, *args, **kwargs):
        return func(self.session, *args, **kwargs)

    return method


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class PlanSelectionAPI(_SessionAPI):
    """Owned session surface for Plan Edit selection behavior."""

    __slots__ = ()

    get_selected_target_for_kind = _bind_session_call(plan_selection.get_selected_target_for_kind)
    set_selected_target_for_kind = _bind_session_call(plan_selection.set_selected_target_for_kind)
    get_selected_plan_target_object = _bind_session_call(
        plan_selection.get_selected_plan_target_object
    )
    is_selected_plan_target = _bind_session_call(plan_selection.is_selected_plan_target)
    clear_selected_plan_target_if_matches = _bind_session_call(
        plan_selection.clear_selected_plan_target_if_matches
    )
    selected_plan_target_changed = _bind_session_call(plan_selection.selected_plan_target_changed)
    set_pending_selected_plan_target = _bind_session_call(
        plan_selection.set_pending_selected_plan_target
    )
    consume_pending_selected_plan_target = _bind_session_call(
        plan_selection.consume_pending_selected_plan_target
    )
    get_selected_plan_target = _bind_session_call(plan_selection.get_selected_plan_target)
    get_first_plan_target_from_selection = _bind_session_call(
        plan_selection.get_first_plan_target_from_selection
    )
    is_valid_plan_target = _bind_session_call(plan_selection.is_valid_plan_target)
    normalize_plan_target_list = _bind_session_call(plan_selection.normalize_plan_target_list)
    normalize_plan_targets_from_selection = _bind_session_call(
        plan_selection.normalize_plan_targets_from_selection
    )
    set_secondary_selected_plan_targets = _bind_session_call(
        plan_selection.set_secondary_selected_plan_targets
    )
    sync_secondary_selected_plan_targets_from_selection = _bind_session_call(
        plan_selection.sync_secondary_selected_plan_targets_from_selection
    )
    sync_secondary_selected_plan_targets_from_gui_selection = _bind_session_call(
        plan_selection.sync_secondary_selected_plan_targets_from_gui_selection
    )
    get_secondary_selected_plan_targets = _bind_session_call(
        plan_selection.get_secondary_selected_plan_targets
    )
    get_selected_plan_targets = _bind_session_call(plan_selection.get_selected_plan_targets)
    set_selected_plan_target = _bind_session_call(plan_selection.set_selected_plan_target)
    schedule_selected_wall_reset = _bind_session_call(plan_selection.schedule_selected_wall_reset)
    reset_selected_wall_after_change = _bind_session_call(
        plan_selection.reset_selected_wall_after_change
    )
    suspend_selected_wall_state = _bind_session_call(plan_selection.suspend_selected_wall_state)
    sync_primary_selected_plan_target_visuals = _bind_session_call(
        plan_selection.sync_primary_selected_plan_target_visuals
    )
    refresh_selected_plan_target = _bind_session_call(plan_selection.refresh_selected_plan_target)
    refresh_primary_selected_plan_target = _bind_session_call(
        plan_selection.refresh_primary_selected_plan_target
    )
    set_hovered_wall = _bind_session_call(plan_selection.set_hovered_wall)
    set_hovered_opening = _bind_session_call(plan_selection.set_hovered_opening)
    set_hovered_symbol = _bind_session_call(plan_selection.set_hovered_symbol)
    set_hovered_provider = _bind_session_call(plan_selection.set_hovered_provider)
    set_hovered_space = _bind_session_call(plan_selection.set_hovered_space)
    set_hovered_region = _bind_session_call(plan_selection.set_hovered_region)
    queue_restore_selected_plan_target = _bind_session_call(
        plan_selection.queue_restore_selected_plan_target
    )
    select_plan_target_for_plan_edit = _bind_session_call(
        plan_selection.select_plan_target_for_plan_edit
    )
    select_opening_for_plan_edit = _bind_session_call(plan_selection.select_opening_for_plan_edit)
    select_symbol_for_plan_edit = _bind_session_call(plan_selection.select_symbol_for_plan_edit)
    select_region_for_plan_edit = _bind_session_call(plan_selection.select_region_for_plan_edit)
    select_space_for_plan_edit = _bind_session_call(plan_selection.select_space_for_plan_edit)
    select_wall_for_plan_edit = _bind_session_call(plan_selection.select_wall_for_plan_edit)
    activate_plan_target = _bind_session_call(plan_selection.activate_plan_target)
    activate_semantic_plan_target = _bind_session_call(plan_selection.activate_semantic_plan_target)
    activate_opening_target = _bind_session_call(plan_selection.activate_opening_target)
    activate_symbol_target = _bind_session_call(plan_selection.activate_symbol_target)
    activate_region_target = _bind_session_call(plan_selection.activate_region_target)
    activate_space_target = _bind_session_call(plan_selection.activate_space_target)
    activate_wall_target = _bind_session_call(plan_selection.activate_wall_target)
    clear_plan_selection_state = _bind_session_call(plan_selection.clear_plan_selection_state)

    get_plan_target_object_from_state = staticmethod(
        plan_selection.get_plan_target_object_from_state
    )
    get_plan_target_state_key = staticmethod(plan_selection.get_plan_target_state_key)

    def get_selected_plan_target_state(self):
        return plan_selection.get_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
        )

    def set_selected_plan_target_state(self, kind=None, obj=None):
        return plan_selection.set_selected_plan_target_state(
            self.session,
            plan_target_kinds.PRIMARY_PLAN_TARGET_KINDS,
            kind=kind,
            obj=obj,
        )


class PlanSpacesAPI(_SessionAPI):
    """Owned session surface for Plan Edit space and region behavior."""

    __slots__ = ()

    get_space_reference_point = _bind_session_call(plan_spaces.get_space_reference_point)
    get_space_boundary_reference_point = _bind_session_call(
        plan_spaces.get_space_boundary_reference_point
    )
    get_space_boundary_entries = _bind_session_call(plan_spaces.get_space_boundary_entries)
    get_selected_space_boundary_links = _bind_session_call(
        plan_spaces.get_selected_space_boundary_links
    )
    get_space_region_seed_targets = _bind_session_call(plan_spaces.get_space_region_seed_targets)
    get_selected_space_region_seed = _bind_session_call(plan_spaces.get_selected_space_region_seed)
    get_space_creation_request = _bind_session_call(plan_spaces.get_space_creation_request)
    get_existing_space_region_filter_spaces = _bind_session_call(
        plan_spaces.get_existing_space_region_filter_spaces
    )
    is_space_region_candidate_claimed = _bind_session_call(
        plan_spaces.is_space_region_candidate_claimed
    )
    filter_claimed_space_region_candidates = _bind_session_call(
        plan_spaces.filter_claimed_space_region_candidates
    )
    get_space_region_candidate_report = _bind_session_call(
        plan_spaces.get_space_region_candidate_report
    )
    get_space_preflight_report = _bind_session_call(plan_spaces.get_space_preflight_report)
    has_active_space_separator_tool = _bind_session_call(
        plan_spaces.has_active_space_separator_tool
    )
    has_active_plan_region_tool = _bind_session_call(plan_spaces.has_active_plan_region_tool)
    clear_plan_region_preview = _bind_session_call(plan_spaces.clear_plan_region_preview)
    cancel_plan_region_tool = _bind_session_call(plan_spaces.cancel_plan_region_tool)
    get_plan_region_close_tolerance = _bind_session_call(
        plan_spaces.get_plan_region_close_tolerance
    )
    get_plan_region_preview_segments = _bind_session_call(
        plan_spaces.get_plan_region_preview_segments
    )
    update_plan_region_preview = _bind_session_call(plan_spaces.update_plan_region_preview)
    create_plan_region = _bind_session_call(plan_spaces.create_plan_region)
    finalize_plan_region = _bind_session_call(plan_spaces.finalize_plan_region)
    handle_plan_region_point = _bind_session_call(plan_spaces.handle_plan_region_point)
    clear_space_separator_preview = _bind_session_call(plan_spaces.clear_space_separator_preview)
    cancel_space_separator_tool = _bind_session_call(plan_spaces.cancel_space_separator_tool)
    update_space_separator_preview = _bind_session_call(plan_spaces.update_space_separator_preview)
    create_space_separator = _bind_session_call(plan_spaces.create_space_separator)
    handle_space_separator_point = _bind_session_call(plan_spaces.handle_space_separator_point)
    get_space_region_candidate_polylines = _bind_session_call(
        plan_spaces.get_space_region_candidate_polylines
    )
    get_space_region_candidate_segments = _bind_session_call(
        plan_spaces.get_space_region_candidate_segments
    )
    pick_space_region_candidate = _bind_session_call(plan_spaces.pick_space_region_candidate)
    create_space_region_base_object = _bind_session_call(
        plan_spaces.create_space_region_base_object
    )
    begin_space_region_pick = _bind_session_call(plan_spaces.begin_space_region_pick)
    cancel_space_region_pick = _bind_session_call(plan_spaces.cancel_space_region_pick)
    create_space_from_region_candidate = _bind_session_call(
        plan_spaces.create_space_from_region_candidate
    )
    activate_space_region_candidate = _bind_session_call(
        plan_spaces.activate_space_region_candidate
    )
    create_space_from_current_selection = _bind_session_call(
        plan_spaces.create_space_from_current_selection
    )
    space_has_valid_geometry = _bind_session_call(plan_spaces.space_has_valid_geometry)
    set_selected_space_label = _bind_session_call(plan_spaces.set_selected_space_label)
    set_selected_space_type = _bind_session_call(plan_spaces.set_selected_space_type)
    set_selected_region_label = _bind_session_call(plan_spaces.set_selected_region_label)
    set_selected_region_scheme = _bind_session_call(plan_spaces.set_selected_region_scheme)
    set_selected_region_type = _bind_session_call(plan_spaces.set_selected_region_type)
    set_selected_region_parent_space = _bind_session_call(
        plan_spaces.set_selected_region_parent_space
    )
    set_space_boundaries = _bind_session_call(plan_spaces.set_space_boundaries)
    add_boundaries_to_selected_space = _bind_session_call(
        plan_spaces.add_boundaries_to_selected_space
    )
    remove_selected_space_boundaries = _bind_session_call(
        plan_spaces.remove_selected_space_boundaries
    )
    start_space_text_position_pick = _bind_session_call(plan_spaces.start_space_text_position_pick)
    finish_space_text_position_pick = _bind_session_call(
        plan_spaces.finish_space_text_position_pick
    )
    cancel_space_text_position_pick = _bind_session_call(
        plan_spaces.cancel_space_text_position_pick
    )

    copy_shape_without_element_map = staticmethod(plan_spaces.copy_shape_without_element_map)
    space_boundary_key = staticmethod(plan_spaces.space_boundary_key)
    get_xy_bound_box_iou = staticmethod(plan_spaces.get_xy_bound_box_iou)
    report_space_region_candidate_failure = staticmethod(
        plan_spaces.report_space_region_candidate_failure
    )
    format_space_preflight_text = staticmethod(plan_spaces.format_space_preflight_text)
    report_space_creation_failure = staticmethod(plan_spaces.report_space_creation_failure)

    def set_hovered_space_region_candidate(self, candidate):
        return plan_spaces.set_hovered_space_region_candidate(
            self.session,
            candidate,
            plan_visual_keys.PLAN_VISUAL_SPACE_REGION_PICK,
        )
