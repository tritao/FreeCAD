# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space boundary helpers for BIM Plan Edit."""

from dataclasses import dataclass

import FreeCAD

from bimplan import document_visuals as plan_document_visuals
from bimplan import selection as plan_selection
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.selection import targets as plan_targets
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


def format_space_region_candidate_area(candidate):
    area = float((candidate or {}).get("area", 0.0) or 0.0)
    if area <= 0.0:
        return ""
    try:
        quantity = FreeCAD.Units.Quantity(area, "mm^2")
        return quantity.UserString
    except Exception:
        return "{:.3f} m^2".format(area / 1000000.0)


def get_space_reference_point(session, space):
    if not session.selection.is_plan_space_object(space):
        return None
    return _get_projected_space_shape_center(session, space) or _get_projected_space_base_point(
        session,
        space,
    )


def _get_projected_space_shape_center(session, space):
    shape = getattr(space, "Shape", None)
    if not (shape and hasattr(shape, "CenterOfMass")):
        return None
    try:
        return session.viewport.project_plan_point(shape.CenterOfMass)
    except Exception:
        return None


def _get_projected_space_base_point(session, space):
    placement = getattr(space, "Placement", None)
    if placement is None:
        return None
    try:
        return session.viewport.project_plan_point(placement.Base)
    except Exception:
        return None


def get_space_boundary_reference_point(session, selection_ex, fallback_space=None):
    points = _collect_space_boundary_selection_points(selection_ex, fallback_space=fallback_space)
    if points:
        return _average_freecad_vectors(points)
    return session.spaces.get_space_reference_point(fallback_space)


def _collect_space_boundary_selection_points(selection_ex, *, fallback_space=None):
    points = []
    for selection in selection_ex or []:
        points.extend(
            _get_space_boundary_selection_points(selection, fallback_space=fallback_space)
        )
    return points


def _get_space_boundary_selection_points(selection, *, fallback_space=None):
    obj = getattr(selection, "Object", None)
    if not obj or obj == fallback_space:
        return []
    subobject_points = _get_space_boundary_subobject_centers(selection)
    if subobject_points:
        return subobject_points
    object_center = _get_space_boundary_object_center(obj)
    if object_center is None:
        return []
    return [object_center]


def _get_space_boundary_subobject_centers(selection):
    points = []
    for subobject in list(getattr(selection, "SubObjects", []) or []):
        center = getattr(subobject, "CenterOfMass", None)
        if center is None:
            continue
        try:
            points.append(FreeCAD.Vector(center.x, center.y, center.z))
        except Exception:
            continue
    return points


def _get_space_boundary_object_center(obj):
    shape = getattr(obj, "Shape", None)
    bound_box = getattr(shape, "BoundBox", None)
    center = getattr(bound_box, "Center", None) if bound_box is not None else None
    if center is None:
        return None
    try:
        return FreeCAD.Vector(center.x, center.y, center.z)
    except Exception:
        return None


def _average_freecad_vectors(points):
    total = FreeCAD.Vector()
    for point in points:
        total = total.add(point)
    return total.multiply(1.0 / float(len(points)))


def get_space_boundary_entries(session, space):
    if not session.selection.is_plan_space_object(space):
        return []
    import ArchSpace

    return ArchSpace.normalizeBoundaryLinks(
        _iter_normalized_space_boundary_entries(getattr(space, "Boundaries", []) or ())
    )


def _iter_normalized_space_boundary_entries(boundaries):
    import ArchSpace

    entries = []
    for boundary in boundaries:
        try:
            obj = boundary[0]
            subnames = boundary[1]
        except Exception:
            continue
        entries.append((obj, ArchSpace.normalizeBoundarySubnames(subnames)))
    return entries


def space_boundary_key(boundary):
    import ArchSpace

    obj, subnames = boundary
    return (
        getattr(obj, "Name", None),
        tuple(ArchSpace.normalizeBoundarySubnames(subnames)),
    )


def get_selected_space_boundary_links(session, fallback_space=None):
    import ArchSpace

    selection_ex = session.selection.get_gui_selection_ex()
    reference_point = _get_selected_space_boundary_reference_point(
        session,
        selection_ex,
        fallback_space=fallback_space,
    )
    entries = _get_selected_space_boundary_link_entries(session, selection_ex)
    return ArchSpace.resolveBoundaryLinks(
        entries,
        reference_point=reference_point,
        exclude_objects=(fallback_space,) if fallback_space is not None else None,
    )


def _get_selected_space_boundary_reference_point(session, selection_ex, *, fallback_space=None):
    if fallback_space is not None:
        return session.spaces.get_space_reference_point(fallback_space)
    return session.spaces.get_space_boundary_reference_point(selection_ex)


def _get_selected_space_boundary_link_entries(session, selection_ex):
    entries = []
    for selection in selection_ex:
        obj = session.visibility.get_plan_semantic_object(getattr(selection, "Object", None))
        if not obj:
            continue
        entries.append((obj, getattr(selection, "SubElementNames", []) or ()))
    return entries


def _resolve_space_selection_shape(targets):
    targets = tuple(targets or ())
    if not targets:
        return SpaceSelectionShape()

    wall_targets = tuple(
        (target_kind, target_obj)
        for target_kind, target_obj in targets
        if target_kind == plan_target_kinds.PLAN_TARGET_WALL
    )
    if len(wall_targets) == len(targets):
        return SpaceSelectionShape(
            targets=targets,
            mode=_SPACE_SELECTION_WALL_BOUNDARIES,
            wall_targets=wall_targets,
        )

    space_targets = [
        target_obj
        for target_kind, target_obj in targets
        if target_kind == plan_target_kinds.PLAN_TARGET_SPACE
    ]
    if len(space_targets) != 1:
        return SpaceSelectionShape(targets=targets)

    region_seed_space = space_targets[0]
    if len(targets) == 1:
        return SpaceSelectionShape(
            targets=targets,
            mode=_SPACE_SELECTION_SINGLE_SPACE,
            region_seed_space=region_seed_space,
        )

    if len(wall_targets) != len(targets) - 1:
        return SpaceSelectionShape(targets=targets)

    return SpaceSelectionShape(
        targets=targets,
        mode=_SPACE_SELECTION_SEEDED_REGION,
        region_seed_space=region_seed_space,
        wall_targets=wall_targets,
    )


def _get_selected_space_boundary_links(session, fallback_space=None):
    spaces_api = getattr(session, "spaces", None)
    if spaces_api is not None:
        return spaces_api.get_selected_space_boundary_links(fallback_space=fallback_space)
    return session.spaces.get_selected_space_boundary_links(fallback_space=fallback_space)


def _get_space_selection_targets(session, targets=None):
    return tuple(
        targets if targets is not None else plan_selection.get_selected_plan_targets(session)
    )


def _build_wall_boundary_space_creation_request(session, selection_shape):
    return SpaceCreationRequest(
        targets=selection_shape.targets,
        mode=selection_shape.mode,
        wall_targets=selection_shape.wall_targets,
        boundaries=tuple(_get_selected_space_boundary_links(session)),
    )


def _get_seed_space_boundary_links(session, selection_shape):
    return tuple(
        _get_selected_space_boundary_links(
            session,
            fallback_space=selection_shape.region_seed_space,
        )
    )


def _build_seeded_region_space_creation_request(session, selection_shape):
    boundaries = _get_seed_space_boundary_links(session, selection_shape)
    if selection_shape.mode == _SPACE_SELECTION_SINGLE_SPACE and not boundaries:
        return None
    region_seed_space = selection_shape.region_seed_space
    return SpaceCreationRequest(
        targets=selection_shape.targets,
        mode=_SPACE_SELECTION_SEEDED_REGION,
        label=getattr(region_seed_space, "Label", None),
        region_seed_space=region_seed_space,
        wall_targets=selection_shape.wall_targets,
        boundaries=boundaries,
    )


def _resolve_space_creation_request(session, targets=None):
    targets = _get_space_selection_targets(session, targets=targets)
    if not targets:
        return None

    selection_shape = _resolve_space_selection_shape(targets)
    if selection_shape.mode == _SPACE_SELECTION_WALL_BOUNDARIES:
        return _build_wall_boundary_space_creation_request(session, selection_shape)

    if selection_shape.mode not in (
        _SPACE_SELECTION_SEEDED_REGION,
        _SPACE_SELECTION_SINGLE_SPACE,
    ):
        return None
    return _build_seeded_region_space_creation_request(session, selection_shape)


def get_space_region_seed_targets(session, targets=None):
    targets = _get_space_selection_targets(session, targets=targets)
    selection_shape = _resolve_space_selection_shape(targets)
    if selection_shape.mode == _SPACE_SELECTION_SEEDED_REGION:
        return (selection_shape.region_seed_space, list(selection_shape.wall_targets))
    if selection_shape.mode != _SPACE_SELECTION_SINGLE_SPACE:
        return (None, [])
    boundary_links = _get_seed_space_boundary_links(session, selection_shape)
    if boundary_links:
        return (selection_shape.region_seed_space, [])
    return (None, [])


def get_selected_space_region_seed(session, targets=None):
    region_seed_space, _wall_targets = get_space_region_seed_targets(session, targets)
    return region_seed_space


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


def get_space_creation_request(session, targets=None):
    request = _resolve_space_creation_request(session, targets=targets)
    return request.to_dict() if request else None


def should_run_space_preflight_for_targets(targets):
    return _resolve_space_selection_shape(targets).should_run_preflight


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


def get_space_preflight_report(session, targets=None):
    if session.current_tool != "Select":
        return None

    targets = list(
        targets if targets is not None else plan_selection.get_selected_plan_targets(session)
    )
    if not should_run_space_preflight_for_targets(targets):
        return None

    request = _resolve_space_creation_request(session, targets=targets)
    if not request:
        return None

    import ArchSpace

    return ArchSpace.analyzeBoundaryLinks(
        request.boundaries,
        label=request.label,
        seed_space=request.region_seed_space,
    )


def format_space_preflight_text(report):
    if not report:
        return ""

    if report.get("valid"):
        inner_void_count = int(report.get("inner_void_count", 0) or 0)
        if inner_void_count <= 0:
            return translate("BIM_PlanEdit", "Space preflight: Valid space")
        if inner_void_count == 1:
            return translate("BIM_PlanEdit", "Space preflight: Valid space with 1 inner void")
        return translate(
            "BIM_PlanEdit", "Space preflight: Valid space with {count} inner voids"
        ).format(count=inner_void_count)

    code = report.get("code")
    status_map = {
        "empty": translate("BIM_PlanEdit", "Space preflight: Select room-bounding walls or faces"),
        "unusable_boundaries": translate(
            "BIM_PlanEdit", "Space preflight: No usable boundary faces"
        ),
        "no_height": translate("BIM_PlanEdit", "Space preflight: Boundaries have no height"),
        "no_intersection": translate(
            "BIM_PlanEdit", "Space preflight: Boundaries miss the plan cut"
        ),
        "open_loop": translate("BIM_PlanEdit", "Space preflight: Open loop"),
        "multiple_regions": translate("BIM_PlanEdit", "Space preflight: Multiple enclosed regions"),
        "nested_islands": translate(
            "BIM_PlanEdit", "Space preflight: Nested islands are not supported"
        ),
        "invalid_solid": translate(
            "BIM_PlanEdit", "Space preflight: Selection cannot become one space"
        ),
    }
    status = status_map.get(
        code,
        translate("BIM_PlanEdit", "Space preflight: Selection cannot become one space"),
    )
    details = [str(detail).strip() for detail in report.get("details", []) if str(detail).strip()]
    if details:
        return "{}\n{}".format(status, details[0])
    return status


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
