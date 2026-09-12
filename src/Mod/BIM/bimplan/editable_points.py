# SPDX-License-Identifier: LGPL-2.1-or-later

"""Object-owned point adapters for contextual BIM editing."""

from dataclasses import dataclass

import FreeCAD


@dataclass(frozen=True)
class ContextualEditPoint:
    """One globally positioned point whose owner controls mutation."""

    point: object
    property_name: str
    subelement: str
    get_value: object
    apply_value: object
    available: object = None
    semantic_id: str = ""

    def is_available(self):
        return True if self.available is None else bool(self.available())


def get_contextual_edit_points(owner, context=None):
    """Return supported editable points without exposing owner details to BIM objects."""

    if owner is None:
        return ()
    proxy_points = _get_proxy_points(owner, context)
    if proxy_points is not None:
        return proxy_points
    if getattr(owner, "TypeId", "") == "Sketcher::SketchObject":
        return _get_sketch_points(owner)
    return ()


def _get_proxy_points(owner, context):
    proxy = getattr(owner, "Proxy", None)
    get_points = getattr(proxy, "getContextualEditPoints", None)
    set_point = getattr(proxy, "setContextualEditPoint", None)
    if not callable(get_points) or not callable(set_point):
        return None
    points = tuple(get_points(owner, context) or ())
    return tuple(
        ContextualEditPoint(
            point=FreeCAD.Vector(point),
            property_name="Points[{}]".format(index),
            subelement="Vertex{}".format(index + 1),
            get_value=lambda owner=owner, index=index: owner.getGlobalPlacement().multVec(
                owner.Points[index]
            ),
            apply_value=lambda value, owner=owner, index=index: set_point(owner, index, value),
        )
        for index, point in enumerate(points)
    )


def _get_sketch_points(sketch):
    if sketch.FullyConstrained:
        return ()
    placement = sketch.getGlobalPlacement()
    blocked_geometry = {
        constraint.First
        for constraint in sketch.Constraints
        if constraint.Type == "Block" and constraint.First >= 0
    }
    vertex_keys = []
    for geometry_index, geometry in enumerate(sketch.Geometry):
        if hasattr(geometry, "StartPoint"):
            vertex_keys.append((geometry_index, 1))
        if hasattr(geometry, "EndPoint"):
            vertex_keys.append((geometry_index, 2))
    groups = _coincident_groups(vertex_keys, sketch.Constraints)
    points = []
    for group in groups:
        key = group[0]
        if any(geometry_index in blocked_geometry for geometry_index, _position in group):
            continue

        def get_value(sketch=sketch, key=key):
            local = sketch.getPoint(*key)
            return sketch.getGlobalPlacement().multVec(local)

        def apply_value(value, sketch=sketch, group=group):
            local = sketch.getGlobalPlacement().inverse().multVec(FreeCAD.Vector(value))
            if len(group) == 1:
                sketch.moveGeometry(group[0][0], group[0][1], local)
            else:
                sketch.moveGeometries(list(group), local)

        semantic_id = "_".join("G{}P{}".format(*item) for item in group)

        points.append(
            ContextualEditPoint(
                point=placement.multVec(sketch.getPoint(*key)),
                property_name="Geometry[{}].Point{}".format(*key),
                subelement=semantic_id,
                get_value=get_value,
                apply_value=apply_value,
                semantic_id=semantic_id,
                available=lambda sketch=sketch, geometry_index=geometry_index: (
                    not sketch.FullyConstrained
                    and not any(
                        constraint.Type == "Block" and constraint.First == geometry_index
                        for constraint in sketch.Constraints
                    )
                ),
            )
        )
    return tuple(points)


def _coincident_groups(keys, constraints):
    """Coalesce Sketch endpoints joined by explicit coincidence constraints."""

    parents = {key: key for key in keys}

    def root(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    for constraint in constraints:
        if constraint.Type != "Coincident":
            continue
        first = (constraint.First, constraint.FirstPos)
        second = (constraint.Second, constraint.SecondPos)
        if first in parents and second in parents:
            parents[root(second)] = root(first)

    grouped = {}
    for key in keys:
        grouped.setdefault(root(key), []).append(key)
    return tuple(tuple(group) for group in grouped.values())
