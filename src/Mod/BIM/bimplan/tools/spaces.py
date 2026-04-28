# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space helpers for BIM Plan Edit."""

import FreeCAD

from bimplan.runtime import tools as plan_runtime_tools
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


def resolve_space_region_seed_targets(session, *args, **kwargs):
    return plan_space_boundaries.resolve_space_region_seed_targets(session, *args, **kwargs)


def build_space_creation_request(session, *args, **kwargs):
    return plan_space_boundaries.build_space_creation_request(session, *args, **kwargs)


def should_run_space_preflight_for_targets(*args, **kwargs):
    return plan_space_boundaries.should_run_space_preflight_for_targets(*args, **kwargs)


def start_space_region_pick(session, *args, **kwargs):
    return plan_space_regions.start_space_region_pick(session, *args, **kwargs)


def start_space_region_reassignment(session, *args, **kwargs):
    return plan_space_regions.start_space_region_reassignment(session, *args, **kwargs)


def create_space_from_current_selection(session, *args, **kwargs):
    return plan_space_regions.create_space_from_current_selection(session, *args, **kwargs)


def prepare_plan_region_tool_state(session, *args, **kwargs):
    return plan_space_interaction.prepare_plan_region_tool_state(session, *args, **kwargs)


def prepare_space_separator_tool_state(session, *args, **kwargs):
    return plan_space_interaction.prepare_space_separator_tool_state(session, *args, **kwargs)


def reset_space_region_pick_state(session, *args, **kwargs):
    return plan_space_regions.reset_space_region_pick_state(session, *args, **kwargs)


def reset_space_text_pick_state(session, *args, **kwargs):
    return plan_space_interaction.reset_space_text_pick_state(session, *args, **kwargs)


class RegionTool(plan_runtime_tools.PlanToolHandler):
    """Keyboard behavior for active plan-region drawing."""

    tool_id = plan_runtime_tools.PlanTool.REGION

    def on_key(self, key, event_callback, coin):
        if key in (coin.SoKeyboardEvent.RETURN, coin.SoKeyboardEvent.ENTER):
            if self.session.spaces.finalize_plan_region():
                _set_key_event_handled(event_callback)
            return True
        if key == coin.SoKeyboardEvent.ESCAPE:
            self.session.spaces.cancel_plan_region_tool()
            return True
        return False


def _set_key_event_handled(event_callback):
    setter = getattr(event_callback, "setHandled", None)
    if callable(setter):
        setter()


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

    def start_space_region_reassignment(self, *args, **kwargs):
        return plan_space_regions.start_space_region_reassignment(self.session, *args, **kwargs)

    def cancel_space_region_pick(self, *args, **kwargs):
        return plan_space_regions.cancel_space_region_pick(self.session, *args, **kwargs)

    def create_space_from_region_candidate(self, *args, **kwargs):
        return plan_space_regions.create_space_from_region_candidate(self.session, *args, **kwargs)

    def reassign_space_from_region_candidate(self, *args, **kwargs):
        return plan_space_regions.reassign_space_from_region_candidate(
            self.session,
            *args,
            **kwargs,
        )

    def space_has_valid_geometry(self, *args, **kwargs):
        return plan_space_regions.space_has_valid_geometry(self.session, *args, **kwargs)

    def report_space_creation_failure(self, *args, **kwargs):
        return plan_space_regions.report_space_creation_failure(*args, **kwargs)

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

    def refresh_target_document_visual_change(self, kind, target_obj, obj, prop):
        from bimplan import document_visuals as plan_document_visuals

        if target_obj is None:
            return False
        property_map = {
            "region": plan_document_visuals.REGION_VISUAL_PROPERTIES,
            "space": plan_document_visuals.SPACE_VISUAL_PROPERTIES,
        }
        if kind not in property_map or obj != target_obj or prop not in property_map[kind]:
            return False
        plan_document_visuals.refresh_plan_object_footprint_display(self.session, target_obj)
        return True

    def refresh_plan_target_footprint(self, kind, target_obj):
        from bimplan import document_visuals as plan_document_visuals

        if kind not in ("region", "space") or target_obj is None:
            return False
        plan_document_visuals.refresh_plan_object_footprint_display(self.session, target_obj)
        return True

    def handle_document_visual_change(self, obj, prop):
        from bimplan import document_visuals as plan_document_visuals

        selected_region = self.session.selection.state.get_selected_plan_target_object("region")
        if self.refresh_target_document_visual_change("region", selected_region, obj, prop):
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_SELECTED_REGION
            )
            self.session.task_panels.refresh_task_panel_status(reason="selection")
            return True
        hovered_region = self.session.hovered_region
        if (
            hovered_region
            and not self.session.selection.state.is_selected_plan_target("region", hovered_region)
            and self.refresh_target_document_visual_change("region", hovered_region, obj, prop)
        ):
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_HOVERED_REGION
            )
            return True
        selected_space = self.session.selection.state.get_selected_plan_target_object("space")
        if self.refresh_target_document_visual_change("space", selected_space, obj, prop):
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE
            )
            self.session.task_panels.refresh_task_panel_status(reason="selection")
            return True
        hovered_space = self.session.hovered_space
        if (
            hovered_space
            and not self.session.selection.state.is_selected_plan_target("space", hovered_space)
            and self.refresh_target_document_visual_change("space", hovered_space, obj, prop)
        ):
            self.session.overlays.queue_plan_overlay_visual_refresh(
                plan_document_visuals.PLAN_VISUAL_HOVERED_SPACE
            )
            return True
        return False

    def handle_deleted_visual_target(self, obj):
        if obj == self.session.hovered_space:
            self.session.hovered_space = None
            self.session.overlays.spaces.clear_hovered_space_overlay()
        if obj == self.session.hovered_region:
            self.session.hovered_region = None
            self.session.overlays.spaces.clear_hovered_region_overlay()
        if self.session.selection.refresh.clear_selected_plan_target_if_matches("region", obj):
            self.refresh_selected_region_visuals()
            self.session.task_panels.refresh_task_panel_status(reason="selection")
            return True
        if self.session.selection.refresh.clear_selected_plan_target_if_matches("space", obj):
            self.refresh_selected_space_visuals()
            self.session.task_panels.refresh_task_panel_status(reason="selection")
            return True
        return False

    def refresh_document_dependent_visuals(self):
        from bimplan import document_visuals as plan_document_visuals

        visuals = []
        selected_region = self.session.selection.state.get_selected_plan_target_object("region")
        if self.refresh_plan_target_footprint("region", selected_region):
            visuals.append(plan_document_visuals.PLAN_VISUAL_SELECTED_REGION)
        hovered_region = self.session.hovered_region
        if (
            hovered_region
            and not self.session.selection.state.is_selected_plan_target("region", hovered_region)
            and self.refresh_plan_target_footprint("region", hovered_region)
        ):
            visuals.append(plan_document_visuals.PLAN_VISUAL_HOVERED_REGION)
        selected_space = self.session.selection.state.get_selected_plan_target_object("space")
        if self.refresh_plan_target_footprint("space", selected_space):
            visuals.append(plan_document_visuals.PLAN_VISUAL_SELECTED_SPACE)
        hovered_space = self.session.hovered_space
        if (
            hovered_space
            and not self.session.selection.state.is_selected_plan_target("space", hovered_space)
            and self.refresh_plan_target_footprint("space", hovered_space)
        ):
            visuals.append(plan_document_visuals.PLAN_VISUAL_HOVERED_SPACE)
        return tuple(visuals)

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
