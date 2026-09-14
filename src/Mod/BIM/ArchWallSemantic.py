# SPDX-License-Identifier: LGPL-2.1-or-later

"""Viewer-independent evaluation for straight wall move and stretch edits."""

from dataclasses import dataclass

import FreeCAD


MINIMUM_WALL_LENGTH = 10.0


@dataclass(frozen=True)
class WallEditEvaluation:
    allowed: bool
    endpoints: tuple = ()
    reason: str = ""
    opening_layout: tuple = ()
    relation_paths: object = None
    relation_claims: object = None
    affected_walls: tuple = ()


def _opening_proxy(opening):
    for owner in (opening, getattr(opening, "ViewObject", None)):
        proxy = getattr(owner, "Proxy", None)
        if proxy is not None and all(
            callable(getattr(proxy, name, None))
            for name in ("get_hosted_opening_move_context", "get_hosted_opening_center_point")
        ):
            return proxy
    return None


def hosted_opening_records(wall, original_endpoints, candidate_endpoints, mode):
    """Describe hosted-opening bounds for a proposed wall path without mutation."""

    original_start, original_end = (FreeCAD.Vector(point) for point in original_endpoints)
    start, end = (FreeCAD.Vector(point) for point in candidate_endpoints)
    old_axis = original_end.sub(original_start)
    axis = end.sub(start)
    if old_axis.Length <= 1e-9 or axis.Length <= 1e-9:
        return None
    old_length, length = old_axis.Length, axis.Length
    old_axis.normalize()
    axis.normalize()
    records = []
    document = getattr(wall, "Document", None)
    for opening in getattr(document, "Objects", ()) or ():
        if wall not in tuple(getattr(opening, "Hosts", ()) or ()):
            continue
        proxy = _opening_proxy(opening)
        if proxy is None:
            continue
        context = proxy.get_hosted_opening_move_context() or {}
        center_value = proxy.get_hosted_opening_center_point()
        if center_value is None:
            continue
        center = FreeCAD.Vector(center_value)
        old_u = center.sub(original_start).dot(old_axis)
        half = float(context.get("opening_half_width_u") or 0.0)
        if mode == "Move":
            desired = old_u
        elif mode == "Start":
            desired = half + max(0.0, old_u - half)
        else:
            desired = length - half - max(0.0, old_length - old_u - half)
        records.append({
            "opening": opening,
            "current": center,
            "desired_u": desired,
            "low": half,
            "high": length - half,
            "half_width": half,
        })
    records.sort(key=lambda item: (item["desired_u"], getattr(item["opening"], "Name", "")))
    return records, start, axis


def resolve_opening_records(records, origin, axis):
    """Return non-overlapping hosted-opening targets, or None when they cannot fit."""

    left = []
    for index, item in enumerate(records):
        minimum = item["low"]
        if index:
            minimum = max(minimum, left[-1] + records[index - 1]["half_width"] + item["half_width"])
        if minimum > item["high"] + 1e-6:
            return None
        left.append(minimum)
    right = [0.0] * len(records)
    for index in range(len(records) - 1, -1, -1):
        maximum = records[index]["high"]
        if index + 1 < len(records):
            maximum = min(maximum, right[index + 1] - records[index]["half_width"] - records[index + 1]["half_width"])
        if maximum < records[index]["low"] - 1e-6:
            return None
        right[index] = maximum
    result = []
    for index, item in enumerate(records):
        center_u = min(max(item["desired_u"], left[index]), right[index])
        if index:
            center_u = max(center_u, result[-1]["target_center_u"] + records[index - 1]["half_width"] + item["half_width"])
        if center_u > right[index] + 1e-6:
            return None
        target = origin.add(FreeCAD.Vector(axis).multiply(center_u))
        target.z = item["current"].z
        result.append({**item, "target_center_u": center_u, "target_point": target})
    return result


def evaluate_hosted_openings(wall, original_endpoints, candidate_endpoints, mode):
    data = hosted_opening_records(wall, original_endpoints, candidate_endpoints, mode)
    if data is None:
        return None
    records, origin, axis = data
    return resolve_opening_records(records, origin, axis)


def apply_wall_candidate(wall, mode, candidate):
    """Atomically-ready domain mutation for a wall and its hosted openings."""

    original = tuple(wall.Proxy.calc_endpoints(wall))
    evaluation = evaluate_wall_edit(wall, mode, candidate)
    if not evaluation.allowed:
        raise ValueError(evaluation.reason)
    wall.Proxy.set_from_endpoints(wall, evaluation.endpoints)
    import ArchOpeningSemantic

    for item in evaluation.opening_layout:
        if not ArchOpeningSemantic.move_hosted_opening(
            item["opening"], item["target_point"]
        ):
            raise ValueError("A hosted opening could not be repositioned.")
    return evaluation


def apply_post_creation_join(
    wall,
    previous_wall,
    *,
    destructive_merge=False,
    auto_join=False,
):
    """Apply the join policy chosen by a wall-creation frontend."""

    if wall is None or previous_wall is None or wall is previous_wall:
        return False
    if wall.getParentGroup() != previous_wall.getParentGroup():
        return False

    import Arch
    import ArchWall

    if (
        destructive_merge
        and getattr(wall, "Base", None)
        and ArchWall.areSameWallTypes([wall, previous_wall])
    ):
        Arch.joinWalls([wall, previous_wall], delete=True, deletebase=True)
        return True
    if not auto_join:
        return False
    wall_group = wall.getParentGroup()
    if wall_group:
        wall_group.removeObject(wall)
    Arch.addComponents(wall, previous_wall)
    return True


def evaluate_wall_edit(wall, mode, candidate):
    """Evaluate geometry, relations, and hosted openings without document mutation."""

    import Part
    import ArchWallGeometry
    import ArchWallRelation

    original = tuple(wall.Proxy.calc_endpoints(wall))
    base = evaluate_wall_candidate(original, mode, candidate)
    if not base.allowed:
        return base
    layout = evaluate_hosted_openings(wall, original, base.endpoints, mode)
    if layout is None:
        return WallEditEvaluation(
            False, base.endpoints,
            "The resized wall cannot contain its hosted openings.",
        )
    baseline = wall.Proxy.get_global_baseline(wall)
    proposed = ArchWallGeometry.WallPath(
        Part.makeLine(*base.endpoints), baseline.normal
    )
    paths = {wall: proposed}
    claims = {}
    affected = {wall}
    for relation in ArchWallRelation.iter_wall_joints(wall):
        if not getattr(relation, "Enabled", True):
            continue
        wall_a, wall_b = relation.WallA, relation.WallB
        path_a = paths.get(wall_a) or ArchWallRelation.get_join_path(wall_a)
        path_b = paths.get(wall_b) or ArchWallRelation.get_join_path(wall_b)
        solution = ArchWallRelation.solve_wall_joint_inputs(
            wall_a, wall_b, relation.JointType, relation.ButtTrimmed,
            relation.TeeStem, relation.EndA, relation.EndB,
            path_a=path_a, path_b=path_b,
        )
        if not solution.is_ok():
            return WallEditEvaluation(
                False,
                base.endpoints,
                getattr(solution, "status_message", "")
                or "The wall relation cannot be solved for this edit.",
            )
        affected.update((wall_a, wall_b))
        paths.setdefault(wall_a, path_a)
        paths.setdefault(wall_b, path_b)
        for claim in solution.trim_claims:
            claims.setdefault(claim.wall, {})[claim.end_name] = claim
    return WallEditEvaluation(
        True,
        base.endpoints,
        opening_layout=tuple(layout),
        relation_paths=paths,
        relation_claims=claims,
        affected_walls=tuple(affected),
    )


def evaluate_wall_candidate(endpoints, mode, candidate, minimum=MINIMUM_WALL_LENGTH):
    """Evaluate a semantic candidate against a stable pair of wall endpoints."""

    if candidate is None or len(tuple(endpoints or ())) != 2:
        return WallEditEvaluation(False, reason="A straight wall path is required.")
    start, end = (FreeCAD.Vector(point) for point in endpoints)
    candidate = FreeCAD.Vector(candidate)
    mode = str(mode)
    if mode == "Move":
        midpoint = (start + end) * 0.5
        delta = candidate.sub(midpoint)
        return WallEditEvaluation(True, (start.add(delta), end.add(delta)))
    if mode not in ("Start", "End"):
        return WallEditEvaluation(False, reason="Unsupported wall edit operation.")
    fixed = end if mode == "Start" else start
    moving = start if mode == "Start" else end
    axis = moving.sub(fixed)
    if axis.Length < minimum:
        return WallEditEvaluation(
            False, reason="Wall length must be at least {:g} mm.".format(minimum)
        )
    axis.normalize()
    length = candidate.sub(fixed).dot(axis)
    if length < minimum:
        return WallEditEvaluation(
            False, reason="Wall length must be at least {:g} mm.".format(minimum)
        )
    target = fixed.add(axis.multiply(length))
    result = (target, fixed) if mode == "Start" else (fixed, target)
    return WallEditEvaluation(True, result)


def evaluate_wall_length(endpoints, mode, length, minimum=MINIMUM_WALL_LENGTH):
    if len(tuple(endpoints or ())) != 2 or mode not in ("Start", "End"):
        return WallEditEvaluation(False, reason="A straight wall endpoint is required.")
    start, end = (FreeCAD.Vector(point) for point in endpoints)
    axis = end.sub(start)
    if axis.Length < minimum:
        return WallEditEvaluation(
            False, reason="Wall length must be at least {:g} mm.".format(minimum)
        )
    axis.normalize()
    length = max(float(length), minimum)
    candidate = end.sub(axis.multiply(length)) if mode == "Start" else start.add(axis.multiply(length))
    return evaluate_wall_candidate((start, end), mode, candidate, minimum)
