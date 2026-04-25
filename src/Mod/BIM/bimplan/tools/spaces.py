# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space helpers for BIM Plan Edit."""

import FreeCAD

from bimplan.selection import targets as plan_targets
from bimplan.tools import space_boundaries as plan_space_boundaries
from bimplan.tools import space_editing as plan_space_editing
from bimplan.tools import space_geometry as plan_space_geometry
from bimplan.tools import space_interaction as plan_space_interaction
from bimplan.tools import space_regions as plan_space_regions


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

    space_boundary_key = staticmethod(plan_space_boundaries.space_boundary_key)
    format_space_region_candidate_area = staticmethod(
        plan_space_geometry.format_space_region_candidate_area
    )
    format_space_preflight_text = staticmethod(plan_space_boundaries.format_space_preflight_text)

    def get_space_reference_point(self, *args, **kwargs):
        return plan_space_boundaries.get_space_reference_point(self.session, *args, **kwargs)

    def get_space_boundary_reference_point(self, *args, **kwargs):
        return plan_space_boundaries.get_space_boundary_reference_point(
            self.session, *args, **kwargs
        )

    def get_space_boundary_entries(self, *args, **kwargs):
        return plan_space_boundaries.get_space_boundary_entries(self.session, *args, **kwargs)

    def get_selected_space_boundary_links(self, *args, **kwargs):
        return plan_space_boundaries.get_selected_space_boundary_links(
            self.session, *args, **kwargs
        )

    def resolve_space_region_seed_targets(self, *args, **kwargs):
        return plan_space_boundaries.resolve_space_region_seed_targets(
            self.session, *args, **kwargs
        )

    def resolve_selected_space_region_seed(self, *args, **kwargs):
        return plan_space_boundaries.resolve_selected_space_region_seed(
            self.session, *args, **kwargs
        )

    def build_space_creation_request(self, *args, **kwargs):
        return plan_space_boundaries.build_space_creation_request(self.session, *args, **kwargs)

    def build_space_region_candidate_report(self, *args, **kwargs):
        return plan_space_regions.build_space_region_candidate_report(self.session, *args, **kwargs)

    def get_space_region_pick_candidates(self, *args, **kwargs):
        return plan_space_regions.get_space_region_pick_candidates(self.session, *args, **kwargs)

    def has_space_region_pick_candidates(self, *args, **kwargs):
        return plan_space_regions.has_space_region_pick_candidates(self.session, *args, **kwargs)

    def get_hovered_space_region_candidate(self, *args, **kwargs):
        return plan_space_regions.get_hovered_space_region_candidate(self.session, *args, **kwargs)

    def build_space_preflight_report(self, *args, **kwargs):
        return plan_space_boundaries.build_space_preflight_report(self.session, *args, **kwargs)

    def has_active_space_separator_tool(self, *args, **kwargs):
        return plan_space_interaction.has_active_space_separator_tool(self.session, *args, **kwargs)

    def has_active_plan_region_tool(self, *args, **kwargs):
        return plan_space_interaction.has_active_plan_region_tool(self.session, *args, **kwargs)

    def clear_plan_region_preview(self, *args, **kwargs):
        return plan_space_interaction.clear_plan_region_preview(self.session, *args, **kwargs)

    def cancel_plan_region_tool(self, *args, **kwargs):
        return plan_space_interaction.cancel_plan_region_tool(self.session, *args, **kwargs)

    def get_plan_region_close_tolerance(self, *args, **kwargs):
        return plan_space_interaction.get_plan_region_close_tolerance(self.session, *args, **kwargs)

    def get_plan_region_parent_space(self, *args, **kwargs):
        return plan_space_interaction.get_plan_region_parent_space(self.session, *args, **kwargs)

    def get_plan_region_preview_segments(self, *args, **kwargs):
        return plan_space_interaction.get_plan_region_preview_segments(
            self.session, *args, **kwargs
        )

    def update_plan_region_preview(self, *args, **kwargs):
        return plan_space_interaction.update_plan_region_preview(self.session, *args, **kwargs)

    def create_plan_region(self, *args, **kwargs):
        return plan_space_interaction.create_plan_region(self.session, *args, **kwargs)

    def finalize_plan_region(self, *args, **kwargs):
        return plan_space_interaction.finalize_plan_region(self.session, *args, **kwargs)

    def handle_plan_region_point(self, *args, **kwargs):
        return plan_space_interaction.handle_plan_region_point(self.session, *args, **kwargs)

    def clear_space_separator_preview(self, *args, **kwargs):
        return plan_space_interaction.clear_space_separator_preview(self.session, *args, **kwargs)

    def cancel_space_separator_tool(self, *args, **kwargs):
        return plan_space_interaction.cancel_space_separator_tool(self.session, *args, **kwargs)

    def update_space_separator_preview(self, *args, **kwargs):
        return plan_space_interaction.update_space_separator_preview(self.session, *args, **kwargs)

    def create_space_separator(self, *args, **kwargs):
        return plan_space_interaction.create_space_separator(self.session, *args, **kwargs)

    def handle_space_separator_point(self, *args, **kwargs):
        return plan_space_interaction.handle_space_separator_point(self.session, *args, **kwargs)

    def pick_space_region_candidate(self, *args, **kwargs):
        return plan_space_regions.pick_space_region_candidate(self.session, *args, **kwargs)

    def start_space_region_pick(self, *args, **kwargs):
        return plan_space_regions.start_space_region_pick(self.session, *args, **kwargs)

    def cancel_space_region_pick(self, *args, **kwargs):
        return plan_space_regions.cancel_space_region_pick(self.session, *args, **kwargs)

    def create_space_from_region_candidate(self, *args, **kwargs):
        return plan_space_regions.create_space_from_region_candidate(self.session, *args, **kwargs)

    def activate_space_region_candidate(self, *args, **kwargs):
        return plan_space_regions.activate_space_region_candidate(self.session, *args, **kwargs)

    def create_space_from_current_selection(self, *args, **kwargs):
        return plan_space_regions.create_space_from_current_selection(self.session, *args, **kwargs)

    def set_selected_space_label(self, *args, **kwargs):
        return plan_space_editing.set_selected_space_label(self.session, *args, **kwargs)

    def set_selected_space_type(self, *args, **kwargs):
        return plan_space_editing.set_selected_space_type(self.session, *args, **kwargs)

    def set_selected_region_label(self, *args, **kwargs):
        return plan_space_editing.set_selected_region_label(self.session, *args, **kwargs)

    def set_selected_region_scheme(self, *args, **kwargs):
        return plan_space_editing.set_selected_region_scheme(self.session, *args, **kwargs)

    def set_selected_region_type(self, *args, **kwargs):
        return plan_space_editing.set_selected_region_type(self.session, *args, **kwargs)

    def set_selected_region_parent_space(self, *args, **kwargs):
        return plan_space_editing.set_selected_region_parent_space(self.session, *args, **kwargs)

    def set_space_boundaries(self, *args, **kwargs):
        return plan_space_editing.set_space_boundaries(self.session, *args, **kwargs)

    def add_boundaries_to_selected_space(self, *args, **kwargs):
        return plan_space_editing.add_boundaries_to_selected_space(self.session, *args, **kwargs)

    def remove_selected_space_boundaries(self, *args, **kwargs):
        return plan_space_editing.remove_selected_space_boundaries(self.session, *args, **kwargs)

    def start_space_text_position_pick(self, *args, **kwargs):
        return plan_space_interaction.start_space_text_position_pick(self.session, *args, **kwargs)

    def finish_space_text_position_pick(self, *args, **kwargs):
        return plan_space_interaction.finish_space_text_position_pick(self.session, *args, **kwargs)

    def cancel_space_text_position_pick(self, *args, **kwargs):
        return plan_space_interaction.cancel_space_text_position_pick(self.session, *args, **kwargs)

    def refresh_selected_space_visuals(self, *args, **kwargs):
        return plan_space_editing.refresh_selected_space_visuals(self.session, *args, **kwargs)

    def refresh_selected_region_visuals(self, *args, **kwargs):
        return plan_space_editing.refresh_selected_region_visuals(self.session, *args, **kwargs)

    def restore_selected_semantic_target(self, *args, **kwargs):
        return plan_space_editing.restore_selected_semantic_target(self.session, *args, **kwargs)

    def queue_restore_selected_semantic_target(self, *args, **kwargs):
        return plan_space_editing.queue_restore_selected_semantic_target(
            self.session, *args, **kwargs
        )

    def restore_selected_region(self, *args, **kwargs):
        return plan_space_editing.restore_selected_region(self.session, *args, **kwargs)

    def queue_restore_selected_region(self, *args, **kwargs):
        return plan_space_editing.queue_restore_selected_region(self.session, *args, **kwargs)

    def restore_selected_space(self, *args, **kwargs):
        return plan_space_editing.restore_selected_space(self.session, *args, **kwargs)

    def queue_restore_selected_space(self, *args, **kwargs):
        return plan_space_editing.queue_restore_selected_space(self.session, *args, **kwargs)

    def is_plan_space_object(self, *args, **kwargs):
        return plan_targets.is_plan_space_object(self.session, *args, **kwargs)
