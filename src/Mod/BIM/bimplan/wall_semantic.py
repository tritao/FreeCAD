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


def _opening_proxy(opening):
    for owner in (opening, getattr(opening, "ViewObject", None)):
        proxy = getattr(owner, "Proxy", None)
        if proxy is not None and all(
            callable(getattr(proxy, name, None))
            for name in ("get_plan_move_context", "get_plan_center_point", "move_along_host")
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
        context = proxy.get_plan_move_context() or {}
        center_value = proxy.get_plan_center_point()
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
            "proxy": proxy,
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
    evaluation = evaluate_wall_candidate(original, mode, candidate)
    if not evaluation.allowed:
        raise ValueError(evaluation.reason)
    layout = evaluate_hosted_openings(wall, original, evaluation.endpoints, mode)
    if layout is None:
        raise ValueError("The resized wall cannot contain its hosted openings.")
    wall.Proxy.set_from_endpoints(wall, evaluation.endpoints)
    for item in layout:
        if not item["proxy"].move_along_host(item["target_point"]):
            raise ValueError("A hosted opening could not be repositioned.")
    return evaluation


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
