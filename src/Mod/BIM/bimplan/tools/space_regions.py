# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space region candidate and creation flows for BIM Plan Edit."""

import FreeCAD

from bimplan import selection as plan_selection
from bimplan.selection import target_kinds as plan_target_kinds

translate = FreeCAD.Qt.translate


def get_space_region_candidate_report(session, boundaries, label=None, seed_space=None):
    import ArchSpace

    report = ArchSpace.getBoundaryRegionCandidates(
        boundaries,
        label=label,
        seed_space=seed_space,
    )
    return _normalize_space_region_candidate_report(
        session,
        report,
        seed_space=seed_space,
    )


def _normalize_space_region_candidate_report(session, report, *, seed_space=None):
    report = dict(report or {})
    candidates = list(report.get("candidates", []) or [])
    skipped_claimed = 0
    if seed_space is None:
        candidates, skipped_claimed = session.spaces.filter_claimed_space_region_candidates(
            candidates
        )
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
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        state.space_region_candidates = list(candidates or [])
        state.hovered_space_region_candidate = hovered_candidate
    else:
        session._space_region_candidates = list(candidates or [])
        session._hovered_space_region_candidate = hovered_candidate
    session._space_region_pick_seed_space = seed_space


def _get_space_region_pick_candidates(session):
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        return list(getattr(state, "space_region_candidates", ()) or ())
    return list(getattr(session, "_space_region_candidates", ()) or ())


def _get_hovered_space_region_candidate(session):
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        return getattr(state, "hovered_space_region_candidate", None)
    return getattr(session, "_hovered_space_region_candidate", None)


def _set_hovered_space_region_candidate_state(session, candidate):
    state = getattr(session, "task_panel_state", None)
    if state is not None:
        state.hovered_space_region_candidate = candidate
    else:
        session._hovered_space_region_candidate = candidate


def _get_space_region_pick_context(session):
    return {
        "boundaries": list(getattr(session, "_space_region_pick_boundaries", ()) or ()),
        "seed_space": getattr(session, "_space_region_pick_seed_space", None),
    }


def reset_space_region_pick_state(session, clear_overlays=True):
    set_space_region_pick_state(session)
    if clear_overlays:
        session.overlays.clear_space_region_pick_overlays()


def _finish_created_space(session, space, event_callback=None, claim_click=False):
    session.visibility.register_plan_object(space)
    session.spaces.restore_selected_space(space)
    if claim_click:
        session.input.claim_left_button_click(event_callback)
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
        session.visibility.add_object_to_active_storey(space)
        session.doc.recompute()
        if not session.spaces.space_has_valid_geometry(space):
            reported_failure = session.spaces.report_space_creation_failure(space)
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
    space = session.spaces.create_space_from_region_candidate(
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
    session.overlays.clear_wall_grips()
    session.selection.clear_hovered_plan_targets(
        kinds=plan_target_kinds.SPACE_EDIT_CLEAR_HOVERED_KINDS
    )
    session.selection.refresh_primary_selected_plan_target()
    FreeCAD.Console.PrintMessage(
        translate(
            "BIM_PlanEdit",
            "Multiple enclosed regions found. Hover a dashed region and click to create that space.\n",
        )
    )
    return True


def _announce_skipped_claimed_space_region_candidates(report, *, enabled):
    skipped_claimed = int(report.get("skipped_claimed_candidate_count", 0) or 0)
    if not enabled or not skipped_claimed:
        return
    FreeCAD.Console.PrintMessage(
        translate(
            "BIM_PlanEdit",
            "Ignoring {count} enclosed region(s) already covered by existing spaces.\n",
        ).format(count=skipped_claimed)
    )


def _create_space_from_single_region_candidate(
    session,
    boundaries,
    report,
    *,
    keep_boundaries,
):
    candidates = list(report.get("candidates", []) or [])
    if len(candidates) != 1:
        return None
    return _create_and_finish_space_region_candidate(
        session,
        candidates[0],
        boundaries=boundaries,
        keep_boundaries=keep_boundaries,
    )


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
        session.spaces.report_space_region_candidate_failure(report)
        return False

    _announce_skipped_claimed_space_region_candidates(
        report,
        enabled=announce_skipped_claimed,
    )

    created = _create_space_from_single_region_candidate(
        session,
        boundaries,
        report,
        keep_boundaries=keep_boundaries,
    )
    if created is not None:
        return created

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
    return session.overlays.get_footprint_overlay_polylines([face])


def get_space_region_candidate_segments(session, candidate):
    segments = []
    for polyline in session.spaces.get_space_region_candidate_polylines(candidate):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            segments.append((start, end))
    return segments


def pick_space_region_candidate(session, mouse_pos, radius_px=10):
    candidates = _get_space_region_pick_candidates(session)
    if session.current_tool != "Pick Space Region" or not candidates:
        return None

    point = session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
    if point is not None:
        for candidate in candidates:
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
    for candidate in candidates:
        for start, end in session.spaces.get_space_region_candidate_segments(candidate):
            distance_sq = session.selection.get_screen_distance_sq_to_segment(mouse_pos, start, end)
            if distance_sq is None or distance_sq > radius_sq:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_candidate = candidate
                best_distance_sq = distance_sq
    return best_candidate


def set_hovered_space_region_candidate(session, candidate, visual_key):
    current_candidate = _get_hovered_space_region_candidate(session)
    if current_candidate is candidate:
        return
    _set_hovered_space_region_candidate_state(session, candidate)
    session.overlays.queue_plan_overlay_visual_refresh(visual_key)
    session.task_panels.refresh_task_panel_status()


def create_space_region_base_object(session, candidate):
    shape = candidate.get("shape") if isinstance(candidate, dict) else None
    if not shape:
        return None
    try:
        base = session.doc.addObject("Part::Feature", "SpaceRegionBase")
    except Exception:
        return None
    try:
        shape_copy = session.spaces.copy_shape_without_element_map(shape)
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
        report = session.spaces.get_space_region_candidate_report(
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
        session.selection.refresh_primary_selected_plan_target()
    elif refresh:
        session.task_panels.refresh_task_panel_status()
    return was_active


def create_space_from_region_candidate(session, candidate, boundaries=None, keep_boundaries=True):
    import Arch

    if not isinstance(candidate, dict):
        return None

    def create_space():
        base = session.spaces.create_space_region_base_object(candidate)
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

    pick_context = _get_space_region_pick_context(session)
    boundaries = pick_context["boundaries"]
    seed_space = pick_context["seed_space"]
    if not boundaries and seed_space is None:
        return False

    return _create_and_finish_space_region_candidate(
        session,
        candidate,
        boundaries=boundaries,
        keep_boundaries=seed_space is None,
        event_callback=event_callback,
        claim_click=True,
        clear_region_pick_state=True,
    )


def create_space_from_current_selection(session):
    import Arch
    import ArchSpace

    request = session.spaces.get_space_creation_request()
    if not request:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces before using Space.\n",
            )
        )
        return False

    boundaries = list(request.get("boundaries", []) or [])
    region_seed_space = request.get("region_seed_space")
    if not boundaries:
        FreeCAD.Console.PrintWarning(
            translate(
                "BIM_PlanEdit",
                "Select room-bounding walls or explicit boundary faces before using Space.\n",
            )
        )
        return False

    if region_seed_space is not None:
        report = session.spaces.get_space_region_candidate_report(
            boundaries,
            label=request.get("label"),
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
        region_report = session.spaces.get_space_region_candidate_report(
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
    if not session.selection.is_plan_space_object(space):
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
