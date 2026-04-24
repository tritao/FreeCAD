# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space boundary helpers for BIM Plan Edit."""

from dataclasses import dataclass

import FreeCAD

from bimplan import document_visuals as plan_document_visuals
from bimplan import selection as plan_selection
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.selection import targets as plan_targets
from bimplan.tools import space_boundaries as plan_space_boundaries
from bimplan.tools import space_interaction as plan_space_interaction
from bimplan.tools import space_regions as plan_space_regions

translate = FreeCAD.Qt.translate

_SPACE_SELECTION_NONE = "none"
_SPACE_SELECTION_WALL_BOUNDARIES = "wall_boundaries"
_SPACE_SELECTION_SEEDED_REGION = "seeded_region"
_SPACE_SELECTION_SINGLE_SPACE = "single_space"


@dataclass(frozen=True)
class SpaceSelectionShape:
    targets: tuple = ()
    mode: str = _SPACE_SELECTION_NONE
    region_seed_space: object = None
    wall_targets: tuple = ()

    @property
    def should_run_preflight(self):
        if len(self.targets) <= 1:
            return False
        return self.mode in (
            _SPACE_SELECTION_WALL_BOUNDARIES,
            _SPACE_SELECTION_SEEDED_REGION,
        )


@dataclass(frozen=True)
class SpaceCreationRequest:
    targets: tuple = ()
    mode: str = _SPACE_SELECTION_NONE
    label: object = None
    region_seed_space: object = None
    wall_targets: tuple = ()
    boundaries: tuple = ()

    def to_dict(self):
        return {
            "targets": list(self.targets),
            "label": self.label,
            "region_seed_space": self.region_seed_space,
            "boundaries": list(self.boundaries),
        }


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


def set_selected_space_label(session, label):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    label = str(label or "").strip()
    if not label or label == space.Label:
        return False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Rename Space"))
        space.Label = label
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.task_panels.refresh_task_panel_status()
    return True


def set_selected_space_type(session, space_type):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    space_type = str(space_type or "")
    if not space_type or space_type == getattr(space, "SpaceType", ""):
        return False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Change Space Type"))
        space.SpaceType = space_type
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.task_panels.refresh_task_panel_status()
    return True


def set_selected_region_label(session, label):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    label = str(label or "").strip()
    if not label or label == getattr(region, "Label", ""):
        return False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Rename Region"))
        region.Label = label
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.task_panels.refresh_task_panel_status()
    return True


def set_selected_region_scheme(session, scheme):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    scheme = str(scheme or "").strip()
    if scheme == str(getattr(region, "Scheme", "") or ""):
        return False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Scheme"))
        region.Scheme = scheme
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.task_panels.refresh_task_panel_status()
    return True


def set_selected_region_type(session, region_type):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    region_type = str(region_type or "").strip()
    if region_type == str(getattr(region, "RegionType", "") or ""):
        return False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Type"))
        region.RegionType = region_type
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.task_panels.refresh_task_panel_status()
    return True


def set_selected_region_parent_space(session, space):
    region = plan_selection.get_selected_plan_target_object(session, "region")
    if not session.selection.is_plan_region_object(region):
        return False
    space = session.visibility.get_plan_semantic_object(space) if space else None
    if space is not None and not session.selection.is_plan_space_object(space):
        return False

    current_parent = getattr(region, "ParentSpace", None)
    current_parent = (
        session.visibility.get_plan_semantic_object(current_parent) if current_parent else None
    )
    if current_parent == space:
        return False

    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Change Region Parent Space"))
        region.ParentSpace = space
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.task_panels.refresh_task_panel_status()
    return True


def set_space_boundaries(session, space, boundaries):
    if not session.selection.is_plan_space_object(space):
        return False
    import ArchSpace

    boundaries = ArchSpace.normalizeBoundaryLinks(boundaries)
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Edit Space Boundaries"))
        space.Boundaries = boundaries
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        return False
    session.spaces.refresh_selected_space_visuals()
    session.task_panels.refresh_task_panel_status()
    return True


def add_boundaries_to_selected_space(session):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    existing = session.spaces.get_space_boundary_entries(space)
    additions = session.spaces.get_selected_space_boundary_links(fallback_space=space)
    if not additions:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces to add to the space.\n",
            )
        )
        return False
    merged = existing + additions
    return session.spaces.set_space_boundaries(space, merged)


def remove_selected_space_boundaries(session, row_indexes=None):
    space = plan_selection.get_selected_plan_target_object(session, "space")
    if not session.selection.is_plan_space_object(space):
        return False
    existing = session.spaces.get_space_boundary_entries(space)
    if not existing:
        return False

    if row_indexes:
        row_indexes = set(int(index) for index in row_indexes if int(index) >= 0)
        remaining = [boundary for idx, boundary in enumerate(existing) if idx not in row_indexes]
        if len(remaining) == len(existing):
            return False
        return session.spaces.set_space_boundaries(space, remaining)

    removals = {
        session.spaces.space_boundary_key(boundary)
        for boundary in session.spaces.get_selected_space_boundary_links(fallback_space=space)
    }
    if not removals:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select boundary rows or room-bounding walls to remove from the space.\n",
            )
        )
        return False
    remaining = [
        boundary
        for boundary in existing
        if session.spaces.space_boundary_key(boundary) not in removals
    ]
    if len(remaining) == len(existing):
        return False
    return session.spaces.set_space_boundaries(space, remaining)


def refresh_selected_space_visuals(session):
    session.overlays.invalidate_selected_space_overlay_cache()
    session.overlays.sync_selected_space_overlay()
    session.viewport.request_view_redraw()


def refresh_selected_region_visuals(session):
    session.overlays.sync_selected_region_overlay()
    session.viewport.request_view_redraw()


def restore_selected_semantic_target(session, kind, obj, *, clear_edit_space=False):
    sync_method = {
        plan_target_kinds.PLAN_TARGET_REGION: session.overlays.sync_selected_region_overlay,
        plan_target_kinds.PLAN_TARGET_SPACE: session.overlays.sync_selected_space_overlay,
    }.get(kind)
    if sync_method is None:
        return
    session.current_tool = "Select"
    if clear_edit_space:
        session._edit_space = None
    if obj:
        session.selection.set_selected_plan_target(kind, obj, pending_restore=True)
        session.selection.set_gui_selection_object(obj)
    else:
        session.selection.set_selected_plan_target()
    sync_method()
    session.task_panels.refresh_task_panel_status()


def queue_restore_selected_semantic_target(session, kind, obj, *, clear_edit_space=False):
    try:
        from PySide import QtCore
    except ImportError:
        restore_selected_semantic_target(
            session,
            kind,
            obj,
            clear_edit_space=clear_edit_space,
        )
        return
    QtCore.QTimer.singleShot(
        0,
        lambda: restore_selected_semantic_target(
            session,
            kind,
            obj,
            clear_edit_space=clear_edit_space,
        ),
    )


def restore_selected_region(session, region):
    restore_selected_semantic_target(session, plan_target_kinds.PLAN_TARGET_REGION, region)


def queue_restore_selected_region(session, region):
    queue_restore_selected_semantic_target(
        session,
        plan_target_kinds.PLAN_TARGET_REGION,
        region,
    )


def restore_selected_space(session, space):
    restore_selected_semantic_target(
        session,
        plan_target_kinds.PLAN_TARGET_SPACE,
        space,
        clear_edit_space=True,
    )


def queue_restore_selected_space(session, space):
    queue_restore_selected_semantic_target(
        session,
        plan_target_kinds.PLAN_TARGET_SPACE,
        space,
        clear_edit_space=True,
    )


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
        from bimplan.runtime import session_components as plan_session_components

        return plan_session_components.plan_spaces.set_hovered_space_region_candidate(
            self.session,
            candidate,
            plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK,
        )
