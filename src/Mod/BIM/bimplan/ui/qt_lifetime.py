# SPDX-License-Identifier: LGPL-2.1-or-later

"""Qt object lifetime helpers for BIM Plan Edit UI."""

_PENDING_DELETE_OBJECTS = []


def _release_pending_delete_object(obj):
    try:
        _PENDING_DELETE_OBJECTS.remove(obj)
    except ValueError:
        pass


def _track_pending_delete_object(obj):
    if obj is None:
        return
    if obj in _PENDING_DELETE_OBJECTS:
        return
    _PENDING_DELETE_OBJECTS.append(obj)
    try:
        obj.destroyed.connect(lambda *_args, _obj=obj: _release_pending_delete_object(_obj))
    except (AttributeError, RuntimeError, TypeError):
        pass


def _iter_child_objects(obj):
    try:
        from PySide import QtCore
    except ImportError:
        return ()
    try:
        return tuple(obj.findChildren(QtCore.QObject))
    except (AttributeError, RuntimeError, TypeError):
        return ()


def delete_later(obj):
    """Schedule a Qt object for deletion while keeping its wrapper tree alive."""
    if obj is None:
        return
    for child in _iter_child_objects(obj):
        _track_pending_delete_object(child)
    _track_pending_delete_object(obj)
    try:
        obj.deleteLater()
    except (AttributeError, RuntimeError, TypeError):
        _release_pending_delete_object(obj)


def detach_widget(widget):
    if widget is None:
        return
    try:
        widget.hide()
    except (AttributeError, RuntimeError, TypeError):
        pass
    try:
        widget.setParent(None)
    except (AttributeError, RuntimeError, TypeError):
        pass
