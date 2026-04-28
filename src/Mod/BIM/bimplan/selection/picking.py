# SPDX-License-Identifier: LGPL-2.1-or-later

"""Pointer picking helpers for BIM Plan Edit."""

from dataclasses import dataclass, field

import FreeCAD
from bimplan.selection import edit_nodes as plan_edit_nodes
from bimplan.selection import hover_picking as plan_hover_picking
from bimplan.selection import overlay_picking as plan_overlay_picking
from bimplan.selection import picking_debug as plan_picking_debug
from bimplan.selection import picking_geometry as plan_picking_geometry
from bimplan.selection import provider_overlay_picking as plan_provider_overlay_picking
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan import selection as plan_selection
from bimplan.selection import targets as plan_targets

_PROVIDER_OVERLAY_PICK_RADIUS_PX = plan_provider_overlay_picking.PROVIDER_OVERLAY_PICK_RADIUS_PX

_append_pick_debug_item = plan_picking_debug.append_pick_debug_item
_describe_pick_info_entry = plan_picking_debug.describe_pick_info_entry
_describe_pick_object = plan_picking_debug.describe_pick_object
_describe_pick_target = plan_picking_debug.describe_pick_target
_emit_pick_debug = plan_picking_debug.emit_pick_debug


@dataclass
class _PickStageCandidates:
    wall: object = field(default_factory=plan_target_kinds.make_plan_target_ref)
    symbol: object = field(default_factory=plan_target_kinds.make_plan_target_ref)
    provider: object = field(default_factory=plan_target_kinds.make_plan_target_ref)
    region: object = field(default_factory=plan_target_kinds.make_plan_target_ref)
    space: object = field(default_factory=plan_target_kinds.make_plan_target_ref)

    def store_if_empty(self, kind, obj):
        current = getattr(self, kind)
        if current.obj is None and obj is not None:
            setattr(self, kind, plan_target_kinds.make_plan_target_ref(kind, obj))

    def as_debug_dict(self, session):
        return {
            "symbol": _describe_pick_target(session, self.symbol.kind, self.symbol.obj),
            "provider": _describe_pick_target(session, self.provider.kind, self.provider.obj),
            "wall": _describe_pick_target(session, self.wall.kind, self.wall.obj),
            "region": _describe_pick_target(session, self.region.kind, self.region.obj),
            "space": _describe_pick_target(session, self.space.kind, self.space.obj),
        }


@dataclass(frozen=True)
class _ObjectsInfoPickStageResult:
    direct_result: object
    candidates: _PickStageCandidates
    debug_infos: tuple


@dataclass(frozen=True)
class _PickResolutionResult:
    target_ref: object
    stage: str = ""


def _get_plan_provider_overlay_pick_mode(session):
    return plan_provider_overlay_picking.get_plan_provider_overlay_pick_mode(session)


def _should_prioritize_provider_targets_for_mode(session):
    return plan_provider_overlay_picking.should_prioritize_provider_targets_for_mode(session)


def _is_pick_visible_view_object(view_object):
    return not (view_object and getattr(view_object, "Visibility", True) is False)


def _get_region_local_points(region):
    proxy = getattr(region, "Proxy", None)
    get_local_points = getattr(proxy, "_get_local_points", None)
    if callable(get_local_points):
        try:
            return list(get_local_points(region) or [])
        except Exception:
            return []
    points = getattr(region, "Points", None)
    if points is None:
        return []
    return [FreeCAD.Vector(point) for point in (points or [])]


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_set_fields(session, **fields):
    return session.performance.plan_perf_set_fields(**fields)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _get_cached_plan_instances(session, cache_field, is_target, count_name, span_name):
    if not session.doc:
        return ()
    doc_name = getattr(session.doc, "Name", None)
    cache_record = getattr(session.overlay_cache_state, cache_field, None)
    if cache_record is not None and cache_record[0] == doc_name:
        _perf_count(session, f"{cache_field}_hits")
        return cache_record[1]

    instances = []
    with _perf_trace_span(session, span_name):
        for obj in getattr(session.doc, "Objects", []) or []:
            _perf_count(session, count_name)
            if is_target(obj):
                instances.append(obj)
    result = tuple(instances)
    setattr(session.overlay_cache_state, cache_field, (doc_name, result))
    return result


def get_plan_space_instances(session):
    return _get_cached_plan_instances(
        session,
        "plan_space_instances_cache",
        lambda obj: plan_targets.is_plan_space_object(session, obj),
        "plan_space_instance_objects_scanned",
        "build_plan_space_instances_cache",
    )


def get_plan_region_instances(session):
    return _get_cached_plan_instances(
        session,
        "plan_region_instances_cache",
        lambda obj: plan_targets.is_plan_region_object(session, obj),
        "plan_region_instance_objects_scanned",
        "build_plan_region_instances_cache",
    )


def get_screen_distance_sq_to_segment(session, mouse_pos, start, end):
    return plan_picking_geometry.get_screen_distance_sq_to_segment(
        session,
        mouse_pos,
        start,
        end,
    )


def get_screen_distance_sq_to_projected_segment(cursor_xy, start_xy, end_xy):
    return plan_picking_geometry.get_screen_distance_sq_to_projected_segment(
        cursor_xy,
        start_xy,
        end_xy,
    )


def should_skip_opening_by_plan_bounds(session, opening, plan_point, radius_px):
    return plan_overlay_picking.should_skip_opening_by_plan_bounds(
        session, opening, plan_point, radius_px
    )


def _is_pick_visible_object(obj):
    view_object = getattr(obj, "ViewObject", None)
    return _is_pick_visible_view_object(view_object)


def _iter_pick_objects(objects, *, unique_names=False):
    seen = set()
    for obj in objects or []:
        if unique_names:
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
        if not _is_pick_visible_object(obj):
            continue
        yield obj


def _pick_best_target_from_overlay_segments(session, objects, get_segments, mouse_pos, radius_px):
    return plan_overlay_picking.pick_best_target_from_overlay_segments(
        session, objects, get_segments, mouse_pos, radius_px
    )


def pick_plan_symbol_target_from_overlays(session, mouse_pos, radius_px=10):
    return plan_overlay_picking.pick_plan_symbol_target_from_overlays(
        session, mouse_pos, radius_px=radius_px
    )


def pick_plan_opening_target_from_overlays(session, mouse_pos, radius_px=10, candidates=None):
    return plan_overlay_picking.pick_plan_opening_target_from_overlays(
        session, mouse_pos, radius_px=radius_px, candidates=candidates
    )


def pick_provider_overlay_target_from_overlays(
    session,
    mouse_pos,
    radius_px=_PROVIDER_OVERLAY_PICK_RADIUS_PX,
):
    return plan_provider_overlay_picking.pick_provider_overlay_target_from_overlays(
        session,
        mouse_pos,
        radius_px=radius_px,
    )


def pick_provider_overlay_target_from_objects_info(session, mouse_pos):
    return plan_provider_overlay_picking.pick_provider_overlay_target_from_objects_info(
        session,
        mouse_pos,
    )


def pick_plan_space_target_from_overlays(session, mouse_pos, radius_px=10):
    if not session.doc or not session.view or not mouse_pos:
        return None
    return _pick_best_target_from_overlay_segments(
        session,
        (
            obj
            for obj in _iter_pick_objects(
                get_plan_space_instances(session),
                unique_names=True,
            )
            if plan_targets.is_plan_space_object(session, obj)
        ),
        session.overlays.geometry.get_space_overlay_segments,
        mouse_pos,
        radius_px,
    )


def pick_plan_region_target_from_overlays(session, mouse_pos, radius_px=10):
    if not session.doc or not session.view or not mouse_pos:
        return None
    return _pick_best_target_from_overlay_segments(
        session,
        (
            obj
            for obj in _iter_pick_objects(
                get_plan_region_instances(session),
                unique_names=True,
            )
            if plan_targets.is_plan_region_object(session, obj)
        ),
        session.overlays.geometry.get_region_overlay_segments,
        mouse_pos,
        radius_px,
    )


def get_region_pick_polylines(session, region):
    if not plan_targets.is_plan_region_object(session, region):
        return []

    polylines = session.overlays.geometry.get_region_overlay_polylines(region)
    if polylines:
        return polylines

    points = _get_region_local_points(region)

    if len(points) < 3:
        return []

    placement = getattr(region, "Placement", None)
    if placement is not None:
        try:
            points = [placement.multVec(FreeCAD.Vector(point)) for point in points]
        except Exception:
            points = [FreeCAD.Vector(point) for point in points]
    return [points + [points[0]]]


def xy_polygon_area(polyline):
    if not polyline or len(polyline) < 4:
        return 0.0
    area = 0.0
    for start, end in zip(polyline, polyline[1:]):
        area += float(start.x) * float(end.y) - float(end.x) * float(start.y)
    return abs(area) * 0.5


def xy_point_in_polygon(point, polyline, tolerance=1e-9):
    if not point or not polyline or len(polyline) < 4:
        return False

    px = float(point.x)
    py = float(point.y)
    inside = False
    points = polyline
    if points[0].distanceToPoint(points[-1]) > tolerance:
        points = list(points) + [points[0]]

    for start, end in zip(points, points[1:]):
        x1 = float(start.x)
        y1 = float(start.y)
        x2 = float(end.x)
        y2 = float(end.y)
        if abs(y2 - y1) <= tolerance:
            continue
        intersects = (y1 > py) != (y2 > py)
        if not intersects:
            continue
        x_cross = x1 + ((py - y1) * (x2 - x1) / (y2 - y1))
        if x_cross >= px - tolerance:
            inside = not inside
    return inside


def pick_plan_region_target_from_polylines(session, mouse_pos):
    with _perf_trace_span(session, "pick_region_target_from_polylines", mouse_pos=mouse_pos):
        if not session.doc or not mouse_pos:
            return None

        point = session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
        if point is None:
            return None

        best_region = None
        best_area = None
        seen = set()
        for obj in get_plan_region_instances(session):
            _perf_count(session, "region_polyline_pick_objects_scanned")
            if not plan_targets.is_plan_region_object(session, obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if not _is_pick_visible_view_object(view_object):
                continue

            containing_area = None
            for polyline in get_region_pick_polylines(session, obj):
                if not xy_point_in_polygon(point, polyline):
                    continue
                area = xy_polygon_area(polyline)
                if area <= 0.0:
                    continue
                if containing_area is None or area < containing_area:
                    containing_area = area

            if containing_area is None:
                continue
            if best_area is None or containing_area < best_area:
                best_region = obj
                best_area = containing_area

        return best_region


def pick_plan_target_from_footprint_faces(
    session, mouse_pos, is_target, get_faces, target_label="target"
):
    span_name = f"pick_{target_label}_target_from_footprints"
    with _perf_trace_span(session, span_name, mouse_pos=mouse_pos):
        if not session.doc or not mouse_pos:
            return None

        point = session.viewport.get_plan_point_from_mouse_pos(mouse_pos)
        if point is None:
            return None

        best_target = None
        best_area = None
        seen = set()
        objects = getattr(session.doc, "Objects", []) or []
        if target_label == "space":
            objects = get_plan_space_instances(session)
        elif target_label == "region":
            objects = get_plan_region_instances(session)

        for obj in objects or []:
            _perf_count(session, f"{target_label}_objects_scanned")
            if not is_target(obj):
                continue
            name = getattr(obj, "Name", None)
            if not name or name in seen:
                continue
            seen.add(name)
            view_object = getattr(obj, "ViewObject", None)
            if not _is_pick_visible_view_object(view_object):
                continue
            _perf_count(session, f"{target_label}_visible_candidates")

            containing_area = None
            faces = list(get_faces(obj) or [])
            _perf_count(session, f"{target_label}_footprint_faces_returned", len(faces))
            for face in faces:
                _perf_count(session, f"{target_label}_footprint_faces_tested")
                bound_box = getattr(face, "BoundBox", None)
                if bound_box is None:
                    continue
                test_point = FreeCAD.Vector(point.x, point.y, float(bound_box.ZMin))
                try:
                    if not face.isInside(test_point, 0.001, True):
                        continue
                except Exception:
                    continue
                area = float(getattr(face, "Area", 0.0) or 0.0)
                if containing_area is None or area < containing_area:
                    containing_area = area

            if containing_area is None:
                continue
            _perf_count(session, f"{target_label}_containing_candidates")
            if best_area is None or containing_area < best_area:
                best_target = obj
                best_area = containing_area

        _perf_set_fields(
            session,
            **{f"{target_label}_pick_result": _describe_pick_object(session, best_target)},
        )
        return best_target


def pick_plan_space_target_from_footprints(session, mouse_pos):
    return pick_plan_target_from_footprint_faces(
        session,
        mouse_pos,
        lambda obj: plan_targets.is_plan_space_object(session, obj),
        session.overlays.geometry.get_space_footprint_faces,
        target_label="space",
    )


def pick_plan_region_target_from_footprints(session, mouse_pos):
    return pick_plan_target_from_footprint_faces(
        session,
        mouse_pos,
        lambda obj: plan_targets.is_plan_region_object(session, obj),
        session.overlays.geometry.get_region_footprint_faces,
        target_label="region",
    )


def _get_view_objects_info(session, mouse_pos):
    try:
        with _perf_trace_span(session, "view_get_objects_info"):
            infos = session.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
    except (AttributeError, ReferenceError, RuntimeError):
        return []
    return list(infos or [])


def _collect_pick_candidates_from_objects_info(session, infos):
    candidates = _PickStageCandidates()
    debug_infos = []
    direct_result = plan_target_kinds.make_plan_target_ref()
    for info in infos:
        _perf_count(session, "objects_info_scanned")
        if not info:
            continue
        doc_name = info.get("Document")
        obj_name = info.get("Object")
        if not doc_name or not obj_name:
            continue
        obj = plan_provider_overlay_picking.resolve_document_object(session, doc_name, obj_name)
        if obj is None:
            continue
        parent_obj = info.get("ParentObject")
        target_ref = plan_target_kinds.coerce_plan_target_ref(
            plan_targets.get_plan_pick_target_for_object(
                session,
                obj,
                parent_obj=parent_obj,
            )
        )
        _append_pick_debug_item(
            debug_infos,
            {
                "info": _describe_pick_info_entry(info),
                "resolved_object": _describe_pick_object(session, obj),
                "target": _describe_pick_target(session, target_ref.kind, target_ref.obj),
            },
        )
        if target_ref.kind == "opening":
            direct_result = plan_target_kinds.make_plan_target_ref("opening", target_ref.obj)
            break
        if target_ref.kind in ("wall", "symbol", "provider", "region", "space"):
            candidates.store_if_empty(target_ref.kind, target_ref.obj)
    return _ObjectsInfoPickStageResult(
        direct_result=direct_result,
        candidates=candidates,
        debug_infos=tuple(debug_infos),
    )


def _resolve_overlay_priority_target(session, mouse_pos, candidates, prioritize_provider_targets):
    result = _resolve_provider_overlay_priority_target(
        session,
        mouse_pos,
        candidates,
        prioritize_provider_targets,
    )
    if result.target_ref.kind is not None:
        return result
    return _resolve_structural_overlay_priority_target(session, mouse_pos, candidates)


def _resolve_provider_overlay_priority_target(
    session,
    mouse_pos,
    candidates,
    prioritize_provider_targets,
):
    if candidates.provider.obj is None:
        provider_overlay_target = pick_provider_overlay_target_from_overlays(
            session,
            mouse_pos,
            radius_px=_PROVIDER_OVERLAY_PICK_RADIUS_PX,
        )
        if provider_overlay_target.kind == "provider" and provider_overlay_target.obj is not None:
            candidates.provider = provider_overlay_target
    if prioritize_provider_targets and candidates.provider.obj is not None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("provider", candidates.provider.obj),
            stage="provider_overlay_priority",
        )
    return _PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def _resolve_structural_overlay_priority_target(session, mouse_pos, candidates):
    if candidates.symbol.obj is not None and candidates.wall.obj is None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("symbol", candidates.symbol.obj),
            stage="symbol_priority_without_wall",
        )

    result = _resolve_opening_overlay_priority_target(session, mouse_pos, candidates)
    if result.target_ref.kind is not None:
        return result
    return _resolve_symbol_or_terminal_overlay_target(session, mouse_pos, candidates)


def _resolve_opening_overlay_priority_target(session, mouse_pos, candidates):
    opening_candidates = None
    if candidates.wall.obj is not None:
        opening_candidates = session.openings.get_wall_hosted_openings(candidates.wall.obj)
    opening_candidate = pick_plan_opening_target_from_overlays(
        session,
        mouse_pos,
        candidates=opening_candidates,
    )
    if opening_candidate is None and opening_candidates is not None:
        opening_candidate = pick_plan_opening_target_from_overlays(session, mouse_pos)
    if opening_candidate is not None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("opening", opening_candidate),
            stage="opening_overlay_priority",
        )
    return _PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def _resolve_symbol_or_terminal_overlay_target(session, mouse_pos, candidates):
    if candidates.symbol.obj is None:
        symbol_candidate = pick_plan_symbol_target_from_overlays(session, mouse_pos)
        candidates.store_if_empty("symbol", symbol_candidate)
    if candidates.symbol.obj is not None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("symbol", candidates.symbol.obj),
            stage="symbol_overlay_or_direct",
        )
    if candidates.wall.obj is not None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("wall", candidates.wall.obj),
            stage="wall_terminal",
        )
    if candidates.provider.obj is not None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("provider", candidates.provider.obj),
            stage="provider_terminal",
        )
    return _PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def _resolve_region_or_space_fallback_target(
    session,
    mouse_pos,
    candidates,
    *,
    include_space_fallback,
):
    result = _resolve_region_fallback_target(session, mouse_pos, candidates)
    if result.target_ref.kind is not None:
        return result
    return _resolve_space_fallback_target(
        session,
        mouse_pos,
        candidates,
        include_space_fallback=include_space_fallback,
    )


def _resolve_region_fallback_target(session, mouse_pos, candidates):
    if candidates.region.obj is None:
        region_candidate = pick_plan_region_target_from_polylines(session, mouse_pos)
        candidates.store_if_empty("region", region_candidate)
    if candidates.region.obj is None:
        region_candidate = pick_plan_region_target_from_footprints(session, mouse_pos)
        candidates.store_if_empty("region", region_candidate)
    if candidates.region.obj is None:
        region_candidate = pick_plan_region_target_from_overlays(session, mouse_pos)
        candidates.store_if_empty("region", region_candidate)
    if candidates.region.obj is not None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("region", candidates.region.obj),
            stage="region_fallback",
        )
    return _PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def _resolve_space_fallback_target(
    session,
    mouse_pos,
    candidates,
    *,
    include_space_fallback,
):
    if not include_space_fallback:
        return _PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())
    if candidates.space.obj is None:
        space_candidate = pick_plan_space_target_from_footprints(session, mouse_pos)
        candidates.store_if_empty("space", space_candidate)
    if candidates.space.obj is None:
        space_candidate = pick_plan_space_target_from_overlays(session, mouse_pos)
        candidates.store_if_empty("space", space_candidate)
    if candidates.space.obj is not None:
        return _PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("space", candidates.space.obj),
            stage="space_fallback",
        )
    return _PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def get_plan_target_at_position(session, mouse_pos, *, include_space_fallback=True):
    with _perf_trace_span(session, "get_plan_target_at_position", mouse_pos=mouse_pos):
        if not session.view or not mouse_pos:
            return plan_target_kinds.make_plan_target_ref()
        prioritize_provider_targets = _should_prioritize_provider_targets_for_mode(session)
        infos = _get_view_objects_info(session, mouse_pos)
        _perf_count(session, "objects_info_entries", len(infos))

        stage_result = _collect_pick_candidates_from_objects_info(session, infos)
        result = stage_result.direct_result
        candidates = stage_result.candidates
        debug_infos = list(stage_result.debug_infos)
        resolution_stage = "objects_info_direct" if result.kind is not None else ""
        if result.kind is None:
            resolution = _resolve_pick_target_from_overlay_stages(
                session,
                mouse_pos,
                candidates,
                prioritize_provider_targets=prioritize_provider_targets,
                include_space_fallback=include_space_fallback,
            )
            result = resolution.target_ref
            resolution_stage = resolution.stage
        _perf_set_fields(
            session,
            picked_target=_describe_pick_target(session, result.kind, result.obj),
        )
        _emit_pick_debug(
            session,
            "get_plan_target_at_position",
            mouse_pos=mouse_pos,
            overlay_mode=_get_plan_provider_overlay_pick_mode(session),
            prioritize_provider_targets=prioritize_provider_targets,
            include_space_fallback=bool(include_space_fallback),
            objects_info=debug_infos,
            candidates=candidates.as_debug_dict(session),
            resolution_stage=resolution_stage,
            result=_describe_pick_target(session, result.kind, result.obj),
        )
        return plan_target_kinds.coerce_plan_target_ref(result)


def _resolve_pick_target_from_overlay_stages(
    session,
    mouse_pos,
    candidates,
    *,
    prioritize_provider_targets,
    include_space_fallback,
):
    result = _resolve_overlay_priority_target(
        session,
        mouse_pos,
        candidates,
        prioritize_provider_targets,
    )
    if result.target_ref.kind is not None:
        return result
    return _resolve_region_or_space_fallback_target(
        session,
        mouse_pos,
        candidates,
        include_space_fallback=include_space_fallback,
    )


def get_plan_target_from_edit_node(session, node):
    if not node:
        return plan_target_kinds.make_plan_target_ref()
    node_kind = plan_edit_nodes.get_edit_node_kind(node)
    if node_kind in ("provider_overlay_point", "provider_overlay_target"):
        target_ref = get_provider_overlay_target_from_edit_node(session, node)
        if plan_selection.is_valid_plan_target(session, target_ref.kind, target_ref.obj):
            return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)
        fallback_target_ref = plan_target_kinds.coerce_plan_target_ref(
            plan_targets.get_plan_target_for_object(session, target_ref.obj)
        )
        return plan_target_kinds.make_plan_target_ref(
            fallback_target_ref.kind, fallback_target_ref.obj
        )
    if node_kind == "opening_handle":
        opening, _index = plan_edit_nodes.get_edit_node_payload(node)
        if session.openings.is_hosted_opening_object(opening):
            return plan_target_kinds.make_plan_target_ref("opening", opening)
        return plan_target_kinds.make_plan_target_ref()
    if node_kind == "symbol_handle":
        symbol, _role = plan_edit_nodes.get_edit_node_payload(node)
        if session.visibility.is_plan_symbol_instance(symbol):
            return plan_target_kinds.make_plan_target_ref("symbol", symbol)
        return plan_target_kinds.make_plan_target_ref()
    try:
        (point,) = plan_edit_nodes.get_edit_node_payload(node)
        doc = FreeCAD.getDocument(str(point.documentName.getValue()))
        obj = doc.getObject(str(point.objectName.getValue()))
    except Exception:
        return plan_target_kinds.make_plan_target_ref()
    if session.openings.is_hosted_opening_object(obj):
        return plan_target_kinds.make_plan_target_ref("opening", obj)
    target_ref = plan_target_kinds.coerce_plan_target_ref(
        plan_targets.get_plan_target_for_object(session, obj)
    )
    return plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj)


def get_edit_node(session, mouse_pos):
    node = _get_selected_handle_edit_node(session, mouse_pos)
    if node is not None:
        return node
    node = _get_provider_overlay_edit_node(session, mouse_pos)
    if node is not None:
        return node
    return _get_ray_picked_edit_node(session, mouse_pos)


def _emit_get_edit_node_result(session, mouse_pos, source, result):
    _emit_pick_debug(
        session,
        "get_edit_node",
        mouse_pos=mouse_pos,
        source=source,
        result=result,
    )
    return result


def _get_selected_handle_edit_node(session, mouse_pos):
    symbol_handle_role = session.overlays.symbols.pick_selected_symbol_handle(mouse_pos)
    if symbol_handle_role is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "selected_symbol_handle",
            plan_edit_nodes.SymbolHandleEditNode(
                plan_selection.get_selected_plan_target_object(session, "symbol"),
                symbol_handle_role,
            ),
        )
    opening_handle_index = pick_selected_opening_handle(session, mouse_pos)
    if opening_handle_index is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "selected_opening_handle",
            plan_edit_nodes.OpeningHandleEditNode(
                plan_selection.get_selected_plan_target_object(session, "opening"),
                opening_handle_index,
            ),
        )
    provider_handle_index = session.overlays.providers.pick_selected_provider_handle(mouse_pos)
    if provider_handle_index is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "selected_provider_handle",
            plan_edit_nodes.ProviderHandleEditNode(
                plan_selection.get_selected_plan_target_object(session, "provider"),
                provider_handle_index,
            ),
        )
    return None


def _get_provider_overlay_edit_node(session, mouse_pos):
    target_ref = pick_provider_overlay_target_from_objects_info(session, mouse_pos)
    if target_ref.obj is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "provider_overlay_objects_info",
            plan_edit_nodes.ProviderOverlayTargetEditNode(target_ref.kind, target_ref.obj),
        )
    target_ref = pick_provider_overlay_target_from_overlays(session, mouse_pos)
    if target_ref.obj is not None:
        return _emit_get_edit_node_result(
            session,
            mouse_pos,
            "provider_overlay_overlays",
            plan_edit_nodes.ProviderOverlayTargetEditNode(target_ref.kind, target_ref.obj),
        )
    return None


def _get_ray_picked_edit_node(session, mouse_pos):
    render_manager = session.viewport_state.render_manager
    if not render_manager:
        return _emit_get_edit_node_result(session, mouse_pos, "no_render_manager", None)
    try:
        from pivy import coin
    except Exception:
        return _emit_get_edit_node_result(session, mouse_pos, "coin_import_failed", None)

    ray_pick = coin.SoRayPickAction(render_manager.getViewportRegion())
    ray_pick.setPoint(coin.SbVec2s(*mouse_pos))
    ray_pick.setRadius(8)
    ray_pick.setPickAll(True)
    ray_pick.apply(render_manager.getSceneGraph())
    picked_points = ray_pick.getPickedPointList()
    if not picked_points:
        return _emit_get_edit_node_result(session, mouse_pos, "no_edit_node", None)
    return _get_edit_node_from_picked_points(session, mouse_pos, picked_points)


def _get_edit_node_from_picked_points(session, mouse_pos, picked_points):
    for picked_point in picked_points:
        path = picked_point.getPath()
        point = path.getNode(path.getLength() - 2)
        try:
            sub_element = str(point.subElementName.getValue())
        except Exception:
            continue
        if is_provider_overlay_point_subname(sub_element):
            return _emit_get_edit_node_result(
                session,
                mouse_pos,
                "ray_pick_provider_overlay_point",
                plan_edit_nodes.ProviderOverlayPointEditNode(point),
            )
        if "EditNode" in sub_element:
            return _emit_get_edit_node_result(
                session,
                mouse_pos,
                "ray_pick_edit_node",
                plan_edit_nodes.RayEditNode(point),
            )
    return _emit_get_edit_node_result(session, mouse_pos, "no_edit_node", None)


def pick_selected_opening_handle(session, mouse_pos, radius_px=10):
    opening = plan_selection.get_selected_plan_target_object(session, "opening")
    if not session.openings.is_hosted_opening_object(opening) or not session.view:
        return None
    try:
        cursor_x = int(mouse_pos[0])
        cursor_y = int(mouse_pos[1])
    except Exception:
        return None
    best_index = None
    best_distance_sq = None
    for idx, _role, point, _marker in session.overlays.openings.get_selected_opening_handle_specs(
        opening
    ):
        try:
            screen_x, screen_y = session.view.getPointOnScreen(point)
        except Exception:
            continue
        dx = float(screen_x) - float(cursor_x)
        dy = float(screen_y) - float(cursor_y)
        distance_sq = dx * dx + dy * dy
        if distance_sq > radius_px * radius_px:
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_index = idx
            best_distance_sq = distance_sq
    return best_index


def get_provider_overlay_target_from_edit_node(session, node):
    return plan_provider_overlay_picking.get_provider_overlay_target_from_edit_node(
        session,
        node,
    )


def is_provider_overlay_point_subname(subname):
    return plan_provider_overlay_picking.is_provider_overlay_point_subname(subname)


def clear_hovered_plan_targets(*args, **kwargs):
    return plan_hover_picking.clear_hovered_plan_targets(*args, **kwargs)


def get_hovered_plan_target(*args, **kwargs):
    return plan_target_kinds.coerce_plan_target_ref(
        plan_hover_picking.get_hovered_plan_target(*args, **kwargs)
    )


def prime_hover_pick_caches(*args, **kwargs):
    return plan_hover_picking.prime_hover_pick_caches(*args, **kwargs)


def queue_prime_hover_pick_caches(*args, **kwargs):
    return plan_hover_picking.queue_prime_hover_pick_caches(*args, **kwargs)


def should_skip_hover_pick(*args, **kwargs):
    return plan_hover_picking.should_skip_hover_pick(*args, **kwargs)


def update_hovered_plan_target(*args, **kwargs):
    return plan_hover_picking.update_hovered_plan_target(*args, **kwargs)
