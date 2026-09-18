# SPDX-License-Identifier: LGPL-2.1-or-later

"""Document-owned renderer-neutral BIM representation cache."""

import FreeCAD
import weakref


_document_caches = {}
_document_derived_values = {}
_observer = None
_invalidation_listeners = weakref.WeakSet()
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
        key += (tuple(sorted(getattr(request, "presentation_profile", {}).items())),)
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


def get_or_create_derived_value(document, namespace, key, factory):
    """Reuse document-derived data until semantic geometry is invalidated."""

    if document is None:
        return factory()
    install_observer()
    cache = _document_derived_values.setdefault(_document_key(document), {})
    cache_key = (str(namespace), key)
    if cache_key not in cache:
        cache[cache_key] = factory()
    return cache[cache_key]


def invalidate_document(document):
    if document is not None:
        _document_caches.pop(_document_key(document), None)
        _document_derived_values.pop(_document_key(document), None)
        from . import representation_layers

        representation_layers.invalidate_document(document)


def invalidate_object(obj):
    document = getattr(obj, "Document", None)
    name = getattr(obj, "Name", None)
    if document is None or not name:
        return
    cache = _document_caches.get(_document_key(document))
    if cache is not None:
        for key in tuple(cache):
            if key[0] == name:
                cache.pop(key, None)
    _document_derived_values.pop(_document_key(document), None)
    from . import representation_layers

    representation_layers.invalidate_document(document)


def invalidate_for_object_change(obj, prop):
    """Invalidate cached representations affected by one document property."""

    try:
        if obj.isDerivedFrom("App::ViewDefinition"):
            return False
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    if str(prop or "") not in _GEOMETRY_PROPERTIES:
        return False
    invalidate_document(getattr(obj, "Document", None))
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
        invalidate_document(getattr(obj, "Document", None))

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
