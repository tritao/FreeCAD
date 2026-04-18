# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space boundary helpers for BIM Plan Edit."""

import FreeCAD

translate = FreeCAD.Qt.translate


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


def get_space_region_seed_targets(session, targets=None):
    targets = list(targets if targets is not None else session._get_selected_plan_targets())
    if not targets:
        return (None, [])

    space_targets = [target_obj for target_kind, target_obj in targets if target_kind == "space"]
    if len(space_targets) != 1:
        return (None, [])

    if len(targets) == 1:
        boundary_links = session._get_selected_space_boundary_links(fallback_space=space_targets[0])
        if boundary_links:
            return (space_targets[0], [])
        return (None, [])

    wall_targets = [
        (target_kind, target_obj) for target_kind, target_obj in targets if target_kind == "wall"
    ]
    if len(wall_targets) != len(targets) - 1:
        return (None, [])

    return (space_targets[0], wall_targets)


def get_selected_space_region_seed(session, targets=None):
    region_seed_space, _wall_targets = session._get_space_region_seed_targets(targets)
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
    targets = list(targets if targets is not None else session._get_selected_plan_targets())
    if not targets:
        return None

    label = None
    region_seed_space = session._get_selected_space_region_seed(targets)
    if region_seed_space is not None:
        boundaries = session._get_selected_space_boundary_links(fallback_space=region_seed_space)
        label = getattr(region_seed_space, "Label", None)
    elif all(target_kind == "wall" for target_kind, _target_obj in targets):
        boundaries = session._get_selected_space_boundary_links()
    else:
        return None

    return {
        "targets": targets,
        "label": label,
        "region_seed_space": region_seed_space,
        "boundaries": boundaries,
    }


def should_run_space_preflight_for_targets(targets):
    targets = list(targets or [])
    if len(targets) <= 1:
        return False

    kinds = [target_kind for target_kind, _target_obj in targets]
    if all(kind == "wall" for kind in kinds):
        return True
    if kinds.count("space") == 1 and all(kind in ("space", "wall") for kind in kinds):
        return True
    return False


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
    candidates = list(report.get("candidates", []) or [])
    if not candidates:
        session._report_space_region_candidate_failure(report)
        return False

    skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
    if skipped_claimed:
        FreeCAD.Console.PrintMessage(
            translate(
                "BIM_PlanEdit",
                "Ignoring {count} enclosed region(s) already covered by existing spaces.\n",
            ).format(count=skipped_claimed)
        )
    if skipped_claimed and len(candidates) == 1:
        space = session._create_space_from_region_candidate(
            candidates[0],
            boundaries=boundaries,
            keep_boundaries=seed_space is None,
        )
        if not space:
            return False
        session._register_plan_object(space)
        session._restore_selected_space(space)
        return True

    session.current_tool = "Pick Space Region"
    session._space_region_pick_boundaries = list(boundaries)
    session._space_region_candidates = candidates
    session._hovered_space_region_candidate = None
    session._space_region_pick_seed_space = seed_space
    session._clear_wall_grips()
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_space(None)
    session._refresh_primary_selected_plan_target()
    FreeCAD.Console.PrintMessage(
        translate(
            "BIM_PlanEdit",
            "Multiple enclosed regions found. Hover a dashed region and click to create that space.\n",
        )
    )
    return True


def cancel_space_region_pick(session, refresh=True):
    was_active = session.current_tool == "Pick Space Region" or bool(
        session._space_region_candidates
    )
    session._space_region_pick_boundaries = []
    session._space_region_candidates = []
    session._hovered_space_region_candidate = None
    session._space_region_pick_seed_space = None
    session._clear_space_region_pick_overlays()
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
    boundaries = list(boundaries or [])

    space = None
    reported_failure = False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Create Space"))
        base = session._create_space_region_base_object(candidate)
        if not base:
            raise RuntimeError("Unable to create space base")
        space = Arch.makeSpace(base)
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


def activate_space_region_candidate(session, candidate, event_callback=None):
    if session.current_tool != "Pick Space Region" or not isinstance(candidate, dict):
        return False

    boundaries = list(session._space_region_pick_boundaries or [])
    if not boundaries and session._space_region_pick_seed_space is None:
        return False

    space = session._create_space_from_region_candidate(
        candidate,
        boundaries=boundaries,
        keep_boundaries=session._space_region_pick_seed_space is None,
    )
    if not space:
        return False

    session._space_region_pick_boundaries = []
    session._space_region_candidates = []
    session._hovered_space_region_candidate = None
    session._space_region_pick_seed_space = None
    session._clear_space_region_pick_overlays()
    session._register_plan_object(space)
    session._restore_selected_space(space)
    session._claim_left_button_click(event_callback)
    return True


def create_space_from_current_selection(session):
    import Arch
    import ArchSpace

    request = session._get_space_creation_request()
    if not request:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces before using Space.\n",
            )
        )
        return False

    boundaries = list(request["boundaries"] or [])
    region_seed_space = request["region_seed_space"]
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
            label=request["label"],
            seed_space=region_seed_space,
        )
        candidate_count = int(report.get("candidate_count", 0) or 0)
        if candidate_count > 1:
            return session._begin_space_region_pick(
                boundaries,
                label=report.get("label"),
                seed_space=region_seed_space,
                report=report,
            )
        if candidate_count == 1:
            space = session._create_space_from_region_candidate(
                report["candidates"][0],
                boundaries=boundaries,
                keep_boundaries=False,
            )
            if not space:
                return False
            session._register_plan_object(space)
            session._restore_selected_space(space)
            return True
        session._report_space_region_candidate_failure(report)
        return False

    report = ArchSpace.analyzeBoundaryLinks(boundaries)
    if report.get("code") == "multiple_regions":
        region_report = session._get_space_region_candidate_report(
            boundaries,
            label=report.get("label"),
        )
        candidate_count = int(region_report.get("candidate_count", 0) or 0)
        if candidate_count > 1:
            return session._begin_space_region_pick(
                boundaries,
                label=report.get("label"),
                report=region_report,
            )
        if candidate_count == 1:
            space = session._create_space_from_region_candidate(
                region_report["candidates"][0],
                boundaries=boundaries,
                keep_boundaries=True,
            )
            if not space:
                return False
            session._register_plan_object(space)
            session._restore_selected_space(space)
            return True
        session._report_space_region_candidate_failure(region_report)
        return False

    space = None
    reported_failure = False
    try:
        session.doc.openTransaction(translate("BIM_PlanEdit", "Create Space"))
        space = Arch.makeSpace(boundaries)
        if not space:
            raise RuntimeError("Unable to create space")
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
        return False

    session._register_plan_object(space)
    session._restore_selected_space(space)
    return True


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
    space = session._get_selected_plan_target_object("space")
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
    space = session._get_selected_plan_target_object("space")
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
    region = session._get_selected_plan_target_object("region")
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
    region = session._get_selected_plan_target_object("region")
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
    region = session._get_selected_plan_target_object("region")
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
    region = session._get_selected_plan_target_object("region")
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
    space = session._get_selected_plan_target_object("space")
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
    space = session._get_selected_plan_target_object("space")
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
    space = session._get_selected_plan_target_object("space")
    if not session._is_plan_space_object(space):
        return False
    import FreeCADGui

    session.current_tool = "Set Space Text"
    session._edit_space = space
    session._set_hovered_wall(None)
    session._set_hovered_opening(None)
    session._set_hovered_symbol(None)
    session._set_hovered_space(None)
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
    session._queue_focus_plan_view()
    return True


def finish_space_text_position_pick(session, point=None, obj=None):
    del obj
    space = session._edit_space
    session._edit_space = None
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
    space = session._edit_space or session._get_selected_plan_target_object("space")
    session._edit_space = None
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

    targets = list(targets if targets is not None else session._get_selected_plan_targets())
    if not should_run_space_preflight_for_targets(targets):
        return None

    request = session._get_space_creation_request(targets=targets)
    if not request:
        return None

    import ArchSpace

    return ArchSpace.analyzeBoundaryLinks(
        request["boundaries"],
        label=request["label"],
        seed_space=request["region_seed_space"],
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
