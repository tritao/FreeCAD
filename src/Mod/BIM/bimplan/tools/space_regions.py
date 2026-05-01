# SPDX-License-Identifier: LGPL-2.1-or-later

"""Space region candidate and creation flows for BIM Plan Edit."""

import FreeCAD

from bimplan import document_visuals as plan_document_visuals
from bimplan.runtime import tools as plan_runtime_tools
from bimplan.selection import kinds as plan_target_kinds
from bimplan.transactions import PlanEditTransaction
from bimplan.tools import space_boundaries as plan_space_boundaries
from bimplan.tools import space_editing as plan_space_editing
from bimplan.tools import space_geometry as plan_space_geometry

translate = FreeCAD.Qt.translate


def _overlay_runtime_api(session):
    overlays = getattr(session, "overlays", None)
    return getattr(overlays, "runtime", overlays)


class PickSpaceRegionTool(plan_runtime_tools.PlanToolHandler):
    """Interactive picker for existing space/region candidates."""

    tool_id = plan_runtime_tools.PlanTool.PICK_SPACE_REGION

    def on_mouse_move(self, mouse_pos, event_callback):
        del event_callback
        if mouse_pos is None:
            return False
        set_hovered_space_region_candidate(
            self.session,
            self.session.spaces.pick_space_region_candidate(mouse_pos),
            plan_document_visuals.PLAN_VISUAL_SPACE_REGION_PICK,
        )
        self.session.overlays.manager.refresh_plan_overlay_visuals()
        return True

    def on_left_mouse_down(self, mouse_pos, event_callback):
        candidate = self.session.spaces.pick_space_region_candidate(mouse_pos)
        if not candidate:
            return False
        self.session.spaces.activate_space_region_candidate(candidate, event_callback)
        return True

    def on_key(self, key, event_callback, coin):
        del event_callback
        if key != coin.SoKeyboardEvent.ESCAPE:
            return False
        self.session.spaces.cancel_space_region_pick()
        return True


def _space_region_pick_state(session):
    return session.space_region_pick_state


def _selection_targets_api(session):
    return session.selection.targets


def _selection_hover_api(session):
    return session.selection.hover


def _selection_refresh_api(session):
    return session.selection.refresh


def build_space_region_candidate_report(session, boundaries, label=None, seed_space=None):
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
        candidates, skipped_claimed = plan_space_geometry.filter_claimed_space_region_candidates(
            session,
            candidates,
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
    edit_space=None,
    hovered_candidate=None,
):
    state = _space_region_pick_state(session)
    state.boundaries = list(boundaries or [])
    state.candidates = list(candidates or [])
    state.hovered_candidate = hovered_candidate
    state.seed_space = seed_space
    state.edit_space = edit_space


def _get_space_region_pick_candidates(session):
    return list(_space_region_pick_state(session).candidates or ())


def get_space_region_pick_candidates(session):
    return _get_space_region_pick_candidates(session)


def has_space_region_pick_candidates(session):
    return bool(_get_space_region_pick_candidates(session))


def _get_hovered_space_region_candidate(session):
    return _space_region_pick_state(session).hovered_candidate


def get_hovered_space_region_candidate(session):
    return _get_hovered_space_region_candidate(session)


def _set_hovered_space_region_candidate_state(session, candidate):
    _space_region_pick_state(session).hovered_candidate = candidate


def _get_space_region_pick_context(session):
    state = _space_region_pick_state(session)
    return {
        "boundaries": list(state.boundaries or ()),
        "seed_space": state.seed_space,
        "edit_space": state.edit_space,
    }


def reset_space_region_pick_state(session, clear_overlays=True):
    set_space_region_pick_state(session)
    if clear_overlays:
        session.overlays.spaces.clear_space_region_pick_overlays()


def _finish_created_space(session, space, event_callback=None, claim_click=False):
    session.visibility.register_plan_object(space)
    session.spaces.restore_selected_space(space)
    if claim_click:
        session.input.claim_left_button_click(event_callback)
    return True


def _report_space_reassignment_failure(space):
    proxy = getattr(space, "Proxy", None)
    message = _get_proxy_last_boundary_error(proxy, space) if proxy is not None else ""
    if message:
        FreeCAD.Console.PrintError(message + "\n")
        return True
    return False


def _create_space_in_transaction(
    session,
    *,
    create_space,
    boundaries=None,
    keep_boundaries=False,
):
    import ArchSpace

    boundaries = list(boundaries or [])
    space = None
    reported_failure = False
    try:
        with PlanEditTransaction(session.doc, translate("BIM_PlanEdit", "Create Space")):
            space = create_space()
            if not space:
                raise RuntimeError("Unable to create space")
            if keep_boundaries and boundaries:
                ArchSpace.setBoundaryLinks(space, boundaries)
            session.visibility.add_object_to_active_storey(space)
            session.doc.recompute()
            geometry_valid = bool(session.spaces.space_has_valid_geometry(space))
            if not geometry_valid:
                reported_failure = bool(session.spaces.report_space_creation_failure(space))
                raise RuntimeError("Unable to create space")
    except Exception:
        if not reported_failure:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to create the selected space.\n")
            )
        return None
    return space


def _reassign_space_in_transaction(
    session,
    space,
    candidate,
    *,
    boundaries=None,
):
    import ArchSpace

    if space is None or not isinstance(candidate, dict):
        return None
    sample_point = candidate.get("sample_point")
    if sample_point is None:
        return None
    boundaries = list(boundaries or session.spaces.get_space_boundary_entries(space))
    reported_failure = False
    try:
        with PlanEditTransaction(session.doc, translate("BIM_PlanEdit", "Reassign Space Region")):
            if boundaries:
                ArchSpace.setBoundaryLinks(space, boundaries)
            ArchSpace.setBoundaryRegionReferencePoint(space, sample_point)
            space.touch()
            session.doc.recompute()
            geometry_valid = bool(session.spaces.space_has_valid_geometry(space))
            status = str(getattr(space, "BoundaryStatus", "") or "").strip()
            if not geometry_valid or status == "Conflict":
                reported_failure = _report_space_reassignment_failure(space)
                raise RuntimeError("Unable to reassign space region")
    except Exception:
        if not reported_failure:
            FreeCAD.Console.PrintError(
                translate("BIM_PlanEdit", "Failed to reassign the selected space.\n")
            )
        return None
    return space


def _create_and_finish_space_region_candidate(
    session,
    candidate,
    *,
    boundaries,
    keep_boundaries,
    edit_space=None,
    event_callback=None,
    claim_click=False,
    clear_region_pick_state=False,
):
    if edit_space is not None:
        space = session.spaces.reassign_space_from_region_candidate(
            edit_space,
            candidate,
            boundaries=boundaries,
        )
    else:
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


def _start_space_region_pick_mode(
    session,
    boundaries,
    candidates,
    seed_space=None,
    edit_space=None,
):
    session.current_tool = "Pick Space Region"
    set_space_region_pick_state(
        session,
        boundaries=boundaries,
        candidates=candidates,
        seed_space=seed_space,
        edit_space=edit_space,
    )
    session.overlays.walls.clear_wall_grips()
    _selection_hover_api(session).clear_hovered_plan_targets(
        kinds=plan_target_kinds.SPACE_EDIT_CLEAR_HOVERED_KINDS
    )
    _selection_refresh_api(session).refresh_primary_selected_plan_target()
    if edit_space is not None:
        FreeCAD.Console.PrintMessage(
            translate(
                "BIM_PlanEdit",
                "Multiple enclosed regions found. Hover a dashed region and click to reassign the selected space.\n",
            )
        )
    else:
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
    edit_space=None,
):
    candidates = list(report.get("candidates", []) or [])
    if len(candidates) != 1:
        return None
    return _create_and_finish_space_region_candidate(
        session,
        candidates[0],
        boundaries=boundaries,
        keep_boundaries=keep_boundaries,
        edit_space=edit_space,
    )


def _consume_space_region_candidate_report(
    session,
    boundaries,
    report,
    *,
    seed_space=None,
    edit_space=None,
    keep_boundaries=True,
    announce_skipped_claimed=False,
):
    candidates = list(report.get("candidates", []) or [])
    if not candidates:
        report_space_region_candidate_failure(report)
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
        edit_space=edit_space,
    )
    if created is not None:
        return created

    return _start_space_region_pick_mode(
        session,
        boundaries,
        candidates,
        seed_space=seed_space,
        edit_space=edit_space,
    )


def get_space_region_candidate_polylines(session, candidate):
    face = candidate.get("face") if isinstance(candidate, dict) else None
    if not face:
        return []
    return session.overlays.geometry.get_footprint_overlay_polylines([face])


def get_space_region_candidate_segments(session, candidate):
    segments = []
    for polyline in get_space_region_candidate_polylines(session, candidate):
        if len(polyline) < 2:
            continue
        for start, end in zip(polyline, polyline[1:]):
            segments.append((start, end))
    return segments


def pick_space_region_candidate(session, mouse_pos, radius_px=10):
    candidates = _get_space_region_pick_candidates(session)
    if session.current_tool != "Pick Space Region" or not candidates:
        return None

    radius_sq = float(radius_px) * float(radius_px)
    if session.view:
        best_candidate = None
        best_distance_sq = None
        for candidate in candidates:
            sample_point = candidate.get("sample_point") if isinstance(candidate, dict) else None
            if sample_point is None:
                continue
            try:
                screen_point = session.view.getPointOnScreen(sample_point)
            except Exception:
                continue
            dx = float(screen_point[0]) - float(mouse_pos[0])
            dy = float(screen_point[1]) - float(mouse_pos[1])
            distance_sq = dx * dx + dy * dy
            if distance_sq > radius_sq:
                continue
            if best_distance_sq is None or distance_sq < best_distance_sq:
                best_candidate = candidate
                best_distance_sq = distance_sq
        if best_candidate is not None:
            return best_candidate

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

    best_candidate = None
    best_distance_sq = None
    for candidate in candidates:
        for start, end in get_space_region_candidate_segments(session, candidate):
            distance_sq = session.picking.get_screen_distance_sq_to_segment(mouse_pos, start, end)
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
    _overlay_runtime_api(session).queue_plan_overlay_visual_refresh(visual_key)
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
        shape_copy = plan_space_geometry.copy_shape_without_element_map(shape)
        if shape_copy is None:
            return None
        base.Shape = shape_copy
    except Exception:
        return None

    view_object = getattr(base, "ViewObject", None)
    _set_view_object_region_base_state(view_object)
    return base


def _set_view_object_region_base_state(view_object):
    if view_object is None:
        return
    for property_name, value in (
        ("Visibility", False),
        ("ShowInTree", False),
        ("Selectable", False),
    ):
        if getattr(view_object, property_name, None) is None:
            continue
        try:
            setattr(view_object, property_name, value)
        except Exception:
            pass


def _get_proxy_last_boundary_error(proxy, space):
    getter = getattr(proxy, "getLastBoundaryError", None)
    if not callable(getter):
        return ""
    try:
        return str(getter(space) or "").strip()
    except Exception:
        return ""


def start_space_region_pick(session, boundaries, label=None, seed_space=None, report=None):
    if report is None:
        report = build_space_region_candidate_report(
            session,
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


def start_space_region_reassignment(session, space, boundaries=None, label=None, report=None):
    if space is None:
        return False
    if boundaries is None:
        boundaries = session.spaces.get_space_boundary_entries(space)
    boundaries = list(boundaries or [])
    if not boundaries:
        return False
    if report is None:
        report = build_space_region_candidate_report(
            session,
            boundaries,
            label=label or getattr(space, "Label", None),
            seed_space=space,
        )
    return _consume_space_region_candidate_report(
        session,
        boundaries,
        report,
        seed_space=space,
        edit_space=space,
        keep_boundaries=True,
    )


def cancel_space_region_pick(session, refresh=True):
    was_active = session.current_tool == "Pick Space Region" or bool(
        _space_region_pick_state(session).candidates
    )
    reset_space_region_pick_state(session)
    if session.current_tool == "Pick Space Region":
        session.current_tool = "Select"
    if was_active:
        _selection_refresh_api(session).refresh_primary_selected_plan_target()
    elif refresh:
        session.task_panels.refresh_task_panel_status()
    return was_active


def create_space_from_region_candidate(session, candidate, boundaries=None, keep_boundaries=True):
    import Arch
    import ArchSpace

    if not isinstance(candidate, dict):
        return None

    def create_space():
        base = create_space_region_base_object(session, candidate)
        if not base:
            return None
        space = Arch.makeSpace(base)
        sample_point = candidate.get("sample_point")
        if space is not None and sample_point is not None:
            ArchSpace.setBoundaryRegionReferencePoint(space, sample_point)
        return space

    return _create_space_in_transaction(
        session,
        create_space=create_space,
        boundaries=boundaries,
        keep_boundaries=keep_boundaries,
    )


def reassign_space_from_region_candidate(session, space, candidate, boundaries=None):
    return _reassign_space_in_transaction(
        session,
        space,
        candidate,
        boundaries=boundaries,
    )


def activate_space_region_candidate(session, candidate, event_callback=None):
    if session.current_tool != "Pick Space Region" or not isinstance(candidate, dict):
        return False

    pick_context = _get_space_region_pick_context(session)
    boundaries = pick_context["boundaries"]
    seed_space = pick_context["seed_space"]
    edit_space = pick_context["edit_space"]
    if not boundaries and seed_space is None and edit_space is None:
        return False

    return _create_and_finish_space_region_candidate(
        session,
        candidate,
        boundaries=boundaries,
        keep_boundaries=seed_space is None,
        edit_space=edit_space,
        event_callback=event_callback,
        claim_click=True,
        clear_region_pick_state=True,
    )


def create_space_from_current_selection(session):
    import Arch
    import ArchSpace

    request = plan_space_boundaries.build_space_creation_request(session)
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
        report = build_space_region_candidate_report(
            session,
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
        region_report = build_space_region_candidate_report(
            session,
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
    if not _selection_targets_api(session).is_plan_space_object(space):
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

    message = _get_proxy_last_boundary_error(proxy, space)

    if not message:
        return False

    FreeCAD.Console.PrintWarning(
        translate(
            "BIM_PlanEdit",
            "Plan Edit kept no new space object because the selection could not be turned into a valid Arch Space.\n",
        )
    )
    return True
