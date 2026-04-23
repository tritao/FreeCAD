# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space boundary helpers for BIM Plan Edit."""

from dataclasses import dataclass

import FreeCAD
import FreeCADGui

from . import selection_access as plan_selection_access
from . import target_dispatch as plan_target_dispatch
from . import target_kinds as plan_target_kinds

translate = FreeCAD.Qt.translate

_MIN_WALL_LENGTH = 10.0
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


def has_active_space_separator_tool(session):
    return session._space_separator_start is not None or session.current_tool == "Separator"


def has_active_plan_region_tool(session):
    return bool(session._plan_region_points) or session.current_tool == "Region"


def clear_plan_region_preview(session):
    session._finalize_trackers(session._plan_region_preview_trackers)
    session._plan_region_preview_trackers = []


def set_plan_region_tool_state(session, points=None, parent_space=None):
    session._plan_region_points = list(points or [])
    session._plan_region_parent_space = parent_space


def reset_plan_region_tool_state(session, clear_preview=True):
    set_plan_region_tool_state(session)
    if clear_preview:
        session._clear_plan_region_preview()


def prepare_plan_region_tool_state(session, parent_space=None):
    reset_plan_region_tool_state(session)
    session._plan_region_parent_space = parent_space


def _cancel_snap_tool(session, *, is_active, clear_preview, reset_state, sync_kinds, refresh=True):
    if not is_active():
        return False
    session._stop_snapper()
    clear_preview()
    reset_state()
    FreeCAD.activeDraftCommand = None
    session.current_tool = "Select"
    if refresh:
        session._refresh_task_panel_status()
    plan_target_dispatch.sync_selected_target_visuals(
        session,
        kinds=sync_kinds,
        force=True,
    )
    return True


def cancel_plan_region_tool(session, refresh=True):
    return _cancel_snap_tool(
        session,
        is_active=session._has_active_plan_region_tool,
        clear_preview=session._clear_plan_region_preview,
        reset_state=lambda: reset_plan_region_tool_state(session, clear_preview=False),
        sync_kinds=plan_target_kinds.PLAN_REGION_CANCEL_VISUAL_KINDS,
        refresh=refresh,
    )


def get_plan_region_close_tolerance(session):
    units_per_pixel = session._get_plan_view_units_per_pixel()
    if units_per_pixel is None:
        return 120.0
    return max(120.0, float(units_per_pixel) * 12.0)


def format_space_region_candidate_area(candidate):
    area = float((candidate or {}).get("area", 0.0) or 0.0)
    if area <= 0.0:
        return ""
    try:
        quantity = FreeCAD.Units.Quantity(area, "mm^2")
        return quantity.UserString
    except Exception:
        return "{:.3f} m^2".format(area / 1000000.0)


def get_plan_region_preview_segments(session, point=None):
    points = [FreeCAD.Vector(item) for item in (session._plan_region_points or [])]
    if point is not None:
        point = session._project_plan_point(point)
        if point is not None and (not points or point.distanceToPoint(points[-1]) > 0.000001):
            points.append(point)
    segments = []
    for start, end in zip(points, points[1:]):
        if start.distanceToPoint(end) <= 0.000001:
            continue
        segments.append((start, end, False))
    if len(points) >= 3 and points[-1].distanceToPoint(points[0]) > 0.000001:
        segments.append((points[-1], points[0], True))
    return segments


def update_plan_region_preview(session, point, info):
    del info
    segments = session._get_plan_region_preview_segments(point)
    session._clear_plan_region_preview()
    if not segments:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return

    color = (0.86, 0.48, 0.12)
    width = session._scaled_line_width(2)
    for index, (start, end, dotted) in enumerate(segments):
        tracker = session._make_plan_line_tracker(
            DraftTrackers,
            "plan_region_preview:{}".format(index),
            dotted=dotted,
            scolor=color,
            swidth=width,
            ontop=True,
        )
        tracker.p1(start)
        tracker.p2(end)
        tracker.on()
        session._plan_region_preview_trackers.append(tracker)


def create_plan_region(session, points):
    import Arch

    region = None
    session.doc.openTransaction(translate("BIM_PlanEdit", "Create Plan Region"))
    try:
        region = Arch.makePlanRegion(
            points=points,
            parent_space=session._plan_region_parent_space,
        )
        if not region:
            raise RuntimeError("Unable to create plan region")
        session._add_object_to_active_storey(region)
        session.doc.recompute()
        if not session._get_region_footprint_faces(region):
            raise RuntimeError("Plan region has no valid footprint")
        session.doc.commitTransaction()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        raise
    return region


def finalize_plan_region(session):
    if len(session._plan_region_points) < 3:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Place at least three points before finishing the region.\n",
            )
        )
        return False
    try:
        region = session._create_plan_region(session._plan_region_points)
    except Exception:
        FreeCAD.Console.PrintError(translate("BIM_PlanEdit", "Failed to create the plan region.\n"))
        return False

    session._register_plan_object(region)
    session._cancel_plan_region_tool(refresh=False)
    session._restore_selected_region(region)
    return True


def handle_plan_region_point(session, point=None, obj=None):
    del obj
    if point is None:
        session._cancel_plan_region_tool()
        return

    point = session._project_plan_point(point)
    if point is None:
        session._cancel_plan_region_tool()
        return

    if session._plan_region_points:
        if point.distanceToPoint(session._plan_region_points[-1]) <= 0.000001:
            FreeCADGui.Snapper.getPoint(
                callback=session._handle_plan_region_point,
                movecallback=session._update_plan_region_preview,
                last=session._plan_region_points[-1],
                title=translate("BIM_PlanEdit", "Next region point"),
                mode="line",
            )
            return
        if (
            len(session._plan_region_points) >= 3
            and point.distanceToPoint(session._plan_region_points[0])
            <= session._get_plan_region_close_tolerance()
        ):
            session._finalize_plan_region()
            return

    session._plan_region_points.append(point)
    session._update_plan_region_preview(None, None)
    FreeCADGui.Snapper.getPoint(
        callback=session._handle_plan_region_point,
        movecallback=session._update_plan_region_preview,
        last=point,
        title=translate("BIM_PlanEdit", "Next region point"),
        mode="line",
    )


def clear_space_separator_preview(session):
    session._finalize_trackers(session._space_separator_preview_trackers)
    session._space_separator_preview_trackers = []


def set_space_separator_tool_state(session, start=None, height=None):
    session._space_separator_start = start
    session._space_separator_height = height


def reset_space_separator_tool_state(session, clear_preview=True):
    set_space_separator_tool_state(session)
    if clear_preview:
        session._clear_space_separator_preview()


def prepare_space_separator_tool_state(session, height=None):
    reset_space_separator_tool_state(session)
    session._space_separator_height = height


def cancel_space_separator_tool(session, refresh=True):
    return _cancel_snap_tool(
        session,
        is_active=session._has_active_space_separator_tool,
        clear_preview=session._clear_space_separator_preview,
        reset_state=lambda: reset_space_separator_tool_state(session, clear_preview=False),
        sync_kinds=plan_target_kinds.SPACE_SEPARATOR_CANCEL_VISUAL_KINDS,
        refresh=refresh,
    )


def update_space_separator_preview(session, point, info):
    del info
    start = session._space_separator_start
    if start is None or point is None:
        return
    end = session._project_plan_point(point)
    if end is None or end.sub(start).Length < _MIN_WALL_LENGTH:
        return
    try:
        import draftguitools.gui_trackers as DraftTrackers
    except Exception:
        return

    if not session._space_separator_preview_trackers:
        tracker = session._make_plan_line_tracker(
            DraftTrackers,
            "space_separator_preview",
            dotted=True,
            ontop=True,
        )
        session._space_separator_preview_trackers.append(tracker)
    tracker = session._space_separator_preview_trackers[0]
    tracker.p1(start)
    tracker.p2(end)
    tracker.on()


def create_space_separator(session, start, end):
    import Arch

    separator = None
    session.doc.openTransaction(translate("BIM_PlanEdit", "Create Space Separator"))
    try:
        separator = Arch.makeSpaceSeparator(
            start=start,
            end=end,
            height=session._space_separator_height,
        )
        if not separator:
            raise RuntimeError("Unable to create space separator")
        session._add_object_to_active_storey(separator)
        session.doc.recompute()
        session.doc.commitTransaction()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        raise
    return separator


def handle_space_separator_point(session, point=None, obj=None):
    del obj
    if point is None:
        session._cancel_space_separator_tool()
        return

    point = session._project_plan_point(point)
    if session._space_separator_start is None:
        session._space_separator_start = point
        FreeCADGui.Snapper.getPoint(
            callback=session._handle_space_separator_point,
            movecallback=session._update_space_separator_preview,
            last=point,
            title=translate("BIM_PlanEdit", "Separator end point"),
            mode="line",
        )
        return

    if point.sub(session._space_separator_start).Length < _MIN_WALL_LENGTH:
        session._cancel_space_separator_tool()
        return

    try:
        separator = session._create_space_separator(session._space_separator_start, point)
    except Exception:
        session._cancel_space_separator_tool()
        FreeCAD.Console.PrintError(
            translate("BIM_PlanEdit", "Failed to create the space separator.\n")
        )
        return

    session._register_plan_object(separator)
    session._cancel_space_separator_tool(refresh=False)
    session.current_tool = "Select"
    session._refresh_primary_selected_plan_target()
    session._refresh_task_panel_status()


def get_space_reference_point(session, space):
    if not session._is_plan_space_object(space):
        return None
    shape = getattr(space, "Shape", None)
    if shape and hasattr(shape, "CenterOfMass"):
        try:
            return session._project_plan_point(shape.CenterOfMass)
        except Exception:
            pass
    placement = getattr(space, "Placement", None)
    if placement is not None:
        try:
            return session._project_plan_point(placement.Base)
        except Exception:
            pass
    return None


def get_space_boundary_reference_point(session, selection_ex, fallback_space=None):
    points = []
    for selection in selection_ex or []:
        obj = getattr(selection, "Object", None)
        if not obj or obj == fallback_space:
            continue
        subobjects = list(getattr(selection, "SubObjects", []) or [])
        added_subobject_center = False
        for subobject in subobjects:
            center = getattr(subobject, "CenterOfMass", None)
            if center is None:
                continue
            try:
                points.append(FreeCAD.Vector(center.x, center.y, center.z))
                added_subobject_center = True
            except Exception:
                continue
        if added_subobject_center:
            continue
        shape = getattr(obj, "Shape", None)
        bound_box = getattr(shape, "BoundBox", None)
        center = getattr(bound_box, "Center", None) if bound_box is not None else None
        if center is None:
            continue
        try:
            points.append(FreeCAD.Vector(center.x, center.y, center.z))
        except Exception:
            continue
    if points:
        total = FreeCAD.Vector()
        for point in points:
            total = total.add(point)
        return total.multiply(1.0 / float(len(points)))
    return session._get_space_reference_point(fallback_space)


def get_space_boundary_entries(session, space):
    if not session._is_plan_space_object(space):
        return []
    import ArchSpace

    entries = []
    for boundary in getattr(space, "Boundaries", []) or []:
        try:
            obj = boundary[0]
            subnames = boundary[1]
        except Exception:
            continue
        entries.append((obj, ArchSpace.normalizeBoundarySubnames(subnames)))
    return ArchSpace.normalizeBoundaryLinks(entries)


def space_boundary_key(boundary):
    import ArchSpace

    obj, subnames = boundary
    return (
        getattr(obj, "Name", None),
        tuple(ArchSpace.normalizeBoundarySubnames(subnames)),
    )


def get_selected_space_boundary_links(session, fallback_space=None):
    import ArchSpace

    selection_ex = session._get_gui_selection_ex()
    reference_point = (
        session._get_space_reference_point(fallback_space)
        if fallback_space is not None
        else session._get_space_boundary_reference_point(selection_ex)
    )
    entries = []
    for selection in selection_ex:
        obj = session._get_plan_semantic_object(getattr(selection, "Object", None))
        if not obj:
            continue
        entries.append((obj, getattr(selection, "SubElementNames", []) or ()))
    return ArchSpace.resolveBoundaryLinks(
        entries,
        reference_point=reference_point,
        exclude_objects=(fallback_space,) if fallback_space is not None else None,
    )


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
    return session._get_selected_space_boundary_links(fallback_space=fallback_space)


def _resolve_space_creation_request(session, targets=None):
    targets = tuple(
        targets if targets is not None else plan_selection_access.get_selected_plan_targets(session)
    )
    if not targets:
        return None

    selection_shape = _resolve_space_selection_shape(targets)
    if selection_shape.mode == _SPACE_SELECTION_WALL_BOUNDARIES:
        return SpaceCreationRequest(
            targets=selection_shape.targets,
            mode=selection_shape.mode,
            wall_targets=selection_shape.wall_targets,
            boundaries=tuple(_get_selected_space_boundary_links(session)),
        )

    if selection_shape.mode not in (
        _SPACE_SELECTION_SEEDED_REGION,
        _SPACE_SELECTION_SINGLE_SPACE,
    ):
        return None

    region_seed_space = selection_shape.region_seed_space
    boundaries = tuple(
        _get_selected_space_boundary_links(session, fallback_space=region_seed_space)
    )
    if selection_shape.mode == _SPACE_SELECTION_SINGLE_SPACE and not boundaries:
        return None

    return SpaceCreationRequest(
        targets=selection_shape.targets,
        mode=_SPACE_SELECTION_SEEDED_REGION,
        label=getattr(region_seed_space, "Label", None),
        region_seed_space=region_seed_space,
        wall_targets=selection_shape.wall_targets,
        boundaries=boundaries,
    )


def get_space_region_seed_targets(session, targets=None):
    targets = tuple(
        targets if targets is not None else plan_selection_access.get_selected_plan_targets(session)
    )
    selection_shape = _resolve_space_selection_shape(targets)
    if selection_shape.mode == _SPACE_SELECTION_SEEDED_REGION:
        return (selection_shape.region_seed_space, list(selection_shape.wall_targets))
    if selection_shape.mode != _SPACE_SELECTION_SINGLE_SPACE:
        return (None, [])
    boundary_links = _get_selected_space_boundary_links(
        session,
        fallback_space=selection_shape.region_seed_space,
    )
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
    exclude_space = session._get_plan_semantic_object(exclude) if exclude else None
    exclude_name = getattr(exclude_space, "Name", None)

    spaces = []
    seen = set()
    for obj in session.doc.Objects:
        semantic_obj = session._get_plan_semantic_object(obj)
        name = getattr(semantic_obj, "Name", None)
        if not name or name in seen:
            continue
        seen.add(name)
        if name == exclude_name or not session._is_plan_space_object(semantic_obj):
            continue
        if active_storey_name is not None:
            storeys = session._get_object_storeys(semantic_obj)
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
        footprint_faces = session._get_space_footprint_faces(space)
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
            if session._get_xy_bound_box_iou(candidate_face, footprint_face) >= float(
                overlap_iou_tolerance
            ):
                return True
    return False


def filter_claimed_space_region_candidates(session, candidates, exclude_space=None):
    candidates = list(candidates or [])
    if not candidates:
        return candidates, 0

    spaces = session._get_existing_space_region_filter_spaces(exclude=exclude_space)
    if not spaces:
        return candidates, 0

    filtered = []
    skipped = 0
    for candidate in candidates:
        if session._is_space_region_candidate_claimed(candidate, spaces):
            skipped += 1
            continue
        filtered.append(candidate)
    return filtered, skipped


def get_space_region_candidate_report(session, boundaries, label=None, seed_space=None):
    import ArchSpace

    report = ArchSpace.getBoundaryRegionCandidates(
        boundaries,
        label=label,
        seed_space=seed_space,
    )
    report = dict(report or {})
    candidates = list(report.get("candidates", []) or [])
    skipped_claimed = 0
    if seed_space is None:
        candidates, skipped_claimed = session._filter_claimed_space_region_candidates(candidates)
    report["candidates"] = candidates
    report["candidate_count"] = len(candidates)
    report["skipped_claimed_candidate_count"] = skipped_claimed
    return report


def report_space_region_candidate_failure(report):
    skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
    if skipped_claimed and not int(report.get("candidate_count", 0) or 0):
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "All enclosed regions are already covered by existing spaces.\n",
            )
        )
        return

    message = str(report.get("message") or "").strip()
    details = [str(detail).strip() for detail in report.get("details", []) if str(detail).strip()]
    if message:
        FreeCAD.Console.PrintError(message + "\n")
        for detail in details:
            FreeCAD.Console.PrintError(f"  - {detail}\n")
        return

    FreeCAD.Console.PrintError(
        translate(
            "BIM_PlanEdit",
            "Failed to derive enclosed space regions from the current selection.\n",
        )
    )


def set_space_region_pick_state(
    session,
    boundaries=None,
    candidates=None,
    *,
    seed_space=None,
    hovered_candidate=None,
):
    session._space_region_pick_boundaries = list(boundaries or [])
    session._space_region_candidates = list(candidates or [])
    session._hovered_space_region_candidate = hovered_candidate
    session._space_region_pick_seed_space = seed_space


def reset_space_region_pick_state(session, clear_overlays=True):
    set_space_region_pick_state(session)
    if clear_overlays:
        session._clear_space_region_pick_overlays()


def set_space_text_pick_state(session, space=None):
    session._edit_space = space


def reset_space_text_pick_state(session):
    set_space_text_pick_state(session)


def _finish_created_space(session, space, event_callback=None, claim_click=False):
    session._register_plan_object(space)
    session._restore_selected_space(space)
    if claim_click:
        session._claim_left_button_click(event_callback)
    return True


def _create_space_in_transaction(
    session,
    *,
    create_space,
    boundaries=None,
    keep_boundaries=False,
):
    boundaries = list(boundaries or [])
    space = None
    reported_failure = False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Create Space"))
        space = create_space()
        if not space:
            raise RuntimeError("Unable to create space")
        if keep_boundaries and boundaries:
            space.Boundaries = boundaries
        session._add_object_to_active_storey(space)
        session.doc.recompute()
        if not session._space_has_valid_geometry(space):
            reported_failure = session._report_space_creation_failure(space)
            raise RuntimeError("Unable to create space")
        session.doc.commitTransaction()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        if not reported_failure:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the selected space.\n")
            )
        return None
    return space


def _create_and_finish_space_region_candidate(
    session,
    candidate,
    *,
    boundaries,
    keep_boundaries,
    event_callback=None,
    claim_click=False,
    clear_region_pick_state=False,
):
    space = session._create_space_from_region_candidate(
        candidate,
        boundaries=boundaries,
        keep_boundaries=keep_boundaries,
    )
    if not space:
        return False
    if clear_region_pick_state:
        reset_space_region_pick_state(session)
    return _finish_created_space(
        session,
        space,
        event_callback=event_callback,
        claim_click=claim_click,
    )


def _start_space_region_pick_mode(session, boundaries, candidates, seed_space=None):
    session.current_tool = "Pick Space Region"
    set_space_region_pick_state(
        session,
        boundaries=boundaries,
        candidates=candidates,
        seed_space=seed_space,
    )
    session._clear_wall_grips()
    session._clear_hovered_plan_targets(kinds=plan_target_kinds.SPACE_EDIT_CLEAR_HOVERED_KINDS)
    session._refresh_primary_selected_plan_target()
    FreeCAD.Console.PrintMessage(
        translate(
            "BIM_PlanEdit",
            "Multiple enclosed regions found. Hover a dashed region and click to create that space.\n",
        )
    )
    return True


def _consume_space_region_candidate_report(
    session,
    boundaries,
    report,
    *,
    seed_space=None,
    keep_boundaries=True,
    announce_skipped_claimed=False,
):
    candidates = list(report.get("candidates", []) or [])
    if not candidates:
        session._report_space_region_candidate_failure(report)
        return False

    skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
    if announce_skipped_claimed and skipped_claimed:
        FreeCAD.Console.PrintMessage(
            translate(
                "BIM_PlanEdit",
                "Ignoring {count} enclosed region(s) already covered by existing spaces.\n",
            ).format(count=skipped_claimed)
        )

    if len(candidates) == 1:
        return _create_and_finish_space_region_candidate(
            session,
            candidates[0],
            boundaries=boundaries,
            keep_boundaries=keep_boundaries,
        )

    return _start_space_region_pick_mode(
        session,
        boundaries,
        candidates,
        seed_space=seed_space,
    )


def get_space_region_candidate_polylines(session, candidate):
    face = candidate.get("face") if isinstance(candidate, dict) else None
    if not face:
        return []
    return session._get_footprint_overlay_polylines([face])


def get_space_region_candidate_segments(session, candidate):
    segments = []
    for polyline in session._get_space_region_candidate_polylines(candidate):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            segments.append((start, end))
    return segments


def pick_space_region_candidate(session, mouse_pos, radius_px=10):
    if session.current_tool != "Pick Space Region" or not session._space_region_candidates:
        return None

    point = session._get_plan_point_from_mouse_pos(mouse_pos)
    if point is not None:
        for candidate in session._space_region_candidates:
            face = candidate.get("face")
            if not face:
                continue
            bound_box = getattr(face, "BoundBox", None)
            if bound_box is None:
                continue
            test_point = FreeCAD.Vector(point.x, point.y, float(bound_box.ZMin))
            try:
                if face.isInside(test_point, 0.001, True):
                    return candidate
            except Exception:
                continue

    radius_sq = float(radius_px) * float(radius_px)
    best_candidate = None
    best_distance_sq = None
    for candidate in session._space_region_candidates:
        for start, end in session._get_space_region_candidate_segments(candidate):
            distance_sq = session._get_screen_distance_sq_to_segment(mouse_pos, start, end)
            if distance_sq is None or distance_sq > radius_sq:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_candidate = candidate
                best_distance_sq = distance_sq
    return best_candidate


def set_hovered_space_region_candidate(session, candidate, visual_key):
    if session._hovered_space_region_candidate is candidate:
        return
    session._hovered_space_region_candidate = candidate
    session._queue_plan_overlay_visual_refresh(visual_key)
    session._refresh_task_panel_status()


def create_space_region_base_object(session, candidate):
    shape = candidate.get("shape") if isinstance(candidate, dict) else None
    if not shape:
        return None
    try:
        base = session.doc.addObject("Part::Feature", "SpaceRegionBase")
    except Exception:
        return None
    try:
        shape_copy = session._copy_shape_without_element_map(shape)
        if shape_copy is None:
            return None
        base.Shape = shape_copy
    except Exception:
        return None

    view_object = getattr(base, "ViewObject", None)
    if view_object:
        if hasattr(view_object, "Visibility"):
            try:
                view_object.Visibility = False
            except Exception:
                pass
        if hasattr(view_object, "ShowInTree"):
            try:
                view_object.ShowInTree = False
            except Exception:
                pass
        if hasattr(view_object, "Selectable"):
            try:
                view_object.Selectable = False
            except Exception:
                pass
    return base


def begin_space_region_pick(session, boundaries, label=None, seed_space=None, report=None):
    if report is None:
        report = session._get_space_region_candidate_report(
            boundaries,
            label=label,
            seed_space=seed_space,
        )
    return _consume_space_region_candidate_report(
        session,
        boundaries,
        report,
        seed_space=seed_space,
        keep_boundaries=seed_space is None,
        announce_skipped_claimed=True,
    )


def cancel_space_region_pick(session, refresh=True):
    was_active = session.current_tool == "Pick Space Region" or bool(
        session._space_region_candidates
    )
    reset_space_region_pick_state(session)
    if session.current_tool == "Pick Space Region":
        session.current_tool = "Select"
    if was_active:
        session._refresh_primary_selected_plan_target()
    elif refresh:
        session._refresh_task_panel_status()
    return was_active


def create_space_from_region_candidate(session, candidate, boundaries=None, keep_boundaries=True):
    import Arch

    if not isinstance(candidate, dict):
        return None

    def create_space():
        base = session._create_space_region_base_object(candidate)
        if not base:
            return None
        return Arch.makeSpace(base)

    return _create_space_in_transaction(
        session,
        create_space=create_space,
        boundaries=boundaries,
        keep_boundaries=keep_boundaries,
    )


def activate_space_region_candidate(session, candidate, event_callback=None):
    if session.current_tool != "Pick Space Region" or not isinstance(candidate, dict):
        return False

    boundaries = list(session._space_region_pick_boundaries or [])
    if not boundaries and session._space_region_pick_seed_space is None:
        return False

    return _create_and_finish_space_region_candidate(
        session,
        candidate,
        boundaries=boundaries,
        keep_boundaries=session._space_region_pick_seed_space is None,
        event_callback=event_callback,
        claim_click=True,
        clear_region_pick_state=True,
    )


def create_space_from_current_selection(session):
    import Arch
    import ArchSpace

    request = _resolve_space_creation_request(session)
    if not request:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces before using Space.\n",
            )
        )
        return False

    boundaries = list(request.boundaries or [])
    region_seed_space = request.region_seed_space
    if not boundaries:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces before using Space.\n",
            )
        )
        return False

    if region_seed_space is not None:
        report = session._get_space_region_candidate_report(
            boundaries,
            label=request.label,
            seed_space=region_seed_space,
        )
        return _consume_space_region_candidate_report(
            session,
            boundaries,
            report,
            seed_space=region_seed_space,
            keep_boundaries=False,
        )

    report = ArchSpace.analyzeBoundaryLinks(boundaries)
    if report.get("code") == "multiple_regions":
        region_report = session._get_space_region_candidate_report(
            boundaries,
            label=report.get("label"),
        )
        return _consume_space_region_candidate_report(
            session,
            boundaries,
            region_report,
            keep_boundaries=True,
        )

    space = _create_space_in_transaction(
        session,
        create_space=lambda: Arch.makeSpace(boundaries),
    )
    if not space:
        return False

    return _finish_created_space(session, space)


def space_has_valid_geometry(session, space):
    if not session._is_plan_space_object(space):
        return False
    try:
        shape = getattr(space, "Shape", None)
    except Exception:
        return False
    if not shape:
        return False
    try:
        if shape.isNull():
            return False
    except Exception:
        pass
    return bool(getattr(shape, "Solids", None))


def report_space_creation_failure(space):
    proxy = getattr(space, "Proxy", None)
    if not proxy:
        return False

    message = ""
    if hasattr(proxy, "getLastBoundaryError"):
        try:
            message = str(proxy.getLastBoundaryError(space) or "").strip()
        except Exception:
            message = ""

    if not message:
        return False

    FreeCAD.Console.PrintWarning(
        translate(
            "BIM_PlanEdit",
            "Plan Edit kept no new space object because the selection could not be turned into a valid Arch Space.\n",
        )
    )
    return True


def set_selected_space_label(session, label):
    space = plan_selection_access.get_selected_plan_target_object(session, "space")
    if not session._is_plan_space_object(space):
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
    session._refresh_task_panel_status()
    return True


def set_selected_space_type(session, space_type):
    space = plan_selection_access.get_selected_plan_target_object(session, "space")
    if not session._is_plan_space_object(space):
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
    session._refresh_task_panel_status()
    return True


def set_selected_region_label(session, label):
    region = plan_selection_access.get_selected_plan_target_object(session, "region")
    if not session._is_plan_region_object(region):
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
    session._refresh_task_panel_status()
    return True


def set_selected_region_scheme(session, scheme):
    region = plan_selection_access.get_selected_plan_target_object(session, "region")
    if not session._is_plan_region_object(region):
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
    session._refresh_task_panel_status()
    return True


def set_selected_region_type(session, region_type):
    region = plan_selection_access.get_selected_plan_target_object(session, "region")
    if not session._is_plan_region_object(region):
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
    session._refresh_task_panel_status()
    return True


def set_selected_region_parent_space(session, space):
    region = plan_selection_access.get_selected_plan_target_object(session, "region")
    if not session._is_plan_region_object(region):
        return False
    space = session._get_plan_semantic_object(space) if space else None
    if space is not None and not session._is_plan_space_object(space):
        return False

    current_parent = getattr(region, "ParentSpace", None)
    current_parent = session._get_plan_semantic_object(current_parent) if current_parent else None
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
    session._refresh_task_panel_status()
    return True


def set_space_boundaries(session, space, boundaries):
    if not session._is_plan_space_object(space):
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
    session._refresh_selected_space_visuals()
    session._refresh_task_panel_status()
    return True


def add_boundaries_to_selected_space(session):
    space = plan_selection_access.get_selected_plan_target_object(session, "space")
    if not session._is_plan_space_object(space):
        return False
    existing = session._get_space_boundary_entries(space)
    additions = session._get_selected_space_boundary_links(fallback_space=space)
    if not additions:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces to add to the space.\n",
            )
        )
        return False
    merged = existing + additions
    return session._set_space_boundaries(space, merged)


def remove_selected_space_boundaries(session, row_indexes=None):
    space = plan_selection_access.get_selected_plan_target_object(session, "space")
    if not session._is_plan_space_object(space):
        return False
    existing = session._get_space_boundary_entries(space)
    if not existing:
        return False

    if row_indexes:
        row_indexes = set(int(index) for index in row_indexes if int(index) >= 0)
        remaining = [boundary for idx, boundary in enumerate(existing) if idx not in row_indexes]
        if len(remaining) == len(existing):
            return False
        return session._set_space_boundaries(space, remaining)

    removals = {
        session._space_boundary_key(boundary)
        for boundary in session._get_selected_space_boundary_links(fallback_space=space)
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
        boundary for boundary in existing if session._space_boundary_key(boundary) not in removals
    ]
    if len(remaining) == len(existing):
        return False
    return session._set_space_boundaries(space, remaining)


def start_space_text_position_pick(session):
    space = plan_selection_access.get_selected_plan_target_object(session, "space")
    if not session._is_plan_space_object(space):
        return False
    import FreeCADGui

    session.current_tool = "Set Space Text"
    set_space_text_pick_state(session, space)
    session._clear_hovered_plan_targets(kinds=plan_target_kinds.SPACE_EDIT_CLEAR_HOVERED_KINDS)
    session._sync_secondary_selected_overlays()
    session._refresh_task_panel_status()
    FreeCAD.activeDraftCommand = session
    session._set_draft_point_focus_suppressed(True)
    FreeCADGui.Snapper.getPoint(
        callback=session._finish_space_text_position_pick,
        last=session._get_space_reference_point(space),
        title=translate("BIM_PlanEdit", "Pick space text position"),
        noTracker=True,
    )
    session.viewport.queue_focus_plan_view()
    return True


def finish_space_text_position_pick(session, point=None, obj=None):
    del obj
    space = session._edit_space
    reset_space_text_pick_state(session)
    FreeCAD.activeDraftCommand = None
    session._set_draft_point_focus_suppressed(False)

    if point is None or not session._is_plan_space_object(space):
        session.current_tool = "Select"
        session._refresh_task_panel_status()
        return

    point = session._project_plan_point(point)
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Set Space Text Position"))
        space.ViewObject.TextPosition = space.Placement.inverse().multVec(point)
        session.doc.commitTransaction()
        session.doc.recompute()
    except Exception:
        try:
            session.doc.abortTransaction()
        except Exception:
            pass
        session._restore_selected_space(space)
        return

    session.current_tool = "Select"
    session._queue_restore_selected_space(space)


def cancel_space_text_position_pick(session):
    space = session._edit_space or plan_selection_access.get_selected_plan_target_object(
        session, "space"
    )
    reset_space_text_pick_state(session)
    session._stop_snapper()
    FreeCAD.activeDraftCommand = None
    session._set_draft_point_focus_suppressed(False)
    session.current_tool = "Select"
    if space:
        session._set_selected_plan_target("space", space, pending_restore=True)
    session._sync_selected_space_overlay()
    session._refresh_task_panel_status()


def get_space_preflight_report(session, targets=None):
    if session.current_tool != "Select":
        return None

    targets = list(
        targets if targets is not None else plan_selection_access.get_selected_plan_targets(session)
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
