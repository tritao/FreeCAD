# SPDX-License-Identifier: LGPL-2.1-or-later

"""Provider-overlay pick target helpers for BIM Plan Edit."""

from dataclasses import dataclass
import math

import FreeCAD

from bimplan.providers import PlanOverlayMarkerKind
from bimplan.providers import runtime as plan_provider_runtime
from bimplan.selection import edit_nodes as plan_edit_nodes
from bimplan.picking import debug as plan_picking_debug
from bimplan.picking import geometry as plan_picking_geometry
from bimplan.selection import target_kinds as plan_target_kinds
from bimplan.selection import targets as plan_targets

_PROVIDER_OVERLAY_POINT_PREFIX = "ProviderOverlayPoint"
PROVIDER_OVERLAY_PICK_RADIUS_PX = 12.0
_PROVIDER_OVERLAY_PICK_PADDING_PX = 3.0
_PROVIDER_OVERLAY_PICK_PADDING_RATIO = 0.15
_PROVIDER_OVERLAY_MARKER_TOLERANCE_BASE_PX = 4.5
_PROVIDER_OVERLAY_MARKER_TOLERANCE_WIDTH_SCALE = 1.25


@dataclass(frozen=True)
class ProviderOverlayPointCandidate:
    distance_sq: float
    target_ref: object


@dataclass(frozen=True)
class ProviderOverlayDebugCandidate:
    overlay: object
    point_index: int
    target: object
    center_distance_px: float
    pick_radius_px: float
    marker_tolerance_px: float
    marker_distance_px: float | None = None
    decision: str = ""
    resolved_object: object = None
    distance_px: float | None = None

    def as_debug_dict(self):
        result = {
            "overlay": self.overlay,
            "point_index": self.point_index,
            "target": self.target,
            "center_distance_px": self.center_distance_px,
            "pick_radius_px": self.pick_radius_px,
            "marker_tolerance_px": self.marker_tolerance_px,
        }
        if self.marker_distance_px is not None:
            result["marker_distance_px"] = self.marker_distance_px
        if self.decision:
            result["decision"] = self.decision
        if self.resolved_object is not None:
            result["resolved_object"] = self.resolved_object
        if self.distance_px is not None:
            result["distance_px"] = self.distance_px
        return result


@dataclass(frozen=True)
class ProviderOverlayVisibleTargetDebugEntry:
    identity: tuple
    target: object

    def as_debug_dict(self):
        return {
            "identity": list(self.identity),
            "target": self.target,
        }


@dataclass(frozen=True)
class ProviderOverlayInfoDebugEntry:
    info: object
    candidates: tuple = ()

    def as_debug_dict(self):
        return {
            "info": self.info,
            "candidates": list(self.candidates),
        }


@dataclass(frozen=True)
class ProviderOverlayObjectsInfoPickResult:
    target_ref: object
    debug_infos: tuple


def replace_provider_overlay_debug_candidate(debug_candidate, **changes):
    return ProviderOverlayDebugCandidate(
        overlay=changes.get("overlay", debug_candidate.overlay),
        point_index=changes.get("point_index", debug_candidate.point_index),
        target=changes.get("target", debug_candidate.target),
        center_distance_px=changes.get("center_distance_px", debug_candidate.center_distance_px),
        pick_radius_px=changes.get("pick_radius_px", debug_candidate.pick_radius_px),
        marker_tolerance_px=changes.get("marker_tolerance_px", debug_candidate.marker_tolerance_px),
        marker_distance_px=changes.get("marker_distance_px", debug_candidate.marker_distance_px),
        decision=changes.get("decision", debug_candidate.decision),
        resolved_object=changes.get("resolved_object", debug_candidate.resolved_object),
        distance_px=changes.get("distance_px", debug_candidate.distance_px),
    )


def get_plan_provider_overlay_pick_mode(session):
    mode = str(plan_provider_runtime.get_plan_provider_overlay_mode(session) or "").strip().lower()
    return mode or "all"


def should_prioritize_provider_targets_for_mode(session):
    return plan_provider_runtime.is_focused_provider_overlay_pick_mode(
        get_plan_provider_overlay_pick_mode(session)
    )


def pick_provider_overlay_target_from_overlays(
    session,
    mouse_pos,
    radius_px=PROVIDER_OVERLAY_PICK_RADIUS_PX,
):
    with session.performance.plan_perf_trace_span(
        "pick_provider_overlay_target_from_overlays",
        mouse_pos=mouse_pos,
        radius_px=radius_px,
    ):
        if not session.view or not mouse_pos:
            return plan_target_kinds.make_plan_target_ref()
        try:
            cursor_x = float(mouse_pos[0])
            cursor_y = float(mouse_pos[1])
        except Exception:
            return plan_target_kinds.make_plan_target_ref()

        overlays = get_visible_provider_overlays(session)
        if overlays is None:
            return plan_target_kinds.make_plan_target_ref()

        best_distance_sq = None
        best_target_ref = plan_target_kinds.make_plan_target_ref()
        debug_candidates = []
        for overlay in overlays:
            points = tuple(getattr(overlay, "points", ()) or ())
            targets = tuple(getattr(overlay, "point_targets", ()) or ())
            for index, point in enumerate(points):
                target = targets[index] if index < len(targets) else None
                candidate, debug_candidate = evaluate_provider_overlay_point_candidate(
                    session,
                    overlay,
                    target,
                    point,
                    point_index=index,
                    cursor_x=cursor_x,
                    cursor_y=cursor_y,
                    mouse_pos=mouse_pos,
                    fallback_radius_px=radius_px,
                )
                if debug_candidate is not None:
                    plan_picking_debug.append_pick_debug_item(
                        debug_candidates, debug_candidate.as_debug_dict()
                    )
                if candidate is None:
                    continue
                distance_sq = candidate.distance_sq
                if best_distance_sq is None or distance_sq < best_distance_sq:
                    best_distance_sq = distance_sq
                    best_target_ref = candidate.target_ref
        session.performance.plan_perf_set_fields(
            provider_overlay_pick_result=plan_picking_debug.describe_pick_object(
                session, best_target_ref.obj
            ),
        )
        plan_picking_debug.emit_pick_debug(
            session,
            "pick_provider_overlay_target_from_overlays",
            mouse_pos=mouse_pos,
            fallback_radius_px=radius_px,
            candidates=debug_candidates,
            result=plan_picking_debug.describe_pick_target(
                session, best_target_ref.kind, best_target_ref.obj
            ),
        )
        return best_target_ref


def get_visible_provider_overlays(session):
    return tuple(
        overlay
        for overlay in tuple(plan_provider_runtime.get_plan_provider_overlays(session) or ())
        if bool(getattr(overlay, "visible", True))
        and plan_provider_runtime.is_plan_provider_overlay_visible(session, overlay)
    )


def make_provider_overlay_debug_candidate(
    overlay,
    target,
    *,
    point_index,
    center_distance_sq,
    pick_radius_px,
    marker_tolerance_px,
    marker_distance_sq=None,
):
    return ProviderOverlayDebugCandidate(
        overlay=plan_picking_debug.describe_pick_overlay(overlay),
        point_index=point_index,
        target=plan_picking_debug.describe_pick_overlay_target(target),
        center_distance_px=round(center_distance_sq**0.5, 3),
        pick_radius_px=round(float(pick_radius_px), 3),
        marker_tolerance_px=round(float(marker_tolerance_px), 3),
        marker_distance_px=(
            round(marker_distance_sq**0.5, 3) if marker_distance_sq is not None else None
        ),
    )


def evaluate_provider_overlay_point_candidate(
    session,
    overlay,
    target,
    point,
    *,
    point_index,
    cursor_x,
    cursor_y,
    mouse_pos,
    fallback_radius_px,
):
    if not has_provider_overlay_target_identity(target):
        return (None, None)
    point_vec = coerce_overlay_point_vector(point)
    if point_vec is None:
        return (None, None)
    try:
        point_x, point_y = session.view.getPointOnScreen(point_vec)
    except Exception:
        return (None, None)
    dx = float(point_x) - cursor_x
    dy = float(point_y) - cursor_y
    center_distance_sq = dx * dx + dy * dy
    pick_radius_px = get_provider_overlay_pick_radius_px(
        session,
        overlay,
        point_vec,
        fallback_radius_px=fallback_radius_px,
    )
    marker_distance_sq = get_provider_overlay_marker_screen_distance_sq(
        session,
        mouse_pos,
        overlay,
        point_vec,
    )
    marker_tolerance_px = get_provider_overlay_marker_tolerance_px(
        overlay,
        fallback_radius_px=fallback_radius_px,
    )
    debug_candidate = make_provider_overlay_debug_candidate(
        overlay,
        target,
        point_index=point_index,
        center_distance_sq=center_distance_sq,
        pick_radius_px=pick_radius_px,
        marker_tolerance_px=marker_tolerance_px,
        marker_distance_sq=marker_distance_sq,
    )
    distance_sq = center_distance_sq
    if marker_distance_sq is not None:
        distance_sq = min(distance_sq, marker_distance_sq)
    if center_distance_sq > pick_radius_px * pick_radius_px and (
        marker_distance_sq is None or marker_distance_sq > marker_tolerance_px * marker_tolerance_px
    ):
        return (
            None,
            replace_provider_overlay_debug_candidate(debug_candidate, decision="outside_radius"),
        )
    target_obj = resolve_document_object(
        session,
        getattr(target, "document_name", ""),
        getattr(target, "object_name", ""),
    )
    if target_obj is None:
        return (
            None,
            replace_provider_overlay_debug_candidate(
                debug_candidate,
                decision="unresolved_object",
            ),
        )
    debug_candidate = replace_provider_overlay_debug_candidate(
        debug_candidate,
        decision="candidate",
        resolved_object=plan_picking_debug.describe_pick_object(session, target_obj),
        distance_px=round(distance_sq**0.5, 3),
    )
    return (
        ProviderOverlayPointCandidate(
            distance_sq=distance_sq,
            target_ref=plan_target_kinds.make_plan_target_ref(
                target.target_kind.value if target.target_kind is not None else "",
                target_obj,
            ),
        ),
        debug_candidate,
    )


def pick_provider_overlay_target_from_objects_info(session, mouse_pos):
    with session.performance.plan_perf_trace_span(
        "pick_provider_overlay_target_from_objects_info",
        mouse_pos=mouse_pos,
    ):
        if not session.view or not mouse_pos:
            return plan_target_kinds.make_plan_target_ref()
        try:
            infos = session.view.getObjectsInfo((int(mouse_pos[0]), int(mouse_pos[1])))
        except (AttributeError, ReferenceError, RuntimeError):
            return plan_target_kinds.make_plan_target_ref()
        if not infos:
            return plan_target_kinds.make_plan_target_ref()

        visible_targets = collect_visible_provider_overlay_targets(session)
        if not visible_targets:
            plan_picking_debug.emit_pick_debug(
                session,
                "pick_provider_overlay_target_from_objects_info",
                mouse_pos=mouse_pos,
                objects_info=[plan_picking_debug.describe_pick_info_entry(info) for info in infos],
                visible_targets=[],
                result=None,
            )
            return plan_target_kinds.make_plan_target_ref()

        pick_result = pick_provider_overlay_target_from_infos(session, infos, visible_targets)
        debug_visible_targets = describe_visible_provider_overlay_targets(visible_targets)
        if pick_result.target_ref.obj is not None:
            session.performance.plan_perf_set_fields(
                provider_overlay_info_pick_result=plan_picking_debug.describe_pick_object(
                    session, pick_result.target_ref.obj
                ),
            )
            plan_picking_debug.emit_pick_debug(
                session,
                "pick_provider_overlay_target_from_objects_info",
                mouse_pos=mouse_pos,
                objects_info=list(pick_result.debug_infos),
                visible_targets=debug_visible_targets,
                result=plan_picking_debug.describe_pick_target(
                    session,
                    pick_result.target_ref.kind,
                    pick_result.target_ref.obj,
                ),
            )
            return pick_result.target_ref
        plan_picking_debug.emit_pick_debug(
            session,
            "pick_provider_overlay_target_from_objects_info",
            mouse_pos=mouse_pos,
            objects_info=list(pick_result.debug_infos),
            visible_targets=debug_visible_targets,
            result=None,
        )
        return plan_target_kinds.make_plan_target_ref()


def describe_visible_provider_overlay_targets(visible_targets):
    return [
        ProviderOverlayVisibleTargetDebugEntry(
            identity=identity,
            target=plan_picking_debug.describe_pick_overlay_target(target),
        ).as_debug_dict()
        for identity, target in tuple(visible_targets.items())[
            : plan_picking_debug.MAX_PICK_DEBUG_ITEMS
        ]
    ]


def resolve_provider_overlay_target_from_info(session, info, visible_targets):
    info_candidates = []
    for target_ref in iter_provider_overlay_targets_from_info(
        session,
        info,
        visible_targets,
    ):
        plan_picking_debug.append_pick_debug_item(
            info_candidates,
            plan_picking_debug.describe_pick_target(session, target_ref.kind, target_ref.obj),
        )
        if target_ref.obj is not None:
            return (
                plan_target_kinds.make_plan_target_ref(target_ref.kind, target_ref.obj),
                ProviderOverlayInfoDebugEntry(
                    info=plan_picking_debug.describe_pick_info_entry(info),
                    candidates=tuple(info_candidates),
                ).as_debug_dict(),
            )
    return (
        plan_target_kinds.make_plan_target_ref(),
        ProviderOverlayInfoDebugEntry(
            info=plan_picking_debug.describe_pick_info_entry(info),
            candidates=tuple(info_candidates),
        ).as_debug_dict(),
    )


def pick_provider_overlay_target_from_infos(session, infos, visible_targets):
    debug_infos = []
    for info in infos:
        target_ref, info_entry = resolve_provider_overlay_target_from_info(
            session, info, visible_targets
        )
        plan_picking_debug.append_pick_debug_item(debug_infos, info_entry)
        if target_ref.obj is not None:
            return ProviderOverlayObjectsInfoPickResult(
                target_ref=target_ref,
                debug_infos=tuple(debug_infos),
            )
    return ProviderOverlayObjectsInfoPickResult(
        target_ref=plan_target_kinds.make_plan_target_ref(),
        debug_infos=tuple(debug_infos),
    )


def get_provider_overlay_target_from_edit_node(session, node):
    if not node:
        return (None, None)
    node_kind = plan_edit_nodes.get_edit_node_kind(node)
    if node_kind == "provider_overlay_target":
        try:
            return plan_edit_nodes.get_edit_node_payload(node)
        except Exception:
            return (None, None)
    if node_kind != "provider_overlay_point":
        return (None, None)
    try:
        (point,) = plan_edit_nodes.get_edit_node_payload(node)
        document_name = str(point.documentName.getValue())
        object_name = str(point.objectName.getValue())
        subname = str(point.subElementName.getValue())
    except Exception:
        return (None, None)
    obj = resolve_document_object(session, document_name, object_name)
    if obj is None:
        return (None, None)
    target_kind = parse_provider_overlay_target_kind(subname)
    if target_kind and session.selection.state.is_valid_plan_target(target_kind, obj):
        return (target_kind, obj)
    inferred_kind, inferred_obj = plan_targets.get_plan_target_for_object(session, obj)
    if inferred_kind and inferred_obj:
        return (inferred_kind, inferred_obj)
    return (None, obj)


def is_provider_overlay_point_subname(subname):
    return str(subname or "").startswith(_PROVIDER_OVERLAY_POINT_PREFIX + ":")


def parse_provider_overlay_target_kind(subname):
    parts = str(subname or "").split(":")
    if len(parts) < 2 or parts[0] != _PROVIDER_OVERLAY_POINT_PREFIX:
        return ""
    return parts[1].strip()


def resolve_document_object(session, document_name, object_name):
    object_name = str(object_name or "").strip()
    if not object_name:
        return None
    document_name = str(document_name or "").strip()
    doc = None
    if document_name:
        try:
            doc = FreeCAD.getDocument(document_name)
        except Exception:
            doc = None
    if doc is None:
        doc = getattr(session, "doc", None)
    if doc is None:
        return None
    try:
        return doc.getObject(object_name)
    except Exception:
        return None


def coerce_overlay_point_vector(point):
    if point is None:
        return None
    if isinstance(point, FreeCAD.Vector):
        return FreeCAD.Vector(point)
    try:
        return FreeCAD.Vector(float(point[0]), float(point[1]), float(point[2]))
    except (TypeError, ValueError, IndexError):
        try:
            return FreeCAD.Vector(
                float(point.x),
                float(point.y),
                float(getattr(point, "z", 0.0) or 0.0),
            )
        except Exception:
            return None


def collect_visible_provider_overlay_targets(session):
    targets = {}
    for identity, target in iter_visible_provider_overlay_targets(session):
        if identity in targets:
            continue
        targets[identity] = target
    return targets


def iter_provider_overlay_targets_from_info(session, info, visible_targets):
    if not info or not visible_targets:
        return ()
    yielded = []
    for obj in get_objects_info_candidate_objects(session, info):
        identity = get_provider_overlay_object_identity(obj)
        if identity is None:
            continue
        target = visible_targets.get(identity)
        if target is None:
            continue
        yielded.append(
            plan_target_kinds.make_plan_target_ref(
                target.target_kind.value if target.target_kind is not None else "",
                obj,
            )
        )
    return tuple(yielded)


def iter_visible_provider_overlay_targets(session):
    yielded = []
    for overlay in tuple(plan_provider_runtime.get_plan_provider_overlays(session) or ()):
        if not bool(getattr(overlay, "visible", True)):
            continue
        if not plan_provider_runtime.is_plan_provider_overlay_visible(session, overlay):
            continue
        for target in tuple(getattr(overlay, "point_targets", ()) or ()):
            if not has_provider_overlay_target_identity(target):
                continue
            identity = get_provider_overlay_target_identity(session, target)
            if identity is None:
                continue
            yielded.append((identity, target))
    return tuple(yielded)


def get_provider_overlay_object_identity(obj):
    if obj is None:
        return None
    identity = (
        str(getattr(getattr(obj, "Document", None), "Name", "") or "").strip(),
        str(getattr(obj, "Name", "") or "").strip(),
    )
    if not identity[1]:
        return None
    return identity


def get_objects_info_candidate_objects(session, info):
    if not info:
        return ()
    candidates = []
    doc_name = str(info.get("Document") or "").strip()
    obj_name = str(info.get("Object") or "").strip()
    if obj_name:
        resolved = resolve_document_object(session, doc_name, obj_name)
        if resolved is not None:
            candidates.append(resolved)
    parent_obj = info.get("ParentObject")
    if parent_obj is not None and parent_obj not in candidates:
        candidates.append(parent_obj)
    return tuple(candidates)


def get_provider_overlay_target_identity(session, target):
    object_name = str(getattr(target, "object_name", "") or "").strip()
    if not object_name:
        return None
    document_name = str(getattr(target, "document_name", "") or "").strip()
    if not document_name:
        document_name = str(getattr(getattr(session, "doc", None), "Name", "") or "")
    return (document_name, object_name)


def has_provider_overlay_target_identity(target):
    return bool(str(getattr(target, "object_name", "") or "").strip())


def get_provider_overlay_pick_radius_px(session, overlay, point, fallback_radius_px):
    radius_px = max(1.0, float(fallback_radius_px))
    projected_radius_px = get_provider_overlay_projected_marker_radius_px(
        session,
        overlay,
        point,
    )
    if projected_radius_px is not None:
        radius_px = max(
            radius_px,
            projected_radius_px
            + max(
                _PROVIDER_OVERLAY_PICK_PADDING_PX,
                projected_radius_px * _PROVIDER_OVERLAY_PICK_PADDING_RATIO,
            ),
        )
    return radius_px


def get_provider_overlay_marker_screen_distance_sq(session, mouse_pos, overlay, point):
    marker_segments = get_provider_overlay_marker_segments(overlay, point)
    if not marker_segments:
        return None
    return get_best_provider_overlay_marker_distance_sq(session, mouse_pos, marker_segments)


def get_provider_overlay_projected_marker_radius_px(session, overlay, point):
    marker_size = max(1.0, float(getattr(overlay, "marker_size", 160.0) or 160.0))
    marker_half_size = marker_size / 2.0
    marker_extent_factor = get_provider_overlay_pick_extent_factor(overlay.marker_kind)
    try:
        center_x, center_y = session.view.getPointOnScreen(point)
        edge_x, edge_y = session.view.getPointOnScreen(
            FreeCAD.Vector(
                point.x + (marker_half_size * marker_extent_factor),
                point.y,
                point.z,
            )
        )
    except Exception:
        return None
    return ((float(edge_x) - float(center_x)) ** 2 + (float(edge_y) - float(center_y)) ** 2) ** 0.5


def get_best_provider_overlay_marker_distance_sq(session, mouse_pos, marker_segments):
    best_distance_sq = None
    for start, end in marker_segments:
        distance_sq = plan_picking_geometry.get_screen_distance_sq_to_segment(
            session, mouse_pos, start, end
        )
        if distance_sq is None:
            continue
        if best_distance_sq is None or distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
    return best_distance_sq


def get_provider_overlay_marker_segments(overlay, point):
    try:
        from bimplan.overlays.providers import _get_point_marker_segment_specs
    except Exception:
        return ()
    try:
        specs = _get_point_marker_segment_specs(
            point,
            label="provider-overlay-pick",
            color=(0.0, 0.0, 0.0),
            width=float(getattr(overlay, "line_width", 2.0) or 2.0),
            dotted=bool(getattr(overlay, "dotted", False)),
            marker_size=float(getattr(overlay, "marker_size", 160.0) or 160.0),
            marker_kind=overlay.marker_kind,
        )
    except Exception:
        return ()
    return tuple(
        (spec.get("start"), spec.get("end"))
        for spec in tuple(specs or ())
        if spec.get("start") is not None and spec.get("end") is not None
    )


def get_provider_overlay_marker_tolerance_px(overlay, fallback_radius_px):
    line_width = max(1.0, float(getattr(overlay, "line_width", 2.0) or 2.0))
    return max(
        _PROVIDER_OVERLAY_MARKER_TOLERANCE_BASE_PX,
        2.0 + (line_width * _PROVIDER_OVERLAY_MARKER_TOLERANCE_WIDTH_SCALE),
    )


def get_provider_overlay_pick_extent_factor(marker_kind):
    if marker_kind in (
        PlanOverlayMarkerKind.SQUARE,
        PlanOverlayMarkerKind.HOURGLASS,
    ):
        return math.sqrt(2.0)
    return 1.0
