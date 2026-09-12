# SPDX-License-Identifier: LGPL-2.1-or-later

"""TechDraw adapters for semantic BIM representations.

This module deliberately keeps the BIM contract at the boundary: callers
provide a ``BIMRepresentation`` and TechDraw projects its selected geometry.
No temporary Draft or TechDraw document objects are created.
"""


def _geometry(representation, collection):
    """Return one shape suitable for TechDraw projection, or ``None``."""
    geometries = list(getattr(representation, collection, ()))
    if not geometries:
        return None
    if len(geometries) == 1:
        return geometries[0]

    import Part

    return Part.makeCompound(geometries)


def project_representation_to_svg(
    representation,
    direction,
    collection="projected_geometry",
    **styles,
):
    """Project one semantic BIM representation to SVG.

    ``collection`` may be ``cut_geometry``, ``projected_geometry`` or
    ``snap_geometry``.  The latter is useful for documentation diagnostics,
    but normal drawings should use projected or cut geometry.
    """
    shape = _geometry(representation, collection)
    if shape is None:
        return ""

    import TechDraw

    return TechDraw.projectToSVG(shape, direction, **styles)


def project_object_to_svg(obj, context, direction, collection="projected_geometry", **styles):
    """Request an object's representation and project it with TechDraw."""
    from ArchRepresentation import representation_for

    representation = representation_for(obj, context)
    return project_representation_to_svg(
        representation,
        direction,
        collection=collection,
        **styles,
    )
