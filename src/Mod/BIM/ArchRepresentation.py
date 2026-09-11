# SPDX-License-Identifier: LGPL-2.1-or-later

"""Renderer-neutral contextual BIM representations.

The classes in this module describe *what* an architectural object should
provide for a context.  They intentionally do not know about Coin, Qt or a
document view.  GUI and documentation consumers can therefore request the
same semantic geometry without creating converted document objects.
"""

from dataclasses import dataclass
from enum import Enum

import FreeCAD


class RepresentationUnavailable(LookupError):
    """Raised when a provider cannot represent an object in a context."""


class RepresentationPurpose(Enum):
    """Architectural intent of a representation request."""

    MODEL = "Model"
    PLAN = "Plan"
    SECTION = "Section"
    ELEVATION = "Elevation"


class RepresentationContext:
    """GUI-independent inputs used to derive a BIM representation.

    ``reference_frame`` is an arbitrary object supplied by the caller (in
    FreeCAD this is normally an ``App.Placement``).  Distances are measured
    on that frame's local Z axis.  The context contains no renderer state and
    is safe to pass to headless representation providers.
    """

    def __init__(
        self,
        purpose=RepresentationPurpose.MODEL,
        reference_frame=None,
        cut_range=None,
        projection_range=None,
        profile=None,
        source=None,
        *,
        cut_offset=None,
        target_offset=None,
    ):
        if not isinstance(purpose, RepresentationPurpose):
            purpose = RepresentationPurpose(purpose)
        self.purpose = purpose
        self.reference_frame = reference_frame
        self.cut_range = cut_range
        self.projection_range = projection_range
        self.profile = profile
        self.source = source
        self.cut_offset = cut_offset
        self.target_offset = target_offset


class RepresentationSource:
    """Semantic origin of one piece of transient representation geometry."""

    def __init__(self, geometry, source, role, subelement=None):
        self.geometry = geometry
        self.source = source
        self.role = role
        self.subelement = subelement


class BIMEditHandle:
    """Renderer-independent semantic interaction offered by a BIM object."""

    def __init__(
        self,
        source,
        role,
        point,
        direction,
        operation,
        *,
        interaction="Linear",
        subelement=None,
        minimum=0.0,
    ):
        self.source = source
        self.role = str(role)
        self.point = FreeCAD.Vector(point)
        self.direction = FreeCAD.Vector(direction)
        if self.direction.Length:
            self.direction.normalize()
        self.operation = operation
        self.interaction = str(interaction)
        self.subelement = subelement
        self.minimum = minimum

    @property
    def property_name(self):
        return getattr(self.operation, "property_name", "")


@dataclass(frozen=True)
class BIMEditValidation:
    allowed: bool
    reason: str = ""
    minimum: float | None = None
    maximum: float | None = None


class BIMEditOperation:
    """Typed semantic mutation used by a renderer-independent edit handle."""

    def __init__(
        self,
        key,
        label,
        get_value,
        apply_value,
        *,
        property_name="",
        manages_transaction=False,
        available=None,
        minimum=None,
        maximum=None,
        value_kind="Scalar",
        sensitivity=1.0,
    ):
        self.key = str(key)
        self.label = str(label)
        self._get_value = get_value
        self._apply_value = apply_value
        self.property_name = str(property_name)
        self.manages_transaction = bool(manages_transaction)
        self._available = available
        self.minimum = minimum
        self.maximum = maximum
        self.value_kind = str(value_kind)
        self.sensitivity = float(sensitivity)

    def is_available(self, source):
        return True if self._available is None else bool(self._available(source))

    def validate(self, source, value=None):
        if not self.is_available(source):
            return BIMEditValidation(False, "This value is controlled by a constraint.")
        if (
            value is not None
            and self.value_kind == "Scalar"
            and self.minimum is not None
            and value < self.minimum
        ):
            return BIMEditValidation(
                False,
                "Value must be at least {:g} mm.".format(self.minimum),
                minimum=self.minimum,
                maximum=self.maximum,
            )
        if (
            value is not None
            and self.value_kind == "Scalar"
            and self.maximum is not None
            and value > self.maximum
        ):
            return BIMEditValidation(
                False,
                "Value must be at most {:g} mm.".format(self.maximum),
                minimum=self.minimum,
                maximum=self.maximum,
            )
        return BIMEditValidation(True, minimum=self.minimum, maximum=self.maximum)

    def get_value(self, source):
        value = self._get_value(source)
        return FreeCAD.Vector(value) if self.value_kind == "Point" else float(value)

    def apply(self, source, value):
        validation = self.validate(source, value)
        if not validation.allowed:
            raise ValueError(validation.reason)
        if self.value_kind == "Point":
            return self._apply_value(source, FreeCAD.Vector(value))
        return self._apply_value(source, float(value))


def is_property_expression_driven(obj, property_name):
    """Return whether a document property path is controlled by an expression."""

    getter = getattr(obj, "getExpression", None)
    if callable(getter):
        try:
            return bool(getter(str(property_name)))
        except Exception:
            pass
    try:
        return any(
            str(path) == str(property_name)
            for path, _expression in (getattr(obj, "ExpressionEngine", ()) or ())
        )
    except Exception:
        return False


class BIMSnapTarget:
    """One renderer-independent semantic snapping candidate."""

    def __init__(self, geometry, source, subelement=None, role=None, context=None):
        self.geometry = geometry
        self.source = source
        self.subelement = subelement
        self.role = role
        self.context = context


class BIMSnapResult:
    """Nearest point and semantic identity returned by a snap query."""

    def __init__(self, point, target, distance):
        self.point = point
        self.target = target
        self.distance = distance

    @property
    def source(self):
        return self.target.source

    @property
    def subelement(self):
        return self.target.subelement

    @property
    def role(self):
        return self.target.role


class BIMPickResult:
    """Screen-space hit that retains semantic representation identity."""

    def __init__(self, target, distance_squared):
        self.target = target
        self.distance_squared = distance_squared

    @property
    def source(self):
        return self.target.source

    @property
    def subelement(self):
        return self.target.subelement

    @property
    def role(self):
        return self.target.role


class BIMRepresentation:
    """Renderer-neutral geometry and identity for one BIM object."""

    _COLLECTIONS = ("cut_geometry", "projected_geometry", "snap_geometry")

    def __init__(self, source=None, context=None):
        self.source = source
        self.context = context
        self.cut_geometry = []
        self.projected_geometry = []
        self.snap_geometry = []
        self.source_mappings = []
        self.edit_handles = []

    def add_geometry(self, collection, geometry, role, subelement=None):
        """Add geometry to a named collection and preserve semantic mapping."""
        if collection not in self._COLLECTIONS:
            raise ValueError("unknown representation collection: %s" % collection)
        getattr(self, collection).append(geometry)
        self.source_mappings.append(
            RepresentationSource(geometry, self.source, role, subelement=subelement)
        )

    def mapping_for(self, geometry):
        """Return the mapping for an exact generated geometry object, if any."""
        return next(
            (mapping for mapping in self.source_mappings if mapping.geometry is geometry),
            None,
        )

    def add_edit_handle(self, handle):
        if handle.source is None:
            handle.source = self.source
        self.edit_handles.append(handle)
        return handle

    def iter_snap_targets(self):
        snap_ids = {id(geometry) for geometry in self.snap_geometry}
        for mapping in self.source_mappings:
            if id(mapping.geometry) in snap_ids:
                yield BIMSnapTarget(
                    geometry=mapping.geometry,
                    source=mapping.source,
                    subelement=mapping.subelement,
                    role=mapping.role,
                    context=self.context,
                )


def _project_to_context_plane(point, context):
    frame = getattr(context, "reference_frame", None)
    if frame is None:
        target_offset = getattr(context, "target_offset", None)
        if target_offset is None:
            return FreeCAD.Vector(point)
        return FreeCAD.Vector(point.x, point.y, target_offset)
    local_point = frame.inverse().multVec(FreeCAD.Vector(point))
    target_offset = getattr(context, "target_offset", None)
    if target_offset is not None:
        local_point.z = target_offset
    return frame.multVec(local_point)


def _nearest_snap_point(geometry, point):
    shape_type = getattr(geometry, "ShapeType", "")
    if shape_type == "Vertex":
        candidate = FreeCAD.Vector(geometry.Point)
        return candidate, candidate.distanceToPoint(point)
    if shape_type == "Edge":
        import Part

        try:
            distance, point_pairs, _info = geometry.distToShape(Part.Vertex(point))
            if point_pairs:
                return FreeCAD.Vector(point_pairs[0][0]), float(distance)
        except Exception:
            return None, None
    if isinstance(geometry, (tuple, list)):
        points = [FreeCAD.Vector(value) for value in geometry]
        winner = None
        for start, end in zip(points, points[1:]):
            direction = end.sub(start)
            length_squared = direction.dot(direction)
            parameter = 0.0
            if length_squared > 1e-18:
                parameter = min(max(point.sub(start).dot(direction) / length_squared, 0.0), 1.0)
            candidate = start.add(direction.multiply(parameter))
            distance = candidate.distanceToPoint(point)
            if winner is None or distance < winner[1]:
                winner = candidate, distance
        return winner or (None, None)
    return None, None


def query_representation_snap(representations, point, tolerance, context=None):
    """Return the nearest semantic representation target within ``tolerance``."""

    query_point = _project_to_context_plane(FreeCAD.Vector(point), context) if context else point
    winner = None
    for representation in representations or ():
        for target in representation.iter_snap_targets():
            candidate, distance = _nearest_snap_point(target.geometry, query_point)
            if candidate is None or distance > tolerance:
                continue
            prefer_vertex = (
                winner is not None
                and abs(distance - winner.distance) <= 1e-9
                and getattr(target.geometry, "ShapeType", "") == "Vertex"
                and getattr(winner.target.geometry, "ShapeType", "") != "Vertex"
            )
            if winner is None or distance < winner.distance or prefer_vertex:
                winner = BIMSnapResult(candidate, target, distance)
    return winner


def _iter_pick_polylines(geometry):
    shape_type = getattr(geometry, "ShapeType", "")
    if shape_type == "Vertex":
        yield (FreeCAD.Vector(geometry.Point),)
    elif shape_type == "Edge":
        try:
            yield tuple(FreeCAD.Vector(point) for point in geometry.discretize(Deflection=0.5))
        except Exception:
            yield tuple(FreeCAD.Vector(vertex.Point) for vertex in geometry.Vertexes)
    elif shape_type == "Face":
        for edge in geometry.Edges:
            yield from _iter_pick_polylines(edge)
    elif isinstance(geometry, (tuple, list)):
        yield tuple(FreeCAD.Vector(point) for point in geometry)


def _screen_segment_distance_squared(cursor, start, end):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    parameter = 0.0 if length_squared <= 1e-12 else min(
        max(((cursor[0] - start[0]) * dx + (cursor[1] - start[1]) * dy) / length_squared, 0.0),
        1.0,
    )
    x = start[0] + parameter * dx
    y = start[1] + parameter * dy
    return (x - cursor[0]) ** 2 + (y - cursor[1]) ** 2


def _screen_face_contains(geometry, cursor, project_point):
    if getattr(geometry, "ShapeType", "") != "Face":
        return False
    inside = False
    for wire in geometry.Wires:
        try:
            polygon = [project_point(point) for point in wire.discretize(Deflection=0.5)]
        except Exception:
            continue
        if len(polygon) < 3:
            continue
        wire_contains = False
        previous = polygon[-1]
        for current in polygon:
            if (current[1] > cursor[1]) != (previous[1] > cursor[1]):
                crossing_x = previous[0] + (cursor[1] - previous[1]) * (
                    current[0] - previous[0]
                ) / (current[1] - previous[1])
                if cursor[0] < crossing_x:
                    wire_contains = not wire_contains
            previous = current
        if wire_contains:
            inside = not inside
    return inside


def query_representation_pick(representations, cursor, project_point, tolerance):
    """Return the nearest visible representation geometry in screen space."""

    cursor = float(cursor[0]), float(cursor[1])
    tolerance_squared = float(tolerance) ** 2
    winner = None
    for representation in representations or ():
        geometries = tuple(representation.projected_geometry) + tuple(representation.cut_geometry)
        geometry_ids = {id(geometry) for geometry in geometries}
        for mapping in representation.source_mappings:
            if id(mapping.geometry) not in geometry_ids:
                continue
            target = BIMSnapTarget(
                mapping.geometry,
                mapping.source,
                mapping.subelement,
                mapping.role,
                representation.context,
            )
            if _screen_face_contains(mapping.geometry, cursor, project_point):
                if winner is None:
                    winner = BIMPickResult(target, 0.0)
                continue
            for polyline in _iter_pick_polylines(mapping.geometry):
                try:
                    projected = [project_point(point) for point in polyline]
                except Exception:
                    continue
                if len(projected) == 1:
                    distance_squared = (projected[0][0] - cursor[0]) ** 2 + (
                        projected[0][1] - cursor[1]
                    ) ** 2
                else:
                    distance_squared = min(
                        _screen_segment_distance_squared(cursor, start, end)
                        for start, end in zip(projected, projected[1:])
                    )
                if distance_squared <= tolerance_squared and (
                    winner is None or distance_squared < winner.distance_squared
                ):
                    winner = BIMPickResult(target, distance_squared)
    return winner


def representation_for(obj, context):
    """Request a representation from the object's semantic provider.

    Provider lookup is deliberately capability-based: no BIM type names are
    inspected here. A Python proxy implementing ``getRepresentation(obj,
    context)`` owns the representation policy for that object.
    """
    provider = getattr(getattr(obj, "Proxy", None), "getRepresentation", None)
    if not callable(provider):
        raise RepresentationUnavailable(
            "BIM object does not provide getRepresentation(obj, context)"
        )
    representation = provider(obj, context)
    if not isinstance(representation, BIMRepresentation):
        raise TypeError("getRepresentation(obj, context) must return BIMRepresentation")
    return representation
