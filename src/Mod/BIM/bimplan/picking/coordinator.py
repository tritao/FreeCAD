# SPDX-License-Identifier: LGPL-2.1-or-later

"""Plan Edit pick target resolution coordinator."""

from dataclasses import dataclass, field

from bimplan.selection import area_picking as plan_area_picking
from bimplan.selection import overlay_picking as plan_overlay_picking
from bimplan.selection import picking_debug as plan_picking_debug
from bimplan.providers import picking as plan_provider_picking
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.selection import targets as plan_targets

PROVIDER_OVERLAY_PICK_RADIUS_PX = plan_provider_picking.PROVIDER_OVERLAY_PICK_RADIUS_PX


@dataclass
class PickStageCandidates:
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
            "symbol": plan_picking_debug.describe_pick_target(
                session, self.symbol.kind, self.symbol.obj
            ),
            "provider": plan_picking_debug.describe_pick_target(
                session, self.provider.kind, self.provider.obj
            ),
            "wall": plan_picking_debug.describe_pick_target(session, self.wall.kind, self.wall.obj),
            "region": plan_picking_debug.describe_pick_target(
                session, self.region.kind, self.region.obj
            ),
            "space": plan_picking_debug.describe_pick_target(
                session, self.space.kind, self.space.obj
            ),
        }


@dataclass(frozen=True)
class ObjectsInfoPickStageResult:
    direct_result: object
    candidates: PickStageCandidates
    debug_infos: tuple


@dataclass(frozen=True)
class PickResolutionResult:
    target_ref: object
    stage: str = ""


def _perf_count(session, name, delta=1):
    return session.performance.plan_perf_count(name, delta=delta)


def _perf_set_fields(session, **fields):
    return session.performance.plan_perf_set_fields(**fields)


def _perf_trace_span(session, name, **fields):
    return session.performance.plan_perf_trace_span(name, **fields)


def _get_plan_provider_overlay_pick_mode(session):
    return plan_provider_picking.get_plan_provider_overlay_pick_mode(session)


def _should_prioritize_provider_targets_for_mode(session):
    return plan_provider_picking.should_prioritize_provider_targets_for_mode(session)


def pick_provider_overlay_target_from_overlays(
    session,
    mouse_pos,
    radius_px=PROVIDER_OVERLAY_PICK_RADIUS_PX,
):
    return plan_provider_picking.pick_provider_overlay_target_from_overlays(
        session,
        mouse_pos,
        radius_px=radius_px,
    )


def pick_plan_opening_target_from_overlays(session, mouse_pos, radius_px=10, candidates=None):
    return plan_overlay_picking.pick_plan_opening_target_from_overlays(
        session,
        mouse_pos,
        radius_px=radius_px,
        candidates=candidates,
    )


def pick_plan_symbol_target_from_overlays(session, mouse_pos, radius_px=10):
    return plan_overlay_picking.pick_plan_symbol_target_from_overlays(
        session,
        mouse_pos,
        radius_px=radius_px,
    )


def pick_plan_region_target_from_polylines(session, mouse_pos):
    return plan_area_picking.pick_plan_region_target_from_polylines(session, mouse_pos)


def pick_plan_region_target_from_footprints(session, mouse_pos):
    return plan_area_picking.pick_plan_region_target_from_footprints(session, mouse_pos)


def pick_plan_region_target_from_overlays(session, mouse_pos, radius_px=10):
    return plan_area_picking.pick_plan_region_target_from_overlays(
        session,
        mouse_pos,
        radius_px=radius_px,
    )


def pick_plan_space_target_from_footprints(session, mouse_pos):
    return plan_area_picking.pick_plan_space_target_from_footprints(session, mouse_pos)


def pick_plan_space_target_from_overlays(session, mouse_pos, radius_px=10):
    return plan_area_picking.pick_plan_space_target_from_overlays(
        session,
        mouse_pos,
        radius_px=radius_px,
    )


def _get_view_objects_info(session, mouse_pos):
    try:
        with _perf_trace_span(session, "view_get_objects_info"):
            infos = session.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
    except (AttributeError, ReferenceError, RuntimeError):
        return []
    return list(infos or [])


def _collect_pick_candidates_from_objects_info(session, infos):
    candidates = PickStageCandidates()
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
        obj = plan_provider_picking.resolve_document_object(session, doc_name, obj_name)
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
        plan_picking_debug.append_pick_debug_item(
            debug_infos,
            {
                "info": plan_picking_debug.describe_pick_info_entry(info),
                "resolved_object": plan_picking_debug.describe_pick_object(session, obj),
                "target": plan_picking_debug.describe_pick_target(
                    session, target_ref.kind, target_ref.obj
                ),
            },
        )
        if target_ref.kind == "opening":
            direct_result = plan_target_kinds.make_plan_target_ref("opening", target_ref.obj)
            break
        if target_ref.kind in ("wall", "symbol", "provider", "region", "space"):
            candidates.store_if_empty(target_ref.kind, target_ref.obj)
    return ObjectsInfoPickStageResult(
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
            radius_px=PROVIDER_OVERLAY_PICK_RADIUS_PX,
        )
        if provider_overlay_target.kind == "provider" and provider_overlay_target.obj is not None:
            candidates.provider = provider_overlay_target
    if prioritize_provider_targets and candidates.provider.obj is not None:
        return PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("provider", candidates.provider.obj),
            stage="provider_overlay_priority",
        )
    return PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def _resolve_structural_overlay_priority_target(session, mouse_pos, candidates):
    if candidates.symbol.obj is not None and candidates.wall.obj is None:
        return PickResolutionResult(
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
        return PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("opening", opening_candidate),
            stage="opening_overlay_priority",
        )
    return PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def _resolve_symbol_or_terminal_overlay_target(session, mouse_pos, candidates):
    if candidates.symbol.obj is None:
        symbol_candidate = pick_plan_symbol_target_from_overlays(session, mouse_pos)
        candidates.store_if_empty("symbol", symbol_candidate)
    if candidates.symbol.obj is not None:
        return PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("symbol", candidates.symbol.obj),
            stage="symbol_overlay_or_direct",
        )
    if candidates.wall.obj is not None:
        return PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("wall", candidates.wall.obj),
            stage="wall_terminal",
        )
    if candidates.provider.obj is not None:
        return PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("provider", candidates.provider.obj),
            stage="provider_terminal",
        )
    return PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


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
        return PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("region", candidates.region.obj),
            stage="region_fallback",
        )
    return PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


def _resolve_space_fallback_target(
    session,
    mouse_pos,
    candidates,
    *,
    include_space_fallback,
):
    if not include_space_fallback:
        return PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())
    if candidates.space.obj is None:
        space_candidate = pick_plan_space_target_from_footprints(session, mouse_pos)
        candidates.store_if_empty("space", space_candidate)
    if candidates.space.obj is None:
        space_candidate = pick_plan_space_target_from_overlays(session, mouse_pos)
        candidates.store_if_empty("space", space_candidate)
    if candidates.space.obj is not None:
        return PickResolutionResult(
            target_ref=plan_target_kinds.make_plan_target_ref("space", candidates.space.obj),
            stage="space_fallback",
        )
    return PickResolutionResult(target_ref=plan_target_kinds.make_plan_target_ref())


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
            picked_target=plan_picking_debug.describe_pick_target(session, result.kind, result.obj),
        )
        plan_picking_debug.emit_pick_debug(
            session,
            "get_plan_target_at_position",
            mouse_pos=mouse_pos,
            overlay_mode=_get_plan_provider_overlay_pick_mode(session),
            prioritize_provider_targets=prioritize_provider_targets,
            include_space_fallback=bool(include_space_fallback),
            objects_info=debug_infos,
            candidates=candidates.as_debug_dict(session),
            resolution_stage=resolution_stage,
            result=plan_picking_debug.describe_pick_target(session, result.kind, result.obj),
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
