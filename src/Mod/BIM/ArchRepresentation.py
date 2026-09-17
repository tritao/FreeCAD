# SPDX-License-Identifier: LGPL-2.1-or-later

"""Renderer-neutral contextual BIM representations.

The classes in this module describe *what* an architectural object should
provide for a request.  They intentionally do not know about Coin, Qt or a
document view.  GUI and documentation consumers can therefore request the
same semantic geometry without creating converted document objects.
"""

from dataclasses import dataclass
from enum import Enum

import FreeCAD


class RepresentationUnavailable(LookupError):
    """Raised when a provider cannot represent an object in a request."""


class RepresentationPurpose(Enum):
    """Architectural intent of a representation request."""

    MODEL = "Model"
    PLAN = "Plan"
    SECTION = "Section"
    ELEVATION = "Elevation"


class BIMPreviewStyle(Enum):
    """Renderer-neutral presentation intent for transient semantic geometry."""

    AVAILABLE = "Available"
    EMPHASIZED = "Emphasized"
    MUTED = "Muted"
    INVALID = "Invalid"


class RepresentationRequest:
    """GUI-independent inputs used to derive a BIM representation.

    ``reference_frame`` is an arbitrary object supplied by the caller (in
    FreeCAD this is normally an ``App.Placement``).  Distances are measured
    on that frame's local Z axis.  The request contains no renderer state and
    is safe to pass to headless representation providers.
    """

    def __init__(
        self,
        purpose=RepresentationPurpose.MODEL,
        reference_frame=None,
        cut_range=None,
        projection_range=None,
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
        self.source = source
        self.cut_offset = cut_offset
        self.target_offset = target_offset


class RepresentationSource:
    """Semantic origin of one piece of transient representation geometry."""

    def __init__(self, geometry, source, role, subelement=None, related_sources=()):
        self.geometry = geometry
        self.source = source
        self.role = role
        self.subelement = subelement
        self.related_sources = tuple(related_sources or ())


@dataclass(frozen=True)
class BIMPreviewEntry:
    representation: object
    replace_committed: bool = False
    affects_spatial_boundary: bool = True
    style: BIMPreviewStyle = BIMPreviewStyle.AVAILABLE


class BIMPreviewState:
    """Renderer-neutral, coordinated representation state for one live edit.

    Entries marked as replacements temporarily stand in for the committed
    representation of their semantic source.  Other entries are overlays.
    The document model is never mutated while this state is being evaluated.
    """

    def __init__(self, primary_source=None):
        self.primary_source = primary_source
        self._entries = []

    def add_representation(
        self,
        representation,
        *,
        replace_committed=False,
        affects_spatial_boundary=True,
        style=BIMPreviewStyle.AVAILABLE,
    ):
        if not isinstance(representation, BIMRepresentation):
            raise TypeError("preview entries must be BIMRepresentation instances")
        if not isinstance(style, BIMPreviewStyle):
            style = BIMPreviewStyle(style)
        self._entries.append(
            BIMPreviewEntry(
                representation,
                bool(replace_committed),
                bool(affects_spatial_boundary),
                style,
            )
        )
        return representation

    @property
    def entries(self):
        return tuple(self._entries)

    @property
    def sources(self):
        return tuple(entry.representation.source for entry in self._entries)

    def representation_for(self, source):
        return next(
            (
                entry.representation
                for entry in reversed(self._entries)
                if entry.representation.source is source
            ),
            None,
        )

    def entry_for(self, source):
        return next(
            (entry for entry in reversed(self._entries) if entry.representation.source is source),
            None,
        )


def preview_state_from_representation(
    representation,
    *,
    replace_committed=False,
    affects_spatial_boundary=True,
    style=BIMPreviewStyle.AVAILABLE,
):
    """Wrap one representation in the canonical semantic preview contract."""

    state = BIMPreviewState(primary_source=representation.source)
    state.add_representation(
        representation,
        replace_committed=replace_committed,
        affects_spatial_boundary=affects_spatial_boundary,
        style=style,
    )
    return state


def expand_preview_dependents(state, request):
    """Ask document objects to contribute representations dependent on a state."""

    if state is None or state.primary_source is None:
        return state
    document = getattr(state.primary_source, "Document", None)
    if document is None:
        return state
    existing = set(state.sources)
    for obj in getattr(document, "Objects", ()) or ():
        if obj in existing:
            continue
        provider = getattr(
            getattr(obj, "Proxy", None),
            "getDependentPreviewRepresentation",
            None,
        )
        if not callable(provider):
            continue
        representation = provider(obj, state, request)
        if representation is not None:
            state.add_representation(representation)
            existing.add(obj)
    return state


class BIMEditRay:
    """World-space pointer ray supplied by a 3D viewer input adapter."""

    def __init__(self, origin, direction):
        self.origin = FreeCAD.Vector(origin)
        self.direction = FreeCAD.Vector(direction)
        if self.direction.Length <= 1e-9:
            raise ValueError("BIM edit ray has no direction")
        self.direction.normalize()


class AxisConstraint:
    """Constrain an edit to an infinite world-space axis."""

    def __init__(self, origin, direction):
        self.origin = FreeCAD.Vector(origin)
        self.direction = FreeCAD.Vector(direction)
        if self.direction.Length <= 1e-9:
            raise ValueError("BIM edit axis has no direction")
        self.direction.normalize()

    def project(self, pointer):
        if isinstance(pointer, BIMEditRay):
            offset = pointer.origin - self.origin
            ray_axis_dot = pointer.direction.dot(self.direction)
            denominator = 1.0 - ray_axis_dot * ray_axis_dot
            if abs(denominator) <= 1e-10:
                return None
            ray_offset = pointer.direction.dot(offset)
            axis_offset = self.direction.dot(offset)
            ray_parameter = (ray_axis_dot * axis_offset - ray_offset) / denominator
            ray_parameter = max(0.0, ray_parameter)
            axis_parameter = axis_offset + ray_axis_dot * ray_parameter
            return self.origin + self.direction * axis_parameter
        point = FreeCAD.Vector(pointer)
        return self.origin + self.direction * (point - self.origin).dot(self.direction)


class PlaneConstraint:
    """Constrain an edit to a plane in world space."""

    def __init__(self, origin, normal):
        self.origin = FreeCAD.Vector(origin)
        self.normal = FreeCAD.Vector(normal)
        if self.normal.Length <= 1e-9:
            raise ValueError("BIM edit plane has no normal")
        self.normal.normalize()

    def project(self, pointer):
        if isinstance(pointer, BIMEditRay):
            denominator = pointer.direction.dot(self.normal)
            if abs(denominator) <= 1e-10:
                return None
            ray_parameter = (self.origin - pointer.origin).dot(self.normal) / denominator
            if ray_parameter < 0.0:
                return None
            return pointer.origin + pointer.direction * ray_parameter
        point = FreeCAD.Vector(pointer)
        return point - self.normal * (point - self.origin).dot(self.normal)


class WorkingPlaneConstraint(PlaneConstraint):
    """Plane constraint built from an origin/normal or a FreeCAD placement."""

    def __init__(self, origin, normal=None):
        if normal is None:
            frame = origin
            origin = frame.Base
            normal = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        super().__init__(origin, normal)


class BIMEditHandle:
    """Renderer-independent edit offered by a BIM object.

    ``constraint`` defines the geometric manifold that pointer input must
    follow.  ``interaction`` remains the compatibility mode for callers that
    still project pointer positions through a representation request.
    """

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
        glyph="Circle",
        glyph_size=9,
        icon_name="",
        constraint=None,
    ):
        self.source = source
        self.role = str(role)
        self.point = FreeCAD.Vector(point)
        self.direction = FreeCAD.Vector(direction)
        if self.direction.Length:
            self.direction.normalize()
        self.constraint = constraint
        if not self.direction.Length and isinstance(constraint, AxisConstraint):
            self.direction = FreeCAD.Vector(constraint.direction)
        self.operation = operation
        self.interaction = str(interaction)
        self.subelement = subelement
        self.minimum = minimum
        self.glyph = str(glyph)
        self.glyph_size = int(glyph_size)
        self.icon_name = str(icon_name)

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
        interaction_intent="",
        preview=None,
        preview_label=None,
        validator=None,
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
        self.interaction_intent = str(interaction_intent)
        self._preview = preview
        self._preview_label = preview_label
        self._validator = validator

    def get_preview(self, source, value, request):
        if not callable(self._preview):
            return None
        state = self._preview(source, value, request)
        if state is not None and not isinstance(state, BIMPreviewState):
            raise TypeError("preview must return BIMPreviewState")
        return state

    def get_preview_label(self, source, value, request):
        if not callable(self._preview_label):
            return ""
        return str(self._preview_label(source, value, request) or "")

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
        if value is not None and callable(self._validator):
            result = self._validator(source, value)
            if isinstance(result, BIMEditValidation):
                return result
            if not getattr(result, "allowed", bool(result)):
                return BIMEditValidation(
                    False,
                    str(getattr(result, "reason", "") or "This value is not allowed."),
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


class BIMEditTransaction:
    """Document transaction used by semantic BIM edits outside Plan Edit."""

    def __init__(self, document, label):
        self.document = document
        self.label = str(label or "").strip()
        self._opened = False

    def __enter__(self):
        if self.document is not None and self.label:
            self.document.openTransaction(self.label)
            self._opened = True
        return self

    def __exit__(self, exception_type, exception, traceback):
        del exception, traceback
        if not self._opened:
            return False
        if exception_type is None:
            self.document.commitTransaction()
        else:
            self.document.abortTransaction()
        return False


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

    def __init__(
        self,
        geometry,
        source,
        subelement=None,
        role=None,
        request=None,
        related_sources=(),
    ):
        self.geometry = geometry
        self.source = source
        self.subelement = subelement
        self.role = role
        self.request = request
        self.related_sources = tuple(related_sources or ())

    @property
    def sources(self):
        """Return every semantic object represented by this target."""

        return tuple(dict.fromkeys((self.source, *self.related_sources)))


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

    @property
    def sources(self):
        return self.target.sources


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


@dataclass(frozen=True)
class BIMFaceMesh:
    """Immutable world-space triangles shared by rendering and picking."""

    geometry: object
    vertices: tuple
    triangles: tuple


class BIMRepresentation:
    """Renderer-neutral geometry and identity for one BIM object."""

    _COLLECTIONS = ("cut_geometry", "projected_geometry", "snap_geometry")

    def __init__(self, source=None, request=None):
        self.source = source
        self.request = request
        self.cut_geometry = []
        self.projected_geometry = []
        self.snap_geometry = []
        self.source_mappings = []
        self.edit_handles = []
        self._face_meshes = {}
        self.analytic_model = None

    def add_geometry(self, collection, geometry, role, subelement=None, *, related_sources=()):
        """Add geometry to a named collection and preserve semantic mapping."""
        if collection not in self._COLLECTIONS:
            raise ValueError("unknown representation collection: %s" % collection)
        getattr(self, collection).append(geometry)
        if collection == "cut_geometry" and getattr(geometry, "ShapeType", "") == "Face":
            try:
                vertices, triangles = tessellate_face(geometry)
                self._face_meshes[id(geometry)] = BIMFaceMesh(
                    geometry,
                    tuple(FreeCAD.Vector(point) for point in vertices),
                    tuple(tuple(int(index) for index in triangle) for triangle in triangles),
                )
            except Exception:
                pass
        self.source_mappings.append(
            RepresentationSource(
                geometry,
                self.source,
                role,
                subelement=subelement,
                related_sources=related_sources,
            )
        )

    def face_mesh_for(self, geometry):
        return self._face_meshes.get(id(geometry))

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
                    request=self.request,
                    related_sources=mapping.related_sources,
                )


class BIMEditCapabilities:
    """Semantic edits offered by one object in a representation request.

    Unlike :class:`BIMRepresentation`, this value carries no replacement or
    picking geometry. Viewers that already render the source object can use it
    to display contextual handles without constructing a second representation.
    """

    def __init__(self, source=None, request=None):
        self.source = source
        self.request = request
        self.edit_handles = []

    def add_edit_handle(self, handle):
        if handle.source is None:
            handle.source = self.source
        self.edit_handles.append(handle)
        return handle


def project_to_representation_plane(point, request):
    """Project *point* onto the target plane of a representation request."""

    frame = getattr(request, "reference_frame", None)
    if frame is None:
        target_offset = getattr(request, "target_offset", None)
        if target_offset is None:
            return FreeCAD.Vector(point)
        return FreeCAD.Vector(point.x, point.y, target_offset)
    local_point = frame.inverse().multVec(FreeCAD.Vector(point))
    target_offset = getattr(request, "target_offset", None)
    if target_offset is not None:
        local_point.z = target_offset
    return frame.multVec(local_point)


def project_direction_to_representation_plane(direction, request):
    """Return a normalized global direction within the request output plane."""

    direction = FreeCAD.Vector(direction)
    frame = getattr(request, "reference_frame", None)
    if frame is not None:
        normal = frame.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        direction = direction - normal * direction.dot(normal)
    else:
        direction.z = 0.0
    if direction.Length <= 1e-9:
        return None
    direction.normalize()
    return direction


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


def query_representation_snap_candidates(representations, point, tolerance, request=None):
    """Return distance-ordered semantic targets, merging coincident identities."""

    query_point = (
        project_to_representation_plane(FreeCAD.Vector(point), request) if request else point
    )
    candidates = []
    for representation in representations or ():
        for target in representation.iter_snap_targets():
            candidate, distance = _nearest_snap_point(target.geometry, query_point)
            if candidate is None or distance > tolerance:
                continue
            duplicate = next(
                (result for result in candidates if result.point.isEqual(candidate, 1e-7)),
                None,
            )
            if duplicate is None:
                candidates.append(BIMSnapResult(candidate, target, distance))
                continue
            merged_sources = tuple(dict.fromkeys((*duplicate.target.sources, *target.sources)))
            prefer_target = (
                getattr(target.geometry, "ShapeType", "") == "Vertex"
                and getattr(duplicate.target.geometry, "ShapeType", "") != "Vertex"
            )
            primary = target if prefer_target else duplicate.target
            primary.related_sources = tuple(
                source for source in merged_sources if source is not primary.source
            )
            if prefer_target:
                duplicate.target = primary
                duplicate.distance = distance
    return tuple(
        sorted(
            candidates,
            key=lambda result: (
                getattr(result.target.geometry, "ShapeType", "") != "Vertex",
                result.distance,
            ),
        )
    )


def query_representation_snap(representations, point, tolerance, request=None):
    """Return the nearest deduplicated semantic target within ``tolerance``."""

    candidates = query_representation_snap_candidates(
        representations, point, tolerance, request=request
    )
    return candidates[0] if candidates else None


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
    parameter = (
        0.0
        if length_squared <= 1e-12
        else min(
            max(((cursor[0] - start[0]) * dx + (cursor[1] - start[1]) * dy) / length_squared, 0.0),
            1.0,
        )
    )
    x = start[0] + parameter * dx
    y = start[1] + parameter * dy
    return (x - cursor[0]) ** 2 + (y - cursor[1]) ** 2


def tessellate_face(geometry, deflection=0.25):
    """Return face triangles in document coordinates, including its placement."""

    vertices, triangles = geometry.tessellate(deflection)
    placement = getattr(geometry, "Placement", None)
    if placement is not None:
        vertices = [placement.multVec(FreeCAD.Vector(point)) for point in vertices]
    return vertices, triangles


def _screen_face_contains(geometry, cursor, project_point, mesh=None):
    if getattr(geometry, "ShapeType", "") != "Face":
        return False
    try:
        if mesh is None:
            vertices, triangles = tessellate_face(geometry)
        else:
            vertices, triangles = mesh.vertices, mesh.triangles
        projected = [project_point(point) for point in vertices]
    except Exception:
        return False
    for triangle in triangles:
        first, second, third = (projected[index] for index in triangle)
        denominator = (second[1] - third[1]) * (first[0] - third[0]) + (
            third[0] - second[0]
        ) * (first[1] - third[1])
        if abs(denominator) <= 1e-12:
            continue
        first_weight = (
            (second[1] - third[1]) * (cursor[0] - third[0])
            + (third[0] - second[0]) * (cursor[1] - third[1])
        ) / denominator
        second_weight = (
            (third[1] - first[1]) * (cursor[0] - third[0])
            + (first[0] - third[0]) * (cursor[1] - third[1])
        ) / denominator
        third_weight = 1.0 - first_weight - second_weight
        if min(first_weight, second_weight, third_weight) >= -1e-9:
            return True
    return False


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
                representation.request,
            )
            if _screen_face_contains(
                mapping.geometry,
                cursor,
                project_point,
                representation.face_mesh_for(mapping.geometry),
            ):
                # Coplanar contextual faces can overlap at wall joints. Coin
                # draws later representations on top, so keep the last face
                # hit to select the geometry the user actually sees.
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


def representation_for(obj, request):
    """Request a representation from the object's semantic provider.

    Provider lookup is deliberately capability-based: no BIM type names are
    inspected here. A Python proxy implementing ``getRepresentation(obj,
    request)`` owns the representation policy for that object.
    """
    provider = getattr(getattr(obj, "Proxy", None), "getRepresentation", None)
    if not callable(provider):
        raise RepresentationUnavailable(
            "BIM object does not provide getRepresentation(obj, request)"
        )
    representation = provider(obj, request)
    if not isinstance(representation, BIMRepresentation):
        raise TypeError("getRepresentation(obj, request) must return BIMRepresentation")
    return representation


def edit_capabilities_for(obj, request):
    """Request semantic edit capabilities without requesting display geometry."""

    provider = getattr(getattr(obj, "Proxy", None), "getEditCapabilities", None)
    if not callable(provider):
        raise RepresentationUnavailable(
            "BIM object does not provide getEditCapabilities(obj, request)"
        )
    capabilities = provider(obj, request)
    if not isinstance(capabilities, BIMEditCapabilities):
        raise TypeError("getEditCapabilities(obj, request) must return BIMEditCapabilities")
    if capabilities.source is None:
        capabilities.source = obj
    if capabilities.request is None:
        capabilities.request = request
    return capabilities
