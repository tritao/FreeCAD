# SPDX-License-Identifier: LGPL-2.1-or-later
"""Viewer-independent construction service for semantic BIM spaces."""


class SpaceConstructionError(RuntimeError):
    pass


def _copy_shape(shape):
    try:
        return shape.copy(noElementMap=True)
    except Exception:
        return shape.copy()


def create_region_base(document, shape):
    if document is None or shape is None or shape.isNull():
        raise SpaceConstructionError("A valid closed space region is required.")
    base = document.addObject("Part::Feature", "SpaceRegionBase")
    base.Shape = _copy_shape(shape)
    view_object = getattr(base, "ViewObject", None)
    for name, value in (("Visibility", False), ("ShowInTree", False), ("Selectable", False)):
        if view_object is not None and hasattr(view_object, name):
            setattr(view_object, name, value)
    return base


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
        base = create_region_base(document, base_shape)
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


def construct_space_from_candidate(document, candidate, **kwargs):
    if not isinstance(candidate, dict):
        raise SpaceConstructionError("A valid space-region candidate is required.")
    return construct_space(
        document,
        candidate.get("shape"),
        sample_point=candidate.get("sample_point"),
        **kwargs,
    )


def construct_space_from_boundaries(
    document,
    boundaries,
    *,
    transaction_name="Create Space",
    add_to_container=None,
    validate=None,
):
    import Arch

    boundaries = list(boundaries or ())
    if not boundaries:
        raise SpaceConstructionError("Space boundaries are required.")
    document.openTransaction(transaction_name)
    try:
        space = Arch.makeSpace(boundaries)
        if space is None:
            raise SpaceConstructionError("Unable to create space.")
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


def construct_space_from_selection(
    document,
    selection,
    *,
    transaction_name="Create Space",
    auto_group=True,
    validate=None,
):
    """Construct a space from command-resolved SelectionEx entries."""

    import FreeCAD

    def add_to_container(space):
        if auto_group and FreeCAD.GuiUp:
            import Draft

            Draft.autogroup(space)

    return construct_space_from_boundaries(
        document,
        selection,
        transaction_name=transaction_name,
        add_to_container=add_to_container,
        validate=validate,
    )
