# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space helpers for BIM Plan Edit."""

import FreeCAD

from bimplan.selection import targets as plan_targets
from bimplan.tools import space_boundaries as plan_space_boundaries
from bimplan.tools import space_editing as plan_space_editing
from bimplan.tools import space_geometry as plan_space_geometry
from bimplan.tools import space_interaction as plan_space_interaction
from bimplan.tools import space_regions as plan_space_regions

has_active_space_separator_tool = plan_space_interaction.has_active_space_separator_tool
has_active_plan_region_tool = plan_space_interaction.has_active_plan_region_tool
clear_plan_region_preview = plan_space_interaction.clear_plan_region_preview
set_plan_region_tool_state = plan_space_interaction.set_plan_region_tool_state
reset_plan_region_tool_state = plan_space_interaction.reset_plan_region_tool_state
prepare_plan_region_tool_state = plan_space_interaction.prepare_plan_region_tool_state
cancel_plan_region_tool = plan_space_interaction.cancel_plan_region_tool
get_plan_region_close_tolerance = plan_space_interaction.get_plan_region_close_tolerance
get_plan_region_preview_segments = plan_space_interaction.get_plan_region_preview_segments
update_plan_region_preview = plan_space_interaction.update_plan_region_preview
create_plan_region = plan_space_interaction.create_plan_region
finalize_plan_region = plan_space_interaction.finalize_plan_region
handle_plan_region_point = plan_space_interaction.handle_plan_region_point
clear_space_separator_preview = plan_space_interaction.clear_space_separator_preview
set_space_separator_tool_state = plan_space_interaction.set_space_separator_tool_state
reset_space_separator_tool_state = plan_space_interaction.reset_space_separator_tool_state
prepare_space_separator_tool_state = plan_space_interaction.prepare_space_separator_tool_state
cancel_space_separator_tool = plan_space_interaction.cancel_space_separator_tool
update_space_separator_preview = plan_space_interaction.update_space_separator_preview
create_space_separator = plan_space_interaction.create_space_separator
handle_space_separator_point = plan_space_interaction.handle_space_separator_point
set_space_text_pick_state = plan_space_interaction.set_space_text_pick_state
reset_space_text_pick_state = plan_space_interaction.reset_space_text_pick_state
start_space_text_position_pick = plan_space_interaction.start_space_text_position_pick
finish_space_text_position_pick = plan_space_interaction.finish_space_text_position_pick
cancel_space_text_position_pick = plan_space_interaction.cancel_space_text_position_pick
get_space_region_candidate_report = plan_space_regions.get_space_region_candidate_report
report_space_region_candidate_failure = plan_space_regions.report_space_region_candidate_failure
set_space_region_pick_state = plan_space_regions.set_space_region_pick_state
reset_space_region_pick_state = plan_space_regions.reset_space_region_pick_state
get_space_region_candidate_polylines = plan_space_regions.get_space_region_candidate_polylines
get_space_region_candidate_segments = plan_space_regions.get_space_region_candidate_segments
pick_space_region_candidate = plan_space_regions.pick_space_region_candidate
set_hovered_space_region_candidate = plan_space_regions.set_hovered_space_region_candidate
create_space_region_base_object = plan_space_regions.create_space_region_base_object
begin_space_region_pick = plan_space_regions.begin_space_region_pick
cancel_space_region_pick = plan_space_regions.cancel_space_region_pick
create_space_from_region_candidate = plan_space_regions.create_space_from_region_candidate
activate_space_region_candidate = plan_space_regions.activate_space_region_candidate
create_space_from_current_selection = plan_space_regions.create_space_from_current_selection
space_has_valid_geometry = plan_space_regions.space_has_valid_geometry
report_space_creation_failure = plan_space_regions.report_space_creation_failure
get_space_reference_point = plan_space_boundaries.get_space_reference_point
get_space_boundary_reference_point = plan_space_boundaries.get_space_boundary_reference_point
get_space_boundary_entries = plan_space_boundaries.get_space_boundary_entries
space_boundary_key = plan_space_boundaries.space_boundary_key
get_selected_space_boundary_links = plan_space_boundaries.get_selected_space_boundary_links
get_space_region_seed_targets = plan_space_boundaries.get_space_region_seed_targets
get_selected_space_region_seed = plan_space_boundaries.get_selected_space_region_seed
get_space_creation_request = plan_space_boundaries.get_space_creation_request
should_run_space_preflight_for_targets = (
    plan_space_boundaries.should_run_space_preflight_for_targets
)
get_space_preflight_report = plan_space_boundaries.get_space_preflight_report
format_space_preflight_text = plan_space_boundaries.format_space_preflight_text
set_selected_space_label = plan_space_editing.set_selected_space_label
set_selected_space_type = plan_space_editing.set_selected_space_type
set_selected_region_label = plan_space_editing.set_selected_region_label
set_selected_region_scheme = plan_space_editing.set_selected_region_scheme
set_selected_region_type = plan_space_editing.set_selected_region_type
set_selected_region_parent_space = plan_space_editing.set_selected_region_parent_space
set_space_boundaries = plan_space_editing.set_space_boundaries
add_boundaries_to_selected_space = plan_space_editing.add_boundaries_to_selected_space
remove_selected_space_boundaries = plan_space_editing.remove_selected_space_boundaries
refresh_selected_space_visuals = plan_space_editing.refresh_selected_space_visuals
refresh_selected_region_visuals = plan_space_editing.refresh_selected_region_visuals
restore_selected_semantic_target = plan_space_editing.restore_selected_semantic_target
queue_restore_selected_semantic_target = plan_space_editing.queue_restore_selected_semantic_target
restore_selected_region = plan_space_editing.restore_selected_region
queue_restore_selected_region = plan_space_editing.queue_restore_selected_region
restore_selected_space = plan_space_editing.restore_selected_space
queue_restore_selected_space = plan_space_editing.queue_restore_selected_space
format_space_region_candidate_area = plan_space_geometry.format_space_region_candidate_area
copy_shape_without_element_map = plan_space_geometry.copy_shape_without_element_map
get_existing_space_region_filter_spaces = (
    plan_space_geometry.get_existing_space_region_filter_spaces
)
get_xy_bound_box_iou = plan_space_geometry.get_xy_bound_box_iou
is_space_region_candidate_claimed = plan_space_geometry.is_space_region_candidate_claimed
filter_claimed_space_region_candidates = plan_space_geometry.filter_claimed_space_region_candidates


class _SessionAPI:
    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session


class PlanSpacesAPI(_SessionAPI):
    """Owned session surface for Plan Edit space and region behavior."""

    __slots__ = ()

    copy_shape_without_element_map = staticmethod(copy_shape_without_element_map)
    space_boundary_key = staticmethod(space_boundary_key)
    get_xy_bound_box_iou = staticmethod(get_xy_bound_box_iou)
    report_space_region_candidate_failure = staticmethod(report_space_region_candidate_failure)
    format_space_region_candidate_area = staticmethod(format_space_region_candidate_area)
    format_space_preflight_text = staticmethod(format_space_preflight_text)
    report_space_creation_failure = staticmethod(report_space_creation_failure)

    def get_space_reference_point(self, *args, **kwargs):
        return get_space_reference_point(self.session, *args, **kwargs)

    def get_space_boundary_reference_point(self, *args, **kwargs):
        return get_space_boundary_reference_point(self.session, *args, **kwargs)

    def get_space_boundary_entries(self, *args, **kwargs):
        return get_space_boundary_entries(self.session, *args, **kwargs)

    def get_selected_space_boundary_links(self, *args, **kwargs):
        return get_selected_space_boundary_links(self.session, *args, **kwargs)

    def get_space_region_seed_targets(self, *args, **kwargs):
        return get_space_region_seed_targets(self.session, *args, **kwargs)

    def get_selected_space_region_seed(self, *args, **kwargs):
        return get_selected_space_region_seed(self.session, *args, **kwargs)

    def get_space_creation_request(self, *args, **kwargs):
        return get_space_creation_request(self.session, *args, **kwargs)

    def get_existing_space_region_filter_spaces(self, *args, **kwargs):
        return get_existing_space_region_filter_spaces(self.session, *args, **kwargs)

    def is_space_region_candidate_claimed(self, *args, **kwargs):
        return is_space_region_candidate_claimed(self.session, *args, **kwargs)

    def filter_claimed_space_region_candidates(self, *args, **kwargs):
        return filter_claimed_space_region_candidates(self.session, *args, **kwargs)

    def get_space_region_candidate_report(self, *args, **kwargs):
        return get_space_region_candidate_report(self.session, *args, **kwargs)

    def get_space_preflight_report(self, *args, **kwargs):
        return get_space_preflight_report(self.session, *args, **kwargs)

    def has_active_space_separator_tool(self, *args, **kwargs):
        return has_active_space_separator_tool(self.session, *args, **kwargs)

    def has_active_plan_region_tool(self, *args, **kwargs):
        return has_active_plan_region_tool(self.session, *args, **kwargs)

    def clear_plan_region_preview(self, *args, **kwargs):
        return clear_plan_region_preview(self.session, *args, **kwargs)

    def cancel_plan_region_tool(self, *args, **kwargs):
        return cancel_plan_region_tool(self.session, *args, **kwargs)

    def get_plan_region_close_tolerance(self, *args, **kwargs):
        return get_plan_region_close_tolerance(self.session, *args, **kwargs)

    def get_plan_region_preview_segments(self, *args, **kwargs):
        return get_plan_region_preview_segments(self.session, *args, **kwargs)

    def update_plan_region_preview(self, *args, **kwargs):
        return update_plan_region_preview(self.session, *args, **kwargs)

    def create_plan_region(self, *args, **kwargs):
        return create_plan_region(self.session, *args, **kwargs)

    def finalize_plan_region(self, *args, **kwargs):
        return finalize_plan_region(self.session, *args, **kwargs)

    def handle_plan_region_point(self, *args, **kwargs):
        return handle_plan_region_point(self.session, *args, **kwargs)

    def clear_space_separator_preview(self, *args, **kwargs):
        return clear_space_separator_preview(self.session, *args, **kwargs)

    def cancel_space_separator_tool(self, *args, **kwargs):
        return cancel_space_separator_tool(self.session, *args, **kwargs)

    def update_space_separator_preview(self, *args, **kwargs):
        return update_space_separator_preview(self.session, *args, **kwargs)

    def create_space_separator(self, *args, **kwargs):
        return create_space_separator(self.session, *args, **kwargs)

    def handle_space_separator_point(self, *args, **kwargs):
        return handle_space_separator_point(self.session, *args, **kwargs)

    def get_space_region_candidate_polylines(self, *args, **kwargs):
        return get_space_region_candidate_polylines(self.session, *args, **kwargs)

    def get_space_region_candidate_segments(self, *args, **kwargs):
        return get_space_region_candidate_segments(self.session, *args, **kwargs)

    def pick_space_region_candidate(self, *args, **kwargs):
        return pick_space_region_candidate(self.session, *args, **kwargs)

    def create_space_region_base_object(self, *args, **kwargs):
        return create_space_region_base_object(self.session, *args, **kwargs)

    def begin_space_region_pick(self, *args, **kwargs):
        return begin_space_region_pick(self.session, *args, **kwargs)

    def cancel_space_region_pick(self, *args, **kwargs):
        return cancel_space_region_pick(self.session, *args, **kwargs)

    def create_space_from_region_candidate(self, *args, **kwargs):
        return create_space_from_region_candidate(self.session, *args, **kwargs)

    def activate_space_region_candidate(self, *args, **kwargs):
        return activate_space_region_candidate(self.session, *args, **kwargs)

    def create_space_from_current_selection(self, *args, **kwargs):
        return create_space_from_current_selection(self.session, *args, **kwargs)

    def space_has_valid_geometry(self, *args, **kwargs):
        return space_has_valid_geometry(self.session, *args, **kwargs)

    def set_selected_space_label(self, *args, **kwargs):
        return set_selected_space_label(self.session, *args, **kwargs)

    def set_selected_space_type(self, *args, **kwargs):
        return set_selected_space_type(self.session, *args, **kwargs)

    def set_selected_region_label(self, *args, **kwargs):
        return set_selected_region_label(self.session, *args, **kwargs)

    def set_selected_region_scheme(self, *args, **kwargs):
        return set_selected_region_scheme(self.session, *args, **kwargs)

    def set_selected_region_type(self, *args, **kwargs):
        return set_selected_region_type(self.session, *args, **kwargs)

    def set_selected_region_parent_space(self, *args, **kwargs):
        return set_selected_region_parent_space(self.session, *args, **kwargs)

    def set_space_boundaries(self, *args, **kwargs):
        return set_space_boundaries(self.session, *args, **kwargs)

    def add_boundaries_to_selected_space(self, *args, **kwargs):
        return add_boundaries_to_selected_space(self.session, *args, **kwargs)

    def remove_selected_space_boundaries(self, *args, **kwargs):
        return remove_selected_space_boundaries(self.session, *args, **kwargs)

    def start_space_text_position_pick(self, *args, **kwargs):
        return start_space_text_position_pick(self.session, *args, **kwargs)

    def finish_space_text_position_pick(self, *args, **kwargs):
        return finish_space_text_position_pick(self.session, *args, **kwargs)

    def cancel_space_text_position_pick(self, *args, **kwargs):
        return cancel_space_text_position_pick(self.session, *args, **kwargs)

    def refresh_selected_space_visuals(self, *args, **kwargs):
        return refresh_selected_space_visuals(self.session, *args, **kwargs)

    def refresh_selected_region_visuals(self, *args, **kwargs):
        return refresh_selected_region_visuals(self.session, *args, **kwargs)

    def restore_selected_semantic_target(self, *args, **kwargs):
        return restore_selected_semantic_target(self.session, *args, **kwargs)

    def queue_restore_selected_semantic_target(self, *args, **kwargs):
        return queue_restore_selected_semantic_target(self.session, *args, **kwargs)

    def restore_selected_region(self, *args, **kwargs):
        return restore_selected_region(self.session, *args, **kwargs)

    def queue_restore_selected_region(self, *args, **kwargs):
        return queue_restore_selected_region(self.session, *args, **kwargs)

    def restore_selected_space(self, *args, **kwargs):
        return restore_selected_space(self.session, *args, **kwargs)

    def queue_restore_selected_space(self, *args, **kwargs):
        return queue_restore_selected_space(self.session, *args, **kwargs)

    def is_plan_space_object(self, *args, **kwargs):
        return plan_targets.is_plan_space_object(self.session, *args, **kwargs)

    def get_space_region_candidate_count(self):
        state = getattr(self.session, "task_panel_state", None)
        if state is not None:
            return len(getattr(state, "space_region_candidates", ()) or ())
        return len(getattr(self.session, "_space_region_candidates", ()) or ())

    def get_hovered_space_region_candidate(self):
        state = getattr(self.session, "task_panel_state", None)
        if state is not None:
            return getattr(state, "hovered_space_region_candidate", None)
        return getattr(self.session, "_hovered_space_region_candidate", None)

    def get_plan_region_parent_space(self):
        state = getattr(self.session, "task_panel_state", None)
        if state is not None:
            return getattr(state, "plan_region_parent_space", None)
        return getattr(self.session, "_plan_region_parent_space", None)

    def set_hovered_space_region_candidate(self, candidate):
        return plan_space_regions.set_hovered_space_region_candidate(self.session, candidate)
