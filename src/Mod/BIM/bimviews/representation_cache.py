# SPDX-License-Identifier: LGPL-2.1-or-later

"""Document-owned renderer-neutral BIM representation cache."""

from contextlib import contextmanager
from contextvars import ContextVar
import weakref

import FreeCAD


_document_caches = {}
_document_derived_values = {}
_document_derived_dependencies = {}
_observer = None
_invalidation_listeners = weakref.WeakSet()
_derived_invalidation_scopes = ContextVar(
    "bim_derived_invalidation_scopes", default=()
)
_GEOMETRY_PROPERTIES = {
    "Shape",
    "Placement",
    "AttachmentOffset",
    "Base",
    "Support",
    "Host",
    "Hosts",
    "Group",
    "Objects",
    "Geometry",
    "Width",
    "Height",
    "Depth",
    "Length",
    "Align",
    "Offset",
    "EndingStart",
    "EndingEnd",
    "EndConditionOrderStart",
    "EndConditionOrderEnd",
    "Enabled",
    "JointType",
    "ButtTrimmed",
    "TeeStem",
    "EndA",
    "EndB",
    "WindowParts",
    "Opening",
    "SillHeight",
}


def _number_key(value):
    if value is None:
        return None
    try:
        return float(value.Value)
    except AttributeError:
        try:
            return float(value)
        except (TypeError, ValueError):
            return repr(value)


def _range_key(value):
    if value is None:
        return None
    try:
        return tuple(_number_key(item) for item in value)
    except TypeError:
        return repr(value)


def _frame_key(frame):
    if frame is None:
        return None
    try:
        matrix = frame.toMatrix()
        return tuple(round(float(value), 12) for value in matrix.A)
    except (AttributeError, TypeError):
        return repr(frame)


def representation_request_key(request, *, include_presentation=True):
    """Return a stable value key for renderer-independent request inputs."""

    if request is None:
        return None
    purpose = getattr(getattr(request, "purpose", None), "value", None)
    source = getattr(request, "source", None)
    source_key = (
        getattr(getattr(source, "Document", None), "Name", None),
        getattr(source, "Name", None),
    )
    key = (
        purpose,
        getattr(getattr(request, "representation_mode", None), "value", None),
        source_key,
        _frame_key(getattr(request, "reference_frame", None)),
        _number_key(getattr(request, "cut_offset", None)),
        _number_key(getattr(request, "target_offset", None)),
        _range_key(getattr(request, "cut_range", None)),
        _range_key(getattr(request, "projection_range", None)),
    )
    if include_presentation:
        key += (
            tuple(sorted(getattr(request, "presentation_profile", {}).items())),
            bool(getattr(request, "include_edit_handles", True)),
        )
    return key


def geometry_request_key(request):
    """Return a key for derived geometry, excluding renderer presentation."""

    return representation_request_key(request, include_presentation=False)


def _document_key(document):
    return id(document), getattr(document, "Name", None)


def get_cached_representation(obj, request):
    document = getattr(obj, "Document", None)
    name = getattr(obj, "Name", None)
    if document is None or not name:
        return None
    cache = _document_caches.get(_document_key(document))
    if cache is None:
        return None
    return cache.get((name, representation_request_key(request)))


def cache_representation(obj, request, representation):
    document = getattr(obj, "Document", None)
    name = getattr(obj, "Name", None)
    if document is None or not name or representation is None:
        return representation
    install_observer()
    cache = _document_caches.setdefault(_document_key(document), {})
    cache[(name, representation_request_key(request))] = representation
    return representation


def _dependency_key(obj):
    return getattr(obj, "Name", None) or id(obj)


def get_or_create_derived_value(
    document, namespace, key, factory, *, dependencies=()
):
    """Reuse document-derived data until semantic geometry is invalidated."""

    if document is None:
        return factory()
    install_observer()
    document_key = _document_key(document)
    cache = _document_derived_values.setdefault(document_key, {})
    dependency_cache = _document_derived_dependencies.setdefault(document_key, {})
    cache_key = (str(namespace), key)
    if cache_key not in cache:
        cache[cache_key] = factory()
        dependency_cache[cache_key] = frozenset(
            _dependency_key(obj) for obj in dependencies if obj is not None
        )
    return cache[cache_key]


def invalidate_document(document):
    if document is not None:
        _document_caches.pop(_document_key(document), None)
        _document_derived_values.pop(_document_key(document), None)
        _document_derived_dependencies.pop(_document_key(document), None)
        from . import representation_layers

        representation_layers.invalidate_document(document)


def invalidate_document_derived_values(document):
    """Discard document-wide lookup data without invalidating object drawings.

    Adding an object can change relationship and classification lookups, but it
    does not make the cached geometry of every existing object incorrect.  The
    new object is installed incrementally by an active contextual session.
    """

    if document is None:
        return
    document_key = _document_key(document)
    _document_derived_values.pop(document_key, None)
    _document_derived_dependencies.pop(document_key, None)


def invalidate_derived_values_for_objects(objects):
    """Discard derived values depending on any supplied semantic object.

    Entries without declared dependencies remain conservative and are removed.
    """

    objects_by_document = {}
    for obj in objects:
        document = getattr(obj, "Document", None)
        if document is not None:
            objects_by_document.setdefault(_document_key(document), set()).add(
                _dependency_key(obj)
            )
    for document_key, changed_keys in objects_by_document.items():
        cache = _document_derived_values.get(document_key)
        if cache is None:
            continue
        dependency_cache = _document_derived_dependencies.get(document_key, {})
        for cache_key in tuple(cache):
            dependencies = dependency_cache.get(cache_key)
            if not dependencies or dependencies.intersection(changed_keys):
                cache.pop(cache_key, None)
                dependency_cache.pop(cache_key, None)
        if not cache:
            _document_derived_values.pop(document_key, None)
            _document_derived_dependencies.pop(document_key, None)


@contextmanager
def scoped_derived_invalidation(objects):
    """Limit observer-driven derived invalidation to declared edit objects."""

    objects = tuple(obj for obj in objects if obj is not None)
    scopes = _derived_invalidation_scopes.get()
    token = _derived_invalidation_scopes.set((*scopes, objects))
    try:
        yield
    finally:
        _derived_invalidation_scopes.reset(token)


def _active_derived_invalidation_objects():
    scopes = _derived_invalidation_scopes.get()
    if not scopes:
        return None
    return scopes[-1]


def invalidate_object_representation(obj):
    """Invalidate only one object's renderer-independent drawing."""

    document = getattr(obj, "Document", None)
    name = getattr(obj, "Name", None)
    if document is None or not name:
        return
    cache = _document_caches.get(_document_key(document))
    if cache is not None:
        for key in tuple(cache):
            if key[0] == name:
                cache.pop(key, None)


def invalidate_object(obj):
    """Invalidate one object's drawing and related document-derived data."""

    document = getattr(obj, "Document", None)
    invalidate_object_representation(obj)
    invalidate_document_derived_values(document)


def invalidate_for_object_change(obj, prop):
    """Invalidate cached representations affected by one document property."""

    try:
        if obj.isDerivedFrom("App::ViewDefinition"):
            return False
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    if str(prop or "") not in _GEOMETRY_PROPERTIES:
        return False
    document = getattr(obj, "Document", None)
    name = getattr(obj, "Name", None)
    cache = (
        _document_caches.get(_document_key(document))
        if document is not None
        else None
    )
    if _derived_invalidation_scopes.get():
        invalidate_object_representation(obj)
        invalidate_derived_values_for_objects(
            _active_derived_invalidation_objects()
        )
        return True
    has_cached_representation = bool(
        name and cache and any(key[0] == name for key in cache)
    )
    if has_cached_representation:
        invalidate_document(document)
    else:
        # A newly constructed object has no installed representation to make
        # stale.  Preserve every existing drawing while discarding only the
        # document-wide relationship data that may include this object.
        invalidate_document_derived_values(document)
    return True


def add_invalidation_listener(listener):
    """Observe cache invalidations through the single document observer."""

    _invalidation_listeners.add(listener)
    install_observer()


def remove_invalidation_listener(listener):
    _invalidation_listeners.discard(listener)


def _notify_invalidation_listeners(method_name, *args):
    for listener in tuple(_invalidation_listeners):
        callback = getattr(listener, method_name, None)
        if callable(callback):
            callback(*args)


class _RepresentationCacheObserver:
    """Keep cached geometry valid while no Plan editing session exists."""

    @staticmethod
    def slotChangedObject(obj, prop):
        # Saved-view activation changes persistent selection metadata and camera
        # state but not model geometry.  Keeping this exception is what allows
        # MODEL -> PLAN -> MODEL -> PLAN to reuse the prepared representation.
        if invalidate_for_object_change(obj, prop):
            _notify_invalidation_listeners("representationCacheObjectInvalidated", obj)

    @staticmethod
    def slotCreatedObject(obj):
        if _derived_invalidation_scopes.get():
            invalidate_derived_values_for_objects(
                _active_derived_invalidation_objects()
            )
        else:
            invalidate_document_derived_values(getattr(obj, "Document", None))

    @staticmethod
    def slotDeletedObject(obj):
        invalidate_document(getattr(obj, "Document", None))

    @staticmethod
    def slotUndoDocument(document):
        invalidate_document(document)

    @staticmethod
    def slotRedoDocument(document):
        invalidate_document(document)

    @staticmethod
    def slotDeletedDocument(document):
        invalidate_document(document)


def install_observer():
    global _observer
    if _observer is None:
        _observer = _RepresentationCacheObserver()
        FreeCAD.addDocumentObserver(_observer)
