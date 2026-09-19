# SPDX-License-Identifier: LGPL-2.1-or-later

"""Render semantic BIM representations through TechDraw's generic API.

This module deliberately keeps the BIM contract at the boundary: callers
provide a ``BIMRepresentation`` and TechDraw projects its selected geometry.
No temporary Draft or TechDraw document objects are created.
"""


def representations_for_context(
    context,
    objects,
    *,
    show_hidden=False,
    fill_spaces=False,
    join_arch=False,
):
    """Resolve an all-semantic TechDraw representation set, or return ``()``.

    Mixed semantic/legacy projection is intentionally unsupported.  Returning
    an empty tuple asks the public Arch compatibility adapter to use its
    established shape renderer for the complete drawing.
    """
    if (
        show_hidden
        or fill_spaces
        or join_arch
        or not objects
        or context.request is None
    ):
        return ()

    from ArchRepresentation import (
        RepresentationPurpose,
        RepresentationUnavailable,
        view_representation_for,
    )

    # Relation-only BIM objects (for example WallJoint) are included when a
    # building part scope is expanded, but they do not contribute drawable
    # geometry. They must not make an otherwise fully semantic scope fall
    # back to the legacy shape exporter.
    render_objects = []
    for obj in objects:
        has_shape = hasattr(obj, "Shape")
        proxy = getattr(obj, "Proxy", None)
        has_provider = callable(getattr(proxy, "getRepresentation", None))
        view_proxy = getattr(getattr(obj, "ViewObject", None), "Proxy", None)
        has_provider = has_provider or callable(
            getattr(view_proxy, "getRepresentation", None)
        )
        if has_shape or has_provider:
            render_objects.append(obj)
    objects = tuple(render_objects)

    if context.request.purpose == RepresentationPurpose.ELEVATION:
        import ArchSectionProjection

        projected = ArchSectionProjection.project_elevation_scope(objects, context.request)
        representations = tuple(projected[obj] for obj in objects)
        if not any(item.projected_geometry for item in representations):
            return ()
        return representations

    representations = []
    for obj in objects:
        try:
            representation = view_representation_for(obj, context.request)
        except RepresentationUnavailable:
            return ()
        if not (
            getattr(representation, "cut_geometry", None)
            or getattr(representation, "projected_geometry", None)
        ):
            return ()
        representations.append(representation)
    return tuple(representations)


def cut_face_bounds(representations):
    """Return a cheap compound of semantic cut faces for symbol filtering."""
    import Part

    faces = [
        geometry
        for representation in representations
        for geometry in getattr(representation, "cut_geometry", ())
        if getattr(geometry, "ShapeType", "") == "Face"
    ]
    if not faces:
        return None
    return faces[0] if len(faces) == 1 else Part.makeCompound(faces)


def render_representations_to_svg(
    representations,
    direction,
    cut_surface_style,
    *,
    drawing_scale,
    line_width,
    elevation=False,
):
    """Render a complete semantic BIM representation set for TechDraw."""
    style = {
        "stroke": "SVGLINECOLOR",
        # The native semantic path exporter preserves connected corners. A
        # bevel prevents acute wall joins from growing a paper-space spike.
        "stroke-linecap": "butt",
        "stroke-linejoin": "bevel",
        "stroke-width": "SVGLINEWIDTH",
    }
    cut_style = {
        "stroke": "SVGLINECOLOR",
        "stroke-linecap": "butt",
        "stroke-linejoin": "bevel",
        "stroke-width": "SVGCUTLINEWIDTH",
    }
    joined_cut_style = dict(cut_style)
    joined_cut_style["stroke-linejoin"] = "miter"
    elevation_role_styles = {}
    visible_style = style
    if elevation:
        request = getattr(
            getattr(representations[0], "request", None),
            "presentation_profile",
            {},
        ) or {}
        visible_width = float(request.get("visible_line_width", 1.0))
        silhouette_width = float(request.get("silhouette_line_width", 1.35))
        visible_style = dict(style)
        silhouette_style = dict(style)
        if visible_width != 1.0:
            visible_style["stroke-width"] = "{}px".format(line_width * visible_width)
        silhouette_style["stroke-width"] = "{}px".format(
            line_width * silhouette_width
        )
        elevation_role_styles = {
            "ProjectionSilhouette": {
                name: silhouette_style
                for name in ("hStyle", "h0Style", "h1Style", "vStyle", "v0Style", "v1Style")
            }
        }

    fragments = []
    from ArchRepresentation import CutFillMode

    if cut_surface_style.mode != CutFillMode.NONE:
        fragments.append(
            fill_representations_to_svg(
                representations,
                direction,
                cut_surface_style,
                drawing_scale=drawing_scale,
            )
        )
    if any(representation.projected_geometry for representation in representations):
        fragments.append(
            project_representations_to_svg(
                representations,
                direction,
                collection="projected_geometry",
                hStyle=visible_style,
                h0Style=visible_style,
                h1Style=visible_style,
                vStyle=visible_style,
                v0Style=visible_style,
                v1Style=visible_style,
                role_styles=elevation_role_styles,
                include_joint_lines=True,
            )
        )
    if any(representation.cut_geometry for representation in representations):
        if elevation_role_styles:
            fragments.append(
                project_representations_to_svg(
                    representations,
                    direction,
                    collection="cut_geometry",
                    hStyle=cut_style,
                    h0Style=cut_style,
                    h1Style=cut_style,
                    vStyle=cut_style,
                    v0Style=cut_style,
                    v1Style=cut_style,
                    include_joint_lines=True,
                )
            )
        else:
            normal_entries, joined_entries = _joined_cut_projection_entries(representations)
            if not joined_entries:
                fragments.append(
                    project_representations_to_svg(
                        representations,
                        direction,
                        collection="cut_geometry",
                        hStyle=cut_style,
                        h0Style=cut_style,
                        h1Style=cut_style,
                        vStyle=cut_style,
                        v0Style=cut_style,
                        v1Style=cut_style,
                        include_joint_lines=True,
                    )
                )
            else:
                if normal_entries:
                    fragments.append(
                        _project_entries_to_svg(
                            normal_entries,
                            direction,
                            {},
                            {
                                "hStyle": cut_style,
                                "h0Style": cut_style,
                                "h1Style": cut_style,
                                "vStyle": cut_style,
                                "v0Style": cut_style,
                                "v1Style": cut_style,
                            },
                        )
                    )
                joined_svg = _project_joined_wall_boundaries_to_svg(
                    representations,
                    direction,
                    joined_cut_style,
                )
                fragments.append(
                    joined_svg
                    or _project_entries_to_svg(
                        joined_entries,
                        direction,
                        {},
                        {
                            "hStyle": joined_cut_style,
                            "h0Style": joined_cut_style,
                            "h1Style": joined_cut_style,
                            "vStyle": joined_cut_style,
                            "v0Style": joined_cut_style,
                            "v1Style": joined_cut_style,
                        },
                    )
                )
    return "".join(fragments)


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


def _point_key(point):
    """Return a stable key for one projected semantic point."""

    tolerance = 1.0e-7
    return tuple(round(float(getattr(point, axis)) / tolerance) for axis in "xyz")


def _segment_key(first, second):
    """Return an orientation-independent key for a straight segment."""

    endpoints = (_point_key(first), _point_key(second))
    return tuple(sorted(endpoints))


def _boundary_graph_paths(representations, indices):
    """Build continuous wall-boundary cycles with joint seams removed."""

    seam_keys = set()
    boundary_edges = {}
    for index in indices:
        representation = representations[index]
        for geometry in getattr(representation, "projected_geometry", ()):
            mapping = representation.mapping_for(geometry)
            role = getattr(mapping, "role", None)
            if role not in {"PlanCutOuterBoundary", "WallJointCutLine"}:
                continue
            if hasattr(geometry, "ShapeType"):
                continue
            points = list(geometry)
            if len(points) < 2:
                continue
            if role == "WallJointCutLine":
                for first, second in zip(points, points[1:]):
                    if _point_key(first) != _point_key(second):
                        seam_keys.add(_segment_key(first, second))
                continue
            for first, second in zip(points, points[1:]):
                if _point_key(first) == _point_key(second):
                    continue
                key = _segment_key(first, second)
                if key not in seam_keys:
                    boundary_edges.setdefault(key, (first, second))

    if not boundary_edges:
        return ()

    # Boundary edges may be encountered before their matching joint seam.
    # Remove those shared seam edges after collecting both geometry roles.
    boundary_edges = {
        key: edge for key, edge in boundary_edges.items() if key not in seam_keys
    }
    adjacency = {}
    for edge_index, (first, second) in enumerate(boundary_edges.values()):
        first_key = _point_key(first)
        second_key = _point_key(second)
        adjacency.setdefault(first_key, []).append((edge_index, second_key))
        adjacency.setdefault(second_key, []).append((edge_index, first_key))
    if any(len(edges) != 2 for edges in adjacency.values()):
        return ()

    edges = tuple(boundary_edges.values())
    paths = []
    visited = set()
    for start_index, (first, second) in enumerate(edges):
        if start_index in visited:
            continue
        start_key = _point_key(first)
        current_key = start_key
        previous_index = None
        points = []
        while True:
            candidates = [
                (edge_index, next_key)
                for edge_index, next_key in adjacency[current_key]
                if edge_index != previous_index and edge_index not in visited
            ]
            if not candidates:
                return ()
            edge_index, next_key = candidates[0]
            visited.add(edge_index)
            edge_first, edge_second = edges[edge_index]
            if not points:
                points.append(
                    edge_first
                    if _point_key(edge_first) == current_key
                    else edge_second
                )
            points.append(
                edge_second
                if _point_key(edge_first) == current_key
                else edge_first
            )
            previous_index = edge_index
            current_key = next_key
            if current_key == start_key:
                break
        if len(points) >= 4:
            paths.append(tuple(points[:-1]))
    return tuple(paths) if len(visited) == len(edges) else ()


def _project_joined_wall_boundaries_to_svg(
    representations, direction, style
):
    """Render joined wall boundaries as continuous stroked SVG paths."""

    components = _wall_joint_components(representations)
    if not components:
        return ""

    # ``components`` maps each member index to its connected component.  The
    # values are normalized so each component is rendered exactly once even
    # when several members point at the same tuple.
    groups = tuple(sorted({tuple(sorted(value)) for value in components.values()}))
    fragments = []
    for indices in groups:
        paths = _boundary_graph_paths(representations, indices)
        if not paths:
            return ""
        for points in paths:
            import Part

            try:
                wire = Part.makePolygon((*points, points[0]))
                face = Part.Face(wire)
            except Exception:
                return ""
            fragment = _project_shape_to_svg(
                face,
                direction,
                {"hStyle": style, "vStyle": style},
            )
            if not fragment:
                return ""
            fragments.append(fragment)

        seam_entries = []
        seen_seams = set()
        for index in indices:
            representation = representations[index]
            for geometry in getattr(representation, "projected_geometry", ()):
                if hasattr(geometry, "ShapeType"):
                    continue
                mapping = representation.mapping_for(geometry)
                if getattr(mapping, "role", None) != "WallJointCutLine":
                    continue
                key = _segment_key(geometry[0], geometry[-1])
                if key in seen_seams:
                    continue
                seen_seams.add(key)
                seam_entries.append((representation, geometry))
        if seam_entries:
            fragments.append(
                _project_entries_to_svg(
                    seam_entries,
                    direction,
                    {},
                    {
                        "hStyle": style,
                        "h0Style": style,
                        "h1Style": style,
                        "vStyle": style,
                        "v0Style": style,
                        "v1Style": style,
                    },
                )
            )
    return "".join(fragments)


def _project_shape_to_svg(shape, direction, styles):
    """Use TechDraw's connected-path exporter for linear semantic geometry."""
    import TechDraw

    path_style = styles.get("hStyle") or styles.get("vStyle") or {}
    path_svg = TechDraw.projectToSVGPath(shape, direction, path_style)
    if path_svg:
        return path_svg
    return TechDraw.projectToSVG(shape, direction, **styles)


def _project_entries_to_svg(entries, direction, role_styles, styles):
    if not role_styles:
        shape = _shape_from_geometry([geometry for _, geometry in entries])
        return "" if shape is None else _project_shape_to_svg(shape, direction, styles)

    grouped = {}
    for representation, geometry in entries:
        mapping = representation.mapping_for(geometry)
        grouped.setdefault(getattr(mapping, "role", None), []).append(geometry)

    fragments = []
    for role, geometries in grouped.items():
        shape = _shape_from_geometry(geometries)
        if shape is None:
            continue
        role_style = dict(styles)
        role_style.update(role_styles.get(role, {}))
        fragments.append(_project_shape_to_svg(shape, direction, role_style))
    return "".join(fragments)


def _representation_entries(representations, collection):
    return [
        (representation, geometry)
        for representation in representations
        for geometry in getattr(representation, collection, ())
    ]


def _wall_joint_components(representations):
    """Return representation groups connected by the same wall joint."""
    parents = list(range(len(representations)))
    joint_owner = {}

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def join(first, second):
        first_root = find(first)
        second_root = find(second)
        if first_root != second_root:
            parents[second_root] = first_root

    for index, representation in enumerate(representations):
        for geometry in getattr(representation, "projected_geometry", ()):
            mapping = representation.mapping_for(geometry)
            if getattr(mapping, "role", None) != "WallJointCutLine":
                continue
            for joint in getattr(mapping, "related_sources", ()) or ():
                key = id(joint)
                owner = joint_owner.get(key)
                if owner is None:
                    joint_owner[key] = index
                else:
                    join(index, owner)

    groups = {}
    for index in range(len(representations)):
        groups.setdefault(find(index), []).append(index)
    return {
        index: tuple(members)
        for members in groups.values()
        if len(members) > 1
        for index in members
    }


def _split_fused_cut_faces(entries, representations, components):
    """Split regular entries from fused faces belonging to wall joints."""
    if not components:
        return entries, []

    representation_indices = {
        id(representation): index for index, representation in enumerate(representations)
    }
    grouped = {}
    remaining = []
    joined_entries = []
    for representation, geometry in entries:
        index = representation_indices.get(id(representation))
        mapping = representation.mapping_for(geometry)
        if (
            index is None
            or index not in components
            or getattr(geometry, "ShapeType", "") != "Face"
            or getattr(mapping, "role", None) != "PlanCutFace"
        ):
            remaining.append((representation, geometry))
            continue
        material_key = tuple(
            id(source) for source in getattr(mapping, "related_sources", ()) or ()
        )
        grouped.setdefault((components[index], material_key), []).append(
            (representation, geometry)
        )

    for face_entries in grouped.values():
        if len(face_entries) == 1:
            remaining.extend(face_entries)
            continue
        joined = face_entries[0][1]
        try:
            for _representation, face in face_entries[1:]:
                joined = joined.fuse(face)
            joined = joined.removeSplitter()
        except Exception:
            joined = None
        if joined is None or joined.isNull():
            remaining.extend(face_entries)
        else:
            joined_entries.append((face_entries[0][0], joined))
    return remaining, joined_entries


def _fuse_cut_faces(entries, representations, components):
    """Fuse only coplanar cut faces belonging to one wall-joint component."""
    remaining, joined_entries = _split_fused_cut_faces(
        entries, representations, components
    )
    return remaining + joined_entries


def _joined_cut_projection_entries(representations):
    """Return regular cut entries and joined-wall entries for separate styling."""
    components = _wall_joint_components(representations)
    entries = _representation_entries(representations, "cut_geometry")
    normal_entries, joined_entries = _split_fused_cut_faces(
        entries, representations, components
    )
    if components:
        joined_entries.extend(
            (representation, geometry)
            for representation in representations
            for geometry in getattr(representation, "projected_geometry", ())
            if getattr(representation.mapping_for(geometry), "role", None)
            == "WallJointCutLine"
        )
    return normal_entries, joined_entries


def _prepared_projection_entries(
    representations,
    collection,
    *,
    include_joint_lines=False,
    role_styles=None,
):
    """Prepare sheet linework without merging unrelated semantic objects."""
    entries = _representation_entries(representations, collection)
    if role_styles:
        return entries

    components = _wall_joint_components(representations)
    if not components:
        return entries

    if collection == "projected_geometry":
        joined_indices = set(components)
        representation_indices = {
            id(representation): index
            for index, representation in enumerate(representations)
        }
        result = []
        for representation, geometry in entries:
            index = representation_indices[id(representation)]
            mapping = representation.mapping_for(geometry)
            role = getattr(mapping, "role", None)
            if index in joined_indices and role == "PlanCutOuterBoundary":
                continue
            if index in joined_indices and role == "WallJointCutLine" and include_joint_lines:
                continue
            result.append((representation, geometry))
        return result

    if collection == "cut_geometry":
        if include_joint_lines:
            entries.extend(
                (representation, geometry)
                for representation in representations
                for geometry in getattr(representation, "projected_geometry", ())
                if getattr(representation.mapping_for(geometry), "role", None)
                == "WallJointCutLine"
            )
        return _fuse_cut_faces(entries, representations, components)

    return entries


def project_representations_to_svg(
    representations,
    direction,
    collection="projected_geometry",
    role_styles=None,
    include_joint_lines=False,
    **styles,
):
    """Project one semantic collection across all representations as one graph."""
    entries = _prepared_projection_entries(
        representations,
        collection,
        include_joint_lines=include_joint_lines,
        role_styles=role_styles,
    )
    return _project_entries_to_svg(entries, direction, role_styles, styles)


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
    return project_representations_to_svg(
        (representation,),
        direction,
        collection=collection,
        role_styles=role_styles,
        **styles,
    )


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
