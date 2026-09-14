# SPDX-License-Identifier: LGPL-2.1-or-later
"""Viewer-independent evaluation and mutation services for BIM spaces."""

from dataclasses import dataclass


class SpaceSemanticError(RuntimeError):
    pass


@dataclass(frozen=True)
class SpaceBoundaryEvaluation:
    boundaries: tuple = ()
    valid: bool = False
    code: str = ""
    message: str = ""
    details: tuple = ()
    candidates: tuple = ()
    inner_void_count: int = 0
    source_report: object = None

    @classmethod
    def from_report(cls, boundaries, report):
        report = dict(report or {})
        return cls(
            boundaries=tuple(boundaries or ()),
            valid=bool(report.get("valid")),
            code=str(report.get("code") or ""),
            message=str(report.get("message") or ""),
            details=tuple(report.get("details", ()) or ()),
            candidates=tuple(report.get("candidates", ()) or ()),
            inner_void_count=int(report.get("inner_void_count", 0) or 0),
            source_report=report,
        )

    def to_report(self):
        report = dict(self.source_report or {})
        report.update({
            "valid": self.valid,
            "code": self.code,
            "message": self.message,
            "details": list(self.details),
            "candidates": list(self.candidates),
            "candidate_count": len(self.candidates),
            "inner_void_count": self.inner_void_count,
        })
        return report


def normalize_boundaries(boundaries):
    import ArchSpace

    return tuple(ArchSpace.normalizeBoundaryLinks(boundaries or ()))


def evaluate_boundaries(boundaries, *, label=None, seed_space=None, candidates=False):
    import ArchSpace

    boundaries = normalize_boundaries(boundaries)
    if candidates:
        report = ArchSpace.getBoundaryRegionCandidates(
            boundaries,
            label=label,
            seed_space=seed_space,
        )
    else:
        report = ArchSpace.analyzeBoundaryLinks(
            boundaries,
            label=label,
            seed_space=seed_space,
        )
    return SpaceBoundaryEvaluation.from_report(boundaries, report)


def has_valid_geometry(space):
    if space is None:
        return False
    try:
        shape = space.Shape
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


def set_boundaries(document, space, boundaries, *, transaction_name="Edit Space Boundaries"):
    import ArchSpace

    boundaries = normalize_boundaries(boundaries)
    document.openTransaction(transaction_name)
    try:
        ArchSpace.setBoundaryLinks(space, list(boundaries))
        document.recompute()
        if not has_valid_geometry(space):
            raise SpaceSemanticError("The space geometry is invalid.")
        document.commitTransaction()
    except Exception:
        document.abortTransaction()
        raise
    return space


def reassign_region(
    document,
    space,
    sample_point,
    *,
    boundaries=(),
    transaction_name="Reassign Space Region",
):
    import ArchSpace

    if space is None or sample_point is None:
        raise SpaceSemanticError("A space and region point are required.")
    boundaries = normalize_boundaries(boundaries)
    document.openTransaction(transaction_name)
    try:
        if boundaries:
            ArchSpace.setBoundaryLinks(space, list(boundaries))
        ArchSpace.setBoundaryRegionReferencePoint(space, sample_point)
        space.touch()
        document.recompute()
        if not has_valid_geometry(space) or str(getattr(space, "BoundaryStatus", "")) == "Conflict":
            raise SpaceSemanticError("The selected region is not valid for this space.")
        document.commitTransaction()
    except Exception:
        document.abortTransaction()
        raise
    return space
