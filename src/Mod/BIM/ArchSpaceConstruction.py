# SPDX-License-Identifier: LGPL-2.1-or-later
"""Viewer-independent construction service for semantic BIM spaces."""


class SpaceConstructionError(RuntimeError):
    pass


def construct_space(
    document,
    base_shape,
    *,
    sample_point=None,
    boundaries=(),
    transaction_name="Create Space",
    add_to_container=None,
    validate=None,
):
    import Arch
    import ArchSpace

    if document is None or base_shape is None or base_shape.isNull():
        raise SpaceConstructionError("A valid closed space region is required.")
    document.openTransaction(transaction_name)
    try:
        base = document.addObject("Part::Feature", "SpaceRegionBase")
        base.Shape = base_shape.copy()
        for name, value in (("Visibility", False), ("ShowInTree", False), ("Selectable", False)):
            if hasattr(base.ViewObject, name):
                setattr(base.ViewObject, name, value)
        space = Arch.makeSpace(base)
        if space is None:
            raise SpaceConstructionError("Unable to create space.")
        if sample_point is not None:
            ArchSpace.setBoundaryRegionReferencePoint(space, sample_point)
        if boundaries:
            ArchSpace.setBoundaryLinks(space, list(boundaries))
        if add_to_container:
            add_to_container(space)
        document.recompute()
        if validate and not validate(space):
            raise SpaceConstructionError("The space geometry is invalid.")
        document.commitTransaction()
        return space
    except Exception:
        document.abortTransaction()
        raise
