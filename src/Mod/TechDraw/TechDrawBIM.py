# SPDX-License-Identifier: LGPL-2.1-or-later

"""TechDraw adapters for semantic BIM representations.

This module deliberately keeps the BIM contract at the boundary: callers
provide a ``BIMRepresentation`` and TechDraw projects its selected geometry.
No temporary Draft or TechDraw document objects are created.
"""


def _shape_from_geometry(geometries):
    """Return one shape suitable for TechDraw projection, or ``None``."""
    import Part

    shapes = []
    for geometry in geometries:
        if hasattr(geometry, "ShapeType"):
            shapes.append(geometry)
            continue
        try:
            points = list(geometry)
        except TypeError:
            continue
        if len(points) >= 2:
            shapes.append(Part.makePolygon(points))
    if not shapes:
        return None
    if len(shapes) == 1:
        return shapes[0]

    return Part.makeCompound(shapes)


def _geometry(representation, collection):
    return _shape_from_geometry(getattr(representation, collection, ()))


def _geometry_by_role(representation, collection):
    grouped = {}
    for geometry in getattr(representation, collection, ()):
        mapping = representation.mapping_for(geometry)
        grouped.setdefault(getattr(mapping, "role", None), []).append(geometry)
    return {
        role: shape
        for role, geometries in grouped.items()
        if (shape := _shape_from_geometry(geometries)) is not None
    }


def project_representation_to_svg(
    representation,
    direction,
    collection="projected_geometry",
    role_styles=None,
    **styles,
):
    """Project one semantic BIM representation to SVG.

    ``collection`` may be ``cut_geometry``, ``projected_geometry`` or
    ``snap_geometry``.  The latter is useful for documentation diagnostics,
    but normal drawings should use projected or cut geometry.
    """
    import TechDraw

    if not role_styles:
        shape = _geometry(representation, collection)
        return "" if shape is None else TechDraw.projectToSVG(shape, direction, **styles)

    fragments = []
    for role, shape in _geometry_by_role(representation, collection).items():
        role_style = dict(styles)
        role_style.update(role_styles.get(role, {}))
        fragments.append(TechDraw.projectToSVG(shape, direction, **role_style))
    return "".join(fragments)


def fill_representation_to_svg(representation, direction, style):
    """Render closed semantic cut faces with a uniform SVG fill."""
    import Draft

    fragments = []
    for geometry in getattr(representation, "cut_geometry", ()):
        if getattr(geometry, "ShapeType", "") != "Face":
            continue
        fragments.append(
            Draft.get_svg(
                geometry,
                linewidth=0,
                fillstyle=Draft.getrgb(style.color, testbw=False),
                direction=direction.negative(),
                color=style.color,
            )
        )
    if not fragments:
        return ""
    return '<g transform="rotate(180)">\n{}\n</g>\n'.format("".join(fragments))


def project_object_to_svg(obj, context, direction, collection="projected_geometry", **styles):
    """Request an object's representation and project it with TechDraw."""
    from ArchRepresentation import view_representation_for

    representation = view_representation_for(obj, context)
    return project_representation_to_svg(
        representation,
        direction,
        collection=collection,
        **styles,
    )
