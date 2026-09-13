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
