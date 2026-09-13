# SPDX-License-Identifier: LGPL-2.1-or-later
"""Viewer-independent construction services for straight BIM walls."""

from dataclasses import dataclass

import FreeCAD


MINIMUM_WALL_LENGTH = 10.0
VALID_ALIGNMENTS = frozenset(("Center", "Left", "Right"))


class WallConstructionError(ValueError):
    """Raised when a wall construction candidate is invalid."""


@dataclass(frozen=True)
class WallConstructionSpec:
    width: float
    height: float
    align: str = "Center"
    offset: float = 0.0
    material: object = None

    def validated(self):
        width = float(self.width)
        height = float(self.height)
        align = str(self.align)
        if width <= 0.0:
            raise WallConstructionError("Wall width must be greater than zero.")
        if height <= 0.0:
            raise WallConstructionError("Wall height must be greater than zero.")
        if align not in VALID_ALIGNMENTS:
            raise WallConstructionError("Unsupported wall alignment: {}".format(align))
        return WallConstructionSpec(width, height, align, float(self.offset), self.material)


def wall_segments(points, *, closed=False, minimum_length=MINIMUM_WALL_LENGTH):
    """Validate ordered global points and return immutable wall segments."""

    candidates = tuple(FreeCAD.Vector(point) for point in tuple(points or ()))
    if len(candidates) < 2:
        raise WallConstructionError("At least two wall points are required.")
    pairs = list(zip(candidates, candidates[1:]))
    if closed:
        if len(candidates) < 3:
            raise WallConstructionError("A closed wall run requires at least three points.")
        pairs.append((candidates[-1], candidates[0]))
    for start, end in pairs:
        if end.sub(start).Length < float(minimum_length):
            raise WallConstructionError(
                "Wall segments must be at least {:g} mm long.".format(minimum_length)
            )
    return tuple(pairs)


def create_wall_segment(
    start,
    end,
    spec,
    *,
    auto_group=True,
    on_created=None,
    minimum_length=MINIMUM_WALL_LENGTH,
):
    """Create one validated baseless wall segment from global endpoints."""

    import Arch

    spec = spec.validated()
    start, end = wall_segments(
        (start, end), minimum_length=minimum_length
    )[0]
    line_vector = end.sub(start)
    length = line_vector.Length
    midpoint = (start + end) * 0.5
    direction = line_vector.normalize()
    wall = Arch.makeWall(
        length=length,
        width=spec.width,
        height=spec.height,
        align=spec.align,
        offset=spec.offset,
    )
    wall.Placement = FreeCAD.Placement(
        midpoint, FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), direction)
    )
    if spec.material is not None:
        wall.Material = spec.material
    if auto_group and FreeCAD.GuiUp:
        try:
            import Draft

            Draft.autogroup(wall)
        except Exception:
            pass
    if on_created:
        on_created(wall)
    return wall


def create_wall_from_base(base, spec, *, normal=None, auto_group=True, on_created=None):
    """Create one wall from an existing path through the shared domain policy."""

    import Arch

    if base is None:
        raise WallConstructionError("A wall path object is required.")
    spec = spec.validated()
    wall = Arch.makeWall(
        base,
        width=spec.width,
        height=spec.height,
        align=spec.align,
        offset=spec.offset,
    )
    if normal is not None:
        wall.Normal = FreeCAD.Vector(normal)
    if spec.material is not None:
        wall.Material = spec.material
    if auto_group and FreeCAD.GuiUp:
        try:
            import Draft

            Draft.autogroup(wall)
        except Exception:
            pass
    if on_created:
        on_created(wall)
    return wall


def create_wall_run(
    points,
    spec,
    *,
    closed=False,
    auto_group=True,
    on_created=None,
    minimum_length=MINIMUM_WALL_LENGTH,
):
    """Create a validated run without owning the caller's transaction."""

    segments = wall_segments(
        points, closed=closed, minimum_length=minimum_length
    )
    return tuple(
        create_wall_segment(
            start,
            end,
            spec,
            auto_group=auto_group,
            on_created=on_created,
            minimum_length=minimum_length,
        )
        for start, end in segments
    )


def autojoin_wall_run(walls, *, closed=False):
    """Apply the standard non-destructive autojoin policy to a wall run."""

    import Arch
    from draftutils import params

    walls = tuple(walls or ())
    if len(walls) < 2 or not params.get_param_arch("autoJoinWalls"):
        return
    host = walls[0]
    if closed:
        additions = [wall for wall in walls[1:] if wall is not host]
        if additions:
            Arch.addComponents(additions, host)
        return
    for wall in walls[1:]:
        if wall is host:
            continue
        Arch.addComponents(wall, host)
        host = wall


def construct_wall_run(
    document,
    points,
    spec,
    *,
    transaction_name,
    closed=False,
    auto_group=True,
    auto_join=True,
    on_created=None,
):
    """Validate and atomically commit a complete wall run."""

    wall_segments(points, closed=closed)
    spec = spec.validated()
    document.openTransaction(transaction_name)
    try:
        walls = create_wall_run(
            points,
            spec,
            closed=closed,
            auto_group=auto_group,
            on_created=on_created,
        )
        if auto_join:
            autojoin_wall_run(walls, closed=closed)
        document.commitTransaction()
        document.recompute()
        return walls
    except Exception:
        try:
            document.abortTransaction()
        except Exception:
            pass
        raise
