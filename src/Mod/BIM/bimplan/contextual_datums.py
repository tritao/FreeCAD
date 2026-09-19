# SPDX-License-Identifier: LGPL-2.1-or-later

"""Editable viewer datums backed by semantic contextual edit operations."""

import time
from dataclasses import dataclass

import FreeCAD


@dataclass(frozen=True)
class ContextualDatumSpec:
    """Declarative description of one editable contextual measurement."""

    key: str
    handle: object
    points: tuple
    value: float
    render_state: object
    value_to_operation: object = float
    label_type: str = "distance"
    label_mode: str = "dimensioning"
    color: tuple = (0.95, 0.45, 0.08)
    refresh_visuals: tuple = ()


@dataclass
class _ContextualDatumEntry:
    spec: object
    datum: object
    editing: bool = False


class PlanContextualDatumService:
    """Own the lifetime and edit bridge for keyed Plan Edit datums."""

    def __init__(self, session):
        self.session = session
        self._entries = {}
        self._active_key = None
        self._last_pointer_click = None

    def get(self, key):
        entry = self._entries.get(str(key))
        return entry.datum if entry is not None else None

    def sync(self, spec):
        key = str(spec.key)
        entry = self._entries.get(key)
        if entry is not None and entry.spec.render_state == spec.render_state:
            return entry.datum
        if entry is not None and entry.editing:
            return entry.datum
        self.clear(key)
        try:
            import FreeCADGui

            datum = FreeCADGui.EditableDatumLabel(
                self.session.view,
                FreeCAD.Placement(),
                color=spec.color,
                autoDistance=True,
            )
            datum.setLabelType(spec.label_type, spec.label_mode)
            datum.setPoints(*spec.points)
            datum.setSpinboxValue(float(spec.value))
            datum.setPickable(True)
            entry = _ContextualDatumEntry(spec, datum)
            self._entries[key] = entry
            datum.setValueChangedCallback(lambda value, key=key: self._preview(key, value))
            datum.setEditingFinishedCallback(lambda value, key=key: self.finish_edit(key, value))
            datum.setEditingCanceledCallback(lambda value, key=key: self.cancel_edit(key))
            datum.activate()
            return datum
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self.clear(key)
            return None

    def clear(self, key):
        key = str(key)
        entry = self._entries.pop(key, None)
        if entry is None:
            return
        if entry.editing and self.session.contextual_editing.editor is not None:
            self.session.contextual_editing.cancel(refresh=False)
        if self._active_key == key:
            self._active_key = None
        datum = entry.datum
        try:
            datum.setValueChangedCallback(None)
            datum.setEditingFinishedCallback(None)
            datum.setEditingCanceledCallback(None)
            datum.deactivate()
        except (AttributeError, RuntimeError):
            pass

    def clear_all(self):
        for key in tuple(self._entries):
            self.clear(key)
        self._last_pointer_click = None

    def handle_pointer_release(self, event_callback, mouse_pos):
        """Consume datum clicks and begin editing on a matching double-click."""

        try:
            picked_point = event_callback.getPickedPoint()
        except (AttributeError, ReferenceError, RuntimeError):
            return False
        if picked_point is None:
            return False
        key = next(
            (
                key
                for key, entry in self._entries.items()
                if entry.datum.containsPickedPoint(picked_point)
            ),
            None,
        )
        if key is None:
            self._last_pointer_click = None
            return False
        now = time.monotonic()
        position = tuple(mouse_pos) if mouse_pos is not None else None
        previous = self._last_pointer_click
        self._last_pointer_click = (key, now, position)
        if previous is None or previous[0] != key:
            return True
        interval = self._double_click_interval_seconds()
        if now - previous[1] > interval or not self._positions_match(previous[2], position):
            return True
        self._last_pointer_click = None
        self.begin_edit(key)
        return True

    @staticmethod
    def _double_click_interval_seconds():
        try:
            from PySide import QtWidgets

            application = QtWidgets.QApplication.instance()
            return max(0.1, float(application.doubleClickInterval()) / 1000.0)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return 0.5

    @staticmethod
    def _positions_match(first, second, tolerance=5.0):
        if first is None or second is None:
            return True
        return (
            abs(float(first[0]) - float(second[0])) <= tolerance
            and abs(float(first[1]) - float(second[1])) <= tolerance
        )

    def begin_edit(self, key):
        key = str(key)
        entry = self._entries.get(key)
        if entry is None or entry.editing or entry.datum.isInEdit():
            return
        if self._active_key is not None:
            self.cancel_edit(self._active_key)
        started = self.session.contextual_editing.begin(entry.spec.handle)
        if getattr(started, "success", True) is False:
            return
        entry.editing = True
        self._active_key = key
        entry.datum.startEdit(float(entry.spec.value), visibleToMouse=True)
        entry.datum.setFocusToSpinbox()

    def _operation_value(self, entry, value):
        return float(entry.spec.value_to_operation(float(value)))

    def _preview(self, key, value):
        entry = self._entries.get(key)
        if entry is None or not entry.editing or self.session.contextual_editing.editor is None:
            return
        try:
            self.session.contextual_editing.preview_value(self._operation_value(entry, value))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass

    def finish_edit(self, key, value):
        key = str(key)
        entry = self._entries.get(key)
        if (
            entry is None
            or not entry.editing
            or self._active_key != key
            or self.session.contextual_editing.editor is None
        ):
            return
        committed = self.session.contextual_editing.commit_value(
            self._operation_value(entry, value)
        )
        if not committed:
            entry.datum.resetLockedState()
            entry.datum.setFocusToSpinbox()
            return
        entry.editing = False
        self._active_key = None
        spec = entry.spec
        self.clear(key)
        self._queue_refresh(spec)

    def cancel_edit(self, key):
        key = str(key)
        entry = self._entries.get(key)
        if entry is None:
            return
        entry.editing = False
        if self._active_key == key:
            self._active_key = None
        self.session.contextual_editing.cancel()
        spec = entry.spec
        self.clear(key)
        self._queue_refresh(spec)

    def _queue_refresh(self, spec):
        if spec.refresh_visuals:
            self.session.overlays.queue_plan_overlay_visual_refresh(*spec.refresh_visuals)
