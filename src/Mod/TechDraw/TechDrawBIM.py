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


def fill_representations_to_svg(representations, direction, style, drawing_scale=1.0):
    """Render semantic cut faces with deduplicated paper-space styles."""
    import Draft
    from ArchRepresentation import CutFillMode, cut_surface_style_for

    entries = []
    for representation in representations:
        for geometry in getattr(representation, "cut_geometry", ()):
            if getattr(geometry, "ShapeType", "") != "Face":
                continue
            mapping = representation.mapping_for(geometry)
            resolved = cut_surface_style_for(mapping, style)
            entries.append((geometry, resolved))
    patterns = {}
    definitions = []
    fragments = []
    for geometry, resolved in entries:
        fill = Draft.getrgb(resolved.color, testbw=False)
        if resolved.mode == CutFillMode.MATERIAL:
            key = (
                resolved.pattern_kind,
                resolved.pattern_data,
                resolved.spacing,
                resolved.angle,
                resolved.line_color,
                resolved.line_weight,
            )
            pattern_id = patterns.get(key)
            if pattern_id is None:
                pattern_id = "bim-cut-pattern-{}".format(len(patterns) + 1)
                patterns[key] = pattern_id
                model_per_paper = 1.0 / max(float(drawing_scale), 1e-9)
                definitions.append(
                    _svg_pattern_definition(
                        pattern_id, resolved, fill, model_per_paper, Draft
                    )
                )
            fill = "url(#{})".format(pattern_id)
        fragment = Draft.get_svg(
            geometry,
            linewidth=0,
            fillstyle=fill,
            direction=direction.negative(),
            color=resolved.color,
        )
        fragments.append(fragment)
    if not fragments:
        return ""
    defs = "<defs>{}</defs>\n".format("".join(definitions)) if definitions else ""
    return '{}<g transform="rotate(180)">\n{}\n</g>\n'.format(
        defs, "".join(fragments)
    )


def _svg_pattern_definition(pattern_id, style, background, model_per_paper, Draft):
    """Translate an official FreeCAD PAT or Pattern File appearance to SVG."""
    if style.pattern_kind == "SVG":
        import os
        import re

        pattern_data = style.pattern_data
        if "<" not in pattern_data and os.path.isfile(pattern_data):
            with open(pattern_data, encoding="utf-8") as pattern_file:
                pattern_data = pattern_file.read()
        match = re.search(r"<pattern\b[^>]*>.*?</pattern>", pattern_data, re.DOTALL)
        if match:
            pattern = re.sub(
                r'id=["\'][^"\']+["\']', 'id="{}"'.format(pattern_id), match.group(0), count=1
            )
            scale = max(style.spacing, 1e-9) * model_per_paper
            line = Draft.getrgb(style.line_color, testbw=False)
            pattern = pattern.replace("#000000", line).replace("stroke:black", "stroke:" + line)
            pattern = pattern.replace(
                ">",
                '><rect width="100%" height="100%" fill="{}"/>'.format(background),
                1,
            )
            pattern = pattern.replace(
                "<pattern ",
                '<pattern patternTransform="scale({}) rotate({})" '.format(
                    scale, style.angle
                ),
                1,
            )
            return pattern

    families = _parse_pat_families(style.pattern_data)
    scale = max(style.spacing, 1e-9) * model_per_paper
    line = Draft.getrgb(style.line_color, testbw=False)
    weight = max(style.line_weight, 0.01) * model_per_paper
    tile = max((abs(family[4]) for family in families), default=1.0) * scale
    tile = max(tile, scale)
    paths = []
    for angle, origin_x, origin_y, _delta_x, _delta_y, dashes in families:
        dash = ""
        positive = [abs(value) * scale for value in dashes if value]
        if positive:
            dash = ' stroke-dasharray="{}"'.format(
                ",".join(str(value) for value in positive)
            )
        paths.append(
            '<path d="M {} {} L {} {}" transform="rotate({} {} {})" '
            'stroke="{}" stroke-width="{}"{} />'.format(
                origin_x * scale,
                origin_y * scale - tile * 2,
                origin_x * scale,
                origin_y * scale + tile * 3,
                angle + style.angle,
                origin_x * scale,
                origin_y * scale,
                line,
                weight,
                dash,
            )
        )
    return (
        '<pattern id="{}" patternUnits="userSpaceOnUse" width="{}" height="{}">'
        '<rect width="100%" height="100%" fill="{}"/>{}</pattern>'
    ).format(pattern_id, tile, tile, background, "".join(paths))


def _parse_pat_families(data):
    """Parse PAT line-family records, ignoring headers and comments."""
    families = []
    for raw_line in str(data or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("*", ";")):
            continue
        try:
            values = [float(value.strip()) for value in line.split(",")]
        except ValueError:
            continue
        if len(values) >= 5:
            families.append((*values[:5], tuple(values[5:])))
    return tuple(families)


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
