# SPDX-License-Identifier: LGPL-2.1-or-later

"""Atomic refresh coordination for camera-dependent viewport decorations."""

from contextvars import ContextVar

import FreeCAD
import FreeCADGui

if FreeCAD.GuiUp:
    from PySide import QtCore


_ACTIVE_TRANSITION = ContextVar("bim_view_projection_transition", default=None)


class ViewportProjectionTransition:
    """Defer enlisted projection refreshes until a view transition completes."""

    def __init__(self):
        self._coordinators = set()
        self._token = None
        self._parent = None

    def __enter__(self):
        self._parent = _ACTIVE_TRANSITION.get()
        self._token = _ACTIVE_TRANSITION.set(self)
        return self

    def enlist(self, coordinator):
        self._coordinators.add(coordinator)

    def __exit__(self, _exc_type, _exc_value, _traceback):
        _ACTIVE_TRANSITION.reset(self._token)
        self._token = None
        if self._parent is not None:
            for coordinator in self._coordinators:
                self._parent.enlist(coordinator)
        else:
            for coordinator in tuple(self._coordinators):
                coordinator.commit_transition()
        self._coordinators.clear()
        self._parent = None


class ViewportProjectionCoordinator:
    """Refresh all viewport decorations from one coherent camera snapshot."""

    def __init__(self, session):
        self.session = session
        self._clients = []
        self._timer = None
        self._projection_key = None
        self._dirty = False

    def register(self, client, parent):
        if client not in self._clients:
            self._clients.append(client)
        if self._timer is None and FreeCAD.GuiUp:
            self._timer = QtCore.QTimer(parent)
            self._timer.setInterval(80)
            self._timer.timeout.connect(self.refresh_if_needed)
            self._timer.start()
        self.request_refresh()

    def unregister(self, client):
        if client in self._clients:
            self._clients.remove(client)

    def request_refresh(self):
        self._dirty = True
        for client in tuple(self._clients):
            client.invalidate_projection()
        transition = _ACTIVE_TRANSITION.get()
        if transition is not None:
            transition.enlist(self)
            return
        self.commit_transition()

    def commit_transition(self):
        if not self._dirty:
            return
        self._dirty = False
        self._projection_key = self._current_projection_key()
        for client in tuple(self._clients):
            client.refresh_projection()

    def refresh_if_needed(self):
        if self._current_projection_key() != self._projection_key:
            self.request_refresh()

    def close(self):
        if FreeCADGui.isValidQObject(self._timer):
            self._timer.stop()
        self._timer = None
        self._clients = []
        self._projection_key = None
        self._dirty = False

    def _current_projection_key(self):
        return self.session.viewport.get_plan_projection_cache_key()
