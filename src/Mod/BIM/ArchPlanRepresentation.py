# SPDX-License-Identifier: LGPL-2.1-or-later

"""Headless plan geometry shared by BIM consumers.

This module intentionally contains only the small model-facing contract needed
by plan editing and Footprint display.  The geometry returned by proxy methods
is in document coordinates, matching ``obj.Shape`` after FreeCAD applies the
object placement.  Consumers should use the returned faces and edges directly
and must not apply ``obj.Placement`` again.  A view provider converts the
geometry back to local coordinates only because its Coin scenegraph applies
the object placement separately.

Proxy extension contract
------------------------

Objects that provide plan geometry implement::

    def getDefaultPlanContext(obj) -> PlanContext
    def getPlanRepresentation(obj, context) -> list[Part.Face]

The proxy owns object-specific geometry generation.  This module owns the
small wrapper, cache key, and cache; it does not import GUI or Coin modules.
Unsupported, missing, and invalid geometry is represented by an empty
``PlanRepresentation`` rather than an exception.
"""

PLAN_REPRESENTATION_VERSION = 1
MAX_CACHED_PLAN_REPRESENTATIONS = 2


def _placement_signature(placement):
    """Return a stable, hashable signature for a FreeCAD placement."""

    if placement is None:
        return None
    try:
        base = placement.Base
        return ((base.x, base.y, base.z), tuple(placement.Rotation.Q))
    except Exception:
        return None


def _property_value(obj, name, default=None):
    """Read a FreeCAD property without requiring a particular property type."""

    try:
        value = getattr(obj, name)
    except AttributeError:
        return default
    try:
        return value.Value
    except AttributeError:
        return value


def _context_source_signature(source):
    """Return the relevant storey state used by a plan context."""

    if source is None:
        return None
    properties = source.PropertiesList
    return (
        source.Name,
        _placement_signature(source.Placement),
        _property_value(source, "LevelOffset") if "LevelOffset" in properties else None,
        _property_value(source, "PlanCutHeight") if "PlanCutHeight" in properties else None,
        _property_value(source, "IfcType") if "IfcType" in properties else None,
    )


class PlanContext:
    """Absolute plan cut and output elevation for derived geometry.

    ``cut_z`` is the document Z coordinate at which a solid is cut.
    ``target_z`` is the document Z coordinate of the returned planar faces.
    ``source`` is optional metadata, normally the Building Storey supplying
    the context.  It is included in the cache signature so storey changes
    replace derived geometry without scanning all document relationships.
    """

    def __init__(self, cut_z=None, target_z=None, source=None):
        self.cut_z = cut_z
        self.target_z = target_z
        self.source = source

    def signature(self):
        """Return the immutable values that define this context."""

        return (self.cut_z, self.target_z, _context_source_signature(self.source))


class PlanRepresentation:
    """Transient plan faces and their exact boundary edges."""

    def __init__(self, faces=None, context=None):
        self.faces = tuple(faces or ())
        self.edges = tuple(edge for face in self.faces for edge in face.Edges)
        self.context = context

    @property
    def isEmpty(self):
        return not self.faces


def _shape_signature(shape):
    """Return the compact geometry state used by the representation cache."""

    if shape is None:
        return None
    try:
        if shape.isNull():
            return None
        box = shape.BoundBox
        return (
            shape.hashCode(),
            shape.isValid(),
            (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax),
            _placement_signature(shape.Placement),
        )
    except Exception:
        return None


def get_plan_cache_signature(obj, context=None):
    """Return the compact cache key for one object/context pair.

    The key deliberately contains object shape and placement, IFC type,
    context signature, and the relevant storey placement/offset/cut values
    through ``PlanContext.source``.  Containment relationship scans do not
    belong in a hot geometry lookup; BuildingPart changes explicitly
    invalidate visible descendants when the relationship itself changes.
    """

    try:
        proxy = obj.Proxy
    except AttributeError:
        proxy = None
    if context is None and proxy is not None:
        context = proxy.getDefaultPlanContext(obj)
    try:
        shape = obj.Shape
    except AttributeError:
        shape = None
    try:
        placement = obj.Placement
    except AttributeError:
        placement = None
    return (
        PLAN_REPRESENTATION_VERSION,
        proxy.__class__.__name__ if proxy is not None else None,
        _shape_signature(shape),
        _placement_signature(placement),
        _property_value(obj, "IfcType"),
        context.signature() if context is not None else None,
    )


def _cached_representation(proxy, cache_key):
    """Return and promote a cached representation, if present."""

    try:
        cache = proxy._arch_plan_representation_cache
        if not isinstance(cache, dict):
            return None
        representation = cache.pop(cache_key)
    except (AttributeError, KeyError, TypeError):
        return None
    cache[cache_key] = representation
    return representation


def _cache_representation(proxy, cache_key, representation):
    """Store one representation in the bounded per-proxy LRU cache."""

    if cache_key is None:
        return
    try:
        cache = proxy._arch_plan_representation_cache
    except AttributeError:
        cache = None
    if not isinstance(cache, dict):
        cache = {}
    try:
        cache.pop(cache_key, None)
        cache[cache_key] = representation
        while len(cache) > MAX_CACHED_PLAN_REPRESENTATIONS:
            cache.pop(next(iter(cache)))
        proxy._arch_plan_representation_cache = cache
    except (AttributeError, TypeError, StopIteration):
        pass


def _empty(context, cache_key=None, proxy=None):
    """Create and optionally cache an empty representation."""

    representation = PlanRepresentation((), context)
    if proxy is not None:
        _cache_representation(proxy, cache_key, representation)
    return representation


def _is_valid_shape(obj):
    """Return false for missing, null, or invalid source geometry."""

    try:
        shape = obj.Shape
    except AttributeError:
        return False
    if shape is None:
        return False
    try:
        return not shape.isNull() and shape.isValid()
    except Exception:
        return False


def get_plan_representation(obj, context=None):
    """Return the cached neutral plan representation for ``obj``.

    The proxy's ``getPlanRepresentation`` method is the only geometry
    extension point.  This function resolves the default context, wraps the
    returned faces, and keeps that wrapper independent from any Coin cache.
    It is safe to call with no GUI, with Footprint mode inactive, or for an
    invisible object.
    """

    try:
        proxy = obj.Proxy
    except AttributeError:
        proxy = None
    if proxy is None:
        return PlanRepresentation((), context)

    if context is None:
        try:
            context = proxy.getDefaultPlanContext(obj)
        except Exception:
            return PlanRepresentation((), context)

    try:
        cache_key = get_plan_cache_signature(obj, context)
    except Exception:
        cache_key = None

    if cache_key is not None:
        cached = _cached_representation(proxy, cache_key)
        if cached is not None:
            return cached

    if not _is_valid_shape(obj):
        return _empty(context, cache_key, proxy)
    try:
        build_faces = proxy.getPlanRepresentation
    except AttributeError:
        return _empty(context, cache_key, proxy)
    if not callable(build_faces):
        return _empty(context, cache_key, proxy)

    try:
        faces = build_faces(obj, context)
        valid_faces = [face for face in (faces or ()) if face is not None and not face.isNull()]
    except Exception:
        return _empty(context, cache_key, proxy)

    try:
        representation = PlanRepresentation(valid_faces, context)
    except Exception:
        return _empty(context, cache_key, proxy)
    _cache_representation(proxy, cache_key, representation)
    return representation


def invalidate_plan_representation(obj):
    """Discard the neutral cache for ``obj`` without regenerating geometry."""

    try:
        proxy = obj.Proxy
    except AttributeError:
        proxy = None
    if proxy is not None:
        try:
            proxy._arch_plan_representation_cache = {}
        except Exception:
            pass
