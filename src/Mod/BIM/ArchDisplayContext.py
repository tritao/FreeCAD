# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# ***************************************************************************

"""Runtime display overrides shared by Arch view providers.

Display overrides are deliberately kept outside the document model.  A
container can temporarily replace the display of hosted objects while its
plan representation is active, without serializing or changing the hosted
objects' ordinary display state.
"""

import weakref

_active_contexts = weakref.WeakSet()
_context_order = 0


def _view_key(view_object):
    """Return a runtime key for a document view object."""

    obj = view_object.Object
    return (id(obj.Document), obj.Name)


def _contexts_for(key):
    """Return active contexts that contain *key*."""

    return [context for context in _active_contexts if context._active and key in context._states]


def is_overridden(view_object):
    """Return whether a view object is currently controlled by a context."""

    key = _view_key(view_object)
    return any(key in context._states for context in _active_contexts)


def reapply(view_object):
    """Reapply the highest-priority override for *view_object*."""

    key = _view_key(view_object)
    contexts = _contexts_for(key)
    if not contexts:
        return
    context = max(contexts, key=lambda item: item._order)
    if context._mutating:
        return
    context._apply_child(key)


class _ChildState:
    """Original display state shared by all contexts controlling one child."""

    def __init__(self, child, visibility, switch_index):
        self.child = child
        self.visibility = visibility
        self.switch_index = switch_index


class DisplayOverrideContext:
    """Scope temporary plan display overrides for a container.

    The context captures each child's ordinary state once, applies the
    Footprint-or-suppress policy while active, and restores the captured state
    when released.  If contexts overlap, the last active context wins and the
    original state is restored only after the final context releases the child.
    """

    def __init__(self, owner):
        self.owner = owner
        self._active = False
        self._host_visible = True
        self._mutating = False
        self._order = 0
        self._children = {}
        self._states = {}

    @property
    def is_active(self):
        """Return whether the context currently owns display overrides."""

        return self._active

    def activate(self, children, host_visible=True):
        """Apply plan display overrides to the current hosted children."""

        global _context_order

        desired = {_view_key(child.ViewObject): child for child in children}
        if not self._active:
            _context_order += 1
            self._order = _context_order
            self._active = True
            _active_contexts.add(self)
        self._host_visible = bool(host_visible)

        for key in list(self._children):
            if key not in desired:
                self._release_child(key)

        for key, child in desired.items():
            if key not in self._states:
                base_state = self._find_existing_base_state(key)
                if base_state is None:
                    child_view = child.ViewObject
                    base_state = (
                        bool(child_view.Visibility),
                        int(child_view.SwitchNode.whichChild.getValue()),
                    )
                self._states[key] = _ChildState(child, *base_state)
                self._children[key] = child
            if self._top_context(key) is self:
                self._apply_child(key)

    def clear(self, host_visible=True):
        """Release all overrides and restore the original child states."""

        if not self._active:
            return

        self._host_visible = bool(host_visible)
        self._active = False
        for key in list(self._states):
            self._release_child(key)
        self._states.clear()
        self._children.clear()
        _active_contexts.discard(self)

    def set_host_visibility(self, visible):
        """Keep hosted overrides consistent with the container visibility."""

        if not self._active:
            return
        self._host_visible = bool(visible)
        for key in self._states:
            if self._top_context(key) is self:
                self._apply_child(key)

    def _find_existing_base_state(self, key):
        """Find the original state captured by an already active context."""

        for context in _active_contexts:
            if context is self or not context._active or key not in context._states:
                continue
            state = context._states[key]
            return (state.visibility, state.switch_index)
        return None

    def _top_context(self, key):
        contexts = _contexts_for(key)
        return max(contexts, key=lambda item: item._order) if contexts else None

    def _release_child(self, key):
        state = self._states[key]
        self._children.pop(key, None)
        remaining = self._top_context(key)
        if remaining is not None and remaining is not self:
            remaining._apply_child(key)
        else:
            self._restore_child(state)
        self._states.pop(key, None)

    def _restore_child(self, state):
        """Restore a child's captured state without triggering host coupling."""

        child_view = state.child.ViewObject
        self._mutating = True
        try:
            switch_index = state.switch_index if self._host_visible and state.visibility else -1
            child_view.SwitchNode.whichChild = switch_index
        finally:
            self._mutating = False

    def _apply_child(self, key):
        """Apply this context's policy to one child."""

        state = self._states.get(key)
        if state is None:
            return
        child_view = state.child.ViewObject
        self._mutating = True
        try:
            if not self._host_visible or not state.visibility:
                child_view.SwitchNode.whichChild = -1
                return
            modes = child_view.listDisplayModes()
            switch_index = modes.index("Footprint") if "Footprint" in modes else -1
            child_view.SwitchNode.whichChild = switch_index
        finally:
            self._mutating = False
