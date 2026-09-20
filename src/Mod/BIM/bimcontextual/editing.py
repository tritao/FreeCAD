# SPDX-License-Identifier: LGPL-2.1-or-later

"""Context- and constraint-projected editing of semantic BIM handles."""

from contextlib import nullcontext
from dataclasses import dataclass

import FreeCAD
import ArchRepresentation
from ArchRepresentation import (
    BIMEditTransaction,
    BIMEditValidation,
    project_to_representation_plane,
)


def _handle_value(handle):
    return handle.operation.get_value(handle.source)


@dataclass(frozen=True)
class BIMEditPreview:
    """Non-persistent result of projecting a pointer onto a semantic handle."""

    handle: object
    value: object
    point: object
    validation: object = None


@dataclass(frozen=True)
class BIMEditResult:
    """Structured outcome of a semantic edit commit."""

    success: bool
    preview: object = None
    reason: str = ""
    impact: object = None

    @property
    def value(self):
        return getattr(self.preview, "value", None)

    @property
    def point(self):
        return getattr(self.preview, "point", None)


class BIMContextualHandleEditor:
    """One active semantic-handle drag, independent of Coin and Qt."""

    def __init__(self, request, refresh=None):
        self.request = request
        self.refresh = refresh
        self.handle = None
        self.start_value = None

    def begin(self, handle):
        if handle is None or (
            handle.constraint is None and handle.interaction not in {"Linear", "Planar"}
        ):
            raise ValueError("Unsupported BIM edit handle")
        validation = handle.operation.validate(handle.source)
        if not validation.allowed:
            raise ValueError(validation.reason)
        if (
            handle.constraint is None
            and handle.interaction == "Linear"
            and handle.direction.Length <= 1e-9
        ):
            raise ValueError("BIM edit handle has no direction")
        if handle.operation.value_kind != "Point" and handle.direction.Length <= 1e-9:
            raise ValueError("BIM edit handle has no value direction")
        self.handle = handle
        self.start_value = _handle_value(handle)
        return self.preview(handle.point)

    def preview(self, pointer):
        if self.handle is None:
            raise RuntimeError("No BIM edit handle is active")
        if self.handle.constraint is not None:
            projected = self.handle.constraint.project(pointer)
            if projected is None:
                validation = BIMEditValidation(
                    False,
                    "The pointer ray does not resolve on this edit constraint.",
                )
                return BIMEditPreview(
                    self.handle,
                    self.start_value,
                    self.handle.point,
                    validation,
                )
            if self.handle.operation.value_kind == "Point":
                value = self.start_value + projected - self.handle.point
                validation = self.handle.operation.validate(self.handle.source, value)
                return BIMEditPreview(self.handle, value, projected, validation)
        else:
            projected = project_to_representation_plane(pointer, self.request)
            if self.handle.interaction == "Planar":
                value = self.start_value + projected - self.handle.point
                validation = self.handle.operation.validate(self.handle.source, value)
                return BIMEditPreview(self.handle, value, projected, validation)
        delta = (projected - self.handle.point).dot(self.handle.direction)
        value = self.start_value + delta * self.handle.operation.sensitivity
        point = self.handle.point + self.handle.direction * delta
        validation = self.handle.operation.validate(self.handle.source, value)
        return BIMEditPreview(self.handle, value, point, validation)

    def preview_value(self, value):
        """Preview an exact scalar without routing it through pointer input."""

        if self.handle is None:
            raise RuntimeError("No BIM edit handle is active")
        if self.handle.operation.value_kind != "Scalar":
            raise ValueError("This handle does not accept a scalar value.")
        value = float(value)
        validation = self.handle.operation.validate(self.handle.source, value)
        sensitivity = float(self.handle.operation.sensitivity)
        point = self.handle.point
        if abs(sensitivity) > 1e-12:
            point = point + self.handle.direction * (
                (value - float(self.start_value)) / sensitivity
            )
        return BIMEditPreview(self.handle, value, point, validation)

    def cancel(self):
        self.handle = None
        self.start_value = None

    def commit(self, pointer):
        preview = self.preview(pointer)
        handle = preview.handle
        if not preview.validation.allowed:
            raise ValueError(preview.validation.reason)
        impact = handle.operation.get_impact(handle.source, preview.value)
        try:
            self._commit_value(handle, preview.value, impact)
            if callable(self.refresh):
                self.refresh(handle.source)
        finally:
            self.cancel()
        return BIMEditResult(True, preview=preview, impact=impact)

    @staticmethod
    def _commit_value(handle, value, impact=None, trace_scope=None):
        obj = handle.source
        doc = getattr(obj, "Document", None) or FreeCAD.ActiveDocument
        operation = handle.operation
        phase = trace_scope or (lambda _name: nullcontext())
        if operation.manages_transaction:
            with phase("contextual_edit_apply"):
                operation.apply(obj, value)
            return
        with BIMEditTransaction(doc, operation.label):
            with phase("contextual_edit_apply"):
                operation.apply(obj, value)
            if doc is not None:
                with phase("contextual_edit_recompute"):
                    _recompute_edit_impact(doc, impact)


def _recompute_edit_impact(doc, impact):
    """Recompute an edit through FreeCAD's dependency-aware document path."""

    plan = getattr(impact, "recompute", None)
    if plan is None:
        doc.recompute()
        return
    doc.recompute(tuple(target for target in plan.roots if target is not None))


class ContextualEditController:
    """Coordinate one contextual edit using injected view and input services.

    The controller owns handle state and preview/commit/cancel behavior. It
    deliberately knows nothing about Plan Edit sessions, selection, Draft, or
    a particular renderer implementation.
    """

    def __init__(
        self,
        view,
        representation_request,
        renderer,
        input_adapter=None,
        *,
        refresh_callback=None,
        refresh_failure_callback=None,
        feedback_callback=None,
        clear_feedback_callback=None,
        commit_scope=None,
        trace_scope=None,
    ):
        self.view = view
        self.request = getattr(representation_request, "request", representation_request)
        self.renderer = renderer
        self.input_adapter = input_adapter
        self.refresh_callback = refresh_callback
        self.refresh_failure_callback = refresh_failure_callback
        self.feedback_callback = feedback_callback
        self.clear_feedback_callback = clear_feedback_callback
        self.commit_scope = commit_scope or (lambda _impact: nullcontext())
        self.trace_scope = trace_scope
        self.editor = None

    @property
    def active_edit(self):
        return self.editor.handle if self.editor is not None else None

    def begin(self, handle):
        self.editor = BIMContextualHandleEditor(
            self.request,
            refresh=self.refresh_callback,
        )
        try:
            preview = self.editor.begin(handle)
        except Exception as exc:
            self.editor = None
            self._set_feedback(exc)
            return BIMEditResult(False, reason=str(exc))
        self._clear_feedback()
        self._call_renderer("set_handle_state", handle, "active")
        return preview

    def preview(self, pointer):
        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        preview = self.editor.preview(pointer)
        return self._render_preview(preview)

    def preview_value(self, value):
        """Preview an exact scalar through the active semantic operation."""

        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        return self._render_preview(self.editor.preview_value(value))

    def _render_preview(self, preview):
        self._call_renderer("preview_handle", preview.handle, preview.point)
        state = "active" if preview.validation.allowed else "invalid"
        self._call_renderer("set_handle_state", preview.handle, state)
        preview_state = preview.handle.operation.get_preview(
            preview.handle.source,
            preview.value,
            self.editor.request,
        )
        preview_state = ArchRepresentation.expand_preview_dependents(
            preview_state, self.editor.request
        )
        source = preview.handle.source
        if preview_state is not None:
            self._call_renderer(
                "set_preview_state",
                preview_state,
                preview.validation.allowed,
            )
        else:
            self._call_renderer("clear_preview", source)
        label = preview.handle.operation.get_preview_label(
            source,
            preview.value,
            self.editor.request,
        )
        if label:
            self._call_renderer(
                "set_edit_label",
                source,
                label,
                preview.point,
                preview.validation.allowed,
            )
        return preview

    def commit(self, pointer):
        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        handle = self.editor.handle
        editor = self.editor
        preview = editor.preview(pointer)
        try:
            if not preview.validation.allowed:
                raise ValueError(preview.validation.reason)
            impact = handle.operation.get_impact(handle.source, preview.value)
            with self.commit_scope(impact):
                BIMContextualHandleEditor._commit_value(
                    handle, preview.value, impact, self.trace_scope
                )
                if callable(self.refresh_callback):
                    phase = self.trace_scope or (lambda _name: nullcontext())
                    with phase("contextual_edit_presentation_refresh"):
                        self.refresh_callback(handle.source, impact)
            editor.cancel()
            self._clear_feedback()
            return BIMEditResult(True, preview=preview, impact=impact)
        except Exception as exc:
            self._set_feedback(exc)
            if callable(self.refresh_failure_callback):
                self.refresh_failure_callback(handle.source)
            return BIMEditResult(False, preview=preview, reason=str(exc))
        finally:
            self._call_renderer("clear_preview", handle.source)
            self.editor = None

    def commit_value(self, value):
        """Commit an exact scalar value through the active handle operation."""

        if self.editor is None:
            raise RuntimeError("No BIM edit handle is active")
        handle = self.editor.handle
        if handle.operation.value_kind != "Scalar":
            return BIMEditResult(False, reason="This handle does not accept a scalar value.")
        preview = self.preview_value(value)
        if not preview.validation.allowed:
            reason = preview.validation.reason or "This value is not allowed."
            self._set_feedback(reason)
            return BIMEditResult(False, preview=preview, reason=reason)
        editor = self.editor
        impact = handle.operation.get_impact(handle.source, preview.value)
        try:
            with self.commit_scope(impact):
                BIMContextualHandleEditor._commit_value(
                    handle, preview.value, impact, self.trace_scope
                )
                if callable(editor.refresh):
                    phase = self.trace_scope or (lambda _name: nullcontext())
                    with phase("contextual_edit_presentation_refresh"):
                        editor.refresh(handle.source, impact)
            editor.cancel()
            self._clear_feedback()
            return BIMEditResult(True, preview=preview, impact=impact)
        except Exception as exc:
            self._set_feedback(exc)
            if callable(self.refresh_failure_callback):
                self.refresh_failure_callback(handle.source)
            return BIMEditResult(False, preview=preview, reason=str(exc))
        finally:
            self._call_renderer("clear_preview", handle.source)
            self.editor = None

    def cancel(self, *, refresh=True):
        editor = self.editor
        handle = editor.handle if editor is not None else None
        if editor is not None:
            editor.cancel()
        self.editor = None
        if handle is not None:
            self._call_renderer("clear_preview", handle.source)
            if refresh and callable(self.refresh_failure_callback):
                self.refresh_failure_callback(handle.source)

    def activate(self, handle):
        """Start an immediate edit or delegate pointer input to the adapter."""

        self.cancel()
        if handle.interaction == "Immediate":
            validation = handle.operation.validate(handle.source)
            if not validation.allowed:
                self._set_feedback(validation.reason)
                return False
            try:
                value = handle.operation.get_value(handle.source)
                impact = handle.operation.get_impact(handle.source, value)
                with self.commit_scope(impact):
                    BIMContextualHandleEditor._commit_value(
                        handle, value, impact, self.trace_scope
                    )
                    if callable(self.refresh_callback):
                        phase = self.trace_scope or (lambda _name: nullcontext())
                        with phase("contextual_edit_presentation_refresh"):
                            self.refresh_callback(handle.source, impact)
                self._call_renderer("sync_visible_handles")
                self._clear_feedback()
                return True
            except Exception as exc:
                self._set_feedback(exc)
                return False
        if self.input_adapter is None:
            self._set_feedback("No input adapter is available for this BIM edit.")
            return False
        started = self.begin(handle)
        if isinstance(started, BIMEditResult) and not started.success:
            return False
        try:
            self.input_adapter.start_point_pick(
                handle.point,
                self._finish_point_pick,
                self._preview_point_pick,
                "Edit {}".format(handle.role),
            )
        except Exception:
            self.cancel()
            raise
        return True

    def _preview_point_pick(self, point=None, input_info=None):
        del input_info
        if point is not None and self.editor is not None:
            self.preview(point)

    def _finish_point_pick(self, point=None, input_info=None):
        del input_info
        editor = self.editor
        target = None if point is None else FreeCAD.Vector(point)

        def finish_after_event():
            try:
                if self.editor is not editor:
                    return
                if target is None:
                    self.cancel()
                else:
                    self.commit(target)
            finally:
                self.input_adapter.clear()

        if not self.input_adapter.defer(
            ("finish-contextual-handle", id(editor)), finish_after_event
        ):
            self.cancel()
            self.input_adapter.clear()

    def _call_renderer(self, method, *args):
        callback = getattr(self.renderer, method, None)
        if callable(callback):
            return callback(*args)
        return None

    def _set_feedback(self, error):
        message = str(error or "").strip() or "BIM contextual edit failed."
        if callable(self.feedback_callback):
            self.feedback_callback(message)

    def _clear_feedback(self):
        if callable(self.clear_feedback_callback):
            self.clear_feedback_callback()
