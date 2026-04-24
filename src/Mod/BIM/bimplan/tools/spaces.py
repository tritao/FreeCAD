# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space helpers for BIM Plan Edit."""

import FreeCAD

from bimplan.selection import targets as plan_targets
from bimplan.tools import space_boundaries as plan_space_boundaries
from bimplan.tools import space_editing as plan_space_editing
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


def format_space_region_candidate_area(candidate):
    area = float((candidate or {}).get("area", 0.0) or 0.0)
    if area <= 0.0:
        return ""
    try:
        quantity = FreeCAD.Units.Quantity(area, "mm^2")
        return quantity.UserString
    except Exception:
        return "{:.3f} m^2".format(area / 1000000.0)


def copy_shape_without_element_map(shape):
    if shape is None:
        return None
    try:
        return shape.copy(noElementMap=True)
    except Exception:
        try:
            return shape.copy()
        except Exception:
            return None


def get_existing_space_region_filter_spaces(session, exclude=None):
    if not session.doc:
        return []
    active_storey_name = getattr(session.active_storey, "Name", None)
    exclude_space = session.visibility.get_plan_semantic_object(exclude) if exclude else None
    exclude_name = getattr(exclude_space, "Name", None)

    spaces = []
    seen = set()
    for obj in session.doc.Objects:
        semantic_obj = session.visibility.get_plan_semantic_object(obj)
        name = getattr(semantic_obj, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        if name == exclude_name or not session.selection.is_plan_space_object(semantic_obj):
            continue
        if active_storey_name is not None:
            storeys = session.visibility.get_object_storeys(semantic_obj)
            if storeys and not any(parent.Name == active_storey_name for parent in storeys):
                continue
        spaces.append(semantic_obj)
    return spaces


def get_xy_bound_box_iou(first_shape, second_shape):
    first_bb = getattr(first_shape, "BoundBox", None)
    second_bb = getattr(second_shape, "BoundBox", None)
    if first_bb is None or second_bb is None:
        return 0.0

    x_overlap = min(float(first_bb.XMax), float(second_bb.XMax)) - max(
        float(first_bb.XMin), float(second_bb.XMin)
    )
    y_overlap = min(float(first_bb.YMax), float(second_bb.YMax)) - max(
        float(first_bb.YMin), float(second_bb.YMin)
    )
    if x_overlap <= 0.000001 or y_overlap <= 0.000001:
        return 0.0

    intersection_area = x_overlap * y_overlap
    first_area = max(
        0.0,
        (float(first_bb.XMax) - float(first_bb.XMin))
        * (float(first_bb.YMax) - float(first_bb.YMin)),
    )
    second_area = max(
        0.0,
        (float(second_bb.XMax) - float(second_bb.XMin))
        * (float(second_bb.YMax) - float(second_bb.YMin)),
    )
    union_area = first_area + second_area - intersection_area
    if union_area <= 0.000001:
        return 0.0
    return intersection_area / union_area


def is_space_region_candidate_claimed(
    session,
    candidate,
    spaces,
    overlap_iou_tolerance=0.9,
):
    if not isinstance(candidate, dict):
        return False
    candidate_face = candidate.get("face")
    sample_point = candidate.get("sample_point")
    if candidate_face is None or sample_point is None:
        return False

    for space in spaces or []:
        footprint_faces = session.overlays.get_space_footprint_faces(space)
        if not footprint_faces:
            continue
        for footprint_face in footprint_faces:
            try:
                test_point = FreeCAD.Vector(
                    sample_point.x,
                    sample_point.y,
                    float(footprint_face.BoundBox.ZMin),
                )
                if not footprint_face.isInside(test_point, 0.001, True):
                    continue
            except Exception:
                continue
            if session.spaces.get_xy_bound_box_iou(candidate_face, footprint_face) >= float(
                overlap_iou_tolerance
            ):
                return True
    return False


def filter_claimed_space_region_candidates(session, candidates, exclude_space=None):
    candidates = list(candidates or [])
    if not candidates:
        return candidates, 0

    spaces = session.spaces.get_existing_space_region_filter_spaces(exclude=exclude_space)
    if not spaces:
        return candidates, 0

    filtered = []
    skipped = 0
    for candidate in candidates:
        if session.spaces.is_space_region_candidate_claimed(candidate, spaces):
            skipped += 1
            continue
        filtered.append(candidate)
    return filtered, skipped


from functools import wraps


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


class PlanSpacesAPI(_SessionAPI):
    """Owned session surface for Plan Edit space and region behavior."""

    __slots__ = ()

    get_space_reference_point = _bind_session_call(get_space_reference_point)
    get_space_boundary_reference_point = _bind_session_call(get_space_boundary_reference_point)
    get_space_boundary_entries = _bind_session_call(get_space_boundary_entries)
    get_selected_space_boundary_links = _bind_session_call(get_selected_space_boundary_links)
    get_space_region_seed_targets = _bind_session_call(get_space_region_seed_targets)
    get_selected_space_region_seed = _bind_session_call(get_selected_space_region_seed)
    get_space_creation_request = _bind_session_call(get_space_creation_request)
    get_existing_space_region_filter_spaces = _bind_session_call(
        get_existing_space_region_filter_spaces
    )
    is_space_region_candidate_claimed = _bind_session_call(is_space_region_candidate_claimed)
    filter_claimed_space_region_candidates = _bind_session_call(
        filter_claimed_space_region_candidates
    )
    get_space_region_candidate_report = _bind_session_call(get_space_region_candidate_report)
    get_space_preflight_report = _bind_session_call(get_space_preflight_report)
    has_active_space_separator_tool = _bind_session_call(has_active_space_separator_tool)
    has_active_plan_region_tool = _bind_session_call(has_active_plan_region_tool)
    clear_plan_region_preview = _bind_session_call(clear_plan_region_preview)
    cancel_plan_region_tool = _bind_session_call(cancel_plan_region_tool)
    get_plan_region_close_tolerance = _bind_session_call(get_plan_region_close_tolerance)
    get_plan_region_preview_segments = _bind_session_call(get_plan_region_preview_segments)
    update_plan_region_preview = _bind_session_call(update_plan_region_preview)
    create_plan_region = _bind_session_call(create_plan_region)
    finalize_plan_region = _bind_session_call(finalize_plan_region)
    handle_plan_region_point = _bind_session_call(handle_plan_region_point)
    clear_space_separator_preview = _bind_session_call(clear_space_separator_preview)
    cancel_space_separator_tool = _bind_session_call(cancel_space_separator_tool)
    update_space_separator_preview = _bind_session_call(update_space_separator_preview)
    create_space_separator = _bind_session_call(create_space_separator)
    handle_space_separator_point = _bind_session_call(handle_space_separator_point)
    get_space_region_candidate_polylines = _bind_session_call(get_space_region_candidate_polylines)
    get_space_region_candidate_segments = _bind_session_call(get_space_region_candidate_segments)
    pick_space_region_candidate = _bind_session_call(pick_space_region_candidate)
    create_space_region_base_object = _bind_session_call(create_space_region_base_object)
    begin_space_region_pick = _bind_session_call(begin_space_region_pick)
    cancel_space_region_pick = _bind_session_call(cancel_space_region_pick)
    create_space_from_region_candidate = _bind_session_call(create_space_from_region_candidate)
    activate_space_region_candidate = _bind_session_call(activate_space_region_candidate)
    create_space_from_current_selection = _bind_session_call(create_space_from_current_selection)
    space_has_valid_geometry = _bind_session_call(space_has_valid_geometry)
    set_selected_space_label = _bind_session_call(set_selected_space_label)
    set_selected_space_type = _bind_session_call(set_selected_space_type)
    set_selected_region_label = _bind_session_call(set_selected_region_label)
    set_selected_region_scheme = _bind_session_call(set_selected_region_scheme)
    set_selected_region_type = _bind_session_call(set_selected_region_type)
    set_selected_region_parent_space = _bind_session_call(set_selected_region_parent_space)
    set_space_boundaries = _bind_session_call(set_space_boundaries)
    add_boundaries_to_selected_space = _bind_session_call(add_boundaries_to_selected_space)
    remove_selected_space_boundaries = _bind_session_call(remove_selected_space_boundaries)
    start_space_text_position_pick = _bind_session_call(start_space_text_position_pick)
    finish_space_text_position_pick = _bind_session_call(finish_space_text_position_pick)
    cancel_space_text_position_pick = _bind_session_call(cancel_space_text_position_pick)
    refresh_selected_space_visuals = _bind_session_call(refresh_selected_space_visuals)
    refresh_selected_region_visuals = _bind_session_call(refresh_selected_region_visuals)
    restore_selected_semantic_target = _bind_session_call(restore_selected_semantic_target)
    queue_restore_selected_semantic_target = _bind_session_call(
        queue_restore_selected_semantic_target
    )
    restore_selected_region = _bind_session_call(restore_selected_region)
    queue_restore_selected_region = _bind_session_call(queue_restore_selected_region)
    restore_selected_space = _bind_session_call(restore_selected_space)
    queue_restore_selected_space = _bind_session_call(queue_restore_selected_space)

    copy_shape_without_element_map = staticmethod(copy_shape_without_element_map)
    space_boundary_key = staticmethod(space_boundary_key)
    get_xy_bound_box_iou = staticmethod(get_xy_bound_box_iou)
    report_space_region_candidate_failure = staticmethod(report_space_region_candidate_failure)
    format_space_region_candidate_area = staticmethod(format_space_region_candidate_area)
    format_space_preflight_text = staticmethod(format_space_preflight_text)
    report_space_creation_failure = staticmethod(report_space_creation_failure)
    is_plan_space_object = _bind_session_call(plan_targets.is_plan_space_object)

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
